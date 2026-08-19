# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) and other agents
when working with code in this repository. `CLAUDE.md` is a one-line include of
it. `docs/*.md` is the German, human-facing explanation of the same system —
**this file instructs, `docs/` explains** (`docs/ai-workflow.md` describes the
split). It is loaded into every session, so it holds only what is needed to
avoid breaking something: exact commands, hard rules, and gotchas that cost a
debugging round to find.

## Project

German-language website of **StuV DHBW Heidenheim** (student representative
body). This repo is the **content source** of the live WordPress site (Twenty
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

**There is no CI and no build step.** Content files are deployed unchanged, and
every check below is run by hand, locally, before a deploy. Human docs:
`docs/architecture.md` (overview), `docs/content-editing.md`,
`docs/adding-a-page.md`, `docs/design-system.md`, `docs/tools.md`,
`docs/plugins.md`, `docs/testing.md`.

## Layout

- `data/manifest.json` — deploy targets (name → REST endpoint, id, source).
  **Source paths are relative to `data/`.** Page ids: homepage 9, ueber-uns 10,
  events 11, studentenleben 12, kontakt 13, linktree 14, kummer-karsten 16.
- `data/sections/` — homepage sections, joined in filename order. `deploy.py`
  globs `*.html` non-recursively, so ordering is the numeric filename prefix.
- `data/parked/` — sections pulled out of a page but kept; **no manifest
  target, never deployed** (this is why `sections/` skips `04`).
- `data/pages/<route>/` — subpages, same join rule.
- `data/header_blocks.html`, `data/footer_blocks.html` — template parts
  (`twentytwentyfive//header` / `//footer`).
- `data/global-styles.json` — theme.json-shaped design tokens (layout widths,
  palette, typography).
- `data/styles/component.css` — ~110 KB of component classes (`.stuv-card`,
  `.stuv-icon-box`, `.stuv-button-*`, `.stuv-wpforms`) plus the `:root.dark`
  overrides; deployed into the global-styles custom-CSS field, which WordPress
  prints inline in `<style id="global-styles-inline-css">` on **every** page
  view and never HTTP-caches — so its size is a page-weight decision.
- `data/media/` — images uploaded via the `media` target. `deploy.py` skips
  **dot-prefixed** files, which is why `.stuv-dhbw-logo.svg` and
  `.stuv-dhbw-favicon.svg` sit there as local-only sources.
- `data/maps/` — map definitions (pins, zoom, padding) for `tools/gen_map.py`.
- `tools/` — site-specific utilities with no WP REST access: `gen_icon_css.py`,
  `gen_map.py`, `export_docs_wiki.py`, `build_skill_zip.py`, `export_pdfs.mjs`,
  plus their `test_*.py`.
- `wp-plugin/` — source of truth for the three plugins; the copies on the host
  are artifacts.

## Commands

Run from the repo root. `source .env` first for anything that talks to the host
(`.env` is git-ignored and holds `WP_SITE`, `WP_USER`, `WP_APP_PASS`,
`WP_REST_ROOT`, `WP_ADDRESS_FAMILY`).

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
# Tools: stdlib-only unit tests, no network, no Pillow.
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
TZ=America/Los_Angeles node --test 'wp-plugin/tests/*.test.js'
```

The `TZ` is deliberate: the Mensa menu computes in Europe/Berlin, and the test
only proves that if the machine is somewhere else.

```bash
# Generated files still match their sources (exit 0, no output).
python3 tools/gen_map.py campus --check        # also stadtgebiet, stadtzentrum
npm install --prefix /tmp/lucide lucide-static@0.577.0 >/dev/null
LUCIDE_ICON_DIR=/tmp/lucide/node_modules/lucide-static/icons \
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
counts) and **never contacts the server** — it cannot tell you a page is empty
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

**The staging host is `dev.stuv-heidenheim.de`** (production DNS will later
point at `stuv-heidenheim.de`). It replaced the beta host `stuv.michi.onl`,
which was a _different_ WordPress instance — page ids, the global-styles id and
the media library all changed with it. Anything that reads like a fact about
the old host (`index.php/wp-json`, `?pagename=` URLs, Cloudflare,
`uploads/<YYYY>/<MM>/`) has been re-verified against the new one below; don't
reintroduce it from memory or from git history.

