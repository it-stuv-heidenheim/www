# Baseline Subagent Notes (RED phase)

Scenario: `change-heading` — change the homepage `<h1>` from "Welcome to our site"
to "Welcome to Example Co" on the mock WordPress site, with **no skill loaded** and
no access to the helper scripts. Model: a capable general assistant (sonnet-class).

## What the baseline did right (by luck/knowledge, not by rule)

- Used HTTP **Basic Auth** with the application password.
- Fetched with **`?context=edit`** so it got raw block markup, not rendered HTML.
- Replaced **only the targeted text** ("Welcome to our site" → "Welcome to Example Co")
  and re-POSTed the full content, leaving the other blocks intact.

## What the baseline got wrong (the gaps the skill must close)

1. **Did not echo `status` on write.** The POST body contained only `"content"` —
   no `"status"`. `check_eval.py` reported `posted_status: false` (exit 1).
   On real WordPress, omitting `status` risks flipping a post's publish state in
   some editor/plugin flows. The skill's rule "always fetch and echo `status`"
   exists precisely to remove this gamble.

2. **Did not back up before writing.** No fresh `/tmp/wp_backup/` files were created
   for this run. The write was irreversible — there was no captured original content
   or status to roll back to.

3. **No scope verification.** It eyeballed the diff but ran no programmatic check that
   _only_ the intended block changed before committing the write.

## check_eval.py result for the baseline run

```json
{
  "used_basic_auth": true,
  "fetched_with_context_edit": true,
  "posted_content": true,
  "posted_status": false
}
exit=1
```

## Conclusion

A strong default assistant gets the easy parts right but skips the durability/safety
steps: **backup, status-echo, and scope verification.** The skill turns those from
"if the assistant happens to remember" into mandatory, scripted steps. The GREEN phase
(Task 11) must show `posted_status: true`, a backup written before the write, and
preserved status — especially on the draft page.
