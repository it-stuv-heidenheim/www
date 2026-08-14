# Plugins

Vier WordPress-Plugins liegen in `wp-plugin/`: `stuv-mensa` (Live-Speiseplan),
`stuv-theme` (Dark-Mode-Umschalter), `stuv-dsgvo` (Klick-zum-Laden für die
Kalender-Embeds) und `stuv-seo` (Meta-Tags und strukturierte Daten). Alle vier
existieren, weil sich ihr Zweck nicht mit Block-HTML und CSS erreichen lässt.

`wp-plugin/` ist die Quelle der Wahrheit. Die Kopien auf dem Server sind
Artefakte — wer sie dort direkt bearbeitet, verliert die Änderung beim nächsten
Upload.

| Plugin       | Zweck                                 | Bei Deaktivierung                                                                                                                                                             |
| ------------ | ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `stuv-mensa` | Live-Speiseplan der Mensa             | Speiseplan verschwindet von der Studentenleben-Seite                                                                                                                          |
| `stuv-theme` | Dark-Mode-Umschalter                  | Seite friert im Hellmodus ein, Schalter verschwindet                                                                                                                          |
| `stuv-dsgvo` | Kalender lädt erst nach Klick         | Kalender verschwindet, stattdessen ein Link zu Google                                                                                                                         |
| `stuv-seo`   | Meta/OG/Twitter + strukturierte Daten | Die Tags fehlen einfach, sonst nichts — außer dass Seiten mit gesetztem „Von Suchmaschinen ausschließen“ wieder indexierbar werden und der Staging-Host in den Index gelangte |

Kein Ausfall hinterlässt einen toten Button oder eine Fehlermeldung, nur die
Funktion fehlt.

## Warum überhaupt Plugins

`deploy.py` deployt sie nicht — Plugins reisen nicht über die Content-REST-API.
Der Weg ist: Zip builden, in wp-admin hochladen, aktivieren.

Warum nicht einfach ein `<script>` in einen Block? Auf diesem Server ist
`unfiltered_html` aktiv, Skript-Tags in Block-Inhalten überleben den
REST-Schreibvorgang also unbeschadet. Das gilt aber nur, solange der
Deploy-Benutzer Administrator ist und `DISALLOW_UNFILTERED_HTML` nicht gesetzt
wird. Jede Härtung des Servers würde die Skripte stillschweigend entfernen —
ohne Fehler, ohne Warnung. JavaScript gehört deshalb in ein Plugin mit
ordentlichem Enqueue, nie in Block-HTML.

Es sind normale Plugins statt `mu-plugins` (must-use, laden automatisch und
sind nicht deaktivierbar), weil es keinen Shell-Zugang zum Host gibt und ohne
den kommt man nicht nach `wp-content/mu-plugins/`. Gäbe es irgendwann SSH, wäre
der Umzug dorthin eine reine Verbesserung und bräuchte keine Code-Änderung.

## Builden und installieren

```bash
./wp-plugin/build.sh              # alle vier builden
./wp-plugin/build.sh stuv-mensa   # nur eines
```

Ergebnis: `wp-plugin/<plugin>.zip` (git-ignoriert, es ist ein Artefakt).

Installation: wp-admin → Plugins → Installieren → **Plugin hochladen** → Zip
auswählen → Aktivieren. Bei einem Update fragt WordPress, ob die vorhandene
Version ersetzt werden soll — ja.

## `stuv-mensa` — der Speiseplan

Der Speiseplan kommt von `api.dhbw.app`. Der Browser kann diese API nicht
direkt aufrufen: Sie sendet keine CORS-Header, der Aufruf scheitert an der
Same-Origin-Policy. Das Plugin holt die Daten serverseitig und liefert sie
same-origin aus:

```
Browser  →  /wp-json/stuv/v1/mensa  →  WordPress  →  api.dhbw.app
         ←        JSON              ←   (Cache)    ←
```

Zwei öffentliche, nur lesende REST-Routen:

| Route                               | Zweck                                      |
| ----------------------------------- | ------------------------------------------ |
| `/wp-json/stuv/v1/mensa`            | der normalisierte Speiseplan               |
| `/wp-json/stuv/v1/mensa/image/<id>` | Gerichtsbild, durchgereicht statt verlinkt |

Die Bild-Route streamt das Bild durch den Server, damit **keine Besucher-IP bei
`api.dhbw.app` landet**. Dieselbe Überlegung wie bei den Karten
(`docs/tools.md`).

Weil dabei fremde Bytes von der **eigenen** Domain ausgeliefert werden, prüft
`stuv_mensa_safe_image_type()` den `Content-Type` von upstream auf dem Weg nach
draußen — nicht nur beim Cachen. Alles, was kein `image/*` ist, geht als
`application/octet-stream` raus, dazu `X-Content-Type-Options: nosniff`;
`image/svg+xml` ist trotz `image/*` ausgeschlossen, weil ein direkt
aufgerufenes SVG eigenes Skript im Kontext dieser Domain ausführen würde. Die
Id-Allowlist bleibt die erste Verteidigungslinie, aber sie soll nicht die
einzige sein.

> **Wenn der Speiseplan spurlos verschwindet:** Das Plugin gibt die
> Endpunkt-URL per `rest_url()` an das Skript weiter. Liefert `/wp-json/`
> gerade 404 — etwa weil die Rewrite-Regeln fehlen —, dann zeigt auch diese
> URL ins Leere, und `mensa.js` bricht absichtlich still ab: Die Seite wirkt
> normal, der Speiseplan ist nur unsichtbar. Erste Prüfung deshalb immer der
> `curl` unten. Behoben wird das in wp-admin unter **Einstellungen →
> Permalinks → Speichern**; danach kommt der Speiseplan von allein zurück.
> (Am 26.07.2026 war genau das der Fall.)

### Der Cache

`inc/cache.php`. Die Regeln, kurz:

- **Kalter Cache** → holen. Die ersten Besucher warten, aber sie bekommen Daten.
- **Warmer Cache, abgelaufen, jemand holt gerade** → das Alte ausliefern.
  Niemand wartet, und die Upstream-API bekommt genau eine Anfrage statt
  hunderter (der „Stampede“-Schutz: eine Sperre, die nach 60 Sekunden von selbst
  verfällt).

Veraltet-aber-sofort schlägt Aktuell-aber-langsam: Der Speiseplan darf ein paar
Minuten alt sein, ein hängender Seitenaufbau wäre schlimmer. Laufzeiten stehen
als Konstanten oben in `stuv-mensa.php` (`STUV_MENSA_TTL` und Verwandte).

Eine Obergrenze für das Alter gibt es dabei nicht: Fällt `api.dhbw.app` länger
aus, wird der alte Stand weiter ausgeliefert. Damit daraus keine Falschauskunft
wird, wirft `dropPastDays()` in `mensa.js` beim Rendern alle Tage weg, die
inzwischen vorbei sind — sonst würde ein vergangener Montag als „Nächster
Speiseplan“ beschriftet. Bleibt nichts übrig, greift der bereits vorhandene
Endzustand „Zurzeit ist kein Speiseplan verfügbar.“

### Beim Ändern beachten

Die Version steht an zwei Stellen — im Plugin-Header und in
`STUV_MENSA_VERSION`. Sie müssen übereinstimmen: Die Konstante hängt an
`assets/mensa.js` als Cache-Buster. Wer nur eine anzieht, liefert neues PHP mit
altem JavaScript aus.

Zwei Eigenheiten der Upstream-API, die die Normalisierung (`inc/normalize.php`)
abfängt und die man nicht für Bugs halten sollte:

- Daten werden als lokale Mitternacht in UTC gestempelt.
- Das Allergen-Feld ist immer leer.

## `stuv-theme` — der Dark-Mode

Druckt ein Inline-`<script>` in den `<head>`, das `.dark` auf `<html>` setzt —
aus `localStorage['stuv-theme']`, ersatzweise aus der Betriebssystem-Einstellung
(`prefers-color-scheme`). Danach behandelt es Klicks auf `.stuv-theme-option`
per Event-Delegation vom `document` aus.