- `WP_REST_ROOT=wp-json` — permalinks are **Beitragsname** (`/%postname%/`) and
  the REST rewrite works; the `index.php/wp-json` fallback the beta host needed
  does not apply (it 301s straight back to `/wp-json/`).
- **If `/wp-json/` ever 404s again, re-save the permalinks — don't hunt for a
  firewall.** This host sat with a 404 REST root on 2026-07-26 until
  **Einstellungen → Permalinks → Speichern** flushed `rewrite_rules`; the
  structure had never been saved after the migration, so core's `wp-json` rules
  were never written. Recognise it by the response: `/wp-json/` returns the
  _theme's_ 404, byte-identical to any unknown slug — the request reached
  WordPress and matched no rule. A firewall block returns 403/deny instead, so
  `all-in-one-wp-security-and-firewall` is the wrong suspect (that
  mis-attribution cost a debugging round). Cross-checks that stayed green:
  `?rest_route=/` answered 200 unauthenticated, and `/feed/`, `/page/2/`,
  `/author/<slug>/` all resolved. `WP_REST_ROOT="?rest_route="` is the stopgap
  that keeps deploys working meanwhile — `wp_block_api.py` handles a `?…` root
  natively.
- `wps-hide-login` is active, so **`wp-login.php` 404s by design** — wp-admin is
  reachable only via its custom slug. Unrelated to the above; don't "fix" it.
- The REST `settings` endpoint does **not** expose `permalink_structure` — core
  never registers that field, so `null` there is evidence of nothing. Judge
  permalinks by whether pretty URLs resolve.
- Front-end subpage URLs are `/<slug>/`; `?pagename=<slug>` still works as a
  fallback. Page permalinks are unaffected by a REST-root breakage.
- **No Cloudflare.** Plain nginx, accepts the default `python-urllib/3.x`
  User-Agent, so the beta host's `403 / error code: 1010` trap does not apply.
  The skill's client still sends `User-Agent: wp-default-editor/1.0` and
  `tools/gen_map.py` still needs its own UA, because CARTO's tile servers do ban
  the stdlib default.
- **The host publishes an AAAA record it does not route.** Every IPv6 connection
  attempt hangs. `curl` and browsers hide this behind Happy Eyeballs, so the
  site feels fine while Python's `urllib` — which gives _each_ candidate address
  the full timeout — stalled 30s per REST call and made `deploy.py all` run for
  minutes and get killed part-way. `wp_block_api.py` caps each connect attempt
  (`WP_CONNECT_TIMEOUT`, default 5s) and caches the address that answered, and
  **`.env` sets `WP_ADDRESS_FAMILY="ipv4"`**, which drops the AAAA candidate
  before any connect (measured 2026-07-30: first REST call 5.6s → 2.2s, full
  `verify_deploy.py` 5.4s). `WP_CONNECT_TIMEOUT` is a per-_process_ cap and
  every script is its own process, so without the pin each command pays it
  again. The pin raises `OSError` if the host ever stops publishing an A record
  — deliberately loud rather than a silent fallback. All three names (`dev.`,
  `www.`, apex) resolve to A `202.61.233.9` plus the same dead AAAA, so the pin
  stays correct when production DNS flips. If a deploy goes mysteriously slow
  again, check this first:

  ```bash
  HOST="$(printf '%s' "$WP_SITE" | sed -E 's#^https?://##')"
  curl -6 -sS -o /dev/null -m 8 -w 'v6 %{http_code} %{time_total}\n' "https://$HOST/wp-json/"
  curl -4 -sS -o /dev/null -m 8 -w 'v4 %{http_code} %{time_total}\n' "https://$HOST/wp-json/"
  ```

- **`WP_SITE` already includes the `https://` scheme.** The skill's client
  normalizes it, ad-hoc `curl` does not: `curl "https://$WP_SITE/..."` builds
  `https://https://…` and fails with `HTTP 000`, which reads like a network
  outage rather than a typo. Strip the scheme first, as above.
