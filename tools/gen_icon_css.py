#!/usr/bin/env python3
"""Emit the CSS custom properties holding Phosphor icons as data-URI masks/images.

Reads SVGs from $PHOSPHOR_ICON_DIR (default
node_modules/@phosphor-icons/core/assets/regular/) and writes a
:root { --ico-*: url("data:...") } block into data/styles/component.css, between
the gen_icon_css markers. The fill colour is baked to the brand primary
so the same data-URI works both as a CSS mask (alpha-only; recoloured via
`background: var(--stuv-primary)`) and as a background-image (shows the baked
primary). Stdlib only.

component.css is deployed into the global-styles custom-CSS field, which WordPress
prints inline in <style id="global-styles-inline-css"> on every page view and never
HTTP-caches. This icon set is the largest single thing in it, so the encoding is
kept as tight as it can be while staying safe:

  * comments and class attributes are dropped (Phosphor's regular set ships
    neither today; the strip is a guard against a release that adds them):
    neither can match anything inside a mask.
  * whitespace is collapsed, so a pretty-printed SVG doesn't turn every
    newline+indent into a run of %20.
  * only %, #, " and the angle brackets are percent-escaped. Spaces, apostrophes,
    '=' and ':' are legal inside a quoted CSS url() and cost 3 bytes each escaped.
    The angle brackets stay escaped on purpose: this CSS is stored in a WordPress
    post, and a raw <svg ...> in the payload is exactly what a KSES pass would
    mangle. That risk is not worth the 2 bytes.

Usage (from repo root; this repo has no node_modules, so fetch the package ad hoc):
    npm install --prefix /tmp/phosphor @phosphor-icons/core@2.1.1
    export PHOSPHOR_ICON_DIR=/tmp/phosphor/node_modules/@phosphor-icons/core/assets/regular
    python3 tools/gen_icon_css.py            # print the block to stdout
    python3 tools/gen_icon_css.py --write    # splice it into component.css
    python3 tools/gen_icon_css.py --check    # diff against component.css; writes nothing

Pin the Phosphor version: a bump redraws paths, and every icon on the site changes
shape with no diff anywhere but here.

The token names (--ico-calendar, --ico-utensils, ...) predate Phosphor: they are
the lucide names the site was built with, and block HTML, data/maps/*.json and
component.css reference them. ICONS maps each token to the Phosphor icon that
draws it, so swapping a glyph is a one-line change here instead of a rename
across the content.
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
    os.environ.get(
        "PHOSPHOR_ICON_DIR", "node_modules/@phosphor-icons/core/assets/regular"
    )
)

START = "/* gen_icon_css:start — erzeugt von tools/gen_icon_css.py; nicht von Hand bearbeiten */"
END = "/* gen_icon_css:end */"

# token -> Phosphor icon. Every token here must be reachable from a rule in component.css or from a
# var(--ico-*) in the block HTML; an unreachable one is ~150 bytes on every page
# view for nothing.
ICONS = {
    # Referate
    "banknote": "money",
    "megaphone": "megaphone",
    "party-popper": "confetti",
    "monitor": "monitor",
    "dumbbell": "barbell",
    "leaf": "leaf",
    "graduation-cap": "graduation-cap",
    "heart": "heart",
    "map-pin": "map-pin",
    "globe": "globe",
    "landmark": "bank",
    # Was wir bieten / Werde aktiv
    "calendar": "calendar-blank",
    "calendar-days": "calendar-dots",
    "coffee": "coffee",
    "trophy": "trophy",
    "home": "house",
    "utensils-crossed": "fork-knife",
    "ticket": "ticket",
    "clock": "clock",
    "instagram": "instagram-logo",
    "message-circle": "chat-circle",
    "link-2": "link-simple",
    "users": "users",
    "mail": "envelope-simple",
    "external-link": "arrow-square-out",
    # Wir hören zu / form
    "message-circle-heart": "hand-heart",
    "send": "paper-plane-tilt",
    # UI
    "chevron-down": "caret-down",
    # Subpages
    "alert-circle": "warning-circle",
    "book-open": "book-open",
    "lock": "lock",
    "phone": "phone",
    "shield": "shield",
    "sparkles": "sparkle",
    "utensils": "fork-knife",
    # Kummer Karsten categories / hilfsangebote card headings
    "briefcase": "briefcase",
    "lightbulb": "lightbulb",
    "moon": "moon",
    # Stadt map icons
    "beer": "beer-stein",
    "binoculars": "binoculars",
    "bus": "bus",
    "castle": "castle-turret",
    "film": "film-strip",
    "flower": "flower",
    "ice-cream-cone": "ice-cream",
    "mountain": "mountains",
    "music": "music-notes",
    "palette": "palette",
    "pizza": "pizza",
    "train-front": "train",
    "tree-pine": "tree-evergreen",
    "waves": "waves",
    "wine": "wine",
}

# Characters that must not survive raw inside url("data:image/svg+xml,…"):
#   %  is the escape character itself
#   #  would start a URL fragment and truncate the icon at the stroke colour
#   <> would put raw markup into a CSS payload that WordPress stores in a post
# Everything else in an SVG is safe inside a double-quoted CSS url().
UNSAFE = "%#<>"
SAFE = "".join(chr(c) for c in range(0x21, 0x7F) if chr(c) not in UNSAFE + '"')


def clean_svg(svg: str) -> str:
    """Strip what a mask can never use, then collapse the whitespace."""
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)
    svg = re.sub(r"\s+class=(['\"])[^'\"]*\1", "", svg)
    svg = re.sub(r"\s+", " ", svg).strip()
    svg = svg.replace("currentColor", PRIMARY)
    return svg.replace('"', "'").replace("> <", "><")


def to_data_uri(svg: str) -> str:
    return 'url("data:image/svg+xml,' + urllib.parse.quote(clean_svg(svg), SAFE) + '")'


def render_css() -> str:
    missing = sorted({n for n in ICONS.values() if not (ICON_DIR / f"{n}.svg").exists()})
    if missing:
        sys.exit(
            f"missing Phosphor icons: {', '.join(missing)}\n"
            f"(looked in {ICON_DIR}; set PHOSPHOR_ICON_DIR)"
        )
    lines = [START, ":root {"]
    for token, name in ICONS.items():
        svg = (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8")
        lines.append(f"  --ico-{token}: {to_data_uri(svg)};")
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