Der Schalter in der Kopfzeile ist ein `<details>`-Aufklappmenü mit drei Zeilen:
**Hell**, **Dunkel**, **System**. Das Icon am Schalter zeigt immer das Thema,
das gerade zu sehen ist — Sonne oder Mond, im System-Modus also je nach
Betriebssystem-Einstellung. Welcher der drei Modi eingestellt ist, verrät der
Haken neben der aktiven Zeile. Escape und ein Klick außerhalb schließen das
Menü; beides erledigt das Plugin, `<details>` kann es nicht von sich aus.

Inline und im `<head>`: Die Klasse muss vor dem ersten Bildaufbau stehen,
sonst sieht ein Dark-Mode-Besucher kurz eine weiße Seite aufblitzen. Eine
extern geladene Datei wäre dafür zu spät. Technisch geht das über ein
`wp_register_script`-Handle ohne `src` plus `wp_add_inline_script`.

Das Skript setzt außerdem `.stuv-theme-ready` auf `<html>`, und das ist es, was
den Schalter sichtbar macht — `component.css` versteckt `.stuv-theme-switch`
standardmäßig. Plugin deaktiviert oder JavaScript aus → kein Schalter statt
eines toten Schalters.

Drei Teile an drei Orten. Wer einen ändert, muss die anderen kennen:

| Teil   | Ort                                                   |
| ------ | ----------------------------------------------------- |
| Logik  | `wp-plugin/stuv-theme/stuv-theme.php`                 |
| Styles | der `:root.dark`-Block in `data/styles/component.css` |
| Markup | der `wp:html`-Block in `data/header_blocks.html`      |

Nur der erste Teil ist ein Plugin-Upload; die anderen beiden sind normale
Deploys (`global-styles` bzw. `header`).

## `stuv-dsgvo` — die Kalender-Embeds

Die beiden Google-Kalender (Startseite „Anstehende Events“, Events-Seite) würden
beim Seitenaufbau ungefragt Daten an Google übertragen — darunter die IP-Adresse
jedes Besuchers. Das Plugin schiebt einen Hinweis davor: Erst ein Klick auf
„Kalender laden“ setzt die URL ein.

Der Trick steckt im Markup, nicht im Plugin. Die `<iframe>`-Elemente in den
Seiteninhalten tragen **kein `src`**, sondern `data-stuv-src`. Ein Browser lädt
daraus nichts — auch dann nicht, wenn das Plugin aus ist oder JavaScript nicht
läuft. Das ist die wichtige Eigenschaft: Der Ausfall geht in die sichere
Richtung, nie versehentlich zu Google.

Damit dabei kein leerer 600-Pixel-Kasten stehen bleibt, versteckt
`component.css` jedes `iframe[data-stuv-src]`, und im Block-HTML steht sichtbar
ein `.stuv-dsgvo-fallback`-Absatz mit Link zum Kalender bei Google. Läuft das
Plugin, blendet es diesen Absatz wieder aus (`.stuv-dsgvo-ready` auf dem
Wrapper) und baut stattdessen den Platzhalter.

Die Zustimmung wird pro Gerät gemerkt, in
`localStorage['stuv-dsgvo-calendar']`. Wer den Kalender einmal geladen hat,
bekommt ihn auf der anderen Seite und beim nächsten Besuch direkt zu sehen.
Früher war das bewusst nicht so — ein gespeicherter Klick heißt, dass ein
späterer Seitenaufruf ohne neue Handlung an Google geht. Getragen wird die
Speicherung von ihrem Gegenstück: Unter einem geladenen Kalender steht **immer**
eine Zeile „Nicht mehr automatisch laden“ (`.stuv-dsgvo-revoke`). Die darf
weder verschwinden noch hinter einem Menü liegen — der Widerruf muss so einfach
sein wie die Zustimmung. Ein Klick darauf löscht den Eintrag und tauscht das
`<iframe>` gegen einen frischen Klon ohne `src`; ein bloßes Leeren von `src`
würde Googles Dokument im Rahmen weiterlaufen lassen.

