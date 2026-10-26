# Design-System

Farben, Schrift, Abstände, Karten, Buttons. Zwei Dateien teilen sich die
Arbeit:

| Datei                       | Enthält                   | Beispiel                                         |
| --------------------------- | ------------------------- | ------------------------------------------------ |
| `data/global-styles.json`   | Tokens: die Werte         | Rot ist `#E2001A`, Inhalt ist 56rem breit        |
| `data/styles/component.css` | Komponenten: die Bauteile | eine Karte hat 1px Rand, Schatten nur beim Hover |

Die Grundregel: Ein Wert gehört in die Tokens, ein Aussehen in die
Komponenten. Für eine andere Markenfarbe änderst du einen Token, für rundere
Karten ebenfalls (`stuvRadius`). Brauchst du eine neue Art von Kachel, schreibst
du eine Komponentenklasse.

Beide Dateien gehen zusammen raus, als ein einziges Deploy-Ziel:

```bash
source .env
python3 .agents/skills/wordpress-default-editor/scripts/deploy.py \
  --manifest data/manifest.json global-styles
```

## Schicht 1: die Tokens

`data/global-styles.json` hat die Form einer `theme.json` und landet im
Global-Styles-Datensatz des Themes, also in der Datenbank und nicht in einer
Datei auf dem Server.

**Die Palette** (`settings.color.palette`) hat acht Einträge:

| Slug                 | Wert               | Rolle                            |
| -------------------- | ------------------ | -------------------------------- |
| `primary`            | `#E2001A`          | DHBW-Rot, die Markenfarbe        |
| `primary-foreground` | `#ffffff`          | Text auf Rot                     |
| `background`         | `#ffffff`          | Seitenhintergrund                |
| `foreground`         | `#0a0a0a`          | Fließtext                        |
| `muted`              | `#f4f4f5`          | gedämpfte Flächen                |
| `muted-foreground`   | `#52525b`          | Sekundärtext, Intros, Kartentext |
| `border`             | `#e4e4e7`          | Ränder                           |
| `band`               | `rgba(0,0,0,0.03)` | Hintergrund der Sektionsstreifen |

Mehr sollen es nicht werden. Jeder Palette-Eintrag erscheint im Editor als
anklickbarer Farbklecks, und eine große Palette lädt dazu ein, Dinge bunt zu
machen, die nicht bunt sein sollen.

WordPress macht daraus automatisch CSS-Variablen: aus `primary` wird
`--wp--preset--color--primary`, dazu die Klasse `.has-primary-color`.

**Die Breiten** (`settings.layout`): `contentSize: 56rem`, `wideSize: 72rem`
sind die Standardbreiten jeder Seite. Eine Sektion über die volle
Fensterbreite braucht `align:full` im Block.

**Die Schrift:** Überschriften (`h1` bis `h6`) setzt Fraunces, eine
Serifenschrift, über `styles.elements.heading` in den Tokens. Der Fließtext steht
auf Atkinson Hyperlegible Next, ebenfalls selbst gehostet (siehe unten), mit
der Systemschrift als Fallback (San Francisco, Segoe UI …). Die Schrift ist auf
Lesbarkeit gezeichnet: Zeichen, die sich sonst leicht verwechseln (I, l, 1 oder
O, 0), haben deutlich verschiedene Formen.

Fraunces hat neben Gewicht und optischer Größe zwei eigene Achsen, die
`component.css` in der `h1`–`h6`-Regel per `font-variation-settings` setzt:
`SOFT 50` rundet die Serifen halb ab, `WONK 1` schaltet die schräg gestellten
Buchstaben (h, m, n) und schiefen Serifen ein, die Fraunces ihren Charakter
geben. Der Hero-Titel (`.stuv-hero-title`) ist eine leichte Display-Zeile:
Gewicht 300, optische Größe fest auf 144 (höchster Kontrast), engere Laufweite
und bis zu 4.5rem groß. Darunter folgt die übliche Regel für Display-Serifen:
`.stuv-h2`, `.stuv-h3` und `.stuv-h3-sm` stehen auf Gewicht 400, die optische
Größe stellt der Browser selbst nach der Schriftgröße ein. Kleine Überschriften
sind dadurch schon kräftiger gezeichnet und wirken bei mehr als 400 fett.

**Die Schriftgrößen:** Es gibt fünf, als Variablen oben in `component.css`, und
jedes `font-size` dort nutzt eine davon (`tools/test_styles.py` prüft das):

