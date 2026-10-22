#!/usr/bin/env python3
"""Compare every manifest target against what the site is actually serving.

`deploy.py --dry-run` validates sources locally and prints byte counts; it never
talks to the server, so it cannot tell you that a target was skipped, half
written, or silently reverted. This closes that gap: it fetches each target's
stored content and diffs it against the source the manifest points at.

Exit codes: 0 all targets match, 1 at least one differs, 2 a target could not be
fetched.

Usage:
  python3 verify_deploy.py --manifest <path>            # check every target
  python3 verify_deploy.py --manifest <path> <target>   # check one
  python3 verify_deploy.py --manifest <path> --diff     # show what differs
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

try:  # run as a script: scripts/ is on sys.path
    import wp_block_api as wp
    from deploy import _read_source
except ModuleNotFoundError:  # imported as scripts.verify_deploy (tests)
    import scripts.wp_block_api as wp
    from scripts.deploy import _read_source


def _live_structural(t):
    return wp.fetch_raw(t["endpoint"], t["id"])["content"]["raw"]


def _live_global_styles_css(_t):
    return (wp.get_global_styles().get("styles") or {}).get("css") or ""


def check_target(name, t, base, show_diff=False):
    """Return (status, detail) where status is 'match', 'differ' or 'error'."""
    if t["type"] == "media":
        # Media is bytes in a library, not markup; upload_media() already
        # reports what it reused or created, so there is nothing to diff here.
        return "skip", "media target (not diffable)"

    if t["type"] == "global-styles":
        css_rel = t.get("css")
        if not css_rel:
            return "skip", "no css in target"
        local, live = _read_source(base, css_rel), _live_global_styles_css(t)
        label = css_rel
    else:
        local, live = _read_source(base, t["source"]), _live_structural(t)
        label = t["source"]

    if local == live:
        return "match", f"{len(live)} bytes"

    detail = f"local {len(local)} bytes vs live {len(live)} bytes"
    if show_diff:
        diff = difflib.unified_diff(
            local.splitlines(), live.splitlines(),
            fromfile=f"local:{label}", tofile=f"live:{name}", lineterm="", n=1,
        )
        detail += "\n" + "\n".join(list(diff)[:60])
    return "differ", detail


def main(argv):
    parser = argparse.ArgumentParser(description="Verify deployed content matches sources")
    parser.add_argument("--manifest", required=True, help="path to the manifest JSON")
    parser.add_argument("target", nargs="?", help="a target name; default is all")
    parser.add_argument("--diff", action="store_true", help="show a unified diff on mismatch")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text())
    base = manifest_path.parent

    if args.target and args.target not in manifest:
        sys.exit(f"unknown target {args.target!r}; have: {', '.join(manifest)}")
    names = [args.target] if args.target else list(manifest)

    counts = {"match": 0, "differ": 0, "error": 0, "skip": 0}
    for name in names:
        try:
            status, detail = check_target(name, manifest[name], base, args.diff)
        except Exception as exc:  # a target that cannot be read is not a pass
            status, detail = "error", f"{type(exc).__name__}: {exc}"
        counts[status] += 1
        mark = {"match": "OK   ", "differ": "DIFF ", "error": "ERROR", "skip": "--   "}[status]
        print(f"  {mark} {name:20} {detail}")

    print(
        f"\n{counts['match']} match, {counts['differ']} differ, "
        f"{counts['error']} error, {counts['skip']} skipped"
    )
    if counts["error"]:
        return 2
    return 1 if counts["differ"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
