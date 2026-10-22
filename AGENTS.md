# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) and other agents
when working with code in this repository. `docs/*.md` is the German, human-facing explanation of the same system:
this file instructs, `docs/` explains (`docs/ai-workflow.md` describes the
split). It is loaded into every session, so it holds only what is needed to
avoid breaking something: exact commands, hard rules, and gotchas that cost a
debugging round to find.

## Project

German-language website of StuV DHBW Heidenheim (student representative
body). This repo is the content source of the live WordPress site (Twenty
Twenty-Five block theme) at the `WP_SITE` host: Gutenberg block HTML, design
tokens, component CSS, three WordPress plugins, and the generators for the maps
and the icon CSS. Deployment is over the WordPress REST API.

**No runnable WP tooling lives here.** Everything runnable is in the
`wordpress-default-editor` skill (checkout: `~/.claude/skills/wordpress-default-editor`,
maintained in a separate skills repository): REST client `wp_block_api.py`,
`deploy.py`, `verify_deploy.py`, `rollback.py`, `upload_media.py`,
`fix_has_text_color.py`, `verify_global_css.py`, and the `blockcheck` Gutenberg
validator. **Read that SKILL.md before editing content here.**
`tools/build_skill_zip.py` snapshots the skill's committed state into
`data/media/wordpress-default-editor.zip`, which ships with the `media` target
so the docs can link a download.

**There is no build step and no auto-deploy.** Content files are deployed
unchanged. `.github/workflows/checks.yml` runs the checks below (all but the
dry-run and the post-deploy steps) on every push and deploys nothing; run them
locally before a deploy anyway. CI takes `blockcheck` from the committed
`data/media/wordpress-default-editor.zip` (the skills repo is private), so
rebuild that zip with `tools/build_skill_zip.py` after a validator change.
`README.md` indexes the human docs.

## Layout

- `data/manifest.json`: deploy targets (name → REST endpoint, id, source).
  **Source paths are relative to `data/`.** Page ids: homepage 9, ueber-uns 10,
  events 11, studentenleben 12, kontakt 13, linktree 14, kummer-karsten 16.
- `data/sections/`: homepage sections, joined in filename order. `deploy.py`
  globs `*.html` non-recursively, so ordering is the numeric filename prefix.
- `data/parked/`: sections pulled out of a page but kept; **no manifest
  target, never deployed** (this is why `sections/` skips `04`).
- `data/pages/<route>/`: subpages, same join rule.
- `data/patterns/`: synced patterns (`wp_block`, endpoint `blocks`). The
  Vorsitz grid is pattern 212, referenced as `<!-- wp:block {"ref":212} /-->`
  from the homepage and Über uns. Edit it there, deploy `pattern-vorsitz`; a
  new pattern needs `create_resource("blocks", …)` once to get its id.
- `data/header_blocks.html`, `data/footer_blocks.html`: template parts
  (`twentytwentyfive//header` / `//footer`).
- `data/global-styles.json`: theme.json-shaped design tokens (layout widths,
  palette, typography).
- `data/styles/component.css`: component classes (`.stuv-card`,
  `.stuv-icon-box`, `.stuv-button-*`, `.stuv-wpforms`) plus the `:root.dark`
  overrides; deployed into the global-styles custom-CSS field, which WordPress
  prints inline in `<style id="global-styles-inline-css">` on **every** page
  view and never HTTP-caches, so its size adds to the weight of every page.
- `data/media/`: images uploaded via the `media` target. `deploy.py` skips
  dot-prefixed files, which is why `.stuv-dhbw-logo.svg` and
  `.stuv-dhbw-favicon.svg` sit there as local-only sources.
- `data/fonts/`: the self-hosted heading font (Fraunces, latin variable woff2
  with all four axes, OFL; `SOFT`/`WONK` are set on `h1`–`h6` in
  `component.css`). **Not a deploy target**: it lives in the WordPress Font Library, which
  on this host stores files at `/wp-content/uploads/fonts/` (not
  `/wp-content/fonts/`); the `fontFace` `src` in `global-styles.json` must match.
  Never point that `src` at Google Fonts (DSGVO).
