"""Rules for the plugin sources in wp-plugin/ and for check_plugins.compare().

Each plugin carries its version twice: in the header WordPress shows in
wp-admin, and in a STUV_*_VERSION constant that cache-busts its assets. Bump
only one and the site runs new PHP with old JavaScript from the browser cache,
or check_plugins.py compares against the wrong number.

Run from the repo root:
    python3 -m unittest discover -s tools -p "test_*.py" -v
"""

import unittest

import check_plugins

PLUGINS = check_plugins.local_plugins()
LOCAL = {"stuv-a": "1.2.0", "stuv-b": "2.0.0"}


class TestPluginSources(unittest.TestCase):
    def test_plugins_are_found(self):
        self.assertIn("stuv-mensa", PLUGINS)

    def test_header_version_matches_constant(self):
        for name, (header, constant) in PLUGINS.items():
            with self.subTest(plugin=name):
                self.assertIsNotNone(header, "no Version: line in the plugin header")
                self.assertEqual(header, constant)


class TestCompare(unittest.TestCase):
    def live(self, **overrides):
        records = {
            "stuv-a": {"plugin": "stuv-a/stuv-a", "status": "active", "version": "1.2.0"},
            "stuv-b": {"plugin": "stuv-b/stuv-b", "status": "active", "version": "2.0.0"},
            "other": {"plugin": "other/other", "status": "inactive", "version": "9"},
        }
        for name, record in overrides.items():
            if record is None:
                del records[name]
            else:
                records[name] = {**records[name], **record}
        return list(records.values())

    def problems(self, live):
        return dict(check_plugins.compare(LOCAL, live))

    def test_all_match(self):
        self.assertEqual(self.problems(self.live()), {"stuv-a": None, "stuv-b": None})

    def test_missing(self):
        self.assertIn("not installed", self.problems(self.live(**{"stuv-b": None}))["stuv-b"])

    def test_inactive(self):
        self.assertIn("inactive", self.problems(self.live(**{"stuv-a": {"status": "inactive"}}))["stuv-a"])

    def test_old_version(self):
        problem = self.problems(self.live(**{"stuv-a": {"version": "1.1.9"}}))["stuv-a"]
        self.assertEqual(problem, "live 1.1.9, repo 1.2.0")

    def test_plugins_not_in_the_repo_are_ignored(self):
        self.assertNotIn("other", self.problems(self.live()))


if __name__ == "__main__":
    unittest.main()
