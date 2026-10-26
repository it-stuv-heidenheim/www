#!/usr/bin/env python3
"""Render the pin maps from data/maps/<id>.json: CARTO tiles -> data/media/karte-<id>-{light,dark}.webp,
plus the core/html block with pins and legend. Pillow is needed for --render/--preview/--check.

    python3 tools/gen_map.py campus --render      # fetch tiles, write the webp pair
    python3 tools/gen_map.py campus --write       # splice the block into its targets
    python3 tools/gen_map.py campus --check       # re-render and diff; writes nothing
    python3 tools/gen_map.py campus               # print the block to stdout

--check compares WebP bytes; after a Pillow/libwebp upgrade, re-render and commit the images.
"""

import argparse
import functools
import hashlib
import html
import io
import json
import math
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request
from typing import NamedTuple

REPO = pathlib.Path(__file__).resolve().parent.parent
MAP_DIR = REPO / "data" / "maps"
MEDIA_DIR = REPO / "data" / "media"
CACHE_DIR = pathlib.Path.home() / ".cache" / "stuv-map-tiles"

TILE = 256  # logical tile edge in px
SCALE = 2  # @2x retina tiles -> 512 px files
STYLES = ("light_all", "dark_all")
EARTH_M_PER_DEG = 111_320.0

# Covers a 2x display of the ~1200px column and stays under WordPress's 2560px big-image
# threshold, above which it rescales the upload and source_url no longer points at our file.
MAX_WIDTH = 2400

# Pins are percentages of the whole image, so the box is widened (never cropped) to 16:9.
# Under 600px component.css crops the sides to 3:2, which only eats fit_aspect's padding.
ASPECT = 16 / 9

# Contrast stretch away from `anchor` (the land's level), ending the land at `base`. Dark
# Matter is lifted to 18 so its buildings (0) stay apart from the land (8).
ENHANCE = {
    "light_all": {"base": 255, "anchor": 255, "gain": 2.2},
    "dark_all": {"base": 18, "anchor": 8, "gain": 1.7},
}

TILE_URL = "https://a.basemaps.cartocdn.com/{style}/{z}/{x}/{y}@2x.png"
# CARTO's tile servers ban the stdlib default User-Agent.
USER_AGENT = "stuv-map-render/1.0 (+https://stuv-heidenheim.de)"

# Pins at least this far down (% of the frame) open their tooltip upwards, higher ones downwards.
TIP_BELOW = 25.0

# Bounds for hand-placed edge_x/edge_y. X is tighter: under 640px the 3:2 frame hides
# ~7.8% of the 16:9 canvas per side. Y is never cropped.
SAFE_ZONE_X = (15.0, 85.0)
SAFE_ZONE_Y = (6.0, 94.0)

# Root-relative, so the markup works on staging and production.
MEDIA_BASE = "/wp-content/uploads"
ATTRIBUTION = "© OpenStreetMap-Mitwirkende, © CARTO"

# Searches name and address so Google Maps opens the place card instead of a bare pin.
MAPS_URL = "https://www.google.com/maps/search/?api=1&query={query}"
MARKER = (
    "<!-- gen_map:{id} — erzeugt von tools/gen_map.py aus data/maps/{id}.json; "
    "nicht von Hand bearbeiten -->"
)


class BBox(NamedTuple):
    south: float
    west: float
    north: float
    east: float


