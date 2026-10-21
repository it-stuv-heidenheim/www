"""Unit tests for tools/gen_map.py. Stdlib only — no network, no Pillow.

Run from the repo root:
    python3 -m unittest discover -s tools -p "test_*.py" -v
"""

import unittest

import gen_map

# The real map, not a copy of it: a hand-transcribed fixture drifts from
# data/maps/campus.json silently, and then these tests assert against pins the
# site does not use.
CAMPUS = gen_map.load_map("campus")
CAMPUS_PINS = CAMPUS["pins"]
SOUTH = min(p["lat"] for p in CAMPUS_PINS)
NORTH = max(p["lat"] for p in CAMPUS_PINS)
WEST = min(p["lon"] for p in CAMPUS_PINS)
EAST = max(p["lon"] for p in CAMPUS_PINS)
CAMPUS_BBOX = gen_map.bbox_from_pins(CAMPUS_PINS, CAMPUS["padding_m"])

# Minimal fixture with an edge pin for testing edge-pin logic.
# Two regular pins define the bbox; the third is far north with "edge": true.
EDGE_FIXTURE = {
    "id": "test-edge",
    "zoom": 15,
    "padding_m": 150,
    "alt": "Testkarte",
    "pins": [
        {
            "n": 1,
            "name": "Central",
            "lat": 48.680,
            "lon": 10.150,
            "detail": "Mitte",
        },
        {
            "n": 2,
            "name": "Far North",
            "lat": 48.710,
            "lon": 10.155,
            "edge": True,
            "edge_x": 50.0,
            "edge_y": 20.0,
            "detail": "Weit im Norden",
        },
        {
            "n": 3,
            "name": "South Edge",
            "lat": 48.670,
            "lon": 10.145,
            "detail": "Südrand",
        },
    ],
}
EDGE_BBOX = gen_map.bbox_from_pins(
    gen_map.visible_pins(EDGE_FIXTURE["pins"]), EDGE_FIXTURE["padding_m"]
)


class TestProject(unittest.TestCase):
    def test_origin_is_the_centre_of_the_zoom_0_tile(self):
        self.assertEqual(gen_map.project(0.0, 0.0, 0), (128.0, 128.0))

    def test_north_and_west_are_smaller(self):
        x_west, _ = gen_map.project(48.0, 10.0, 17)
        x_east, _ = gen_map.project(48.0, 11.0, 17)
        _, y_north = gen_map.project(49.0, 10.0, 17)
        _, y_south = gen_map.project(48.0, 10.0, 17)
        self.assertLess(x_west, x_east)
        self.assertLess(y_north, y_south)

    def test_zoom_doubles_the_pixel_scale(self):
        x16, y16 = gen_map.project(NORTH, WEST, 16)
        x17, y17 = gen_map.project(NORTH, WEST, 17)
        self.assertAlmostEqual(x17, x16 * 2, places=6)
        self.assertAlmostEqual(y17, y16 * 2, places=6)


class TestBBoxFromPins(unittest.TestCase):
    def test_pads_every_side_around_the_pins(self):
        bbox = CAMPUS_BBOX
        self.assertLess(bbox.south, SOUTH)
        self.assertLess(bbox.west, WEST)
        self.assertGreater(bbox.north, NORTH)
        self.assertGreater(bbox.east, EAST)

    def test_longitude_padding_is_wider_in_degrees_at_this_latitude(self):
        # 80 m of longitude spans more degrees than 80 m of latitude at 48.68°N,
        # because the meridians converge. Getting this backwards squashes the map.
        self.assertGreater(CAMPUS_BBOX.east - EAST, CAMPUS_BBOX.north - NORTH)


class TestPinPercent(unittest.TestCase):
    def test_corners_map_to_the_corners_of_the_image(self):
        bbox = CAMPUS_BBOX
        x, y = gen_map.pin_percent(bbox.north, bbox.west, bbox)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)
        x, y = gen_map.pin_percent(bbox.south, bbox.east, bbox)
        self.assertAlmostEqual(x, 100.0, places=6)
        self.assertAlmostEqual(y, 100.0, places=6)

    def test_a_lone_padded_pin_sits_in_the_middle(self):
        pin = CAMPUS_PINS[0]
        bbox = gen_map.bbox_from_pins([pin], 100)
        x, y = gen_map.pin_percent(pin["lat"], pin["lon"], bbox)
        self.assertAlmostEqual(x, 50.0, places=2)
        self.assertAlmostEqual(y, 50.0, places=2)


