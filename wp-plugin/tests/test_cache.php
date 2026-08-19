<?php
/**
 * Zero-dependency test harness. Run: php wp-plugin/tests/test_cache.php
 */
require __DIR__ . '/../stuv-mensa/inc/cache.php';

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

// --- stuv_mensa_payload_decision -------------------------------------------
check('fresh payload is served',
    stuv_mensa_payload_decision(true, false, true), 'serve');

check('fresh payload served regardless of lock',
    stuv_mensa_payload_decision(true, true, true), 'serve');

check('expired, no lock, store present — fetch',
    stuv_mensa_payload_decision(false, false, true), 'fetch');

check('expired, lock held — serve stale',
    stuv_mensa_payload_decision(false, true, true), 'serve_stale');

check('cold cache — fetch regardless of lock',
    stuv_mensa_payload_decision(false, false, false), 'fetch');

check('cold cache, lock held — still fetch (never block first visitors)',
    stuv_mensa_payload_decision(false, true, false), 'fetch');

// --- stuv_mensa_image_cacheable --------------------------------------------
check('cacheable: valid image response',
    stuv_mensa_image_cacheable(200, 'image/webp', str_repeat('x', 50000)),
    true);

check('cacheable: empty body — no',
    stuv_mensa_image_cacheable(200, 'image/webp', ''), false);

check('cacheable: non-200 status — no',
    stuv_mensa_image_cacheable(500, 'image/webp', 'bytes'), false);

check('cacheable: text/html Content-Type — no',
    stuv_mensa_image_cacheable(200, 'text/html', '<html>'), false);

check('cacheable: application/octet-stream — no',
    stuv_mensa_image_cacheable(200, 'application/octet-stream', 'bytes'), false);

check('cacheable: image/svg+xml — no (executes script same-origin)',
    stuv_mensa_image_cacheable(200, 'image/svg+xml', '<svg></svg>'), false);

check('cacheable: Content-Type with charset parameter — yes',
    stuv_mensa_image_cacheable(200, 'image/webp; charset=binary', 'bytes'), true);

// --- stuv_mensa_safe_image_type --------------------------------------------
check('safe type: image/webp passes through',
    stuv_mensa_safe_image_type('image/webp'), 'image/webp');

check('safe type: parameters stripped, case normalized',
    stuv_mensa_safe_image_type('IMAGE/JPEG; charset=binary'), 'image/jpeg');

check('safe type: text/html neutralized',
    stuv_mensa_safe_image_type('text/html'), 'application/octet-stream');

check('safe type: image/svg+xml neutralized',
    stuv_mensa_safe_image_type('image/svg+xml'), 'application/octet-stream');

check('safe type: empty neutralized',
    stuv_mensa_safe_image_type(''), 'application/octet-stream');

check('cacheable: exactly at 2 MB — yes',
    stuv_mensa_image_cacheable(200, 'image/webp', str_repeat('x', 2 * 1024 * 1024)),
    true);

check('cacheable: one byte over 2 MB — no',
    stuv_mensa_image_cacheable(200, 'image/webp', str_repeat('x', 2 * 1024 * 1024 + 1)),
    false);

echo $failed ? "\n$failed failed\n" : "\nall passed\n";
exit($failed ? 1 : 0);
