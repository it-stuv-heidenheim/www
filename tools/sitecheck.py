"""Read-only model of the site sources for test_content.py and test_styles.py: pages built as
deploy.py builds them, plus parsers for block comments, HTML, CSS rules and colours."""

import json
import pathlib
import re
from html.parser import HTMLParser
from typing import NamedTuple

REPO = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO / "data"
CSS_PATH = DATA / "styles" / "component.css"
TOKENS_PATH = DATA / "global-styles.json"

# Links that are a card's whole clickable surface; each needs a hover and focus rule in component.css.
CARD_LINK_CLASSES = ("stuv-card-cover", "stuv-quicklink", "stuv-linktree-card")

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "source", "track", "wbr",
}


# --- sources ---------------------------------------------------------------


def manifest():
    return json.loads((DATA / "manifest.json").read_text())


def source_files(source):
    path = DATA / source
    return sorted(path.glob("*.html")) if path.is_dir() else [path]


def read_source(source):
    return "\n\n".join(f.read_text() for f in source_files(source))


def page_url(target):
    return "/" if target == "homepage" else f"/{target}/"


def deployed_files():
    """Every block-HTML file some manifest target deploys (data/parked/ is not)."""
    files = []
    for t in manifest().values():
        if t.get("type") == "structural":
            files.extend(source_files(t["source"]))
    return files


def pages():
    """{url: markup} for every page target, synced patterns inlined."""
    m = manifest()
    patterns = {
        str(t["id"]): read_source(t["source"])
        for t in m.values()
        if t.get("endpoint") == "blocks"
    }

    def inline(mo):
        ref = mo.group(1)
        if ref not in patterns:
            raise KeyError(f"wp:block ref {ref} has no 'blocks' target in the manifest")
        return patterns[ref]

    return {
        page_url(name): re.sub(r'<!-- wp:block \{"ref":(\d+)\} /-->', inline, read_source(t["source"]))
        for name, t in m.items()
        if t.get("endpoint") == "pages"
    }


def template_parts():
    return {
        name: read_source(t["source"])
        for name, t in manifest().items()
        if t.get("endpoint") == "template-parts"
    }


# --- block comments --------------------------------------------------------

BLOCK_RE = re.compile(
    r"<!--\s+(?P<close>/?)wp:(?P<name>[a-z0-9-]+(?:/[a-z0-9-]+)?)\s+"
    r"(?P<json>\{.*?\}\s+)?(?P<self>/?)-->",
    re.S,
)
ROOT_TAG_RE = re.compile(r"\s*<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>")


class Block(NamedTuple):
    name: str
    attrs: dict
    raw_json: str
    root_tag: str
    root_attrs: str
    line: int


def blocks(markup):
    """Every opening block comment, with its parsed attributes and root element."""
    out = []
    for mo in BLOCK_RE.finditer(markup):
        if mo.group("close"):
            continue
        raw = (mo.group("json") or "").strip()
        attrs = json.loads(raw) if raw else {}
        root_tag, root_attrs = None, ""
        if not mo.group("self"):
            tag = ROOT_TAG_RE.match(markup, mo.end())
            if tag:
                root_tag, root_attrs = tag.group(1).lower(), tag.group(2)
        line = markup.count("\n", 0, mo.start()) + 1
        out.append(Block(mo.group("name"), attrs, raw, root_tag, root_attrs, line))
    return out


def attr_value(attr_text, name):
    mo = re.search(rf'\b{name}\s*=\s*"([^"]*)"', attr_text)
    return mo.group(1) if mo else None


def parse_inline_style(style):
    """'color: red; margin-top: 1rem' -> {'color': 'red', 'margin-top': '1rem'}."""
    out = {}
    for decl in split_top_level(style or "", ";"):
        if ":" in decl:
            prop, value = decl.split(":", 1)
            out[prop.strip().lower()] = value.strip()
    return out


def norm_css_value(value):
    return re.sub(r"\s+", "", str(value)).lower()


def preset_to_css(value):
    """'var:preset|spacing|4' -> 'var(--wp--preset--spacing--4)', as core serializes it."""
    value = str(value)
    if value.startswith("var:"):
        return "var(--wp--" + value[4:].replace("|", "--") + ")"
    return value


_TYPOGRAPHY_PROPS = {
    "fontSize": "font-size",
    "fontWeight": "font-weight",
    "fontStyle": "font-style",
    "lineHeight": "line-height",
    "letterSpacing": "letter-spacing",
    "textTransform": "text-transform",
    "textDecoration": "text-decoration",
}