def load_map(map_id: str) -> dict:
    path = MAP_DIR / f"{map_id}.json"
    if not path.exists():
        sys.exit(f"no such map definition: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["id"] != map_id:
        sys.exit(f"{path.name} declares id {data['id']!r}, expected {map_id!r}")
    if not data["pins"]:
        sys.exit(f"{path.name} has no pins")
    validate_edge_pins(data)
    return data


def validate_edge_pins(data: dict) -> None:
    """Every edge pin needs a hand-placed edge_x/edge_y inside its axis' bounds."""
    for pin in data["pins"]:
        if not pin.get("edge"):
            continue
        for axis, (low, high) in (("edge_x", SAFE_ZONE_X), ("edge_y", SAFE_ZONE_Y)):
            if axis not in pin:
                sys.exit(f"{data['id']}: edge pin {pin['n']} has no {axis}")
            value = pin[axis]
            if not (low <= value <= high):
                sys.exit(
                    f"{data['id']}: edge pin {pin['n']} {axis}={value} outside "
                    f"the safe zone [{low}, {high}]"
                )


def project(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Web Mercator world pixel coordinates at `zoom` (256 px tiles, unscaled)."""
    n = 2.0**zoom * TILE
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def unproject(x: float, y: float, zoom: int) -> tuple[float, float]:
    """Inverse of project(): world pixel coordinates back to (lat, lon)."""
    n = 2.0**zoom * TILE
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n))))
    return lat, lon


def fit_aspect(bbox: BBox, aspect: float = ASPECT) -> BBox:
    """Grow the short axis about the centre until the box is `aspect` wide:tall, in projected pixels."""
    x0, y0 = project(bbox.north, bbox.west, 0)
    x1, y1 = project(bbox.south, bbox.east, 0)
    width, height = x1 - x0, y1 - y0
    if width < height * aspect:
        grow = (height * aspect - width) / 2.0
        x0, x1 = x0 - grow, x1 + grow
    else:
        grow = (width / aspect - height) / 2.0
        y0, y1 = y0 - grow, y1 + grow
    north, west = unproject(x0, y0, 0)
    south, east = unproject(x1, y1, 0)
    return BBox(south, west, north, east)


def bbox_from_pins(pins: list[dict], padding_m: float, aspect: float = ASPECT) -> BBox:
    """Smallest box holding every pin, plus `padding_m` on each side, at `aspect`."""
    lats = [p["lat"] for p in pins]
    lons = [p["lon"] for p in pins]
    mid_lat = (min(lats) + max(lats)) / 2.0
    dlat = padding_m / EARTH_M_PER_DEG
    dlon = padding_m / (EARTH_M_PER_DEG * math.cos(math.radians(mid_lat)))
    padded = BBox(
        min(lats) - dlat, min(lons) - dlon, max(lats) + dlat, max(lons) + dlon
    )
    return fit_aspect(padded, aspect)


def pixel_box(bbox: BBox, zoom: int) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the bbox in scaled pixels at `zoom`."""
    left, top = project(bbox.north, bbox.west, zoom)
    right, bottom = project(bbox.south, bbox.east, zoom)
    return (
        round(left * SCALE),
        round(top * SCALE),
        round(right * SCALE),
        round(bottom * SCALE),
    )


def tile_range(bbox: BBox, zoom: int) -> tuple[int, int, int, int]:
    """Inclusive tile indices (x0, y0, x1, y1) covering the bbox."""
    left, top, right, bottom = pixel_box(bbox, zoom)
    edge = TILE * SCALE
    return (left // edge, top // edge, (right - 1) // edge, (bottom - 1) // edge)


def image_size(bbox: BBox, zoom: int) -> tuple[int, int]:
    """Pixel size of the image render_image() writes, MAX_WIDTH included (the one place the clamp lives)."""
    left, top, right, bottom = pixel_box(bbox, zoom)
    width, height = right - left, bottom - top
    if width > MAX_WIDTH:
        height = round(height * MAX_WIDTH / width)
        width = MAX_WIDTH
    return width, height


def pin_percent(lat: float, lon: float, bbox: BBox) -> tuple[float, float]:
    """Pin position as a percentage of the cropped image, top-left origin."""
    x, y = project(lat, lon, 0)
    x0, y0 = project(bbox.north, bbox.west, 0)
    x1, y1 = project(bbox.south, bbox.east, 0)
    return (x - x0) / (x1 - x0) * 100.0, (y - y0) / (y1 - y0) * 100.0


def visible_pins(pins: list[dict]) -> list[dict]:
    """Pins that contribute to the bounding box; edge pins are excluded."""
    return [p for p in pins if not p.get("edge")]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in metres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# component.css draws an edge arrow only for these directions.
DIR_LABELS = {"n": "nördlich", "s": "südlich"}


def format_distance_km(m: float) -> str:
    if m < 1000:
        return f"{m:.0f} m"
    return f"{m / 1000:.1f} km"


def edge_pin_info(pin: dict, bbox: BBox) -> tuple[str, float, str]:
    """Direction, distance (m), and label for an off-map pin's tooltip; edge_x/edge_y place the pin."""
    x, y = pin_percent(pin["lat"], pin["lon"], bbox)
    ns = "n" if y < 0 else "s" if y > 100 else ""
    we = "w" if x < 0 else "e" if x > 100 else ""
    direction = ns + we or "center"

    # Closest point on the bbox perimeter; clamping each axis covers the diagonals.
    lat, lon = pin["lat"], pin["lon"]
    closest_lat = {"n": bbox.north, "s": bbox.south}.get(ns, lat)
    closest_lon = {"w": bbox.west, "e": bbox.east}.get(we, lon)

    if direction not in DIR_LABELS:
        sys.exit(
            f"pin {pin['n']} lies {direction} of the map, but component.css only "
            f"draws {'/'.join(DIR_LABELS)} edge arrows: add .stuv-map-pin-edge-{direction}"
        )
    return direction, haversine_m(lat, lon, closest_lat, closest_lon), DIR_LABELS[direction]


def media_name(map_id: str, style: str) -> str:
    return f"karte-{map_id}-{'dark' if style == 'dark_all' else 'light'}.webp"


def fetch_tile(style: str, z: int, x: int, y: int) -> bytes:
    """One CARTO tile, cached on disk so re-renders don't re-fetch."""
    cached = CACHE_DIR / style / str(z) / f"{x}_{y}@2x.png"
    if cached.exists():
        return cached.read_bytes()
    request = urllib.request.Request(
        TILE_URL.format(style=style, z=z, x=x, y=y),
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        blob = response.read()
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(blob)
    return blob


def enhance(image, style: str):
    """Apply the style's anchored contrast stretch (see ENHANCE)."""
    knobs = ENHANCE[style]
    base, anchor, gain = knobs["base"], knobs["anchor"], knobs["gain"]
    lut = [
        min(255, max(0, round(base + (level - anchor) * gain))) for level in range(256)
    ]
    return image.point(lut * 3)


def render_image(data: dict, style: str):
    """Stitch the tiles covering the map's bbox, cropped to the bbox exactly."""
    from PIL import Image

    zoom = data["zoom"]
    bbox = bbox_from_pins(visible_pins(data["pins"]), data["padding_m"])
    x0, y0, x1, y1 = tile_range(bbox, zoom)
    edge = TILE * SCALE
    mosaic = Image.new("RGB", ((x1 - x0 + 1) * edge, (y1 - y0 + 1) * edge))
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            tile = Image.open(io.BytesIO(fetch_tile(style, zoom, tx, ty))).convert(
                "RGB"
            )
            mosaic.paste(tile, ((tx - x0) * edge, (ty - y0) * edge))
    left, top, right, bottom = pixel_box(bbox, zoom)
    ox, oy = x0 * edge, y0 * edge
    image = enhance(mosaic.crop((left - ox, top - oy, right - ox, bottom - oy)), style)
    target = image_size(bbox, zoom)
    if image.size != target:
        image = image.resize(target, Image.LANCZOS)
    return image


def webp_bytes(image) -> bytes:
    # The stretch roughly doubles the payload; quality 84 brings it back down without ringing.
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=84, method=6)
    return buffer.getvalue()


def write_preview(data: dict, style: str, path: pathlib.Path) -> None:
    """Dot every pin onto the rendered image to check the projection by eye."""
    from PIL import ImageDraw

    image = render_image(data, style)
    draw = ImageDraw.Draw(image)
    bbox = bbox_from_pins(visible_pins(data["pins"]), data["padding_m"])
    width, height = image.size
    for pin in data["pins"]:
        px, py = pin_percent(pin["lat"], pin["lon"], bbox)
        cx, cy = px / 100.0 * width, py / 100.0 * height
        draw.ellipse(
            (cx - 16, cy - 16, cx + 16, cy + 16),
            fill="#E2001A",
            outline="#FFFFFF",
            width=3,
        )
        draw.text((cx - 3, cy - 6), str(pin["n"]), fill="#FFFFFF")
    image.save(path)


@functools.lru_cache(maxsize=None)
def _image_hash(map_id: str, style: str) -> str:
    """First 8 chars of SHA-256 of the image file; empty if it doesn't exist."""
    path = MEDIA_DIR / media_name(map_id, style)
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def _cache_busted_url(map_id: str, style: str, media_base: str) -> str:
    """URL with ?v=<content-hash> appended so no cache survives an image change."""
    base = f"{media_base}/{media_name(map_id, style)}"
    h = _image_hash(map_id, style)
    return f"{base}?v={h}" if h else base


def maps_url(pin: dict) -> str:
    """The pin's Google-Maps link: its maps_query, else its name and address."""
    query = pin.get("maps_query") or f"{pin['name']}, {pin['detail']}"
    return MAPS_URL.format(query=urllib.parse.quote(query, safe=","))


def esc(text: str) -> str:
    """HTML-escape, apostrophes included: the inline style quotes url('...')."""
    return html.escape(str(text), quote=True)


def render_html(data: dict, media_base: str = MEDIA_BASE) -> str:
    """The core/html block: basemap frame, pin overlay, caption, legend.

    Light/dark follows the .dark class (the theme's toggle), not prefers-color-scheme, so both
    basemaps ride in as custom properties and CSS picks one. --stuv-map-ratio gives the frame
    its height before the background loads; the canvas keeps that ratio and overflows the 3:2
    phone frame, so pins and basemap crop together.
    """
    map_id = data["id"]
    bbox = bbox_from_pins(visible_pins(data["pins"]), data["padding_m"])
    width, height = image_size(bbox, data["zoom"])
    light = _cache_busted_url(map_id, "light_all", media_base)
    dark = _cache_busted_url(map_id, "dark_all", media_base)

    out = [
        "<!-- wp:html -->",
        MARKER.format(id=map_id),
        '<figure class="stuv-map">',
        '  <div class="stuv-map-frame stuv-card" role="img"'
        f' aria-label="{esc(data["alt"])}"'
        f" style=\"--stuv-map-light: url('{esc(light)}');"
        f" --stuv-map-dark: url('{esc(dark)}');"
        f' --stuv-map-ratio: {width} / {height}">',
        '    <div class="stuv-map-canvas">',
    ]
    for pin in data["pins"]:
        if pin.get("edge"):
            direction, dist_m, dir_label = edge_pin_info(pin, bbox)
            edge_cls = f" stuv-map-pin-edge stuv-map-pin-edge-{direction}"
            edge_tip = f"<br />{format_distance_km(dist_m)} {dir_label}"
            x, y = pin["edge_x"], pin["edge_y"]
        else:
            x, y = pin_percent(pin["lat"], pin["lon"], bbox)
            edge_cls = edge_tip = ""

        below = " stuv-map-pin-below" if y < TIP_BELOW else ""
        tip = (
            f'<span class="stuv-map-tip"><strong>{esc(pin["name"])}</strong>'
            f'<br />{esc(pin["detail"])}{edge_tip}</span>'
        )

        href = f' href="#karte-{map_id}-{pin["n"]}"'
        aria = f' aria-label="{esc(pin["name"])} – zum Eintrag in der Legende">'
        if pin.get("icon"):
            icon_cls = " stuv-map-pin-icon"
            icon_style = f' --stuv-map-icon: var(--ico-{esc(pin["icon"])});'
            number = ""
        else:
            icon_cls = ""
            icon_style = ""
            number = f'<span aria-hidden="true">{pin["n"]}</span>'
        out.append(
            f'      <a class="stuv-map-pin{below}{edge_cls}{icon_cls}"{href}'
            f' style="left: {x:.2f}%; top: {y:.2f}%;{icon_style}"'
            + aria
            + number
            + f"{tip}</a>"
        )
    out += [
        "    </div>",
        "  </div>",
        f'  <figcaption class="stuv-map-caption">{ATTRIBUTION}</figcaption>',
        "</figure>",
    ]
    out.append('<ol class="stuv-map-legend stuv-card">')
    for pin in data["pins"]:
        if pin.get("icon"):
            badge = (
                '<span class="stuv-map-legend-num stuv-map-legend-icon"'
                f' aria-hidden="true" style="--stuv-map-icon: var(--ico-{esc(pin["icon"])})"></span>'
            )
        else:
            badge = f'<span class="stuv-map-legend-num" aria-hidden="true">{pin["n"]}</span>'
        out += [
            f'  <li id="karte-{map_id}-{pin["n"]}">',
            f'    <p class="stuv-map-legend-head">{badge}'
            f'<strong>{esc(pin["name"])}</strong></p>',
            f'    <p class="stuv-map-legend-detail">{esc(pin["detail"])}</p>',
        ]
        if pin.get("note"):
            out.append(f'    <p class="stuv-map-legend-note">{esc(pin["note"])}</p>')
        out += [
            # The label names the place; the visible text repeats on every pin.
            f'    <p><a class="stuv-button-link" href="{esc(maps_url(pin))}"'
            f' aria-label="{esc(pin["name"])} in Karten öffnen"'
            ' target="_blank" rel="noopener noreferrer">In Karten öffnen</a></p>',
            "  </li>",
        ]
    out.append("</ol>")
    out.append("<!-- /wp:html -->")
    return "\n".join(out) + "\n"


def _bounds(lines: list[str], map_id: str) -> tuple[int, int]:
    """(start, end) line indices of the gen_map:<id> core/html block, inclusive."""
    marker = MARKER.format(id=map_id)
    marked = next((i for i, line in enumerate(lines) if line.strip() == marker), -1)
    if marked < 1 or lines[marked - 1].strip() != "<!-- wp:html -->":
        sys.exit(f"no '<!-- wp:html -->' block carrying the gen_map:{map_id} marker")
    end = next(
        (
            i
            for i in range(marked, len(lines))
            if lines[i].strip() == "<!-- /wp:html -->"
        ),
        -1,
    )
    if end < 0:
        sys.exit(f"the gen_map:{map_id} block is never closed")
    return marked - 1, end


def splice(text: str, block: str, map_id: str) -> str:
    """Replace the gen_map:<id> core/html block in `text`, keeping its indentation."""
    lines = text.split("\n")
    start, end = _bounds(lines, map_id)
    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    body = [indent + line if line else line for line in block.rstrip("\n").split("\n")]
    return "\n".join(lines[:start] + body + lines[end + 1 :])


def prettify(text: str, path: pathlib.Path) -> str:
    """Format `text` with the repo's prettier as if it were `path`, so --check can compare bytes."""
    try:
        done = subprocess.run(
            ["npx", "prettier", "--stdin-filepath", str(path)],
            input=text,
            capture_output=True,
            text=True,
            cwd=REPO,
            timeout=180,
        )
    except FileNotFoundError:
        sys.exit("gen_map needs prettier: install Node, then `npx prettier --version`")
    if done.returncode != 0:
        sys.exit(f"prettier failed on {path.name}:\n{done.stderr.strip()}")
    return done.stdout


def rendered_target(
    data: dict, path: pathlib.Path, media_base: str, current: str
) -> str:
    """`current` (the text of `path`) with a fresh map block spliced in, formatted."""
    block = render_html(data, media_base)
    return prettify(splice(current, block, data["id"]), path)


def check(data: dict, media_base: str) -> int:
    """Re-render and diff against what is committed. Writes nothing."""
    problems = []
    for style in STYLES:
        path = MEDIA_DIR / media_name(data["id"], style)
        if not path.exists():
            problems.append(f"missing {path.relative_to(REPO)}")
        elif path.read_bytes() != webp_bytes(render_image(data, style)):
            problems.append(f"{path.relative_to(REPO)} differs from a fresh render")
    for target in data["targets"]:
        path = REPO / target
        if not path.exists():
            problems.append(f"missing {target}")
            continue
        current = path.read_text(encoding="utf-8")
        if rendered_target(data, path, media_base, current) != current:
            problems.append(f"{target}: the map block differs from a fresh render")
    for problem in problems:
        print(f"drift: {problem}", file=sys.stderr)
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render a static StuV map")
    parser.add_argument("map_id", help="stem of a file in data/maps/")
    parser.add_argument(
        "--render",
        action="store_true",
        help="fetch tiles and write the webp pair into data/media/",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="splice the block HTML into the map's targets",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="re-render and diff; writes nothing, exit 1 on drift",
    )
    parser.add_argument(
        "--preview",
        metavar="PATH",
        help="write a PNG with the pins dotted on, to check the projection",
    )
    parser.add_argument(
        "--media-base",
        default=MEDIA_BASE,
        help=f"URL prefix of the uploaded images (default: {MEDIA_BASE})",
    )
    args = parser.parse_args(argv)

    data = load_map(args.map_id)

    if args.preview:
        write_preview(data, "light_all", pathlib.Path(args.preview))
        print(f"wrote {args.preview}")
        return 0
    if args.check:
        return check(data, args.media_base)
    if args.render:
        for style in STYLES:
            blob = webp_bytes(render_image(data, style))
            path = MEDIA_DIR / media_name(args.map_id, style)
            path.write_bytes(blob)
            print(f"wrote {path.relative_to(REPO)} ({len(blob):,} bytes)")
    if args.write:
        for target in data["targets"]:
            path = REPO / target
            current = path.read_text(encoding="utf-8")
            path.write_text(
                rendered_target(data, path, args.media_base, current), encoding="utf-8"
            )
            print(f"spliced the {args.map_id} block into {target}")
    if not (args.render or args.write):
        print(render_html(data, args.media_base), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
