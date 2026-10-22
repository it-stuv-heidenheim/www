---
name: wordpress-default-editor
description: 'Edits WordPress block-editor (Gutenberg) sites via the REST API: text, buttons, images, bulk changes, page and template-part rebuilds, global styles, "Attempt Block Recovery" fixes. Needs an Application Password. Trigger: a Gutenberg site, wp-json, a WordPress page to change. DIVI sites: managing-divi-sites.'
---

# WordPress Default Editor

## Overview

Edit WordPress sites running the default block editor through `https://<site>/wp-json/`. All reads and writes use the WordPress REST API with Basic Auth (Application Password).

## When to Use

- Updating text in heading, paragraph, button, or image blocks
- Fixing placeholder or demo content
- Auditing pages/posts for specific text
- Swapping image URLs
- Publishing, unpublishing, or changing post status

## When NOT to Use

- DIVI sites (use managing-divi-sites)
- Server-level setup (nginx, PHP, hosting)
- Plugin or theme development
- Visual layout redesign that requires the block editor UI (full template-part or page rebuilds _expressed as block markup_ are supported — see "Structural writes, creates & template parts")

## Quick Reference

| Task                      | How                                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| List pages                | `GET /wp-json/wp/v2/pages?per_page=100&_fields=id,title,status`                                                                                                                      |
| Fetch raw blocks          | `GET /wp-json/wp/v2/{endpoint}/{id}?context=edit&_fields=id,title,content,status`                                                                                                    |
| Save                      | `POST /wp-json/wp/v2/{endpoint}/{id}` with `{"content": ..., "status": ...}`                                                                                                         |
| Backup                    | `scripts/wp_block_api.py backup(endpoint, pid)` writes to `/tmp/wp_backup/<site>/`                                                                                                   |
| Update text (leaf)        | `scripts/wp_block_api.py update_block_text(content, block_type, old_text, new_text)`                                                                                                 |
| Verify scope              | `scripts/wp_block_api.py verify_only_text_changed(old, new, block_type, old_text, new_text)`                                                                                         |
| Structural write          | `scripts/wp_block_api.py save_structural(endpoint, id, content, status, confirm=True)` (full tree; backup + balanced-markup gated)                                                   |
| Create resource           | `scripts/wp_block_api.py create_resource("blocks", {...})`; undo with `delete_resource`; dedupe with `find_by_slug`                                                                  |
| Template part             | endpoint `template-parts`, id `theme//slug` (e.g. `twentytwentyfive//header`)                                                                                                        |
| Global styles             | `scripts/wp_block_api.py apply_global_styles(settings_patch, styles_patch, confirm=True)` (design tokens / layout widths; JSON-backup gated). See `references/block-theme-layout.md` |
| Rollback                  | `python3 scripts/rollback.py <id> [--endpoint pages]` (id may be `theme//slug`)                                                                                                      |
| Validate blocks           | `node scripts/blockcheck/validate_blocks.cjs <raw-markup-file>` → lists invalid blocks + exact `save()` mismatch (auto-installs deps). See "Block validation errors"                 |
| Upload media              | `python3 scripts/upload_media.py <file> [--alt "text"] [--force]` (idempotent by filename)                                                                                           |
| Manifest deploy           | `python3 scripts/deploy.py --manifest <path> [--list \| all --dry-run \| <target>]` — see "Manifest-driven site deploys"                                                             |
| Verify a deploy           | `python3 scripts/verify_deploy.py --manifest <path> [<target>] [--diff]` — diffs live content against sources (exit 0 match / 1 differ / 2 unfetchable)                              |
| Verify custom CSS         | `python3 scripts/verify_global_css.py --marker .cls [--icon-marker=--ico-x]` (exit 0/1/2)                                                                                            |
| Backfill validity classes | `scripts/fix_has_text_color.py` → `add_missing_classes(html)`, gate with `assert_only_additions(old, new)`                                                                           |

## Authentication

