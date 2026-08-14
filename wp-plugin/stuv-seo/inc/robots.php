<?php
/**
 * Robots, sitemap and staging handling — everything through the wp_robots API
 * (the 5.7-era array filter), never through handwritten <meta> lines.
 *
 * Two independent "noindex" reasons:
 *
 *  1. A page flag: _stuv_seo_noindex (set in the SEO metabox) makes that one
 *     page noindex, follow. The page ALSO drops out of the sitemap — noindex
 *     alone would leave it in wp-sitemap.xml, a contradictory signal, and
 *     nobody thinks of the second step when they tick the box. That second
 *     half lives in the wp_sitemaps_posts_query_args filter below.
 *
 *  2. A non-production host: fail-closed noindex for the whole site, plus the
 *     sitemap switched off and a robots.txt that disallows everything. This
 *     inverts the plugin's own deactivation: switching the plugin off makes
 *     staging indexable again. As of 2026-08-06 there is no second lock — the
 *     nginx X-Robots-Tag on dev is planned but not configured (checked: no
 *     such header on /, /robots.txt or /wp-sitemap.xml), so until it exists
 *     this file is the only thing keeping staging out of the index. The
 *     setting under Einstellungen → Lesen keeps working but no longer carries
 *     the site.
 *
 * Setting only $robots['noindex'] (not wp_robots_no_robots(), which also sets
 * nofollow) is deliberate: the audit asks for `noindex, follow` on /docs/.
 *
 * Every host check runs inside a filter callback, never at load time: this file
 * is required from the plugin bootstrap, long before `init`, and home_url() at
 * that point cannot see a filter on `home_url`/`option_home` registered later.
 */

if (!defined('ABSPATH')) {
    exit;
}

function stuv_seo_sitemaps_enabled(bool $enabled): bool {
    return $enabled && stuv_seo_is_production();
}
add_filter('wp_sitemaps_enabled', 'stuv_seo_sitemaps_enabled');

function stuv_seo_wp_robots(array $robots): array {
    if (!stuv_seo_is_production()) {
        $robots['noindex'] = true;

        return $robots;
    }

    if (is_singular('page') && stuv_seo_get_noindex(get_queried_object_id())) {
        $robots['noindex'] = true;
    }

    return $robots;
}
add_filter('wp_robots', 'stuv_seo_wp_robots');

function stuv_seo_robots_txt(string $output): string {
    if (stuv_seo_is_production()) {
        return $output;
    }

    // Without shell access this is the only maintainable place for the one
    // rule that matters on staging. On production the Core default is left
    // untouched (including the Sitemap: line Core adds itself).
    return "User-agent: *\nDisallow: /\n";
}
add_filter('robots_txt', 'stuv_seo_robots_txt');

/**
 * Keep pages flagged noindex out of the posts sitemap.
 */
function stuv_seo_sitemap_posts_query_args(array $args, string $post_type): array {
    if ('page' !== $post_type) {
        return $args;
    }

    $noindexed = get_posts([
        'post_type'      => 'page',
        'post_status'    => 'publish',
        'fields'         => 'ids',
        'posts_per_page' => -1,
        'meta_key'       => '_stuv_seo_noindex',
        'meta_value'     => '1',
        'no_found_rows'  => true,
    ]);

    if ($noindexed) {
        $args['post__not_in'] = array_merge($args['post__not_in'] ?? [], $noindexed);
    }

    return $args;
}
add_filter('wp_sitemaps_posts_query_args', 'stuv_seo_sitemap_posts_query_args', 10, 2);

/**
 * Drop the users and taxonomies providers: the site has one author and no
 * archive pages anyone should find. If a provider appears again later, that
 * is a signal, not a bug.
 */
function stuv_seo_sitemaps_add_provider($provider, string $name) {
    if (in_array($name, ['users', 'taxonomies'], true)) {
        return false;
    }

    return $provider;
}
add_filter('wp_sitemaps_add_provider', 'stuv_seo_sitemaps_add_provider', 10, 2);
