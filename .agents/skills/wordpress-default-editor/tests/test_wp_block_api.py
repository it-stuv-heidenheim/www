import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

import rollback as rb
import wp_block_api as api


@pytest.fixture(scope="module")
def mock_server():
    """Start the Flask mock server for the duration of the test module."""
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "scripts/mock_wp_server.py"],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(50):
        try:
            urllib.request.urlopen(
                "http://127.0.0.1:5001/wp-json/wp/v2/pages",
                timeout=1,
            )
            break
        except urllib.error.HTTPError:
            # Server responded (e.g. 401 unauthenticated) -> it is up.
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError("Mock server did not start")
    yield
    proc.terminate()
    proc.wait()


@pytest.fixture(autouse=True)
def restore_pages(request):
    """Snapshot mock page state and restore it after each server-backed test."""
    if "mock_server" not in request.fixturenames:
        yield
        return
    snapshot = {
        p["id"]: (p["content"]["raw"], p["status"])
        for p in api._request("GET", "pages?per_page=100&context=edit")
    }
    yield
    for pid, (raw, status) in snapshot.items():
        api.save_content("pages", pid, raw, status)


def test_fetch_raw_returns_blocks_and_status(mock_server):
    data = api.fetch_raw("pages", 1)
    assert data["id"] == 1
    assert data["status"] == "publish"
    assert "Welcome to our site" in data["content"]["raw"]


def test_backup_writes_content_and_status(mock_server):
    shutil.rmtree(api.backup_dir(), ignore_errors=True)
    api.backup("pages", 1)
    site_dir = api.backup_dir()
    with open(f"{site_dir}/pages__1_original.txt", encoding="utf-8") as f:
        assert "Welcome to our site" in f.read()
    with open(f"{site_dir}/pages__1_status.txt", encoding="utf-8") as f:
        assert f.read().strip() == "publish"
    # Namespaced by site: two sites with the same page id must not share a file.
    assert not os.path.exists("/tmp/wp_backup/pages__1_original.txt")


def test_backup_key_is_slash_safe_and_endpoint_scoped():
    key = api._backup_key("template-parts", "twentytwentyfive//header")
    assert "/" not in key
    assert key.startswith("template-parts__")
    assert api._backup_key("pages", 10) != api._backup_key("posts", 10)


def test_rest_base_honors_override(monkeypatch):
    monkeypatch.delenv("WP_REST_ROOT", raising=False)
    assert api._rest_base() == "wp-json"
    monkeypatch.setenv("WP_REST_ROOT", "/index.php/wp-json/")
    assert api._rest_base() == "index.php/wp-json"


def test_backup_dir_distinguishes_same_host_installs(monkeypatch):
    """Two installs on one host must not share a backup directory."""
    monkeypatch.setenv("WP_SITE", "https://example.com/blog")
    blog = api.backup_dir()
    monkeypatch.setenv("WP_SITE", "https://example.com/shop")
    shop = api.backup_dir()
    monkeypatch.setenv("WP_SITE", "http://example.com")
    insecure = api.backup_dir()
    assert blog != shop
    assert blog != insecure


def test_save_content_preserves_status(mock_server):
    data = api.fetch_raw("pages", 1)
    updated = data["content"]["raw"].replace("placeholder text", "new copy")
    api.save_content("pages", 1, updated, data["status"])
    after = api.fetch_raw("pages", 1)
    assert "new copy" in after["content"]["raw"]
    assert after["status"] == "publish"


def test_save_content_does_not_publish_draft(mock_server):
    data = api.fetch_raw("pages", 2)
    updated = data["content"]["raw"].replace("Draft placeholder", "Updated draft copy")
    api.save_content("pages", 2, updated, data["status"])
    after = api.fetch_raw("pages", 2)
    assert after["status"] == "draft"


def test_rollback_restores_content_and_status(mock_server):
    original = api.backup("pages", 2)
    orig_raw = original["content"]["raw"]
    orig_status = original["status"]

    # Mutate both content and status away from the original.
    api.save_content(
        "pages",
        2,
        "<!-- wp:paragraph -->\n<p>Temp mutation</p>\n<!-- /wp:paragraph -->",
        "publish",
    )
    mutated = api.fetch_raw("pages", 2)
    assert "Temp mutation" in mutated["content"]["raw"]

    # Roll back from /tmp/wp_backup/.
    rb.rollback(2, "pages")
    restored = api.fetch_raw("pages", 2)
    assert restored["content"]["raw"] == orig_raw
    assert restored["status"] == orig_status
    assert "Temp mutation" not in restored["content"]["raw"]


