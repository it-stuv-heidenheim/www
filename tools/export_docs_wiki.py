#!/usr/bin/env python3
"""Render docs/*.md into paste-ready Markdown for the AStA wiki.

The docs used to be published to `/docs/` on the WordPress site by
`tools/gen_docs_page.py`. They now live on https://wiki.dhbw-asta.de/, which
runs **BookStack** — a wiki with a native Markdown editor per page. So this
script emits Markdown, not HTML: open the file, copy it, and paste it into a
BookStack page whose editor is switched to Markdown.

    python3 tools/export_docs_wiki.py
    open build/wiki/

Stdlib only — no `markdown` package. Nothing here renders Markdown; BookStack
does that. The script only rewrites the few things that would break once the
text leaves this repo, and it deliberately does not touch anything inside a
fenced code block: a code sample showing `src="/wp-content/…"` is documentation
*about* the WordPress markup and must stay verbatim.

BookStack's editor is CommonMark + GFM tables, so tables, indented fences
inside list items and inline HTML all pass through as written.

Output goes to build/ (git-ignored) — these are artifacts, the Markdown in
docs/ stays the source of truth.
"""

import argparse
import re
import sys
from pathlib import Path

DOCS_DIR = Path("docs")
OUTPUT_DIR = Path("build/wiki")

# Reading order, not alphabetical — this is also the order of index.md and the
# order the wiki pages should be created in. Overview first, then the two
# everyday tasks, then reference, then the rare one. docs/not-public/ is
# deliberately absent: it is internal and must not reach a public wiki.
DOC_FILES = [
    "architecture.md",
    "content-editing.md",
    "adding-a-page.md",
    "design-system.md",
    "tools.md",
    "plugins.md",
    "testing.md",
    "ai-workflow.md",
]

# Root-relative links (the skill ZIP) point at the WordPress host, not at the
# wiki. Pasted unchanged they would silently mean wiki.dhbw-asta.de/wp-content/…
DEFAULT_SITE = "https://dev.stuv-heidenheim.de"

FENCE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>`{3,}|~{3,})(?P<info>.*)$")


def fenced_mask(lines):
    """True for every line inside a fenced code block, delimiters included.

    Fences are matched at any indentation because the docs put them inside
    numbered list items. A closing fence is the same character repeated at
    least as often as the opening one, which is what lets a ````` block quote a
    ``` block.
    """
    mask = [False] * len(lines)
    marker = None
    for i, line in enumerate(lines):
        if marker is None:
            m = FENCE_RE.match(line)
            if m:
                marker = m.group("marker")
                mask[i] = True
            continue

        mask[i] = True
        stripped = line.strip()
        if (
            stripped
            and set(stripped) == {marker[0]}
            and len(stripped) >= len(marker)
        ):
            marker = None
    return mask


def unwrap_wphtml(md_text):
    """Turn a ```wphtml fence back into real markup.

    A `wphtml` fence carries a verified raw block (today: the skill-ZIP download
    button) that the docs mean as an element, not as a code sample. Left as a
    fence it would paste visible HTML source into the wiki. Only the exact
    `wphtml` info string triggers this — a plain ```html sample stays code.

    BookStack renders inline HTML in a Markdown page, but it has none of the
    site's `.stuv-*` CSS, so the button arrives as an ordinary link. That is
    the intent: the link has to work, the styling is the website's.
    """
    lines = md_text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m or m.group("info").strip() != "wphtml":
            out.append(lines[i])
            i += 1
            continue

        marker = m.group("marker")
        i += 1
        # The body keeps its indentation: the fence sits inside a numbered list
        # item, and dedenting the markup would break it out of that item.
        while i < len(lines):
            stripped = lines[i].strip()
            if (
                stripped
                and set(stripped) == {marker[0]}
                and len(stripped) >= len(marker)
            ):
                i += 1
                break
            out.append(lines[i])
            i += 1

    return "\n".join(out)


CODE_SPAN_RE = re.compile(r"(?P<ticks>`+)(?P<body>.+?)(?P=ticks)")


