# Prüfen und Testen

Alles hier läuft lokal, vor dem Deploy. Dieselben Prüfungen (ohne Dry-Run und
ohne die Schritte nach dem Deploy) laufen außerdem bei jedem Push in GitHub
Actions (`.github/workflows/checks.yml`). Die Deploy-Action
(`.github/workflows/deploy.yml`) führt sie vor jedem Deploy aus, dazu den
Dry-Run und die Prüfungen nach dem Deploy (`docs/ai-workflow.md`). Die Befehle
unten brauchst du für lokale Läufe.

## Der Kurzdurchlauf

Vor jedem Commit:

```bash
npx prettier --check .
python3 -m unittest discover -s tools -p "test_*.py"
```

Vor jedem Deploy zusätzlich:

```bash
source .env
SKILL=.agents/skills/wordpress-default-editor
node $SKILL/scripts/blockcheck/validate_blocks.cjs $(git ls-files 'data/*.html') \
  | grep -E ': [1-9][0-9]* invalid'
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json all --dry-run
```

Gibt die `grep`-Zeile nichts aus, sind alle Blöcke gültig.

## Die einzelnen Prüfungen

### Formatierung

```bash
npx prettier --check .    # prüfen
npx prettier --write .    # korrigieren
```

Prettier formatiert Block-HTML, CSS, JSON, Markdown und JS. Für PHP bräuchte es
`@prettier/plugin-php` als installierte Abhängigkeit, und das Repo hat kein
`package.json`; den PHP-Stil musst du also von Hand treffen.

Ein Formatierlauf ändert die Bytes **aller** Deploy-Ziele, nicht nur die der
bearbeiteten Datei, und der nächste Deploy schreibt dann alles neu. Inhaltlich
ändert sich dabei nichts.

### Block-Validierung

Gutenberg vergleicht gespeichertes Markup mit dem, was der Block selbst erzeugen
würde. Weicht es ab, meldet der Editor „Dieser Block enthält unerwarteten oder
ungültigen Inhalt“, und wer nur einen Text ändern wollte, kommt dann nicht
weiter. Der Validator-Aufruf im Kurzdurchlauf findet solche Blöcke vorher.

`validate_blocks.cjs` nimmt beliebig viele Dateien und prüft sie in einem
Prozess. Das Laden des Gutenberg-Parsers dauert rund zwei Sekunden, die Dateien
selbst gehen schnell; ein Aufruf pro Datei bräuchte für den ganzen Baum über
eine Minute. Für jede Datei steht eine Zeile `=== <datei>: N invalid` in der
Ausgabe. Das Muster
`'data/*.html'` ist Absicht: Gits `*` passt auch über Schrägstriche hinweg und
erfasst damit alle Dateien im Baum. `'data/**/*.html'` würde
`header_blocks.html` und `footer_blocks.html` verfehlen, die in keinem
Unterverzeichnis liegen.

### Generierte Dateien

So prüfst du, ob die committeten generierten Dateien noch zu ihren Quellen
passen (Details in `docs/tools.md`):

```bash
python3 tools/gen_map.py campus --check
python3 tools/gen_map.py stadtgebiet --check
python3 tools/gen_map.py stadtzentrum --check

npm install --prefix /tmp/phosphor @phosphor-icons/core@2.1.1 >/dev/null
PHOSPHOR_ICON_DIR=/tmp/phosphor/node_modules/@phosphor-icons/core/assets/regular \
  python3 tools/gen_icon_css.py --check
```

Erwartet: keine Ausgabe, Exit 0. Drift heißt, dass jemand eine generierte Datei
von Hand bearbeitet oder eine Quelle geändert hat, ohne neu zu generieren.

### Der Tool-Code

Die Unittests der `tools/`-Skripte (Aufruf im Kurzdurchlauf, mit `-v` für jede
Testzeile) brauchen kein Netz und kein Pillow, nur die Standardbibliothek:

