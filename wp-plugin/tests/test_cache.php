<?php
/**
 * Unit tests for inc/cache.php. Run: php wp-plugin/tests/test_cache.php
 */
require __DIR__ . '/harness.php';
require __DIR__ . '/../stuv-mensa/inc/cache.php';

// --- stuv_mensa_should_fetch -----------------------------------------------
check('fresh payload is served',
    stuv_mensa_should_fetch(true, false, true), false);

check('fresh payload served regardless of lock',
    stuv_mensa_should_fetch(true, true, true), false);

check('expired, no lock, store present: fetch',
    stuv_mensa_should_fetch(false, false, true), true);

check('expired, lock held: serve stale',
    stuv_mensa_should_fetch(false, true, true), false);

check('cold cache: fetch regardless of lock',
    stuv_mensa_should_fetch(false, false, false), true);

check('cold cache, lock held: still fetch (never block first visitors)',
    stuv_mensa_should_fetch(false, true, false), true);

// --- stuv_mensa_image_cacheable --------------------------------------------
check('cacheable: valid image response',
    stuv_mensa_image_cacheable('image/webp', str_repeat('x', 50000)),
    true);

check('cacheable: empty body rejected',
    stuv_mensa_image_cacheable('image/webp', ''), false);

check('cacheable: text/html Content-Type rejected',
    stuv_mensa_image_cacheable('text/html', '<html>'), false);

check('cacheable: application/octet-stream rejected',
    stuv_mensa_image_cacheable('application/octet-stream', 'bytes'), false);

check('cacheable: image/svg+xml rejected (executes script same-origin)',
    stuv_mensa_image_cacheable('image/svg+xml', '<svg></svg>'), false);

check('cacheable: Content-Type with charset parameter accepted',
    stuv_mensa_image_cacheable('image/webp; charset=binary', 'bytes'), true);

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

check('cacheable: exactly 2 MB accepted',
    stuv_mensa_image_cacheable('image/webp', str_repeat('x', 2 * 1024 * 1024)),
    true);

check('cacheable: one byte over 2 MB rejected',
    stuv_mensa_image_cacheable('image/webp', str_repeat('x', 2 * 1024 * 1024 + 1)),
    false);
