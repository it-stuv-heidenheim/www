<?php
/**
 * Unit tests for stuv-events/inc/ics.php. Run: php wp-plugin/tests/test_ics.php
 */
require __DIR__ . '/harness.php';
require __DIR__ . '/../stuv-events/inc/ics.php';

$ics = file_get_contents(__DIR__ . '/fixtures/events.ics');
$now = new DateTimeImmutable('2026-10-26 12:00', new DateTimeZone('Europe/Berlin'));
$all = stuv_events_build($ics, $now, 120, 100);

$by_series = function (string $uid) use ($all): array {
    return array_values(array_map(
        fn($e) => $e['start'],
        array_filter($all, fn($e) => $e['series'] === $uid)
    ));
};
$one = function (string $uid) use ($all): array {
    foreach ($all as $e) {
        if ($e['series'] === $uid) {
            return $e;
        }
    }
    return [];
};

// --- one-off events ---------------------------------------------------------
// 18:30Z in late October is 19:30 in Berlin (CET, after the switch on the 25th).
check('UTC start is shown in Berlin time',
    $one('party@test')['start'], '2026-10-28T19:30');

check('labels for a timed event',
    array_intersect_key($one('party@test'), array_flip(['weekday', 'day_month', 'day', 'month', 'time'])),
    ['weekday' => 'Mittwoch', 'day_month' => '28. Oktober', 'day' => '28', 'month' => 'Okt', 'time' => '19:30 Uhr']);

check('place is the first part of the location, unescaped',
    $one('party@test')['place'], 'Felsen');

check('a link as location shows no place',
    $one('gaudi@test')['place'], '');

check('an event ending at midnight stays on its day',
    $one('gaudi@test')['time'], '19:30 Uhr');

check('a cancelled event is left out',
    $by_series('abgesagt@test'), []);

check('an event that has ended is left out',
    $by_series('vorbei@test'), []);

// --- all-day events ---------------------------------------------------------
check('folded summary is joined',
    $one('wochenende@test')['title'], 'StuV-Wochenende in Österreich');

check('multi-day all-day event: DTEND is exclusive',
    [$one('wochenende@test')['start'], $one('wochenende@test')['time']],
    ['2026-11-27T00:00', 'Bis So, 29. Nov']);

// --- weekly rule with UNTIL and EXDATE ---------------------------------------
// The past Mondays (5.-19.10.) are gone, 2.11. is an EXDATE, and UNTIL ends
// the series on 30.11. The cap keeps three of the remaining five.
check('weekly: past dates, EXDATE and the per-series cap',
    $by_series('sport@test'),
    ['2026-10-26T20:00', '2026-11-09T20:00', '2026-11-16T20:00']);

$weekly = stuv_events_expand(
    new DateTimeImmutable('2026-10-05 20:00', new DateTimeZone('Europe/Berlin')),
    stuv_events_parse_rrule('FREQ=WEEKLY;WKST=MO;UNTIL=20261130T225959Z;BYDAY=MO'),
    PHP_INT_MAX
);
check('weekly: UNTIL is inclusive, wall-clock time survives the DST change',
    array_map(fn($d) => $d->format('m-d H:i'), $weekly),
    ['10-05 20:00', '10-12 20:00', '10-19 20:00', '10-26 20:00', '11-02 20:00',
     '11-09 20:00', '11-16 20:00', '11-23 20:00', '11-30 20:00']);

// --- every fourth week, with a moved and a cancelled instance ----------------
// 13.10. is past; 10.11. moved to 11.11. (its own entry, same series);
// 8.12. is cancelled by its override.
check('interval 4: moved instance replaces its slot, cancelled one is gone',
    $by_series('sitzung@test'),
    ['2026-11-11T19:15', '2027-01-05T19:15', '2027-02-02T19:15']);

check('a moved instance keeps its own title',
    $one('sitzung@test')['title'], 'StuV Sitzung (verschoben)');

// --- monthly ----------------------------------------------------------------
check('monthly on the first Tuesday, COUNT=3',
    $by_series('monat@test'),
    ['2026-11-03T18:00', '2026-12-01T18:00', '2027-01-05T18:00']);

check('an unsupported rule shows only its first date',
    $by_series('unbekannt@test'), ['2026-10-29T18:00']);

// --- ordering and limits ----------------------------------------------------
$starts = array_map(fn($e) => $e['start'], $all);
$sorted = $starts;
sort($sorted);
check('sorted by start', $starts, $sorted);

check('max limits the payload',
    count(stuv_events_build($ics, $now, 120, 2)), 2);

// Four days ahead reaches Friday noon: the Monday training (ends 22:00 today),
// Wednesday's party and Thursday's one-off date, nothing from November.
check('the horizon limits how far ahead',
    array_map(fn($e) => $e['series'], stuv_events_build($ics, $now, 4, 100)),
    ['sport@test', 'party@test', 'unbekannt@test']);

// --- helpers ----------------------------------------------------------------
check('nth weekday: last Friday',
    stuv_events_nth_weekday(new DateTimeImmutable('2026-10-01'), -1, 5)->format('Y-m-d'), '2026-10-30');

check('nth weekday: a fifth Monday that does not exist',
    stuv_events_nth_weekday(new DateTimeImmutable('2026-12-01'), 5, 1), null);

check('unescape',
    stuv_events_unescape('a\\, b\\; c\\nd\\\\e'), "a, b; c\nd\\e");
