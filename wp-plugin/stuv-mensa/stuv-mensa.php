<?php
/**
 * Plugin Name: StuV Mensa
 * Description: Liefert den Speiseplan der Mensa Heidenheim (api.dhbw.app) same-origin an die Website. ACHTUNG: Wird dieses Plugin deaktiviert, verschwindet der Speiseplan auf der Seite "Studentenleben". Quellcode: im Repository dieser Website (Verzeichnis wp-plugin/)
 * Version: 1.2.2
 * Requires PHP: 8.0
 * Author: StuV DHBW Heidenheim
 */

if (!defined('ABSPATH')) {
    exit;
}

require_once __DIR__ . '/inc/normalize.php';
require_once __DIR__ . '/inc/cache.php';

define('STUV_MENSA_VERSION', '1.2.2'); // = header Version; cache-busts assets/mensa.js
define('STUV_MENSA_TTL', 30 * MINUTE_IN_SECONDS);
define('STUV_MENSA_LOCK_TTL', 60);
define('STUV_MENSA_IMAGE_TTL', 30 * DAY_IN_SECONDS);

/**
 * The normalized payload, stale-first: the _stale option is the only store, a value-less
 * transient marks it fresh, and a 60 s lock lets one request refresh while others get the
 * stale copy, also when upstream fails. Null only if nothing was ever cached.
 */
function stuv_mensa_payload(): ?array {
    $store = get_option('stuv_mensa_payload_stale');
    if (!stuv_mensa_should_fetch(
        get_transient('stuv_mensa_fresh') !== false,
        get_transient('stuv_mensa_refresh_lock') !== false,
        is_array($store)
    )) {
        return $store;
    }

    // A warm fetch means no lock is held: take it so others serve stale.
    if (is_array($store)) {
        set_transient('stuv_mensa_refresh_lock', 1, STUV_MENSA_LOCK_TTL);
    }

    $response = wp_remote_get(STUV_MENSA_UPSTREAM, [
        'timeout' => 8,
        'headers' => ['Accept' => 'application/json'],
    ]);

    $upstream = is_wp_error($response) || 200 !== wp_remote_retrieve_response_code($response)
        ? null
        : json_decode(wp_remote_retrieve_body($response), true);
    $payload = is_array($upstream) ? stuv_mensa_normalize(
        $upstream,
        (new DateTimeImmutable('now', new DateTimeZone('Europe/Berlin')))->format('Y-m-d'),
        rest_url('stuv/v1/mensa/image/')
    ) : null;
    if ($payload === null) {
        return is_array($store) ? $store : null;
    }

    update_option('stuv_mensa_payload_stale', $payload, false);
    set_transient('stuv_mensa_fresh', 1, STUV_MENSA_TTL);
    delete_transient('stuv_mensa_refresh_lock');
    return $payload;
}

add_action('rest_api_init', function (): void {
    register_rest_route('stuv/v1', '/mensa', [
        'methods'             => 'GET',
        'permission_callback' => '__return_true',
        'callback'            => fn() => stuv_mensa_payload()
            ?? new WP_Error('stuv_mensa_unavailable', 'Speiseplan nicht verfügbar', ['status' => 503]),
    ]);

    register_rest_route('stuv/v1', '/mensa/image/(?P<id>\d+)', [
        'methods'             => 'GET',
        'permission_callback' => '__return_true',
        'args'                => [
            'id' => ['validate_callback' => fn($v) => ctype_digit((string) $v)],
        ],
        'callback'            => 'stuv_mensa_image_route',
    ]);
});

/**
 * Proxy a meal image so visitor IPs never reach api.dhbw.app; cached 30 days as base64
 * (option_value is utf8mb4 text). SECURITY: only ids in the cached payload, or this is an open proxy.
 */
function stuv_mensa_image_route(WP_REST_Request $request) {
    $id      = (int) $request['id'];
    $payload = stuv_mensa_payload();

    if (null === $payload || !in_array($id, stuv_mensa_image_ids($payload), true)) {
        return new WP_Error('stuv_mensa_unknown_image', 'Unbekannte Bild-ID', ['status' => 404]);
    }

    $transient = 'stuv_mensa_img_' . $id;
    $cached    = get_transient($transient);
    if (is_array($cached) && isset($cached['type'], $cached['body'])) {
        $body = base64_decode($cached['body'], true);
        if ($body !== false) {
            stuv_mensa_send_image($cached['type'], $body);
        }
        delete_transient($transient);
    }

    $response = wp_remote_get(stuv_mensa_upstream_image_url($id), ['timeout' => 8]);
    if (is_wp_error($response) || 200 !== wp_remote_retrieve_response_code($response)) {
        return new WP_Error('stuv_mensa_image_failed', 'Bild nicht abrufbar', ['status' => 502]);
    }

    $body = wp_remote_retrieve_body($response);
    $type = wp_remote_retrieve_header($response, 'content-type') ?: 'image/webp';

    if (stuv_mensa_image_cacheable($type, $body)) {
        set_transient($transient, ['type' => $type, 'body' => base64_encode($body)], STUV_MENSA_IMAGE_TTL);
    }

    stuv_mensa_send_image($type, $body);
}

/** Emit an image response and stop; both arms of the route end here, so headers can't drift. */
function stuv_mensa_send_image(string $type, string $body): void {
    header('Content-Type: ' . stuv_mensa_safe_image_type($type));
    header('X-Content-Type-Options: nosniff');
    header('Content-Length: ' . strlen($body));
    header('Cache-Control: public, max-age=' . STUV_MENSA_IMAGE_TTL . ', immutable');
    echo $body;
    exit;
}

/** Enqueue the script only where the block markup carries the marker attribute. */
add_action('wp_enqueue_scripts', function (): void {
    $post = get_post();
    if (!is_singular() || !$post || !str_contains($post->post_content, 'data-stuv-mensa')) {
        return;
    }

    wp_enqueue_script(
        'stuv-mensa',
        plugins_url('assets/mensa.js', __FILE__),
        [],
        STUV_MENSA_VERSION,
        true
    );

    // rest_url() covers /wp-json/, index.php/wp-json and ?rest_route= alike.
    wp_localize_script('stuv-mensa', 'stuvMensaConfig', [
        'endpoint' => rest_url('stuv/v1/mensa'),
    ]);
});
