# Plugins

`wp-plugin/` ist die Quelle; Änderungen auf dem Server gehen beim nächsten Upload verloren. Fällt ein Plugin aus, fehlt nur seine Funktion, ohne toten Button oder Fehlermeldung.

| Plugin        | Zweck                         | Ohne Plugin                                   |
| ------------- | ----------------------------- | --------------------------------------------- |
| `stuv-mensa`  | Live-Speiseplan               | Speiseplan fehlt auf Studentenleben           |
| `stuv-events` | Nächste Termine als Liste     | Hinweis auf den Kalender                      |
| `stuv-theme`  | Dark-Mode-Umschalter          | immer hell, kein Schalter                     |
| `stuv-dsgvo`  | Kalender lädt erst nach Klick | kein Kalender, stattdessen ein Link zu Google |

JavaScript gehört in ein Plugin, nie in Block-HTML: `<script>` übersteht den REST-Schreibvorgang nur dank `unfiltered_html` und verschwände bei jeder Härtung kommentarlos. Normale Plugins statt `mu-plugins`, weil es keinen Shell-Zugang gibt.

## Bauen und installieren

```bash
./wp-plugin/build.sh              # alle, oder: ./wp-plugin/build.sh stuv-mensa
```

`wp-plugin/<plugin>.zip` in wp-admin → Plugins → Installieren → **Plugin hochladen**, Ersetzen bestätigen. Eine neue Version ändert Header-`Version` und `STUV_*_VERSION` zusammen (die Konstante ist Cache-Buster der JS-Datei; `tools/test_plugins.py` prüft es). Hängt Inhalt am Plugin: erst ZIP, dann Deploy.

## `stuv-mensa`

`api.dhbw.app` sendet keine CORS-Header, also holt WordPress den Plan und liefert ihn unter `/wp-json/stuv/v1/mensa` aus; Gerichtsbilder kommen über `/wp-json/stuv/v1/mensa/image/<id>`, damit upstream keine Besucher-IP sieht. Nur Ids aus dem aktuellen Plan werden ausgeliefert; `stuv_mensa_safe_image_type()` lässt nur Rasterbilder durch (kein SVG, sonst `application/octet-stream`, dazu `nosniff`).

Cache (`inc/cache.php`, Laufzeiten oben in `stuv-mensa.php`): kalt wird geholt; abgelaufen holt genau ein Request (Sperre 60 s), alle anderen bekommen den alten Stand, auch wenn upstream ausfällt. `dropPastDays()` in `mensa.js` wirft vergangene Tage weg; bleibt nichts, steht „Zurzeit ist kein Speiseplan verfügbar.“ `inc/normalize.php` fängt ab, dass upstream lokale Mitternacht als UTC stempelt; das Allergen-Feld ist immer leer.

Fehlt der Speiseplan spurlos, liefert meist `/wp-json/` 404 (Permalinks neu speichern, [content-editing.md](content-editing.md)); `mensa.js` bricht dann still ab.

## `stuv-events`

Startseite (4 Termine) und Events-Seite (8) zeigen die nächsten Termine aus dem öffentlichen Google-Kalender. Der Server holt den iCal-Feed (`STUV_EVENTS_FEED`), Besucher laden nichts von Google, also braucht es keine Einwilligung. Route `/wp-json/stuv/v1/events`, Cache wie bei `stuv-mensa` (30 min frisch), Antwort höchstens 2 MB.

`inc/ics.php` rechnet Serien aus: `DAILY`, `WEEKLY`, `MONTHLY` (selber Tag oder n-ter Wochentag), `YEARLY`, mit `INTERVAL`, `COUNT`, `UNTIL`, `EXDATE` und `RECURRENCE-ID`. Andere Regeln zeigen nur den ersten Termin; abgesagte fehlen. Ort: `LOCATION` bis zum ersten Komma, nie als Link. Die Antwort enthält die nächsten 120 Tage, höchstens 40 Termine und drei je Serie; `events.js` zeigt jede Serie einmal und verwirft Vergangenes. Der Browser parst keinen Zeitstempel (Berliner Uhrzeit als Text, fertige Beschriftungen).

