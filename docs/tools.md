# Tools

Vier Skripte in `tools/`. Keines spricht mit WordPress — zwei erzeugen Dateien,
die über den normalen Deploy-Weg auf die Site kommen
(`docs/content-editing.md`), die beiden Export-Skripte erzeugen Artefakte
außerhalb des Repos. Das Deploy-Tooling selbst liegt woanders
(`docs/ai-workflow.md`).

Zwei der vier sind Generatoren, deren Ergebnis im Repo liegt. Generierte
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
python3 tools/gen_map.py campus --preview          # PNG mit gesetzten Pins, zur Kontrolle
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
CSS-Custom-Properties, die `:root.dark .stuv-map-frame` aufgreift. Ein
`<picture>` mit `prefers-color-scheme` wäre falsch — das folgt dem
Betriebssystem und ignoriert den Theme-Schalter der Seite.

**Bilder ersetzen ist eine Falle.** Der `media`-Deploy überspringt existierende
Dateinamen stillschweigend, und `--force` legt `karte-…-1.webp` an, worauf keine
CSS-Referenz zeigt. Der Ablauf steht in `AGENTS.md` unter „Deploying“; die
Kartenbilder sind aber ohnehin mit `--render` reproduzierbar, was der
einfachere Weg ist. `rollback.py` deckt Medien nicht ab.

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

## `export_docs_wiki.py` — diese Doku

Bereitet das Markdown aus `docs/` zum Einfügen ins AStA-Wiki auf
(`wiki.dhbw-asta.de`, eine **BookStack**-Instanz). Eine Datei pro Doku-Seite.

```bash
python3 tools/export_docs_wiki.py    # nur Standardbibliothek, keine Installation
open build/wiki/
```

BookStack hat pro Seite einen echten Markdown-Editor. Deshalb kommt hier auch
Markdown heraus und kein gerendertes HTML: im Wiki eine Seite anlegen, im
Editor auf **Markdown** umschalten, die Datei komplett hineinkopieren. Als
Seitenname dient die H1 der Doku — die steht deshalb nicht mehr im Export,
sonst stünde dieselbe Überschrift zweimal auf der Seite. Welcher Name zu
welcher Datei gehört, listet `build/wiki/index.md`.

Das Skript rendert also nichts, es schreibt nur um. `build/` ist git-ignoriert;
die exportierten Dateien sind Artefakte, Quelle bleibt das Markdown in `docs/`.

Drei Umschreibungen, alles andere geht unverändert durch:

- **Root-relative Links werden absolut** (`--site`, Standard
  `https://dev.stuv-heidenheim.de`). Ein `/wp-content/...`-Link würde im Wiki
  sonst gegen `wiki.dhbw-asta.de` aufgelöst.
- **Ein `wphtml`-Fence wird echtes Markup** statt eines Code-Blocks — dieselbe
  Luke wie früher beim WordPress-Generator, damit der ZIP-Download ein Link
  bleibt statt sichtbarem HTML-Quelltext. Ein gewöhnlicher `html`-Fence bleibt
  Code. (BookStack rendert Inline-HTML, kennt aber die `.stuv-*`-Klassen der
  Website nicht — im Wiki ist der Button ein normaler Link.)
- **Die H1 wird abgetrennt** und als Seitenname ausgegeben, siehe oben.

**Code-Blöcke fasst das Skript nie an.** In `content-editing.md` steht ein
Bild-Block mit `src="/wp-content/uploads/altes-bild.jpg"` — das ist ein
Beispiel dafür, was in der Seitendatei steht, und muss wörtlich stehen bleiben.
Absolut gemacht wird nur, was außerhalb eines Fences steht.

Einen Schreib-Zugang hätte BookStack auch (`PUT /api/pages`), womit der
Einfüge-Schritt entfiele. Dafür braucht es einen API-Token, und der hängt an
der Rollen-Berechtigung `Access system API`, die unser Konto nicht hat. Bis
sich das ändert, bleibt es beim Einfügen von Hand.

Die Liste der exportierten Docs ist eine Allowlist, kein Glob: die Konstante
`DOC_FILES` in `tools/export_docs_wiki.py`. Eine neue Datei in `docs/` bleibt
also repo-intern, bis sie dort eingetragen wird. Entsprechend gilt: nichts
Geheimes in `docs/`. `docs/not-public/` wird nie exportiert.

Ein Link auf eine Nachbar-Doku (`testing.md`) lässt sich nicht automatisch auf
eine Wiki-URL abbilden — das Skript meldet ihn und bricht ab, statt zu raten.

## `export_pdfs.mjs` — der PDF-Export

Rendert jede Route als durchgehende PDF-Seite und fügt sie zu einem Dokument
zusammen. Zweck ist Design-Review und Übergabe, nicht der Betrieb.

> **Kein Lauf ohne ausdrückliche Freigabe des Maintainers — jedes Mal.**
> Ein echter Lauf installiert Puppeteer und Chrome (mehrere hundert MB) nach
> `~/.cache/stuv-pdf-export` und ruft die Live-Site auf.

Unbedenklich ist nur:

```bash
node tools/export_pdfs.mjs --list    # zeigt geplante URLs, startet nichts
```

| Flag            | Wirkung                                               |
| --------------- | ----------------------------------------------------- |
| `--list`        | geplante URLs + Ausgaben zeigen, kein Browser         |
| `--out DIR`     | Zielverzeichnis (Standard: `~/Desktop`)               |
| `--width PX`    | Viewport-/PDF-Breite in CSS-Pixeln (Standard: 1440)   |
| `--pages a,b,c` | nur diese Routen (Startseite heißt `home`)            |
| `--keep-parts`  | Einzel-PDFs neben der zusammengefügten Datei behalten |

Zusammengefügt wird mit `pdfunite` (poppler) oder ersatzweise `qpdf`. Das
Skript installiert sich selbst in den Cache, damit das Repo sauber bleibt.
