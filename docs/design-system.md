# Design-System

Farben, Schrift, Abstände, Karten, Buttons. Zwei Dateien teilen sich die
Arbeit:

| Datei                       | Enthält                        | Beispiel                                  |
| --------------------------- | ------------------------------ | ----------------------------------------- |
| `data/global-styles.json`   | **Tokens** — die Werte         | Rot ist `#E2001A`, Inhalt ist 56rem breit |
| `data/styles/component.css` | **Komponenten** — die Bauteile | eine Karte hat 1px Rand und Schatten      |

Die Trennung ist die Grundregel: **Ein Wert gehört in die Tokens, ein Aussehen
in die Komponenten.** Wer die Markenfarbe ändern will, ändert einen Token; wer
Karten runder machen will, auch (`stuvRadius`); wer eine neue Art von Kachel
braucht, schreibt eine Komponentenklasse.

Beide reisen zusammen: Sie sind **ein** Deploy-Ziel.

```bash
source .env
python3 ~/.claude/skills/wordpress-default-editor/scripts/deploy.py \
  --manifest data/manifest.json global-styles
```

## Schicht 1: die Tokens

`data/global-styles.json` hat die Form einer `theme.json` und landet im
Global-Styles-Datensatz des Themes — in der Datenbank, nicht in einer Datei auf
dem Server.

**Die Palette** (`settings.color.palette`) — acht Einträge, mehr nicht:

| Slug                 | Wert               | Rolle                            |
| -------------------- | ------------------ | -------------------------------- |
| `primary`            | `#E2001A`          | DHBW-Rot, die Markenfarbe        |
| `primary-foreground` | `#ffffff`          | Text auf Rot                     |
| `background`         | `#ffffff`          | Seitenhintergrund                |
| `foreground`         | `#0a0a0a`          | Fließtext                        |
| `muted`              | `#f4f4f5`          | gedämpfte Flächen                |
| `muted-foreground`   | `#71717a`          | Sekundärtext                     |
| `border`             | `#e4e4e7`          | Ränder                           |
| `band`               | `rgba(0,0,0,0.03)` | Hintergrund der Sektionsstreifen |

Acht ist Absicht: Jeder Palette-Eintrag taucht im Editor als anklickbarer
Farbklecks auf — eine große Palette lädt dazu ein, Dinge bunt zu machen, die
nicht bunt sein sollen.

WordPress macht daraus automatisch CSS-Variablen: aus `primary` wird
`--wp--preset--color--primary`, dazu die Klasse `.has-primary-color`.

**Die Breiten** (`settings.layout`): `contentSize: 56rem`, `wideSize: 72rem`.
Standardbreite jeder Seite. Eine Sektion, die über die volle Fensterbreite gehen
soll, braucht `align:full` im Block.

**Die Schrift:** Inter, mit den üblichen System-Fallbacks.

**Eigene Tokens** (`settings.custom`): aktuell nur `stuvRadius: 0.5rem` — der
Eckenradius. WordPress übersetzt den camelCase-Namen zu
`--wp--custom--stuv-radius`.

## Schicht 2: die Komponenten

`data/styles/component.css`, rund 1400 Zeilen, alle Klassen mit `stuv-`
vorangestellt. Sie wird ins Custom-CSS-Feld der Global Styles deployt und
erscheint auf jeder Seite in `<style id="global-styles-inline-css">`.

Die Familien:

