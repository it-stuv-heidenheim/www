"""Design-token contrast and component.css invariants.

The contrast pairs below are the ones a visitor actually sees: text on the
three surfaces (page, section band, card), the focus ring, input borders and
button labels, each in light and dark mode. The values are resolved from
component.css and global-styles.json exactly as the browser would, so a palette
change that drops a pair below its minimum fails here instead of on the site.

Run from the repo root:
    python3 -m unittest discover -s tools -p "test_*.py" -v
"""

import re
import unittest

import sitecheck as sc

# WCAG 2.2: 4.5:1 for body text (1.4.3), 3:1 for UI component boundaries and
# focus indicators (1.4.11). CARD_EDGE is a house rule, not WCAG: dark mode has
# no visible shadow, so the card border alone has to separate card from page.
TEXT = 4.5
UI = 3.0
CARD_EDGE = 1.5

# (foreground token, surface, minimum). Surfaces are resolved in surfaces().
PAIRS = [
    ("--stuv-foreground", "page", TEXT),
    ("--stuv-foreground", "card", TEXT),
    ("--stuv-muted-foreground", "page", TEXT),
    ("--stuv-muted-foreground", "band", TEXT),
    ("--stuv-muted-foreground", "card", TEXT),
    # Links are primary-coloured text.
    ("--stuv-primary", "page", TEXT),
    ("--stuv-primary", "band", TEXT),
    ("--stuv-primary", "card", TEXT),
    ("--stuv-ring", "page", UI),
    ("--stuv-ring", "band", UI),
    ("--stuv-ring", "card", UI),
    # Form fields sit on a card and are filled with the page colour.
    ("--stuv-input", "page", UI),
    ("--stuv-input", "card", UI),
    # The Kummer Karsten crisis notice. Its phone links are alert-foreground,
    # not primary: dark red on the dark amber wash is only 4.3:1.
    ("--stuv-alert-foreground", "alert", TEXT),
    ("--stuv-ring", "alert", UI),
]


def surfaces(env):
    page = sc.parse_color(sc.resolve_vars("var(--stuv-background)", env))
    band = sc.over(sc.parse_color(sc.resolve_vars("var(--wp--preset--color--band)", env)), page)
    card = sc.over(sc.parse_color(sc.resolve_vars("var(--stuv-card)", env)), page)
    alert = sc.over(sc.parse_color(sc.resolve_vars("var(--stuv-alert-bg)", env)), page)
    return {"page": page, "band": band, "card": card, "alert": alert}


def colour(token, env, surface):
    return sc.over(sc.parse_color(sc.resolve_vars(f"var({token})", env)), surface)


class TestContrast(unittest.TestCase):
    def test_token_pairs(self):
        for dark in (False, True):
            env = sc.root_custom_properties(dark=dark)
            surf = surfaces(env)
            for token, surface, minimum in PAIRS:
                with self.subTest(mode="dark" if dark else "light", fg=token, on=surface):
                    ratio = sc.contrast(colour(token, env, surf[surface]), surf[surface])
                    self.assertGreaterEqual(round(ratio, 2), minimum, f"{ratio:.2f}:1")

    def test_button_label_on_primary(self):
        for dark in (False, True):
            env = sc.root_custom_properties(dark=dark)
            surf = surfaces(env)
            with self.subTest(mode="dark" if dark else "light"):
                bg = colour("--stuv-primary-surface", env, surf["page"])
                fg = colour("--stuv-primary-foreground", env, bg)
                self.assertGreaterEqual(sc.contrast(fg, bg), TEXT)

    def test_primary_fill_is_only_an_icon_glyph(self):
        # Painted through a mask, --stuv-primary is an icon in the brand red.
        # Anything else filled with it carries white text or a white glyph,
        # which needs --stuv-primary-surface (see test_button_label_on_primary).
        rules = sc.css_rules(sc.component_css())
        for rule in rules:
            fill = rule.decls.get("background") or rule.decls.get("background-color") or ""
            if sc.norm_css_value(fill) == "var(--stuv-primary)":
                with self.subTest(selector=rule.selector_text):
                    self.assertTrue({"mask", "-webkit-mask"} & set(rule.decls), "use --stuv-primary-surface")

    def test_dark_cards_have_a_visible_edge(self):
        env = sc.root_custom_properties(dark=True)
        surf = surfaces(env)
        for surface in ("page", "band"):
            with self.subTest(on=surface):
                edge = colour("--stuv-card-border", env, surf[surface])
                self.assertGreaterEqual(sc.contrast(edge, surf[surface]), CARD_EDGE)


class TestCssInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = sc.component_css()
        cls.rules = sc.css_rules(cls.css)

    def test_outline_is_never_removed(self):
        # Windows High Contrast drops box-shadows, so an `outline: none` with a
        # shadow ring leaves those users with no focus indicator at all.
        for rule in self.rules:
            value = sc.norm_css_value(rule.decls.get("outline", ""))
            with self.subTest(selector=rule.selector_text):
                self.assertNotIn(value, {"none", "0", "0px"})

    def test_focus_rules_draw_an_outline(self):
        focus = [r for r in self.rules if ":focus" in r.selector_text]
        self.assertTrue(focus)
        for rule in focus:
            if "box-shadow" in rule.decls or "border-color" in rule.decls:
                with self.subTest(selector=rule.selector_text):
                    self.assertIn("outline", rule.decls)

    def test_global_focus_ring(self):
        rule = next(r for r in self.rules if "a:focus-visible" in r.selectors)
        self.assertEqual(sc.norm_css_value(rule.decls["outline"]), "2pxsolidvar(--stuv-ring)")
        self.assertIn("outline-offset", rule.decls)

    def test_every_card_link_class_has_a_card_ring(self):
        # The link is clipped by .stuv-clip, so its own outline never shows;
        # the card has to draw the ring instead.
        for cls in sc.CARD_LINK_CLASSES:
            with self.subTest(card_link=cls):
                self.assertTrue(
                    any(
                        ":has(" in s and f".{cls}:focus-visible" in s and "outline" in r.decls
                        for r in self.rules
                        for s in r.selectors
                    ),
                    f"no .stuv-card:has(.{cls}:focus-visible) rule with an outline",
                )

    def test_running_text_links_are_underlined(self):
        self.assertTrue(
            any(
                ".wp-block-post-content" in r.selector_text
                and "underline" in r.decls.get("text-decoration", "")
                for r in self.rules
            )
        )

    def test_no_truncated_text(self):
        for rule in self.rules:
            with self.subTest(selector=rule.selector_text):
                self.assertNotEqual(rule.decls.get("text-overflow"), "ellipsis")

    def test_font_sizes_come_from_the_scale(self):
        # Five sizes (--text-small … --text-display); a literal size in a rule
        # is a sixth one. Blocks may set the three static sizes inline.
        for rule in self.rules:
            size = rule.decls.get("font-size")
            if size is not None:
                with self.subTest(selector=rule.selector_text):
                    self.assertRegex(size, r"^var\(--text-(small|body|title|heading|display)\)$")
        for f in sc.deployed_files():
            for size in re.findall(r"font-size:\s*([^;\"]+)", f.read_text()):
                with self.subTest(file=str(f.relative_to(sc.REPO)), size=size):
                    self.assertIn(size.strip(), {"0.875rem", "1rem", "1.25rem"})

    def test_every_custom_property_is_defined(self):
        defined = set(sc.root_custom_properties(dark=True))
        defined |= {p for r in self.rules for p in r.decls if p.startswith("--")}
        # Inline custom properties set on a block's own element (map images).
        defined |= {"--stuv-map-light", "--stuv-map-dark", "--stuv-map-ratio", "--stuv-map-icon"}
        markup = self.css + "".join(f.read_text() for f in sc.deployed_files())
        used = set(re.findall(r"var\((--stuv-[a-z0-9-]+|--space-[a-z0-9_-]+|--text-[a-z]+)", markup))
        self.assertEqual(sorted(used - defined), [])


if __name__ == "__main__":
    unittest.main()