def expected_inline_style(style_attr):
    """The inline declarations core's save() writes on the root element for a `style` attribute."""
    out = {}
    typo = style_attr.get("typography") or {}
    for key, prop in _TYPOGRAPHY_PROPS.items():
        if key in typo:
            out[prop] = typo[key]
    spacing = style_attr.get("spacing") or {}
    for box in ("margin", "padding"):
        value = spacing.get(box)
        if isinstance(value, dict):
            for side in ("top", "right", "bottom", "left"):
                if side in value:
                    out[f"{box}-{side}"] = value[side]
        elif isinstance(value, str):
            out[box] = value
    color = style_attr.get("color") or {}
    if "text" in color:
        out["color"] = color["text"]
    if "background" in color:
        out["background-color"] = color["background"]
    return {prop: preset_to_css(v) for prop, v in out.items()}


# --- HTML tree -------------------------------------------------------------


class Element:
    def __init__(self, tag, attrs, line, parent):
        self.tag = tag
        self.attrs = attrs
        self.classes = set((attrs.get("class") or "").split())
        self.line = line
        self.parent = parent
        self.text_parts = []

    def ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def closest(self, cls):
        return next((a for a in self.ancestors() if cls in a.classes), None)

    @property
    def text(self):
        return " ".join("".join(self.text_parts).replace("\u200b", " ").split())


def expand_navigation(markup):
    """Stand in an <a> for each navigation-link block (rendered server-side, saved as a comment)."""

    def link(mo):
        attrs = json.loads(mo.group(1))
        return f'<a href="{attrs.get("url", "")}">{attrs.get("label", "")}</a>'

    return re.sub(r"<!-- wp:navigation-link (\{.*?\}) /-->", link, markup)


class Doc(HTMLParser):
    """Walks markup once, keeping every element, every link and every tag-balance error."""

    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        markup = expand_navigation(markup)
        self.elements = []
        self.errors = []
        self._stack = []
        self.feed(markup)
        self.close()
        for el in self._stack:
            self.errors.append(f"line {el.line}: <{el.tag}> is never closed")

    def _open(self, tag, attrs, void):
        parent = self._stack[-1] if self._stack else None
        el = Element(tag, dict(attrs), self.getpos()[0], parent)
        self.elements.append(el)
        if not void:
            self._stack.append(el)

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, tag in VOID_TAGS)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, True)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        line = self.getpos()[0]
        if not any(el.tag == tag for el in self._stack):
            self.errors.append(f"line {line}: stray </{tag}>")
            return
        while self._stack:
            el = self._stack.pop()
            if el.tag == tag:
                return
            self.errors.append(f"line {el.line}: <{el.tag}> closed implicitly by </{tag}> on line {line}")

    def handle_data(self, data):
        for el in self._stack:
            el.text_parts.append(data)

    @property
    def ids(self):
        return {el.attrs["id"] for el in self.elements if el.attrs.get("id")}

    @property
    def links(self):
        return [el for el in self.elements if el.tag == "a" and el.attrs.get("href") is not None]


# --- CSS -------------------------------------------------------------------


def split_top_level(text, sep):
    """Split on `sep`, ignoring separators inside quotes or parentheses."""
    parts, depth, quote, start = [], 0, None, 0
    for i, ch in enumerate(text):
        if quote:
            if ch == quote and text[i - 1] != "\\":
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def _matching_brace(text, open_at):
    depth, quote = 0, None
    for i in range(open_at, len(text)):
        ch = text[i]
        if quote:
            if ch == quote and text[i - 1] != "\\":
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unbalanced '{{' at offset {open_at}")


class Rule(NamedTuple):
    selectors: list
    decls: dict
    media: str

    @property
    def selector_text(self):
        return ", ".join(self.selectors)


