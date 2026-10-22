# Block Theme Layout (structural writes)

Use when authoring full page or section markup for `save_structural` on a **block theme** (Twenty Twenty-X and most modern themes). This is the knowledge that turns a Next.js / Tailwind design into block markup that actually fills the page.

## The trap: `contentSize` is not width

A page's `core/post-content` is a **constrained** layout capped at the theme's _content width_ (Twenty Twenty-Five ≈ **645px**; wide ≈ 1340px). A top-level block with **no alignment is clamped to that content width** — _even if you set a larger `contentSize` on it_, because `contentSize` sizes a group's **children**, not the group itself.

Symptom: full-width section backgrounds render as a narrow centre strip and the page "looks too narrow." This is the #1 structural-rebuild bug.

```html
<!-- WRONG: section clamps to ~645px; the grey background never goes full width -->
<!-- wp:group {"tagName":"section","style":{"color":{"background":"#f3f3f3"}},"layout":{"type":"constrained","contentSize":"80rem"}} -->
```

A block's own width comes from its **alignment**, relative to its constrained parent:

| Alignment    | Class       | Width                  | Use for             |
| ------------ | ----------- | ---------------------- | ------------------- |
| (none)       | —           | content width (~645px) | body-text columns   |
| `align:wide` | `alignwide` | wide width (~1340px)   | wide media rows     |
| `align:full` | `alignfull` | viewport, edge to edge | section bands, hero |

## The section pattern: full-bleed band + centred column

To reproduce `<section className="bg-muted/30 py-20"><div className="mx-auto max-w-7xl px-4 lg:px-8">…</div></section>`:

- **OUTER** group: `align:full` + the background + vertical padding → the edge-to-edge band.
- **INNER** constrained group: `contentSize` = your container width + horizontal padding → the centred readable column.

```html
<!-- wp:group {"tagName":"section","align":"full","style":{"color":{"background":"rgba(0,0,0,0.03)"},"spacing":{"padding":{"top":"5rem","bottom":"5rem"}}},"layout":{"type":"default"}} -->
<section
  class="wp-block-group alignfull has-background"
  style="background-color:rgba(0,0,0,0.03);padding-top:5rem;padding-bottom:5rem"
>
  <!-- wp:group {"layout":{"type":"constrained","contentSize":"80rem"},"style":{"spacing":{"padding":{"left":"1.5rem","right":"1.5rem"}}}} -->
  <div class="wp-block-group" style="padding-left:1.5rem;padding-right:1.5rem">
    <!-- heading, paragraph, wp:columns … -->
  </div>
  <!-- /wp:group -->
</section>
<!-- /wp:group -->
```

## Tailwind → block mapping

| Tailwind                                                                | Block                                                         |
| ----------------------------------------------------------------------- | ------------------------------------------------------------- |
| full-bleed section background                                           | OUTER group `align:full` carries the background               |
| `py-20`                                                                 | top/bottom padding on the OUTER group                         |
| `mx-auto max-w-7xl` (80rem) / `max-w-6xl` (72rem) / `max-w-3xl` (48rem) | INNER constrained group `contentSize` (centres automatically) |
| `px-4 lg:px-8`                                                          | left/right padding on the INNER group                         |

## Read the theme — don't guess

- **Width:** get the content/wide width from the rendered page's `:root { --wp--style--global--content-size: …; --wp--style--global--wide-size: …; }`, or from `GET /wp-json/wp/v2/global-styles/themes/<theme>`. Don't assume 645px.
- **Colours:** don't guess palette slugs (`base-2`, `contrast-2`, …) — they vary per theme and a wrong slug **silently drops the colour**. Use a verified slug, or inline the colour with `style.color.background` (as above).
- **Images:** point at a live host. `placehold.co` works; **`via.placeholder.com` is defunct** (DNS dead) — never author it.

## Fix the root cause: put the design system in global styles, not injected CSS

Per-section `contentSize` guessing and a `<style>` block full of `--my-*` vars are a symptom. The cure is to set the design system **once** in the active theme's _user_ global-styles record (theme.json shape) so widths and colours are global:

- `layout.contentSize` / `layout.wideSize` → kills the ~645px content-width trap site-wide; new sections inherit a sane width with no per-section guessing.
- `color.palette` as real slugs → blocks reference `var(--wp--preset--color--primary)` instead of guessing `base-2`/`contrast-2` (the silent-drop trap above disappears).
- `typography.fontFamilies`, `custom.*` (e.g. a radius token) → the rest of the tokens.

```python
import scripts.wp_block_api as wp

wp.apply_global_styles(
    settings_patch={
        "layout": {"contentSize": "80rem", "wideSize": "90rem"},
        "color": {"palette": [
            {"slug": "primary", "color": "#E2001A", "name": "Primary"},
            {"slug": "background", "color": "#fcfcfc", "name": "Background"},
        ]},
        "typography": {"fontFamilies": [
            {"fontFamily": "Inter, sans-serif", "slug": "inter", "name": "Inter"}
        ]},
        "custom": {"radius": "0.5rem"},   # -> var(--wp--custom--radius)
    },
    styles_patch={"typography": {"fontFamily": "var:preset|font-family|inter"}},
    confirm=True,   # JSON-backups the current record first; restore by POSTing it back
)
```

What you need to know:

- **Discovery, not guessing.** `apply_global_styles` finds the editable record via the active theme's `wp:user-global-styles` REST link (`discover_global_styles_id()`); the id is install-specific. Creating a record may fail, but updating the existing one works.
- **`custom` origin on read.** WordPress nests _user_ palette/font values under a `custom` key on read — `get_global_styles()["settings"]["color"]["palette"]["custom"]` is a list, not a list directly. Account for it when verifying.
- **`align:full` is still required per section.** Global widths fix the _default_ content width; they do **not** make a section full-bleed. Section bands still need `align:full` (see the band pattern above) — inherent to block themes.
- **Keep component CSS where it belongs.** theme.json/global styles hold tokens and block styles only. Arbitrary component classes (`.card`, `.icon-box`) stay in a template-part `<style>` block; source their light values _from_ the new presets (`--my-primary: var(--wp--preset--color--primary, #E2001A)`) so a dark-mode `@media` override still flips them.

## Pre-flight checklist (structural page/section writes)

- [ ] Every top-level section that should span the page has `align:full` (or `align:wide`) — not just a large `contentSize`.
- [ ] Background + vertical padding on the **full-width** wrapper; readable column is a **nested constrained** group with `contentSize` + horizontal padding.
- [ ] Content/wide widths and palette slugs verified against the theme, not guessed.
- [ ] Design system (widths, palette, type) set once in **global styles** (`apply_global_styles`), not re-guessed per section.
- [ ] Image hosts are live (`placehold.co`, not `via.placeholder.com`).
- [ ] Markup balanced (`save_structural` checks this).
