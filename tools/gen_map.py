#!/usr/bin/env python3
"""Render the static, pin-annotated maps for the StuV site.

Reads a map definition from data/maps/<id>.json, fetches CARTO basemap tiles
once at build time, composites them into data/media/karte-<id>-{light,dark}.webp,
and emits the Gutenberg core/html block that shows the image with its pin overlay
and legend. Nothing here talks to the WordPress REST API: the images go up with
the skill's upload_media.py, the blocks with deploy.py.

The geometry is stdlib-only so it stays unit-testable. Pillow is imported lazily
and is needed only for --render, --preview and --check; --write and --check also
shell out to `npx prettier`, which owns the formatting of the block HTML.

    pip install Pillow
    python3 tools/gen_map.py campus --render      # fetch tiles, write the webp pair
    python3 tools/gen_map.py campus --write       # splice the block into its targets
    python3 tools/gen_map.py campus --check       # re-render and diff; writes nothing
    python3 tools/gen_map.py campus               # print the block to stdout

--check compares WebP bytes. A Pillow or libwebp upgrade can change the encoder's
output for identical input; when that happens, re-render and commit the images.

Tiles are cached under ~/.cache/stuv-map-tiles/, so re-runs hit CARTO once.
"""

import argparse
import hashlib
import html
import io
import json
import math
import pathlib
import subprocess
import sys
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

# The frame is never wider than the content column (~1200 px), so 2400 px covers
# a 2x display exactly and anything past it is bytes nobody can see. Zoom is an
# integer, so the raw mosaic overshoots (the campus comes off the tiles 2804 px
# wide) and image_size() trims it back. That also keeps the render under the
# 2560 px WordPress big-image threshold, above which WordPress rescales the
# upload and source_url stops pointing at the file we made. Never upscales --
# the city map is under the cap already.
MAX_WIDTH = 2400

# Both sets of pins run north-south, so their bare extent is portrait: the city
# map would come out 800x1244 and stand ~1200 px tall at page width. The frame
# has to use the image's true aspect ratio -- pin positions are percentages of
# the whole image, so cropping to a nicer shape would slide every pin off its
# building. Widening the box instead keeps the pins exactly where they are and
# just shows more basemap around them.
#
# 16:9 is also the *widest* shape the frame is ever asked to show. Under 600 px
# the frame is 3:2 again (a 16:9 map is a letterbox slit on a phone), and
# component.css gets that by letting the sides of this image overflow the frame.
# Rendering wide and cropping narrow only ever eats the padding that fit_aspect
# added; rendering 3:2 and cropping to 16:9 on desktop would eat the top and
# bottom, which is where the outermost pins actually are.
ASPECT = 16 / 9

# CARTO's Positron and Dark Matter are deliberately washed out -- they are made
# to sit *under* a data layer, and on Positron the land (247), the buildings
# (237) and the roads (250) all live in the top 20 levels of white. Scaling every
# pixel away from the basemap's own background level pulls those apart: the
# background stays where the designers put it and everything drawn on top of it
# gains contrast, in place, without a hue shift. The channels scale with it, so
# the greens and blues deepen too and no separate saturation pass is needed.
#
#   base:   what the land ends up at
#   anchor: what the land is now (Positron pivots on white instead, so its own
#           247 moves down with everything else and the paper stays paper)
#   gain:   how much further from that everything else is pushed
#
# Dark Matter needs the lift: its land is 8 and its buildings are 0, so a pass
# anchored at the land alone would clip the buildings into the land and dissolve
# the block edges. Ending the land at 18 keeps them 14 levels apart.
ENHANCE = {
    "light_all": {"base": 255, "anchor": 255, "gain": 2.2},
    "dark_all": {"base": 18, "anchor": 8, "gain": 1.7},
}

TILE_URL = "https://a.basemaps.cartocdn.com/{style}/{z}/{x}/{y}@2x.png"
# Cloudflare fronts the site and CARTO bans the stdlib default UA outright.
USER_AGENT = "stuv-map-render/1.0 (+https://stuv-heidenheim.de)"

# A pin this far down (in % of the frame) has room for a tooltip above it; one
# higher up gets the tooltip below instead, or the frame clips it away.
TIP_BELOW = 25.0

