<?php
/**
 * Pure helper: build the ordered meta/OG/Twitter tag list for a page.
 *
 * NO WordPress dependencies may be added to this file — it is unit-tested with
 * the plain `php` CLI (wp-plugin/tests/test_seo_tags.php). It returns raw data
 * structures; escaping with esc_attr() happens in inc/head.php.
 */

/**
 * Strip markup and collapse whitespace. Shared by description and title so
 * that what is compared against empty is the value that would actually be
 * printed. Never truncates: a long description is a signal to the person who
 * wrote it, not a licence to cut foreign prose here.
 */
function stuv_seo_normalize_text(string $text): string {
    return trim(preg_replace('/\s+/u', ' ', strip_tags($text)) ?? '');
}

/**
 * The ordered head tags for a page.
 *
 * Input keys (all optional — empty values emit nothing):
 *   description   string  Meta description. Stripped of markup and whitespace-
 *                         collapsed, never truncated. When empty, neither
 *                         `description` nor `og:description` is emitted and
 *                         nothing is cobbled together from page content.
 *   title         string  og:title (the document title).
 *   url           string  og:url (the canonical URL).
 *   site_name     string  og:site_name.
 *   image         array   ['url' => ..., 'width' => ..., 'height' => ...,
 *                         'alt' => ...] — only non-empty entries become tags.
 *   locale        string  og:locale, e.g. de_DE. Passed in, never hardcoded.
 *   verification  string  Google Search Console token (`name=...`).
 *
 * og:type is always `website` — `article` would promise publication and
 * modification dates that mean nothing on these pages.
 *
 * Twitter stays deliberately short: only `twitter:card` and `twitter:image:alt`.
 * X reads title, description and image from the OG tags, so a second set of
 * the same strings can only drift apart. There is no twitter:site — there is
 * no account. The card only appears when there is an image: `summary_large_image`
 * without one is a broken promise.
 *
 * @return array<int, array{meta: string, key: string, content: string}>
 */
function stuv_seo_meta_tags(array $v): array {
    $tags = [];

    $description = stuv_seo_normalize_text((string) ($v['description'] ?? ''));
    if ('' !== $description) {
        $tags[] = ['meta' => 'name', 'key' => 'description', 'content' => $description];
    }

    $title = stuv_seo_normalize_text((string) ($v['title'] ?? ''));
    if ('' !== $title) {
        $tags[] = ['meta' => 'property', 'key' => 'og:title', 'content' => $title];
    }

    if ('' !== $description) {
        $tags[] = ['meta' => 'property', 'key' => 'og:description', 'content' => $description];
    }

    $url = trim((string) ($v['url'] ?? ''));
    if ('' !== $url) {
        $tags[] = ['meta' => 'property', 'key' => 'og:url', 'content' => $url];
    }

    $tags[] = ['meta' => 'property', 'key' => 'og:type', 'content' => 'website'];

    $site_name = stuv_seo_normalize_text((string) ($v['site_name'] ?? ''));
    if ('' !== $site_name) {
        $tags[] = ['meta' => 'property', 'key' => 'og:site_name', 'content' => $site_name];
    }

    $locale = trim((string) ($v['locale'] ?? ''));
    if ('' !== $locale) {
        $tags[] = ['meta' => 'property', 'key' => 'og:locale', 'content' => $locale];
    }

    $image = $v['image'] ?? [];
    $image_url = trim((string) ($image['url'] ?? ''));
    if ('' !== $image_url) {
        $tags[] = ['meta' => 'property', 'key' => 'og:image', 'content' => $image_url];

        foreach (['width' => 'og:image:width', 'height' => 'og:image:height'] as $dim => $key) {
            $dim_value = trim((string) ($image[$dim] ?? ''));
            if ('' !== $dim_value) {
                $tags[] = ['meta' => 'property', 'key' => $key, 'content' => $dim_value];
            }
        }

        $tags[] = ['meta' => 'name', 'key' => 'twitter:card', 'content' => 'summary_large_image'];
    }

    $image_alt = trim((string) ($image['alt'] ?? ''));
    if ('' !== $image_alt) {
        $tags[] = ['meta' => 'property', 'key' => 'og:image:alt', 'content' => $image_alt];
        $tags[] = ['meta' => 'name', 'key' => 'twitter:image:alt', 'content' => $image_alt];
    }

    $verification = trim((string) ($v['verification'] ?? ''));
    if ('' !== $verification) {
        $tags[] = ['meta' => 'name', 'key' => 'google-site-verification', 'content' => $verification];
    }

    return $tags;
}
