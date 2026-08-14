<?php
/**
 * Output the meta description, Open Graph and Twitter tags on wp_head.
 *
 * Priority 2 keeps the tags near the top of the head, above the stylesheet
 * flood. Values are collected per page — post meta first, the sitewide option
 * second, nothing else — and handed to the pure stuv_seo_meta_tags() as raw
 * data; escaping happens here with esc_attr(), once, at the single point that
 * touches the HTML.
 *
 * og:url comes from wp_get_canonical_url() so the two can never diverge. The
 * image is resolved to an absolute URL via wp_get_attachment_image_src() —
 * root-relative URLs are not valid og:image values, and an absolute one built
 * from the attachment points at the production host automatically once the
 * DNS moves.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * The sitewide SEO settings option, always an array.
 *
 * Keys: `og_image` (attachment id of the default preview image) and
 * `google_verification` (the Search Console token). Registered and edited on
 * the settings page in inc/admin.php; read here for the fallback image.
 */
function stuv_seo_get_settings(): array {
    $settings = get_option('stuv_seo_settings', []);

    return is_array($settings) ? $settings : [];
}

function stuv_seo_head(): void {
    if (!is_singular('page')) {
        return;
    }

    $post_id  = get_queried_object_id();
    $settings = stuv_seo_get_settings();

    $image_id = stuv_seo_get_og_image_id($post_id);
    if ($image_id < 1) {
        $image_id = (int) ($settings['og_image'] ?? 0);
    }

    $image = null;
    if ($image_id > 0) {
        $src = wp_get_attachment_image_src($image_id, 'full');
        if (is_array($src)) {
            $image = [
                'url'    => (string) $src[0],
                'width'  => (string) $src[1],
                'height' => (string) $src[2],
                'alt'    => (string) get_post_meta($image_id, '_wp_attachment_image_alt', true),
            ];
        }
    }

    $canonical = wp_get_canonical_url();

    $tags = stuv_seo_meta_tags([
        'description'  => stuv_seo_get_description($post_id),
        'title'        => (string) wp_get_document_title(),
        'url'          => is_string($canonical) ? $canonical : home_url('/'),
        'site_name'    => (string) get_bloginfo('name'),
        'image'        => $image,
        'locale'       => (string) get_locale(),
        'verification' => (string) ($settings['google_verification'] ?? ''),
    ]);

    foreach ($tags as $tag) {
        $attribute = 'property' === $tag['meta'] ? 'property' : 'name';
        printf(
            '<meta %s="%s" content="%s" />' . "\n",
            $attribute,
            esc_attr($tag['key']),
            esc_attr($tag['content'])
        );
    }
}
add_action('wp_head', 'stuv_seo_head', 2);
