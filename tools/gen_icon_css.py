#!/usr/bin/env python3
"""Write the Phosphor icons as data-URI custom properties (--ico-*) between the gen_icon_css
markers in data/styles/component.css. The fill is baked to the brand primary, so one URI works
as mask and as background-image. Only %, #, " and <> are escaped: the CSS is inlined on every page.

    npm install --prefix /tmp/phosphor @phosphor-icons/core@2.1.1
    export PHOSPHOR_ICON_DIR=/tmp/phosphor/node_modules/@phosphor-icons/core/assets/regular
    python3 tools/gen_icon_css.py            # print the block to stdout
    python3 tools/gen_icon_css.py --write    # splice it into component.css
    python3 tools/gen_icon_css.py --check    # diff against component.css; writes nothing

Keep the version pinned: a bump redraws every icon. Token names are the older lucide names.
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

# token -> Phosphor icon. Every token must be used by component.css or the block HTML
# (each one costs ~150 bytes on every page view).
ICONS = {
    # Referate
    "dumbbell": "barbell",
    "graduation-cap": "graduation-cap",
    "heart": "heart",
    "map-pin": "map-pin",
    "landmark": "bank",
    # Was wir bieten / Werde aktiv
    "calendar": "calendar-blank",
    "calendar-days": "calendar-dots",
    "coffee": "coffee",
    "trophy": "trophy",
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

# Escaped inside url("data:image/svg+xml,…"): % (escape char), # (fragment), <> (KSES).
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
