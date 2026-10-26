<?php
/**
 * Parse the iCalendar feed, expand recurrences, label occurrences in German.
 * No WordPress dependencies: tested with the plain `php` CLI (wp-plugin/tests/test_ics.php).
 */

const STUV_EVENTS_WEEKDAYS = [
    1 => 'Montag', 2 => 'Dienstag', 3 => 'Mittwoch', 4 => 'Donnerstag',
    5 => 'Freitag', 6 => 'Samstag', 7 => 'Sonntag',
];

const STUV_EVENTS_WEEKDAYS_SHORT = [
    1 => 'Mo', 2 => 'Di', 3 => 'Mi', 4 => 'Do', 5 => 'Fr', 6 => 'Sa', 7 => 'So',
];

const STUV_EVENTS_MONTHS = [
    1 => 'Januar', 2 => 'Februar', 3 => 'März', 4 => 'April',
    5 => 'Mai', 6 => 'Juni', 7 => 'Juli', 8 => 'August',
    9 => 'September', 10 => 'Oktober', 11 => 'November', 12 => 'Dezember',
];

const STUV_EVENTS_MONTHS_SHORT = [
    1 => 'Jan', 2 => 'Feb', 3 => 'März', 4 => 'Apr', 5 => 'Mai', 6 => 'Juni',
    7 => 'Juli', 8 => 'Aug', 9 => 'Sept', 10 => 'Okt', 11 => 'Nov', 12 => 'Dez',
];

const STUV_EVENTS_ICAL_DAYS = ['MO' => 1, 'TU' => 2, 'WE' => 3, 'TH' => 4, 'FR' => 5, 'SA' => 6, 'SU' => 7];

// Rules with any other part show only their first occurrence: a wrong date does more harm than a missing repeat.
const STUV_EVENTS_RRULE_PARTS = ['FREQ', 'INTERVAL', 'COUNT', 'UNTIL', 'BYDAY', 'WKST'];

const STUV_EVENTS_MAX_STEPS = 5000; // bounds the expansion of a runaway rule
const STUV_EVENTS_PER_SERIES = 3;

function stuv_events_tz(): DateTimeZone {
    return new DateTimeZone('Europe/Berlin');
}

/** VEVENT property maps: ['NAME' => [['params' => [...], 'value' => '...'], ...]]. */
function stuv_events_parse_ics(string $ics): array {
    $text   = preg_replace("/\r?\n[ \t]/", '', str_replace("\r\n", "\n", $ics));
    $events = [];
    $event  = null;

    foreach (explode("\n", $text) as $line) {
        if ($line === 'BEGIN:VEVENT') {
            $event = [];
            continue;
        }
        if ($line === 'END:VEVENT') {
            if ($event !== null) {
                $events[] = $event;
            }
            $event = null;
            continue;
        }
        if ($event === null || !preg_match('/^([A-Za-z0-9-]+)((?:;[^:;]+=(?:"[^"]*"|[^:;]*))*):(.*)$/', $line, $m)) {
            continue;
        }
        $params = [];
        preg_match_all('/;([^=;]+)=("[^"]*"|[^;]*)/', $m[2], $pm, PREG_SET_ORDER);
        foreach ($pm as $p) {
            $params[strtoupper($p[1])] = trim($p[2], '"');
        }
        $event[strtoupper($m[1])][] = ['params' => $params, 'value' => $m[3]];
    }
    return $events;
}

/** Undo iCalendar TEXT escaping. */
function stuv_events_unescape(string $value): string {
    return strtr($value, ['\\\\' => '\\', '\\n' => "\n", '\\N' => "\n", '\\,' => ',', '\\;' => ';']);
}

/**
 * [DateTimeImmutable, all_day]. UTC and TZID values keep their zone (RFC 5545 expands
 * there), floating values are Berlin time.
 */
function stuv_events_parse_date(array $prop): ?array {
    $value = trim($prop['value']);
    if (preg_match('/^\d{8}$/', $value) || ($prop['params']['VALUE'] ?? '') === 'DATE') {
        $dt = DateTimeImmutable::createFromFormat('!Ymd', substr($value, 0, 8), stuv_events_tz());
        return $dt ? [$dt, true] : null;
    }
    if (!preg_match('/^(\d{8}T\d{6})(Z?)$/', $value, $m)) {
        return null;
    }
    if ($m[2] === 'Z') {
        $tz = new DateTimeZone('UTC');
    } else {
        try {
            $tz = new DateTimeZone($prop['params']['TZID'] ?? 'Europe/Berlin');
        } catch (Exception $e) {
            $tz = stuv_events_tz();
        }
    }
    $dt = DateTimeImmutable::createFromFormat('Ymd\THis', $m[1], $tz);
    return $dt ? [$dt, false] : null;
}

/** Every date in every EXDATE line of an event, as Unix timestamps. */
function stuv_events_exdates(array $event): array {
    $out = [];
    foreach ($event['EXDATE'] ?? [] as $prop) {
        foreach (explode(',', $prop['value']) as $value) {
            $parsed = stuv_events_parse_date(['params' => $prop['params'], 'value' => $value]);
            if ($parsed) {
                $out[] = $parsed[0]->getTimestamp();
            }
        }
    }
    return $out;
}

