# Green Phase Notes (skill loaded)

All three eval scenarios were run by fresh subagents that loaded and followed the
`wordpress-default-editor` skill. Each was a sonnet-class agent — the same calibre as
the RED baseline — so the difference in behavior is attributable to the skill, not the model.

## check_eval.py (cumulative server log)

```json
{
  "used_basic_auth": true,
  "fetched_with_context_edit": true,
  "posted_content": true,
  "posted_status": true
}
exit=0
```

`posted_status` flipped from **false** (baseline) to **true**: every write echoed the
fetched `status`.

## Per-scenario results

| Scenario        | Result                                           | Status handling     | Scope                        |
| --------------- | ------------------------------------------------ | ------------------- | ---------------------------- |
| change-heading  | `<h1>` → "Welcome to Example Co"                 | publish preserved   | only heading block changed   |
| fix-placeholder | paragraph → "We build great things for the web." | publish preserved   | only paragraph block changed |
| preserve-status | page 2 paragraph → "Updated draft copy."         | **draft preserved** | only paragraph block changed |

Final page 1 still contains its untouched `wp:buttons` and `wp:image` blocks — the
surgical edits did not disturb neighboring or nested markup.

## Gaps closed vs. baseline

1. **Status echo** — baseline POSTed `{"content": ...}` only; every skilled run POSTed
   `{"content": ..., "status": ...}` with the exact fetched status. The draft page stayed a draft.
2. **Backup first** — each run wrote `/tmp/wp_backup/{id}_original.txt` and `{id}_status.txt`
   before its write.
3. **Scope verification** — each run called `verify_only_text_changed(...)` and only
   proceeded on PASS.

## Observed rationalizations

None. All three subagents performed backup → modify → verify → save-with-status without
shortcuts. No new loopholes surfaced that the existing Safety Rules and helper guards
(`_is_leaf_block`, no-op rejection, attribute-change rejection) do not already cover.