def test_rollback_preserves_trailing_newline(mock_server):
    original = "<!-- wp:paragraph -->\n<p>Keep newline</p>\n<!-- /wp:paragraph -->\n"
    api.save_content("pages", 1, original, "publish")
    api.backup("pages", 1)
    api.save_content(
        "pages",
        1,
        "<!-- wp:paragraph -->\n<p>changed</p>\n<!-- /wp:paragraph -->",
        "publish",
    )
    rb.rollback(1, "pages")
    restored = api.fetch_raw("pages", 1)
    assert restored["content"]["raw"] == original


def test_assert_balanced_blocks_accepts_nested_and_self_closing():
    content = (
        '<!-- wp:group {"layout":{"type":"flex"}} -->\n'
        '<div class="wp-block-group">\n'
        '<!-- wp:site-title /-->\n'
        '<!-- wp:paragraph -->\n<p>hi</p>\n<!-- /wp:paragraph -->\n'
        '</div>\n<!-- /wp:group -->'
    )
    assert api.assert_balanced_blocks(content)


def test_assert_balanced_blocks_rejects_unclosed():
    with pytest.raises(ValueError, match="unclosed"):
        api.assert_balanced_blocks("<!-- wp:group -->\n<div></div>")


def test_assert_balanced_blocks_rejects_mismatch():
    content = (
        "<!-- wp:group -->\n<!-- wp:paragraph -->\n<p>x</p>\n"
        "<!-- /wp:group -->\n<!-- /wp:paragraph -->"
    )
    with pytest.raises(ValueError):
        api.assert_balanced_blocks(content)


def test_template_part_round_trip(mock_server):
    tp = "twentytwentyfive//header"
    api.backup("template-parts", tp)
    site_dir = api.backup_dir()
    assert os.path.exists(
        os.path.join(site_dir, f"{api._backup_key('template-parts', tp)}_original.txt")
    )
    new = (
        '<!-- wp:group -->\n<div class="wp-block-group">\n'
        "<!-- wp:site-title /-->\n</div>\n<!-- /wp:group -->"
    )
    api.save_structural("template-parts", tp, new, "publish", confirm=True)
    after = api.fetch_raw("template-parts", tp)
    assert after["content"]["raw"] == new


def test_save_structural_requires_confirm(mock_server):
    api.backup("pages", 1)
    leaf = "<!-- wp:paragraph -->\n<p>x</p>\n<!-- /wp:paragraph -->"
    with pytest.raises(ValueError, match="confirm"):
        api.save_structural("pages", 1, leaf, "publish", confirm=False)


def test_save_structural_requires_backup(mock_server):
    shutil.rmtree(api.backup_dir(), ignore_errors=True)
    leaf = "<!-- wp:paragraph -->\n<p>x</p>\n<!-- /wp:paragraph -->"
    with pytest.raises(RuntimeError, match="no backup"):
        api.save_structural("pages", 1, leaf, "publish", confirm=True)


def test_create_find_and_delete_resource(mock_server):
    created = api.create_resource(
        "blocks",
        {
            "title": "Stuv Hero",
            "slug": "stuv-hero",
            "content": "<!-- wp:paragraph -->\n<p>hero</p>\n<!-- /wp:paragraph -->",
            "status": "publish",
        },
    )
    bid = created["id"]
    found = api.find_by_slug("blocks", "stuv-hero")
    assert found is not None and found["id"] == bid
    api.delete_resource("blocks", bid)
    assert api.find_by_slug("blocks", "stuv-hero") is None


def test_rollback_template_part(mock_server):
    tp = "twentytwentyfive//header"
    original = api.backup("template-parts", tp)
    orig_raw = original["content"]["raw"]
    api.save_structural(
        "template-parts",
        tp,
        "<!-- wp:paragraph -->\n<p>temp</p>\n<!-- /wp:paragraph -->",
        "publish",
        confirm=True,
    )
    rb.rollback(tp, "template-parts")
    restored = api.fetch_raw("template-parts", tp)
    assert restored["content"]["raw"] == orig_raw


