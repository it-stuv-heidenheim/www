# Tools

In `tools/` liegen die beiden Generatoren unten. Keiner spricht mit WordPress;
beide erzeugen Dateien, die über den normalen Deploy-Weg auf die Site kommen
(`docs/content-editing.md`). Das Deploy-Tooling liegt unter `.agents/skills/`
(`docs/ai-workflow.md`).

Die beiden Generatoren schreiben ihr Ergebnis ins Repo. Generierte Dateien
**nie von Hand bearbeiten**: Eine Handänderung hält nur bis zum nächsten
Generatorlauf und verschwindet dann ohne Fehlermeldung. Bearbeite stattdessen
die Quelle und generiere neu.

Betroffen sind:

| Generierte Datei                                                             | Erzeugt von       | Quelle                                                      |
| ---------------------------------------------------------------------------- | ----------------- | ----------------------------------------------------------- |
| `data/pages/studentenleben/02-campus-karte.html`                             | `gen_map.py`      | `data/maps/campus.json`                                     |
| Karten-Blöcke in `.../09-freizeit.html`                                      | `gen_map.py`      | `data/maps/stadtgebiet.json`, `data/maps/stadtzentrum.json` |
| `data/media/karte-*.webp` (6 Bilder)                                         | `gen_map.py`      | `data/maps/*.json`                                          |
| Abschnitt zwischen den `gen_icon_css`-Markern in `data/styles/component.css` | `gen_icon_css.py` | Phosphor-SVGs                                               |

Beide Generatoren haben ein `--check`, das neu rendert und vergleicht, ohne
etwas zu schreiben. Exit-Code 1 heißt, die committete Datei passt nicht mehr zu
ihrer Quelle.

## `gen_map.py`: die Karten

Das Skript erzeugt die statischen Karten (Campus, Stadtgebiet, Stadtzentrum)
mit Pin-Overlay und Legende. Es lädt dafür einmalig CARTO-Basemap-Kacheln,
setzt sie zu einem Bild zusammen und schreibt den passenden Gutenberg-Block
dazu.

Die Kacheln lädt das Skript beim Bauen, damit Besucher sie nie laden müssen:
Eine Live-Karte (Leaflet o. ä.) würde die IP jedes Besuchers an einen
Kartenanbieter schicken. Die Bilder sind selbst gehostet, und beim Aufruf der
Seite geht keine Anfrage nach außen.

```bash
python3 tools/gen_map.py campus --render --write   # Bilder + Block neu builden
python3 tools/gen_map.py campus --check            # driftet etwas? (schreibt nichts)
python3 tools/gen_map.py campus --preview /tmp/campus.png   # PNG mit Pins, zur Kontrolle
```

Karten-IDs sind `campus`, `stadtgebiet` und `stadtzentrum` (die Dateinamen in
`data/maps/` ohne Endung). `09-freizeit.html` enthält zwei Blöcke:
`stadtgebiet` als Übersicht über ganz Heidenheim und `stadtzentrum` als
herangezoomte Detailkarte. Im Zentrum liegen die Orte so dicht, dass sie sich
auf der Übersicht überlagern, und in ein Bild kann man nicht hineinzoomen.

| Flag           | Wirkung                                                   |
| -------------- | --------------------------------------------------------- |
| `--render`     | Kacheln laden, WebP-Paar nach `data/media/` schreiben     |
| `--write`      | Block-HTML in die Zielseiten splicen                      |
| `--check`      | neu rendern und diffen; schreibt nichts, Exit 1 bei Drift |
| `--preview`    | PNG mit eingezeichneten Pins, um die Projektion zu prüfen |
| `--media-base` | URL-Präfix der hochgeladenen Bilder                       |

