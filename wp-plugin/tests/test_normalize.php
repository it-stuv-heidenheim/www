<?php
/**
 * Unit tests for inc/normalize.php. Run: php wp-plugin/tests/test_normalize.php
 */
require __DIR__ . '/harness.php';
require __DIR__ . '/../stuv-mensa/inc/normalize.php';

// --- stuv_mensa_berlin_date -------------------------------------------------
// The regression test for the whole feature: upstream stamps local midnight as
// UTC, so a naive parse reads this as Sunday.
check('summer: 22:00Z is next day in Berlin (CEST)',
    stuv_mensa_berlin_date('2026-07-12T22:00:00.000Z'), '2026-07-13');

// In winter Berlin is UTC+1, so the upstream offset changes to 23:00Z.
// Hardcoding a +2 shift would break every winter.
check('winter: 23:00Z is next day in Berlin (CET)',
    stuv_mensa_berlin_date('2026-01-12T23:00:00.000Z'), '2026-01-13');

// --- stuv_mensa_label -------------------------------------------------------
check('label: Monday',
    stuv_mensa_label('2026-07-13'),
    ['weekday' => 'Montag', 'label' => 'Montag, 13. Juli']);

check('label: Saturday in March',
    stuv_mensa_label('2026-03-07'),
    ['weekday' => 'Samstag', 'label' => 'Samstag, 7. März']);

// --- stuv_mensa_normalize ---------------------------------------------------
$fixture = json_decode(file_get_contents(__DIR__ . '/fixtures/mensa-hdh.json'), true);
$base    = 'https://example.test/index.php/wp-json/stuv/v1/mensa/image/';

// Tuesday: today is an open day and comes first.
$mon = stuv_mensa_normalize($fixture, '2026-07-14', $base);
check('tuesday: window is 5 open days', count($mon['days']), 5);
check('tuesday: first day is today', $mon['days'][0]['date'], '2026-07-14');
check('tuesday: first day labelled Dienstag', $mon['days'][0]['weekday'], 'Dienstag');
check('tuesday: opening hours passed through', $mon['openingHours'], '11:30 – 13:45 Uhr');
check('tuesday: meals have a student price',
    is_float($mon['days'][0]['meals'][0]['price']), true);
check('tuesday: image points at our proxy, not api.dhbw.app',
    str_starts_with($mon['days'][0]['meals'][0]['image'], $base), true);

// Saturday: no menu today. The next open day is Monday of the NEXT week —
// which a calendar-week payload would not contain. This is the weekend bug.
$sat = stuv_mensa_normalize($fixture, '2026-07-18', $base);
check('saturday: skips to the next open day', $sat['days'][0]['date'], '2026-07-20');
check('saturday: next open day is a Monday', $sat['days'][0]['weekday'], 'Montag');
check('saturday: no past days leak in',
    array_filter($sat['days'], fn($d) => $d['date'] < '2026-07-18'), []);

// Semester break: nothing left in the window. `days: []` is a valid response,
// not an error — the widget renders its closed state from it.
$break = stuv_mensa_normalize($fixture, '2030-01-01', $base);
check('semester break: empty days, not an error', $break['days'], []);
check('semester break: opening hours still present',
    $break['openingHours'], '11:30 – 13:45 Uhr');

// Window is honoured.
check('window: respects a smaller window',
    count(stuv_mensa_normalize($fixture, '2026-07-13', $base, 2)['days']), 2);

// --- image helpers ----------------------------------------------------------
check('image id: parsed from the upstream url',
    stuv_mensa_image_id('https://api.dhbw.app/file/12692/12692.webp'), 12692);
check('image id: null when the url has no id',
    stuv_mensa_image_id('https://api.dhbw.app/file/nope.webp'), null);

check('upstream url: rebuilt from an id',
    stuv_mensa_upstream_image_url(12692),
    'https://api.dhbw.app/file/12692/12692.webp');

// The allowlist the proxy checks against.
$ids = stuv_mensa_image_ids(stuv_mensa_normalize($fixture, '2026-07-13', $base));
check('allowlist: is non-empty', count($ids) > 0, true);
check('allowlist: every entry is an int', array_filter($ids, fn($i) => !is_int($i)), []);
check('allowlist: excludes an id that is not in the payload',
    in_array(999999999, $ids, true), false);
check('allowlist: empty payload yields no ids',
    stuv_mensa_image_ids(['openingHours' => '', 'days' => []]), []);
