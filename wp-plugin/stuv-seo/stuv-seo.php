<?php
/**
 * Plugin Name: StuV SEO
 * Description: Liefert pro Seite eine Meta-Beschreibung, Open Graph, Twitter Card und strukturierte Daten (Organization, FAQPage). Staging bleibt über eine Konstante im Code auf noindex, dazu ein verstecktes 404-Weiterleitungsnetz für alte Slugs. ACHTUNG: Wird dieses Plugin deaktiviert, fehlen die Meta-Tags einfach — Seiten und Layout bleiben unverändert, bis auf zwei Folgen: Seiten mit gesetztem "Von Suchmaschinen ausschließen" werden wieder indexierbar und der Staging-Host würde in den Index gelangen (einen zweiten Riegel auf Server-Ebene gibt es derzeit nicht). Beschreibungen und Bilder werden in der Datenbank gespeichert, nie in dieser Datei. Quellcode: im Repository dieser Website (Verzeichnis wp-plugin/)
 * Version: 1.0.1
 * Requires PHP: 8.0
 * Author: StuV DHBW Heidenheim
 */

if (!defined('ABSPATH')) {
    exit;
}

define('STUV_SEO_VERSION', '1.0.1');

/**
 * This file, for plugins_url().
 *
 * Everything that builds an asset URL lives in inc/, and plugins_url() derives
 * the plugin folder from dirname(plugin_basename($file)) — passing __FILE__
 * from inc/admin.php therefore yields `stuv-seo/inc/assets/…`, a 404 that
 * nothing reports because a missing script just silently does nothing.
 */
define('STUV_SEO_FILE', __FILE__);

/**
 * The recommended maximum length of a meta description, in characters.
 *
 * One number for all three places that show it: the hint under the metabox
 * field, the live counter in assets/admin.js (which gets it from here, so the
 * JS carries no second value) and the red mark in the start checklist. It used
 * to be 155 in the metabox and 160 in the checklist, which promised a limit
 * that nothing enforced. Nothing is ever truncated at it — a longer text is a
 * signal to whoever wrote it, not a licence to cut their prose.
 */
const STUV_SEO_DESCRIPTION_LIMIT = 155;

/**
 * The hosts that may be indexed. Everything else is staging and gets noindex
 * plus a robots.txt that disallows everything. Decided by a constant, not a
 * database option, so that "staging is indexable" cannot be switched on by
 * accident in wp-admin — and the fail-closed direction holds on an unknown
 * host. Compared against the host of home_url(), never against
 * $_SERVER['HTTP_HOST'], which reflects the request.
 */
const STUV_SEO_PRODUCTION_HOSTS = [
    'stuv-heidenheim.de',
    'www.stuv-heidenheim.de',
];

function stuv_seo_is_production(): bool {
    $host = (string) wp_parse_url(home_url('/'), PHP_URL_HOST);

    return in_array($host, STUV_SEO_PRODUCTION_HOSTS, true);
}

require_once __DIR__ . '/inc/pure/tags.php';
require_once __DIR__ . '/inc/pure/faq.php';
require_once __DIR__ . '/inc/pure/routes.php';
require_once __DIR__ . '/inc/meta.php';
require_once __DIR__ . '/inc/head.php';
require_once __DIR__ . '/inc/jsonld.php';
require_once __DIR__ . '/inc/robots.php';
require_once __DIR__ . '/inc/redirects.php';

if (is_admin()) {
    require_once __DIR__ . '/inc/admin.php';
}
