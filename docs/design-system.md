# Design-System

Werte (Tokens) stehen in `data/global-styles.json`, Aussehen (Komponenten) in `data/styles/component.css`. Eine andere Markenfarbe oder ein anderer Eckenradius ist ein Token, eine neue Kachelart eine Komponentenklasse. Beide gehen zusammen als Ziel `global-styles` raus. Stilvorbild ist [shadcn/ui](https://ui.shadcn.com/), die Bibliothek der Vorgängerseite.

## Tokens

`global-styles.json` hat die Form einer `theme.json` und landet in der Datenbank. Die Palette (`settings.color.palette`) bleibt bei acht Einträgen, weil jeder im Editor als Farbklecks erscheint:

| Slug                 | Wert               | Rolle             |
| -------------------- | ------------------ | ----------------- |
| `primary`            | `#E2001A`          | DHBW-Rot          |
| `primary-foreground` | `#ffffff`          | Text auf Rot      |
| `background`         | `#ffffff`          | Seite             |
| `foreground`         | `#0a0a0a`          | Fließtext         |
| `muted`              | `#f4f4f5`          | gedämpfte Flächen |
| `muted-foreground`   | `#52525b`          | Sekundärtext      |
| `border`             | `#e4e4e7`          | Ränder            |
| `band`               | `rgba(0,0,0,0.03)` | Sektionsstreifen  |

Daraus werden `--wp--preset--color--<slug>` und `.has-<slug>-color`. Breiten: `contentSize: 56rem`, `wideSize: 72rem`; volle Breite braucht `align:full`. Eigener Token: `stuvRadius: 0.5rem` → `--wp--custom--stuv-radius`.

**Schrift:** Überschriften in Fraunces (`SOFT 50`, `WONK 1` per `font-variation-settings`), Fließtext in Atkinson Hyperlegible Next, Fallback Georgia bzw. Systemschrift. Der Hero-Titel ist Gewicht 300, optische Größe 144; `h2`/`h3` Gewicht 400. Keine Versal- oder Kicker-Zeilen.

Fünf Größen oben in `component.css`, jedes `font-size` nutzt eine (`test_styles.py`); die Media Queries ändern nur die Variablen. Die Editor-Presets haben dieselben Werte, am Block sind nur 0.875, 1 und 1.25rem erlaubt. `.stuv-h2`, `.stuv-h3`, `.stuv-h3-sm` sind nur Namen für die Elementgrößen.

| Variable         | Größe               | Wofür                                  |
| ---------------- | ------------------- | -------------------------------------- |
| `--text-small`   | 0.875rem            | Buttons, Navigation, Badges, Formulare |
| `--text-body`    | 1rem                | Fließtext                              |
| `--text-title`   | 1.25rem             | `h3`, `h4`, Kartentitel, Intro         |
| `--text-heading` | 1.75 → 2.25rem      | `h2`                                   |
| `--text-display` | 2.25 → 3.5 → 4.5rem | `h1`, Hero                             |

Schriften sind selbst gehostet (DSGVO: kein `fonts.googleapis.com`), in der Font Library unter `/wp-content/uploads/fonts/`, Kopien mit OFL-Lizenz in `data/fonts/`: Fraunces variabel Latin mit allen Achsen (`@fontsource-variable/fraunces` 5.3.0, 121 KB) und Atkinson Hyperlegible Next mit Gewichtsachse (`@fontsource-variable/atkinson-hyperlegible-next` 5.3.0, 34 KB), ohne Kursiv; → kommt aus der Systemschrift. Kein Deploy-Ziel lädt sie hoch, sondern einmalig die REST-Route `wp/v2/font-families/<id>/font-faces`.

## Komponenten

`component.css` landet im Custom-CSS der Global Styles und damit inline auf jeder Seite. Alle Klassen beginnen mit `stuv-`:

| Klasse                                                          | Wofür                                              |
| --------------------------------------------------------------- | -------------------------------------------------- |
| `.stuv-section`, `-continued`, `-primary`                       | Vollbreiter Streifen; ohne Abstand oben; rot       |
| `.stuv-page-header`                                             | Seitenkopf der Unterseiten                         |
| `.stuv-card`, `.stuv-card-*`                                    | Karten mit Cover-Link, Hover, Fokusring            |
| `.stuv-button-*`                                                | Buttons außerhalb von Button-Blöcken               |
| `.stuv-icon-box`, `.stuv-ico-*`                                 | Icons (`--ico-*` generiert, [tools.md](tools.md))  |
| `.stuv-badge*`, `.stuv-chip*`                                   | Pillen; Chips als Sprungleiste                     |
| `.stuv-crisis`, `.stuv-topic-list`, `.stuv-steps`               | Kummer Karsten                                     |
| `.stuv-schedule`, `.stuv-stats`                                 | Termintabelle; Zahlenreihe unter dem Hero          |
| `.stuv-map-*`, `.stuv-events`, `.stuv-event-*`, `.stuv-mensa-*` | Karten, Terminliste, Speiseplan                    |
| `.stuv-person`, `.stuv-person-quote`                            | Vorsitz-Karte                                      |
| `.stuv-media`, `.stuv-split`, `.stuv-photo-strip`               | Foto; Text neben Foto ab 1024px; Fotoreihe         |
| `.stuv-sr-only`                                                 | nur für Screenreader                               |
| `.stuv-wpforms`                                                 | WPForms ([content-editing.md](content-editing.md)) |
| `.stuv-header`, `.stuv-footer`, `.stuv-theme-*`                 | Kopf, Fuß, Dark-Mode-Schalter                      |

**Die Brücke `--stuv-*`:** `:root` leitet aus den Presets ab (`--stuv-primary: var(--wp--preset--color--primary, #e2001a)`; der Hex-Wert ist nur Notnagel). Abgeleitete Werte (`--stuv-ring`, `--stuv-radius-sm`, `--stuv-card`) wären als Palette-Einträge unnötige Farbkleckse. Im Dark Mode ist `--stuv-primary` `#ff1a33` (lesbare rote Schrift), unter weißer Schrift aber nur 3,85:1; deshalb liegt unter `--stuv-primary-foreground` immer `--stuv-primary-surface` (`#e2001a`, 4,94:1). `--stuv-destructive` hat eigene Werte (`#b91c1c` / `#f87171`), dazu Icon und roten Rahmen: Farbe allein ist kein Fehlersignal (WCAG 1.4.1).

## Dark Mode

`.dark` auf `<html>` (Klasse statt Media Query, damit der Schalter gilt); `:root.dark` definiert die Tokens neu, jede Komponente liest nur `var(--stuv-*)`.

- `color-scheme` steht ausdrücklich auf `light` bzw. `dark` (Scrollbalken, `<select>`, Autofill), nicht `light dark`. Ausnahme: Die invertierten Kalender-Iframes bleiben `light`, sonst blitzen sie weiß auf.
- `band` hat keinen Alias, deshalb überschreibt `:root.dark` den Preset selbst.

## Fallstricke in `component.css`

`component.css` geht auf jede Seite, deshalb stehen die Begründungen hier statt in Kommentaren.

- **Sticky Header** sitzt auf `header.wp-block-template-part`, nicht auf `.stuv-header`. `scroll-padding-top` ist Header-Höhe plus Luft; nach einer Padding-Änderung neu messen.
- **Header-/Footer-Padding** sind TT5s Spacing 30/50/60 wörtlich, damit ein Theme-Update nichts verschiebt.
- **Navigation:** Core schaltet bei 600px aufs Hamburger-Menü (`!important`), wir bei 1023px. Darunter kein `backdrop-filter` (würde das Overlay abschneiden). Overlay-Farben per `!important` aus `--stuv-*`, weil TT5s `base`/`contrast` nicht dunkel werden und ein Umdefinieren die Hero-Abdunklung umkehrte.
- **Lücke über dem Footer:** TT5s blockGap nur auf `.wp-site-blocks > .wp-block-template-part` zurücksetzbar.
- **Footer ist immer dunkel;** seine Hex-Werte von Hand mit `:root.dark` mitziehen.
- **Logo ist Inline-SVG** (`<g id="stuv-logo">` im Header, `<use>` in Footer und Linktree), weil WordPress keine SVGs annimmt. Farben über `--stuv-logo-text`/`-rule` als `style="fill: var(…)"`, denn Selektoren erreichen `<use>`-Kopien nicht. Quelle `data/media/.stuv-dhbw-logo.svg`.
- **Kartenlegende** ist eine Karte (`<ol class="stuv-card">`) mit Grid-Zeilen, `align-content: start`.
- **Hero-Übergang:** 6rem Verlauf = `padding-bottom: 6rem` in `01-hero.html`, Smoothstep-Stopps.
- **Badge-Kontrast:** `.stuv-badge-secondary` nutzt `#52525b` (muted-foreground auf muted: nur 4,40:1).
- **Icons:** immer `.stuv-ico.stuv-ico-<name>`; allein würde es die Icon-Box maskieren.
- **Mobil** ist `max-width: 639px`, nie 640px.
- **Fokus** ist eine 2px-Outline mit 2px Abstand (4,94:1 / 5,16:1), nie ein Schatten (fehlt im Windows-Kontrastmodus); `outline: none` lässt `test_styles.py` scheitern.
- **Ganze Karten als Link:** `.stuv-card-cover` (`::after` überdeckt die Karte), `.stuv-quicklink`, `.stuv-linktree-card` (füllen eine `.stuv-clip`-Karte, deren `overflow: hidden` den Ring abschneidet; die Karte zeichnet ihn per `:has(…)`). Neue Klasse: in `CARD_LINK_CLASSES` (`tools/sitecheck.py`) und diese Regeln.
- **Links im Fließtext** (`p`, `li` im Post-Content) sind unterstrichen, weil Rot auf Grau keinen Kontrast hat; außer Buttons, Cover-Links, Chips.
- **Buttons sind Button-Blöcke.** Ohne Stil rot gefüllt, `is-style-outline` Kontur, `is-style-overlay` halbtransparent fürs Hero. Auf `.stuv-section-primary` wird der ungestylte weiß (Hauptaktion), `overlay` durchsichtig mit weißem Rand. `stuv-button-lg` größer; Icons als `<span class="stuv-ico stuv-ico-…">`. Mobil untereinander in voller Breite. `stuv-button-outline` (Plugin-`<button>`) und `stuv-button-link` (Textlink mit Pfeil) gibt es außerhalb von Button-Blöcken.
- **WPForms:** Textfarbe bei `:focus` und `:focus:invalid` wiederholt (WPForms' Spezifität, sonst schwarz auf schwarz); Autofill über `-webkit-text-fill-color` und `caret-color`; Submit braucht `[type="submit"]` gegen WPForms' Blau, dessen `::after`-Fokusring ausgeblendet wird; „Mittel“-Felder in voller Breite; Eingaben mobil mindestens 16px (sonst zoomt iOS).

## Wohin gehört meine Änderung?

| Vorhaben                  | Ort                                     |
| ------------------------- | --------------------------------------- |
| Farben                    | Palette in `global-styles.json`         |
| Seitenbreite, Eckenradius | `settings.layout`, `settings.custom`    |
| Aussehen eines Bauteils   | die `.stuv-*`-Klasse                    |
| Neue Kachelart            | erst nach einer passenden Klasse suchen |
| Dark Mode                 | `:root.dark`                            |
| Icons                     | nie von Hand ([tools.md](tools.md))     |

Keine festen Werte ins Block-HTML: `style="color:#e2001a"` übersteht keinen Palettenwechsel und keinen Dark Mode.
