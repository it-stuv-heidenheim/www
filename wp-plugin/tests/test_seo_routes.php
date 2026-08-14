<?php
/**
 * Zero-dependency test harness for the pure routes layer.
 * Run: php wp-plugin/tests/test_seo_routes.php
 */
require __DIR__ . '/../stuv-seo/inc/pure/routes.php';

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

// Root-relative targets, like the real map in inc/redirects.php: an absolute
// URL would be thrown out by wp_validate_redirect() on any host but the one it
// names.
$map = [
    '/campus/'           => '/studentenleben/',
    '/hochschulpolitik/' => '/ueber-uns/#referate',
    '/links/'            => '/linktree/',
];

// --- normalization ---------------------------------------------------------
check('exact path', stuv_seo_redirect_target('/campus/', $map), '/studentenleben/');
check('query string is dropped', stuv_seo_redirect_target('/campus/?utm_source=x', $map),
    '/studentenleben/');
check('case does not matter', stuv_seo_redirect_target('/CAMPUS/', $map), '/studentenleben/');
check('no leading slash', stuv_seo_redirect_target('campus', $map), '/studentenleben/');
check('no trailing slash', stuv_seo_redirect_target('/campus', $map), '/studentenleben/');
check('anchor dropped as part of the fragment', stuv_seo_redirect_target('/hochschulpolitik/#x', $map),
    '/ueber-uns/#referate');

// --- unknown paths ---------------------------------------------------------
check('unknown path is null', stuv_seo_redirect_target('/nichtsda/', $map), null);
check('empty path is null', stuv_seo_redirect_target('', $map), null);
check('root is null without a root entry', stuv_seo_redirect_target('/', $map), null);

// --- self-protection -------------------------------------------------------
$loop = ['/loop/' => '/loop/'];
check('entry pointing at itself is null', stuv_seo_redirect_target('/loop/', $loop), null);

// An absolute target whose path normalizes to the same key is equally a loop:
// /same/ would redirect to /same/.
$absolute_loop = ['/same/' => 'https://example.test/same/'];
check('absolute target back to the same path is null',
    stuv_seo_redirect_target('/same/', $absolute_loop), null);

// A redirect INTO a dead entry is not a loop — it passes through and the
// second request terminates at the 404.
$into_dead = ['/other/' => '/loop/', '/loop/' => '/loop/'];
check('redirect into a dead entry passes through', stuv_seo_redirect_target('/other/', $into_dead), '/loop/');

// --- root map entry --------------------------------------------------------
// '/' -> the site root normalizes to the same key, so the self-protection
// treats it as a loop. There is no legitimate root redirect anyway.
$root_map = ['/' => 'https://stuv-heidenheim.de/'];
check('root entry normalizes to itself and is null', stuv_seo_redirect_target('/', $root_map), null);

echo $failed ? "\n$failed failed\n" : "\nall passed\n";
exit($failed ? 1 : 0);
