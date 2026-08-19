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
        bbox = gen_map.bbox_from_pins(CAMPUS_PINS, 80)
        self.assertLess(bbox.south, SOUTH)
        self.assertLess(bbox.west, WEST)
        self.assertGreater(bbox.north, NORTH)
        self.assertGreater(bbox.east, EAST)

    def test_longitude_padding_is_wider_in_degrees_at_this_latitude(self):
        # 80 m of longitude spans more degrees than 80 m of latitude at 48.68°N,
        # because the meridians converge. Getting this backwards squashes the map.
        bbox = gen_map.bbox_from_pins(CAMPUS_PINS, 80)
        dlat = bbox.north - NORTH
        dlon = bbox.east - EAST
        self.assertGreater(dlon, dlat)

    def test_a_single_pin_still_yields_a_box(self):
        bbox = gen_map.bbox_from_pins(CAMPUS_PINS[:1], 100)
        self.assertLess(bbox.south, bbox.north)
        self.assertLess(bbox.west, bbox.east)


class TestPinPercent(unittest.TestCase):
    def test_corners_map_to_the_corners_of_the_image(self):
        bbox = gen_map.bbox_from_pins(CAMPUS_PINS, 80)
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

    def test_every_campus_pin_lands_inside_the_image(self):
        bbox = gen_map.bbox_from_pins(CAMPUS_PINS, 80)
        for pin in CAMPUS_PINS:
            x, y = gen_map.pin_percent(pin["lat"], pin["lon"], bbox)
            self.assertTrue(0.0 < x < 100.0, f"pin {pin['n']} x={x}")
            self.assertTrue(0.0 < y < 100.0, f"pin {pin['n']} y={y}")


class TestTiling(unittest.TestCase):
    def test_the_tile_range_covers_the_pixel_box(self):
        bbox = gen_map.bbox_from_pins(CAMPUS_PINS, 80)
        left, top, right, bottom = gen_map.pixel_box(bbox, 17)
        x0, y0, x1, y1 = gen_map.tile_range(bbox, 17)
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
        bbox = gen_map.bbox_from_pins(CAMPUS_PINS, 80)
        _, top, _, bottom = gen_map.pixel_box(bbox, 17)
        self.assertTrue(1400 < bottom - top < 1700, bottom - top)


class TestImageSize(unittest.TestCase):
    def test_it_clamps_to_max_width_and_keeps_the_ratio(self):
        # The campus really does overshoot: zoom is an integer, so the tiles hand
        # back more pixels than the frame can ever show. image_size is where that
        # is trimmed, so the block's ratio and the render agree by construction.
        bbox = gen_map.bbox_from_pins(CAMPUS_PINS, CAMPUS["padding_m"])
        left, top, right, bottom = gen_map.pixel_box(bbox, CAMPUS["zoom"])
        raw_width, raw_height = right - left, bottom - top
        width, height = gen_map.image_size(bbox, CAMPUS["zoom"])
        self.assertGreater(raw_width, gen_map.MAX_WIDTH)
        self.assertEqual(width, gen_map.MAX_WIDTH)
        self.assertAlmostEqual(width / height, raw_width / raw_height, places=2)

    def test_the_campus_render_is_16_by_9_and_clears_the_wordpress_threshold(self):
        bbox = gen_map.bbox_from_pins(CAMPUS_PINS, CAMPUS["padding_m"])
        width, height = gen_map.image_size(bbox, CAMPUS["zoom"])
        self.assertAlmostEqual(width / height, gen_map.ASPECT, places=2)
        self.assertLess(max(width, height), 2560)


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

    def test_it_only_ever_grows_the_box(self):
        box = gen_map.BBox(48.670, 10.150, 48.690, 10.155)
        fitted = gen_map.fit_aspect(box, 3 / 2)
        self.assertLessEqual(fitted.south, box.south)
        self.assertLessEqual(fitted.west, box.west)
        self.assertGreaterEqual(fitted.north, box.north)
        self.assertGreaterEqual(fitted.east, box.east)

    def test_it_keeps_the_centre_put(self):
        box = gen_map.BBox(48.670, 10.150, 48.690, 10.155)
        fitted = gen_map.fit_aspect(box, 3 / 2)
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
        self.assertRegex(
            self.html,
            r"--stuv-map-light: url\('https://example\.test/up/karte-campus-light"
            r"\.webp(\?v=[a-f0-9]{8})?'\)",
        )
        self.assertRegex(
            self.html,
            r"--stuv-map-dark: url\('https://example\.test/up/karte-campus-dark"
            r"\.webp(\?v=[a-f0-9]{8})?'\)",
        )

    def test_the_frame_carries_its_ratio_so_the_page_does_not_shift(self):
        # No <img> means no intrinsic size; without this the frame is 0 px tall
        # until the background loads, and everything below it jumps. It rides in
        # as a custom property because component.css needs the number twice — the
        # frame crops to 3:2 on a phone, the canvas inside it keeps the image's own.
        bbox = gen_map.bbox_from_pins(CAMPUS["pins"], CAMPUS["padding_m"])
        width, height = gen_map.image_size(bbox, CAMPUS["zoom"])
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
        bbox = gen_map.bbox_from_pins(CAMPUS["pins"], CAMPUS["padding_m"])
        pin = CAMPUS_PINS[0]
        x, y = gen_map.pin_percent(pin["lat"], pin["lon"], bbox)
        self.assertIn(f"left: {x:.2f}%; top: {y:.2f}%", self.html)

    def test_a_pin_near_the_top_edge_opens_its_tooltip_downwards(self):
        # The frame clips (that is what crops the canvas), so a tooltip opening
        # upwards from the top of the frame would be cut in half.
        bbox = gen_map.bbox_from_pins(CAMPUS["pins"], CAMPUS["padding_m"])
        for pin in CAMPUS_PINS:
            _, y = gen_map.pin_percent(pin["lat"], pin["lon"], bbox)
            marker = f'href="#karte-campus-{pin["n"]}"'
            line = next(l for l in self.html.splitlines() if marker in l)
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