- **The host runs WP-Optimize page caching.** A fetch can return a stale,
  minified copy of a page (`x-cache-status: HIT`) whose _inline_ global-styles
  CSS predates the deploy. Bust it with a query string when verifying a CSS
  change. `verify_deploy.py` is unaffected — it reads the REST API, not the
  front end.

## Media

**Deploying the `media` target does not update a changed image.** `deploy.py
media` calls `upload_media(reuse_existing=True)`, which returns the existing
attachment with the _same filename_ untouched — re-running is a no-op that keeps
the old bytes (deliberate: it stops duplicate uploads). `upload_media.py
--force` doesn't help either — WordPress uniquifies the name to
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
`/wp-content/uploads` — root-relative on purpose, so the same markup renders on
staging and on production instead of pinning every map to the host it was
generated against. That URL stability is what makes delete-then-re-upload safe
here. If month/year folders are ever re-enabled, `MEDIA_BASE` has to change with
them and the "URL only survives within the same month" caveat comes back.

Toggling that setting mid-migration is how the library ended up with two
attachments per filename (`uploads/2026/07/jan.jpg` **and** `uploads/jan.jpg`);
the stale set was deleted 2026-07-26. `find_media_by_filename` takes the newest
match and warns on stderr when a name is ambiguous — if that warning appears,
stop and clean up the library before deploying.

`rollback.py` does not cover media; the map images are regenerable with
`gen_map.py --render`. The map images are CSS backgrounds coupled to
`component.css` and the `studentenleben` page HTML, so a map change is a
**three-part deploy** (images, `global-styles`, `studentenleben`) that must go
together or the maps render with the old image under the new geometry.

## The plugins (`wp-plugin/`)

Three plugins, none deployed by `deploy.py` — plugins do not travel over the
content REST API.

- Build: `./wp-plugin/build.sh [plugin …]` → `wp-plugin/<plugin>.zip` (no
  argument builds all three)
- Install: wp-admin → Plugins → Installieren → Plugin hochladen → Aktivieren

They are normal plugins rather than `mu-plugins` only because there is no shell
access to the host; if SSH is ever set up, moving them to
`wp-content/mu-plugins/` is a strict improvement and needs no code change.

**`stuv-mensa`** — the live Mensa menu needs a server-side proxy: `api.dhbw.app`
sends **no CORS headers**, so the browser cannot call it directly. Deactivating
it removes the Speiseplan from the Studentenleben page. Design:
`git show 6a19d0a^:docs/superpowers/specs/2026-07-13-mensa-live-menu-design.md`.

**`stuv-theme`** — the dark-mode toggle. Prints an inline `<script>` in `<head>`
(src-less `wp_register_script` handle + `wp_add_inline_script`) that puts `.dark`
on `<html>` from `localStorage['stuv-theme']`, falling back to the OS
`prefers-color-scheme`, then delegates clicks on `.stuv-theme-option` from
`document`. Head-level and inline is the point: the class must land before the
first paint or dark-mode visitors get a white flash. The matching CSS is the
`:root.dark` block in `component.css`; the markup is a `wp:html` block in
`data/header_blocks.html`. The script also sets `.stuv-theme-ready` on `<html>`,
which is what makes the control visible — `component.css` hides
`.stuv-theme-switch` by default, so **deactivating the plugin freezes the site
in light mode and removes the control** rather than leaving a dead one behind
(same for visitors with JS disabled).
The control is a `<details>` dropdown with three rows (Hell / Dunkel / System),
not a one-click cycle. Two things are deliberate: the `<summary>` icon keys off
`.dark`, i.e. the _resolved_ theme, so System shows sun or moon and never a
monitor glyph — which mode is set is signalled only by the check mark on the
active row (`[aria-checked="true"] .stuv-icon-check`, set from JS). And
`<details>` was chosen over the `popover` attribute because an open popover sits
in the top layer, where the containing block is the viewport, so it cannot be
anchored under the trigger without CSS anchor positioning. The price is that
Escape and outside-click dismissal are hand-rolled in the plugin's `document`
listeners. Plan: `git show 6a19d0a^:docs/superpowers/plans/2026-07-10-wp-dark-mode-toggle.md`
(its inline-script-in-block-HTML approach was rejected for the `unfiltered_html`
reason below).

