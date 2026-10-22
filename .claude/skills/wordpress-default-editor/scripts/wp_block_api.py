#!/usr/bin/env python3
"""
WordPress default block editor REST API helpers.
Reads credentials from environment: WP_USER, WP_APP_PASS, WP_SITE.
"""
import base64
import http.client
import json
import mimetypes
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


# --- Connection: fast fallback between address families ---
#
# socket.create_connection() gives *every* candidate address the full timeout,
# so a host that publishes an unroutable AAAA record stalls each request for
# the whole read timeout before urllib falls back to IPv4. That turns a normal
# `deploy.py all` into a run of many minutes that gets killed before it
# finishes -- and it looks like a slow server rather than a broken route,
# because curl and browsers hide the same misconfiguration behind Happy
# Eyeballs. urllib has no equivalent, so cap each connect attempt instead.

# Seconds to spend on any single address before moving to the next.
_CONNECT_TIMEOUT = float(os.environ.get("WP_CONNECT_TIMEOUT", "5"))

# (host, port) -> sockaddr that last answered, so the dead address costs one
# attempt per run rather than one per request.
_preferred_addr = {}

# Capping the per-address budget still pays that cap once per process, and each
# script (deploy, verify, upload) is its own process -- so a host whose AAAA is
# permanently unroutable costs a stall on every command. Set
# WP_ADDRESS_FAMILY=ipv4 to drop IPv6 candidates before connecting at all.
# Unset (the default) tries every address, which is what a healthy dual-stack
# host wants.
_ADDRESS_FAMILIES = {
    "": None,
    "auto": None,
    "any": None,
    "ipv4": socket.AF_INET,
    "v4": socket.AF_INET,
    "4": socket.AF_INET,
    "inet": socket.AF_INET,
    "ipv6": socket.AF_INET6,
    "v6": socket.AF_INET6,
    "6": socket.AF_INET6,
    "inet6": socket.AF_INET6,
}


def _address_family():
    """Family to pin connections to, or None to try every candidate."""
    raw = os.environ.get("WP_ADDRESS_FAMILY", "").strip().lower()
    try:
        return _ADDRESS_FAMILIES[raw]
    except KeyError:
        allowed = ", ".join(sorted(k for k in _ADDRESS_FAMILIES if k))
        raise ValueError(
            f"WP_ADDRESS_FAMILY={raw!r} is not recognised; use one of: {allowed}"
        ) from None


def _connect_any(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """Drop-in for socket.create_connection with a per-address connect budget.

    Signature matches HTTPConnection._create_connection so it can replace it
    wholesale; the returned socket carries the caller's timeout, not the short
    connect budget, so reads are unaffected.
    """
    host, port = address[0], address[1]
    read_timeout = (
        socket.getdefaulttimeout()
        if timeout is socket._GLOBAL_DEFAULT_TIMEOUT
        else timeout
    )
    attempt_timeout = _CONNECT_TIMEOUT
    if read_timeout is not None:
        attempt_timeout = min(attempt_timeout, read_timeout)

    pinned = _address_family()
    infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    if pinned is not None:
        infos = [info for info in infos if info[0] == pinned]
        if not infos:
            raise OSError(
                f"no {'ipv4' if pinned == socket.AF_INET else 'ipv6'} address for "
                f"{host}:{port} (WP_ADDRESS_FAMILY pins the family)"
            )
    preferred = _preferred_addr.get((host, port))
    if preferred is not None:  # stable sort: the known-good address goes first
        infos = sorted(infos, key=lambda info: info[4] != preferred)

    last_error = None
    for family, socktype, proto, _canonname, sockaddr in infos:
        sock = None
        try:
            sock = socket.socket(family, socktype, proto)
            sock.settimeout(attempt_timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            sock.settimeout(read_timeout)
            _preferred_addr[(host, port)] = sockaddr
            return sock
        except OSError as exc:
            last_error = exc
            if sock is not None:
                sock.close()
    raise last_error or OSError(f"no address for {host}:{port} could be reached")


class _FallbackHTTPConnection(http.client.HTTPConnection):
    # HTTPConnection.connect() calls self._create_connection(), so swapping the
    # factory keeps proxy tunnelling -- and, for the HTTPS subclass, the TLS
    # wrap -- exactly as the stdlib does them. Python 3.14 assigns
    # _create_connection as an *instance* attribute in __init__, which shadows
    # a class-level override, so it has to be set after super().__init__().
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_any


class _FallbackHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_any


class _FallbackHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_FallbackHTTPConnection, req)


class _FallbackHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_FallbackHTTPSConnection, req, context=self._context)


# build_opener drops the default handlers these subclass, so every request made
# through _opener gets the capped connect.
_opener = urllib.request.build_opener(_FallbackHTTPHandler, _FallbackHTTPSHandler)


