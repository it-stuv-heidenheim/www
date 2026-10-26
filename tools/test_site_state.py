"""Tests for site_state.py's page parser and the committed snapshot. The markup is cut down
from WPForms 2.0 and The SEO Framework 5.2; the honeypot field is random on every view."""

import json
import re
import unittest

import site_state

PAGE = """<html><head>
<meta name="robots" content="max-snippet:-1">
<link rel="canonical" href="https://example.org/kontakt/">
<meta name="description" content="So erreichst du uns.">
<meta property="og:title" content="Kontakt">
<meta property="og:image" content="https://example.org/og.jpg">
<meta name="viewport" content="width=device-width">
<title>
Kontakt - StuV
</title>
</head><body>
<form id="wpforms-form-129" class="wpforms-validate">
<div class="wpforms-field-container">
<div id="wpforms-129-field_1-container" class="wpforms-field wpforms-field-name" data-field-id="1">
<fieldset><legend class="wpforms-field-label">Name <span class="wpforms-required-label" aria-hidden="true">*</span></legend>
<label for="x" class="wpforms-field-sublabel after">Vorname</label></fieldset></div>
<div id="wpforms-129-field_4-container"
  class="wpforms-field wpforms-field-text"
  data-field-type="text"
  data-field-id="4"
  ><label class="wpforms-field-label">E-Mail-Adresse Name</label></div>
<div id="wpforms-129-field_2-container" class="wpforms-field wpforms-field-select" data-field-id="2">
<label class="wpforms-field-label">Anliegen (optional)</label>
<select><option>Studium</option><option>Feedback</option></select></div>
</div>
<div class="wpforms-submit-container"><button type="submit" class="wpforms-submit">Absenden</button></div>
</form>
</body></html>"""


class TestServed(unittest.TestCase):
    def setUp(self):
        self.served = site_state.Served(PAGE)

    def test_seo_tags(self):
        self.assertEqual(self.served.seo, {
            "robots": "max-snippet:-1",
            "canonical": "https://example.org/kontakt/",
            "description": "So erreichst du uns.",
            "og:title": "Kontakt",
            "og:image": "https://example.org/og.jpg",
            "title": "Kontakt - StuV",
        })

    def test_fields_without_the_honeypot(self):
        self.assertEqual(self.served.forms["129"]["fields"], [
            {"id": 1, "type": "name", "label": "Name", "required": True},
            {"id": 2, "type": "select", "label": "Anliegen (optional)", "required": False,
             "options": ["Studium", "Feedback"]},
        ])

    def test_submit_text(self):
        self.assertEqual(self.served.forms["129"]["submit"], "Absenden")


class TestSnapshot(unittest.TestCase):
    def test_holds_no_email_address(self):
        # The repo is public: the admin address and form recipients stay out.
        text = site_state.STATE_PATH.read_text()
        self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text))

    def test_is_canonical(self):
        # --write output, so a hand edit or a formatter pass shows up here.
        text = site_state.STATE_PATH.read_text()
        self.assertEqual(text, site_state.dump(json.loads(text)))


if __name__ == "__main__":
    unittest.main()
