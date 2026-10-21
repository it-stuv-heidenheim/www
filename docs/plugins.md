# Plugins

Drei WordPress-Plugins liegen in `wp-plugin/`: `stuv-mensa` (Live-Speiseplan),
`stuv-theme` (Dark-Mode-Umschalter) und `stuv-dsgvo` (Klick-zum-Laden für die
Kalender-Embeds). Jedes davon macht etwas, das Block-HTML und CSS allein nicht
können.

`wp-plugin/` ist die Quelle der Wahrheit. Die Kopien auf dem Server sind
Artefakte; wer sie dort direkt bearbeitet, verliert die Änderung beim nächsten
Upload.

| Plugin       | Zweck                         | Bei Deaktivierung                                     |
| ------------ | ----------------------------- | ----------------------------------------------------- |
| `stuv-mensa` | Live-Speiseplan der Mensa     | Speiseplan verschwindet von der Studentenleben-Seite  |
| `stuv-theme` | Dark-Mode-Umschalter          | Seite friert im Hellmodus ein, Schalter verschwindet  |
| `stuv-dsgvo` | Kalender lädt erst nach Klick | Kalender verschwindet, stattdessen ein Link zu Google |

Fällt ein Plugin aus, fehlt nur seine Funktion. Es bleibt kein toter Button und
keine Fehlermeldung zurück.

## Warum überhaupt Plugins

Plugins gehen nicht über die Content-REST-API, also deployt `deploy.py` sie
auch nicht. Stattdessen baust du ein Zip, lädst es in wp-admin hoch und
aktivierst es.

Ein `<script>` direkt in einem Block würde heute funktionieren: Auf diesem
Server ist `unfiltered_html` aktiv, Skript-Tags in Block-Inhalten überstehen den
REST-Schreibvorgang also. Das gilt aber nur, solange der Deploy-Benutzer
Administrator ist und niemand `DISALLOW_UNFILTERED_HTML` setzt. Jede Härtung des
Servers würde die Skripte ohne Fehler und ohne Warnung entfernen. JavaScript
gehört deshalb in ein Plugin mit ordentlichem Enqueue, nie in Block-HTML.

Es sind normale Plugins und keine `mu-plugins` (must-use, laden automatisch und
lassen sich nicht deaktivieren), weil es keinen Shell-Zugang zum Host gibt und
man ohne ihn nicht nach `wp-content/mu-plugins/` kommt. Mit SSH wäre der Umzug
dorthin eine Verbesserung, die keine Code-Änderung bräuchte.

## Builden und installieren

```bash
./wp-plugin/build.sh              # alle drei builden
./wp-plugin/build.sh stuv-mensa   # nur eines
```

Ergebnis: `wp-plugin/<plugin>.zip` (git-ignoriert, es ist ein Artefakt).

Installation: wp-admin → Plugins → Installieren → **Plugin hochladen** → Zip
auswählen → Aktivieren. Bei einem Update fragt WordPress, ob die vorhandene
Version ersetzt werden soll; das bestätigst du.

## `stuv-mensa`: der Speiseplan

Der Speiseplan kommt von `api.dhbw.app`. Der Browser kann diese API nicht
direkt aufrufen: Sie sendet keine CORS-Header, und die Same-Origin-Policy
blockiert den Aufruf. Das Plugin holt die Daten deshalb serverseitig und
liefert sie von der eigenen Domain aus:

```
Browser  →  /wp-json/stuv/v1/mensa  →  WordPress  →  api.dhbw.app
         ←        JSON              ←   (Cache)    ←
```

Zwei öffentliche, nur lesende REST-Routen:

| Route                               | Zweck                                      |
| ----------------------------------- | ------------------------------------------ |
| `/wp-json/stuv/v1/mensa`            | der normalisierte Speiseplan               |
| `/wp-json/stuv/v1/mensa/image/<id>` | Gerichtsbild, durchgereicht statt verlinkt |

