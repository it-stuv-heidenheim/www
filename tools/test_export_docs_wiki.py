"""Unit tests for tools/export_docs_wiki.py. Stdlib only.

Focused on what the export actually changes — the wphtml raw-block escape
hatch, root-relative link absolutization, and the H1 that becomes the BookStack
page name. Everything else is passed through untouched, so the load-bearing
cases here are the *negative* ones: code fences must survive verbatim. Run from
the repo root:
    python3 -m unittest discover -s tools -p "test_*.py" -v
"""

import unittest

import export_docs_wiki as e


WPHTML_DOC = """# Titel

```wphtml
<a class="stuv-button-outline" href="https://example.test/x.zip" download
   >wordpress-default-editor herunterladen (ZIP)</a>
```
"""

HTML_SAMPLE_DOC = """# Titel

```html
<p>Nur ein Beispiel</p>
```
"""


class TestWphtmlEscapeHatch(unittest.TestCase):
    def setUp(self):
        self.out = e.unwrap_wphtml(WPHTML_DOC)

    def test_it_becomes_real_markup(self):
        self.assertIn(
            '<a class="stuv-button-outline" href="https://example.test/x.zip" download',
            self.out,
        )
        self.assertIn("(ZIP)</a>", self.out)

    def test_the_fence_markers_are_gone(self):
        self.assertNotIn("```", self.out)

    def test_an_indented_fence_keeps_its_list_indentation(self):
        md_text = "1. Schritt\n\n   ```wphtml\n   <a href=\"/x.zip\">z</a>\n   ```\n"
        self.assertIn('   <a href="/x.zip">z</a>', e.unwrap_wphtml(md_text))


class TestPlainHtmlFenceStaysCode(unittest.TestCase):
    def test_a_plain_html_fence_is_left_alone(self):
        self.assertEqual(e.unwrap_wphtml(HTML_SAMPLE_DOC), HTML_SAMPLE_DOC)


class TestLinkAbsolutization(unittest.TestCase):
    SITE = "https://example.test"

    def test_root_relative_markdown_links_get_the_site_prefix(self):
        # Pasted into the wiki, "/wp-content/…" would resolve against the wiki.
        out, rewritten = e.absolutize_links("[z](/wp-content/x.zip)", self.SITE)
        self.assertEqual(out, "[z](https://example.test/wp-content/x.zip)")
        self.assertEqual(rewritten, ["/wp-content/x.zip"])

    def test_root_relative_html_attributes_are_rewritten_too(self):
        # The unwrapped wphtml button is raw markup by the time we get here.
        out, rewritten = e.absolutize_links('<a href="/wp-content/x.zip">z</a>', self.SITE)
        self.assertIn('href="https://example.test/wp-content/x.zip"', out)
        self.assertEqual(rewritten, ["/wp-content/x.zip"])

    def test_absolute_and_fragment_links_are_left_alone(self):
        text = "[a](https://other.test/a) [b](#anker)"
        out, rewritten = e.absolutize_links(text, self.SITE)
        self.assertEqual(out, text)
        self.assertEqual(rewritten, [])

    def test_a_code_fence_is_never_rewritten(self):
        # docs/content-editing.md shows a wp:image block whose src is exactly
        # this — it documents the file's contents and must stay verbatim.
        text = '```html\n<img src="/wp-content/uploads/altes-bild.jpg" />\n```\n'
        out, rewritten = e.absolutize_links(text, self.SITE)
        self.assertEqual(out, text)
        self.assertEqual(rewritten, [])

    def test_an_indented_fence_is_skipped_as_well(self):
        text = '1. So:\n\n   ```html\n   <img src="/wp-content/alt.jpg" />\n   ```\n'
        out, _ = e.absolutize_links(text, self.SITE)
        self.assertEqual(out, text)

    def test_an_inline_code_span_is_skipped(self):
        # docs/tools.md names this path in prose as `src="/wp-content/…"`;
        # rewriting it would make the docs describe markup that does not exist.
        text = 'Ein Block mit `src="/wp-content/uploads/alt.jpg"` bleibt so.'
        out, rewritten = e.absolutize_links(text, self.SITE)
        self.assertEqual(out, text)
        self.assertEqual(rewritten, [])

    def test_a_real_link_next_to_a_code_span_is_still_rewritten(self):
        text = "`/wp-content/x` und [z](/wp-content/x.zip)"
        out, rewritten = e.absolutize_links(text, self.SITE)
        self.assertEqual(out, "`/wp-content/x` und [z](https://example.test/wp-content/x.zip)")
        self.assertEqual(rewritten, ["/wp-content/x.zip"])


class TestUnresolvedMdLinks(unittest.TestCase):
    def test_a_link_to_a_sibling_doc_is_reported(self):
        # No wiki page path can be guessed from a .md filename.
        self.assertEqual(e.find_unresolved_md_links("[x](testing.md)"), ["testing.md"])

    def test_a_md_path_inside_a_fence_is_not_a_link(self):
        self.assertEqual(e.find_unresolved_md_links("```\n[x](testing.md)\n```\n"), [])

    def test_a_md_path_inside_a_code_span_is_not_a_link(self):
        self.assertEqual(e.find_unresolved_md_links("siehe `[x](testing.md)`"), [])


class TestTitleSplit(unittest.TestCase):
    def test_the_h1_becomes_the_page_name_and_leaves_the_body(self):
        # BookStack renders the page name as the heading; a kept H1 duplicates it.
        title, body = e.split_title("# Architektur\n\nText.\n", "fallback")
        self.assertEqual(title, "Architektur")
        self.assertEqual(body, "Text.\n")

    def test_a_doc_without_an_h1_keeps_its_body(self):
        title, body = e.split_title("## Nur H2\n", "architecture.md")
        self.assertEqual(title, "architecture.md")
        self.assertEqual(body, "## Nur H2\n")


class TestConvert(unittest.TestCase):
    def test_the_wphtml_button_ends_up_absolute(self):
        md_text = '# T\n\n```wphtml\n<a href="/wp-content/x.zip">z</a>\n```\n'
        title, body, rewritten, problems = e.convert(md_text, "https://example.test", "t.md")
        self.assertEqual(title, "T")
        self.assertIn('<a href="https://example.test/wp-content/x.zip">z</a>', body)
        self.assertEqual(rewritten, ["/wp-content/x.zip"])
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