- `test_gen_map.py` prüft die Geometrie: Projektion, Kachelmathematik,
  Pin-Platzierung. Es testet gegen `data/maps/campus.json` selbst und nicht
  gegen eine Kopie. Eine abgeschriebene Fixture würde unbemerkt von der echten
  Karte abweichen, und die Tests prüften dann Pins, die es nicht mehr gibt.
- `test_map_data.py` prüft die committeten Kartendaten. Eine Kartendatei kann
  syntaktisch fehlerfrei und trotzdem unbrauchbar sein, etwa mit einem Pin
  außerhalb des Bildes oder einem Render, der so groß ist, dass WordPress ihn
  beim Upload herunterrechnet. Dann zeigt die `source_url` nicht mehr auf das
  Bild, das wir gebaut haben. Beides fängt diese Datei ab.
- `test_content.py` prüft das Block-HTML aller Deploy-Ziele auf das, was der
  Gutenberg-Validator durchlässt: interne Links und Anker, die es nicht gibt;
  Linktexte wie „Zur Seite“ oder gleicher Text mit verschiedenen Zielen; Block-
  JSON, das etwas anderes sagt als das `style`-Attribut daneben (der Editor
  übernimmt beim nächsten Öffnen den JSON-Wert, und die Seite sieht plötzlich
  anders aus); unbalancierte Tags; `stuv-`-Klassen, die `component.css` nicht
  kennt; Kontaktadressen, die nicht in der Liste `CONTACTS` stehen (ein
  vertippter Instagram-Name oder eine falsche Krisennummer fällt so auf); und
  den Krisenhinweis, der auf Kummer Karsten vor dem Formular stehen muss. Eine
  neue Kontaktadresse trägst du dort in `CONTACTS` ein.
- `test_styles.py` rechnet die Farbtoken aus `component.css` und
  `global-styles.json` so aus wie der Browser und prüft die Kontraste, die
  Besucher sehen: Text auf Seite, Band und Karte, Fokusring, Formularränder,
  hell und dunkel. Dazu Regeln für `component.css` selbst: kein
  `outline: none`, Fokus als Outline statt Schatten (den entfernt der
  Windows-Kontrastmodus), ein Fokusring auf der Karte für jede Klasse eines
  kartenfüllenden Links, keine abgeschnittenen Texte mit `…`.

### Der Skill

Die Tests des Deploy-Toolings brauchen als Einzige in diesem Repo Pakete
außerhalb der Standardbibliothek: `pytest` und `flask`, Letzteres für einen
nachgebauten WordPress-Server, gegen den `deploy.py` und der REST-Client
schreiben. Am einfachsten in einer virtuellen Umgebung:

```bash
cd .agents/skills/wordpress-default-editor
python3 -m venv .venv && .venv/bin/pip install -r tests/requirements.txt
.venv/bin/python -m pytest -q
```

### Die Plugins

Ohne Abhängigkeiten, ohne Netz, ohne WordPress:

```bash
php wp-plugin/tests/test_normalize.php
php wp-plugin/tests/test_cache.php
php wp-plugin/tests/test_theme.php
TZ=America/Los_Angeles node --test 'wp-plugin/tests/*.test.js'
```

Die Zeitzone ist Absicht. Der Speiseplan rechnet in Europe/Berlin, und der Test
soll zeigen, dass das auch stimmt, wenn die Maschine woanders steht: Um 00:30
Uhr Berliner Zeit muss ein Besucher in Los Angeles den richtigen Berliner Tag
sehen. In der eigenen Zeitzone ausgeführt, beweist der Test nichts.

Die Fixtures in `wp-plugin/tests/fixtures/` sind mitgeschnittene Antworten von
`api.dhbw.app`. Sie stehen in `.prettierignore` und müssen Byte für Byte
unverändert bleiben, sonst sind sie keine Aufzeichnung mehr.