**Voraussetzungen:** `--render`, `--preview` und `--check` brauchen
[Pillow](https://python-pillow.org/); `--write` und `--check` rufen zusätzlich
`npx prettier` auf. Die Geometrie allein kommt mit der Standardbibliothek aus
und ist deshalb ohne Pillow testbar (`docs/testing.md`).

**Ein Kartenwechsel ist ein Dreifach-Deploy.** Die Bilder sind
CSS-Hintergründe: Die Geometrie steckt in `component.css`, das Bild in
`data/media/`, der Block in der Seite. Wer nur eines davon deployt, bekommt das
alte Bild unter der neuen Geometrie. Deploye deshalb alle drei zusammen. Ein neu
gerendertes Bild behält seinen Dateinamen, und den überspringt der
`media`-Deploy; es geht deshalb mit `--replace` hoch (hier für `campus`):

```bash
source .env
SKILL=.agents/skills/wordpress-default-editor
python3 $SKILL/scripts/upload_media.py --replace data/media/karte-campus-light.webp data/media/karte-campus-dark.webp
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json global-styles
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json studentenleben
```

**Hell/Dunkel:** Jede Karte hat zwei Bilder. Umgeschaltet wird über zwei
CSS-Custom-Properties, die `:root.dark .stuv-map-canvas` aufgreift. Ein
`<picture>` mit `prefers-color-scheme` würde dem Betriebssystem folgen und den
Theme-Schalter der Seite ignorieren.

**Vorsicht beim Ersetzen von Bildern.** Der `media`-Deploy überspringt
vorhandene Dateinamen ohne Meldung, und ein zweiter Upload desselben Namens
landet als `karte-…-1.webp`, auf das nichts verweist. `upload_media.py
--replace` (`replace_media()` im Skill) sichert die alte Datei, löscht sie und
lädt die neue unter dieselbe URL; `rollback.py --media <dateiname>` stellt die
alte wieder her. Das `?v=` in der Bild-URL ändert sich mit dem Inhalt, also
holt der Browser das neue Bild, statt das alte aus dem Cache zu zeigen.

## `gen_icon_css.py`: die Icons

Das Skript schreibt die `--ico-*`-Custom-Properties in
`data/styles/component.css`: [Phosphor](https://phosphoricons.com/)-Icons (Gewicht „regular“), als Data-URI
eingebettet. Sie liegen zwischen zwei Markern:

```css
/* gen_icon_css:start — erzeugt von tools/gen_icon_css.py; nicht von Hand bearbeiten */
...
/* gen_icon_css:end */
```

Nur dieser Abschnitt gehört dem Generator. Den Rest von `component.css`
schreiben wir von Hand.

Die Phosphor-Version ist gepinnt, weil ein Versionssprung Pfade neu zeichnet und
sich dann jedes Icon auf der Seite auf einmal ändert. Das Repo hat kein
`node_modules` (siehe `AGENTS.md`), Phosphor wird also bei Bedarf installiert:

```bash
npm install --prefix /tmp/phosphor @phosphor-icons/core@2.1.1
export PHOSPHOR_ICON_DIR=/tmp/phosphor/node_modules/@phosphor-icons/core/assets/regular
python3 tools/gen_icon_css.py --write
python3 tools/gen_icon_css.py --check    # driftet etwas? (schreibt nichts)
```

Ohne `PHOSPHOR_ICON_DIR` sucht das Skript in
`node_modules/@phosphor-icons/core/assets/regular`.

Die Namen der `--ico-*`-Tokens stammen noch aus lucide (`--ico-utensils`,
`--ico-alert-circle`, …), weil Block-HTML, Karten-JSON und `component.css` sie
verwenden. `ICONS` im Skript ordnet jedem Token das Phosphor-Icon zu, das ihn
zeichnet; ein anderes Icon ist damit eine Zeile im Skript statt einer
Umbenennung im ganzen Inhalt.

Die Markenfarbe ist fest in den Data-URI eingebacken. So funktioniert dasselbe
Bild als CSS-Maske (dort zählt nur der Alphakanal, die Farbe kommt aus
`background: var(--stuv-primary)`) und als `background-image` (dort zählt die
eingebackene Farbe).

**Nach dem Deploy prüfen.** WordPress' REST-Sanitizer kann Data-URIs aus dem
Custom-CSS-Feld entfernen. Ob die Icons angekommen sind, sagt
`verify_global_css.py`, das `deploy.py` nach jedem `global-styles`-Deploy
selbst aufruft (die Marker stehen in `data/manifest.json`). Exit-Code 2 heißt, dass sie
entfernt wurden; dann müssen sie stattdessen im `core/html`-Block des Headers
stehen.
