#!/usr/bin/env python3
"""Compare every manifest target against what the site serves.

--history looks a differing target up in git: BEHIND (an older commit had it, or the page is
empty) or EDITED (no commit had it: a wp-admin edit a deploy would destroy).

Exit codes: 0 all match, 1 some differ (with --history: all BEHIND), 2 fetch failed, 3 some EDITED.

Usage:
  python3 verify_deploy.py --manifest <path> [<target>] [--diff] [--history]
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

import wp_block_api as wp
from deploy import _read_source


def _fetch_live(t):
    if t["type"] == "global-styles":
        return wp.get_global_styles()
    return wp.fetch_raw(t["endpoint"], t["id"])["content"]["raw"]


def _norm_tokens(v):
    """Tokens as WordPress stores them: `var:preset|x|y` reads back as a CSS var."""
    if isinstance(v, str):
        return re.sub(r"var:preset\|([a-z0-9-]+)\|([a-z0-9-]+)", r"var(--wp--preset--\1--\2)", v)
    if isinstance(v, dict):
        return {k: _norm_tokens(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_norm_tokens(x) for x in v]
    return v


def _project(tokens, live):
    """The part of the live record that `tokens` writes, in the tokens' shape. A
    preset list written by a deploy reads back under its origin: {"custom": [...]}."""
    if isinstance(tokens, list) and isinstance(live, dict) and set(live) == {"custom"}:
        live = live["custom"]
    if isinstance(tokens, dict) and isinstance(live, dict):
        return {k: _project(v, live[k]) for k, v in tokens.items() if k in live}
    return live


def _texts(t, read, live):
    """(local, live) as comparable text; `read(rel)` returns a source."""
    if t["type"] != "global-styles":
        return read(t["source"]), live
    tokens = _norm_tokens(json.loads(read(t["tokens"])))
    mine, served = {}, {}
    for part in ("settings", "styles"):
        mine[part] = {k: v for k, v in (tokens.get(part) or {}).items() if k != "css"}
        served[part] = _project(mine[part], live.get(part) or {})
    css = live_css = ""
    if t.get("css"):
        css, live_css = read(t["css"]), (live.get("styles") or {}).get("css") or ""

    def dump(d):
        return json.dumps(d, indent=1, sort_keys=True, ensure_ascii=False)

    return css + "\n/* tokens */\n" + dump(mine), live_css + "\n/* tokens */\n" + dump(served)


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout


def _git_reader(repo, commit, prefix):
    """_read_source for the sources as they were in `commit`."""
    def read(rel):
        path = (prefix / rel).as_posix()
        if _git(repo, "cat-file", "-t", f"{commit}:{path}").strip() != "tree":
            return _git(repo, "show", f"{commit}:{path}")
        names = sorted(
            n for n in _git(repo, "ls-tree", "--name-only", f"{commit}:{path}").splitlines()
            if n.endswith(".html")
        )
        if not names:
            raise FileNotFoundError(f"no *.html in {path} at {commit}")
        return "\n\n".join(_git(repo, "show", f"{commit}:{path}/{n}") for n in names)
    return read


def find_commit(t, base, live):
    """(sha, subject) of the newest commit whose sources match what the site
    serves, or None: content git never had, or no history to search (a shallow
    clone), which is treated the same so a deploy stops rather than guesses."""
    try:
        repo = Path(_git(base, "rev-parse", "--show-toplevel").strip()).resolve()
    except (OSError, subprocess.CalledProcessError):
        return None
    prefix = Path(base).resolve().relative_to(repo)
    if t["type"] == "global-styles":
        rels = [t["tokens"]] + ([t["css"]] if t.get("css") else [])
    else:
        rels = [t["source"]]
    log = _git(repo, "log", "--format=%H %s", "--", *[(prefix / r).as_posix() for r in rels])
    for line in log.splitlines():
        sha, _, subject = line.partition(" ")
        try:
            local, served = _texts(t, _git_reader(repo, sha, prefix), live)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            continue  # a source missing or unreadable in this commit
        if local == served:
            return sha[:7], subject
    return None


def check_target(name, t, base, show_diff=False, history=False):
    """Return (status, detail) where status is 'match', 'differ' or 'error';
    with history, 'behind' or 'edited' instead of 'differ'."""
    if t["type"] == "media":
        # Media is bytes in a library, not markup; upload_media() already
        # reports what it reused or created, so there is nothing to diff here.
        return "skip", "media target (not diffable)"

    live = _fetch_live(t)
    local, served = _texts(t, lambda rel: _read_source(base, rel), live)
    label = t.get("source") or t.get("css") or t["tokens"]

    if local == served:
        return "match", f"{len(served)} bytes"

    status, detail = "differ", f"local {len(local)} bytes vs live {len(served)} bytes"
    if history and not served.strip():
        status, detail = "behind", f"live is empty; {detail}"
    elif history:
        found = find_commit(t, base, live)
        if found:
            status, detail = "behind", f"live is {found[0]} ({found[1]}); {detail}"
        else:
            status, detail = "edited", f"live matches no commit; {detail}"
    if show_diff:
        diff = difflib.unified_diff(
            local.splitlines(), served.splitlines(),
            fromfile=f"local:{label}", tofile=f"live:{name}", lineterm="", n=1,
        )
        detail += "\n" + "\n".join(list(diff)[:60])
    return status, detail


def main(argv):
    parser = argparse.ArgumentParser(description="Verify deployed content matches sources")
    parser.add_argument("--manifest", required=True, help="path to the manifest JSON")
    parser.add_argument("target", nargs="?", help="a target name; default is all")
    parser.add_argument("--diff", action="store_true", help="show a unified diff on mismatch")
    parser.add_argument("--history", action="store_true",
                        help="tell BEHIND (an older commit) from EDITED (no commit, wp-admin)")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text())
    base = manifest_path.parent

    if args.target and args.target not in manifest:
        sys.exit(f"unknown target {args.target!r}; have: {', '.join(manifest)}")
    names = [args.target] if args.target else list(manifest)

    counts = {"match": 0, "differ": 0, "behind": 0, "edited": 0, "error": 0, "skip": 0}
    marks = {"match": "OK", "differ": "DIFF", "behind": "BEHIND", "edited": "EDITED",
             "error": "ERROR", "skip": "--"}
    for name in names:
        try:
            status, detail = check_target(name, manifest[name], base, args.diff, args.history)
        except Exception as exc:  # a target that cannot be read is not a pass
            status, detail = "error", f"{type(exc).__name__}: {exc}"
        counts[status] += 1
        print(f"  {marks[status]:6} {name:20} {detail}")

    differ = (f"{counts['behind']} behind, {counts['edited']} edited" if args.history
              else f"{counts['differ']} differ")
    print(f"\n{counts['match']} match, {differ}, {counts['error']} error, {counts['skip']} skipped")
    if counts["error"]:
        return 2
    if counts["edited"]:
        return 3
    return 1 if counts["differ"] or counts["behind"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