# Edge pins are placed by hand (edge_x/edge_y in data/maps/*.json) rather than
# projected and clamped like other pins -- their real lat/lon only drives the
# distance/direction text in the tooltip now. These are the bounds those
# hand-picked values must stay inside.
#
# The two axes are not symmetric, and treating them as one number is what used
# to strand the north/south pins 15% inside the frame, where they read as real
# locations at the wrong spot instead of "off the map, this way".
#
# X is the tight one: under 640px the frame goes 3:2 while the canvas keeps its
# 16:9, so (16/9 - 3/2) / (16/9) = 15.6% of the image hides, ~7.8% per side (see
# .stuv-map-frame in component.css). Add the pin's own half-width and the CSS
# arrow's overshoot past the circle and 15% is about the first safe column.
#
# Y is never cropped -- the canvas is exactly as tall as the frame. Only the pin
# itself has to stay inside, and on the shortest frame the site renders (a phone,
# ~218px tall) the 28px circle is 12.8% of that, so 6% puts the pin flush against
# the edge with its rim just inside. The arrow beyond it is clipped at that size;
# on desktop, where the frame is ~576px tall, both clear comfortably.
SAFE_ZONE_X = (15.0, 85.0)
SAFE_ZONE_Y = (6.0, 94.0)

# Root-relative: the same markup has to render on the staging host and on
# production, and an absolute URL would pin every map to whichever host it was
# generated against.
MEDIA_BASE = "/wp-content/uploads"
ATTRIBUTION = "© OpenStreetMap-Mitwirkende, © CARTO"

# The legend's outbound link, built from the pin's own lat/lon rather than stored
# per pin: the coordinates are already the single source of truth for where the
# pin sits on the image, so the link cannot drift away from it. Searching by name
# instead would leave Google guessing at a German place name and can land a
# street away. Nothing is requested until a visitor clicks -- the basemap itself
# stays self-hosted.
MAPS_URL = "https://www.google.com/maps/search/?api=1&query={lat:.5f},{lon:.5f}"
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
    """Every edge pin needs a hand-placed edge_x/edge_y inside its axis' bounds.

    Catching a missing or unsafe value here turns a pin silently clipped in a
    visitor's browser into a build-time error instead.
    """
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
    """Grow the short axis about the centre until the box is `aspect` wide:tall.

    Measured in projected pixels, not degrees: Mercator stretches latitude, so a
    box that looks 3:2 in degrees is not 3:2 on screen.
    """
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
    """Pixel size of the image render_image() actually writes, MAX_WIDTH included.

    The clamp lives here rather than next to the resize so that everything that
    reasons about the render reads one number: the block's --stuv-map-ratio, the
    WordPress big-image check in the tests, and the resize itself.
    """
    left, top, right, bottom = pixel_box(bbox, zoom)
    width, height = right - left, bottom - top
    if width > MAX_WIDTH:
        height = round(height * MAX_WIDTH / width)
        width = MAX_WIDTH
    return width, height


def pin_percent(lat: float, lon: float, bbox: BBox) -> tuple[float, float]:
    """Pin position as a percentage of the cropped image, top-left origin.

    Zoom-independent: the Mercator scale factor cancels in the ratio. The integer
    rounding in pixel_box shifts this by at most one pixel (~0.4 m), an order of
    magnitude below the pin's own diameter.
    """
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


DIR_LABELS = {
    "n": "nördlich",
    "ne": "nordöstlich",
    "e": "östlich",
    "se": "südöstlich",
    "s": "südlich",
    "sw": "südwestlich",
    "w": "westlich",
    "nw": "nordwestlich",
}


def format_distance_km(m: float) -> str:
    if m < 1000:
        return f"{m:.0f} m"
    return f"{m / 1000:.1f} km"


