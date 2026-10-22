# Design-System

Farben, Schrift, Abstände, Karten, Buttons. Zwei Dateien teilen sich die
Arbeit:

| Datei                       | Enthält                   | Beispiel                                  |
| --------------------------- | ------------------------- | ----------------------------------------- |
| `data/global-styles.json`   | Tokens: die Werte         | Rot ist `#E2001A`, Inhalt ist 56rem breit |
| `data/styles/component.css` | Komponenten: die Bauteile | eine Karte hat 1px Rand und Schatten      |

Die Grundregel: Ein Wert gehört in die Tokens, ein Aussehen in die
Komponenten. Für eine andere Markenfarbe änderst du einen Token, für rundere
Karten ebenfalls (`stuvRadius`). Brauchst du eine neue Art von Kachel, schreibst
du eine Komponentenklasse.

Beide Dateien gehen zusammen raus, als ein einziges Deploy-Ziel:

```bash
source .env
python3 .claude/skills/wordpress-default-editor/scripts/deploy.py \
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
| `muted-foreground`   | `#71717a`          | Sekundärtext                     |
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
auf Inter mit System-Fallbacks; Inter wird nirgends geladen, sichtbar ist also
die Systemschrift (San Francisco, Segoe UI …).

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

Fraunces liegt selbst gehostet auf dem Server, nicht bei Google: Ein Abruf von
`fonts.googleapis.com` schickt bei jedem Seitenaufruf die IP-Adresse an Google,
und das ist ohne Einwilligung nicht DSGVO-konform. Die Datei ist der variable
Latin-Schnitt mit allen vier Achsen (Gewichte 100 bis 900, 121 KB, deckt
Umlaute, ß, € und Typografie-Zeichen ab; Quelle `@fontsource-variable/fraunces`
5.3.0, `fraunces-latin-full-normal.woff2`) und liegt mit ihrer Lizenz (SIL OFL)
unter `data/fonts/`. Der Schnitt ohne `SOFT`-Achse wäre 67 KB groß, hätte aber
nur die spitzen Serifen.
Auf dem Server liegt sie in der Font Library von WordPress unter
`/wp-content/uploads/fonts/`; der `fontFace`-Eintrag in `data/global-styles.json` zeigt
dorthin, und WordPress druckt daraus selbst die `@font-face`-Regel. Die Datei
geht mit keinem Deploy-Ziel raus. Einmal hochgeladen wird sie über die
REST-Route `wp/v2/font-families/<id>/font-faces`. Fehlt die Datei, fallen die Überschriften auf
Georgia zurück.

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
| `.stuv-h2`, `.stuv-h3`                   | Überschriften-Größen                                      |
| `.stuv-badge*`, `.stuv-chip*`            | Pillen; Chips als Sprungleiste (Über uns)                 |
| `.stuv-kicker`                           | Rote Zeile über einer Überschrift, die eine Sektionsart   |
| `.stuv-crisis`, `.stuv-topic-list`       | Krisenhinweis und Themenliste (Kummer Karsten)            |
| `.stuv-steps`                            | Nummerierte Schritte als `<ol>` (Kummer Karsten)          |
| `.stuv-schedule`                         | Liste aus Name und Termin (Hochschulsport, Startseite)    |
| `.stuv-map-*`                            | Kartenrahmen, Pins, Legende                               |
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
- **Rot wird im Dunkeln heller** (`#ff1a33` statt `#e2001a`): Das DHBW-Rot hat
  auf Fast-Schwarz zu wenig Kontrast.
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
  Hero-Bild und rote Streifen (angemeldet von `stuv-theme`, siehe
  `plugins.md`). `stuv-button-lg` macht einen Button größer (Hero). Ein Icon ist
  ein `<span class="stuv-ico stuv-ico-…">` im Link, vor oder nach dem Text; es
  nimmt die Schriftfarbe des Buttons an. Dieselben Varianten gibt es als
  Klassen `stuv-button-primary`, `-outline`, `-overlay` für ein `<a>` oder
  `<button>` außerhalb eines Button-Blocks, etwa im Markup eines Plugins.
  `stuv-button-link` ist ein Textlink mit Pfeil oder Icon im Fließtext, kein
  Button-Block. Mobil stehen die Buttons eines Blocks untereinander in voller
  Breite, und ein langer Text bricht im Button um, statt herauszuragen.
- **Sektions-Kicker** ist immer `.stuv-kicker` am Absatz, ohne Inline-Stil.
  Nur das Hero-Cover setzt zusätzlich Weiß als Blockfarbe.
- **WPForms** (zusätzlich zur Ahnenketten-Regel in `docs/content-editing.md`):
  - Die Textfarbe steht bei `:focus` und `:focus:invalid` noch einmal, weil
    WPForms dort eigene Farben setzt (`textarea:focus` mit 0,3,2,
    `…:focus:invalid` mit 0,4,3). Ohne die Wiederholung tippt man im Dark Mode
    schwarz auf schwarz.
  - Autofill: Der Browser erzwingt seine Textfarbe mit `!important`;
    `-webkit-text-fill-color` und `caret-color` umgehen das. Die beiden
    Autofill-Selektoren stehen in getrennten Regeln, weil ein Browser, der einen
    davon nicht kennt, sonst die ganze Liste verwirft.
  - Der Absenden-Button braucht `[type="submit"]`, um WPForms' Blau (0,4,2) zu
    schlagen.
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

## Nach dem Deploy

WordPress' REST-Sanitizer kann Teile des Custom-CSS entfernen. Ob alles
angekommen ist, prüft `verify_global_css.py` (Aufruf in `AGENTS.md`, Exit-Codes
in `docs/tools.md`).