Die Bild-Route streamt das Bild durch den Server, damit `api.dhbw.app` keine
Besucher-IP sieht. Bei den Karten gilt dieselbe Überlegung (`docs/tools.md`).

Weil so fremde Bytes von der eigenen Domain kommen, prüft
`stuv_mensa_safe_image_type()` den `Content-Type` von upstream beim Cachen und
noch einmal bei jeder Auslieferung. Alles, was kein `image/*` ist, geht als
`application/octet-stream` raus, dazu `X-Content-Type-Options: nosniff`.
`image/svg+xml` ist trotz `image/*` ausgeschlossen, weil ein direkt aufgerufenes
SVG eigenes Skript im Kontext dieser Domain ausführen würde. Die Id-Allowlist
bleibt die erste Verteidigungslinie, soll aber nicht die einzige sein.

> **Wenn der Speiseplan spurlos verschwindet:** Das Plugin gibt die
> Endpunkt-URL per `rest_url()` an das Skript weiter. Liefert `/wp-json/`
> gerade 404, etwa weil die Rewrite-Regeln fehlen, zeigt auch diese URL ins
> Leere, und `mensa.js` bricht absichtlich ohne Meldung ab: Die Seite wirkt
> normal, nur der Speiseplan fehlt. Prüfe in diesem Fall zuerst mit dem `curl`
> unten. Beheben lässt sich das in wp-admin unter **Einstellungen →
> Permalinks → Speichern**; danach erscheint der Speiseplan wieder.

### Der Cache

Die Regeln aus `inc/cache.php`:

- Kalter Cache: holen. Die ersten Besucher warten, bekommen aber Daten.
- Warmer Cache, abgelaufen, und ein anderer Request holt gerade: den alten
  Stand ausliefern. Niemand wartet, und die Upstream-API bekommt eine einzige
  Anfrage statt hunderter. Das ist der „Stampede“-Schutz, eine Sperre, die nach
  60 Sekunden von selbst verfällt.

Ein Speiseplan, der ein paar Minuten alt ist, stört weniger als ein hängender
Seitenaufbau. Die Laufzeiten stehen als Konstanten oben in `stuv-mensa.php`
(`STUV_MENSA_TTL` und Verwandte).

Eine Obergrenze für das Alter gibt es nicht: Fällt `api.dhbw.app` länger aus,
liefert das Plugin weiter den alten Stand. Damit daraus keine Falschauskunft
wird, wirft `dropPastDays()` in `mensa.js` beim Rendern alle Tage weg, die
schon vorbei sind; sonst stünde ein vergangener Montag als „Nächster
Speiseplan“ da. Bleibt nichts übrig, zeigt die Seite den Endzustand „Zurzeit
ist kein Speiseplan verfügbar.“

### Beim Ändern beachten

Die Version steht an zwei Stellen, im Plugin-Header und in
`STUV_MENSA_VERSION`, und beide müssen übereinstimmen: Die Konstante hängt als
Cache-Buster an `assets/mensa.js`. Wer nur eine erhöht, liefert neues PHP mit
altem JavaScript aus.

Zwei Eigenheiten der Upstream-API fängt die Normalisierung
(`inc/normalize.php`) ab. Beide sind keine Bugs:

- Die API stempelt Daten als lokale Mitternacht in UTC.
- Das Allergen-Feld ist immer leer.

## `stuv-theme`: der Dark Mode

Das Plugin druckt ein Inline-`<script>` in den `<head>`, das `.dark` auf
`<html>` setzt, und zwar nach `localStorage['stuv-theme']`, ersatzweise nach der
Betriebssystem-Einstellung (`prefers-color-scheme`). Danach behandelt es Klicks
auf `.stuv-theme-option` per Event-Delegation vom `document` aus.

