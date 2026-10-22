---
name: wordpress-default-editor
description: 'Deploys, verifies and rolls back this repo''s WordPress block content over the REST API, and repairs blocks the editor flags as invalid ("unerwarteten oder ungültigen Inhalt"). Trigger: deploy, rollback, an invalid block, a REST call to the site.'
---

# WordPress REST tooling

`data/` is the source of truth: change content there and deploy it. A direct
REST write to a page is drift that the next deploy overwrites, so REST writes
are for deploys, rollbacks, media and creating a resource.

Run from the repo root with `SKILL=.agents/skills/wordpress-default-editor`
after `source .env`. Each script's docstring and `--help` hold its full usage.

## Environment

- `WP_SITE`: site URL including `https://`.
- `WP_USER`, `WP_APP_PASS`: user and Application Password (Basic Auth).
- `WP_REST_ROOT`: default `wp-json`; `?rest_route=` while `/wp-json/` 404s.
- `WP_ADDRESS_FAMILY=ipv4` skips a dead AAAA record that would otherwise cost
  every process one `WP_CONNECT_TIMEOUT` (default 5s); raises if the host has
  no address in that family.

## Scripts (`$SKILL/scripts/`)

- `deploy.py --manifest M --list | all --dry-run | <target>` writes targets in
  manifest order. `--dry-run` checks sources only, never the server.
- `verify_deploy.py --manifest M [<target>] [--diff]` diffs live `content.raw`
  and custom CSS against the sources: 0 match, 1 drift, 2 unfetchable. The only
  proof a deploy landed.
- `verify_global_css.py --marker SEL … --icon-marker=--ico-x`, after a
  `global-styles` write: 1 = component rules stripped, 2 = data-URI icons
  stripped.
- `rollback.py <id> [--endpoint E]` restores content and status from
  `/tmp/wp_backup/<site>/`; the id may be `theme//slug`.
- `upload_media.py <file> [--alt T]` returns the existing attachment when the
  filename is already in the library.
- `fix_has_text_color.py`: `add_missing_classes(html)` adds `has-text-color` /
  `wp-element-button`; gate the write with `assert_only_additions(old, new)`.
- `blockcheck/validate_blocks.cjs <file>` runs the real Gutenberg parser and
  reads only its first argument.

Manifest targets, paths relative to the manifest's directory:

- `structural`: `endpoint`, `id`, `source` (a file, or a directory whose
  `*.html` join in filename order), optional `status` (otherwise fetched).
  Template parts use endpoint `template-parts` and id `theme//slug`.
- `global-styles`: `tokens` (theme.json-shaped) plus optional `css` for the
  custom-CSS field.
- `media`: a directory, non-recursive, dotfiles skipped. A failed file prints
  `SKIP`, the rest continue, and the run exits non-zero.

## Python API

```python
import sys; sys.path.insert(0, ".agents/skills/wordpress-default-editor/scripts")
import wp_block_api as wp
```

- `fetch_raw(endpoint, id)` reads with `context=edit`: raw block comments plus
  `status`. Echo that `status` back on every write; a write without it can
  publish a draft.
- `backup(endpoint, id)`, then `save_structural(endpoint, id, content, status, confirm=True)`,
  which refuses without a backup, `confirm` and balanced block markup.
- `get_global_styles()`; `apply_global_styles(settings, styles, confirm=True)`
  deep-merges into the user record after a JSON backup. User palette and font
  values read back nested under a `custom` key.
- `find_by_slug(endpoint, slug)` before `create_resource(endpoint, fields)`;
  `delete_resource` undoes it. A synced pattern goes on `blocks` with
  `"meta": {"wp_pattern_sync_status": "fully"}`.
- `find_media_by_filename(name)` returns the newest match and warns on
  duplicates; `upload_media(path, reuse_existing=…)`.

## Invalid blocks

The editor shows "Dieser Block enthält unerwarteten oder ungültigen Inhalt"
when a block's stored HTML differs from what its `save()` regenerates from the
comment JSON. The front end renders fine.

1. Run `validate_blocks.cjs` on the markup for the exact `Expected …, saw …`.
   On first run it installs the latest `@wordpress` packages; when a verdict
   looks off, match them to the site's WordPress version
   (`<meta name="generator">`).
2. Make the attributes carry everything the HTML shows:
   - `Expected tag h2, saw h3`, undeclared inline style: add `level`; move
     inline sizes and margins into `style.typography` / `style.spacing`.
   - Extra `text-align` on a group: drop it; add `has-text-align-center` via
     `className`.
   - Extra style with no block support (`overflow:hidden`): a utility class in
     `component.css`, set via `className`.
   - Missing `has-border-color` with a border shorthand: let `save()` emit
     class and longhands; set `style.border.style: "solid"`.
   - `color` attribute absent though the HTML has it: it was written as a
     sibling of `style`; move it inside.
   - Raw `<a>` / `<div>` inside a group: wrap it in a `core/html` block.

3. Re-run the validator to 0 invalid and confirm no class, style declaration
   or text was lost.

"Attempt Block Recovery" and `serialize()` rebuild a block from its
attributes and drop whatever the attributes lack, so they come after step 2,
never instead of it.