Markup: `<div data-stuv-events data-stuv-events-limit="4">` mit sichtbarem `.stuv-events-fallback`, in `data/sections/02-was-wir-bieten.html` und `data/pages/events/02-upcoming.html`; Styles `.stuv-event*`.

## `stuv-theme`

Ein Inline-Skript im `<head>` setzt `.dark` auf `<html>` (aus `localStorage['stuv-theme']`, sonst `prefers-color-scheme`), bevor die Seite erscheint. Der Schalter ist ein `<details>`-Menü (Hell, Dunkel, System): Das Icon zeigt das sichtbare Thema, ein Haken den Modus; Escape und Klick außerhalb schließen es. `.stuv-theme-ready` macht den Schalter erst sichtbar.

| Teil   | Ort                                          | Deploy          |
| ------ | -------------------------------------------- | --------------- |
| Logik  | `wp-plugin/stuv-theme/stuv-theme.php`        | ZIP             |
| Styles | `:root.dark` in `data/styles/component.css`  | `global-styles` |
| Markup | `wp:html`-Block in `data/header_blocks.html` | `header`        |

Außerdem:

- **Apple-Touch-Icon:** iOS füllt das transparente Favicon schwarz, also verweist das Plugin auf `stuv-dhbw-apple-touch-icon.png`, sobald es hochgeladen ist. Erzeugt mit:

  ```bash
  rsvg-convert -w 132 -h 132 data/media/.stuv-dhbw-favicon.svg |
    magick - -background white -gravity center -extent 180x180 -alpha off \
      -strip PNG24:data/media/stuv-dhbw-apple-touch-icon.png
  ```

- **Copyright-Jahr:** ersetzt das erste Jahr nach `©` in einem Absatz `.stuv-copyright` durch das aktuelle; ohne Plugin bleibt das gespeicherte. `tools/test_content.py` verlangt die Klasse. Der WP-Optimize-Cache zeigt das alte Jahr, bis er abläuft.
- **Button-Stil `overlay`** („Auf Farbfläche“) im Editor; das Aussehen steht in `component.css`.

## `stuv-dsgvo`

Der Google-Kalender (Events, „Monatsansicht“) lädt erst nach Klick auf „Kalender laden“. Die `<iframe>`s haben nur `data-stuv-src`, kein `src`; ohne Plugin oder JS geht also nie eine Anfrage an Google. `component.css` versteckt `iframe[data-stuv-src]`, ein sichtbarer `.stuv-dsgvo-fallback`-Link bleibt, bis das Plugin übernimmt (`.stuv-dsgvo-ready`).

Die Zustimmung bleibt in `localStorage['stuv-dsgvo-calendar']`. Deshalb steht unter jedem geladenen Kalender **immer** sichtbar „Nicht mehr automatisch laden“ (`.stuv-dsgvo-revoke`): Widerruf so einfach wie Zustimmung. Er ersetzt das `<iframe>` durch einen Klon ohne `src`. Blockiertes `localStorage` heißt nur: jedes Mal fragen.

Das Skript lädt nur, wenn der Seiteninhalt `data-stuv-src` enthält (`stuv_dsgvo_has_embed()`); ein Embed in Template-Part, Widget oder wiederverwendbarem Block würde nie laden, dann die Prüfung entfernen. Markup: `data/pages/events/02-upcoming.html`.

Offen: Die AStA-Datenschutzerklärung (`legal.dhbw-asta.de`, außerhalb dieses Repos) nennt Google Kalender nicht.

## Live prüfen

```bash
source .env
python3 tools/check_plugins.py    # Version und Status; DIFFERS: ZIP bauen und hochladen
HOST="$(printf '%s' "$WP_SITE" | sed -E 's#^https?://##')"
curl -sS -A "stuv-check/1.0" "https://$HOST/wp-json/stuv/v1/mensa" | head -c 200
curl -sS -A "stuv-check/1.0" "https://$HOST/wp-json/stuv/v1/events" | head -c 300
```

`rest_no_route`: Plugin inaktiv. Eine 404-HTML-Seite: `/wp-json/` selbst antwortet nicht (Permalinks). `stuv-dsgvo` aktiv heißt: im Quelltext steht ein Inline-Skript mit `stuv-dsgvo-placeholder`.