**Check memory and `references/auth.md` first.** For a new site, ask for the site URL, WordPress username, and an Application Password (see `references/auth.md` to create one). Google SSO blocks normal-password REST login; Application Passwords bypass it. Then export and verify:

```bash
export WP_USER="username"
export WP_APP_PASS="xxxx xxxx xxxx xxxx"
export WP_SITE="https://example.com"
curl -s -u "$WP_USER:$WP_APP_PASS" "$WP_SITE/wp-json/wp/v2/users/me"
```

### REST root / permalinks

The client builds URLs as `$WP_SITE/wp-json/...`, which assumes **pretty permalinks** (the usual case — e.g. a postname structure like `/sample-post/`). If the site uses _plain_ permalinks (`?p=123`) or a plugin blocks the pretty REST route, `/wp-json/` 404s. Set `WP_REST_ROOT` instead of hacking `WP_SITE`:

```bash
export WP_REST_ROOT="index.php/wp-json"   # plain-permalink REST root
```

Confirm which root works before writing: `curl -s -o /dev/null -w "%{http_code}\n" "$WP_SITE/wp-json/"`.

### A site that is slow only from Python

If REST calls take ~30s each while `curl` against the same URL is instant, the
host almost certainly publishes an address it does not route — typically an
AAAA record on a box with no working IPv6. `curl` and browsers paper over this
with Happy Eyeballs; `socket.create_connection` does not, and hands _every_
candidate address the full timeout, so each request eats the whole read timeout
before falling back. A `deploy.py all` then runs for minutes and tends to get
killed part-way, which looks like a hung deploy rather than a routing bug.

`wp_block_api.py` caps each connect attempt and remembers the address that
answered, so the cost is one short stall per run. Tune with `WP_CONNECT_TIMEOUT`
(seconds, default 5). That cap is still paid once per _process_, and every
script here is its own process — so on a host whose AAAA is permanently
unroutable, pin the family and skip IPv6 before connecting at all:

```bash
export WP_ADDRESS_FAMILY="ipv4"   # or ipv6; unset/auto tries every address
```

Pinning raises `OSError` if the host publishes no address in that family rather
than falling back silently — a pin that stops matching reality should be loud.
To confirm the diagnosis:

```bash
HOST="$(printf '%s' "$WP_SITE" | sed -E 's#^https?://##')"
curl -6 -sS -o /dev/null -m 8 -w 'v6 %{http_code} %{time_total}\n' "https://$HOST/wp-json/"
curl -4 -sS -o /dev/null -m 8 -w 'v4 %{http_code} %{time_total}\n' "https://$HOST/wp-json/"
```

The real fix belongs in DNS; the client-side cap only keeps deploys usable.

## Content Endpoints

A full site audit iterates all of:

- `wp/v2/pages`
- `wp/v2/posts`
- Custom post types registered with `show_in_rest=true`

Skip any endpoint that returns 404. The fetch and write mechanics are identical; only the path changes.

**Always use `?context=edit`.** Without it, the API returns rendered HTML with entity-encoded block comments that cannot be parsed or written back.

**Always fetch `status` alongside `content`** so you can echo it back on write. POSTing without `status` can accidentally publish a draft.

## Implementation

For all modifications, use the pattern in `scripts/wp_block_api.py`:

```python
import scripts.wp_block_api as wp

# 1. Backup
data = wp.backup("pages", 1)
old_content = data["content"]["raw"]
status = data["status"]

# 2. Modify
new_content = wp.update_block_text(
    old_content, "paragraph", "old text", "new text"
)

# 3. Verify scope
if not wp.verify_only_text_changed(old_content, new_content, "paragraph", "old text", "new text"):
    raise RuntimeError("Scope check failed")

# 4. Save
wp.save_content("pages", 1, new_content, status)
```

Only edit **leaf blocks** (heading, paragraph, button, image) with this helper. Target a button as `block_type="button"`, not the `buttons` wrapper. If a change touches nested blocks (columns, groups, query loops), stop and ask the user for confirmation before saving.

