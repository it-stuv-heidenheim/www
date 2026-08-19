<?php
/**
 * Pure cache-decision helpers for the StuV Mensa widget.
 *
 * NO WordPress dependencies — unit-tested with the plain `php` CLI
 * (wp-plugin/tests/test_cache.php).
 */

if (!defined('STUV_MENSA_IMAGE_MAX_BYTES')) {
    define('STUV_MENSA_IMAGE_MAX_BYTES', 2 * 1024 * 1024); // 2 MB
}

/**
 * Decide whether to fetch a fresh payload or serve what we already have.
 *
 * Returns one of:
 *   'serve'       — payload is fresh, serve the store
 *   'serve_stale' — another worker is already fetching; serve what we have
 *   'fetch'       — freshness expired, fetch upstream
 */
function stuv_mensa_payload_decision(
    bool $fresh,
    bool $lock_held,
    bool $store_present
): string {
    if (!$store_present) {
        return 'fetch'; // cold cache — never block first-ever visitors
    }
    if ($fresh) {
        return 'serve';
    }
    if ($lock_held) {
        return 'serve_stale';
    }
    return 'fetch';
}

/**
 * The Content-Type a proxied upstream image may be served with.
 *
 * The image route echoes upstream bytes back from THIS site's origin, so the
 * type has to be constrained on the way out and not merely at cache time: a
 * text/html body from a hostile or compromised upstream would otherwise run as
 * same-origin script. image/svg+xml is excluded despite being image/* for the
 * same reason — an SVG navigated to directly executes its own script, and
 * `X-Content-Type-Options: nosniff` does not prevent that; the upstream only
 * ever serves photographs. Anything unrecognised degrades to an inert
 * octet-stream rather than being rejected, so an odd-but-harmless upstream
 * type costs a broken thumbnail instead of a blank widget.
 */
function stuv_mensa_safe_image_type(string $type): string {
    $bare = strtolower(trim(explode(';', $type)[0]));

    if (!str_starts_with($bare, 'image/')) {
        return 'application/octet-stream';
    }
    if ($bare === 'image/svg+xml' || $bare === 'image/svg') {
        return 'application/octet-stream';
    }

    return $bare;
}

/**
 * Guard against caching non-image or oversized responses.
 *
 * Error pages, HTML bodies, truncated and empty responses are never cached —
 * a bad fetch costs one request, not 30 days of wrong bytes. Shares its notion
 * of "an image" with stuv_mensa_safe_image_type() so the cache can never hold
 * bytes the serving path would refuse to label as their own type.
 */
function stuv_mensa_image_cacheable(
    int $code,
    string $type,
    string $body
): bool {
    return $code === 200
        && stuv_mensa_safe_image_type($type) !== 'application/octet-stream'
        && $body !== ''
        && strlen($body) <= STUV_MENSA_IMAGE_MAX_BYTES;
}