# --- global styles (theme.json design tokens via REST) ---

def test_deep_merge_replaces_lists_not_merges():
    merged = api._deep_merge({"a": {"x": 1}, "l": [1, 2]}, {"a": {"y": 2}, "l": [3]})
    assert merged == {"a": {"x": 1, "y": 2}, "l": [3]}


def test_discover_global_styles_id_from_theme_link(mock_server):
    # Never guessed: read from the active theme's wp:user-global-styles link.
    assert api.discover_global_styles_id() == "1"


def test_apply_global_styles_requires_confirm(mock_server):
    with pytest.raises(ValueError, match="confirm"):
        api.apply_global_styles({"layout": {"contentSize": "80rem"}}, confirm=False)


def test_apply_global_styles_merges_and_backs_up(mock_server):
    shutil.rmtree(api.backup_dir(), ignore_errors=True)
    result = api.apply_global_styles(
        {
            "layout": {"contentSize": "80rem"},
            "color": {"palette": [{"slug": "primary", "color": "#E2001A", "name": "StuV Red"}]},
        },
        {"typography": {"fontFamily": "var:preset|font-family|inter"}},
        confirm=True,
    )
    assert result["settings"]["layout"]["contentSize"] == "80rem"
    # current record backed up to JSON before the write (restore by POSTing it back)
    assert os.path.exists(os.path.join(api.backup_dir(), "global-styles__1_original.json"))
    # round-trips on read
    gs = api.get_global_styles()
    assert gs["settings"]["color"]["palette"][0]["slug"] == "primary"
    assert gs["styles"]["typography"]["fontFamily"] == "var:preset|font-family|inter"


def test_apply_global_styles_deep_merges_existing(mock_server):
    api.apply_global_styles({"layout": {"contentSize": "80rem"}}, confirm=True)
    api.apply_global_styles({"layout": {"wideSize": "90rem"}}, confirm=True)
    layout = api.get_global_styles()["settings"]["layout"]
    assert layout["contentSize"] == "80rem"  # preserved, not clobbered
    assert layout["wideSize"] == "90rem"      # added alongside


# --- connect-time address-family fallback (unroutable AAAA) ---------------

BLACKHOLE = ("192.0.2.1", 443)  # TEST-NET-1: routed nowhere, so connects hang


def _addrinfo(host, port, family=socket.AF_INET):
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (host, port))


@pytest.fixture
def listening_socket():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)  # several tests connect repeatedly without ever accept()ing
    yield srv.getsockname()
    srv.close()


def test_connect_any_falls_back_past_a_blackholed_address(monkeypatch, listening_socket):
    """A hanging first address must not consume the caller's whole read timeout,
    and with WP_ADDRESS_FAMILY unset both families are tried."""
    monkeypatch.setattr(api, "_CONNECT_TIMEOUT", 0.5)
    api._preferred_addr.clear()
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [_addrinfo(*BLACKHOLE), _addrinfo(*listening_socket)],
    )
    start = time.monotonic()
    sock = api._connect_any(listening_socket, timeout=30)
    elapsed = time.monotonic() - start
    try:
        assert sock.getpeername() == listening_socket
        # The short connect budget must not leak into the socket's read timeout.
        assert sock.gettimeout() == 30
    finally:
        sock.close()
    # Old behaviour: one 30s attempt on the blackhole, then the fallback.
    assert elapsed < 5, f"fallback took {elapsed:.1f}s; per-attempt cap not applied"


def test_connect_any_remembers_the_address_that_answered(monkeypatch, listening_socket):
    """The dead address is tried once per run, not once per request."""
    monkeypatch.setattr(api, "_CONNECT_TIMEOUT", 0.5)
    api._preferred_addr.clear()
    calls = []

    def fake_getaddrinfo(*a, **k):
        calls.append(a)
        return [_addrinfo(*BLACKHOLE), _addrinfo(*listening_socket)]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    api._connect_any(listening_socket, timeout=30).close()
    start = time.monotonic()
    api._connect_any(listening_socket, timeout=30).close()
    elapsed = time.monotonic() - start
    assert elapsed < 0.4, f"second connect re-tried the blackhole ({elapsed:.1f}s)"


