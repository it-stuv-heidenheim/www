<?php
/**
 * Pure helpers for the StuV Mensa widget.
 *
 * NO WordPress dependencies may be added to this file — it is unit-tested with
 * the plain `php` CLI (wp-plugin/tests/test_normalize.php). All date handling
 * lives here so the browser never parses an upstream timestamp.
 */

if (!defined('STUV_MENSA_HOST')) {
    define('STUV_MENSA_HOST', 'https://api.dhbw.app');
}
if (!defined('STUV_MENSA_UPSTREAM')) {
    define('STUV_MENSA_UPSTREAM', STUV_MENSA_HOST . '/mensa/HDH');
}
if (!defined('STUV_MENSA_WINDOW')) {
    define('STUV_MENSA_WINDOW', 5); // open days shown, rolling from today
}

const STUV_MENSA_WEEKDAYS = [
    1 => 'Montag', 2 => 'Dienstag', 3 => 'Mittwoch', 4 => 'Donnerstag',
    5 => 'Freitag', 6 => 'Samstag', 7 => 'Sonntag',
];

const STUV_MENSA_MONTHS = [
    1 => 'Januar', 2 => 'Februar', 3 => 'März', 4 => 'April',
    5 => 'Mai', 6 => 'Juni', 7 => 'Juli', 8 => 'August',
    9 => 'September', 10 => 'Oktober', 11 => 'November', 12 => 'Dezember',
];

/**
 * Upstream stamps local midnight as UTC ("2026-07-12T22:00:00.000Z" is Monday
 * the 13th in Berlin). Convert to a plain Berlin calendar date. The offset is
 * +2 in summer and +1 in winter, so this must go through a real timezone —
 * a fixed shift breaks twice a year.
 */
function stuv_mensa_berlin_date(string $upstream_ts): string {
    $dt = new DateTimeImmutable($upstream_ts); // trailing Z is parsed as UTC
    return $dt->setTimezone(new DateTimeZone('Europe/Berlin'))->format('Y-m-d');
}

/** German weekday + long label for a 'Y-m-d' date. No intl extension required. */
function stuv_mensa_label(string $date): array {
    $dt = DateTimeImmutable::createFromFormat(
        '!Y-m-d', $date, new DateTimeZone('Europe/Berlin')
    );
    $weekday = STUV_MENSA_WEEKDAYS[(int) $dt->format('N')];
    $month   = STUV_MENSA_MONTHS[(int) $dt->format('n')];

    return [
        'weekday' => $weekday,
        'label'   => sprintf('%s, %d. %s', $weekday, (int) $dt->format('j'), $month),
    ];
}

/**
 * Trim the upstream payload to what the widget needs.
 *
 * Returns a rolling window of the next $window OPEN days starting at $today.
 * Weekends and holidays are simply absent from the upstream data (they are NOT
 * flagged `closed`), so "no menu today" is expressed by absence — which is why
 * this filters by date rather than trusting the `closed` flag alone.
 *
 * An empty `days` array is a normal response (semester break), not an error.
 */
function stuv_mensa_normalize(
    array $upstream,
    string $today,
    string $image_base,
    int $window = STUV_MENSA_WINDOW
): array {
    $site = $upstream[0] ?? [];

    $days = [];
    foreach (($site['menus'] ?? []) as $menu) {
        if (!empty($menu['closed']) || empty($menu['date'])) {
            continue;
        }

        $date = stuv_mensa_berlin_date((string) $menu['date']);
        if ($date < $today) { // 'Y-m-d' compares correctly as a string
            continue;
        }

        $meals = [];
        foreach (($menu['mainCourses'] ?? []) as $course) {
            if (!isset($course['name'], $course['priceStudent'])) {
                continue;
            }
            $id = isset($course['image'])
                ? stuv_mensa_image_id((string) $course['image'])
                : null;

            $meals[] = [
                'name'    => (string) $course['name'],
                'price'   => (float) $course['priceStudent'],
                'image'   => $id === null ? null : $image_base . $id,
                'imageId' => $id, // the proxy allowlist reads this, not the url
            ];
        }

        if (!$meals) {
            continue; // a day with no meals is not an open day
        }

        $days[$date] = ['date' => $date]
            + stuv_mensa_label($date)
            + ['meals' => $meals];
    }

    ksort($days);

    return [
        'openingHours' => (string) ($site['mensaInfo']['openingHours'] ?? ''),
        'days'         => array_slice(array_values($days), 0, $window),
    ];
}

/** Extract the numeric id from an upstream image url, or null. */
function stuv_mensa_image_id(string $url): ?int {
    return preg_match('#/file/(\d+)/#', $url, $m) ? (int) $m[1] : null;
}

/**
 * Rebuild the upstream image url from an id. The upstream path is always
 * /file/<id>/<id>.webp, so the id is the only thing we need to store.
 */
function stuv_mensa_upstream_image_url(int $id): string {
    return sprintf('%s/file/%d/%d.webp', STUV_MENSA_HOST, $id, $id);
}

/**
 * Every image id present in a normalized payload.
 *
 * SECURITY: this is the allowlist the image proxy checks against. An id that is
 * not in the current menu must 404. Skip this and the route becomes an open
 * proxy that will fetch any /file/<n>/ upstream on a stranger's behalf.
 */
function stuv_mensa_image_ids(array $payload): array {
    $ids = [];
    foreach (($payload['days'] ?? []) as $day) {
        foreach (($day['meals'] ?? []) as $meal) {
            $id = (int) ($meal['imageId'] ?? 0);
            if ($id > 0) {
                $ids[$id] = true;
            }
        }
    }
    return array_keys($ids);
}