`update_block_text` refuses (raises) when `old_text` matches more than one block of that type. Pass a longer, unique snippet to disambiguate rather than letting it guess.

## Structural writes, creates & template parts

`update_block_text` is for surgical leaf edits. Three operations go beyond it; all keep the same auth, backup, and rollback discipline.

**Structural write — replace a whole block tree** (a template part, or a full page rebuild from section markup). This intentionally does _not_ preserve surrounding blocks, so "verify scope" is replaced by a backup requirement, an explicit `confirm=True`, and a balanced-markup check:

```python
import scripts.wp_block_api as wp

wp.backup("template-parts", "twentytwentyfive//header")          # required, or it raises
new = open("scripts/data/header_blocks.html").read_text()
wp.save_structural("template-parts", "twentytwentyfive//header", new, "publish", confirm=True)
```

`save_structural(endpoint, id, content, status, *, confirm)` raises unless `confirm=True`, a backup already exists for that resource, and `assert_balanced_blocks(content)` passes (block-comment delimiters nest correctly). Roll back with `rollback.py`.

**Block themes constrain layout.** On a block theme the page's `post-content` is constrained at the theme content width (~645px in Twenty Twenty-Five), so a top-level section with no `align` is clamped to it — _even if you set a larger `contentSize`_, since `contentSize` sizes a group's children, not the group. The result is a too-narrow page with backgrounds that don't reach the edges. Before any page or section rebuild, read **`references/block-theme-layout.md`** for the full-bleed-band pattern, the Tailwind→block width mapping, theme/palette verification, and a pre-flight checklist.

**Template parts & templates** use the `template-parts` (or `templates`) endpoint and a string id `theme//slug`, e.g. `twentytwentyfive//header`. `fetch_raw`, `save_content`, `save_structural`, `backup`, and `rollback.py` all accept that id form.

**Create a resource** — synced patterns / reusable blocks live on `wp/v2/blocks`. There is no prior state to back up, so make it reversible: check `find_by_slug` first (idempotency), and `delete_resource` to undo.

```python
existing = wp.find_by_slug("blocks", "stuv-hero")
if existing is None:
    wp.create_resource("blocks", {
        "title": "Stuv Hero", "slug": "stuv-hero",
        "content": pattern_markup, "status": "publish",
        "meta": {"wp_pattern_sync_status": "fully"},
    })
```

## Manifest-driven site deploys

For a site whose content lives in a repo as block-HTML files, drive all writes
from a manifest instead of hand-written per-page scripts:

```bash
python3 scripts/deploy.py --manifest /path/to/data/manifest.json --list
python3 scripts/deploy.py --manifest /path/to/data/manifest.json all --dry-run
python3 scripts/deploy.py --manifest /path/to/data/manifest.json homepage
python3 scripts/verify_deploy.py --manifest /path/to/data/manifest.json   # after
```

**`--dry-run` is not verification.** It validates sources locally and prints
byte counts without contacting the server, so it cannot tell you a target was
skipped, half-written, or is serving an empty page. Always finish a deploy with
`verify_deploy.py`, which fetches each target and diffs it against its source
(exit 0 match / 1 differ / 2 unfetchable); add `--diff` to see what changed.

The manifest maps target names to resources. **Source paths are relative to
the manifest's directory:**

```json
{
  "global-styles": {
    "type": "global-styles",
    "tokens": "global-styles.json",
    "css": "styles/component.css"
  },
  "header": {
    "type": "structural",
    "endpoint": "template-parts",
    "id": "twentytwentyfive//header",
    "source": "header_blocks.html",
    "status": "publish"
  },
  "homepage": {
    "type": "structural",
    "endpoint": "pages",
    "id": 10,
    "source": "sections",
    "status": "publish"
  },
  "images": { "type": "media", "source": "assets/img" }
}
```