- `data/maps/`: map definitions (pins, zoom, padding) for `tools/gen_map.py`.
- `tools/`: site-specific utilities with no WP REST access: `gen_icon_css.py`,
  `gen_map.py`, `build_skill_zip.py`, plus their `test_*.py`.
- `wp-plugin/`: source of truth for the three plugins; the copies on the host
  are artifacts.

## Commands

Run from the repo root. `source .env` first for anything that talks to the host
(`.env` is git-ignored and holds `WP_SITE`, `WP_USER`, `WP_APP_PASS`,
`WP_REST_ROOT`).

```bash
npx prettier --check .        # before every commit
npx prettier --write .
```

```bash
# Block validation — the whole tree, one file per invocation (see below).
SKILL=~/.claude/skills/wordpress-default-editor
for f in $(git ls-files 'data/*.html'); do
  node $SKILL/scripts/blockcheck/validate_blocks.cjs "$f"
done | grep -E ': [1-9][0-9]* invalid'    # silent = everything valid
```

```bash
# Tools and site rules: stdlib-only unit tests, no network, no Pillow.
# Run before every commit: test_content.py and test_styles.py check data/.
python3 -m unittest discover -s tools -p "test_*.py" -v
python3 -m unittest discover -s tools -p "test_gen_map.py"   # one module
```

A single module goes through `discover` too: the tests do `import gen_map`,
which only resolves with `tools/` on `sys.path`, so `-m unittest
tools.test_gen_map` fails with an import error.

```bash
# Plugins: no dependencies, no network, no WordPress.
php wp-plugin/tests/test_normalize.php
php wp-plugin/tests/test_cache.php
php wp-plugin/tests/test_theme.php
TZ=America/Los_Angeles node --test 'wp-plugin/tests/*.test.js'
```

The `TZ` is deliberate: the Mensa menu computes in Europe/Berlin, and the test
only proves that if the machine is somewhere else.

```bash
# Generated files still match their sources (exit 0, no output).
python3 tools/gen_map.py campus --check        # also stadtgebiet, stadtzentrum
npm install --prefix /tmp/phosphor @phosphor-icons/core@2.1.1 >/dev/null
PHOSPHOR_ICON_DIR=/tmp/phosphor/node_modules/@phosphor-icons/core/assets/regular \
  python3 tools/gen_icon_css.py --check
```

```bash
source .env
SKILL=~/.claude/skills/wordpress-default-editor
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json --list
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json all --dry-run   # before every deploy
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json <target>
python3 $SKILL/scripts/verify_deploy.py --manifest data/manifest.json          # after every deploy
python3 $SKILL/scripts/rollback.py <id> [--endpoint pages|template-parts]      # undo
```

`--dry-run` validates sources locally (files present, markup balanced, byte
counts) and **never contacts the server**, so it cannot tell you a page is empty
or that an id points at the wrong page. `verify_deploy.py` fetches every target
and diffs it against its source; it is the only step that proves the site
serves what this repo says (exit 0 match / 1 drift / 2 unfetchable, `--diff`
shows what changed). Writes are gated: backup to `/tmp/wp_backup/<site-slug>/`,
`confirm=True`, balanced-markup check.

After a `global-styles` deploy, confirm REST sanitization kept the CSS:

```bash
python3 $SKILL/scripts/verify_global_css.py \
  --marker .stuv-card --marker .stuv-icon-box \
  --marker ":root.dark" --marker .stuv-wpforms \
  --marker .stuv-body-muted \
  --icon-marker=--ico-calendar
```

Exit 2 means the icon data-URIs were stripped; they would then have to live in
the header `core/html` block's `--ico-*` `:root` rules (that block currently
carries no inline CSS at all).

## Host facts

**The live host is `stuv-heidenheim.de`, and `WP_SITE` points at it.**

- `WP_REST_ROOT=wp-json`: permalinks are **Beitragsname** (`/%postname%/`).
  Front-end subpage URLs are `/<slug>/`.
- **If `/wp-json/` returns the theme's 404 while `?rest_route=/` answers 200,
  the rewrite rules are unwritten:** re-save **Einstellungen → Permalinks →
  Speichern**. `WP_REST_ROOT="?rest_route="` keeps deploys working meanwhile.
  The REST `settings` endpoint never exposes `permalink_structure`, so `null`
  there proves nothing.
