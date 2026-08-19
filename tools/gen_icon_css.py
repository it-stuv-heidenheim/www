#!/usr/bin/env python3
"""Emit the CSS custom properties holding lucide icons as data-URI masks/images.

Reads SVGs from node_modules/lucide-static/icons/ (devDependency: lucide-static)
and writes a :root { --ico-*: url("data:...") } block into data/styles/component.css,
between the gen_icon_css markers. The stroke colour is baked to the brand primary
so the same data-URI works both as a CSS mask (alpha-only; recoloured via
`background: var(--stuv-primary)`) and as a background-image (shows the baked
primary). Stdlib only.

component.css is deployed into the global-styles custom-CSS field, which WordPress
prints inline in <style id="global-styles-inline-css"> on every page view and never
HTTP-caches. This icon set is the largest single thing in it, so the encoding is
kept as tight as it can be while staying safe:

  * lucide's @license comment and its class='lucide lucide-x' attribute are dropped
    — neither can match anything inside a mask, and together they cost ~4 KB.
  * whitespace is collapsed; lucide pretty-prints its SVGs and the old encoder
    turned every newline+indent into a run of %20.
  * only %, #, " and the angle brackets are percent-escaped. Spaces, apostrophes,
    '=' and ':' are legal inside a quoted CSS url() and cost 3 bytes each escaped.
    The angle brackets stay escaped on purpose: this CSS is stored in a WordPress
    post, and a raw <svg ...> in the payload is exactly what a KSES pass would
    mangle. That risk is not worth the 2 bytes.

Usage (from repo root; this repo has no node_modules — install lucide-static ad hoc):
    npm install --prefix /tmp/lucide lucide-static@0.577.0
    export LUCIDE_ICON_DIR=/tmp/lucide/node_modules/lucide-static/icons
    python3 tools/gen_icon_css.py            # print the block to stdout
    python3 tools/gen_icon_css.py --write    # splice it into component.css
    python3 tools/gen_icon_css.py --check    # diff against component.css; writes nothing

Pin the lucide version: a bump redraws paths, and every icon on the site changes
shape with no diff anywhere but here.
"""

import argparse
import os
import pathlib
import re
import sys
import urllib.parse

REPO = pathlib.Path(__file__).resolve().parent.parent
CSS = REPO / "data" / "styles" / "component.css"

PRIMARY = "#E2001A"
ICON_DIR = pathlib.Path(
    os.environ.get("LUCIDE_ICON_DIR", "node_modules/lucide-static/icons")
)

START = "/* gen_icon_css:start — erzeugt von tools/gen_icon_css.py; nicht von Hand bearbeiten */"
END = "/* gen_icon_css:end */"

# Every name here must be reachable from a rule in component.css or from a
# var(--ico-*) in the block HTML; an unreachable one is ~150 bytes on every page
# view for nothing.
ICONS = [
    # Referate
    "banknote", "megaphone", "party-popper", "monitor", "dumbbell", "leaf",
    "graduation-cap", "heart", "map-pin", "globe", "landmark",
    # Was wir bieten / Werde aktiv
    "calendar", "calendar-days", "coffee", "trophy", "home", "utensils-crossed",
    "ticket", "clock", "instagram", "message-circle", "link-2",
    "users", "mail", "external-link",
    # Wir hören zu / form
    "message-circle-heart", "send",
    # UI
    "chevron-down",
    # Subpages
    "alert-circle", "book-open", "lock", "phone", "shield",
    "sparkles", "utensils",
    # Kummer Karsten categories / hilfsangebote card headings
    "briefcase", "lightbulb", "moon",
    # Stadt map icons
    "beer", "binoculars", "bus", "castle", "film", "flower",
    "ice-cream-cone", "mountain", "music", "palette", "pizza",
    "train-front", "tree-pine", "waves", "wine",
]

# Characters that must not survive raw inside url("data:image/svg+xml,…"):
#   %  is the escape character itself
#   #  would start a URL fragment and truncate the icon at the stroke colour
#   <> would put raw markup into a CSS payload that WordPress stores in a post
# Everything else in an SVG is safe inside a double-quoted CSS url().
UNSAFE = "%#<>"
SAFE = "".join(chr(c) for c in range(0x21, 0x7F) if chr(c) not in UNSAFE + '"')


def clean_svg(svg: str) -> str:
    """Strip what a mask can never use, then collapse the whitespace."""
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)  # lucide's @license
    svg = re.sub(r"\s+class=(['\"])lucide[^'\"]*\1", "", svg)
    svg = re.sub(r"\s+", " ", svg).strip()
    svg = svg.replace("currentColor", PRIMARY)
    return svg.replace('"', "'").replace("> <", "><")


def to_data_uri(svg: str) -> str:
    return 'url("data:image/svg+xml,' + urllib.parse.quote(clean_svg(svg), SAFE) + '")'


def render_css() -> str:
    missing = [n for n in ICONS if not (ICON_DIR / f"{n}.svg").exists()]
    if missing:
        sys.exit(
            f"missing lucide-static icons: {', '.join(missing)}\n"
            f"(looked in {ICON_DIR}; set LUCIDE_ICON_DIR)"
        )
    lines = [START, ":root {"]
    for name in ICONS:
        svg = (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8")
        lines.append(f"  --ico-{name}: {to_data_uri(svg)};")
    lines += ["}", END]
    return "\n".join(lines) + "\n"


def splice(text: str, block: str) -> str:
    """Replace everything between the markers, the markers included."""
    start, end = text.find(START), text.find(END)
    if start < 0 or end < 0:
        sys.exit(f"{CSS.name} has no gen_icon_css markers")
    return text[:start] + block + text[end + len(END) + 1 :]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render the StuV icon tokens")
    parser.add_argument(
        "--write", action="store_true", help="splice the block into component.css"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="diff against component.css; writes nothing, exit 1 on drift",
    )
    args = parser.parse_args(argv)

    block = render_css()
    if not (args.write or args.check):
        print(block, end="")
        return 0

    current = CSS.read_text(encoding="utf-8")
    spliced = splice(current, block)
    if args.check:
        if spliced != current:
            print("drift: component.css differs from a fresh icon render", file=sys.stderr)
            return 1
        return 0
    CSS.write_text(spliced, encoding="utf-8")
    print(f"spliced {len(ICONS)} icons into {CSS.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
