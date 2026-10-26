# AGENTS.md

Content source of the live WordPress site of StuV DHBW Heidenheim (`stuv-heidenheim.de`, Twenty Twenty-Five
block theme): block HTML, design tokens, component CSS, four plugins, map and icon generators. This file
instructs; `docs/*.md` (German, human-facing) explains, and `docs/testing.md` lists every check command.

## Tooling, deploy, host

- All WP tooling (REST client, `deploy.py`, `verify_deploy.py`, `rollback.py`, `blockcheck`) is in the
  `wordpress-default-editor` skill in this repo (`SKILL=.agents/skills/wordpress-default-editor`, paths relative to
  the repo root); read its SKILL.md first. Its tests: `pytest` in that directory.
- No build step, no root `package.json` (Prettier runs via `npx`; PHP is formatted by hand).
  `source .env` before talking to the host; `WP_SITE` includes `https://`, so strip it for ad-hoc `curl`.
- Before every commit: `npx prettier --check .` and `python3 -m unittest discover -s tools -p "test_*.py"`.
- Sweep the tree with `validate_blocks.cjs` after every edit or Prettier pass (one process, all files):
  `node $SKILL/scripts/blockcheck/validate_blocks.cjs $(git ls-files 'data/*.html') | grep -E ': [1-9][0-9]* invalid'` (silent = valid)
- Deploy runs as `.github/workflows/deploy.yml` on `main`, by `workflow_dispatch` only (`gh workflow run deploy.yml`);
  a push runs only the checks, so `main` may hold undeployed commits. Environment `production`, scripts from the
  same commit. Every run waits for a required reviewer of `production`; never remove that gate, add a push
  trigger or deploy from another branch. Start a deploy only when asked. Locally, the same as the Action:
  `deploy.py --manifest data/manifest.json changed` (or target names); it reads every written target back, and
  checks the `markers` of `global-styles`. A target whose live content matches no commit (`EDITED`) was edited in
  wp-admin, and the deploy stops before writing. Port the edit into `data/`, then deploy with
  `--overwrite <target>` (Action: `overwrite` input). Undo: `rollback.py <id>` or `--global-styles`.
- Manifest source paths are relative to `data/`; a page is its directory's `*.html` joined in filename order.
  `data/parked/` is never deployed. The Vorsitz grid is synced pattern 212 (`pattern-vorsitz`).
- Generated regions, edit only their sources: maps between `gen_map:` markers (`data/maps/*.json`, then
  `tools/gen_map.py <id> --render --write`) and `--ico-*` between `gen_icon_css:` markers (`tools/gen_icon_css.py`).
- Fonts live in the WP Font Library at `/wp-content/uploads/fonts/`; `fontFace` `src` stays self-hosted (DSGVO).
- `wp-login.php` 404s by design. `/wp-json/` 404 with `?rest_route=/` 200: re-save Permalinks; meanwhile
  `WP_REST_ROOT="?rest_route="`. WP-Optimize caches pages: add a query string when checking front-end CSS.
- `.github/workflows/monitor.yml` (environment `monitor`, no reviewer, reads only) runs daily
  `verify_deploy.py --history`, `tools/check_plugins.py` and `tools/site_state.py`, Mondays `tools/check_links.py`.
- `data/site-state.json` records what only wp-admin sets (settings, pages, plugins, media, SEO, form fields); it is
  never deployed. After a change in wp-admin: `tools/site_state.py --write`, commit. No e-mail addresses in it.

## Media

- `deploy.py media` and `upload_media.py` keep an existing attachment of the same filename, so a changed file never
  goes up that way. Replace at the same URL with `upload_media.py --replace <file>` only (`replace_media()`: backs up
  the old file, deletes, uploads, raises if the URL changed); undo: `rollback.py --media <filename>`. An ambiguity
  warning means clean up first. A map change: both images with `--replace`, then a `changed` deploy.

## Plugins (`wp-plugin/`, see `docs/plugins.md`)

- Shipped as zips (`./wp-plugin/build.sh`, upload in wp-admin), never by `deploy.py`. A version bump changes the
  header `Version` and the `STUV_*_VERSION` constant together; `tools/check_plugins.py` compares with the site.
- `stuv-dsgvo`: calendar iframes carry `data-stuv-src` and no `src`, so nothing reaches Google before a click;
  a loaded embed always shows `.stuv-dsgvo-revoke`. A change ships as the zip, then a `changed` deploy.
- `stuv-events`: the server reads the public calendar feed, so the event lists need no consent; the browser never
  parses a timestamp. Markup without the plugin shows `.stuv-events-fallback`. Same shipping order as above.

## Block content

- Match Gutenberg's `save()`: `style.color.text` needs `has-text-color`, button links `wp-element-button`.
- In block-comment JSON, `--` is written `\u002d\u002d` (verify with `od`: some tools decode it on write).
- Keep JSON `style` and inline `style` in agreement; omit an empty `"style":{}` (stored as `[]`, permanent drift).
- Borders come from `.stuv-card`; a block border colour adds `has-border-color`, which turns the text grey.
- REST-created pages set `"template": "page-no-title"`. Fluid typography stays off; responsive sizes live in
  `component.css` media queries. Verify sizes and alignment on the served page, not in the HTML.
- New contact link → `CONTACTS` in `tools/test_content.py`; new card-link class → `CARD_LINK_CLASSES`
  (`tools/sitecheck.py`) and the `.stuv-card:has(…)` rule.

## Rendering

- The checks read source and render nothing. Render the served page whenever it helps, in a browser or headless
  with screenshots; that needs no approval. After a layout change: 360px width (no sideways scroll), light and
  dark, a Tab pass (every link and whole card shows a ring).