def test_connect_any_raises_when_every_address_fails(monkeypatch):
    monkeypatch.setattr(api, "_CONNECT_TIMEOUT", 0.3)
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    dead = closed.getsockname()
    closed.close()  # nothing listening -> connection refused
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [_addrinfo(*dead)])
    with pytest.raises(OSError):
        api._connect_any(dead, timeout=5)


# --- pinning the address family ------------------------------------------


def test_address_family_skips_ipv6_when_pinned_to_v4(monkeypatch, listening_socket):
    monkeypatch.setenv("WP_ADDRESS_FAMILY", "ipv4")
    monkeypatch.setattr(api, "_CONNECT_TIMEOUT", 0.5)
    api._preferred_addr.clear()
    v6 = _addrinfo("2001:db8::1", 443, socket.AF_INET6)
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [v6, _addrinfo(*listening_socket)]
    )
    start = time.monotonic()
    sock = api._connect_any(listening_socket, timeout=30)
    elapsed = time.monotonic() - start
    try:
        assert sock.getpeername() == listening_socket
    finally:
        sock.close()
    assert elapsed < 0.4, f"IPv6 address was still tried ({elapsed:.1f}s)"


def test_address_family_pinned_to_v6_skips_ipv4(monkeypatch, listening_socket):
    monkeypatch.setenv("WP_ADDRESS_FAMILY", "ipv6")
    monkeypatch.setattr(api, "_CONNECT_TIMEOUT", 0.3)
    api._preferred_addr.clear()
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [_addrinfo(*listening_socket)]
    )
    with pytest.raises(OSError, match="ipv6"):
        api._connect_any(listening_socket, timeout=5)


def test_address_family_rejects_an_unknown_value(monkeypatch, listening_socket):
    monkeypatch.setenv("WP_ADDRESS_FAMILY", "ipv5")
    with pytest.raises(ValueError, match="WP_ADDRESS_FAMILY"):
        api._connect_any(listening_socket, timeout=5)


def test_requests_go_through_the_fallback_opener(mock_server):
    """_request must use the patched opener, not bare urlopen."""
    api._preferred_addr.clear()
    api.fetch_raw("pages", 1)
    assert api._preferred_addr, "request bypassed _connect_any"


# --- media lookup with duplicate filenames ---------------------------------


def _media_rows():
    return [
        {"id": 20, "source_url": "https://example.test/wp-content/uploads/2026/07/jan.jpg"},
        {"id": 42, "source_url": "https://example.test/wp-content/uploads/jan.jpg"},
        {"id": 19, "source_url": "https://example.test/wp-content/uploads/jan-klein.jpg"},
    ]


def test_find_media_by_filename_is_deterministic_across_api_order(monkeypatch):
    """Result must not depend on the order the REST API returns rows in, and the
    order is pinned in the query, not left to the endpoint default."""
    seen = {}

    def fake(method, path, data=None, retries=3):
        seen["path"] = path
        return list(reversed(_media_rows())) if seen.get("flip") else _media_rows()

    monkeypatch.setattr(api, "_request", fake)
    first = api.find_media_by_filename("jan.jpg")
    assert "orderby=id" in seen["path"] and "order=desc" in seen["path"]
    seen["flip"] = True
    second = api.find_media_by_filename("jan.jpg")
    assert first["id"] == second["id"] == 42  # newest upload wins, both times


def test_find_media_by_filename_warns_about_duplicates(monkeypatch, capsys):
    monkeypatch.setattr(api, "_request", lambda *a, **k: _media_rows())
    api.find_media_by_filename("jan.jpg")
    err = capsys.readouterr().err
    assert "jan.jpg" in err and "20" in err and "42" in err


def test_find_media_by_filename_ignores_partial_name_matches(monkeypatch):
    monkeypatch.setattr(api, "_request", lambda *a, **k: _media_rows())
    assert api.find_media_by_filename("jan-klein.jpg")["id"] == 19
    assert api.find_media_by_filename("nope.jpg") is None


# --- replacing an image at the same URL ------------------------------------

OLD_URL = "https://example.test/wp-content/uploads/jan.jpg"


