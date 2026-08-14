<?php
/**
 * Uninstall handler.
 *
 * Deliberately deletes NOTHING — no post meta, no options.
 *
 * "Plugin löschen" sits one click next to "Deaktivieren", and the update
 * dialog ("vorhandene Version ersetzen?") invites deleting instead of
 * updating. Losing the eight hand-written descriptions for that would be a
 * bad trade. The data is small (a few rows in wp_postmeta, one option),
 * completely inert without the plugin, and expensive to reproduce — it is
 * prose, not a cache. A cache or a transient would be the counterexample;
 * this plugin has neither.
 *
 * The file still exists because its absence looks like an oversight and the
 * next person would add a delete loop. If the data ever has to go, remove the
 * option and the three `_stuv_seo_*` post-meta keys by hand.
 */

if (!defined('WP_UNINSTALL_PLUGIN')) {
    exit;
}