def _site():
    return os.environ["WP_SITE"].rstrip("/")


def _headers(for_write=False):
    auth = base64.b64encode(
        f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASS']}".encode()
    ).decode()
    headers = {"Authorization": f"Basic {auth}", "User-Agent": "wp-default-editor/1.0"}
    if for_write:
        headers["Content-Type"] = "application/json"
    return headers


def _rest_base():
    """REST namespace prefix. Default assumes pretty permalinks; set WP_REST_ROOT
    to "index.php/wp-json" (or similar) for plain-permalink or route-restricted sites.
    When wp-json rewriting is broken (e.g. caching plugin), use "?rest_route="."""
    return os.environ.get("WP_REST_ROOT", "wp-json").strip("/")


def _request(method, path, data=None, retries=3):
    rest_base = _rest_base()
    if rest_base.startswith("?"):
        if "?" in path:
            route, qs = path.split("?", 1)
        else:
            route, qs = path, ""
        base_url = f"{_site()}/{rest_base}/wp/v2/{route}"
        url = f"{base_url}&{qs}" if qs else base_url
    else:
        url = f"{_site()}/{rest_base}/wp/v2/{path}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers=_headers(for_write=data is not None),
                method=method,
            )
            with _opener.open(req, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def fetch_raw(endpoint, pid):
    """Fetch raw block markup and status for a page/post."""
    return _request(
        "GET",
        f"{endpoint}/{pid}?context=edit&_fields=id,title,content,status",
    )


def save_content(endpoint, pid, new_content, status):
    """Write content back while preserving the original status."""
    payload = json.dumps({"content": new_content, "status": status}).encode()
    return _request("POST", f"{endpoint}/{pid}", data=payload)


def backup_dir():
    """Per-site backup directory so equal page ids on different sites don't collide.

    Keys on the full site URL (scheme, host, and path), so subdirectory multisite
    installs on one host and http/https variants each get a distinct directory.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]", "_", _site()) or "default"
    return os.path.join("/tmp/wp_backup", slug)


def _backup_key(endpoint, pid):
    """Filename-safe backup key. Prefixing the endpoint disambiguates equal ids
    across resource types (pages/10 vs posts/10) and sanitizes the slashes in
    template-part ids like 'theme//slug'."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", f"{endpoint}__{pid}")


def backup(endpoint, pid):
    """Fetch and back up content + status under backup_dir(), byte-for-byte."""
    data = fetch_raw(endpoint, pid)
    out_dir = backup_dir()
    os.makedirs(out_dir, exist_ok=True)
    key = _backup_key(endpoint, pid)
    with open(os.path.join(out_dir, f"{key}_original.txt"), "w", encoding="utf-8") as f:
        f.write(data["content"]["raw"])
    with open(os.path.join(out_dir, f"{key}_status.txt"), "w", encoding="utf-8") as f:
        f.write(data["status"])
    return data


def list_content(endpoint, search=None):
    """Paginate through all items on an endpoint."""
    results = []
    page = 1
    while True:
        query = f"{endpoint}?per_page=100&page={page}&context=edit&_fields=id,title,status,content"
        if search:
            query += f"&search={urllib.parse.quote(search)}"
        chunk = _request("GET", query)
        if not chunk:
            break
        results.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return results


def _block_re(block_type):
    return re.compile(
        r"<!-- wp:" + re.escape(block_type) + r'(\s[^>]*)? -->(.*?)<!-- /wp:' + re.escape(block_type) + r" -->",
        re.DOTALL,
    )


def _is_leaf_block(inner):
    """Return True when inner HTML contains no nested block comments."""
    return "<!-- wp:" not in inner


def find_blocks(content, block_type):
    """Return all serialized block strings of the given type."""
    return [m.group(0) for m in _block_re(block_type).finditer(content)]


def update_block_text(content, block_type, old_text, new_text):
    """Replace old_text with new_text inside the single matching leaf block.

    Refuses to act when old_text matches more than one block of the type, so an
    ambiguous target can never silently edit the wrong block.
    """
    if old_text == "":
        raise ValueError("old_text must not be empty")
    matches = [
        m for m in _block_re(block_type).finditer(content) if old_text in m.group(2)
    ]
    if not matches:
        raise ValueError(f"old_text not found in any {block_type} block")
    if len(matches) > 1:
        raise ValueError(
            f"old_text matches {len(matches)} {block_type} blocks; "
            "use a more specific old_text to disambiguate"
        )
    match = matches[0]
    inner = match.group(2)
    if not _is_leaf_block(inner):
        raise ValueError(f"refusing to edit non-leaf {block_type} block")
    new_inner = inner.replace(old_text, new_text, 1)
    return content[: match.start(2)] + new_inner + content[match.end(2) :]


