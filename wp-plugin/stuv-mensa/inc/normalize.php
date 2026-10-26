<?php
/**
 * Pure helpers for the Mensa widget; all date handling lives here. No WordPress
 * dependencies: tested with the plain `php` CLI (wp-plugin/tests/test_normalize.php).
 */

const STUV_MENSA_HOST = 'https://api.dhbw.app';
const STUV_MENSA_UPSTREAM = STUV_MENSA_HOST . '/mensa/HDH';
const STUV_MENSA_WINDOW = 5; // open days shown, rolling from today

const STUV_MENSA_WEEKDAYS = [
    1 => 'Montag', 2 => 'Dienstag', 3 => 'Mittwoch', 4 => 'Donnerstag',
    5 => 'Freitag', 6 => 'Samstag', 7 => 'Sonntag',
];

const STUV_MENSA_MONTHS = [
    1 => 'Januar', 2 => 'Februar', 3 => 'März', 4 => 'April',
    5 => 'Mai', 6 => 'Juni', 7 => 'Juli', 8 => 'August',
    9 => 'September', 10 => 'Oktober', 11 => 'November', 12 => 'Dezember',
];

/** Upstream stamps Berlin midnight as UTC; convert through the real timezone (DST). */
function stuv_mensa_berlin_date(string $upstream_ts): string {
    $dt = new DateTimeImmutable($upstream_ts);
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
 * The next STUV_MENSA_WINDOW open days from $today. Upstream leaves closed days out instead of
 * flagging them, hence the date filter. Empty `days` is normal (semester break); null means
 * upstream sent no menu and the caller keeps its copy.
 */
function stuv_mensa_normalize(
    array $upstream,
    string $today,
    string $image_base
): ?array {
    $site = $upstream[0] ?? null;
    if (!is_array($site) || !is_array($site['menus'] ?? null)) {
        return null;
    }

    $days = [];
    foreach ($site['menus'] as $menu) {
        if (!empty($menu['closed']) || empty($menu['date'])) {
            continue;
        }

        $date = stuv_mensa_berlin_date((string) $menu['date']);
        if ($date < $today) {
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
                'imageId' => $id, // the proxy allowlist reads this
            ];
        }

        if (!$meals) {
            continue;
        }

        $days[$date] = ['date' => $date]
            + stuv_mensa_label($date)
            + ['meals' => $meals];
    }

    ksort($days);

    return [
        'openingHours' => (string) ($site['mensaInfo']['openingHours'] ?? ''),
        'days'         => array_slice(array_values($days), 0, STUV_MENSA_WINDOW),
    ];
}

/** Extract the numeric id from an upstream image url, or null. */
function stuv_mensa_image_id(string $url): ?int {
    return preg_match('#/file/(\d+)/#', $url, $m) ? (int) $m[1] : null;
}

/** The upstream image url for an id (always /file/<id>/<id>.webp). */
function stuv_mensa_upstream_image_url(int $id): string {
    return sprintf('%s/file/%d/%d.webp', STUV_MENSA_HOST, $id, $id);
}

/** Every image id in a normalized payload. SECURITY: the image proxy's allowlist. */
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
