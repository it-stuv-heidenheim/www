<?php
/**
 * Post-meta registration and read access for the SEO values.
 *
 * All three keys carry an underscore prefix — that makes them "protected",
 * which is exactly what register_post_meta needs an auth_callback for. The
 * values live in the database, not in this repo or in the manifest: they are
 * the same data type as the page title, edited by whoever writes the page,
 * and invisible to verify_deploy.py, so editing them in wp-admin can never
 * become drift against the deployed content.
 */

if (!defined('ABSPATH')) {
    exit;
}

function stuv_seo_meta_auth_callback($post_id): bool {
    return current_user_can('edit_page', $post_id);
}

function stuv_seo_sanitize_boolean($value): bool {
    return (bool) $value;
}

function stuv_seo_register_meta(): void {
    register_post_meta('page', '_stuv_seo_description', [
        'type'              => 'string',
        'single'            => true,
        'show_in_rest'      => true,
        'sanitize_callback' => fn($v) => sanitize_text_field((string) $v),
        'auth_callback'     => 'stuv_seo_meta_auth_callback',
    ]);

    register_post_meta('page', '_stuv_seo_og_image', [
        'type'              => 'integer',
        'single'            => true,
        'show_in_rest'      => true,
        'sanitize_callback' => 'absint',
        'auth_callback'     => 'stuv_seo_meta_auth_callback',
    ]);

    register_post_meta('page', '_stuv_seo_noindex', [
        'type'              => 'boolean',
        'single'            => true,
        'show_in_rest'      => true,
        'sanitize_callback' => 'stuv_seo_sanitize_boolean',
        'auth_callback'     => 'stuv_seo_meta_auth_callback',
    ]);
}
add_action('init', 'stuv_seo_register_meta');

function stuv_seo_get_description($post_id): string {
    $value = get_post_meta($post_id, '_stuv_seo_description', true);

    return is_string($value) ? $value : '';
}

function stuv_seo_get_og_image_id($post_id): int {
    return (int) get_post_meta($post_id, '_stuv_seo_og_image', true);
}

function stuv_seo_get_noindex($post_id): bool {
    return (bool) get_post_meta($post_id, '_stuv_seo_noindex', true);
}
