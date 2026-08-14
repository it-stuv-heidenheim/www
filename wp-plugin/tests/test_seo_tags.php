<?php
/**
 * Zero-dependency test harness for the pure tags layer.
 * Run: php wp-plugin/tests/test_seo_tags.php
 */
require __DIR__ . '/../stuv-seo/inc/pure/tags.php';

$failed = 0;

function check(string $name, $actual, $expected): void {
    global $failed;
    if ($actual === $expected) {
        echo "  ok    $name\n";
        return;
    }
    $failed++;
    echo "FAIL    $name\n";
    echo "        expected: " . var_export($expected, true) . "\n";
    echo "        actual:   " . var_export($actual, true) . "\n";
}

/** Fold the tag list into key => content for assertions. */
function tags_map(array $tags): array {
    $map = [];
    foreach ($tags as $tag) {
        $map[$tag['key']] = $tag['content'];
    }
    return $map;
}

// --- normalization ---------------------------------------------------------
check('normalize: collapses whitespace and trims',
    stuv_seo_normalize_text("  Hallo   Welt \n"), 'Hallo Welt');
check('normalize: strips markup',
    stuv_seo_normalize_text('<b>fett</b> Text'), 'fett Text');
check('normalize: empty stays empty',
    stuv_seo_normalize_text('   '), '');

// --- empty values ----------------------------------------------------------
$empty = tags_map(stuv_seo_meta_tags([]));
check('empty: no description', isset($empty['description']), false);
check('empty: no og:title', isset($empty['og:title']), false);
check('empty: no og:url', isset($empty['og:url']), false);
check('empty: no og:image', isset($empty['og:image']), false);
check('empty: no twitter:card', isset($empty['twitter:card']), false);
check('empty: og:type is always website', $empty['og:type'] ?? null, 'website');

// --- a full page -----------------------------------------------------------
$full = tags_map(stuv_seo_meta_tags([
    'description' => 'Alles über die StuV DHBW Heidenheim.',
    'title'       => 'Kummer Karsten – StuV Heidenheim',
    'url'         => 'https://stuv-heidenheim.de/kummer-karsten/',
    'site_name'   => 'StuV DHBW Heidenheim',
    'image'       => [
        'url'    => 'https://stuv-heidenheim.de/wp-content/uploads/og-default.jpg',
        'width'  => '1200',
        'height' => '630',
        'alt'    => 'Logo StuV Heidenheim',
    ],
    'locale'      => 'de_DE',
    'verification' => 'abc123',
]));

check('full: description present', $full['description'] ?? null, 'Alles über die StuV DHBW Heidenheim.');
check('full: og:title is the document title', $full['og:title'] ?? null, 'Kummer Karsten – StuV Heidenheim');
check('full: og:description equals description', $full['og:description'] ?? null, $full['description']);
check('full: og:url', $full['og:url'] ?? null, 'https://stuv-heidenheim.de/kummer-karsten/');
check('full: og:type website', $full['og:type'] ?? null, 'website');
check('full: og:site_name', $full['og:site_name'] ?? null, 'StuV DHBW Heidenheim');
check('full: og:locale from input', $full['og:locale'] ?? null, 'de_DE');
check('full: og:image url', $full['og:image'] ?? null, 'https://stuv-heidenheim.de/wp-content/uploads/og-default.jpg');
check('full: og:image:width', $full['og:image:width'] ?? null, '1200');
check('full: og:image:height', $full['og:image:height'] ?? null, '630');
check('full: og:image:alt', $full['og:image:alt'] ?? null, 'Logo StuV Heidenheim');
check('full: twitter:card summary_large_image', $full['twitter:card'] ?? null, 'summary_large_image');
check('full: twitter:image:alt', $full['twitter:image:alt'] ?? null, 'Logo StuV Heidenheim');
check('full: no twitter:title (stays short)', isset($full['twitter:title']), false);
check('full: no twitter:description (stays short)', isset($full['twitter:description']), false);
check('full: no twitter:site', isset($full['twitter:site']), false);
check('full: google-site-verification', $full['google-site-verification'] ?? null, 'abc123');

// --- no description --------------------------------------------------------
$no_desc = tags_map(stuv_seo_meta_tags([
    'title' => 'Kontakt',
    'url'   => 'https://stuv-heidenheim.de/kontakt/',
]));
check('no description: no meta description', isset($no_desc['description']), false);
check('no description: no og:description either', isset($no_desc['og:description']), false);
check('no description: og:title still there', $no_desc['og:title'] ?? null, 'Kontakt');

// --- no image --------------------------------------------------------------
$no_img = tags_map(stuv_seo_meta_tags([
    'title' => 'Events',
    'url'   => 'https://stuv-heidenheim.de/events/',
]));
check('no image: no og:image', isset($no_img['og:image']), false);
check('no image: no twitter:card', isset($no_img['twitter:card']), false);

// --- image without alt -----------------------------------------------------
$img_no_alt = tags_map(stuv_seo_meta_tags([
    'title' => 'Startseite',
    'image' => ['url' => 'https://example.test/bild.jpg'],
]));
check('image no alt: card present', $img_no_alt['twitter:card'] ?? null, 'summary_large_image');
check('image no alt: no og:image:alt', isset($img_no_alt['og:image:alt']), false);
check('image no alt: no twitter:image:alt', isset($img_no_alt['twitter:image:alt']), false);

// --- never truncated -------------------------------------------------------
$long = 'x';
while (mb_strlen($long) <= 300) {
    $long .= ' Dieser Satz wird sehr lang, damit klar ist, dass niemand die Beschreibung kürzt.';
}
$long_tags = tags_map(stuv_seo_meta_tags(['description' => $long]));
check('never truncated: description keeps its full length',
    mb_strlen($long_tags['description'] ?? ''), mb_strlen($long));

// --- verification empty ----------------------------------------------------
$no_ver = tags_map(stuv_seo_meta_tags(['verification' => '  ']));
check('verification empty: no tag', isset($no_ver['google-site-verification']), false);

echo $failed ? "\n$failed failed\n" : "\nall passed\n";
exit($failed ? 1 : 0);
