<?php
/**
 * Pure cache-decision helpers for the StuV Mensa widget.
 *
 * NO WordPress dependencies: unit-tested with the plain `php` CLI
 * (wp-plugin/tests/test_cache.php).
 */

const STUV_MENSA_IMAGE_MAX_BYTES = 2 * 1024 * 1024; // 2 MB

/**
 * Whether to fetch upstream now rather than serve the store.
 *
 * A cold cache always fetches, so first-ever visitors are never blocked. A warm
 * one fetches only once the freshness marker has expired and no other worker
 * holds the refresh lock; everyone else is served the store, stale or not.
 */
function stuv_mensa_should_fetch(bool $fresh, bool $lock_held, bool $store_present): bool {
    return !$store_present || (!$fresh && !$lock_held);
}

/**
 * The Content-Type a proxied upstream image may be served with.
 *
 * The image route echoes upstream bytes back from THIS site's origin, so the
 * type has to be constrained on the way out and not merely at cache time: a
 * text/html body from a hostile or compromised upstream would otherwise run as
 * same-origin script. image/svg+xml is excluded despite being image/* for the
 * same reason: an SVG navigated to directly executes its own script, and
 * `X-Content-Type-Options: nosniff` does not prevent that; the upstream only
 * ever serves photographs. Anything unrecognised degrades to an inert
 * octet-stream rather than being rejected, so an odd-but-harmless upstream
 * type costs a broken thumbnail instead of a blank widget.
 */
function stuv_mensa_safe_image_type(string $type): string {
    $bare = strtolower(trim(explode(';', $type)[0]));

    if (!str_starts_with($bare, 'image/') || $bare === 'image/svg+xml' || $bare === 'image/svg') {
        return 'application/octet-stream';
    }
    return $bare;
}

/**
 * Guard against caching non-image or oversized 200 responses.
 *
 * Error pages, HTML bodies, truncated and empty responses are never cached, so
 * a bad fetch costs one request, not 30 days of wrong bytes. Shares its notion
 * of "an image" with stuv_mensa_safe_image_type() so the cache can never hold
 * bytes the serving path would refuse to label as their own type.
 */
function stuv_mensa_image_cacheable(string $type, string $body): bool {
    return stuv_mensa_safe_image_type($type) !== 'application/octet-stream'
        && $body !== ''
        && strlen($body) <= STUV_MENSA_IMAGE_MAX_BYTES;
}