class FakeLibrary:
    """Stands in for the media endpoints and records the order of the calls."""

    def __init__(self, monkeypatch, tmp_path, existing=True, new_url=OLD_URL):
        self.calls = []
        self.uploads = []
        self.old = {"id": 42, "source_url": OLD_URL, "alt_text": "Jan"} if existing else None
        self.new_url = new_url
        monkeypatch.setattr(api, "backup_dir", lambda: str(tmp_path))
        monkeypatch.setattr(api, "find_media_by_filename", self.find)
        monkeypatch.setattr(api, "_download", self.download)
        monkeypatch.setattr(api, "delete_resource", self.delete)
        monkeypatch.setattr(api, "upload_media", self.upload)

    def find(self, filename):
        return self.old

    def download(self, url):
        self.calls.append("download")
        return b"old bytes"

    def delete(self, endpoint, pid, force=True):
        self.calls.append(f"delete {endpoint}/{pid}")

    def upload(self, path, *, filename=None, alt_text=None, reuse_existing=True):
        self.calls.append("upload")
        with open(path, "rb") as f:
            self.uploads.append({"bytes": f.read(), "filename": filename, "alt_text": alt_text,
                                 "reuse_existing": reuse_existing})
        return {"id": 43, "source_url": self.new_url}


def test_replace_media_backs_up_before_it_deletes(monkeypatch, tmp_path):
    lib = FakeLibrary(monkeypatch, tmp_path)
    new = tmp_path / "jan.jpg"
    new.write_bytes(b"new bytes")
    api.replace_media(str(new))
    assert lib.calls == ["download", "delete media/42", "upload"]
    path, meta_path = api.media_backup_paths("jan.jpg")
    assert open(path, "rb").read() == b"old bytes"
    assert json.load(open(meta_path))["source_url"] == OLD_URL
    assert lib.uploads[0]["reuse_existing"] is False


def test_replace_media_keeps_the_alt_text(monkeypatch, tmp_path):
    lib = FakeLibrary(monkeypatch, tmp_path)
    new = tmp_path / "jan.jpg"
    new.write_bytes(b"new bytes")
    api.replace_media(str(new))
    assert lib.uploads[0]["alt_text"] == "Jan"


def test_replace_media_raises_when_the_url_changes(monkeypatch, tmp_path):
    FakeLibrary(monkeypatch, tmp_path, new_url="https://example.test/wp-content/uploads/jan-1.jpg")
    new = tmp_path / "jan.jpg"
    new.write_bytes(b"new bytes")
    with pytest.raises(RuntimeError, match="jan-1.jpg"):
        api.replace_media(str(new))
    assert os.path.exists(api.media_backup_paths("jan.jpg")[0])


def test_replace_media_without_an_old_file_only_uploads(monkeypatch, tmp_path):
    lib = FakeLibrary(monkeypatch, tmp_path, existing=False)
    new = tmp_path / "jan.jpg"
    new.write_bytes(b"new bytes")
    api.replace_media(str(new))
    assert lib.calls == ["upload"]


def test_upload_media_cli_replace_goes_through_replace_media(monkeypatch, tmp_path, capsys):
    import upload_media

    lib = FakeLibrary(monkeypatch, tmp_path)
    new = tmp_path / "jan.jpg"
    new.write_bytes(b"new bytes")
    upload_media.main(["--replace", str(new)])
    assert lib.calls == ["download", "delete media/42", "upload"]
    assert OLD_URL in capsys.readouterr().out


def test_rollback_media_restores_the_backup(monkeypatch, tmp_path):
    lib = FakeLibrary(monkeypatch, tmp_path)
    new = tmp_path / "jan.jpg"
    new.write_bytes(b"new bytes")
    api.replace_media(str(new))
    rb.rollback_media("jan.jpg")
    restored = lib.uploads[-1]
    assert restored["bytes"] == b"old bytes" and restored["filename"] == "jan.jpg"
    assert restored["alt_text"] == "Jan"
    # The restore takes no backup of its own, so the one it restores survives.
    assert open(api.media_backup_paths("jan.jpg")[0], "rb").read() == b"old bytes"


def test_rollback_media_without_a_backup_exits(monkeypatch, tmp_path):
    monkeypatch.setattr(rb, "media_backup_paths", lambda n: (str(tmp_path / n), str(tmp_path / n) + ".json"))
    with pytest.raises(SystemExit):
        rb.rollback_media("nope.jpg")