**`stuv-dsgvo`** — click-to-load for the two Google Calendar embeds (homepage
`sections/02-was-wir-bieten.html`, `pages/events/02-upcoming.html`). **The
privacy guarantee lives in the markup, not in the plugin:** those `<iframe>`s
carry `data-stuv-src` and **no `src`**, so nothing reaches Google until a
visitor clicks — plugin off and JS off included. Don't "fix" that back to a real
`src`. Consequences that hang together and must change together:

- `component.css` hides `iframe[data-stuv-src]` and reveals it again on
  `.stuv-dsgvo-loaded`. Hiding on the _attribute_ is what keeps a
  plugin-off/JS-off visitor from getting an empty 600px box.
- Each embed ships a visible `.stuv-dsgvo-fallback` link inside a
  `.stuv-dsgvo-embed` wrapper; the plugin hides it by setting
  `.stuv-dsgvo-ready` on that wrapper once its script has run.
- The script is enqueued only when the rendered post's content contains
  `data-stuv-src` (`stuv_dsgvo_has_embed()`). An embed moved into a template
  part, widget or reusable block would never load — drop the check if that
  happens.
- Consent **is** persisted per device in `localStorage['stuv-dsgvo-calendar']`
  (since 2026-07-30; it deliberately was not before, because a remembered click
  sends a later pageview to Google without a fresh action — but re-consenting on
  every navigation between homepage and Events page was the reported pain
  point). What makes that defensible is the counterpart: a loaded embed
  **always** renders a `.stuv-dsgvo-revoke` line under it. Don't remove it and
  don't hide it behind a hover or a toggle — the DSGVO wants withdrawal as easy
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
  has no `package.json`. That is also why **PHP is left unformatted** — it would
  need `@prettier/plugin-php` as a real installed dependency. Match the
  surrounding style by hand in `wp-plugin/`.
- `.prettierignore` covers the captured `api.dhbw.app` fixtures (must stay
  byte-exact to be a valid recording) and the built plugin zips.
- **Reformatting block HTML rewrites deployed bytes.** Prettier reflows tags and
  inline `style` attributes. The rendered output is equivalent, but a format
  pass changes the bytes of _every_ target, not just the page you edited — the
  next real deploy rewrites them all. Expect that; don't read it as a content
  change.
- **Always re-validate after formatting** — the whole `data/` tree, not just the
  file you touched.
- Prettier moves the zero-width space in `.stuv-icon-box` paragraphs onto its
  own line. Harmless: Gutenberg's equivalence check normalizes that whitespace,
  and the box renders via CSS mask rather than text.

## Content gotchas

- **German orthography**: legacy migrated content spelled umlauts as ASCII
  digraphs; live content is fixed. **Never blanket-replace** `ae→ä`/`ss→ß`
  (corrupts `neue`, `Wohnungssuche`, …). URL slugs (`?pagename=ueber-uns`) must
  stay digraphs.
- **`--` inside block-comment JSON must be escaped as `\u002d\u002d`.** A literal
  `--` is illegal inside an HTML comment, so Gutenberg writes
  `"color":{"text":"var(\u002d\u002dstuv-muted-foreground)"}` — the `<p>`'s own
  `style` attribute keeps the real `var(--stuv-…)`. Copying a block's JSON by
  hand and leaving the dashes raw produces an invalid block. Note that some
  editing tools decode the escape back to `--` on write; verify with `od` after
  writing one by hand.
- **Block validation**: hand-written HTML must match Gutenberg's canonical
  `save()` output or the editor flags "Dieser Block enthält unerwarteten oder
  ungültigen Inhalt". A block with `style.color.text` needs `has-text-color` on
  its root; button links need `wp-element-button` (backfill: the skill's
  `fix_has_text_color.py`). `validate_blocks.cjs` reads **only its first
  argument** — passing it a glob silently checks one file and prints a clean
  pass, so sweep the tree with the loop under Commands. The pattern
  `'data/*.html'` is deliberate: git's `*` spans slashes, so it matches every
  block-HTML file in the tree (40 today), while `'data/**/*.html'` would miss
  `header_blocks.html` / `footer_blocks.html` (no subdirectory).