Der Schalter in der Kopfzeile ist ein `<details>`-Aufklappmenü mit drei Zeilen:
Hell, Dunkel und System. Das Icon am Schalter zeigt das Thema, das gerade zu
sehen ist, also Sonne oder Mond; im System-Modus hängt das von der
Betriebssystem-Einstellung ab. Den eingestellten Modus markiert ein Haken neben
der aktiven Zeile. Escape und ein Klick außerhalb schließen das Menü. Beides
erledigt das Plugin, weil `<details>` es nicht von sich aus kann.

Das Skript steht inline im `<head>`, weil die Klasse vor dem ersten Bildaufbau
gesetzt sein muss. Sonst sieht ein Dark-Mode-Besucher kurz eine weiße Seite
aufblitzen, und eine extern geladene Datei käme dafür zu spät. Technisch läuft
das über ein `wp_register_script`-Handle ohne `src` plus
`wp_add_inline_script`.

Das Skript setzt außerdem `.stuv-theme-ready` auf `<html>`, und erst diese
Klasse macht den Schalter sichtbar; `component.css` versteckt
`.stuv-theme-switch` standardmäßig. Ist das Plugin deaktiviert oder JavaScript
aus, erscheint gar kein Schalter, also auch kein toter.

Die drei Teile liegen an drei Orten, und wer einen ändert, muss die anderen
kennen:

| Teil   | Ort                                                   |
| ------ | ----------------------------------------------------- |
| Logik  | `wp-plugin/stuv-theme/stuv-theme.php`                 |
| Styles | der `:root.dark`-Block in `data/styles/component.css` |
| Markup | der `wp:html`-Block in `data/header_blocks.html`      |

Nur der erste Teil ist ein Plugin-Upload; die anderen beiden sind normale
Deploys (`global-styles` bzw. `header`).

### Das Apple-Touch-Icon

Nebenbei tauscht das Plugin das Apple-Touch-Icon aus. Das Website-Icon in
WordPress ist ein einziges Bild für alle Größen, also liefert WordPress das
transparente `stuv-dhbw-favicon.png` auch an iOS aus, und iOS füllt
Transparenz mit Schwarz. Der Filter auf `site_icon_meta_tags` verweist
stattdessen auf `stuv-dhbw-apple-touch-icon.png` (180 × 180, weißer
Hintergrund, kommt mit dem `media`-Deploy). Liegt die Datei noch nicht in den
Uploads, bleibt der Tag von WordPress stehen, damit kein Link ins Leere zeigt.

Erzeugt aus `.stuv-dhbw-favicon.svg`:

```bash
rsvg-convert -w 132 -h 132 data/media/.stuv-dhbw-favicon.svg |
  magick - -background white -gravity center -extent 180x180 -alpha off \
    -strip PNG24:data/media/stuv-dhbw-apple-touch-icon.png
```

## `stuv-dsgvo`: die Kalender-Embeds

Die beiden Google-Kalender (Startseite „Anstehende Events“, Events-Seite) würden
beim Seitenaufbau ungefragt Daten an Google übertragen, darunter die IP-Adresse
jedes Besuchers. Das Plugin schiebt einen Hinweis davor, und erst ein Klick auf
„Kalender laden“ setzt die URL ein.

Den Schutz leistet das Markup. Die `<iframe>`-Elemente in den Seiteninhalten
haben kein `src`, nur ein `data-stuv-src`, aus dem ein Browser nichts lädt. Das
gilt auch, wenn das Plugin aus ist oder JavaScript nicht läuft: Fällt etwas aus,
geht trotzdem keine Anfrage an Google.

Damit dabei kein leerer 600-Pixel-Kasten stehen bleibt, versteckt
`component.css` jedes `iframe[data-stuv-src]`, und im Block-HTML steht sichtbar
ein `.stuv-dsgvo-fallback`-Absatz mit Link zum Kalender bei Google. Läuft das
Plugin, blendet es diesen Absatz aus (`.stuv-dsgvo-ready` auf dem Wrapper) und
baut stattdessen den Platzhalter.

