# Prüfen und Testen

Es gibt kein CI. Kein GitHub-Actions-Lauf prüft einen Push, kein Hook deployt
automatisch — die Gründe stehen in `docs/ai-workflow.md`. Alles hier läuft von
Hand, lokal, vor dem Deploy.

## Der Kurzdurchlauf

Vor jedem Commit:

```bash
npx prettier --check .
```

Vor jedem Deploy zusätzlich:

```bash
source .env
SKILL=~/.claude/skills/wordpress-default-editor
for f in $(git ls-files 'data/*.html'); do
  node $SKILL/scripts/blockcheck/validate_blocks.cjs "$f"
done | grep -E ': [1-9][0-9]* invalid'
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json all --dry-run
```

Keine Ausgabe der `grep`-Zeile heißt: alle Blöcke gültig.

## Die einzelnen Prüfungen

### Formatierung

```bash
npx prettier --check .    # prüfen
npx prettier --write .    # korrigieren
```

Prettier besitzt die Formatierung von Block-HTML, CSS, JSON, Markdown und JS.
PHP bräuchte ein installiertes Plugin, und das Repo hat keine npm-Abhängigkeiten
(`docs/plugins.md`).

Ein Formatierlauf ändert die Bytes **aller** Deploy-Ziele, nicht nur der
bearbeiteten Datei — der nächste Deploy schreibt alles neu. Keine inhaltliche
Änderung.

### Block-Validierung

Gutenberg vergleicht gespeichertes Markup mit dem, was der Block selbst erzeugen
würde. Weicht es ab, steht im Editor „Dieser Block enthält unerwarteten oder
ungültigen Inhalt“ — für jemanden, der nur einen Text ändern wollte, eine
Sackgasse. Der Validator fängt das vorher ab:

```bash
SKILL=~/.claude/skills/wordpress-default-editor
node $SKILL/scripts/blockcheck/validate_blocks.cjs data/pages/kontakt/01-pageheader.html
```

`validate_blocks.cjs` liest **nur sein erstes Argument**. Ein Glob übergeben
heißt: eine Datei wird geprüft, der Rest ignoriert, und die Ausgabe sieht nach
einem sauberen Durchlauf aus. Für den ganzen Baum eine Schleife, Datei für Datei:

```bash
SKILL=~/.claude/skills/wordpress-default-editor
for f in $(git ls-files 'data/*.html'); do
  node $SKILL/scripts/blockcheck/validate_blocks.cjs "$f"
done | grep -E ': [1-9][0-9]* invalid'
```

Das Muster `'data/*.html'` ist Absicht: Gits `*` überspringt Schrägstriche
nicht, erfasst also alle Dateien im Baum. `'data/**/*.html'` würde
`header_blocks.html` und `footer_blocks.html` verfehlen, die in keinem
Unterverzeichnis liegen.

### Generierte Dateien

Ob die committeten Generate noch zu ihren Quellen passen (Details:
`docs/tools.md`):

```bash
python3 tools/gen_map.py campus --check
python3 tools/gen_map.py stadtgebiet --check
python3 tools/gen_map.py stadtzentrum --check

npm install --prefix /tmp/lucide lucide-static@0.577.0 >/dev/null
LUCIDE_ICON_DIR=/tmp/lucide/node_modules/lucide-static/icons \
  python3 tools/gen_icon_css.py --check
```

Erwartet: keine Ausgabe, Exit 0. Drift heißt, jemand hat eine generierte Datei
von Hand bearbeitet oder eine Quelle geändert, ohne neu zu generieren.

### Der Tool-Code

Die Unittests der `tools/`-Skripte, kein Netz, kein Pillow, alles stdlib-only:

```bash
python3 -m unittest discover -s tools -p "test_*.py" -v
```

- `test_gen_map.py` prüft die **Geometrie** — Projektion, Kachelmathematik,
  Pin-Platzierung. Es testet gegen `data/maps/campus.json` selbst, nicht gegen
  eine Kopie: Eine abgeschriebene Fixture driftet unbemerkt von der echten
  Karte weg, und dann prüfen die Tests Pins, die es nicht mehr gibt.
- `test_map_data.py` prüft die **committeten Kartendaten**. Eine Kartendatei
  kann syntaktisch fehlerfrei und trotzdem unbrauchbar sein: ein Pin außerhalb
  des Bildes, oder ein Render so groß, dass WordPress es beim Upload
  herunterrechnet — womit die `source_url` nicht mehr auf das zeigt, was wir
  gebuildet haben. Beides fängt diese Datei ab.
- `test_build_skill_zip.py` prüft den **ZIP-Build des Tooling-Skills**: gegen
  ein Wegwerf-Git-Repo als Fixture, dass `SKILL.md` unter dem Prefix landet,
  installierte Abhängigkeiten (`node_modules/`, `.venv/`, …) draußen bleiben und
  nur der eine Skill eingepackt wird.
