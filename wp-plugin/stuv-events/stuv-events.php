<?php
/**
 * Plugin Name: StuV Events
 * Description: Zeigt die nächsten Termine aus dem öffentlichen StuV-Google-Kalender als Liste auf der Website. Der Server holt den Kalender, Besucher laden nichts von Google. ACHTUNG: Wird dieses Plugin deaktiviert, verschwindet die Terminliste auf Startseite und Events-Seite. Quellcode: im Repository dieser Website (Verzeichnis wp-plugin/)
 * Version: 1.0.0
 * Requires PHP: 8.0
 * Author: StuV DHBW Heidenheim
 */

if (!defined('ABSPATH')) {
    exit;
}

require_once __DIR__ . '/inc/ics.php';

define('STUV_EVENTS_VERSION', '1.0.0'); // keep in sync with the header Version above; it cache-busts assets/events.js
define('STUV_EVENTS_FEED', 'https://calendar.google.com/calendar/ical/c_05fa202a6d427f41057993d22dba02b7a229645cdd29f50deb7297c30d2c40a0%40group.calendar.google.com/public/basic.ics');
define('STUV_EVENTS_TTL', 30 * MINUTE_IN_SECONDS);
define('STUV_EVENTS_LOCK_TTL', 60);
define('STUV_EVENTS_DAYS', 120);   // how far ahead the list looks
define('STUV_EVENTS_MAX', 40);     // occurrences in the payload
define('STUV_EVENTS_MAX_BYTES', 2 * 1024 * 1024);

/**
 * The upcoming occurrences, served stale-first with a stampede lock.
 *
 * Same soft-TTL design as stuv-mensa: the _stale option is the only payload
 * store, a value-less transient marks it fresh, and while one request
 * refreshes an expired store the others get the old copy. On a failed fetch
 * the old copy is served; events.js drops what has ended in the meantime.
 * Returns null only when Google is unreachable AND nothing was ever cached.
 */
function stuv_events_payload(): ?array {
    $store = get_option('stuv_events_payload_stale');
    $fresh = get_transient('stuv_events_fresh') !== false;
    $lock  = get_transient('stuv_events_refresh_lock') !== false;
    if (is_array($store) && ($fresh || $lock)) {
        return $store;
    }

    // A warm fetch means no lock is held: take it so others serve stale.
    if (is_array($store)) {
        set_transient('stuv_events_refresh_lock', 1, STUV_EVENTS_LOCK_TTL);
    }

    $response = wp_remote_get(STUV_EVENTS_FEED, [
        'timeout'             => 8,
        'limit_response_size' => STUV_EVENTS_MAX_BYTES,
        'headers'             => ['Accept' => 'text/calendar'],
    ]);
    $body = is_wp_error($response) || 200 !== wp_remote_retrieve_response_code($response)
        ? ''
        : wp_remote_retrieve_body($response);
    if (!str_contains($body, 'BEGIN:VCALENDAR')) {
        return is_array($store) ? $store : null;
    }

    $payload = ['events' => stuv_events_build(
        $body,
        new DateTimeImmutable('now', stuv_events_tz()),
        STUV_EVENTS_DAYS,
        STUV_EVENTS_MAX
    )];

    update_option('stuv_events_payload_stale', $payload, false);
    set_transient('stuv_events_fresh', 1, STUV_EVENTS_TTL);
    delete_transient('stuv_events_refresh_lock');
    return $payload;
}

add_action('rest_api_init', function (): void {
    register_rest_route('stuv/v1', '/events', [
        'methods'             => 'GET',
        'permission_callback' => '__return_true', // public, read-only
        'callback'            => fn() => stuv_events_payload()
            ?? new WP_Error('stuv_events_unavailable', 'Termine nicht verfügbar', ['status' => 503]),
    ]);
});

/**
 * Enqueue the list script only where a list is, keyed on the marker attribute
 * in the block markup rather than a page id.
 */
add_action('wp_enqueue_scripts', function (): void {
    $post = get_post();
    if (!is_singular() || !$post || !str_contains($post->post_content, 'data-stuv-events')) {
        return;
    }

    wp_enqueue_script(
        'stuv-events',
        plugins_url('assets/events.js', __FILE__),
        [],
        STUV_EVENTS_VERSION,
        true
    );

    // rest_url() tracks /wp-json/ and the ?rest_route= fallback alike.
    wp_localize_script('stuv-events', 'stuvEventsConfig', [
        'endpoint' => rest_url('stuv/v1/events'),
    ]);
});
