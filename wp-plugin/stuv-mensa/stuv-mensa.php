<?php
/**
 * Plugin Name: StuV Mensa
 * Description: Liefert den Speiseplan der Mensa Heidenheim (api.dhbw.app) same-origin an die Website. ACHTUNG: Wird dieses Plugin deaktiviert, verschwindet der Speiseplan auf der Seite "Studentenleben". Quellcode: im Repository dieser Website (Verzeichnis wp-plugin/)
 * Version: 1.2.0
 * Requires PHP: 8.0
 * Author: StuV DHBW Heidenheim
 */

if (!defined('ABSPATH')) {
    exit;
}

require_once __DIR__ . '/inc/normalize.php';
require_once __DIR__ . '/inc/cache.php';

define('STUV_MENSA_VERSION', '1.2.0'); // keep in sync with the header Version above; it cache-busts assets/mensa.js
define('STUV_MENSA_TTL', 30 * MINUTE_IN_SECONDS);
define('STUV_MENSA_LOCK_TTL', 60); // stampede lock expires in 60 s
define('STUV_MENSA_IMAGE_TTL', 30 * DAY_IN_SECONDS);

/**
 * The normalized payload, served-stale-first with a stampede lock.
 *
 * Soft-TTL design: the _stale option is the single payload store; a separate
 * value-less marker transient records freshness. When the marker expires, the
 * first request fetches upstream while others are served the stale copy. A
 * 60-second lock bounds concurrent fetches during the refresh window.
 *
 * On upstream failure, the stale copy is served. Returns null only when
 * upstream is down AND nothing was ever cached.
 */
function stuv_mensa_payload(): ?array {
    $store     = get_option('stuv_mensa_payload_stale');
    $fresh     = get_transient('stuv_mensa_fresh');
    $lock_held = get_transient('stuv_mensa_refresh_lock') !== false;

    $decision = stuv_mensa_payload_decision(
        $fresh !== false,
        $lock_held,
        is_array($store)
    );

    if ($decision === 'serve') {
        return $store;
    }

    if ($decision === 'serve_stale') {
        return $store;
    }

    // 'fetch'
    if (!$lock_held && is_array($store)) {
        set_transient('stuv_mensa_refresh_lock', 1, STUV_MENSA_LOCK_TTL);
    }

    $response = wp_remote_get(STUV_MENSA_UPSTREAM, [
        'timeout' => 8,
        'headers' => ['Accept' => 'application/json'],
    ]);

    if (is_wp_error($response) || 200 !== wp_remote_retrieve_response_code($response)) {
        return is_array($store) ? $store : null;
    }

    $upstream = json_decode(wp_remote_retrieve_body($response), true);
    if (!is_array($upstream)) {
        return is_array($store) ? $store : null;
    }

    $payload = stuv_mensa_normalize(
        $upstream,
        (new DateTimeImmutable('now', new DateTimeZone('Europe/Berlin')))->format('Y-m-d'),
        rest_url('stuv/v1/mensa/image/')
    );

    update_option('stuv_mensa_payload_stale', $payload, false);
    set_transient('stuv_mensa_fresh', 1, STUV_MENSA_TTL);
    delete_transient('stuv_mensa_refresh_lock');
    return $payload;
}

add_action('rest_api_init', function (): void {
    register_rest_route('stuv/v1', '/mensa', [
        'methods'             => 'GET',
        'permission_callback' => '__return_true', // public, read-only
        'callback'            => function () {
            $payload = stuv_mensa_payload();
            if (null === $payload) {
                return new WP_Error('stuv_mensa_unavailable', 'Speiseplan nicht verfügbar', ['status' => 503]);
            }
            return rest_ensure_response($payload);
        },
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
 * Stream a meal image from upstream so visitor IPs never reach api.dhbw.app.
 *
 * Images are cached in per-id transients for 30 days (base64-encoded, because
 * wp_options.option_value is utf8mb4 text and raw binary does not survive the
 * charset round-trip).
 *
 * SECURITY: only ids present in the current cached payload are served. Dropping
 * this check turns the route into an open proxy.
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
            // Re-checked on read, not trusted from the cache: a transient written
            // by an older build predates the guard.
            header('Content-Type: ' . stuv_mensa_safe_image_type($cached['type']));
            header('X-Content-Type-Options: nosniff');
            header('Content-Length: ' . strlen($body));
            header('Cache-Control: public, max-age=2592000, immutable');
            echo $body;
            exit;
        }
        delete_transient($transient);
    }

    $response = wp_remote_get(stuv_mensa_upstream_image_url($id), ['timeout' => 8]);
    if (is_wp_error($response) || 200 !== wp_remote_retrieve_response_code($response)) {
        return new WP_Error('stuv_mensa_image_failed', 'Bild nicht abrufbar', ['status' => 502]);
    }

    $body = wp_remote_retrieve_body($response);
    $type = wp_remote_retrieve_header($response, 'content-type') ?: 'image/webp';

    if (stuv_mensa_image_cacheable(200, $type, $body)) {
        $encoded = base64_encode($body);
        set_transient($transient, ['type' => $type, 'body' => $encoded], STUV_MENSA_IMAGE_TTL);
    }

    header('Content-Type: ' . stuv_mensa_safe_image_type($type));
    header('X-Content-Type-Options: nosniff');
    header('Content-Length: ' . strlen($body));
    header('Cache-Control: public, max-age=2592000, immutable');
    echo $body;
    exit;
}

/**
 * Enqueue the widget script only where the widget actually is.
 *
 * Keyed on the marker attribute in the block markup rather than a page id, so
 * moving the widget to another page needs no change here.
 */
add_action('wp_enqueue_scripts', function (): void {
    if (!is_singular()) {
        return;
    }

    $post = get_post();
    if (!$post || !str_contains($post->post_content, 'data-stuv-mensa')) {
        return;
    }

    wp_enqueue_script(
        'stuv-mensa',
        plugins_url('assets/mensa.js', __FILE__),
        [],
        STUV_MENSA_VERSION,
        true
    );

    // Always let rest_url() resolve the REST root — the script must never build
    // this URL itself. The staging host serves /wp-json/ under Beitragsname
    // permalinks, but the beta host needed index.php/wp-json and a host with a
    // broken rewrite falls back to ?rest_route=; rest_url() tracks all three.
    wp_localize_script('stuv-mensa', 'stuvMensaConfig', [
        'endpoint' => rest_url('stuv/v1/mensa'),
    ]);
});
