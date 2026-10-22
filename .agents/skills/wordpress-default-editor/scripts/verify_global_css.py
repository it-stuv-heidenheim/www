#!/usr/bin/env python3
"""Verify custom CSS survived a global-styles write intact.

Reads the live user global-styles record and checks styles.css for the given
marker strings and, optionally, an icon custom property carrying a data: URI
(REST sanitization strips data: URIs on some hosts). Run after deploying a
global-styles target.

Exit codes: 0 all intact; 1 marker rules missing (restore); 2 icon data: URIs
stripped (keep the icon :root block in a header core/html block instead).

Usage:
  python3 verify_global_css.py --marker .my-card --marker .my-box \
      --icon-marker=--ico-calendar
(argparse needs the `=` form for values that start with `--`.)
"""
import argparse
import sys

try:  # run as a script: scripts/ is on sys.path
    import wp_block_api as wp
except ModuleNotFoundError:  # imported as scripts.verify_global_css (tests)
    import scripts.wp_block_api as wp


def check(css, markers, icon_marker=None):
    """Return the exit code described in the module docstring."""
    missing = [m for m in markers if m not in css]
    print(f"styles.css length: {len(css)} bytes")
    for m in markers:
        print(f"  {'OK  ' if m not in missing else 'MISS'}  {m}")
    if missing:
        print("FAIL: marker rules stripped on save:", missing)
        return 1
    if icon_marker is not None:
        icon_ok = (icon_marker in css) and ("data:image/svg+xml" in css)
        print(f"  {'OK  ' if icon_ok else 'MISS'}  {icon_marker} (data: URI)")
        if not icon_ok:
            print("NOTE: icon data: URIs stripped by REST sanitization. "
                  "Keep the --ico-* :root block in a header core/html block.")
            return 2
    print("PASS: custom CSS markers intact in global-styles.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify global-styles custom CSS")
    parser.add_argument("--marker", action="append", required=True,
                        help="string that must appear in styles.css (repeatable)")
    parser.add_argument("--icon-marker", default=None,
                        help="custom property whose value must be a data: URI "
                             "(use --icon-marker=--ico-name)")
    args = parser.parse_args(argv)
    rec = wp.get_global_styles()
    css = ((rec.get("styles") or {}).get("css")) or ""
    return check(css, args.marker, args.icon_marker)


if __name__ == "__main__":
    sys.exit(main())