/** RRULE as a part map, or null when it uses a part the expander does not know. */
function stuv_events_parse_rrule(string $value): ?array {
    $rule = [];
    foreach (explode(';', $value) as $pair) {
        [$key, $val] = array_pad(explode('=', $pair, 2), 2, '');
        $rule[strtoupper($key)] = $val;
    }
    if (array_diff(array_keys($rule), STUV_EVENTS_RRULE_PARTS)
        || !in_array($rule['FREQ'] ?? '', ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'], true)) {
        return null;
    }
    return $rule;
}

/** The nth weekday of $month ($n < 0 counts from the end), or null (a fifth Monday). */
function stuv_events_nth_weekday(DateTimeImmutable $month, int $n, int $weekday): ?DateTimeImmutable {
    $first = $month->modify('first day of this month');
    if ($n > 0) {
        $day = $first->modify('+' . (($weekday - (int) $first->format('N') + 7) % 7) . ' days')
            ->modify('+' . ($n - 1) . ' weeks');
    } else {
        $last = $first->modify('last day of this month');
        $day  = $last->modify('-' . (((int) $last->format('N') - $weekday + 7) % 7) . ' days')
            ->modify('-' . (-$n - 1) . ' weeks');
    }
    return $day->format('Y-m') === $month->format('Y-m') ? $day : null;
}

/**
 * Start times from $start up to $until_ts. DAILY, WEEKLY (BYDAY), MONTHLY (same day or one nth
 * weekday), YEARLY; INTERVAL, COUNT, UNTIL. COUNT counts before EXDATE, as RFC 5545 defines.
 */
function stuv_events_expand(DateTimeImmutable $start, array $rule, int $until_ts): array {
    $interval = max(1, (int) ($rule['INTERVAL'] ?? 1));
    $count    = isset($rule['COUNT']) ? (int) $rule['COUNT'] : null;
    $rule_end = null;
    if (isset($rule['UNTIL'])) {
        $parsed   = stuv_events_parse_date(['params' => [], 'value' => $rule['UNTIL']]);
        $rule_end = $parsed ? ($parsed[1] ? $parsed[0]->modify('+1 day')->getTimestamp() - 1 : $parsed[0]->getTimestamp()) : null;
    }
    $limit = $rule_end === null ? $until_ts : min($until_ts, $rule_end);

    $byday = array_values(array_filter(explode(',', $rule['BYDAY'] ?? '')));
    $freq  = $rule['FREQ'];
    if ($freq === 'MONTHLY' && $byday) {
        if (count($byday) !== 1 || !preg_match('/^([+-]?\d)(MO|TU|WE|TH|FR|SA|SU)$/', $byday[0], $nth)) {
            return [$start];
        }
    } elseif ($freq !== 'WEEKLY' && $byday) {
        return [$start];
    }

    $time = $start->format('H:i:s');
    $out  = [];
    $made = 0;
    for ($step = 0; $step < STUV_EVENTS_MAX_STEPS; $step++) {
        if ($freq === 'DAILY') {
            $candidates = [$start->modify('+' . ($step * $interval) . ' days')];
        } elseif ($freq === 'WEEKLY') {
            $days = $byday
                ? array_map(fn($d) => STUV_EVENTS_ICAL_DAYS[substr($d, -2)] ?? 0, $byday)
                : [(int) $start->format('N')];
            sort($days);
            $monday     = $start->modify('-' . ((int) $start->format('N') - 1) . ' days')
                ->modify('+' . ($step * $interval) . ' weeks');
            $candidates = [];
            foreach ($days as $d) {
                if ($d >= 1) {
                    $candidates[] = $monday->modify('+' . ($d - 1) . ' days')->modify($time);
                }
            }
        } elseif ($freq === 'MONTHLY') {
            $month = $start->modify('first day of this month')->modify('+' . ($step * $interval) . ' months');
            if ($byday) {
                $day = stuv_events_nth_weekday($month, (int) $nth[1], STUV_EVENTS_ICAL_DAYS[$nth[2]]);
                $candidates = $day ? [$day->modify($time)] : [];
            } else {
                $day = (int) $start->format('j');
                $candidates = $day <= (int) $month->format('t') ? [$month->setDate((int) $month->format('Y'), (int) $month->format('n'), $day)->modify($time)] : [];
            }
        } else {
            $year = (int) $start->format('Y') + $step * $interval;
            $day  = $start->setDate($year, (int) $start->format('n'), (int) $start->format('j'));
            $candidates = $day->format('m-d') === $start->format('m-d') ? [$day] : [];
        }

        foreach ($candidates as $candidate) {
            if ($candidate < $start) {
                continue;
            }
            if ($candidate->getTimestamp() > $limit || ($count !== null && $made >= $count)) {
                return $out;
            }
            $out[] = $candidate;
            $made++;
        }
    }
    return $out;
}

/** German labels in Berlin time: badge `day` over `month`, `weekday` and `time`, `day_month` for screen readers. */
function stuv_events_labels(DateTimeImmutable $start, DateTimeImmutable $end, bool $all_day): array {
    $start = $start->setTimezone(stuv_events_tz());
    $end   = $end->setTimezone(stuv_events_tz());
    // DTEND is exclusive.
    $last = $all_day ? $end->modify('-1 day') : $end->modify('-1 second');

    $time = $all_day ? 'Ganztägig' : $start->format('G:i') . ' Uhr';
    if ($last->format('Y-m-d') > $start->format('Y-m-d')) {
        $until = STUV_EVENTS_WEEKDAYS_SHORT[(int) $last->format('N')] . ', ' . $last->format('j') . '. '
            . STUV_EVENTS_MONTHS_SHORT[(int) $last->format('n')];
        $time = $all_day ? 'Bis ' . $until : $time . ' bis ' . $until;
    }

    return [
        'weekday'   => STUV_EVENTS_WEEKDAYS[(int) $start->format('N')],
        'day_month' => $start->format('j') . '. ' . STUV_EVENTS_MONTHS[(int) $start->format('n')],
        'day'       => $start->format('j'),
        'month'     => STUV_EVENTS_MONTHS_SHORT[(int) $start->format('n')],
        'time'      => $time,
    ];
}

/** The place as a short line: its first comma-separated part, never a link. */
function stuv_events_place(string $location): string {
    $first = trim(explode(',', stuv_events_unescape($location))[0]);
    return preg_match('#^[a-z]+://#i', $first) ? '' : $first;
}

/**
 * Occurrences not ended by $now that start within $days, sorted, at most $max and at most
 * STUV_EVENTS_PER_SERIES per series (UID), so the cache still holds the next one after the first
 * passes. Cancelled ones are left out.
 */
function stuv_events_build(string $ics, DateTimeImmutable $now, int $days, int $max): array {
    $horizon = $now->modify("+$days days")->getTimestamp();
    $events  = stuv_events_parse_ics($ics);

    // Instances replaced by an override; the override is listed on its own.
    $overridden = [];
    foreach ($events as $event) {
        if (isset($event['RECURRENCE-ID'][0])) {
            $rid = stuv_events_parse_date($event['RECURRENCE-ID'][0]);
            if ($rid) {
                $overridden[($event['UID'][0]['value'] ?? '') . '@' . $rid[0]->getTimestamp()] = true;
            }
        }
    }

    $out = [];
    foreach ($events as $event) {
        $start = isset($event['DTSTART'][0]) ? stuv_events_parse_date($event['DTSTART'][0]) : null;
        if (!$start || strtoupper($event['STATUS'][0]['value'] ?? '') === 'CANCELLED') {
            continue;
        }
        [$first, $all_day] = $start;
        $end = isset($event['DTEND'][0]) ? stuv_events_parse_date($event['DTEND'][0]) : null;
        $duration = $end
            ? $end[0]->getTimestamp() - $first->getTimestamp()
            : ($all_day ? 86400 : 0);

        $uid  = $event['UID'][0]['value'] ?? '';
        $rule = isset($event['RRULE'][0]) && !isset($event['RECURRENCE-ID'])
            ? stuv_events_parse_rrule($event['RRULE'][0]['value'])
            : null;
        $starts = $rule ? stuv_events_expand($first, $rule, $horizon) : [$first];
        $skip   = array_flip(stuv_events_exdates($event));

        foreach ($starts as $occ) {
            $ts = $occ->getTimestamp();
            if (isset($skip[$ts]) || ($rule && isset($overridden["$uid@$ts"]))) {
                continue;
            }
            // All-day spans move by days, so DST doesn't shift them.
            $occ_end = $all_day
                ? $occ->modify('+' . max(1, (int) round($duration / 86400)) . ' days')
                : $occ->modify("+$duration seconds");
            if ($occ_end <= $now || $ts > $horizon) {
                continue;
            }
            $berlin_start = $occ->setTimezone(stuv_events_tz());
            $out[] = [
                'series' => $uid,
                'start'  => $berlin_start->format('Y-m-d\TH:i'),
                'end'    => $occ_end->setTimezone(stuv_events_tz())->format('Y-m-d\TH:i'),
                'title'  => trim(stuv_events_unescape($event['SUMMARY'][0]['value'] ?? '')),
                'place'  => stuv_events_place($event['LOCATION'][0]['value'] ?? ''),
            ] + stuv_events_labels($occ, $occ_end, $all_day);
        }
    }

    usort($out, fn($a, $b) => [$a['start'], $a['title']] <=> [$b['start'], $b['title']]);
    $per_series = [];
    $out = array_filter($out, function ($occ) use (&$per_series) {
        $per_series[$occ['series']] = ($per_series[$occ['series']] ?? 0) + 1;
        return $per_series[$occ['series']] <= STUV_EVENTS_PER_SERIES;
    });
    return array_slice(array_values($out), 0, $max);
}