| Präfix                                   | Wofür                                                     |
| ---------------------------------------- | --------------------------------------------------------- |
| `.stuv-section`                          | Vollbreiter Sektionsstreifen                              |
| `.stuv-page-header`                      | Linksbündiger Seitenkopf der Unterseiten                  |
| `.stuv-card`, `.stuv-card-*`             | Karten samt Cover und Hover-Pfeil                         |
| `.stuv-button-*`                         | Buttons (`primary`, `outline`, `link`, `overlay`)         |
| `.stuv-icon-box`, `.stuv-ico-*`          | Icons — `--ico-*` ist generiert, siehe `docs/tools.md`    |
| `.stuv-h2`, `.stuv-h3`                   | Überschriften-Größen                                      |
| `.stuv-badge*`, `.stuv-eyebrow`          | Pillen und Etiketten                                      |
| `.stuv-map-*`                            | Kartenrahmen, Pins, Legende                               |
| `.stuv-mensa-*`                          | Speiseplan-Widget                                         |
| `.stuv-wpforms`                          | WPForms-Formularstyling (siehe `docs/content-editing.md`) |
| `.stuv-header`, `.stuv-footer`           | Kopf- und Fußzeile                                        |
| `.stuv-theme-switch`, `.stuv-theme-menu` | Dark-Mode-Schalter (siehe `docs/plugins.md`)              |

