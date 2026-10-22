#!/usr/bin/env python3
"""Add the block-support classes Gutenberg's save() emits but the migration omitted.

Two systematic omissions made the block editor flag content as invalid:
  * a block whose delimiter declares `style.color.text` must render its ROOT
    element with the `has-text-color` class (alongside the inline `color:`)
  * a button link (`wp-block-button__link`) must also carry `wp-element-button`

The text-color fix is *delimiter-driven*: it edits only the element that
immediately follows a `<!-- wp:… {"style":{"color":{"text":…}}} -->` delimiter,
so inline `<span style="color">` inside rich-text content is never touched.

The transform is purely additive and order-independent, matching how Gutenberg
compares the `class` attribute. `assert_only_additions` proves nothing but those
two class tokens changed before anything is written.
"""
import re

TOKENS = ('has-text-color', 'wp-element-button')

# A block delimiter: optional closing `/`, type, optional JSON, optional self-close.
DELIM_RE = re.compile(
    r'<!--\s*(?P<close>/)?wp:(?P<type>[a-z][a-z0-9-]*(?:/[a-z][a-z0-9-]*)?)'
    r'(?P<json>\s+\{.*?\})?\s*(?P<self>/)?-->',
    re.DOTALL,
)
# The opening tag immediately after a delimiter (the block root element).
ROOT_TAG_RE = re.compile(r'\s*<([a-z][a-z0-9]*)\b([^>]*?)(/?)>')
CLASS_RE = re.compile(r'\bclass\s*=\s*"([^"]*)"')


def _add_class_to_tag(tag_attrs, token):
    """Return tag attrs with `token` added to the class list (creating one if absent)."""
    m = CLASS_RE.search(tag_attrs)
    if m:
        classes = m.group(1).split()
        if token in classes:
            return tag_attrs, False
        classes.append(token)
        return CLASS_RE.sub('class="' + ' '.join(classes) + '"', tag_attrs, count=1), True
    return ' class="' + token + '"' + tag_attrs, True


def add_missing_classes(html):
    """Return (new_html, n_text_color, n_button).

    has-text-color is applied per delimiter that declares style.color.text;
    wp-element-button is applied to every button link that lacks it.
    """
    n_color = 0
    out = []
    pos = 0
    for d in DELIM_RE.finditer(html):
        if d.group('close') or d.group('self'):
            continue
        json = d.group('json') or ''
        if '"color":{"text"' not in json:
            continue
        # find the block root tag right after this delimiter
        tm = ROOT_TAG_RE.match(html, d.end())
        if not tm:
            continue
        new_attrs, changed = _add_class_to_tag(tm.group(2), 'has-text-color')
        if not changed:
            continue
        out.append(html[pos:tm.start(2)])
        out.append(new_attrs)
        pos = tm.end(2)
        n_color += 1
    out.append(html[pos:])
    html = ''.join(out)

    # button links: unambiguous, edit by class token directly
    n_button = 0

    def fix_button(m):
        nonlocal n_button
        classes = m.group(1).split()
        if 'wp-element-button' in classes:
            return m.group(0)
        n_button += 1
        classes.insert(classes.index('wp-block-button__link') + 1, 'wp-element-button')
        return 'class="' + ' '.join(classes) + '"'

    html = re.sub(r'class="([^"]*\bwp-block-button__link\b[^"]*)"', fix_button, html)
    return html, n_color, n_button


def _canon(s):
    """Strip the two added tokens from class lists and normalize whitespace, so two
    markups that differ *only* by those tokens canonicalize identically."""
    def strip_tokens(m):
        kept = [t for t in m.group(1).split() if t not in TOKENS]
        return 'class="' + ' '.join(kept) + '"' if kept else ''
    s = CLASS_RE.sub(strip_tokens, s)
    return re.sub(r'\s+', ' ', s).strip()


def assert_only_additions(old, new):
    """Raise unless old and new are identical apart from the two added class tokens."""
    # location check: every added token sits where Gutenberg would emit it
    if _canon(old) != _canon(new):
        raise AssertionError("change is not a pure class-token addition")
    return True
