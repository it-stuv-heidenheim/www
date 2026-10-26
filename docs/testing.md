# Prüfen und Testen

`checks.yml` führt die Prüfungen bei jedem Push aus, die Deploy-Action vor jedem Deploy ([ai-workflow.md](ai-workflow.md)). Lokal:

```bash
# vor jedem Commit
npx prettier --check .            # --write korrigiert
python3 -m unittest discover -s tools -p "test_*.py"

# vor jedem Deploy zusätzlich (grep ohne Ausgabe: alle Blöcke gültig)
source .env
SKILL=.agents/skills/wordpress-default-editor
node $SKILL/scripts/blockcheck/validate_blocks.cjs $(git ls-files 'data/*.html') \
  | grep -E ': [1-9][0-9]* invalid'
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json all --dry-run
```

- **Prettier** formatiert HTML, CSS, JSON, Markdown, JS; PHP von Hand (kein `package.json`). Ein Formatierlauf ändert oft die Bytes vieler Deploy-Ziele, inhaltlich nichts.
- **Block-Validierung:** Weicht Markup von `save()` ab, meldet der Editor „unerwarteten oder ungültigen Inhalt“. Ein Prozess für alle Dateien (der Parser lädt 2 s); `'data/*.html'` erfasst dank Gits `*` auch Unterverzeichnisse und die Header-/Footer-Dateien.
- **Dry-Run:** Quellen vorhanden, Markup balanciert; fragt den Server nicht.

## Generierte Dateien

```bash
python3 tools/gen_map.py campus --check        # ebenso stadtgebiet, stadtzentrum
npm install --prefix /tmp/phosphor @phosphor-icons/core@2.1.1 >/dev/null
PHOSPHOR_ICON_DIR=/tmp/phosphor/node_modules/@phosphor-icons/core/assets/regular \
  python3 tools/gen_icon_css.py --check
```

Drift heißt: Generiertes von Hand bearbeitet oder Quelle nicht neu generiert ([tools.md](tools.md)).

## Unittests in `tools/`

Nur Standardbibliothek:

- `test_gen_map.py`: Projektion, Kacheln, Pins, gegen das echte `data/maps/campus.json`.
- `test_map_data.py`: Pins im Bild, Render unter WordPress' Herunterrechnen-Grenze.
- `test_content.py`: interne Links und Anker, nichtssagende oder mehrdeutige Linktexte, Block-JSON gegen `style`-Attribut, Tag-Balance, unbekannte `stuv-`-Klassen, Kontakte außerhalb von `CONTACTS` (neue dort eintragen), Krisenhinweis vor dem Formular auf Kummer Karsten.
- `test_styles.py`: Kontraste (Text, Fokusring, Formularränder; hell und dunkel), kein `outline: none`, Fokus als Outline, Fokusring für jede Kartenlink-Klasse, kein Abschneiden mit `…`.

## Skill und Plugins

```bash
cd .agents/skills/wordpress-default-editor
python3 -m venv .venv && .venv/bin/pip install -r tests/requirements.txt   # pytest, flask
.venv/bin/python -m pytest -q
cd -

php wp-plugin/tests/test_normalize.php
php wp-plugin/tests/test_cache.php
php wp-plugin/tests/test_theme.php
php wp-plugin/tests/test_ics.php
TZ=America/Los_Angeles node --test 'wp-plugin/tests/*.test.js'
```

Die fremde Zeitzone ist Absicht: Der Berliner Tag muss überall stimmen. Die JSON-Fixtures in `wp-plugin/tests/fixtures/` sind Mitschnitte von `api.dhbw.app` und bleiben Byte für Byte (`.prettierignore`); `events.ics` ist von Hand geschrieben (der echte Kalender enthält persönliche Daten), ein Termin je Fall.

`stuv-theme` und `stuv-dsgvo` sind sonst Browser-Code. `stuv-dsgvo` von Hand prüfen, mit Plugin, ohne Plugin und ohne JavaScript: nie ein leerer Kasten, beim Seitenaufbau keine Anfrage an `calendar.google.com` (Netzwerk-Tab). Dann: laden, neu laden (lädt direkt), „Nicht mehr automatisch laden“, neu laden (Platzhalter, keine Anfrage). Im privaten Fenster mit blockiertem Speicher: jedes Mal fragen, keine Exception.

## Nach dem Deploy

`deploy.py` liest jedes Ziel zurück und prüft nach `global-styles` die `markers` und den `icon_marker` aus `data/manifest.json` (eine neue, gefährdete Komponente bekommt dort einen Marker). Stand aller Ziele, auch ohne Deploy:

```bash
python3 .agents/skills/wordpress-default-editor/scripts/verify_deploy.py \
  --manifest data/manifest.json        # --diff zeigt Unterschiede, --history BEHIND/EDITED
```

Exit 0 gleich, 1 Drift, 2 nicht abrufbar, 3 `EDITED`. Es liest die REST-API, nicht den WP-Optimize-Cache.

Die Prüfungen lesen nur Quelltext. Nach jeder Layout-Änderung die Seite ansehen: hell **und** dunkel, 360px breit (kein seitliches Scrollen, Buttons berühren sich nicht), einmal mit Tab durch (jeder Link und jede Karte zeigt einen Ring).

## Rollback

```bash
python3 .agents/skills/wordpress-default-editor/scripts/rollback.py <id> --endpoint pages
python3 .agents/skills/wordpress-default-editor/scripts/rollback.py --media <dateiname>
```

Backups liegen unter `/tmp/wp_backup/<site-slug>/` (Bilder in `media/`); nach einem Action-Deploy im Artefakt `wp-backup-<Nummer>`, entpackt nach `/tmp/wp_backup/` nutzbar, wenn `WP_SITE` gleich lautet. Oft einfacher: `git revert` und neu deployen.

## Überwachung

Die Action **Monitor** (`monitor.yml`, Environment `monitor`) liest nur; von Hand gestartet laufen alle Prüfungen.

- Täglich `verify_deploy.py --history`: `EDITED` scheitert, `BEHIND` warnt (undeployte Commits).
- Täglich `tools/check_plugins.py`: jedes Plugin installiert, aktiv, gleiche Version.
- Täglich `tools/site_state.py`: wp-admin-Stand gegen `data/site-state.json`. Gewollte Änderung: `tools/site_state.py --write` und committen; sonst in wp-admin zurücksetzen.
- Montags `tools/check_links.py`: `BROKEN` scheitert, `WARN` und `MOVED` sind Hinweise.

```bash
source .env
python3 .agents/skills/wordpress-default-editor/scripts/verify_deploy.py \
  --manifest data/manifest.json --history
python3 tools/check_plugins.py
python3 tools/site_state.py
python3 tools/check_links.py
```

Fehlschläge mailt GitHub an die Person, die den Zeitplan zuletzt geändert hat. Nach 60 Tagen ohne Commit schaltet GitHub geplante Workflows ab; unter **Actions → Monitor** wieder einschalten.