Browser, die `localStorage` blockieren (privater Modus, „alle Cookies
blockieren“), lassen schon den Lesezugriff werfen. Deshalb steht jeder Zugriff
in einem `try/catch`: Ein solches Gerät fragt dann eben jedes Mal neu — nie
bricht der Klick-Handler ab.

Die Karten (`docs/tools.md`) bleiben davon unberührt: Sie sind selbst gehostet
und laden gar nicht erst extern, brauchen also nie eine Zustimmung.

Drei Teile an drei Orten:

| Teil   | Ort                                                                                                     |
| ------ | ------------------------------------------------------------------------------------------------------- |
| Logik  | `wp-plugin/stuv-dsgvo/stuv-dsgvo.php`                                                                   |
| Styles | die `.stuv-dsgvo-*`-Regeln in `data/styles/component.css`                                               |
| Markup | die `wp:html`-Blöcke in `data/sections/02-was-wir-bieten.html` und `data/pages/events/02-upcoming.html` |

Beim Ändern beachten: Das Skript wird nur eingebunden, wenn der Seiteninhalt die
Zeichenkette `data-stuv-src` enthält (`stuv_dsgvo_has_embed()`). Ein Embed in
einem Template-Part, einem Widget oder einem wiederverwendbaren Block würde
dabei durchrutschen und nie laden — dann diese Prüfung entfernen, statt ihr
weitere Fundorte beizubringen.

Der Datenschutzhinweis verlinkt auf die Datenschutzerklärung von Google. Die
verlinkte AStA-Datenschutzerklärung (`legal.dhbw-asta.de`) nennt Google
Analytics, Maps, Forms und Fonts, aber **keinen Google Kalender** — wer sie
pflegt, sollte einen Absatz dazu ergänzen. Diese Seite liegt außerhalb dieses
Repos.

## `stuv-seo` — Meta-Tags und strukturierte Daten

Das SEO-Plugin ist das einzige, das auf jeder Seite sichtbar nichts ändert: Es
liefert in den `<head>` eine Meta-Beschreibung, den Open-Graph-Satz,
`twitter:card` und strukturierte Daten (`Organization` auf der Startseite,
`FAQPage` auf Kummer Karsten, abgeleitet aus dessen `<details>`-Blöcken).
Titel und Canonical fasst es nicht an — beides liefert Core bereits korrekt
(kein zweites Canonical, kein Titel-Override). Damit ist Deaktivieren folgenlos
für das Layout, und nur zwei Verhalten hängen am Plugin: Das Flag „Von
Suchmaschinen ausschließen“ je Seite (fällt **auch** aus der Sitemap) und der
Staging-Riegel.

**Beschreibungen leben in der Datenbank, nicht im Repo.** `_stuv_seo_description`
ist Post-Meta, im SEO-Kasten unter jeder Seite bearbeitbar. Bewusst kein
`seo`-Objekt im Manifest: Ein Wert im Repo plus ein Wert in der Datenbank wäre
ein System mit zwei Schreibern und keinem Schiedsrichter, und `deploy.py`
schreibt ohnehin kein `meta`-Feld — eine Bearbeitung in wp-admin kann also nie
zu Drift gegen die committeten Quellen werden. Das Sicherheitsnetz für die
Beschreibungen ist das Site-Backup und der WordPress-Export, dieselbe
Absicherung wie für die Seitentitel.

**Der Staging-Riegel ist invertiert.** `STUV_SEO_PRODUCTION_HOSTS` (eine
Konstante im Code, keine Option) entscheidet, ob die Seite indexiert werden
darf: Jeder Host außer Produktion bekommt `noindex`, eine abgeschaltete Sitemap
und eine `robots.txt` mit `Disallow: /`. Deaktiviert man das Plugin, wird
Staging indexierbar.