def sub_outside_code(line, pattern, repl):
    """Apply `pattern` to the parts of `line` that are not an inline code span.

    A backticked `/wp-content/…` is a *path being named*, not a link — docs
    quote both the WordPress markup and the paths inside it, and rewriting
    those would make the documentation describe something the repo does not
    contain. Code spans are matched per line: a span wrapped across a line
    break is legal CommonMark but appears nowhere in docs/.
    """
    out = []
    pos = 0
    for m in CODE_SPAN_RE.finditer(line):
        out.append(pattern.sub(repl, line[pos : m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(pattern.sub(repl, line[pos:]))
    return "".join(out)


MD_LINK_RE = re.compile(r"\]\((?P<url>/[^)\s]*)\)")
HTML_ATTR_RE = re.compile(r'(?P<attr>href|src)="(?P<url>/[^"]*)"')


def absolutize_links(md_text, site):
    """Rewrite root-relative links to absolute ones on the WordPress host.

    A relative link resolves against the wiki's own origin once pasted, which
    is never what these mean — they point at files served by the WP site.
    Fragment-only links (#anchor) stay relative: they are in-page. Code — both
    fenced blocks and inline spans — is skipped, so the `src="/wp-content/…"`
    in the image-block sample keeps saying what the block file contains.
    """
    lines = md_text.split("\n")
    mask = fenced_mask(lines)
    base = site.rstrip("/")
    rewritten = []

    def repl_md(m):
        rewritten.append(m.group("url"))
        return f']({base}{m.group("url")})'

    def repl_attr(m):
        rewritten.append(m.group("url"))
        return f'{m.group("attr")}="{base}{m.group("url")}"'

    for i, line in enumerate(lines):
        if mask[i]:
            continue
        line = sub_outside_code(line, MD_LINK_RE, repl_md)
        lines[i] = sub_outside_code(line, HTML_ATTR_RE, repl_attr)

    return "\n".join(lines), rewritten


MD_TARGET_RE = re.compile(r"\]\((?P<url>[^)\s]*\.md(?:#[^)\s]*)?)\)")


def find_unresolved_md_links(md_text):
    """Links to a sibling .md file — they would 404 on the wiki.

    None exist today (the docs cross-reference by name in prose, not by link).
    If one is ever added it has to become a real wiki URL by hand, so this
    reports rather than guesses a page path. Code is skipped for the same
    reason as in absolutize_links: a sample or a named path may legitimately
    show a repo-relative `.md`.
    """
    lines = md_text.split("\n")
    mask = fenced_mask(lines)
    return [
        m.group("url")
        for i, line in enumerate(lines)
        if not mask[i]
        for m in MD_TARGET_RE.finditer(CODE_SPAN_RE.sub("", line))
    ]


H1_RE = re.compile(r"^#\s+(?P<title>.+?)\s*$")


def split_title(md_text, fallback):
    """Pop the leading `# H1` and return it as the wiki page name.

    BookStack shows the page name as the page's heading, so a kept H1 would
    render twice. Everything below stays as written — H2/H3 are what BookStack
    builds its page navigation from.
    """
    lines = md_text.split("\n")
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = H1_RE.match(line)
        if not m:
            return fallback, md_text
        rest = lines[i + 1 :]
        while rest and not rest[0].strip():
            rest.pop(0)
        return m.group("title"), "\n".join(rest)
    return fallback, md_text


def convert(md_text, site, fallback_title):
    text = unwrap_wphtml(md_text)
    text, rewritten = absolutize_links(text, site)
    problems = find_unresolved_md_links(text)
    title, body = split_title(text, fallback_title)
    if not body.endswith("\n"):
        body += "\n"
    return title, body, rewritten, problems


def build_index(entries, site):
    rows = "\n".join(
        f"| `{name}` | {title} | `{source}` |" for name, title, source in entries
    )
    return f"""# StuV-Doku — Vorlagen für das AStA-Wiki

Eine Datei pro Wiki-Seite. Das Wiki (<https://wiki.dhbw-asta.de/>) ist eine
BookStack-Instanz: Seite anlegen, im Editor auf **Markdown** umschalten, die
Datei komplett hineinkopieren, als Seitenname die Spalte „Seitenname“ nehmen.
Die H1 steht absichtlich nicht mehr im Text — BookStack zeigt den Seitennamen
schon als Überschrift.

| Datei | Seitenname | Quelle |
| --- | --- | --- |
{rows}

Quelle bleibt das Markdown in `docs/` im Website-Repo. Nach einer Änderung dort
`python3 tools/export_docs_wiki.py` erneut laufen lassen und die betroffene
Seite neu einfügen.

Root-relative Links zeigen auf `{site}`.
Diese Datei selbst ist nur eine Checkliste und gehört nicht ins Wiki.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site",
        default=DEFAULT_SITE,
        help=f"host that root-relative links resolve against (default: {DEFAULT_SITE})",
    )
    parser.add_argument(
        "--out",
        default=str(OUTPUT_DIR),
        help=f"output directory (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    problems = []
    for name in DOC_FILES:
        source = DOCS_DIR / name
        if not source.exists():
            problems.append(f"{source}: missing (listed in DOC_FILES)")
            continue

        title, body, rewritten, unresolved = convert(
            source.read_text(encoding="utf-8"), args.site, name
        )
        for url in unresolved:
            problems.append(f"{source}: link to {url!r} has no wiki equivalent")

        (out_dir / name).write_text(body, encoding="utf-8")
        entries.append((name, title, str(source)))
        suffix = f"  [{len(rewritten)} abs. Links]" if rewritten else ""
        print(f"  {name:<24} {title}{suffix}")

    (out_dir / "index.md").write_text(build_index(entries, args.site), encoding="utf-8")
    print(f"\n{len(entries)} Seiten + index.md in {out_dir}/")
    print(f"Öffnen: open {out_dir}/")

    if problems:
        sys.exit("\n".join(["error:"] + problems))


if __name__ == "__main__":
    main()