def verify_only_text_changed(old, new, block_type, old_text, new_text=None):
    """Confirm that only the targeted block instance changed.

    Optionally checks that new_text appears in the updated block, and rejects
    changes that only mutate the block's opening-comment attributes.
    """
    if not old_text:
        raise ValueError("old_text must not be empty")
    old_blocks = find_blocks(old, block_type)
    new_blocks = find_blocks(new, block_type)
    if len(old_blocks) != len(new_blocks):
        return False

    target_index = None
    for i, block in enumerate(old_blocks):
        inner = _block_re(block_type).search(block).group(2)
        if old_text in inner:
            target_index = i
            break
    if target_index is None:
        return False

    old_attrs = _block_re(block_type).search(old_blocks[target_index]).group(1)
    new_attrs = _block_re(block_type).search(new_blocks[target_index]).group(1)
    if old_attrs != new_attrs:
        return False

    if old_blocks[target_index] == new_blocks[target_index]:
        return False

    if new_text is not None and new_text not in new_blocks[target_index]:
        return False

    sentinel = uuid.uuid4().hex

    def _replace_at_index(content, index):
        seen = [0]

        def replacer(match):
            if seen[0] == index:
                seen[0] += 1
                return sentinel
            seen[0] += 1
            return match.group(0)

        return _block_re(block_type).sub(replacer, content)

    return _replace_at_index(old, target_index) == _replace_at_index(new, target_index)


# --- Creating resources (reusable blocks / synced patterns) ---

def create_resource(endpoint, fields):
    """Create a new resource (e.g. a reusable block / synced pattern on 'blocks').

    Creation has no prior state to back up; make it reversible by checking
    find_by_slug() before creating and delete_resource() to undo.
    """
    return _request("POST", endpoint, data=json.dumps(fields).encode())


def find_by_slug(endpoint, slug):
    """Return the first item on endpoint matching slug, or None."""
    items = _request("GET", f"{endpoint}?slug={urllib.parse.quote(slug)}&context=edit")
    return items[0] if items else None


def delete_resource(endpoint, pid, force=True):
    """Delete a resource. Used to undo a create_resource()."""
    suffix = "?force=true" if force else ""
    return _request("DELETE", f"{endpoint}/{pid}{suffix}")


# --- Media library uploads ---


def find_media_by_filename(filename):
    """Return the newest media item whose source_url ends in filename, or None.

    Used to make upload_media() idempotent across re-runs: WordPress dedupes
    nothing on its own, it just appends '-1', '-2', ... to the filename.

    One filename can match several attachments -- uploading the same name while
    "organize uploads into month/year folders" is toggled leaves both
    uploads/2026/07/x.jpg and uploads/x.jpg -- and the caller usually goes on to
    delete what it finds, so the choice must not depend on whatever order the
    endpoint felt like returning. Pin the order, take the newest, and say so
    when the library is ambiguous.
    """
    stem = os.path.splitext(filename)[0]
    items = _request(
        "GET",
        f"media?search={urllib.parse.quote(stem)}&per_page=100"
        "&orderby=id&order=desc&context=edit",
    )
    matches = [
        i for i in items if i.get("source_url", "").rsplit("/", 1)[-1] == filename
    ]
    if not matches:
        return None
    matches.sort(key=lambda i: i["id"], reverse=True)  # newest first, regardless of API order
    if len(matches) > 1:
        ids = ", ".join(str(i["id"]) for i in matches)
        print(
            f"warning: {len(matches)} attachments are named {filename} (ids {ids}); "
            f"using {matches[0]['id']}. Delete the stale ones -- content referencing "
            "the others will not be updated.",
            file=sys.stderr,
        )
    return matches[0]


def upload_media(file_path, *, filename=None, alt_text=None, reuse_existing=True, retries=3):
    """Upload a local file to the WP media library. Returns the attachment record.

    Unlike _request(), POST /media takes the raw file body (not JSON): the file
    bytes go straight in the request body with Content-Type set to the file's
    mime type and the filename passed via Content-Disposition, per the REST
    media-endpoint contract.

    When reuse_existing (default), an existing attachment with the same
    filename is returned as-is instead of re-uploading, so re-running a deploy
    step is a no-op rather than accumulating duplicate uploads.
    """
    filename = filename or os.path.basename(file_path)
    if reuse_existing:
        existing = find_media_by_filename(filename)
        if existing:
            return existing

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(file_path, "rb") as fh:
        data = fh.read()

    url = f"{_site()}/{_rest_base()}/wp/v2/media"
    headers = _headers()
    headers["Content-Type"] = content_type
    headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with _opener.open(req, timeout=60) as response:
                result = json.loads(response.read())
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            raise

    if alt_text:
        result = _request(
            "POST", f"media/{result['id']}", data=json.dumps({"alt_text": alt_text}).encode()
        )
    return result