class TestTiling(unittest.TestCase):
    def test_the_tile_range_covers_the_pixel_box(self):
        left, top, right, bottom = gen_map.pixel_box(CAMPUS_BBOX, 17)
        x0, y0, x1, y1 = gen_map.tile_range(CAMPUS_BBOX, 17)
        edge = gen_map.TILE * gen_map.SCALE
        self.assertLessEqual(x0 * edge, left)
        self.assertLessEqual(y0 * edge, top)
        self.assertGreaterEqual((x1 + 1) * edge, right)
        self.assertGreaterEqual((y1 + 1) * edge, bottom)

    def test_the_campus_box_is_roughly_600_metres_tall(self):
        # z17 @2x is 0.39 m/px at this latitude. The pins span 462 m north-south;
        # 80 m of padding on each side puts the box near 620 m, i.e. ~1580 px. A
        # sanity bracket, not a spec: it catches a projection or scale bug, not
        # exact pixels.
        _, top, _, bottom = gen_map.pixel_box(CAMPUS_BBOX, 17)
        self.assertTrue(1400 < bottom - top < 1700, bottom - top)


class TestImageSize(unittest.TestCase):
    def test_it_clamps_to_max_width_and_keeps_the_ratio(self):
        # The campus really does overshoot: zoom is an integer, so the tiles hand
        # back more pixels than the frame can ever show. image_size is where that
        # is trimmed, so the block's ratio and the render agree by construction.
        left, top, right, bottom = gen_map.pixel_box(CAMPUS_BBOX, CAMPUS["zoom"])
        raw_width, raw_height = right - left, bottom - top
        width, height = gen_map.image_size(CAMPUS_BBOX, CAMPUS["zoom"])
        self.assertGreater(raw_width, gen_map.MAX_WIDTH)
        self.assertEqual(width, gen_map.MAX_WIDTH)
        self.assertAlmostEqual(width / height, raw_width / raw_height, places=2)

    def test_the_campus_render_is_16_by_9(self):
        width, height = gen_map.image_size(CAMPUS_BBOX, CAMPUS["zoom"])
        self.assertAlmostEqual(width / height, gen_map.ASPECT, places=2)


class TestUnproject(unittest.TestCase):
    def test_it_round_trips_project(self):
        for lat, lon in ((NORTH, EAST), (0.0, 0.0), (-33.86, 151.21)):
            x, y = gen_map.project(lat, lon, 17)
            back_lat, back_lon = gen_map.unproject(x, y, 17)
            self.assertAlmostEqual(back_lat, lat, places=9)
            self.assertAlmostEqual(back_lon, lon, places=9)


class TestFitAspect(unittest.TestCase):
    def test_it_widens_a_portrait_box_to_the_target_ratio(self):
        # The bare pin extent is portrait; without this the city map stands
        # ~1200 px tall at page width.
        tall = gen_map.BBox(48.670, 10.150, 48.690, 10.155)
        fitted = gen_map.fit_aspect(tall, 3 / 2)
        width, height = gen_map.image_size(fitted, 15)
        self.assertAlmostEqual(width / height, 3 / 2, places=2)

    def test_it_heightens_a_landscape_box_to_the_target_ratio(self):
        wide = gen_map.BBox(48.680, 10.100, 48.682, 10.200)
        fitted = gen_map.fit_aspect(wide, 3 / 2)
        width, height = gen_map.image_size(fitted, 15)
        self.assertAlmostEqual(width / height, 3 / 2, places=2)

    def test_it_only_grows_the_box_around_its_centre(self):
        box = gen_map.BBox(48.670, 10.150, 48.690, 10.155)
        fitted = gen_map.fit_aspect(box, 3 / 2)
        self.assertLessEqual(fitted.south, box.south)
        self.assertLessEqual(fitted.west, box.west)
        self.assertGreaterEqual(fitted.north, box.north)
        self.assertGreaterEqual(fitted.east, box.east)
        self.assertAlmostEqual(
            (fitted.west + fitted.east) / 2, (box.west + box.east) / 2, places=6
        )