def css_rules(text, media=None):
    """Every style rule as Rule(selectors, {prop: value}, media), @media unwrapped."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    rules, i = [], 0
    while True:
        open_at = text.find("{", i)
        if open_at == -1:
            return rules
        close_at = _matching_brace(text, open_at)
        prelude = " ".join(text[i:open_at].split())
        body = text[open_at + 1 : close_at]
        if prelude.startswith("@"):
            rules.extend(css_rules(body, media=prelude))
        else:
            rules.append(Rule(split_top_level(prelude, ","), parse_inline_style(body), media))
        i = close_at + 1


def component_css():
    return CSS_PATH.read_text()


def root_custom_properties(dark=False):
    """Custom properties as the browser sees them on <html>: palette presets,
    then :root, then (for dark) :root.dark on top."""
    tokens = json.loads(TOKENS_PATH.read_text())
    env = {
        f"--wp--preset--color--{p['slug']}": p["color"]
        for p in tokens["settings"]["color"]["palette"]
    }
    wanted = (":root", ":root.dark") if dark else (":root",)
    for sel in wanted:
        for rule in css_rules(component_css()):
            if rule.media is None and rule.selectors == [sel]:
                env.update({k: v for k, v in rule.decls.items() if k.startswith("--")})
    return env


# --- colours ---------------------------------------------------------------


def _find_call(text, name):
    """(start, end, inner) of the first `name(...)` in text, or None."""
    start = text.find(name + "(")
    if start == -1:
        return None
    depth = 0
    for i in range(start + len(name), len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return start, i + 1, text[start + len(name) + 1 : i]
    raise ValueError(f"unbalanced {name}( in {text!r}")


def resolve_vars(value, env, _depth=0):
    """Substitute var(--x, fallback) recursively; KeyError if neither is available."""
    if _depth > 20:
        raise ValueError(f"var() cycle in {value!r}")
    while True:
        call = _find_call(value, "var")
        if call is None:
            return value.strip()
        start, end, inner = call
        args = split_top_level(inner, ",")
        name, fallback = args[0], (args[1] if len(args) > 1 else None)
        if name in env:
            sub = resolve_vars(env[name], env, _depth + 1)
        elif fallback is not None:
            sub = resolve_vars(fallback, env, _depth + 1)
        else:
            raise KeyError(f"{name} is not defined")
        value = value[:start] + sub + value[end:]


_NAMED = {"white": (1, 1, 1, 1), "black": (0, 0, 0, 1), "transparent": (0, 0, 0, 0)}


def parse_color(text):
    """CSS colour -> (r, g, b, a), channels 0..1. Covers what component.css uses."""
    text = text.strip().lower()
    if text in _NAMED:
        return _NAMED[text]
    if text.startswith("#"):
        h = text[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        channels = [int(h[i : i + 2], 16) / 255 for i in range(0, len(h), 2)]
        return tuple(channels) + ((1.0,) if len(channels) == 3 else ())
    mo = re.fullmatch(r"rgba?\((.*)\)", text)
    if mo:
        parts = [p for p in re.split(r"[\s,/]+", mo.group(1)) if p]
        rgb = [float(p) / 255 for p in parts[:3]]
        alpha = parts[3] if len(parts) > 3 else "1"
        a = float(alpha[:-1]) / 100 if alpha.endswith("%") else float(alpha)
        return (*rgb, a)
    if text.startswith("color-mix("):
        return _color_mix(_find_call(text, "color-mix")[2])
    raise ValueError(f"unsupported colour {text!r}")


def _color_mix(inner):
    space, first, second = split_top_level(inner, ",")
    if space.split() != ["in", "srgb"]:
        raise ValueError(f"only color-mix(in srgb, …) is supported, got {space!r}")

    def colour_and_pct(arg):
        mo = re.fullmatch(r"(.*?)\s+([\d.]+)%", arg.strip())
        return (parse_color(mo.group(1)), float(mo.group(2)) / 100) if mo else (parse_color(arg), None)

    (c1, p1), (c2, p2) = colour_and_pct(first), colour_and_pct(second)
    if p1 is None and p2 is None:
        p1 = p2 = 0.5
    elif p1 is None:
        p1 = 1 - p2
    elif p2 is None:
        p2 = 1 - p1
    total = p1 + p2
    p1, p2 = p1 / total, p2 / total
    # Interpolation happens on premultiplied alpha, so mixing with
    # `transparent` keeps the hue and only lowers the alpha.
    alpha = c1[3] * p1 + c2[3] * p2
    if alpha == 0:
        return (0, 0, 0, 0)
    rgb = [(c1[i] * c1[3] * p1 + c2[i] * c2[3] * p2) / alpha for i in range(3)]
    return (*rgb, alpha)


def over(fg, bg):
    """Composite a possibly translucent colour over an opaque one."""
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def luminance(c):
    def lin(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