# --- Structural writes (full template part / page rebuilds) ---

_BLOCK_DELIM = re.compile(
    r"<!--\s*(?P<close>/)?wp:(?P<type>[a-z][a-z0-9-]*(?:/[a-z][a-z0-9-]*)?)"
    r"(?P<rest>.*?)(?P<self>/)?\s*-->",
    re.DOTALL,
)


def assert_balanced_blocks(content):
    """Raise ValueError if block-comment delimiters are unbalanced or mis-nested.

    Structural writes replace a whole tree, so 'only block N changed' can't be the
    check; instead confirm the new markup is well-formed before it is saved.
    """
    stack = []
    for m in _BLOCK_DELIM.finditer(content):
        btype = m.group("type")
        if m.group("self"):
            continue
        if m.group("close"):
            if not stack or stack[-1] != btype:
                raise ValueError(f"unbalanced block markup: unexpected closing wp:{btype}")
            stack.pop()
        else:
            stack.append(btype)
    if stack:
        unclosed = ", ".join("wp:" + t for t in stack)
        raise ValueError(f"unbalanced block markup: unclosed {unclosed}")
    return True


def save_structural(endpoint, pid, new_content, status, *, confirm):
    """Replace a resource's entire block tree (template part, full page rebuild).

    Unlike update_block_text, this does not preserve surrounding blocks, so it is
    gated: requires an existing backup, explicit confirm=True (human review), and a
    balanced-markup check. Roll back with rollback.py if the result is wrong.
    """
    if not confirm:
        raise ValueError("structural writes require confirm=True after human review")
    backup_path = os.path.join(backup_dir(), f"{_backup_key(endpoint, pid)}_original.txt")
    if not os.path.exists(backup_path):
        raise RuntimeError(
            f"no backup at {backup_path}; call backup({endpoint!r}, {pid!r}) first"
        )
    assert_balanced_blocks(new_content)
    return save_content(endpoint, pid, new_content, status)


# --- Global styles (theme.json design tokens via REST) ---
#
# Set the design system (layout widths, colour palette as real theme slugs,
# typography, custom properties) in the active theme's *user* global-styles
# record instead of injected CSS. This is what kills the per-section width/colour
# guessing on block themes: contentSize/wideSize and palette slugs become global.
# See references/block-theme-layout.md.


def _deep_merge(base, patch):
    """Recursively merge patch into base. Dicts merge key-by-key; every other
    value (including lists like a colour palette) replaces wholesale."""
    out = dict(base or {})
    for key, val in patch.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def discover_global_styles_id():
    """Return the editable user global-styles post id for the active theme.

    Read from the active theme's `wp:user-global-styles` REST link, never guessed
    (the id is install-specific). Requires context=edit auth.
    """
    themes = _request("GET", "themes?status=active&context=edit")
    theme = themes[0] if isinstance(themes, list) else themes
    link = (theme.get("_links") or {}).get("wp:user-global-styles")
    if not link:
        raise RuntimeError("active theme exposes no wp:user-global-styles link")
    return link[0]["href"].rstrip("/").split("/")[-1]


def get_global_styles(gid=None):
    """Fetch the user global-styles record (settings + styles). Discovers the id
    when not given. Note: WordPress nests *user* palette/font values under a
    `custom` origin key on read (e.g. settings.color.palette.custom)."""
    gid = gid or discover_global_styles_id()
    return _request("GET", f"global-styles/{gid}?context=edit")


def apply_global_styles(settings_patch=None, styles_patch=None, *, gid=None, confirm):
    """Deep-merge a theme.json-shaped patch into the user global-styles record.

    Site-wide write, so it is gated like save_structural: requires confirm=True
    and writes a full JSON backup of the current record first. Roll back by
    POSTing that backup file's {settings, styles} back to the same id.

    settings_patch / styles_patch mirror theme.json, e.g.
        settings={"layout": {"contentSize": "80rem", "wideSize": "90rem"},
                  "color": {"palette": [{"slug": "primary", "color": "#E2001A",
                                          "name": "Primary"}]}}
        styles={"typography": {"fontFamily": "var:preset|font-family|inter"}}
    """
    if not confirm:
        raise ValueError("global-styles writes require confirm=True after human review")
    gid = gid or discover_global_styles_id()
    current = _request("GET", f"global-styles/{gid}?context=edit")

    out_dir = backup_dir()
    os.makedirs(out_dir, exist_ok=True)
    backup_path = os.path.join(out_dir, f"global-styles__{gid}_original.json")
    with open(backup_path, "w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2)

    payload = json.dumps(
        {
            "settings": _deep_merge(current.get("settings") or {}, settings_patch or {}),
            "styles": _deep_merge(current.get("styles") or {}, styles_patch or {}),
        }
    ).encode()
    return _request("POST", f"global-styles/{gid}", data=payload)