`test_theme.php` deckt die Jahreszahl im Copyright der Fußzeile ab, die
`stuv-theme` beim Ausliefern aktualisiert. Der Rest von `stuv-theme` und
`stuv-dsgvo` ist Browser-Code, den du von Hand prüfst. `stuv-dsgvo` testest du dreimal: mit
aktivem Plugin (Platzhalter, ein Klick lädt den Kalender), mit deaktiviertem
Plugin und mit abgeschaltetem JavaScript. In keinem der drei Fälle darf ein
leerer Kasten stehen bleiben oder beim Seitenaufbau eine Anfrage an
`calendar.google.com` gehen (Netzwerk-Tab der Entwicklerwerkzeuge).

Ein vierter Durchgang prüft die gespeicherte Zustimmung: Kalender laden, auf die
andere Seite wechseln (dort lädt er jetzt direkt), unter dem Kalender „Nicht
mehr automatisch laden“ klicken und neu laden. Dann muss der Platzhalter zurück
sein, und beim Seitenaufbau darf wieder nichts an `calendar.google.com` gehen.
Danach dasselbe in einem privaten Fenster mit blockiertem Speicher: Dort fragt
die Seite jedes Mal neu, aber in der Konsole darf keine Exception erscheinen.

### Der Dry-Run

Der Dry-Run (Aufruf im Kurzdurchlauf) prüft, ob die Quelldateien vorhanden sind, ob das Block-Markup
balanciert ist, und zeigt die Bytezahlen. Er kontaktiert den Server **nicht**
und vergleicht nichts mit dem, was dort liegt. Ein sauberer Dry-Run heißt also,
dass die Dateien hochladbar sind; ob das Ergebnis richtig aussieht, sagt er
nicht. Ob eine Page-ID zur gemeinten Seite gehört, zeigt erst die Prüfung nach
dem echten Deploy.

### Nach jedem Deploy

```bash
source .env
python3 .agents/skills/wordpress-default-editor/scripts/verify_deploy.py \
  --manifest data/manifest.json
```

`verify_deploy.py` holt jedes Deploy-Ziel über die REST-API und vergleicht es
mit seiner Quelle im Repo. Nur dieser Schritt belegt, dass die Site ausliefert,
was hier steht. Exit 0 heißt, alles stimmt überein; 1 heißt Drift, 2 heißt, ein
Ziel ließ sich nicht abrufen. Mit `--diff` siehst du, was sich unterscheidet.
Mit `--history` sucht es den Live-Stand eines abweichenden Ziels in der
Git-Historie: `BEHIND` heißt, die Seite zeigt einen älteren Commit (die
Ausgabe nennt ihn) oder ist leer, etwa eine neu angelegte; `EDITED` heißt, kein Commit hatte diesen Stand, er wurde
also in wp-admin geändert (Exit 3). Über ein `EDITED`-Ziel schreibt `deploy.py`
nur mit `--overwrite`.
Den Page-Cache von WP-Optimize umgeht das Skript, weil es die REST-API liest und
nicht das Frontend.

### Nach dem `global-styles`-Deploy

WordPress' REST-Sanitizer kann Teile des Custom-CSS entfernen. Deshalb gehört
`verify_global_css.py` zu diesem Deploy dazu (Aufruf in `AGENTS.md`, Erklärung
in `docs/tools.md`).

## Überwachung zwischen den Deploys

Die Action **Monitor** (`.github/workflows/monitor.yml`) liest die Live-Site,
ohne etwas zu schreiben. Sie läuft im Environment `monitor`, ohne Freigabe
(Einrichtung in `docs/ai-workflow.md`), und lässt sich unter **Actions →
Monitor → Run workflow** auch von Hand starten; dann laufen alle Prüfungen.

Täglich:

- `verify_deploy.py --history`: Ein Ziel, das in wp-admin geändert wurde
  (`EDITED`), lässt den Lauf scheitern. So fällt die Änderung am Tag danach auf
  und nicht erst beim nächsten Deploy, der dann abbricht. `BEHIND` gibt nur
  eine Warnung: Auf `main` liegen Commits, die noch niemand deployt hat.
