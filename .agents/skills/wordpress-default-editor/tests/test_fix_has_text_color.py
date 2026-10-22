
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from scripts.fix_has_text_color import add_missing_classes, assert_only_additions

HEADING = (
    '<!-- wp:heading {"style":{"color":{"text":"#e2001a"}}} -->\n'
    '<h2 class="wp-block-heading" style="color:#e2001a">Titel</h2>\n'
    '<!-- /wp:heading -->'
)

BUTTON = (
    '<!-- wp:button -->\n'
    '<div class="wp-block-button">'
    '<a class="wp-block-button__link" href="/?pagename=kontakt">Kontakt</a></div>\n'
    '<!-- /wp:button -->'
)


def test_adds_has_text_color_and_button_class():
    html = HEADING + "\n\n" + BUTTON
    new, n_color, n_button = add_missing_classes(html)
    assert n_color == 1 and n_button == 1
    assert 'class="wp-block-heading has-text-color"' in new
    assert 'wp-block-button__link wp-element-button' in new
    assert_only_additions(html, new)


def test_idempotent_and_leaves_inline_spans_alone():
    html = (
        '<!-- wp:paragraph -->\n'
        '<p>ein <span style="color:#e2001a">rotes</span> Wort</p>\n'
        '<!-- /wp:paragraph -->'
    )
    new, n_color, n_button = add_missing_classes(html)
    assert (new, n_color, n_button) == (html, 0, 0)
    again, _, _ = add_missing_classes(add_missing_classes(HEADING)[0])
    assert again == add_missing_classes(HEADING)[0]


def test_assert_only_additions_rejects_real_changes():
    with pytest.raises(AssertionError):
        assert_only_additions(HEADING, HEADING.replace("Titel", "Anders"))
