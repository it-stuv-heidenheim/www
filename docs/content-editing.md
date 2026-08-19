# Inhalte bearbeiten

So änderst du Texte, Namen, Fotos und Links auf der StuV-Website.
WordPress-, Gutenberg- oder CSS-Wissen ist nicht nötig — Grundkenntnisse in
Git und der Kommandozeile schon.

## Voraussetzungen

- Git-Zugriff auf dieses Repo
- Node.js (für `npx prettier` und die Block-Validierung)
- Das `wordpress-default-editor`-Tooling, entpackt nach `~/.claude/skills/`.
  Lade den ZIP-Schnappschuss herunter und entpacke ihn dorthin — er enthält
  denselben Stand wie ein frischer Checkout des Skills, nur ohne die
  installierten Abhängigkeiten, die beim ersten Lauf ohnehin neu entstehen:

  ```wphtml
  <a class="stuv-button-outline" href="/wp-content/uploads/wordpress-default-editor.zip" download
     >wordpress-default-editor herunterladen (ZIP)</a>
  ```

  ```bash
  unzip wordpress-default-editor.zip -d ~/.claude/skills/
  ```

- Zum Deployen: git-ignorierte `.env`-Datei mit `WP_USER`, `WP_APP_PASS`
  (WordPress Application Password), `WP_SITE`, `WP_REST_ROOT="wp-json"`

  Falls einmal **jeder** Deploy-Befehl mit `HTTP Error 404` abbricht, obwohl
  die Website normal läuft: dann fehlen die Rewrite-Regeln für `/wp-json/`.
  In wp-admin einmal **Einstellungen → Permalinks → Speichern** — mehr ist
  nicht nötig, es muss nichts geändert werden. (Genau das war am 26.07.2026
  der Fall, nachdem die Permalinks nach dem Umzug nie gespeichert worden
  waren.)

## Die richtige Datei finden

Die Seite ist aus HTML-Dateien in `data/` aufgebaut:

| Was du ändern willst                 | Wo es liegt                                                           |
| ------------------------------------ | --------------------------------------------------------------------- |
| Startseite                           | `data/sections/` (nummerierte Dateien, in Reihenfolge zusammengefügt) |
| Über uns                             | `data/pages/ueber-uns/`                                               |
| Events                               | `data/pages/events/`                                                  |
| Studentenleben                       | `data/pages/studentenleben/`                                          |
| Kontakt                              | `data/pages/kontakt/`                                                 |
| Kummer Karsten                       | `data/pages/kummer-karsten/`                                          |
| Linktree                             | `data/pages/linktree/`                                                |
| Header (Logo, Nav, Dark-Mode-Button) | `data/header_blocks.html`                                             |
| Footer                               | `data/footer_blocks.html`                                             |
| Farben und Schrift                   | `data/global-styles.json`                                             |
| Komponenten-Styles (Cards, Buttons)  | `data/styles/component.css`                                           |
| Bilder                               | `data/media/`                                                         |

## Text bearbeiten

1. Öffne die Datei in einem Plain-Text-Editor (VS Code, Sublime — nicht Word
   oder Pages).

2. Suche den zu ändernden Text. Block-HTML sieht so aus:

   ```html
   <!-- wp:paragraph -->
   <p>Hier steht der Text, den du ändern möchtest.</p>
   <!-- /wp:paragraph -->
   ```

3. Ändere **nur den Text zwischen den HTML-Tags**. Die `<!-- wp:... -->`-
   Kommentare sind Gutenberg-Block-Markierungen — nicht anfassen.

4. **Umlaute:** ä, ö, ü, ß verwenden (nicht ae, oe, ue, ss) — außer in
   URL-Slugs wie `?pagename=ueber-uns`.

5. **Bindestriche in Block-Kommentaren:** Innerhalb der JSON-Strings der
   `<!-- wp:... -->`-Kommentare ist ein doppelter Bindestrich als `\u002d\u002d`
   escaped (z. B. `var(\u002d\u002dstuv-muted)`), weil `--` in HTML-Kommentaren
   verboten ist. Das Muster aus der bestehenden Datei unverändert übernehmen —
   nie zu `--` „korrigieren“.

## Warum manche Absätze im Editor „ohne Wert“ dastehen

Bei vielen Absätzen standen Schriftgröße und Farbe früher direkt am Block. Seit
Juli 2026 stehen sie stattdessen in `data/styles/component.css`, an einer
Klasse: `.stuv-body-muted` für den grauen Fließtext in Karten und Listen,
`.stuv-eyebrow` für die kleine Überschrift-Zeile darüber. Der Block trägt nur
noch die Klasse.

Für alle, die Text ändern, macht das keinen Unterschied. Wer aber im Editor in
der rechten Seitenleiste unter **Farbe** oder **Typografie** nachsieht, findet
dort jetzt „kein Wert festgelegt“ — obwohl der Absatz auf der Seite grau und in
seiner Größe erscheint. Das ist kein Fehler: Der Wert kommt aus dem
Stylesheet, und die Seitenleiste zeigt nur, was am Block selbst hängt.

Daraus folgt zweierlei:

- Die Farbe eines solchen Absatzes lässt sich **nicht mehr über die
  Seitenleiste** umstellen. Wer sie ändern will, ändert die Klasse in
  `component.css` — und damit überall gleichzeitig, was genau der Zweck ist.
- Wird über die Seitenleiste doch eine Farbe gesetzt, gewinnt sie gegen die
  Klasse und dieser eine Absatz schert aus dem gemeinsamen Bild aus. Im Zweifel
  die Farbe dort wieder entfernen („zurücksetzen“) statt sie passend zu klicken.

## Namen und Kontaktdaten ändern

Namen und E-Mails stehen in Paragraph- und Heading-Blöcken. Beispiel aus
Über uns:

```html
<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">Max Mustermann</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><a href="mailto:max@example.com">max@example.com</a></p>
<!-- /wp:paragraph -->
```

Neuen Namen und E-Mail-Adresse eintragen. Das umgebende Markup unverändert
lassen.

## Ein Bild ersetzen

1. Neues Bild unter einem **neuen Dateinamen** nach `data/media/` legen
   (bevorzugt `.webp`). Nicht den alten Dateinamen wiederverwenden: der
   Media-Deploy überspringt bereits hochgeladene Dateinamen stillschweigend
   (Details in `AGENTS.md` unter „Deploying“).