- `wps-hide-login` is active, so **`wp-login.php` 404s by design**: wp-admin is
  reachable only via its custom slug.
- **`WP_SITE` already includes the `https://` scheme.** The skill's client
  normalizes it, ad-hoc `curl` does not: `curl "https://$WP_SITE/..."` fails
  with `HTTP 000`, which reads like a network outage. Strip the scheme first:
  `HOST="$(printf '%s' "$WP_SITE" | sed -E 's#^https?://##')"`.
- **The host runs WP-Optimize page caching.** A fetch can return a stale,
  minified copy of a page (`x-cache-status: HIT`) whose _inline_ global-styles
  CSS predates the deploy. Bust it with a query string when verifying a CSS
  change. `verify_deploy.py` is unaffected because it reads the REST API, not the
  front end.

## Media

**Deploying the `media` target does not update a changed image.** `deploy.py
media` calls `upload_media(reuse_existing=True)`, which returns the existing
attachment with the _same filename_ untouched. Re-running is a no-op that keeps
the old bytes (deliberate: it stops duplicate uploads). `upload_media.py
--force` doesn't help either: WordPress uniquifies the name to
`karte-…-1.webp`, a new URL that nothing references, orphaning the upload. To
replace an image at its existing URL, **delete the old attachment, then
re-upload the same filename**:

```bash
python3 - <<'PY'
import sys, os; sys.path.insert(0, os.path.expanduser("~/.claude/skills/wordpress-default-editor/scripts"))
import wp_block_api as wp
for n in ["karte-campus-light.webp", "karte-campus-dark.webp"]:
    old = wp.find_media_by_filename(n)
    if old: wp.delete_resource("media", old["id"], force=True)
    new = wp.upload_media(f"data/media/{n}", reuse_existing=False)
    assert new["source_url"].endswith("/" + n), new["source_url"]  # no -1 suffix
    print(n, "->", new["source_url"])
PY
```

**Uploads are flat on this host.** Month/year folders are switched off, so files
land at `uploads/<name>` and `MEDIA_BASE` in `gen_map.py` is the root-relative
`/wp-content/uploads`, root-relative so the same markup renders on every host
name. That stable URL is why delete-then-re-upload is safe here. If month/year
folders are ever re-enabled, `MEDIA_BASE` has to change with them.

`find_media_by_filename` takes the newest
match and warns on stderr when a name is ambiguous. If that warning appears,
stop and clean up the library before deploying.

`rollback.py` does not cover media; the map images are regenerable with
`gen_map.py --render`. The map images are CSS backgrounds coupled to
`component.css` and the `studentenleben` page HTML, so a map change is a
**three-part deploy** (images, `global-styles`, `studentenleben`) that must go
together or the maps render with the old image under the new geometry.

## The plugins (`wp-plugin/`)

Three plugins. `deploy.py` deploys none of them, because plugins do not travel
over the content REST API.

- Build: `./wp-plugin/build.sh [plugin …]` → `wp-plugin/<plugin>.zip` (no
  argument builds all three)
- Install: wp-admin → Plugins → Installieren → Plugin hochladen → Aktivieren

**`stuv-mensa`**: the live Mensa menu needs a server-side proxy: `api.dhbw.app`
sends **no CORS headers**, so the browser cannot call it directly. Deactivating
it removes the Speiseplan from the Studentenleben page. Design:
`git show 6a19d0a^:docs/superpowers/specs/2026-07-13-mensa-live-menu-design.md`.