Stilvorbild ist [shadcn/ui](https://ui.shadcn.com/) — die Vorgängerseite war
eine Next.js-App mit dieser Bibliothek, die Klassen sind deren Nachbauten in
reinem CSS. Deshalb sehen `.stuv-card` und `.stuv-button-outline` aus wie
shadcn-Karten und -Buttons.

## Die Brücke: `--stuv-*`

Zwischen beiden Schichten liegt eine Indirektion, die am leichtesten falsch
verstanden wird. Ganz oben in `component.css`:

```css
:root {
  --stuv-primary: var(--wp--preset--color--primary, #e2001a);
  --stuv-radius: var(--wp--custom--stuv-radius, 0.5rem);
  --stuv-radius-sm: calc(var(--stuv-radius) - 0.125rem);
  --stuv-ring: color-mix(in srgb, var(--stuv-primary) 50%, transparent);
  --stuv-accent: var(--stuv-muted);
}
```

Das ist **keine** doppelte Definition der Farben. `--stuv-primary` ist ein
Zeiger auf den Palette-Eintrag; der Hex-Wert dahinter ist nur ein Notnagel,
falls der Preset einmal fehlt. Die Palette bleibt die einzige Quelle.

Der Zwischenschritt kauft zwei Dinge:

1. **Abgeleitete Werte, die keine Palette-Einträge sein sollen.** `--stuv-ring`
   (der Fokusring) ist die Markenfarbe zu 50 % transparent, `--stuv-radius-sm`
   ist der Radius minus 2px. Als Palette-Einträge wären das Farbkleckse im
   Editor, die niemand anklicken soll.
2. **Aliasse.** `--stuv-accent` ist dasselbe Grau wie `muted`. Ändert sich die
   Palette, folgt es von allein.
3. **Rollen, die im Dark Mode auseinanderlaufen.** `--stuv-primary` ist im
   Dark Mode auf `#ff1a33` aufgehellt, damit rote _Schrift_ auf der fast
   schwarzen Seite lesbar bleibt. Als _Füllfarbe_ mit weißer Schrift darauf
   reicht dieser Wert aber nicht (3,85:1, unter der WCAG-AA-Schwelle 4,5:1).
   Dafür gibt es `--stuv-primary-surface`: in beiden Modi das Marken-Rot
   `#e2001a`, weiße Schrift darauf 4,94:1. **Faustregel:** Wo
   `--stuv-primary-foreground` obendrauf liegt (Buttons, Badges, Karten-Pins,
   Mensa-Tabs, Absenden-Button), gehört `--stuv-primary-surface` darunter —
   `--stuv-primary` bleibt für Schrift, Rahmen und Akzente.

`--stuv-destructive` ist bewusst **kein** Alias mehr auf das Marken-Rot: Ein
Formularfehler im selben Rot wie der Absenden-Button und jeder Akzent daneben
macht die Farbe zum einzigen Fehlersignal (WCAG 1.4.1) und ist für Rot-Grün-
Sehschwäche schwach. Der Token hat jetzt eigene Werte (`#b91c1c` hell,
`#f87171` dunkel), und die Fehlermeldung trägt zusätzlich ein Alert-Icon, das
ungültige Feld einen roten Rahmen.

## Dark Mode

Klassenbasiert, nicht per Media Query: Das Theme-Skript setzt `.dark` auf
`<html>`, und `component.css` definiert die Token darunter neu:

```css
:root.dark {
  --stuv-background: #09090b;
  --stuv-primary: #ff1a33;
  ...
}
```

Für alles, was die Seite selbst malt, reicht das — jede Komponente liest ohnehin
nur `var(--stuv-*)`, also kippt sie mit. Abgeleitete Token wie `--stuv-ring`
rechnen sich selbst neu, weil sie auf `--stuv-primary` zeigen.

- **Was der Browser selbst malt, hört nicht auf die Token.** Scrollbalken, der
  Cursor, das aufklappende `<select>`-Menü und die Autofill-Markierung kommen aus
  dem Browser und richten sich nach `color-scheme`. Ohne Angabe nimmt er den
  hellen Zweig — im Dark Mode blieb so ein heller Scrollbalken am rechten Rand
  stehen und autoausgefüllte Felder standen fast schwarz auf schwarz. `:root` und
  `:root.dark` setzen `color-scheme` darum explizit auf `light` bzw. `dark`,
  gebunden an die `.dark`-Klasse statt an `prefers-color-scheme`, damit es dem
  Schalter der Seite folgt. Bewusst nicht `light dark` — das gäbe die
  Entscheidung ans Betriebssystem zurück. Einzige Ausnahme sind die invertierten
  Kalender-iframes, die per `color-scheme: light` wieder aussteigen: unter
  `invert(1)` würde eine dunkle Startfläche weiß aufblitzen, bis Googles eigene
  Seite darüber malt.
- **Rot wird im Dunkeln heller** (`#ff1a33` statt `#e2001a`): Das DHBW-Rot hat
  auf Fast-Schwarz zu wenig Kontrast.
- **`band` hat keinen `--stuv-*`-Alias**, weil es direkt über
  `.has-band-background-color` benutzt wird. Deshalb wird ausnahmsweise der
  Preset selbst in `:root.dark` überschrieben — die hellen 3 % Schwarz wären
  auf dunklem Grund unsichtbar.

Warum keine Media Query: Die würde dem Betriebssystem folgen und den Schalter
der Seite ignorieren. Details in `docs/plugins.md`.

## Wohin gehört meine Änderung?

| Vorhaben                            | Ort                                               |
| ----------------------------------- | ------------------------------------------------- |
| Markenfarbe, Textfarbe, Grautöne    | Palette in `data/global-styles.json`              |
| Seitenbreite                        | `settings.layout`                                 |
| Eckenradius                         | `settings.custom.stuvRadius`                      |
| Aussehen von Karten, Buttons, Icons | die passende `.stuv-*`-Klasse in `component.css`  |
| Neue Art von Kachel                 | erst prüfen, ob eine `.stuv-*`-Klasse schon passt |
| Dark-Mode-Korrektur                 | der `:root.dark`-Block                            |
| Icon-Data-URIs                      | **gar nicht von Hand** — `docs/tools.md`          |

- **Keine festen Werte ins Block-HTML.** Ein `style="color:#e2001a"` in einer
  Seite überlebt keinen Palette-Wechsel und kennt keinen Dark Mode. Stattdessen
  eine Klasse oder die Gutenberg-Farbwahl benutzen.
- **Erst suchen, dann schreiben.** Es gibt schon viele Klassen. Eine neue, die
  fast dasselbe tut, ist der übliche Weg, wie ein Stylesheet unwartbar wird —
  siehe `.claude/skills/improving-code/`.

## Nach dem Deploy

WordPress' REST-Sanitizer kann am Custom-CSS schneiden. Ob es überlebt hat:

```bash
source .env
python3 ~/.claude/skills/wordpress-default-editor/scripts/verify_global_css.py \
  --marker .stuv-card --marker .stuv-icon-box \
  --marker ":root.dark" --marker .stuv-wpforms \
  --icon-marker=--ico-calendar
```

Exit 0 = ok. Exit 2 = Icon-Data-URIs wurden entfernt; der Ausweg steht in
`AGENTS.md` (sie müssen dann im `core/html`-Block des Headers leben).