2. `media` deployen — die Ausgabe zeigt die endgültige URL des Uploads:

   ```bash
   source .env
   python3 ~/.claude/skills/wordpress-default-editor/scripts/deploy.py \
     --manifest data/manifest.json media
   ```

   Ausgabe z. B.:
   `neues-bild.webp -> https://stuv-heidenheim.de/wp-content/uploads/neues-bild.webp (id 123)`

   Den Pfad aus der Ausgabe kopieren, nicht raten — WordPress legt Dateien ohne
   Monatsordner ab (Einstellung: „Meine Uploads in monats- und jahresbasierten
   Ordnern organisieren" ist deaktiviert).

3. Bildreferenz in der Seitendatei suchen. Ein Bild-Block sieht so aus:

   ```html
   <!-- wp:image {"width":"80px","height":"80px","scale":"cover","className":"is-style-rounded"} -->
   <figure class="wp-block-image is-resized is-style-rounded">
     <img
       src="/wp-content/uploads/altes-bild.jpg"
       alt="Beschreibung"
       style="object-fit: cover; width: 80px; height: 80px"
     />
   </figure>
   <!-- /wp:image -->
   ```

4. Die `src`-URL durch die neue ersetzen und den `alt`-Text aktualisieren (kurze
   Bildbeschreibung). **Den Host weglassen**: aus der Ausgabe von Schritt 2 nur
   den Teil ab `/wp-content/` übernehmen. Bild-URLs stehen im Repo
   host-relativ, damit dieselben Blöcke auf der Staging- und auf der
   Produktions-Domain funktionieren. Alles andere unverändert lassen — nichts
   wird beim Deploy automatisch umgeschrieben.

5. Die Seite deployen (siehe Abschnitt Deploy).

## Google-Kalender ändern

Der StuV-Google-Kalender erscheint an drei Stellen, alle über dieselbe
Kalender-ID (`c_05fa...@group.calendar.google.com`, URL-encodiert im
Query-Parameter):

| Stelle                                     | Datei                                  | Form                                                                   |
| ------------------------------------------ | -------------------------------------- | ---------------------------------------------------------------------- |
| Startseite, „Was wir bieten"               | `data/sections/02-was-wir-bieten.html` | kompaktes Embed, `mode=AGENDA`, 380px hoch, ohne Titel/Navigation/Tabs |
| Events-Seite                               | `data/pages/events/02-upcoming.html`   | volles Embed, 600px hoch                                               |
| Events-Seite, Button „Kalender abonnieren" | `data/pages/events/02-upcoming.html`   | Link auf `calendar.google.com/calendar/render?cid=...`                 |

**Kalender wechseln:** Die Kalender-ID steht dreimal fest verdrahtet — in
beiden `<iframe src>` und im Abonnieren-Link. Alle drei Stellen ersetzen,
sonst zeigen sie unterschiedliche Kalender.

Wichtige Embed-Parameter (volle Liste in den Google-Kalender-Einstellungen
unter „Kalender einbetten"):

- `ctz=Europe%2FBerlin` — Zeitzone
- `mode=AGENDA` — Listenansicht statt Monatsraster (nur im kompakten Embed)
- `showTitle=0&showNav=0&showDate=0&showPrint=0&showTabs=0&showCalendars=0&showTz=0`
  — Google-eigene UI-Elemente ausgeblendet, damit das Embed wie eine eigene
  Komponente aussieht statt wie eingebettetes Google-Kalender-Chrome
- `wkst=2` — Wochenstart Montag
- `hl=de` — deutsche Sprache
- `bgcolor=%23fcfcfc&color=%23E2001A` — Hintergrund- und Akzentfarbe. Nicht an
  `--stuv-*`-Tokens gekoppelt: Google-Kalender liest keine CSS-Variablen des
  Elternfensters, eine Farbänderung heißt die Hex-Werte direkt in der URL
  anpassen.

Beide Iframes sind `wp:html`-Blöcke, keine nativen Gutenberg-Embeds — der
native Embed-Block schreibt immer ein echtes `src`-Attribut, und genau das darf
hier nicht im Markup stehen: Der Kalender lädt erst auf Klick über
`data-stuv-src` (siehe `stuv-dsgvo` in `docs/plugins.md`).

`scrolling="no"` und `frameborder` trugen die Iframes früher ebenfalls; beide
sind entfernt. In HTML5 sind sie obsolet, das inline `border: 0` ersetzt
`frameborder`, und `scrolling="no"` war schädlich: Auf schmalen Viewports
staucht Google die Agenda in höhere Zeilen, der Inhalt lief aus der festen
Pixelhöhe heraus, und `scrolling="no"` nahm die einzige Möglichkeit, ihn noch
zu erreichen. Die Höhe steuert jetzt zusätzlich eine `min-height` in
`component.css` unterhalb von 639px.

## Formular ändern (WPForms)

Kontakt und Kummer Karsten binden ihr Formular per Shortcode ein, verpackt in
eine `.stuv-card.stuv-wpforms`-Gruppe:

```html
<!-- wp:group {"className":"stuv-card stuv-wpforms"} -->
<div class="wp-block-group stuv-card stuv-wpforms">
  <!-- wp:shortcode -->
  [wpforms id="129"]
  <!-- /wp:shortcode -->
</div>
<!-- /wp:group -->
```

| Seite          | Datei                                    | Formular-ID |
| -------------- | ---------------------------------------- | ----------- |
| Kontakt        | `data/pages/kontakt/03-form.html`        | 129         |
| Kummer Karsten | `data/pages/kummer-karsten/02-form.html` | 132         |

WPForms ist ein Drittanbieter-Plugin, installiert auf dem Host — anders als
`stuv-mensa`/`stuv-theme`/`stuv-dsgvo` nicht Teil von `wp-plugin/` und nicht in
diesem Repo versioniert (siehe `docs/plugins.md`). Daraus folgt:

- **Felder, Pflichtangaben, Bestätigungstext, Benachrichtigungs-E-Mail:**
  ausschließlich in wp-admin → WPForms → Formular bearbeiten. Nichts davon
  steht in diesem Repo — ein Feld hinzufügen heißt im WPForms-Builder
  speichern, nicht diese Seite deployen.
- **Aussehen** (Card-Rahmen, Eingabefelder, Button): die `.stuv-wpforms`-Regeln
  in `data/styles/component.css`, deployt über `global-styles` wie jede andere
  Komponentenklasse.
- Nur die Formular-ID im Shortcode und die umgebende Karte gehören in dieses
  Repo — den Rest liefert das Plugin zur Laufzeit aus der Datenbank.

**Styling-Eigenheit:** WPForms' eigenes `wpforms-full.min.css` lädt nach
`component.css` und gewinnt bei gleicher Selektor-Spezifität. Die
`.stuv-wpforms`-Regeln wiederholen deshalb die volle Ahnenkette
(`.stuv-wpforms .wpforms-container-full .wpforms-form ...`) statt kurzer
Selektoren, um WPForms rein über Spezifität zu schlagen, ohne `!important`.
Wer hier eine neue Regel ergänzt und sie nicht greift, hat meist zu kurz
selektiert.

**Neues Formular hinzufügen:** in wp-admin bauen, ID notieren, das Muster oben
mit der neuen ID in die Zielseite einsetzen.

## Formatieren

Nach dem Bearbeiten alle Dateien mit Prettier formatieren:

```bash
npx prettier --write .
```

Repo-Konvention und Pflicht vor jedem Commit. Ein Format-Lauf ändert die Bytes
aller Deploy-Ziele, nicht nur der bearbeiteten Datei — der nächste Deploy
schreibt deshalb alle Ziele neu. Keine inhaltliche Änderung.

## Blöcke validieren

Gutenberg-Blöcke müssen dem erwarteten Format des Editors entsprechen.
Geänderte Dateien prüfen — der Aufruf steht in `docs/testing.md` unter
„Block-Validierung“.

## Deploy

Vor jedem Deploy zuerst trocken laufen lassen (prüft lokal, ohne Server-Kontakt):

```bash
source .env
SKILL=~/.claude/skills/wordpress-default-editor
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json all --dry-run
```

Ausgabe prüfen. Wenn alles passt, die geänderten Ziele deployen:

```bash
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json <zielname>
```

Zielnamen aus `data/manifest.json`: `homepage`, `ueber-uns`, `events`,
`studentenleben`, `kontakt`, `kummer-karsten`, `linktree`, `header`, `footer`,
`global-styles`, `media`.

- **Bild geändert:** zuerst `media`, dann die Seite deployen.
- **Farben oder Styles geändert:** `global-styles` deployen.
- **Header/Footer geändert:** `header` oder `footer` deployen.

Nach dem Deploy die Live-Seite besuchen und die Änderung prüfen. Der gesamte
Prüfungs-Kanon steht in `docs/testing.md`.