- A `structural` source is one `.html` file or a directory whose `*.html`
  files are joined in filename order. Writes go through `save_structural`
  (backup + `confirm=True` + balanced-markup check). An omitted `status` is
  fetched from the live resource.
- A `global-styles` target sends `tokens` (theme.json-shaped settings/styles)
  through `apply_global_styles`; an optional `css` file is injected into the
  custom-CSS field (`styles.css`).
- A `media` target uploads every file in the `source` **directory** (non-recursive,
  dotfiles skipped) via `upload_media`, which reuses an existing attachment with
  the same filename — so re-running is a no-op, not a duplicate upload. Put media
  targets before the structural targets that reference the URLs. A file that fails
  to upload is printed as `SKIP` and the batch continues, but the run then exits
  non-zero: a partial media deploy never looks like a clean one.
- Run `all --dry-run` before every real deploy: it reads and validates every
  source (balanced block delimiters) without writing.
- After a global-styles deploy, confirm REST sanitization kept your CSS:
  `python3 scripts/verify_global_css.py --marker .my-component-class --icon-marker=--ico-name`
  — exit 1 = component rules stripped (restore from backup); exit 2 = data-URI
  icon vars stripped (keep them in a header `core/html` block instead).

## Block validation errors ("ungültiger Inhalt")

The editor flags **"Dieser Block enthält unerwarteten oder ungültigen Inhalt / Wiederherstellung versuchen"** ("…unexpected or invalid content / Attempt Block Recovery") when a block's stored HTML doesn't match what its `save()` regenerates from its JSON attributes. Hand-authored or migrated markup triggers this in bulk. The page still renders fine on the front end — it's an editor-only problem — but recovery rewrites the block.

**Get ground truth — don't guess.** You cannot reliably eyeball which blocks are invalid or why; reasoning about it ships wrong fixes. Save the raw markup (`?context=edit`) to a file and run the bundled validator, which runs the _actual_ Gutenberg parser:

```bash
node scripts/blockcheck/validate_blocks.cjs /tmp/page.html   # auto-installs deps on first run
```

It prints each invalid block's type, the exact `Expected …, saw …` reason, its parsed `style` attributes, and its markup. Match the validator's `@wordpress` version to the site's WordPress version (front-end `<meta name="generator">`) — `save()` details drift between majors.

**Fix losslessly — make the attributes (or a wrapper) capture the visual, then re-save.** The invalidity is always "the HTML carries something the attributes don't." Resolve each by ADDING it to the block model, never by dropping it:

| Validator says…                                                                        | Cause                                                                                                                    | Lossless fix                                                                                                                   |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `Expected tag h2, saw h3` + undeclared inline style on the heading                     | `level`/`style` missing from the comment JSON                                                                            | Add `level` to match the tag; lift inline `font-size`/`font-weight`/`margin` into `style.typography`/`style.spacing`           |
| `style` has extra `text-align:center`                                                  | core/group has no `style.typography.textAlign` support (dead attribute)                                                  | Drop it; add the `has-text-align-center` class via `className` (core CSS centers it)                                           |
| `style` has extra `overflow:hidden`                                                    | no core support                                                                                                          | Drop it; add a utility class (e.g. `stuv-clip`) via `className`, and add `.stuv-clip{overflow:hidden}` to the theme/header CSS |
| `class` missing `has-background`/`has-border-color`; border is `1px solid …` shorthand | shorthand can't be expressed by `border.{color,width}`; without `border-style` the border defaults to none → it vanishes | Let `save()` emit the class + longhand; set `style.border.style:"solid"`                                                       |
| `color` absent from attributes but the HTML has the background                         | `color` was written as a SIBLING of `style` in the JSON                                                                  | Move it inside `style.color`                                                                                                   |
| group contains raw `<a>`/`<div>` (not a block)                                         | `save()` renders InnerBlocks, not raw HTML                                                                               | Wrap the raw inner HTML in a `core/html` block                                                                                 |