- `tools/check_plugins.py`: Jedes Plugin aus `wp-plugin/` muss installiert,
  aktiv und in derselben Version sein. Ein vergessener Zip-Upload fällt sonst
  niemandem auf.
- `tools/site_state.py` vergleicht, was nur in wp-admin eingestellt wird, mit
  `data/site-state.json`: Einstellungen, Theme, aktive Plugins, Seiten (Titel,
  Slug, Status, Template), Dateien der Mediathek, die nicht in `data/media/`
  liegen (in wp-admin hochgeladen oder im Repo gelöscht), die SEO-Angaben jeder
  Seite (Titel, Beschreibung, Vorschaubild) und die Felder der beiden
  Formulare. Bei einer Abweichung zeigt das Log den Diff. War die Änderung
  gewollt, `python3 tools/site_state.py --write` ausführen und die Datei
  committen; sonst die Einstellung in wp-admin zurücksetzen. Deployt wird die
  Datei nie, und E-Mail-Adressen stehen absichtlich nicht darin, weil das Repo
  öffentlich ist (`docs/architecture.md`).

Montags:

- `tools/check_links.py` ruft jeden externen Link der Seiten einmal auf.
  `BROKEN` (404, 410, eine Domain ohne DNS-Eintrag, ein ungültiges Zertifikat,
  jeweils auch beim zweiten Versuch) lässt den Lauf scheitern; `WARN` (etwa 403
  von einem Bot-Schutz oder ein Timeout) und `MOVED` (Link landet auf einer
  anderen Domain) sind Hinweise. Instagram, WhatsApp, Google Maps und der
  Abo-Link des Kalenders lassen sich so nicht prüfen und werden übersprungen.

Alle drei laufen auch lokal, die ersten beiden nach `source .env`:

```bash
python3 .agents/skills/wordpress-default-editor/scripts/verify_deploy.py \
  --manifest data/manifest.json --history
python3 tools/check_plugins.py
python3 tools/site_state.py
python3 tools/check_links.py
```

Scheitert ein geplanter Lauf, schickt GitHub eine Mail an die Person, die den
Zeitplan in `monitor.yml` zuletzt geändert hat. In einem öffentlichen Repo
schaltet GitHub geplante Workflows nach 60 Tagen ohne Commit ab; dann unter
**Actions → Monitor** wieder einschalten.

## Was keine dieser Prüfungen sieht

Die Prüfungen oben lesen Quelltext; gerendert wird nichts. Kontraste rechnet
`test_styles.py` aus, aber ob die Seite gut aussieht und auf ein Handy passt,
zeigt nur die gerenderte Seite. Nach jeder Änderung am Layout:

- Seite aufrufen, hell **und** dunkel.
- Das Fenster auf 360px Breite ziehen: Nichts darf seitlich scrollen, Buttons
  stehen untereinander und berühren sich nicht.
- Einmal mit der Tab-Taste durch die Seite: Jeder Link, auch jede ganze Karte,
  zeigt einen sichtbaren Ring.

Wenn etwas schiefgegangen ist:

```bash
python3 .agents/skills/wordpress-default-editor/scripts/rollback.py <id> \
  --endpoint pages
```

Vor jedem Schreibvorgang legt der Client ein Backup unter
`/tmp/wp_backup/<site-slug>/` ab. Für ein Bild, das `replace_media()` unter
derselben URL ersetzt hat, liegt die alte Datei unter
`/tmp/wp_backup/<site-slug>/media/`; zurück kommt sie mit
`rollback.py --media <dateiname>`. Ein neu hochgeladenes Bild, das vorher nicht
in der Mediathek war, braucht kein Backup: Die Datei liegt in `data/media/`.

Nach einem Deploy über die Action liegen die Backups im Artefakt
`wp-backup-<Nummer>` des Laufs. Entpackt nach `/tmp/wp_backup/` findet
`rollback.py` sie, sofern `WP_SITE` in der `.env` genau so lautet wie in der
Action. Meist einfacher: den Commit mit `git revert` zurücknehmen und die Action
erneut starten.