**`stuv-theme`**: the dark-mode toggle. Prints an inline `<script>` in `<head>`
(src-less `wp_register_script` handle + `wp_add_inline_script`) that puts `.dark`
on `<html>` from `localStorage['stuv-theme']`, falling back to the OS
`prefers-color-scheme`, then delegates clicks on `.stuv-theme-option` from
`document`. It is inline and in `<head>` because the class must land before the
first paint or dark-mode visitors get a white flash. The matching CSS is the
`:root.dark` block in `component.css`; the markup is a `wp:html` block in
`data/header_blocks.html`. The script also sets `.stuv-theme-ready` on `<html>`,
and only that class makes the control visible: `component.css` hides
`.stuv-theme-switch` by default, so **deactivating the plugin freezes the site
in light mode and removes the control** rather than leaving a dead one behind
(same for visitors with JS disabled).
The control is a `<details>` dropdown (Hell / Dunkel / System), not a
`popover`: an open popover sits in the top layer, whose containing block is the
viewport, so it cannot be anchored under the trigger without CSS anchor
positioning. Escape and outside-click dismissal are therefore hand-rolled in the
plugin's `document` listeners. The `<summary>` icon keys off `.dark` (the
_resolved_ theme), so System shows sun or moon, never a monitor glyph. The
plugin also registers the `overlay` block style for `core/button` (editor picker
only: the look is `.wp-block-button.is-style-overlay` in `component.css`), points the apple-touch-icon at the opaque
`stuv-dhbw-apple-touch-icon.png` (`docs/plugins.md`), and on render replaces
the year after `©` in the footer paragraph classed `stuv-copyright`; the stored
year is only the plugin-off fallback.

**`stuv-dsgvo`**: click-to-load for the two Google Calendar embeds (homepage
`sections/02-was-wir-bieten.html`, `pages/events/02-upcoming.html`). **The
privacy guarantee lives in the markup, not in the plugin:** those `<iframe>`s
carry `data-stuv-src` and **no `src`**, so nothing reaches Google until a
visitor clicks, even with the plugin off or JS disabled. Don't "fix" that back to a real
`src`. Consequences that hang together and must change together:

- `component.css` hides `iframe[data-stuv-src]` and reveals it again on
  `.stuv-dsgvo-loaded`. Hiding on the _attribute_ keeps a
  plugin-off/JS-off visitor from getting an empty 600px box.
- Each embed ships a visible `.stuv-dsgvo-fallback` link inside a
  `.stuv-dsgvo-embed` wrapper; the plugin hides it by setting
  `.stuv-dsgvo-ready` on that wrapper once its script has run.
- The script is enqueued only when the rendered post's content contains
  `data-stuv-src` (`stuv_dsgvo_has_embed()`). An embed moved into a template
  part, widget or reusable block would never load; drop the check if that
  happens.
- Consent **is** persisted per device in `localStorage['stuv-dsgvo-calendar']`.
  That is defensible only because a loaded embed
  **always** renders a `.stuv-dsgvo-revoke` line under it. Don't remove it and
  don't hide it behind a hover or a toggle: the DSGVO wants withdrawal as easy
  as consent, and this is the only route out. Revoking swaps the iframe for an
  src-less clone rather than clearing `src`, which would leave Google's document
  running in the frame. All `localStorage` access is in try/catch: a browser
  that blocks storage falls back to asking every time, never to an exception
  that kills the click handler.

So a change here is a **four-part deploy**: plugin zip upload, `global-styles`,
`homepage`, `events`.

## Formatting

