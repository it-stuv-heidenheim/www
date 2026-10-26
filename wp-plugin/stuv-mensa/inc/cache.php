<?php
/** Pure cache helpers for the Mensa widget. No WordPress dependencies (wp-plugin/tests/test_cache.php). */

const STUV_MENSA_IMAGE_MAX_BYTES = 2 * 1024 * 1024;

/** True if a request should fetch: always on a cold cache, on a warm one once stale and unlocked. */
function stuv_mensa_should_fetch(bool $fresh, bool $lock_held, bool $store_present): bool {
    return !$store_present || (!$fresh && !$lock_held);
}

/**
 * The Content-Type a proxied image is served with. The bytes come from this origin, so
 * text/html and image/svg+xml would run as same-origin script; unknown types become
 * octet-stream, so the worst case is a broken thumbnail.
 */
function stuv_mensa_safe_image_type(string $type): string {
    $bare = strtolower(trim(explode(';', $type)[0]));

    if (!str_starts_with($bare, 'image/') || $bare === 'image/svg+xml' || $bare === 'image/svg') {
        return 'application/octet-stream';
    }
    return $bare;
}

/** Never cache error pages, non-images, truncated or oversized bodies (same notion of image as above). */
function stuv_mensa_image_cacheable(string $type, string $body): bool {
    return stuv_mensa_safe_image_type($type) !== 'application/octet-stream'
        && $body !== ''
        && strlen($body) <= STUV_MENSA_IMAGE_MAX_BYTES;
}
