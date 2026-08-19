---
name: improving-code
description: Use when asked to refactor, clean up, simplify, dedupe, or improve code quality anywhere in the StuV repo — Gutenberg block HTML, component CSS, design tokens, data files, or tools scripts. Covers "make this higher quality", "reduce duplication", "refactor this stylesheet/section".
---

# Improving Code (StuV repo)

## Overview

This repo holds WordPress block HTML, CSS, and design tokens deployed via REST API to a live Twenty Twenty-Five site. "Higher quality" means **less duplication, correct reuse of existing abstractions, and valid Gutenberg blocks**. Every change must be a verified no-op on deployed content (or a deliberate, stated improvement).

**Read `AGENTS.md` first** — it is the source of truth for conventions. This skill is the _procedure_ for applying them.

## The Loop

1. **Baseline.** Capture the affected page(s) as-is (live view or local file state) before touching anything.
2. **Find the real duplication.** Grep for repeated markup/rules/patterns; identify the existing abstraction that already covers it.
3. **Reuse, don't invent.** Extract to an existing mechanism (existing CSS class, existing section structure), not a new one.
4. **Validate blocks.** Run the `blockcheck` validator from the `wordpress-default-editor` skill against changed block HTML. A clean edit must not introduce validation errors.
5. **Verify no-op.** Deploy dry-run, review diffs; any markup/visual difference must be intentional and explained.
6. **Report.** State the line/rule reduction and verification result. Commit only if asked.

## Where quality problems actually live

| Symptom                                      | Idiomatic fix                                                                                                                                     | Reference in AGENTS.md               |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| Same block HTML written 2+ times             | Copy from the existing deployed occurrence directly — deployed content is the single source of truth, no separate template dir                    | Layout                               |
| Repeated CSS rules across sections           | Reuse existing `.stuv-*` component class from `data/styles/component.css`                                                                         | Layout                               |
| Magic values (colors, sizes, spacing) in CSS | Tokens in `data/global-styles.json` (palette, typography, layout widths)                                                                          | Layout                               |
| Magic values (colors, sizes) in inline HTML  | Use Gutenberg native controls (`style.color.text`, `style.spacing.*`) or CSS class instead of hardcoded `style=`                                  | Layout                               |
| Block flagged "ungültiger Inhalt"            | Match Gutenberg's canonical `save()` output; add `has-text-color` / `wp-element-button` as needed; validate with `blockcheck/validate_blocks.cjs` | Content Gotchas — Block validation   |
| `!important` reflex in CSS                   | Tighter selector instead                                                                                                                          | —                                    |
| URL slugs with umlauts                       | Keep ASCII digraphs (`ueber-uns` not `über-uns`)                                                                                                  | Content Gotchas — German orthography |
| Duplicated manifest entries                  | One source file, one manifest entry; sections join via filename order                                                                             | Layout                               |

## Verifying a refactor is a no-op

There is no build — changes are deployed live. Verification means:

1. **Block validation** (always run before deploying changed blocks):

```bash
SKILL=~/.claude/skills/wordpress-default-editor
node $SKILL/blockcheck/validate_blocks.cjs data/pages/<page>/<file>.html
```

2. **CSS diff** (for `component.css` changes) — normalize minified output to compare semantically:

```bash
sed 's/}/}\n/g' before.css > b.n; sed 's/}/}\n/g' data/styles/component.css > a.n; diff b.n a.n
```

3. **Dry-run deploy** to catch any manifest or structural issues before writing:

```bash
source .env
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json <target> --dry-run
```

4. **Visual review** — after deploying, check the affected page(s) at the live URL (`?pagename=<slug>`) in both light and dark mode.

## Guardrails

- Do **not** edit `data/global-styles.json` design tokens unless the change is explicitly requested — many components depend on palette values.
- Do **not** rename existing CSS classes (`.stuv-card`, `.stuv-icon-box`, `.stuv-button-*`) without updating every occurrence across all block HTML.
- Dark-mode `@media (prefers-color-scheme: dark)` overrides must stay in sync with their light-mode counterparts.
- Commit only when asked. No `Co-Authored-By` trailer. Keep commit messages in repo style.
- Don't churn the whole repo. Do the clearly-safe, highest-value dedup and verify it; list further candidates rather than mass-editing.