| Variable         | Größe               | Wofür                                              |
| ---------------- | ------------------- | -------------------------------------------------- |
| `--text-small`   | 0.875rem            | Buttons, Navigation, Badges, Formulare, Hinweise   |
| `--text-body`    | 1rem                | Fließtext                                          |
| `--text-title`   | 1.25rem             | `h3`, `h4`, Kartentitel, Intro unter Überschriften |
| `--text-heading` | 1.75 → 2.25rem      | `h2`                                               |
| `--text-display` | 2.25 → 3.5 → 4.5rem | `h1`, Hero-Titel                                   |

Die beiden großen wachsen ab 640px und 768px; die Media Queries ändern nur
die Variablen, nicht die Regeln. Die Größen-Presets in `global-styles.json`
(`small` bis `xx-large`) haben dieselben Werte, damit der Editor nur Größen der
Skala anbietet; am Block selbst sind nur die drei festen erlaubt (0.875rem,
1rem, 1.25rem). Die Überschriften bekommen ihre Größe vom Element: Ein `h3`
ohne Klasse ist schon richtig, `.stuv-h2`, `.stuv-h3` und `.stuv-h3-sm` sind
nur noch gleichbedeutende Namen dafür. Kleine Versalzeilen mit Sperrung gibt es
nicht, auch keine roten Zeilen über einer Überschrift (Kicker); was dort
stünde, gehört in die Überschrift oder den ersten Satz. Die Überschriften der
Fußzeile stehen in normaler Schreibung.

Beide Schriften liegen selbst gehostet auf dem Server, nicht bei Google: Ein Abruf von
`fonts.googleapis.com` schickt bei jedem Seitenaufruf die IP-Adresse an Google,
und das ist ohne Einwilligung nicht DSGVO-konform. Die Fraunces-Datei ist der variable
Latin-Schnitt mit allen vier Achsen (Gewichte 100 bis 900, 121 KB, deckt
Umlaute, ß, € und Typografie-Zeichen ab; Quelle `@fontsource-variable/fraunces`
5.3.0, `fraunces-latin-full-normal.woff2`) und liegt mit ihrer Lizenz (SIL OFL,
`OFL-Fraunces.txt`) unter `data/fonts/`. Der Schnitt ohne `SOFT`-Achse wäre
67 KB groß, hätte aber nur die spitzen Serifen. Atkinson Hyperlegible Next ist
der variable Latin-Schnitt mit der Gewichtsachse (Gewichte 200 bis 800, 34 KB;
Quelle `@fontsource-variable/atkinson-hyperlegible-next` 5.3.0,
`atkinson-hyperlegible-next-latin-wght-normal.woff2`, Lizenz
`OFL-Atkinson-Hyperlegible-Next.txt`). Den kursiven Schnitt lädt die Seite
nicht, weil sie keinen Kursivtext hat. Der Pfeil → fehlt im Latin-Schnitt und
kommt aus der Systemschrift.
Auf dem Server liegt sie in der Font Library von WordPress unter
`/wp-content/uploads/fonts/`; der `fontFace`-Eintrag in `data/global-styles.json` zeigt
dorthin, und WordPress druckt daraus selbst die `@font-face`-Regel. Die Dateien
gehen mit keinem Deploy-Ziel raus. Einmal hochgeladen werden sie über die
REST-Route `wp/v2/font-families/<id>/font-faces` (für eine neue Familie vorher
`wp/v2/font-families` anlegen). Fehlt eine Datei, fallen die Überschriften auf
Georgia und der Fließtext auf die Systemschrift zurück.

**Eigene Tokens** (`settings.custom`): bisher nur der Eckenradius
`stuvRadius: 0.5rem`. WordPress übersetzt den camelCase-Namen zu
`--wp--custom--stuv-radius`.

## Schicht 2: die Komponenten

`data/styles/component.css` enthält die Klassen, alle mit dem Präfix `stuv-`.
Der Deploy schreibt die Datei ins Custom-CSS-Feld der Global Styles, und sie
erscheint auf jeder Seite in `<style id="global-styles-inline-css">`.

Die Familien:

