<?php
/**
 * Build and output the JSON-LD @graph.
 *
 * Three nodes, no more: Organization (front page only), FAQPage (Kummer
 * Karsten, derived from the page's own <details> blocks). Event stays out —
 * there are no real term data to mark up yet; it will plug in via the
 * `stuv_seo_jsonld_graph` filter below without touching this file.
 *
 * The graph is emitted with JSON_HEX_TAG | JSON_HEX_AMP: the values come from
 * wp-admin-editable fields, and without those flags a `</script>` inside one
 * of them would leave the JSON-LD block.
 */

if (!defined('ABSPATH')) {
    exit;
}

function stuv_seo_jsonld(): void {
    if (!is_singular('page')) {
        return;
    }

    $post  = get_post();
    $nodes = [];

    if (is_front_page()) {
        $nodes[] = [
            '@type'              => 'Organization',
            '@id'                => home_url('/#organization'),
            'name'               => (string) get_bloginfo('name'),
            'url'                => home_url('/'),
            'logo'               => [
                '@type'  => 'ImageObject',
                'url'    => home_url('/wp-content/uploads/stuv-dhbw-logo-q.png'),
                'width'  => 1342,
                'height' => 320,
            ],
            'email'              => 'vorsitz@stuv-heidenheim.de',
            'address'            => [
                '@type'          => 'PostalAddress',
                'streetAddress'  => 'Marienstraße 20',
                'postalCode'     => '89518',
                'addressLocality' => 'Heidenheim an der Brenz',
                'addressRegion'  => 'BW',
                'addressCountry' => 'DE',
            ],
            'parentOrganization' => [
                '@type' => 'CollegeOrUniversity',
                'name'  => 'DHBW Heidenheim',
            ],
            // No sameAs: the Instagram handle is unresolved (two conflicting
            // handles in the content). A machine-readable identity claim would
            // state the wrong account as fact. Valid without it.
        ];
    }

    if (is_a($post, WP_Post::class) && 'kummer-karsten' === $post->post_name) {
        $pairs = stuv_seo_faq_pairs(parse_blocks((string) $post->post_content));
        if ($pairs) {
            $nodes[] = [
                '@type'      => 'FAQPage',
                'mainEntity' => array_map(
                    fn($pair) => [
                        '@type'          => 'Question',
                        'name'           => $pair['question'],
                        'acceptedAnswer' => [
                            '@type' => 'Answer',
                            'text'  => $pair['answer'],
                        ],
                    ],
                    $pairs
                ),
            ];
        }
    }

    $nodes = apply_filters('stuv_seo_jsonld_graph', $nodes);

    if (!$nodes) {
        return;
    }

    $json = wp_json_encode(
        ['@context' => 'https://schema.org', '@graph' => $nodes],
        JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP
    );

    if (is_string($json)) {
        echo '<script type="application/ld+json">' . $json . '</script>' . "\n";
    }
}
add_action('wp_head', 'stuv_seo_jsonld', 5);