- **`"style":{}` is not stable across a save.** An empty JSON object in a block
  comment comes back from WordPress as `"style":[]` — PHP decodes `{}` to an
  empty array and re-encodes it as `[]`. It renders fine and still validates,
  but it makes the affected target report drift on every source-vs-live
  comparison forever, which buries real drift. The attribute is a no-op anyway:
  omit it rather than writing it empty.
- **Verify a deploy by comparing raw block markup, not by eyeballing the page.**
  Fetch `content.raw` per manifest target and compare it to the joined source —
  every target should be byte-identical. That is what `verify_deploy.py` does.
- **`unfiltered_html` is active.** `<script>` tags and `onclick` attributes in
  block content survive REST writes byte-for-byte (verified by draft
  round-trip). Do **not** rely on it: it holds only because the deploy user is
  an admin and `DISALLOW_UNFILTERED_HTML` is unset. Any hardening would strip
  inline scripts silently, with no error. Ship JS via a plugin enqueue instead.
- **Page template**: all pages use the theme's `page-no-title` template. New
  pages created via REST **must** set `"template": "page-no-title"`, or
  WordPress renders a big post-title heading.
- **Layout**: global widths/colors/typography belong in
  `data/global-styles.json`; component classes in `data/styles/component.css`.
  Full-bleed section bands need `align:full` per section.
- **A group's `contentSize` sizes its children, not the group** — and that
  silently un-aligns the section lead. Core's constrained layout gives the
  _children_ of a group with its own `contentSize` a `max-width` and
  `margin-inline:auto`, but the group's own box still fills the parent column
  (currently `contentSize: 56rem` / `wideSize: 72rem` in the tokens).
  `p.stuv-section-intro` carries `margin-inline:0 !important`, and that "0" is
  measured against the full-width group box — so the heading lands at the inner
  column while its lead escapes further left. Symptom: a section header where
  eyebrow and heading sit inset but the lead does not. Fix by dropping the inner
  `contentSize` so everything inherits one column, or by capping the group
  itself with a class. **Eyeballing the block HTML will not show this** —
  measure `getBoundingClientRect().left` for eyebrow/heading/lead/body on the
  rendered page.
- **A page-wide horizontal scroll on mobile came from the header, not from the
  page.** The document is as wide as its widest child, so one overflowing
  element in the template part makes _every_ page swipeable sideways — which is
  why it reads like a per-page bug and isn't one. `.stuv-header-row` is
  `flexWrap:nowrap` and at 360px held ~350px of content in ~300px: the logo is
  168px on its own (`.stuv-logo-mark` is `height:2.5rem` and the mark is
  1342x320, so its width is a _consequence_ of its height — easy to miss when
  reading the CSS). Fixed 2026-07-30 in the `max-width:639px` block. The numbers
  there are the smaller half of the fix; the load-bearing half is `min-width:0`
  on the logo group plus `max-width:100%` on the mark, which lets the logo
  shrink instead of the row overflowing at widths nobody measured. Keep that
  when touching the header. Diagnose by filtering
  `getBoundingClientRect().right > document.documentElement.clientWidth`, not by
  reading the CSS.