| Präfix                                   | Wofür                                                     |
| ---------------------------------------- | --------------------------------------------------------- |
| `.stuv-section`                          | Vollbreiter Sektionsstreifen                              |
| `.stuv-section-continued`                | Sektion ohne Abstand oben, setzt die vorige fort          |
| `.stuv-section-primary`                  | Roter Streifen mit weißer Schrift (Events)                |
| `.stuv-page-header`                      | Linksbündiger Seitenkopf der Unterseiten                  |
| `.stuv-card`, `.stuv-card-*`             | Karten samt Cover-Link, Hover und Fokusring               |
| `.stuv-button-*`                         | Buttons außerhalb von Button-Blöcken, siehe unten         |
| `.stuv-icon-box`, `.stuv-ico-*`          | Icons; `--ico-*` ist generiert, siehe `docs/tools.md`     |
| `.stuv-h2`, `.stuv-h3`                   | Namen für die Größen von `h2` und `h3`                    |
| `.stuv-badge*`, `.stuv-chip*`            | Pillen; Chips als Sprungleiste (Studentenleben)           |
| `.stuv-crisis`, `.stuv-topic-list`       | Krisenhinweis und Themenliste (Kummer Karsten)            |
| `.stuv-steps`                            | Nummerierte Schritte als `<ol>` (Kummer Karsten)          |
| `.stuv-schedule`                         | Liste aus Name und Termin (Hochschulsport, Startseite)    |
| `.stuv-map-*`                            | Kartenrahmen, Pins, Legende                               |
| `.stuv-events`, `.stuv-event-*`          | Terminliste mit Datumskachel (`stuv-events`-Plugin)       |
| `.stuv-stats`                            | Zahlenreihe unter dem Hero (Startseite)                   |
| `.stuv-person`, `.stuv-person-quote`     | Vorsitz-Karte: Foto neben Name, Zitat darunter            |
| `.stuv-media`                            | Foto (Bild-Block); in einer Karte oben randlos            |
| `.stuv-split`                            | Text neben Foto ab 1024px (Seitenkopf, Werde aktiv)       |
| `.stuv-photo-strip`                      | Drei Fotos in einer Reihe (Mitmachen auf Über uns)        |
| `.stuv-sr-only`                          | Nur für Screenreader sichtbarer Text                      |
| `.stuv-mensa-*`                          | Speiseplan-Widget                                         |
| `.stuv-wpforms`                          | WPForms-Formularstyling (siehe `docs/content-editing.md`) |
| `.stuv-header`, `.stuv-footer`           | Kopf- und Fußzeile                                        |
| `.stuv-theme-switch`, `.stuv-theme-menu` | Dark-Mode-Schalter (siehe `docs/plugins.md`)              |