Die Zustimmung merkt sich das Plugin pro Gerät in
`localStorage['stuv-dsgvo-calendar']`. Wer den Kalender einmal geladen hat,
sieht ihn auf der anderen Seite und beim nächsten Besuch sofort. Damit geht ein
späterer Seitenaufruf aber ohne neuen Klick an Google. Vertretbar ist das nur,
weil es ein Gegenstück gibt: Unter einem geladenen Kalender steht **immer** eine
Zeile „Nicht mehr automatisch laden“ (`.stuv-dsgvo-revoke`). Sie darf weder
verschwinden noch hinter einem Menü liegen, denn der Widerruf muss so einfach
sein wie die Zustimmung. Ein Klick darauf löscht den Eintrag und ersetzt das
`<iframe>` durch einen frischen Klon ohne `src`. Würde das Skript nur `src`
leeren, liefe Googles Dokument im Rahmen weiter.

Browser, die `localStorage` blockieren (privater Modus, „alle Cookies
blockieren“), werfen schon beim Lesen eine Exception. Deshalb steht jeder
Zugriff in einem `try/catch`: Ein solches Gerät fragt dann jedes Mal neu, aber
der Klick-Handler bricht nie ab.

Die Karten (`docs/tools.md`) betrifft das alles nicht. Sie sind selbst gehostet,
laden nichts von außen und brauchen deshalb keine Zustimmung.

Auch hier drei Teile an drei Orten:

| Teil   | Ort                                                                                                     |
| ------ | ------------------------------------------------------------------------------------------------------- |
| Logik  | `wp-plugin/stuv-dsgvo/stuv-dsgvo.php`                                                                   |
| Styles | die `.stuv-dsgvo-*`-Regeln in `data/styles/component.css`                                               |
| Markup | die `wp:html`-Blöcke in `data/sections/02-was-wir-bieten.html` und `data/pages/events/02-upcoming.html` |

Beim Ändern beachten: Das Plugin bindet sein Skript nur ein, wenn der
Seiteninhalt die Zeichenkette `data-stuv-src` enthält
(`stuv_dsgvo_has_embed()`). Ein Embed in einem Template-Part, einem Widget oder
einem wiederverwendbaren Block fiele durch diese Prüfung und würde nie laden.
Entferne in dem Fall die Prüfung, statt ihr weitere Fundorte beizubringen.

Der Datenschutzhinweis verlinkt auf die Datenschutzerklärung von Google. Die
verlinkte AStA-Datenschutzerklärung (`legal.dhbw-asta.de`) nennt Google
Analytics, Maps, Forms und Fonts, aber **keinen Google Kalender**. Wer sie
pflegt, sollte einen Absatz dazu ergänzen; die Seite liegt außerhalb dieses
Repos.

## Plugins auf der Live-Site prüfen

```bash
HOST="$(printf '%s' "$WP_SITE" | sed -E 's#^https?://##')"
curl -sS -A "stuv-check/1.0" "https://$HOST/wp-json/stuv/v1/mensa" | head -c 200
```

Kommt JSON mit Speiseplan zurück, ist alles in Ordnung. `rest_no_route` heißt,
dass `stuv-mensa` nicht aktiv ist. Eine 404-HTML-Seite dagegen heißt, dass
`/wp-json/` selbst nicht antwortet; dann liegt es an den Permalinks und nicht am
Plugin (siehe oben).

Welche Plugins aktiv sind, zeigt diese Abfrage:

```bash
curl -sS -u "$WP_USER:$WP_APP_PASS" "https://$HOST/wp-json/wp/v2/plugins" |
  python3 -c "import sys,json;[print(p['status'], p['plugin']) for p in json.load(sys.stdin)]"
```

Für `stuv-dsgvo` reicht ein Blick in den Quelltext einer Seite mit Kalender: Ist
das Plugin aktiv, steht dort ein Inline-Skript mit `stuv-dsgvo-placeholder`.
Fehlt es, bleibt der Fallback-Link stehen, und so ist es auch gewollt.

Die Tests selbst stehen in `docs/testing.md`.