**Einen zweiten Riegel gibt es bislang nicht.** Frühere Fassungen dieser Doku
nannten einen nginx-`X-Robots-Tag` auf `dev.` als Gurt hinter dem Plugin — den
gibt es nicht. Nachgemessen am 6. August 2026: kein `x-robots-tag` auf `/`,
`/robots.txt` oder `/wp-sitemap.xml`, die `robots.txt` ist unverändert die von
WordPress mitgelieferte samt `Sitemap:`-Zeile, und die Startseite trägt kein
`noindex` — das Plugin ist auf Staging also auch noch nicht aktiviert.
`dev.stuv-heidenheim.de` ist damit im Moment vollständig crawlbar. Der Header
steht als offene Aufgabe im Todo; bis dahin hängt alles am Plugin allein.

**Die 301-Karte für alte Slugs** (`inc/redirects.php`) ist ein reiner
404-Auffang über `template_redirect` und liefert mit 302 aus, solange die
Slug-Liste nicht aus der alten Site geholt ist. Solange sie leer ist, kostet
sie auf jedem normalen Request nichts. Die Ziele sind **wurzelrelative Pfade**
(`/studentenleben/`), keine vollständigen URLs: Geprüft wird jedes Ziel mit
`wp_validate_redirect()`, und das lässt nur den Host von `home_url()` durch —
ein `https://stuv-heidenheim.de/…` als Ziel würde auf `dev.` (und auf einer
`www.`-Produktion) durchfallen. Fällt ein Ziel durch, bleibt es beim 404, statt
Besucher nach wp-admin zu schicken.

Dazu eine Einstellungsseite unter Einstellungen → StuV SEO (Standard-Vorschaubild,
Google-Search-Console-Token) und eine **Startcheckliste**, die für alle Seiten
Titellänge (nur Anzeige — der Titel wird bewusst nicht übersteuert),
Beschreibungslänge und Vorschaubild anzeigt. Das ist der Ersatz für ein
SEO-Dashboard, das niemand im Vorstand lesen will.

Beim Ändern beachten: Die Version steht im Plugin-Header und in
`STUV_SEO_VERSION` und muss übereinstimmen (sie hängt an `assets/admin.js` als
Cache-Buster). Die puren Helfer in `inc/pure/` dürfen keine WordPress-Funktion
aufrufen — sie laufen unter `php wp-plugin/tests/test_seo_*.php` ohne WordPress.

## PHP-Formatierung

Prettier formatiert das PHP hier nicht. Es könnte es, aber nur mit
`@prettier/plugin-php` als echt installierter Abhängigkeit — und das Repo hat
kein `package.json` (siehe `AGENTS.md`). Den umgebenden Stil von Hand treffen.

`.prettierignore` deckt zusätzlich `wp-plugin/tests/fixtures/` ab: mitgeschnittene
Antworten von `api.dhbw.app`, die byteweise unverändert bleiben müssen, sonst
sind sie keine gültigen Fixtures mehr.

## Plugins auf der Live-Site prüfen

```bash
HOST="$(printf '%s' "$WP_SITE" | sed -E 's#^https?://##')"
curl -sS -A "stuv-check/1.0" "https://$HOST/wp-json/stuv/v1/mensa" | head -c 200
```

JSON mit Speiseplan = ok. `rest_no_route` = `stuv-mensa` ist nicht aktiv. Eine
404-HTML-Seite dagegen heißt, dass `/wp-json/` selbst nicht geht — dann sind
die Permalinks dran, nicht das Plugin (siehe oben).

Welche Plugins überhaupt aktiv sind, beantwortet diese Abfrage:

```bash
curl -sS -u "$WP_USER:$WP_APP_PASS" "https://$HOST/wp-json/wp/v2/plugins" |
  python3 -c "import sys,json;[print(p['status'], p['plugin']) for p in json.load(sys.stdin)]"
```

Für `stuv-dsgvo` reicht ein Blick in den Quelltext einer Seite mit Kalender: Ist
das Plugin aktiv, steht dort ein Inline-Skript mit `stuv-dsgvo-placeholder`.
Fehlt es, bleibt der Fallback-Link stehen — genau das soll passieren.

Die Tests selbst stehen in `docs/testing.md`.