- **Fluid typography is off; a size ships exactly as written.**
  `data/global-styles.json` sets `settings.typography.fluid: false` and declares
  its own static `fontSizes` presets (`small` 0.875, `medium` 1, `large` 1.125,
  `x-large` 1.875, `xx-large` 3rem). Before 2026-07-30 TT5's fluid typography
  rewrote _every_ block-level `"fontSize"` into a `clamp()` floored at
  `minFontSize`, collapsing all eight inline sizes in use — `0.75rem` through
  `2rem` — to the **same 16px** at a 320px viewport. Do not re-enable it: the
  responsive steps live in `component.css` media queries (`.stuv-hero-title`,
  `.stuv-h2`), where a breakpoint-based scale belongs and which fluid typography
  never touched anyway. Declaring the presets explicitly is **not** optional —
  with `fluid:false` an undeclared preset falls back to TT5's own `size` field.
  `p.stuv-section-intro` owns its size in CSS with `!important` (to beat the
  blocks' inline `font-size`). Verify a size change on the served HTML, not with
  `--dry-run` or the block validator — neither reads rendered CSS.

## Generated files — never hand-edit

- **The maps are generated.** `data/pages/studentenleben/02-campus-karte.html`
  and the map block in `09-freizeit.html` are emitted by `tools/gen_map.py` from
  `data/maps/*.json`. Edit the JSON and re-run
  `python3 tools/gen_map.py <id> --render --write`, never the block HTML — a
  hand edit is silently overwritten on the next `--write`. Only the region
  between the `gen_map:` markers is owned by the generator; the rest of those
  files is hand-editable. `--check` (needs Pillow and `npx prettier`) proves the
  committed images and blocks still match the data; a Pillow/libwebp upgrade can
  change WebP bytes for identical input, in which case re-render and commit. The
  basemaps are self-hosted and the light/dark swap is two inline custom
  properties picked up by `:root.dark .stuv-map-frame`; a `<picture>` with a
  `prefers-color-scheme` `<source>` would follow the OS and ignore the site's
  own theme toggle. Leaflet was rejected on purpose (it would send visitor IPs
  to a tile host).
- **The icon CSS is generated.** The `:root { --ico-*: url("data:…") }` block in
  `component.css` sits between the `gen_icon_css:` markers and comes from
  `tools/gen_icon_css.py` (pinned to `lucide-static@0.577.0`). It is the largest
  single thing in the inline global CSS, so its encoding is deliberately tight —
  read the module docstring before touching the escaping.

## Docs

`docs/*.md` is human-readable documentation, written in German.
**They are no longer published on the WordPress site.** They live in the AStA
wiki at `https://wiki.dhbw-asta.de/`, which runs **BookStack**; `/docs/` was
trashed and the footer link removed on 2026-08-14. BookStack has a native
per-page Markdown editor, so `tools/export_docs_wiki.py` emits **Markdown**, one
`build/wiki/<doc>.md` per page (git-ignored), to be pasted into a page switched
to the Markdown editor. It is stdlib-only — it does not render Markdown,
BookStack does; it only rewrites what breaks outside this repo, and it skips
fenced code blocks so a sample showing `src="/wp-content/…"` stays verbatim.

**A docs edit is therefore a two-step change**: edit the Markdown, then
re-export and re-paste the affected page. Nobody but a human can do the second
step, so say so rather than assuming the wiki is current. BookStack _does_ have
a write API (`PUT /api/pages`, `Authorization: Token <id>:<secret>`) that would
collapse this to one step, but it needs an API token and the maintainer's
account lacks the `Access system API` role permission — don't design around the
API until that changes. The exporter reads an explicit allow-list (`DOC_FILES`
in `tools/export_docs_wiki.py`), not a glob: a new `docs/*.md` stays repo-only
until it is added there. Nothing in `docs/` may contain secrets. Do not re-add a
`docs` deploy target to `data/manifest.json`.

`docs/superpowers/` holds specs and plans from the brainstorm → spec → plan →
execute cycle, and lists **open work only** — executed specs and plans are
deleted from the tree once their work ships (precedent: `6a19d0a`), so the
directory is absent when nothing is open. They stay in git history: reference a
deleted one as `git show 6a19d0a^:<path>`, never as a bare path, which reads
like a live file and rots silently. Grep the tree for references before
deleting.

## Full-site PDF export

> **Puppeteer rule:** do **not** run Puppeteer/Playwright or any
> headless-browser script without the maintainer's explicit approval each time —
> including `tools/export_pdfs.mjs`.

`node tools/export_pdfs.mjs --list` prints planned URLs without a browser; a
real run self-installs Puppeteer + Chrome into `~/.cache/stuv-pdf-export` and
merges per-route PDFs with `pdfunite`/`qpdf`.

## Repo-local skills

`.claude/skills/improving-code/` — the refactoring procedure for this repo's
block HTML, component CSS and design tokens. Its rule: a cleanup must be a
**verified no-op** on deployed content, or the difference must be stated.

## History

Full pre-split history (Next.js app, migration scripts, parity-verification era)
is archived in the predecessor repository (2026-07-10). Rationale:
`git show 6a19d0a^:docs/superpowers/specs/2026-07-10-repo-split-design.md`.