if __name__ == "__main__":
    unittest.main()


class TestVisiblePins(unittest.TestCase):
    def test_excludes_edge_pins(self):
        self.assertEqual(len(gen_map.visible_pins(EDGE_FIXTURE["pins"])), 2)

    def test_includes_non_edge_pins(self):
        visible = gen_map.visible_pins(EDGE_FIXTURE["pins"])
        self.assertTrue(all(not p.get("edge") for p in visible))

    def test_returns_all_when_none_are_edge(self):
        self.assertEqual(
            len(gen_map.visible_pins(CAMPUS_PINS)), len(CAMPUS_PINS)
        )


class TestHaversine(unittest.TestCase):
    def test_zero_distance(self):
        self.assertEqual(gen_map.haversine_m(48.0, 10.0, 48.0, 10.0), 0.0)

    def test_one_degree_latitude_is_about_111_km(self):
        d = gen_map.haversine_m(48.0, 10.0, 49.0, 10.0)
        self.assertTrue(110_000 < d < 112_000, d)

    def test_one_degree_longitude_at_48_north_is_shorter(self):
        d = gen_map.haversine_m(48.0, 10.0, 48.0, 11.0)
        self.assertTrue(73_000 < d < 76_000, d)

    def test_is_symmetric(self):
        a = gen_map.haversine_m(48.68, 10.15, 48.71, 10.18)
        b = gen_map.haversine_m(48.71, 10.18, 48.68, 10.15)
        self.assertAlmostEqual(a, b, places=9)


class TestFormatDistanceKm(unittest.TestCase):
    def test_metres_below_1000(self):
        self.assertEqual(gen_map.format_distance_km(0), "0 m")
        self.assertEqual(gen_map.format_distance_km(999), "999 m")

    def test_kilometres_above_1000(self):
        self.assertEqual(gen_map.format_distance_km(1000), "1.0 km")
        self.assertEqual(gen_map.format_distance_km(2345), "2.3 km")


class TestEdgePinInfo(unittest.TestCase):
    def setUp(self):
        self.bbox = gen_map.bbox_from_pins(
            gen_map.visible_pins(EDGE_FIXTURE["pins"]),
            EDGE_FIXTURE["padding_m"],
        )
        self.edge_pin = EDGE_FIXTURE["pins"][1]  # "Far North", edge=True

    def test_returns_north_direction(self):
        direction, _, label = gen_map.edge_pin_info(self.edge_pin, self.bbox)
        self.assertEqual(direction, "n")
        self.assertEqual(label, "nördlich")

    def test_returns_positive_distance(self):
        _, dist_m, _ = gen_map.edge_pin_info(self.edge_pin, self.bbox)
        self.assertGreater(dist_m, 0)

    def test_distance_is_roughly_two_kilometres(self):
        # Pin 2 is at 48.710, bbox north is around 48.680 + padding ≈ 48.681.
        # That is ~3.2 km; the haversine distance to the bbox edge should
        # match.
        _, dist_m, _ = gen_map.edge_pin_info(self.edge_pin, self.bbox)
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

    def test_ignores_non_edge_pins(self):
        data = {"id": "t", "pins": [{"n": 1, "lat": 48.0, "lon": 10.0}]}
        gen_map.validate_edge_pins(data)  # must not raise


class TestRenderHtmlWithEdgePins(unittest.TestCase):
    def setUp(self):
        self.html = gen_map.render_html(
            EDGE_FIXTURE, media_base="https://example.test/up"
        )

    def test_edge_pin_gets_edge_class(self):
        self.assertIn("stuv-map-pin-edge", self.html)

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

    def test_edge_pin_still_links_to_legend(self):
        self.assertIn('href="#karte-test-edge-2"', self.html)
        self.assertIn('id="karte-test-edge-2"', self.html)

    def test_bbox_uses_only_visible_pins(self):
        # The bbox in the URL is derived only from pins 1 and 3.
        # Pin 2 (edge) does not contribute.
        bbox = gen_map.bbox_from_pins(
            gen_map.visible_pins(EDGE_FIXTURE["pins"]),
            EDGE_FIXTURE["padding_m"],
        )
        width, height = gen_map.image_size(bbox, EDGE_FIXTURE["zoom"])
        self.assertIn(f"--stuv-map-ratio: {width} / {height}", self.html)
