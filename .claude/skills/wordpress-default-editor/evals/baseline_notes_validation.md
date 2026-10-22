# Baseline Notes — block-validation scenario (RED phase)

Scenario: `diagnose-invalid-blocks` — a page opened in the block editor shows
"Dieser Block enthält unerwarteten oder ungültigen Inhalt. Wiederherstellung versuchen"
on multiple blocks. The page's raw block markup is at
`/tmp/wpval_eval/page_with_invalid_blocks.html` (a real migrated page: 7 invalid
`core/heading`, 9 invalid `core/group`). Task: diagnose every root cause and give a
look-preserving fix. Skill loaded was the version WITHOUT the "Block validation errors"
section. Model: capable general assistant.

## What the baseline did right

- Recognized that validation = re-running each block's `save()` from its JSON
  attributes and diffing against the stored HTML.
- **Built the real Gutenberg validator from scratch** (`@wordpress/blocks` +
  `@wordpress/block-library` under jsdom) and got authoritative results: enumerated
  all 16 invalid blocks with exact `Expected …, saw …` messages, and the 4 underlying
  mismatch patterns. The diagnosis was correct and complete.

## What the baseline got wrong (the gaps the skill must close)

1. **Enormous, repeated cost.** Rebuilding the harness took ~10 minutes, 37 tool calls,
   ~80k tokens, and live debugging of jsdom globals. Every future run repeats this from
   zero. A weaker (sonnet-class) agent may not get there at all and will fall back to
   eyeballing the markup and guessing — exactly the failure mode that ships wrong fixes.

2. **Lossy / destructive remediation.** It recommended clicking **"Attempt block
   recovery"** (and re-saving) and asserted it "renders identically." This is FALSE for
   this page: recovery/`serialize()` regenerates each block from its attributes and
   therefore DROPS styling the attributes don't carry — `overflow:hidden` and the
   undeclared heading `font-size`/`font-weight`/`margin` — causing a visible regression.
   It also gave only vague CSS-relocation advice and never identified the lossless path:
   lift undeclared inline styles INTO the block attributes, set the heading `level`,
   convert unsupported props (`text-align`, `overflow`) to a className backed by CSS,
   move a misplaced `color` into `style`, and wrap raw inner HTML in a `core/html` block.

## Conclusion

Diagnosis is self-healing for a strong agent but expensive and unreliable; **remediation
is where the baseline actively fails** — it steers toward block recovery, which silently
loses styling. The skill must (a) bundle a ready validator so ground truth is one command,
and (b) document the lossless fix patterns and explicitly forbid naive recovery/regeneration
that drops undeclared styling. GREEN must show: validator used immediately (no rebuild),
and a fix that preserves visuals (no "Attempt block recovery").
