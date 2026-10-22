# Common Block Patterns

Block markup is HTML wrapped in block comments.

## Heading

```html
<!-- wp:heading -->
<h1>Heading text</h1>
<!-- /wp:heading -->
```

## Paragraph

```html
<!-- wp:paragraph -->
<p>Paragraph text</p>
<!-- /wp:paragraph -->
```

## Button (inside buttons wrapper)

```html
<!-- wp:buttons -->
<div class="wp-block-buttons">
  <!-- wp:button -->
  <a class="wp-block-button__link wp-element-button">Button text</a>
  <!-- /wp:button -->
</div>
<!-- /wp:buttons -->
```

## Image

```html
<!-- wp:image {"id":5,"sizeSlug":"large"} -->
<figure class="wp-block-image size-large">
  <img src="https://example.com/image.jpg" alt="" />
</figure>
<!-- /wp:image -->
```

## Regex Notes

Match a leaf block with `re.DOTALL`:

```python
re.compile(r'<!-- wp:paragraph(\s[^>]*)? -->(.*?)<!-- /wp:paragraph -->', re.DOTALL)
```

Do not use this regex across nested containers (columns, groups). For nested blocks, ask for human review.

## Nested containers (structural writes only)

These wrap other blocks, so they can't be edited with `update_block_text`. Author them as full markup and write with `save_structural`. Attributes live as JSON in the opening comment; a block with no inner blocks self-closes (`/-->`).

### Group

```html
<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group">
  <!-- wp:paragraph -->
  <p>Inner content</p>
  <!-- /wp:paragraph -->
</div>
<!-- /wp:group -->
```

### Cover (hero)

```html
<!-- wp:cover {"dimRatio":70,"align":"full"} -->
<div class="wp-block-cover alignfull">
  <span
    aria-hidden="true"
    class="wp-block-cover__background has-background-dim"
  ></span>
  <div class="wp-block-cover__inner-container">
    <!-- wp:heading -->
    <h2 class="wp-block-heading">Title</h2>
    <!-- /wp:heading -->
  </div>
</div>
<!-- /wp:cover -->
```

### Buttons (wrapper)

```html
<!-- wp:buttons -->
<div class="wp-block-buttons">
  <!-- wp:button -->
  <a class="wp-block-button__link wp-element-button">Button text</a>
  <!-- /wp:button -->
</div>
<!-- /wp:buttons -->
```

### Details (accordion)

```html
<!-- wp:details -->
<details class="wp-block-details">
  <summary>Summary</summary>
  <!-- wp:paragraph -->
  <p>Revealed content</p>
  <!-- /wp:paragraph -->
</details>
<!-- /wp:details -->
```

### Self-closing block (no inner blocks)

```html
<!-- wp:site-title /-->
```

`assert_balanced_blocks` checks that every non-self-closing open has a matching close and that they nest in order; run it (or `save_structural`, which calls it) before writing.