Prettier owns the formatting of block HTML, `component.css`, the JSON design
tokens, docs and JS. Config: `.prettierrc.json` (`printWidth: 80`,
`proseWrap: "preserve"` so Markdown paragraphs aren't rewrapped).

- **No npm dependencies.** Prettier runs through `npx`; the repo deliberately
  has no `package.json`. That is also why **PHP is left unformatted**: it would
  need `@prettier/plugin-php` as a real installed dependency. Match the
  surrounding style by hand in `wp-plugin/`.
- `.prettierignore` covers the captured `api.dhbw.app` fixtures (must stay
  byte-exact to be a valid recording) and the built plugin zips.
- **Reformatting block HTML rewrites deployed bytes.** Prettier reflows tags and
  inline `style` attributes. The rendered output is equivalent, but a format
  pass changes the bytes of _every_ target, not just the page you edited, and the
  next real deploy rewrites them all. Expect that; don't read it as a content
  change.
- **Always re-validate after formatting**, across the whole `data/` tree, not just the
  file you touched.
- Prettier moves the zero-width space in `.stuv-icon-box` paragraphs onto its
  own line. Harmless: Gutenberg's equivalence check normalizes that whitespace,
  and the box renders via CSS mask rather than text.

## Content gotchas

- **`--` inside block-comment JSON must be escaped as `\u002d\u002d`.** A literal
  `--` is illegal inside an HTML comment, so Gutenberg writes
  `"color":{"text":"var(\u002d\u002dstuv-muted-foreground)"}`; the `<p>`'s own
  `style` attribute keeps the real `var(--stuv-…)`. Copying a block's JSON by
  hand and leaving the dashes raw produces an invalid block. Note that some
  editing tools decode the escape back to `--` on write; verify with `od` after
  writing one by hand.
- **Block validation**: hand-written HTML must match Gutenberg's canonical
  `save()` output or the editor flags "Dieser Block enthält unerwarteten oder
  ungültigen Inhalt". A block with `style.color.text` needs `has-text-color` on
  its root; button links need `wp-element-button` (backfill: the skill's
  `fix_has_text_color.py`). `validate_blocks.cjs` reads **only its first
  argument**: passing it a glob silently checks one file and prints a clean
  pass, so sweep the tree with the loop under Commands. The pattern
  `'data/*.html'` is deliberate: git's `*` spans slashes, so it matches every
  block-HTML file in the tree, while `'data/**/*.html'` would miss
  `header_blocks.html` / `footer_blocks.html` (no subdirectory). The validator
  passes a block whose JSON `style` disagrees with its inline `style` (a
  `"fontWeight":"500"` over `font-weight: 400`); the editor then re-saves the
  JSON value and the look changes. `tools/test_content.py` catches that drift.
- **Omit an empty `"style":{}`.** WordPress stores it back as `"style":[]` (PHP
  round-trip), so that target reports drift against its source forever.
- **Verify a deploy by comparing raw block markup, not by eyeballing the page.**
  Fetch `content.raw` per manifest target and compare it to the joined source;
  every target should be byte-identical. `verify_deploy.py` does exactly this.
- **Use the `.stuv-card` border, not a block border colour.** A custom border
  colour adds `has-border-color`, which the palette slug `border` turns into
  `color:var(--wp--preset--color--border) !important`: the block's text goes
  light grey.
- **Page template**: all pages use the theme's `page-no-title` template. New
  pages created via REST **must** set `"template": "page-no-title"`, or
  WordPress renders a big post-title heading.
- **Layout**: global widths/colors/typography belong in
  `data/global-styles.json`; component classes in `data/styles/component.css`.
  Full-bleed section bands need `align:full` per section.
- **A group's `contentSize` sizes its children, not the group**, and that
  silently un-aligns the section lead. Core's constrained layout gives the
  _children_ of a group with its own `contentSize` a `max-width` and
  `margin-inline:auto`, but the group's own box still fills the parent column
  (currently `contentSize: 56rem` / `wideSize: 72rem` in the tokens).
  `p.stuv-section-intro` carries `margin-inline:0 !important`, and that "0" is
  measured against the full-width group box, so the heading lands at the inner
  column while its lead escapes further left. Symptom: a section header where
  eyebrow and heading sit inset but the lead does not. Fix by dropping the inner
  `contentSize` so everything inherits one column, or by capping the group
  itself with a class. **Eyeballing the block HTML will not show this**;
  measure `getBoundingClientRect().left` for eyebrow/heading/lead/body on the
  rendered page.
- **A sideways scroll on every page at mobile width comes from the header**
  (`.stuv-header-row` is `flexWrap:nowrap`). In the `max-width:639px` block,
  `min-width:0` on the logo group plus `max-width:100%` on `.stuv-logo-mark` is
  what lets the logo shrink; keep both. Find the overflowing element by
  filtering `getBoundingClientRect().right >
document.documentElement.clientWidth`.
- **Fluid typography is off; a size ships exactly as written.**
  `data/global-styles.json` sets `settings.typography.fluid: false` and declares
  its own static `fontSizes` presets (`small` 0.875, `medium` 1, `large` 1.125,
  `x-large` 1.875, `xx-large` 3rem). TT5's fluid typography rewrites _every_
  block-level `"fontSize"` into a `clamp()` floored at `minFontSize`, collapsing
  the inline sizes in use (`0.75rem` to `2rem`) to the **same 16px** at a 320px
  viewport. Do not re-enable it: the
  responsive steps live in `component.css` media queries (`.stuv-hero-title`,
  `.stuv-h2`), where a breakpoint-based scale belongs and which fluid typography
  never touched anyway. The presets **must** be declared explicitly:
  with `fluid:false` an undeclared preset falls back to TT5's own `size` field.
  Verify a size change on the served HTML, not with
  `--dry-run` or the block validator, since neither reads rendered CSS.

## Site rules the tests enforce

`tools/test_content.py` and `tools/test_styles.py` encode the site's
accessibility and consistency rules; a failure names the rule, and each test's
comment says why it exists. Change a rule there, in one place. The ones that
need an edit beyond the content itself:

- **Contact links** (`tel:`, `mailto:`, Instagram, WhatsApp, Google Forms) must
  appear in `CONTACTS` in `test_content.py`. Add a new address there
  deliberately; the canonical Instagram handle is `@stuvheidenheim`.
- **Whole-card links** use `.stuv-card-cover`, `.stuv-quicklink` or
  `.stuv-linktree-card`, listed in `CARD_LINK_CLASSES` in `tools/sitecheck.py`.
  The card draws the hover border and focus ring through `.stuv-card:has(…)`;
  a new card-link class goes into both places.
- **Buttons** are `wp:button` blocks whose block style is the variant: none
  (primary), `is-style-outline`, `is-style-overlay`; `stuv-button-lg` for size,
  a `<span class="stuv-ico …">` in the link for an icon. The
  `stuv-button-primary|outline|overlay` classes match only a bare
  `<a>`/`<button>` (plugin markup) and are rejected in `data/`;
  `stuv-button-link` is a text link, not a button.
- **Section labels** are a paragraph with `.stuv-kicker` and no inline style.
- **Kummer Karsten** keeps the `.stuv-crisis` notice (112 and both
  Telefonseelsorge numbers) before the form.
- **Colours**: a token change must keep the contrast pairs in `test_styles.py`
  green in light and dark mode. Focus is `outline: 2px solid var(--stuv-ring)`;
  `box-shadow` rings vanish in Windows High Contrast.

Rendering is out of the tests' reach: check 360px width (no sideways scroll,
stacked buttons) and a keyboard Tab pass by eye, per `docs/testing.md`.