class TestRenderHtml(unittest.TestCase):
    def setUp(self):
        self.html = gen_map.render_html(CAMPUS, media_base="https://example.test/up")

    def test_it_is_a_core_html_block_with_its_marker(self):
        lines = self.html.splitlines()
        self.assertEqual(lines[0], "<!-- wp:html -->")
        self.assertIn("gen_map:campus", lines[1])
        self.assertEqual(lines[-1], "<!-- /wp:html -->")

    def test_the_frame_carries_both_basemaps_as_custom_properties(self):
        # Dark mode on this site is class-driven (:root.dark, set before first
        # paint by the stuv-theme plugin), not OS-driven, so a <picture> with a
        # prefers-color-scheme <source> would ignore the toggle. component.css
        # picks one of these two var()s instead. Only the one that ends up in
        # background-image is ever fetched.
        for mode in ("light", "dark"):
            self.assertRegex(
                self.html,
                rf"--stuv-map-{mode}: url\('https://example\.test/up/karte-campus-"
                rf"{mode}\.webp(\?v=[a-f0-9]{{8}})?'\)",
            )

    def test_the_frame_carries_its_ratio_so_the_page_does_not_shift(self):
        # No <img> means no intrinsic size; without this the frame is 0 px tall
        # until the background loads, and everything below it jumps. It rides in
        # as a custom property because component.css needs the number twice — the
        # frame crops to 3:2 on a phone, the canvas inside it keeps the image's own.
        width, height = gen_map.image_size(CAMPUS_BBOX, CAMPUS["zoom"])
        self.assertIn(f"--stuv-map-ratio: {width} / {height}", self.html)

    def test_the_basemap_is_labelled_for_screen_readers(self):
        self.assertIn('role="img"', self.html)
        self.assertIn(f'aria-label="{CAMPUS["alt"]}"', self.html)

    def test_each_pin_links_inward_to_its_legend_entry(self):
        for pin in CAMPUS_PINS:
            self.assertIn(f'href="#karte-campus-{pin["n"]}"', self.html)
            self.assertIn(f'id="karte-campus-{pin["n"]}"', self.html)

    def test_only_the_legend_links_out(self):
        # The outbound link is labelled and deliberate; a pin never leaves the site.
        for line in self.html.splitlines():
            if 'class="stuv-map-pin' in line:
                self.assertNotIn("google.com", line)
        self.assertIn("In Karten öffnen", self.html)

    def test_the_outbound_link_points_at_the_pin_coordinates(self):
        for pin in CAMPUS_PINS:
            self.assertIn(f"query={pin['lat']:.5f},{pin['lon']:.5f}", self.html)

    def test_the_attribution_is_rendered_on_the_page(self):
        self.assertIn("© OpenStreetMap-Mitwirkende, © CARTO", self.html)

    def test_ampersands_in_links_are_escaped(self):
        self.assertIn("&amp;query=", self.html)
        self.assertNotIn("&query=", self.html.replace("&amp;query=", ""))

    def test_pins_sit_where_the_projection_puts_them(self):
        pin = CAMPUS_PINS[0]
        x, y = gen_map.pin_percent(pin["lat"], pin["lon"], CAMPUS_BBOX)
        self.assertIn(f"left: {x:.2f}%; top: {y:.2f}%", self.html)

    def test_a_pin_near_the_top_edge_opens_its_tooltip_downwards(self):
        # The frame clips (that is what crops the canvas), so a tooltip opening
        # upwards from the top of the frame would be cut in half.
        for pin in CAMPUS_PINS:
            _, y = gen_map.pin_percent(pin["lat"], pin["lon"], CAMPUS_BBOX)
            marker = f'href="#karte-campus-{pin["n"]}"'
            line = next(ln for ln in self.html.splitlines() if marker in ln)
            self.assertEqual(
                "stuv-map-pin-below" in line, y < gen_map.TIP_BELOW, f"pin {pin['n']}"
            )


