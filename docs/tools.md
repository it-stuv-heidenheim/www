# Tools

Drei Skripte in `tools/`. Keines spricht mit WordPress — alle erzeugen Dateien,
die über den normalen Deploy-Weg auf die Site kommen
(`docs/content-editing.md`): die beiden Generatoren unten und
`build_skill_zip.py`, das den Tooling-Skill als ZIP nach `data/media/` packt.
Das Deploy-Tooling selbst liegt woanders (`docs/ai-workflow.md`).

Zwei der drei sind Generatoren, deren Ergebnis im Repo liegt. Generierte
Dateien **nie von Hand bearbeiten** — die Änderung überlebt bis zum nächsten
Generatorlauf und verschwindet dann ohne Fehlermeldung. Die Quelle bearbeiten
und neu generieren.

Betroffen sind:

| Generierte Datei                                                             | Erzeugt von       | Quelle                                                      |
| ---------------------------------------------------------------------------- | ----------------- | ----------------------------------------------------------- |
| `data/pages/studentenleben/02-campus-karte.html`                             | `gen_map.py`      | `data/maps/campus.json`                                     |
| Karten-Blöcke in `.../09-freizeit.html`                                      | `gen_map.py`      | `data/maps/stadtgebiet.json`, `data/maps/stadtzentrum.json` |
| `data/media/karte-*.webp` (6 Bilder)                                         | `gen_map.py`      | `data/maps/*.json`                                          |
| Abschnitt zwischen den `gen_icon_css`-Markern in `data/styles/component.css` | `gen_icon_css.py` | lucide-static-SVGs                                          |

Beide Generatoren haben ein `--check`: rendert neu, vergleicht, schreibt nichts.
Exit-Code 1 heißt, die committete Datei passt nicht mehr zu ihrer Quelle.

---

## `gen_map.py` — die Karten

Erzeugt die statischen Karten (Campus, Stadtgebiet, Stadtzentrum) mit Pin-Overlay und
Legende: lädt CARTO-Basemap-Kacheln **einmalig zur Bauzeit**, setzt sie zu
einem Bild zusammen und schreibt den passenden Gutenberg-Block dazu.

Die Kacheln werden zur Bauzeit, nicht zur Laufzeit geladen: Eine Live-Karte
(Leaflet o. ä.) würde die IP jedes Besuchers an einen Kartenanbieter
schicken. Die Bilder sind selbst gehostet, es gibt zur Laufzeit keine fremde
Anfrage.

```bash
python3 tools/gen_map.py campus --render --write   # Bilder + Block neu builden
python3 tools/gen_map.py campus --check            # driftet etwas? (schreibt nichts)
python3 tools/gen_map.py campus --preview /tmp/campus.png   # PNG mit Pins, zur Kontrolle
```

Karten-IDs: `campus`, `stadtgebiet`, `stadtzentrum` (die Stems der Dateien in
`data/maps/`). `09-freizeit.html` trägt zwei Blöcke: `stadtgebiet` als Übersicht
über ganz Heidenheim und `stadtzentrum` als herangezoomte Detailkarte — im
Zentrum liegen die Orte so dicht beieinander, dass sie sich auf der
Übersicht überlagern, und zoomen kann man auf einem Bild nicht.

| Flag           | Wirkung                                                   |
| -------------- | --------------------------------------------------------- |
| `--render`     | Kacheln laden, WebP-Paar nach `data/media/` schreiben     |
| `--write`      | Block-HTML in die Zielseiten splicen                      |
| `--check`      | neu rendern und diffen; schreibt nichts, Exit 1 bei Drift |
| `--preview`    | PNG mit eingezeichneten Pins — prüft die Projektion       |
| `--media-base` | URL-Präfix der hochgeladenen Bilder                       |

**Voraussetzungen:** `--render`, `--preview` und `--check` brauchen
[Pillow](https://python-pillow.org/); `--write` und `--check` rufen zusätzlich
`npx prettier` auf. Die reine Geometrie ist stdlib-only und damit testbar
(`docs/testing.md`).

**Ein Kartenwechsel ist ein Dreifach-Deploy.** Die Bilder sind
CSS-Hintergründe: Die Geometrie steckt in `component.css`, das Bild in
`data/media/`, der Block in der Seite. Wer nur eines davon deployt, bekommt das
alte Bild unter der neuen Geometrie. Also zusammen deployen:

```bash
source .env
SKILL=~/.claude/skills/wordpress-default-editor
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json media
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json global-styles
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json studentenleben
```

**Hell/Dunkel:** Es gibt je zwei Bilder, umgeschaltet wird über zwei
CSS-Custom-Properties, die `:root.dark .stuv-map-canvas` aufgreift. Ein
`<picture>` mit `prefers-color-scheme` wäre falsch — das folgt dem
Betriebssystem und ignoriert den Theme-Schalter der Seite.

**Bilder ersetzen ist eine Falle.** Der `media`-Deploy überspringt existierende
Dateinamen stillschweigend, und `--force` legt `karte-…-1.webp` an, worauf keine
CSS-Referenz zeigt. Der Ablauf steht in `AGENTS.md` unter „Media“; die
Kartenbilder sind aber ohnehin mit `--render` reproduzierbar, was der
einfachere Weg ist.

## `gen_icon_css.py` — die Icons

Schreibt die `--ico-*`-Custom-Properties in `data/styles/component.css` —
[lucide](https://lucide.dev/)-Icons, als Data-URI eingebettet. Sie liegen
zwischen zwei Markern:

```css
/* gen_icon_css:start — erzeugt von tools/gen_icon_css.py; nicht von Hand bearbeiten */
...
/* gen_icon_css:end */
```

Nur dieser Abschnitt gehört dem Generator. Der Rest von `component.css` ist
handgeschrieben.

Die lucide-Version ist gepinnt: Ein Versionssprung zeichnet Pfade neu, und dann
ändert sich jedes Icon auf der Seite gleichzeitig. Das Repo hat kein
`node_modules` (siehe `AGENTS.md`), lucide wird also ad hoc installiert:

```bash
npm install --prefix /tmp/lucide lucide-static@0.577.0
export LUCIDE_ICON_DIR=/tmp/lucide/node_modules/lucide-static/icons
python3 tools/gen_icon_css.py --write
python3 tools/gen_icon_css.py --check    # driftet etwas? (schreibt nichts)
```

Ohne `LUCIDE_ICON_DIR` sucht das Skript in `node_modules/lucide-static/icons`.

Der Data-URI trägt die Markenfarbe fest eingebacken, damit dasselbe Bild sowohl
als CSS-Maske funktioniert (nur der Alphakanal zählt, die Farbe kommt aus
`background: var(--stuv-primary)`) als auch als `background-image` (dann zählt
die eingebackene Farbe).

**Nach dem Deploy prüfen.** WordPress' REST-Sanitizer entfernt Data-URIs aus
dem Custom-CSS-Feld. Ob die Icons überlebt haben, sagt `verify_global_css.py`
(Aufruf in `AGENTS.md`); Exit-Code 2 heißt, sie wurden gestrippt und müssen
stattdessen im `core/html`-Block des Headers stehen.
