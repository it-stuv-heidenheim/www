"""Rules for the deployed block HTML that the Gutenberg validator does not check.

blockcheck proves that each block matches its save() output. It does not
notice a link to an anchor that no longer exists, a block whose JSON says one
font weight while its markup says another, or a crisis notice that drifted
below the form. Each test here exists because one of those reached the site.

Run from the repo root:
    python3 -m unittest discover -s tools -p "test_*.py" -v
"""

import re
import unittest
import urllib.parse

import sitecheck as sc

# Every contact address the site may link. A new one is added here on purpose;
# a misspelt one (an Instagram handle with an extra underscore, a digit missing
# from a crisis line) fails instead of shipping. Normalized by contact_key().
CONTACTS = {
    "tel:112",
    "tel:+498001110111",  # Telefonseelsorge
    "tel:+498001110222",  # Telefonseelsorge
    "tel:+49731790315100",  # PBS Studierendenwerk Ulm
    "mailto:vorsitz@stuv-heidenheim.de",
    "mailto:pbs@studierendenwerk-ulm.de",
    "instagram.com/stuvheidenheim",
    "instagram.com/awarenessheidenheim",
    "instagram.com/connectheidenheim",
    "instagram.com/hochschulsporthdh",
    "wa.me/message/NELC2NH5VK65D1",
    "chat.whatsapp.com/Ifuw41vBTJb7l4emQcKNi3",
    "forms.gle/RTqLmyPasqMUMexy7",
}
CONTACT_HOSTS = {"instagram.com", "wa.me", "chat.whatsapp.com", "forms.gle"}

# Link texts that say nothing once read out of context, which is how a screen
# reader's link list presents them.
GENERIC_LINK_TEXT = {
    "besuchen", "hier", "hier klicken", "klick hier", "link", "mehr",
    "mehr erfahren", "mehr lesen", "weiter", "zur seite",
}

# Blocks whose style attribute core serializes onto the root element.
STYLED_ROOT_BLOCKS = {"paragraph", "heading", "group", "list", "columns", "column", "details", "separator"}

# Kummer Karsten: someone in crisis must meet these numbers before the form.
CRISIS_NUMBERS = {"tel:112", "tel:+498001110111", "tel:+498001110222"}


def contact_key(href):
    if href.startswith(("tel:", "mailto:")):
        return href.replace(" ", "")
    url = urllib.parse.urlsplit(href)
    host = url.netloc.lower().removeprefix("www.")
    if host not in CONTACT_HOSTS:
        return None
    return f"{host}{url.path.rstrip('/')}"


def link_text(a):
    return a.attrs.get("aria-label") or a.text


def norm_link_text(text):
    return " ".join(re.sub(r"[→←›»]", " ", text).lower().split())


# Each page as served: its own blocks plus the header and footer template parts.
PAGES = sc.pages()
PARTS = sc.template_parts()
CHROME = "".join(PARTS.values())
DOCS = {url: sc.Doc(markup + CHROME) for url, markup in PAGES.items()}
FILES = sc.deployed_files()


class TestMarkup(unittest.TestCase):
    def test_tags_are_balanced(self):
        for f in FILES:
            with self.subTest(file=str(f.relative_to(sc.REPO))):
                self.assertEqual(sc.Doc(f.read_text()).errors, [])

    def test_block_json_has_no_raw_double_dash(self):
        # `--` ends an HTML comment early; Gutenberg writes it as \u002d\u002d.
        for f in FILES:
            for block in sc.blocks(f.read_text()):
                with self.subTest(file=str(f.relative_to(sc.REPO)), line=block.line):
                    self.assertNotIn("--", block.raw_json)

    def test_block_json_matches_inline_style(self):
        # The validator accepts a mismatch here, the editor does not: opening
        # the page re-saves the JSON value and the look changes silently.
        for f in FILES:
            for block in sc.blocks(f.read_text()):
                if block.name not in STYLED_ROOT_BLOCKS or not block.root_tag:
                    continue
                want = sc.expected_inline_style(block.attrs.get("style") or {})
                have = sc.parse_inline_style(sc.attr_value(block.root_attrs, "style"))
                for prop, value in want.items():
                    with self.subTest(file=str(f.relative_to(sc.REPO)), line=block.line, prop=prop):
                        self.assertEqual(
                            sc.norm_css_value(have.get(prop, "<missing>")), sc.norm_css_value(value)
                        )

    def test_stuv_classes_exist(self):
        # A class is defined if component.css styles it or a plugin script hooks it.
        defined = set(re.findall(r"\.(stuv-[a-z0-9_-]+)", sc.component_css()))
        for src in (sc.REPO / "wp-plugin").rglob("*"):
            if src.suffix in {".js", ".php"}:
                defined |= set(re.findall(r"\bstuv-[a-z0-9_-]+", src.read_text()))
        for f in FILES:
            used = set(re.findall(r"\bstuv-[a-z0-9_-]+", " ".join(re.findall(r'class="([^"]*)"', f.read_text()))))
            with self.subTest(file=str(f.relative_to(sc.REPO))):
                self.assertEqual(sorted(used - defined), [])

    def test_no_inline_primary_fill(self):
        # --stuv-primary is lightened for text in dark mode, and white on it is
        # 3.85:1. A fill under text is --stuv-primary-surface, best via a class
        # (.stuv-section-primary, .stuv-badge, .stuv-steps).
        for f in FILES:
            with self.subTest(file=str(f.relative_to(sc.REPO))):
                self.assertNotRegex(f.read_text(), r"background(-color)?:\s*var\(--stuv-primary\)")

    def test_no_inline_text_transform(self):
        # Section labels use .stuv-kicker; inline uppercase means a hand-rolled one.
        for f in FILES:
            with self.subTest(file=str(f.relative_to(sc.REPO))):
                self.assertNotRegex(f.read_text(), r'style="[^"]*text-transform')

    def test_buttons_are_button_blocks(self):
        # Content buttons are wp:button blocks with a block style (none,
        # is-style-outline, is-style-overlay). The stuv-button-* variants match
        # only a bare <a>/<button>: on a wp:button wrapper they style nothing,
        # and a button link in a paragraph misses the wp:buttons layout.
        for f in FILES:
            with self.subTest(file=str(f.relative_to(sc.REPO))):
                self.assertNotRegex(f.read_text(), r"\bstuv-button-(primary|outline|overlay)\b")


