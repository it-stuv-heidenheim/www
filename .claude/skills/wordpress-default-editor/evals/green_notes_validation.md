# Green Notes — block-validation scenario (GREEN phase)

Same scenario as `baseline_notes_validation.md`, run by a fresh subagent of the same
calibre, now with the SKILL.md "Block validation errors" section + the bundled
`scripts/blockcheck/validate_blocks.cjs` validator present.

## Gaps closed vs. baseline

1. **Ground truth was instant, not rebuilt.** The agent ran the bundled validator
   straight away instead of installing packages and writing a jsdom harness from
   scratch. Cost dropped from the baseline's ~37 tool calls / ~597s / ~80k tokens to
   **12 tool calls / ~169s / ~48k tokens**. It also followed the version-match note
   (checked the WP 7.0 `<meta name="generator">`).

2. **Remediation was lossless — no block recovery.** For every cause it gave a
   fix that preserves visuals and matches the skill's patterns:
   - heading → add `"level":3` (inline styles already declared);
   - group `text-align:center` → drop `typography.textAlign`, add `has-text-align-center` via `className`;
   - border → set `style.border.style:"solid"` + longhand + `has-border-color` (it independently noted that without `border-style` "the recovered border would default to none and vanish visually");
   - `overflow:hidden` → move to a `stuv-clip` className backed by CSS.
     It explicitly did **not** recommend "Attempt block recovery" (the baseline did, and
     wrongly claimed it renders identically).

3. **Adopted the write gate.** It stated the definitive check is to "re-run the
   validator to 0 invalid … before any write" and re-validated each corrected fragment
   to 0 invalid to prove completeness.

## Observed rationalizations

None. The agent did not argue for recovery or any lossy shortcut. No new loopholes
surfaced, so no REFACTOR iteration was needed.

## Conclusion

The section + bundled validator turn an expensive, partly-wrong baseline into a fast,
complete, look-preserving diagnosis. GREEN achieved on both measured dimensions:
validator used immediately, and remediation preserves visuals.
