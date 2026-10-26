# Tools

Zwei Generatoren in `tools/` schreiben Dateien ins Repo, die normal deployt werden. Generiertes **nie von Hand bearbeiten**, sondern die Quelle ändern und neu generieren; der nächste Lauf überschreibt Handänderungen. `--check` rendert neu und vergleicht, ohne zu schreiben (Exit 1: Drift).

| Generiert                                                        | Von               | Quelle             |
| ---------------------------------------------------------------- | ----------------- | ------------------ |
| Karten-Blöcke in `02-campus-karte.html` und `09-freizeit.html`   | `gen_map.py`      | `data/maps/*.json` |
| `data/media/karte-*.webp`                                        | `gen_map.py`      | `data/maps/*.json` |
| Abschnitt zwischen den `gen_icon_css`-Markern in `component.css` | `gen_icon_css.py` | Phosphor-SVGs      |

## `gen_map.py`: Karten

Statische Karten (`campus`, `stadtgebiet`, `stadtzentrum`) mit Pins und Legende. Die CARTO-Kacheln lädt das Skript beim Bauen, damit kein Besucher seine IP an einen Kartenanbieter schickt. `stadtzentrum` ist die Detailkarte zu `stadtgebiet`, weil sich die Orte im Zentrum überlagern.

```bash
python3 tools/gen_map.py campus --render --write   # Bilder und Block neu
python3 tools/gen_map.py campus --check            # Drift? (schreibt nichts)
python3 tools/gen_map.py campus --preview /tmp/campus.png   # Pins zur Kontrolle
```

`--render`, `--preview` und `--check` brauchen Pillow, `--write` und `--check` zusätzlich `npx prettier`. Jede Karte hat ein helles und ein dunkles Bild; umgeschaltet wird per CSS über `.dark`, damit der Theme-Schalter gilt.

**Kartenwechsel deployen:** Ein neues Bild behält seinen Dateinamen, und den überspringt der `media`-Deploy (ein zweiter Upload landete als unverlinktes `-1`). Also beide Bilder mit `--replace` hochladen, dann ein `changed`-Deploy (Seite und `global-styles`). Undo: `rollback.py --media <datei>`. Das `?v=` in der URL ändert sich mit dem Inhalt, der Browser-Cache greift also nicht.

```bash
source .env
SKILL=.agents/skills/wordpress-default-editor
python3 $SKILL/scripts/upload_media.py --replace data/media/karte-campus-light.webp data/media/karte-campus-dark.webp
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json changed
```

## `gen_icon_css.py`: Icons

Schreibt die `--ico-*`-Properties ([Phosphor](https://phosphoricons.com/), „regular“, als Data-URI in Markenfarbe, nutzbar als Maske und als Hintergrundbild). Die Version ist gepinnt, weil ein Sprung jedes Icon neu zeichnet. Die Token-Namen stammen noch aus lucide; `ICONS` im Skript ordnet jedem Token ein Phosphor-Icon zu.

```bash
npm install --prefix /tmp/phosphor @phosphor-icons/core@2.1.1
export PHOSPHOR_ICON_DIR=/tmp/phosphor/node_modules/@phosphor-icons/core/assets/regular
python3 tools/gen_icon_css.py --write
python3 tools/gen_icon_css.py --check
```

Nach einem `global-styles`-Deploy prüft `deploy.py` per `verify_global_css.py`, ob der REST-Sanitizer die Data-URIs entfernt hat (Exit 2); dann müssten sie in den `core/html`-Block des Headers.
