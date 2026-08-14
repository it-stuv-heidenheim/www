<?php
/**
 * Pure helper: resolve a 404 request path against the old-slug redirect map.
 *
 * NO WordPress dependencies may be added to this file — it is unit-tested with
 * the plain `php` CLI (wp-plugin/tests/test_seo_routes.php).
 */

/**
 * Look up a request path in a redirect map.
 *
 * Normalization: the query string is dropped, case does not matter, and a
 * leading or trailing slash does not change the hit — so `/Campus?x=1` hits
 * the same entry as `campus/`. Map keys and the request are normalized the
 * same way before comparison.
 *
 * Self-protection: an entry that points at itself (e.g. the path itself after
 * normalization) resolves to null instead of an endless redirect loop.
 * Unknown paths resolve to null and the caller keeps the 404.
 *
 * @param array<string, string> $map source path => target URL.
 */
function stuv_seo_redirect_target(string $path, array $map): ?string {
    $key = stuv_seo_normalize_path($path);

    $normalized = [];
    foreach ($map as $from => $to) {
        $normalized[stuv_seo_normalize_path((string) $from)] = $to;
    }

    if (!isset($normalized[$key])) {
        return null;
    }

    $target = $normalized[$key];

    if (stuv_seo_normalize_path($target) === $key) {
        return null;
    }

    return $target;
}

/**
 * A comparable form of a URL or path: just the path, lower-cased, slashes
 * trimmed, always a single leading and trailing slash (or '/' for the root).
 */
function stuv_seo_normalize_path(string $path): string {
    $path = (string) parse_url($path, PHP_URL_PATH);
    if ('' === $path) {
        return '/';
    }

    $trimmed = trim(strtolower($path), '/');
    if ('' === $trimmed) {
        return '/';
    }

    return '/' . $trimmed . '/';
}
