<?php
/**
 * 404 fallback for the old-slug redirect map.
 *
 * A pure 404 catch layer on template_redirect: it costs nothing on a normal
 * request and touches the meta layer nowhere. Deactivating the plugin brings
 * the 404s back — worse, not broken.
 *
 * The map ships empty. The old slugs have to be harvested from the Elementor
 * site before the DNS move (sitemap, menu structure, or its wp-admin page
 * list) — they are not invented here. Until then the mechanism stands ready.
 *
 * Shipped with 302 so a wrong entry cannot burn into browser caches; after
 * review with real slugs, switch to 301 in a commit of its own.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * source path (normalized) => target. Filled before the move.
 *
 * **Targets are root-relative paths, never absolute URLs.** Everything here is
 * validated with wp_validate_redirect(), which only passes the host of
 * home_url() — an absolute `https://stuv-heidenheim.de/…` entry would be
 * rejected on staging (and on production too if home ever ends up as `www.`),
 * so the whole map would quietly stop working on exactly the host it was
 * written for. A path has no host to get wrong.
 */
function stuv_seo_redirect_map(): array {
    return [
        // '/campus/'              => '/studentenleben/',
        // '/standort-heidenheim/' => '/ueber-uns/',
    ];
}

function stuv_seo_handle_redirects(): void {
    if (!is_404()) {
        return;
    }

    $path = (string) ($_SERVER['REQUEST_URI'] ?? '/');

    $target = stuv_seo_redirect_target($path, stuv_seo_redirect_map());
    if (null === $target) {
        return;
    }

    // Deliberately not wp_safe_redirect(): its fallback for a target on a
    // foreign host is admin_url(), so a bad entry would send visitors to
    // wp-admin — a worse answer than the 404 they came for. Validating by hand
    // with an empty fallback keeps the 404 instead.
    $validated = wp_validate_redirect($target, '');
    if ('' === $validated) {
        return;
    }

    wp_redirect($validated, 302);
    exit;
}
add_action('template_redirect', 'stuv_seo_handle_redirects');