def edge_pin_info(pin: dict, bbox: BBox) -> tuple[str, float, str]:
    """Direction, distance (m), and label for an off-map pin's tooltip text.

    The pin's percentage position relative to the rendered bbox decides only
    which side(s) it lies beyond -- any value outside [0, 100] means the pin is
    off that edge of the frame. Where the pin is actually drawn is a separate,
    hand-placed edge_x/edge_y (see render_html and SAFE_ZONE_MIN/MAX); this
    function never returns a screen position.
    """
    x, y = pin_percent(pin["lat"], pin["lon"], bbox)

    beyond_n = y < 0
    beyond_s = y > 100
    beyond_w = x < 0
    beyond_e = x > 100

    dirs = []
    if beyond_n:
        dirs.append("n")
    if beyond_s:
        dirs.append("s")
    if beyond_w:
        dirs.append("w")
    if beyond_e:
        dirs.append("e")
    direction = "".join(dirs) if dirs else "center"

    # Closest point on the bbox perimeter
    lat, lon = pin["lat"], pin["lon"]
    if direction == "n":
        closest_lat, closest_lon = bbox.north, lon
    elif direction == "s":
        closest_lat, closest_lon = bbox.south, lon
    elif direction == "e":
        closest_lat, closest_lon = lat, bbox.east
    elif direction == "w":
        closest_lat, closest_lon = lat, bbox.west
    elif direction == "ne":
        closest_lat, closest_lon = bbox.north, bbox.east
    elif direction == "nw":
        closest_lat, closest_lon = bbox.north, bbox.west
    elif direction == "se":
        closest_lat, closest_lon = bbox.south, bbox.east
    elif direction == "sw":
        closest_lat, closest_lon = bbox.south, bbox.west
    else:
        closest_lat, closest_lon = lat, lon

    dist_m = haversine_m(lat, lon, closest_lat, closest_lon)
    label = DIR_LABELS.get(direction, "außerhalb")

    return direction, dist_m, label


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
    # The stretch roughly doubles the WebP payload -- flat washed-out basemaps are
    # exactly what the encoder is good at, and contrast is entropy. 84 buys most of
    # that back and leaves no ringing on the labels at the size they are shown.
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=84, method=6)
    return buffer.getvalue()


def render_webps(data: dict) -> dict[str, bytes]:
    return {style: webp_bytes(render_image(data, style)) for style in STYLES}


def write_preview(data: dict, style: str, path: pathlib.Path) -> None:
    """Dot every pin onto the rendered image so the projection can be checked by eye.

    A projection bug produces a plausible-looking map with the Mensa in a car park;
    no unit test catches that. This is the check that does.
    """
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


def _image_hash(map_id: str, style: str) -> str:
    """First 8 chars of SHA-256 of the image file on disk.

    Returns empty string if the file doesn't exist (run --render first).
    """
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
    """The pin's Google-Maps link, from its coordinates."""
    return MAPS_URL.format(lat=pin["lat"], lon=pin["lon"])


def esc(text: str) -> str:
    """HTML-escape, apostrophes included: the inline style quotes url('...')."""
    return html.escape(str(text), quote=True)