After repairing attributes, regenerate canonical markup with `@wordpress/blocks` `serialize()`, then **gate the write**: re-run the validator (**0 invalid**) AND confirm no style declaration, class token, or visible text was lost.

**Red flag — STOP:** _"Just click Wiederherstellung / Attempt Block Recovery"_ or _"`serialize()` will clean it up."_ Both regenerate blocks from attributes and **silently drop anything the attributes don't carry** (`overflow`, undeclared inline styles, raw inner HTML) → visual regression. Repair the attributes FIRST, then regenerate, then re-validate.

## Safety Rules

No exceptions. Mandatory for every write.

1. **Backup first** — save content + status to `/tmp/wp_backup/<site>/` before any modification. Backups are namespaced per site, so the same page id on two sites can't collide.
2. **Preserve status** — echo back the exact `status` value fetched with `?context=edit`.
3. **Target surgically** — match by block type and the exact old text; never global search/replace across the whole page.
4. **Verify scope** — confirm only the targeted block changed. For a deliberate full-tree replacement, scope verification doesn't apply; use `save_structural` instead, which enforces a backup, `confirm=True`, and a balanced-markup check.
5. **Write page by page** — don't batch all pages into a single request.

Creating a resource (`create_resource`) has no prior state to back up; the equivalent safety is `find_by_slug` before creating (idempotency) and `delete_resource` to undo.

## Red Flags — STOP

These thoughts mean stop and follow the safety rules (restore from backup if you already wrote):

- "This change is too small to need a backup"
- "I'll verify scope after saving"
- "Omitting `status` won't change anything"
- "A global find/replace is faster"

An unskilled baseline run skipped the backup and POSTed without `status` — leaving a write it could not undo. Don't repeat it.

## Rollback

If something goes wrong, restore from the backup. Pass `--endpoint` for anything other than pages; the id may be a `theme//slug` template-part id:

```bash
python3 scripts/rollback.py 1
python3 scripts/rollback.py "twentytwentyfive//header" --endpoint template-parts
```

## Common Mistakes

| Mistake                                                     | Why It Happens                                                                               | Fix                                                                                                                                           |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Corrupted nested blocks                                     | Regex greedily matched across group/column boundaries                                        | Only edit leaf blocks; ask for nested changes                                                                                                 |
| `old_text matches N blocks` error                           | Same snippet appears in several blocks                                                       | Pass a longer, unique `old_text`                                                                                                              |
| Auth returns 401                                            | SSO plugin blocks normal passwords                                                           | Create an Application Password                                                                                                                |
| Changes not visible                                         | Browser/CDN cache                                                                            | Hard-refresh or clear cache                                                                                                                   |
| "Ungültiger Inhalt" / Attempt Block Recovery on many blocks | Stored HTML ≠ what the block's `save()` regenerates (hand-authored/migrated markup)          | Get ground truth with `validate_blocks.cjs`; fix losslessly per "Block validation errors". Don't click recovery — it drops undeclared styling |
| Front-end page URL 404s after editing                       | Site uses plain permalinks — pretty URLs (`/page/`) don't resolve                            | View via `/?pagename=<slug>` (or `?p=<id>`)                                                                                                   |
| Page too narrow / section background not full-width         | Top-level section set `contentSize` but no `align` → clamped to theme content width (~645px) | `align:full` (or `wide`) on the section; set `contentSize` on a nested constrained group. See `references/block-theme-layout.md`              |
| Background/border colour silently missing                   | Guessed a theme palette slug (`base-2`, `contrast-2`) that doesn't exist                     | Verify slugs against the theme, or inline the colour via `style.color`                                                                        |
| Broken placeholder images                                   | `via.placeholder.com` is defunct (dead DNS)                                                  | Use `placehold.co`                                                                                                                            |

## Output Format

- **Audits:** table with page title, block type, issue, current vs expected.
- **Edits:** per-page confirmation like `Home: 1 paragraph updated`.
- **Rollbacks:** list of restored pages.
- Always report skipped pages and why.