class TestLinks(unittest.TestCase):
    def test_internal_links_resolve(self):
        for url, doc in DOCS.items():
            for a in doc.links:
                href = a.attrs["href"]
                if href.startswith(("http:", "https:", "mailto:", "tel:", "/wp-content/")):
                    continue
                path, _, fragment = href.partition("#")
                target = path or url
                with self.subTest(page=url, href=href, line=a.line):
                    self.assertIn(target, DOCS, "no page at that path")
                    if fragment:
                        self.assertIn(fragment, DOCS[target].ids, "no element with that id")

    def test_link_text_is_descriptive(self):
        for url, doc in DOCS.items():
            seen = {}
            for a in doc.links:
                text = norm_link_text(link_text(a))
                with self.subTest(page=url, line=a.line, text=text):
                    self.assertTrue(text, "link without text or aria-label")
                    self.assertNotIn(text, GENERIC_LINK_TEXT)
                    href = a.attrs["href"]
                    self.assertEqual(seen.setdefault(text, href), href, "same text, different target")

    def test_contacts_are_known(self):
        for f in FILES:
            for href in re.findall(r'href="([^"]+)"', f.read_text()):
                key = contact_key(href)
                if key is None:
                    continue
                with self.subTest(file=str(f.relative_to(sc.REPO)), href=href):
                    self.assertIn(key, CONTACTS)

    def test_nav_reaches_every_page(self):
        nav = sc.Doc("".join(PARTS.values()))
        targets = {a.attrs["href"].partition("#")[0] for a in nav.links}
        self.assertEqual(sorted(set(PAGES) - targets), [])


class TestCards(unittest.TestCase):
    def test_links_filling_a_clip_card_are_card_links(self):
        # A link that fills .stuv-clip has its focus ring clipped; only the card
        # link classes get a ring drawn on the card itself.
        for url, doc in DOCS.items():
            for a in doc.links:
                if a.parent is not None and "stuv-clip" in a.parent.classes:
                    with self.subTest(page=url, line=a.line, href=a.attrs["href"]):
                        self.assertTrue(a.classes & set(sc.CARD_LINK_CLASSES))

    def test_card_links_sit_in_a_card(self):
        # .stuv-card-cover stretches over its nearest positioned ancestor; outside
        # a card that is some section, and the link swallows every click there.
        for url, doc in DOCS.items():
            cards = {}
            for a in doc.links:
                if a.classes & set(sc.CARD_LINK_CLASSES):
                    card = a.closest("stuv-card")
                    with self.subTest(page=url, line=a.line):
                        self.assertIsNotNone(card, "card link outside .stuv-card")
                        self.assertNotIn(id(card), cards, "two card links in one card")
                    cards[id(card)] = a


class TestPages(unittest.TestCase):
    def test_crisis_notice_comes_before_the_form(self):
        page = PAGES["/kummer-karsten/"]
        doc = sc.Doc(page)
        crisis = [el for el in doc.elements if "stuv-crisis" in el.classes]
        self.assertEqual(len(crisis), 1, "exactly one .stuv-crisis block")
        self.assertLess(page.index("stuv-crisis"), page.index("[wpforms"))
        numbers = {a.attrs["href"] for a in doc.links if a.closest("stuv-crisis")}
        self.assertEqual(numbers & CRISIS_NUMBERS, CRISIS_NUMBERS)

    def test_copyright_year_is_kept_current(self):
        # stuv-theme replaces the year inside .stuv-copyright on every render.
        for f in FILES:
            for el in sc.Doc(f.read_text()).elements:
                if el.tag == "p" and re.search(r"©\s*20\d\d", el.text):
                    with self.subTest(file=str(f.relative_to(sc.REPO)), line=el.line):
                        self.assertIn("stuv-copyright", el.classes)

if __name__ == "__main__":
    unittest.main()