def render_html(data: dict, media_base: str = MEDIA_BASE) -> str:
    """The core/html block: the basemap frame, the pin overlay, the caption, the legend.

    The light/dark swap is class-driven, not OS-driven: the stuv-theme plugin puts
    .dark on <html> before first paint, so a <picture> with a prefers-color-scheme
    <source> would ignore the site's own toggle. The frame carries both basemaps as
    custom properties instead and component.css picks one in background-image. An
    unreferenced var() is never fetched, so this still costs exactly one request.

    That means no <img>, hence no intrinsic size, hence the explicit ratio: without
    it the frame is 0 px tall until the background arrives and the whole page below
    it jumps. It rides in as --stuv-map-ratio rather than as aspect-ratio, because
    component.css needs the number twice -- the frame is 3:2 on a phone and the
    image's own 16:9 on a desktop, and the inner .stuv-map-canvas is what always
    keeps the image's ratio, overflowing the frame's sides when the two disagree.
    The basemap and the pins share that canvas, so a crop moves them together and
    no pin ever slides off its building.

    Pins are positioned in percent, so they scale with the frame and need no JS.
    Each pin links to its legend entry; the legend is always rendered and is the
    accessible, touch and print path to the same content.

    A tooltip opens upwards, and the frame has to clip (that is what crops the
    canvas), so a pin in the top TIP_BELOW of the frame gets one that opens
    downwards instead. The threshold is generous: the box is only as tall as the
    padding around the outermost pins, so on both maps a pin does sit that close
    to the top edge.
    """
    map_id = data["id"]
    bbox = bbox_from_pins(visible_pins(data["pins"]), data["padding_m"])
    width, height = image_size(bbox, data["zoom"])
    light = _cache_busted_url(map_id, "light_all", media_base)
    dark = _cache_busted_url(map_id, "dark_all", media_base)

    legend_pins = {p["n"] for p in data["pins"] if p.get("legend")}
    has_legend = len(legend_pins) > 0

    def _pin_has_legend(pin):
        return not has_legend or pin["n"] in legend_pins

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
            dist = format_distance_km(dist_m)
            edge_cls = f" stuv-map-pin-edge stuv-map-pin-edge-{direction}"
            x, y = pin["edge_x"], pin["edge_y"]
        else:
            x, y = pin_percent(pin["lat"], pin["lon"], bbox)
            edge_cls = ""

        below = " stuv-map-pin-below" if y < TIP_BELOW else ""

        tip_parts = [f'<strong>{esc(pin["name"])}</strong><br />{esc(pin["detail"])}']
        if pin.get("edge"):
            tip_parts.append(f"<br />{dist} {dir_label.lower()}")
        tip = f'<span class="stuv-map-tip">{"".join(tip_parts)}</span>'

        has_link = _pin_has_legend(pin)
        tag = "a" if has_link else "span"
        href = f' href="#karte-{map_id}-{pin["n"]}"' if has_link else ""
        aria = (
            f' aria-label="{esc(pin["name"])} – zum Eintrag in der Legende">'
            if has_link
            else f' aria-label="{esc(pin["name"])}">'
        )
        closing = "</a>" if has_link else "</span>"
        if pin.get("icon"):
            icon_cls = " stuv-map-pin-icon"
            icon_style = f' --stuv-map-icon: var(--ico-{esc(pin["icon"])});'
            number = ""
        else:
            icon_cls = ""
            icon_style = ""
            number = f'<span aria-hidden="true">{pin["n"]}</span>'
        out.append(
            f'      <{tag} class="stuv-map-pin{below}{edge_cls}{icon_cls}"{href}'
            f' style="left: {x:.2f}%; top: {y:.2f}%;{icon_style}"'
            + aria
            + number
            + f"{tip}{closing}"
        )
    out += [
        "    </div>",
        "  </div>",
        f'  <figcaption class="stuv-map-caption">{ATTRIBUTION}</figcaption>',
        "</figure>",
    ]
    out.append('<ol class="stuv-map-legend">')
    for pin in data["pins"]:
        if not _pin_has_legend(pin):
            continue
        if pin.get("icon"):
            badge = (
                '<span class="stuv-map-legend-num stuv-map-legend-icon"'
                f' aria-hidden="true" style="--stuv-map-icon: var(--ico-{esc(pin["icon"])})"></span>'
            )
        else:
            badge = f'<span class="stuv-map-legend-num" aria-hidden="true">{pin["n"]}</span>'
        out += [
            f'  <li id="karte-{map_id}-{pin["n"]}" class="stuv-card">',
            f'    <p class="stuv-map-legend-head">{badge}'
            f'<strong>{esc(pin["name"])}</strong></p>',
            f'    <p class="stuv-map-legend-detail">{esc(pin["detail"])}</p>',
        ]
        if pin.get("note"):
            out.append(f'    <p class="stuv-map-legend-note">{esc(pin["note"])}</p>')
        out += [
            f'    <p><a class="stuv-button-link" href="{esc(maps_url(pin))}"'
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
    """Format `text` with the repo's prettier, as if it were `path`.

    What render_html() emits is not what ends up in the file. Prettier owns block
    HTML in this repo (AGENTS.md): it rewrites url('x') to url("x"), adds the
    trailing semicolon to an inline style, breaks long tags one attribute per line
    and wraps text nodes. Formatting the spliced file here is what lets --check
    compare bytes instead of guessing at an equivalence rule, and it leaves
    `npx prettier --check .` green straight after a --write.
    """
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


def rendered_target(data: dict, path: pathlib.Path, media_base: str) -> str:
    """`path` with a freshly generated map block spliced in, formatted as committed."""
    block = render_html(data, media_base)
    spliced = splice(path.read_text(encoding="utf-8"), block, data["id"])
    return prettify(spliced, path)


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
        if rendered_target(data, path, media_base) != path.read_text(encoding="utf-8"):
            problems.append(f"{target}: the map block differs from a fresh render")
    for problem in problems:
        print(f"drift: {problem}", file=sys.stderr)
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render a static StuV map")
    parser.add_argument("map_id", help="stem of a file in data/maps/ (campus, stadt)")
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
        for style, blob in render_webps(data).items():
            path = MEDIA_DIR / media_name(args.map_id, style)
            path.write_bytes(blob)
            print(f"wrote {path.relative_to(REPO)} ({len(blob):,} bytes)")
    if args.write:
        for target in data["targets"]:
            path = REPO / target
            path.write_text(
                rendered_target(data, path, args.media_base), encoding="utf-8"
            )
            print(f"spliced the {args.map_id} block into {target}")
    if not (args.render or args.write):
        print(render_html(data, args.media_base), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
