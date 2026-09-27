"""Validates the committed data/maps/*.json against the geometry.

A map file can be syntactically fine and still produce an unusable image: a pin
outside the frame, or a render so large that WordPress rescales it on upload and
the source_url stops pointing at what we made. Both are caught here.

Run from the repo root:
    python3 -m unittest discover -s tools -p "test_*.py" -v
"""

import unittest

import gen_map

# WordPress rescales uploads larger than this on either axis ("big image" threshold),
# and the attachment's source_url then points at the -scaled derivative, not at ours.
WP_BIG_IMAGE_PX = 2560

# Derived from the directory, not typed out: a new data/maps/<id>.json is
# covered by these tests the moment it lands, instead of silently untested.
MAPS = tuple(sorted(p.stem for p in (gen_map.REPO / "data" / "maps").glob("*.json")))


class TestMapData(unittest.TestCase):
    def test_every_map_loads(self):
        for map_id in MAPS:
            with self.subTest(map=map_id):
                data = gen_map.load_map(map_id)
                self.assertEqual(data["id"], map_id)
                self.assertTrue(data["alt"])
                self.assertTrue(data["targets"])

    def test_pins_are_numbered_from_one(self):
        for map_id in MAPS:
            with self.subTest(map=map_id):
                pins = gen_map.load_map(map_id)["pins"]
                self.assertEqual([p["n"] for p in pins], list(range(1, len(pins) + 1)))

    def test_every_pin_carries_the_fields_the_legend_renders(self):
        for map_id in MAPS:
            for pin in gen_map.load_map(map_id)["pins"]:
                with self.subTest(map=map_id, pin=pin["n"]):
                    for field in ("name", "lat", "lon", "detail"):
                        self.assertIn(field, pin)
                    # The outbound link is derived from the coordinates, so a pin
                    # carrying its own would be silently ignored, not honoured.
                    self.assertNotIn("link", pin)
                    self.assertIn(
                        f"{pin['lat']:.5f},{pin['lon']:.5f}", gen_map.maps_url(pin)
                    )

    def test_every_pin_lands_inside_the_rendered_image(self):
        for map_id in MAPS:
            data = gen_map.load_map(map_id)
            bbox = gen_map.bbox_from_pins(data["pins"], data["padding_m"])
            for pin in data["pins"]:
                with self.subTest(map=map_id, pin=pin["n"]):
                    x, y = gen_map.pin_percent(pin["lat"], pin["lon"], bbox)
                    self.assertTrue(0.0 < x < 100.0, f"x={x}")
                    self.assertTrue(0.0 < y < 100.0, f"y={y}")

    def test_the_render_stays_under_the_wordpress_big_image_threshold(self):
        for map_id in MAPS:
            data = gen_map.load_map(map_id)
            bbox = gen_map.bbox_from_pins(data["pins"], data["padding_m"])
            width, height = gen_map.image_size(bbox, data["zoom"])
            with self.subTest(map=map_id):
                self.assertLess(width, WP_BIG_IMAGE_PX, f"{map_id} is {width} px wide")
                self.assertLess(height, WP_BIG_IMAGE_PX, f"{map_id} is {height} px tall")
                self.assertGreater(min(width, height), 400)


if __name__ == "__main__":
    unittest.main()
