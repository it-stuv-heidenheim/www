# AGENTS.md

Content source of the live WordPress site of StuV DHBW Heidenheim (`stuv-heidenheim.de`, Twenty Twenty-Five
block theme): block HTML, design tokens, component CSS, three plugins, map and icon generators. This file
instructs; `docs/*.md` (German, human-facing) explains, and `docs/testing.md` lists every check command.

## Tooling, deploy, host

- All WP tooling (REST client, `deploy.py`, `verify_deploy.py`, `rollback.py`, `blockcheck`) is in the
  `wordpress-default-editor` skill in this repo (`SKILL=.claude/skills/wordpress-default-editor`, paths relative to
  the repo root); read its SKILL.md first. Its tests: `pytest` in that directory (needs `flask`, `pytest`).
- No build step, no auto-deploy, no root `package.json` (Prettier runs via `npx`; PHP is formatted by hand).
  `source .env` before talking to the host; `WP_SITE` includes `https://`, so strip it for ad-hoc `curl`.
- Before every commit: `npx prettier --check .` and `python3 -m unittest discover -s tools -p "test_*.py"`.
- `validate_blocks.cjs` reads only its first argument; sweep the tree after every edit or Prettier pass:
  `for f in $(git ls-files 'data/*.html'); do node $SKILL/scripts/blockcheck/validate_blocks.cjs "$f"; done | grep -E ': [1-9][0-9]* invalid'` (silent = valid)
- Deploy runs as `.github/workflows/deploy.yml`: manual `workflow_dispatch` on `main`, environment `production`,
  scripts from the same commit. Never add a push trigger. Locally:
  `deploy.py --manifest data/manifest.json all --dry-run` (no server), `deploy.py … <target>`, then
  `verify_deploy.py --manifest data/manifest.json`, the only proof the site serves this repo. Undo:
  `rollback.py <id>`. After a `global-styles` deploy:
  `verify_global_css.py --marker .stuv-card --marker .stuv-icon-box --marker ":root.dark" --marker .stuv-wpforms --marker .stuv-body-muted --icon-marker=--ico-calendar`
- Manifest source paths are relative to `data/`; a page is its directory's `*.html` joined in filename order.
  `data/parked/` is never deployed. The Vorsitz grid is synced pattern 212 (`pattern-vorsitz`).
- Generated regions, edit only their sources: maps between `gen_map:` markers (`data/maps/*.json`, then
  `tools/gen_map.py <id> --render --write`) and `--ico-*` between `gen_icon_css:` markers (`tools/gen_icon_css.py`).
- Fonts live in the WP Font Library at `/wp-content/uploads/fonts/`; `fontFace` `src` stays self-hosted (DSGVO).
- `wp-login.php` 404s by design. `/wp-json/` 404 with `?rest_route=/` 200: re-save Permalinks; meanwhile
  `WP_REST_ROOT="?rest_route="`. WP-Optimize caches pages: add a query string when checking front-end CSS.

## Media

- `deploy.py media` keeps an existing attachment of the same filename; `--force` orphans a `-1` copy. Replace at
  the same URL: `wp.delete_resource("media", wp.find_media_by_filename(n)["id"], force=True)`, then
  `wp.upload_media(path, reuse_existing=False)`, assert no `-1`. An ambiguity warning means clean up first.
  A map change deploys together: images, `global-styles`, `studentenleben`.

## Plugins (`wp-plugin/`, see `docs/plugins.md`)

- Shipped as zips (`./wp-plugin/build.sh`, upload in wp-admin), never by `deploy.py`.
- `stuv-dsgvo`: calendar iframes carry `data-stuv-src` and no `src`, so nothing reaches Google before a click;
  a loaded embed always shows `.stuv-dsgvo-revoke`. Deploy together: zip, `global-styles`, `homepage`, `events`.

## Block content

- Match Gutenberg's `save()`: `style.color.text` needs `has-text-color`, button links `wp-element-button`.
- In block-comment JSON, `--` is written `\u002d\u002d` (verify with `od`: some tools decode it on write).
- Keep JSON `style` and inline `style` in agreement; omit an empty `"style":{}` (stored as `[]`, permanent drift).
- Borders come from `.stuv-card`; a block border colour adds `has-border-color`, which turns the text grey.
- REST-created pages set `"template": "page-no-title"`. Fluid typography stays off; responsive sizes live in
  `component.css` media queries. Verify sizes and alignment on the served page, not in the HTML.
- New contact link → `CONTACTS` in `tools/test_content.py`; new card-link class → `CARD_LINK_CLASSES`
  (`tools/sitecheck.py`) and the `.stuv-card:has(…)` rule. Check 360px width and a Tab pass by eye.