Das Stilvorbild ist [shadcn/ui](https://ui.shadcn.com/). Die Vorgängerseite war
eine Next.js-App mit dieser Bibliothek, und die Klassen bauen deren Komponenten
in reinem CSS nach. Deshalb sehen `.stuv-card` und `.stuv-button-outline` aus
wie shadcn-Karten und -Buttons.

## Die Brücke: `--stuv-*`

Zwischen beiden Schichten liegt eine Indirektion, die man leicht missversteht.
Ganz oben in `component.css`:

```css
:root {
  --stuv-primary: var(--wp--preset--color--primary, #e2001a);
  --stuv-radius: var(--wp--custom--stuv-radius, 0.5rem);
  --stuv-radius-sm: calc(var(--stuv-radius) - 0.125rem);
  --stuv-ring: var(--stuv-primary);
  --stuv-accent: var(--stuv-muted);
}
```

Die Farben sind hier nicht doppelt definiert. `--stuv-primary` zeigt auf den
Palette-Eintrag; der Hex-Wert dahinter ist ein Notnagel für den Fall, dass der
Preset fehlt. Die Palette bleibt die einzige Quelle.

Der Zwischenschritt bringt drei Dinge:

1. **Abgeleitete Werte, die keine Palette-Einträge sein sollen.** `--stuv-ring`
   (der Fokusring) ist die Markenfarbe unter eigenem Namen, `--stuv-radius-sm`
   ist der Radius minus 2px, `--stuv-card` und `--stuv-card-border` sind
   Fläche und Rand der Karten. Als Palette-Einträge wären das Farbkleckse im
   Editor, die niemand anklicken soll.
2. **Aliasse.** `--stuv-accent` ist dasselbe Grau wie `muted` und folgt jeder
   Änderung der Palette.
3. **Rollen, die im Dark Mode auseinanderlaufen.** Im Dark Mode ist
   `--stuv-primary` auf `#ff1a33` aufgehellt, damit rote _Schrift_ auf der fast
   schwarzen Seite lesbar bleibt. Als _Füllfarbe_ unter weißer Schrift reicht
   dieser Wert nicht (3,85:1, unter der WCAG-AA-Schwelle von 4,5:1). Dafür gibt
   es `--stuv-primary-surface`: in beiden Modi das Marken-Rot `#e2001a`, mit
   4,94:1 für weiße Schrift. Faustregel: Wo `--stuv-primary-foreground`
   obendrauf liegt (Buttons, Badges, Karten-Pins, Mensa-Tabs, Absenden-Button),
   gehört `--stuv-primary-surface` darunter. `--stuv-primary` bleibt für
   Schrift, Rahmen und Akzente.

`--stuv-destructive` war früher ein Alias auf das Marken-Rot. Ein Formularfehler
im selben Rot wie der Absenden-Button und jeder Akzent daneben macht die Farbe
zum einzigen Fehlersignal (WCAG 1.4.1), und bei Rot-Grün-Sehschwäche fällt er
kaum auf. Der Token hat deshalb eigene Werte (`#b91c1c` hell, `#f87171`
dunkel); die Fehlermeldung trägt zusätzlich ein Alert-Icon, das ungültige Feld
einen roten Rahmen.

## Dark Mode

Der Dark Mode hängt an einer Klasse. Eine Media Query würde dem Betriebssystem
folgen und den Schalter der Seite ignorieren (`docs/plugins.md`). Das
Theme-Skript setzt `.dark` auf `<html>`, und `component.css` definiert die Token
darunter neu:

```css
:root.dark {
  --stuv-background: #09090b;
  --stuv-primary: #ff1a33;
  ...
}
```

Für alles, was die Seite selbst malt, reicht das: Jede Komponente liest nur
`var(--stuv-*)` und wechselt deshalb mit. Abgeleitete Token wie `--stuv-ring`
rechnen sich neu, weil sie auf `--stuv-primary` zeigen.

- **Was der Browser selbst malt, folgt `color-scheme` statt den Token.**
  Scrollbalken, Cursor, das aufklappende `<select>`-Menü und die
  Autofill-Markierung kommen aus dem Browser. Ohne Angabe nimmt er die helle
  Variante; im Dark Mode blieb so ein heller Scrollbalken am rechten Rand
  stehen, und autoausgefüllte Felder zeigten fast schwarze Schrift auf Schwarz.
  `:root` und `:root.dark` setzen `color-scheme` darum ausdrücklich auf `light`
  bzw. `dark`, gebunden an die `.dark`-Klasse statt an `prefers-color-scheme`,
  damit es dem Schalter der Seite folgt. `light dark` würde die Entscheidung
  wieder dem Betriebssystem überlassen. Die einzige Ausnahme sind die
  invertierten Kalender-iframes, die mit `color-scheme: light` aussteigen:
  Unter `invert(1)` würde eine dunkle Startfläche weiß aufblitzen, bis Googles
  eigene Seite darüber malt.
- **`band` hat keinen `--stuv-*`-Alias**, weil die Seiten es direkt über
  `.has-band-background-color` benutzen. Deshalb überschreibt `:root.dark`
  ausnahmsweise den Preset selbst; die hellen 3 % Schwarz wären auf dunklem
  Grund unsichtbar.

## Fallstricke in `component.css`

`component.css` enthält keine Kommentare, weil jeder Kommentar mit auf jede
Seite ausgeliefert würde. Was man beim Ändern wissen muss, steht deshalb hier.

- **Sticky Header:** `position: sticky` sitzt auf dem von WordPress erzeugten
  `header.wp-block-template-part`, nicht auf `.stuv-header`, dessen Elternbox
  genau so hoch ist wie er selbst. Dort könnte nichts kleben.
  `scroll-padding-top` auf `:root` hält Sprungziele (Karten-Pins, `#wg-suche`
  …) unter dem Header frei: Header-Höhe (2.5rem + 2× Padding von
  `.stuv-header-row` + 1px Rand) plus Luft. Wer das Header-Padding ändert, muss
  neu messen.
- **Header- und Footer-Padding** sind TT5s Spacing-Werte 30/50/60, wörtlich
  übernommen, damit ein Theme-Update sie nicht verschiebt.
- **Navigation unter 1024px:** Core schaltet fest bei 600px auf das
  Hamburger-Menü um (mit `!important`); `component.css` überschreibt beide
  Seiten dieses Umschalters auf 1023px. Unter 1024px entfällt
  `backdrop-filter` am Header, sonst würde das fixierte Menü-Overlay auf
  Header-Höhe abgeschnitten. Die Overlay-Farben kommen per `!important` aus den
  `--stuv-*`-Token: Die Block-Attribute zeigen auf TT5s
  `base`/`contrast`-Presets, die nicht dunkel werden, und würde man diese
  Presets unter `:root.dark` umdefinieren, kehrte sich die Abdunklung des
  Hero-Covers um.
- **Lücke über dem Footer:** TT5s Root-blockGap gibt jedem Kind von
  `.wp-site-blocks` 1rem `margin-block-start`. Das lässt sich nur auf dem
  Wrapper `.wp-site-blocks > .wp-block-template-part` zurücksetzen; auf
  `.stuv-footer` wirkt es nicht.
- **Der Footer ist immer dunkel.** Seine Hex-Werte sind die aus `:root.dark`
  und müssen von Hand mitgezogen werden.
- **Das Logo ist Inline-SVG.** WordPress nimmt keine SVG-Uploads an (siehe
  `plugins.md`), und ein PNG hätte im Dark Mode und in der immer dunklen
  Fußzeile seine graue Schrift behalten. Die Kopfzeile enthält das Logo darum
  als `<g id="stuv-logo">`, Fußzeile und Linktree-Seite zeigen es per
  `<use href="#stuv-logo">`. Schrift und Trennstrich färben
  `--stuv-logo-text` und `--stuv-logo-rule`; `.stuv-footer` setzt sie fest auf
  die dunklen Werte. Selektoren aus `component.css` erreichen die Kopie in
  `<use>` nicht, Custom Properties dagegen schon; deshalb steht die Farbe als
  `style="fill: var(…)"` im SVG und nicht in einer Regel für dessen Pfade. Die
  Quelle ist `data/media/.stuv-dhbw-logo.svg` mit auf eine Nachkommastelle
  gerundeten Pfaden.
- **Kartenlegenden** sind eine Karte mit Zeilen, keine Karte je Ort:
  `gen_map.py` schreibt `stuv-card` an die `<ol>`. Jede Zeile ist ein Grid mit
  Symbol, Name und Link in der ersten Zeile; `align-content: start` hält die
  Zeilen oben, wenn die Nachbarzeile höher ist.
- **Hero-Übergang:** Die 6rem Verlauf entsprechen dem inline
  `padding-bottom: 6rem` der Hero-Gruppe in `01-hero.html`. Die Zwischenstopps
  folgen einer Smoothstep-Kurve, damit an beiden Enden keine harte Kante
  entsteht.
- **Badge-Kontrast:** `.stuv-badge-secondary` nimmt `#52525b`, weil
  `--stuv-muted-foreground` auf `--stuv-muted` nur 4,40:1 erreicht.
- **Icons:** `.stuv-ico.stuv-ico-<name>` muss zusammengesetzt bleiben. Ein
  nacktes `.stuv-ico-<name>` würde die `.stuv-icon-box` selbst maskieren.
- **Mobil-Breakpoint** ist `max-width: 639px`, nie 640px: Bei genau 640px greift
  schon `min-width: 640px`.
- **Fokus ist eine Outline, kein Schatten.** 2px `--stuv-ring` mit 2px Abstand,
  auf Weiß 4,94:1, auf Dunkel 5,16:1. Ein `box-shadow`-Ring entfällt im
  Windows-Kontrastmodus ersatzlos, und ein Ring mit 50 % Deckkraft lag unter
  3:1. `tools/test_styles.py` schlägt bei `outline: none` an.
- **Ganze Karten als Link.** Drei Klassen machen eine Karte klickbar:
  `.stuv-card-cover` (ein Link in der Karte, dessen `::after` die Karte
  überdeckt), `.stuv-quicklink` und `.stuv-linktree-card` (der Link füllt eine
  `.stuv-clip`-Karte). In einer `.stuv-clip`-Karte schneidet `overflow: hidden`
  den Fokusring des Links ab, deshalb zeichnet die Karte selbst Ring und
  Hover-Rand, über `.stuv-card:has(…)`. Eine Karte ohne einen dieser Links
  reagiert nicht und sieht damit auch nicht klickbar aus. Eine neue solche
  Klasse gehört in `CARD_LINK_CLASSES` in `tools/sitecheck.py` und in diese
  Regeln; die Tests prüfen beides.
- **Links im Fließtext sind unterstrichen**, alle `a` in `p` und `li` innerhalb
  von `.wp-block-post-content`. Ausgenommen sind Buttons, Karten-Cover-Links und
  Chips; Kopf- und Fußzeile liegen außerhalb. Rot in grauem Text hat zu Grau
  nur rund 1:1 Kontrast, die Farbe allein markiert den Link also nicht.
- **Buttons sind Button-Blöcke** (`wp:buttons` mit `wp:button`), keine Links in
  einem Absatz. Die Variante ist der Block-Stil: ohne Stil (oder „Füllen“) rot
  gefüllt, `is-style-outline` mit Kontur, `is-style-overlay` halbtransparent für
  das Hero-Bild (angemeldet von `stuv-theme`, siehe `plugins.md`). Auf dem roten
  Streifen (`.stuv-section-primary`) wird der ungestylte Button weiß mit roter
  Schrift, die Hauptaktion; `is-style-overlay` ist dort durchsichtig mit weißem
  Rand, die Nebenaktion. Die halbtransparente Füllung des Hero-Bilds hätte auf
  Rot unter 4,5:1 für die weiße Schrift gelegen. `stuv-button-lg` macht einen
  Button größer (Hero). Ein Icon ist ein `<span class="stuv-ico stuv-ico-…">` im
  Link, vor oder nach dem Text; es nimmt die Schriftfarbe des Buttons an.
  Außerhalb eines Button-Blocks, im Markup eines Plugins, gibt es
  `stuv-button-outline` für ein `<button>`. `stuv-button-link` ist ein Textlink
  mit Pfeil oder Icon im Fließtext, kein Button-Block. Mobil stehen die Buttons
  eines Blocks untereinander in voller Breite, und ein langer Text bricht im
  Button um, statt herauszuragen.
- **WPForms** (zusätzlich zur Ahnenketten-Regel in `docs/content-editing.md`):
  - Die Textfarbe steht bei `:focus` und `:focus:invalid` noch einmal, weil
    WPForms dort eigene Farben setzt (`textarea:focus` mit 0,3,2,
    `…:focus:invalid` mit 0,4,3). Ohne die Wiederholung tippt man im Dark Mode
    schwarz auf schwarz.
  - Autofill: Der Browser erzwingt seine Textfarbe mit `!important`;
    `-webkit-text-fill-color` und `caret-color` umgehen das. `:-webkit-autofill`
    reicht: Jeder Browser, der `:autofill` kennt, kennt auch diese Form.
  - Der Absenden-Button braucht `[type="submit"]`, um WPForms' Blau (0,4,2) zu
    schlagen. Seinen Fokusring malt WPForms ebenfalls blau, als `::after`; der
    wird ausgeblendet, und der Button bekommt den Ring der Seite.
  - Felder der Größe „Mittel“ begrenzt WPForms auf 60 %. In der Karte stehen
    alle Felder in voller Breite, wie Textfeld und Button darunter.
  - Eingabefelder sind mobil mindestens 16px groß, sonst zoomt iOS Safari beim
    Antippen hinein und nicht wieder heraus.

## Wohin gehört meine Änderung?

| Vorhaben                            | Ort                                               |
| ----------------------------------- | ------------------------------------------------- |
| Markenfarbe, Textfarbe, Grautöne    | Palette in `data/global-styles.json`              |
| Seitenbreite                        | `settings.layout`                                 |
| Eckenradius                         | `settings.custom.stuvRadius`                      |
| Aussehen von Karten, Buttons, Icons | die passende `.stuv-*`-Klasse in `component.css`  |
| Neue Art von Kachel                 | erst prüfen, ob eine `.stuv-*`-Klasse schon passt |
| Dark-Mode-Korrektur                 | der `:root.dark`-Block                            |
| Icon-Data-URIs                      | nie von Hand, siehe `docs/tools.md`               |

- Keine festen Werte ins Block-HTML. Ein `style="color:#e2001a"` in einer Seite
  überlebt keinen Palette-Wechsel und kennt keinen Dark Mode. Nimm stattdessen
  eine Klasse oder die Gutenberg-Farbwahl.
- Erst suchen, dann schreiben. Es gibt schon viele Klassen, und mit jeder
  neuen, die fast dasselbe tut, wird das Stylesheet schwerer zu pflegen.