class TestSplice(unittest.TestCase):
    SECTION = (
        "<!-- wp:group -->\n"
        "<div>\n"
        "  <!-- wp:html -->\n"
        "  " + gen_map.MARKER.format(id="campus") + "\n"
        "  <p>alt</p>\n"
        "  <!-- /wp:html -->\n"
        "</div>\n"
        "<!-- /wp:group -->\n"
    )

    def test_it_replaces_the_marked_block_and_keeps_its_indentation(self):
        block = (
            "<!-- wp:html -->\n"
            + gen_map.MARKER.format(id="campus")
            + "\n<p>neu</p>\n<!-- /wp:html -->\n"
        )
        out = gen_map.splice(self.SECTION, block, "campus")
        self.assertIn("  <p>neu</p>", out)
        self.assertNotIn("<p>alt</p>", out)
        self.assertTrue(out.startswith("<!-- wp:group -->"))
        self.assertTrue(out.endswith("<!-- /wp:group -->\n"))

    def test_it_is_idempotent(self):
        block = gen_map.render_html(CAMPUS)
        once = gen_map.splice(self.SECTION, block, "campus")
        twice = gen_map.splice(once, block, "campus")
        self.assertEqual(once, twice)

    def test_it_refuses_a_file_without_the_marker(self):
        with self.assertRaises(SystemExit):
            gen_map.splice(
                "<!-- wp:paragraph --><p>x</p><!-- /wp:paragraph -->\n",
                "block",
                "campus",
            )


class TestVisiblePins(unittest.TestCase):
    def test_it_drops_exactly_the_edge_pins(self):
        pins = EDGE_FIXTURE["pins"]
        self.assertEqual(gen_map.visible_pins(pins), [pins[0], pins[2]])
        self.assertEqual(gen_map.visible_pins(CAMPUS_PINS), CAMPUS_PINS)


class TestHaversine(unittest.TestCase):
    def test_one_degree_latitude_is_about_111_km(self):
        d = gen_map.haversine_m(48.0, 10.0, 49.0, 10.0)
        self.assertTrue(110_000 < d < 112_000, d)


class TestFormatDistanceKm(unittest.TestCase):
    def test_metres_below_1000_kilometres_above(self):
        self.assertEqual(gen_map.format_distance_km(0), "0 m")
        self.assertEqual(gen_map.format_distance_km(1000), "1.0 km")


class TestEdgePinInfo(unittest.TestCase):
    def setUp(self):
        self.edge_pin = EDGE_FIXTURE["pins"][1]  # "Far North", edge=True

    def test_returns_north_direction(self):
        direction, _, label = gen_map.edge_pin_info(self.edge_pin, EDGE_BBOX)
        self.assertEqual(direction, "n")
        self.assertEqual(label, "nördlich")

    def test_distance_is_a_few_kilometres(self):
        # Pin 2 is at 48.710, the bbox's north edge near 48.681: ~3.2 km.
        _, dist_m, _ = gen_map.edge_pin_info(self.edge_pin, EDGE_BBOX)
        self.assertTrue(2000 < dist_m < 4000, dist_m)


class TestValidateEdgePins(unittest.TestCase):
    def test_accepts_a_pin_inside_the_safe_zone(self):
        gen_map.validate_edge_pins(EDGE_FIXTURE)  # must not raise

    def test_rejects_a_missing_edge_x(self):
        data = {"id": "t", "pins": [{"n": 1, "edge": True, "edge_y": 20.0}]}
        with self.assertRaises(SystemExit):
            gen_map.validate_edge_pins(data)

    def test_rejects_a_value_outside_the_safe_zone(self):
        data = {
            "id": "t",
            "pins": [{"n": 1, "edge": True, "edge_x": 5.0, "edge_y": 20.0}],
        }
        with self.assertRaises(SystemExit):
            gen_map.validate_edge_pins(data)


class TestRenderHtmlWithEdgePins(unittest.TestCase):
    def setUp(self):
        self.html = gen_map.render_html(
            EDGE_FIXTURE, media_base="https://example.test/up"
        )

    def test_edge_pin_gets_directional_class(self):
        self.assertIn("stuv-map-pin-edge-n", self.html)

    def test_edge_pin_tooltip_includes_distance(self):
        self.assertRegex(self.html, r"\d+[.,]\d km nördlich")

    def test_regular_pin_has_no_edge_class(self):
        # Pin 1 ("Central") should NOT have stuv-map-pin-edge
        lines = self.html.splitlines()
        for line in lines:
            if 'href="#karte-test-edge-1"' in line:
                self.assertNotIn("stuv-map-pin-edge", line)

    def test_bbox_uses_only_visible_pins(self):
        # The ratio is derived only from pins 1 and 3; pin 2 (edge) does not count.
        width, height = gen_map.image_size(EDGE_BBOX, EDGE_FIXTURE["zoom"])
        self.assertIn(f"--stuv-map-ratio: {width} / {height}", self.html)