## Generated files: never hand-edit

- **The maps are generated.** `data/pages/studentenleben/02-campus-karte.html`
  and the map block in `09-freizeit.html` are emitted by `tools/gen_map.py` from
  `data/maps/*.json`. Edit the JSON and re-run
  `python3 tools/gen_map.py <id> --render --write`, never the block HTML; a
  hand edit is silently overwritten on the next `--write`. Only the region
  between the `gen_map:` markers is owned by the generator; the rest of those
  files is hand-editable. `--check` (needs Pillow and `npx prettier`) proves the
  committed images and blocks still match the data; a Pillow/libwebp upgrade can
  change WebP bytes for identical input, in which case re-render and commit. The
  basemaps are self-hosted and the light/dark swap is two inline custom
  properties picked up by `:root.dark .stuv-map-canvas`; a `<picture>` with a
  `prefers-color-scheme` `<source>` would follow the OS and ignore the site's
  own theme toggle. Leaflet was rejected on purpose (it would send visitor IPs
  to a tile host).
- **The icon CSS is generated.** The `:root { --ico-*: url("data:…") }` block in
  `component.css` sits between the `gen_icon_css:` markers and comes from
  `tools/gen_icon_css.py` (Phosphor regular, pinned to
  `@phosphor-icons/core@2.1.1`; the `--ico-*` token names are still the old
  lucide names, mapped in `ICONS`). It is the largest
  single thing in the inline global CSS, so its encoding is deliberately tight.
  Read the module docstring before touching the escaping.

## Docs

`docs/*.md` is human-readable documentation, written in German, and is read
**on GitHub** (the repo is public), so a docs edit is done once it is pushed.
Links must work on GitHub: other docs
relative (`testing.md`), site files absolute (`https://stuv-heidenheim.de/…`), because
a root-relative `/wp-content/…` resolves against github.com. Nothing in `docs/`
may contain secrets. Do not re-add a `docs` deploy target to
`data/manifest.json`.
