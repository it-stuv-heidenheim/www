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
for f in $(git ls-files 'data/*.html'); do
  node $SKILL/scripts/blockcheck/validate_blocks.cjs "$f"
done | grep -E ': [1-9][0-9]* invalid'
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
weiter. Die Validator-Schleife im Kurzdurchlauf findet solche Blöcke vorher.

`validate_blocks.cjs` liest **nur sein erstes Argument**. Übergibst du einen
Glob, prüft er eine Datei, ignoriert den Rest und gibt trotzdem einen sauberen
Durchlauf aus. Deshalb läuft die Schleife Datei für Datei. Das Muster
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

Die Unittests der `tools/`-Skripte brauchen kein Netz und kein Pillow, nur die
Standardbibliothek:

```bash
python3 -m unittest discover -s tools -p "test_*.py" -v
```

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

```bash
source .env
python3 .agents/skills/wordpress-default-editor/scripts/deploy.py \
  --manifest data/manifest.json all --dry-run
```

Der Dry-Run prüft, ob die Quelldateien vorhanden sind, ob das Block-Markup
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
Ausgabe nennt ihn); `EDITED` heißt, kein Commit hatte diesen Stand, er wurde
also in wp-admin geändert (Exit 3). Über ein `EDITED`-Ziel schreibt `deploy.py`
nur mit `--overwrite`.
Den Page-Cache von WP-Optimize umgeht das Skript, weil es die REST-API liest und
nicht das Frontend.

### Nach dem `global-styles`-Deploy

WordPress' REST-Sanitizer kann Teile des Custom-CSS entfernen. Deshalb gehört
`verify_global_css.py` zu diesem Deploy dazu (Aufruf in `AGENTS.md`, Erklärung
in `docs/tools.md`).

## Was keine dieser Prüfungen sieht

Die Prüfungen oben lesen Quelltext; gerendert wird nichts. Kontraste rechnet
`test_styles.py` aus, aber ob die Seite gut aussieht und auf ein Handy passt,
siehst du nur, wenn du hinschaust:

- Seite aufrufen, hell **und** dunkel.
- Das Fenster auf 360px Breite ziehen: Nichts darf seitlich scrollen, Buttons
  stehen untereinander und berühren sich nicht.
- Einmal mit der Tab-Taste durch die Seite: Jeder Link, auch jede ganze Karte,
  zeigt einen sichtbaren Ring.
- Bei Kartenänderungen die drei Deploy-Ziele zusammen deployen, sonst liegt das
  alte Bild unter der neuen Geometrie (`docs/tools.md`).

Wenn etwas schiefgegangen ist:

```bash
python3 .agents/skills/wordpress-default-editor/scripts/rollback.py <id> \
  --endpoint pages
```

Vor jedem Schreibvorgang legt der Client ein Backup unter
`/tmp/wp_backup/<site-slug>/` ab. Medien deckt `rollback.py` nicht ab.

Nach einem Deploy über die Action liegen die Backups im Artefakt
`wp-backup-<Nummer>` des Laufs. Entpackt nach `/tmp/wp_backup/` findet
`rollback.py` sie, sofern `WP_SITE` in der `.env` genau so lautet wie in der
Action. Meist einfacher: den Commit mit `git revert` zurücknehmen und die Action
erneut starten.