- `test_export_docs_wiki.py` prüft die Umschreibungen des Wiki-Exports: die
  **`wphtml`-Escape-Luke** (ein `wphtml`-Fence wird echtes Markup, ein
  gewöhnlicher `html`-Fence bleibt ein Code-Block), dass **root-relative Links
  absolut** werden — im Wiki würden sie sonst gegen `wiki.dhbw-asta.de`
  aufgelöst — und dass die **H1 zum Seitennamen** wird. Die wichtigsten Fälle
  sind die negativen: Der Export ist überwiegend Durchreichen, und was in einem
  Code-Fence steht, muss wörtlich stehen bleiben.

### Die Plugins

Ohne Abhängigkeiten, ohne Netz, ohne WordPress:

```bash
php wp-plugin/tests/test_normalize.php
php wp-plugin/tests/test_cache.php
php wp-plugin/tests/test_seo_tags.php
php wp-plugin/tests/test_seo_faq.php
php wp-plugin/tests/test_seo_routes.php
TZ=America/Los_Angeles node --test 'wp-plugin/tests/*.test.js'
```

Die Zeitzone ist Absicht: Der Speiseplan rechnet in Europe/Berlin, und der Test
stellt sicher, dass das auch dann stimmt, wenn die Maschine woanders steht. Um
00:30 Uhr Berliner Zeit muss ein Besucher in Los Angeles trotzdem den richtigen
Berliner Tag sehen. Läuft der Test in der eigenen Zeitzone, beweist er nichts.

Die Fixtures in `wp-plugin/tests/fixtures/` sind mitgeschnittene Antworten von
`api.dhbw.app`. Sie stehen in `.prettierignore` und müssen byteweise
unverändert bleiben, sonst sind sie keine Aufzeichnung mehr.

Die Tests decken `stuv-mensa` und die pure Schicht von `stuv-seo` ab. Der
Browser-Code wird von Hand geprüft: `stuv-dsgvo` einmal mit aktivem Plugin
(Platzhalter, Klick lädt den Kalender), einmal deaktiviert und einmal mit
abgeschaltetem JavaScript — in allen drei Fällen darf **kein** leerer Kasten
stehen bleiben und beim Aufbau der Seite darf keine Anfrage an
`calendar.google.com` gehen (Netzwerk-Tab der Entwicklerwerkzeuge).

`stuv-seo` hat zwei Stellen für die Handprüfung: `assets/admin.js` (Zeichenzähler
und Medienauswahl auf der Bearbeitungsseite und unter Einstellungen → StuV SEO —
einmal eine Beschreibung ändern und ein Vorschaubild wählen) und die
Deaktivierungsprobe (Plugin deaktivieren, alle sieben Seiten aufrufen: identisches
Layout, nur fehlende Tags — danach wieder aktivieren und prüfen, dass die
Beschreibungen noch dastehen).

Dazu kommt seit der gespeicherten Zustimmung ein vierter Durchgang: Kalender
laden, auf die andere Seite wechseln (er lädt jetzt direkt), unter dem Kalender
„Nicht mehr automatisch laden“ klicken, neu laden — der Platzhalter muss zurück
sein und wieder darf beim Seitenaufbau nichts an `calendar.google.com` gehen.
Danach dasselbe in einem privaten Fenster mit blockiertem Speicher: Dort wird
jedes Mal neu gefragt, aber nichts darf in der Konsole werfen.

### Der Dry-Run

```bash
source .env
python3 ~/.claude/skills/wordpress-default-editor/scripts/deploy.py \
  --manifest data/manifest.json all --dry-run
```

Prüft: Quelldateien vorhanden, Block-Markup balanciert, Bytezahlen. Er
kontaktiert den Server **nicht** und vergleicht **nicht** mit dem, was dort
liegt. Ein sauberer Dry-Run sagt „diese Dateien sind hochladbar“, nicht „das
Ergebnis wird richtig aussehen“. Ob eine Page-ID zur gemeinten Seite gehört,
zeigt erst der echte Deploy plus ein Blick auf die Seite.

### Nach dem `global-styles`-Deploy

WordPress' REST-Sanitizer kann am Custom-CSS schneiden, also gehört diese
Prüfung zum Deploy dazu — siehe `docs/design-system.md`.

## Was keine dieser Prüfungen sieht

Es gibt keinen Test für das Aussehen. Alle Prüfungen oben sind syntaktisch. Ob
die Seite gut aussieht, ob der Kontrast im Dark Mode reicht, ob die Karte auf
dem Handy passt — dafür gibt es nur Hinsehen:

- Seite aufrufen, hell **und** dunkel.
- Schmales Fenster ausprobieren.
- Bei Kartenänderungen: die drei Deploy-Ziele zusammen deployen, sonst liegt
  das alte Bild unter der neuen Geometrie (`docs/tools.md`).

Für Design-Review über alle Seiten hinweg gibt es den PDF-Export — der braucht
aber **jedes Mal** eine ausdrückliche Freigabe, weil er einen Browser
installiert und die Live-Site abruft (`docs/tools.md`).

Und wenn etwas schiefging:

```bash
python3 ~/.claude/skills/wordpress-default-editor/scripts/rollback.py <id> \
  --endpoint pages
```

Vor jedem Schreibvorgang legt der Client ein Backup unter
`/tmp/wp_backup/<site-slug>/` ab. Medien deckt `rollback.py` nicht ab.
