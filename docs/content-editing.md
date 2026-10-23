# Inhalte bearbeiten

So änderst du Texte, Namen, Fotos und Links auf der StuV-Website. Du brauchst
dafür kein WordPress-, Gutenberg- oder CSS-Wissen, aber Grundkenntnisse in Git
und auf der Kommandozeile.

## Voraussetzungen

- Git-Zugriff auf dieses Repo
- Node.js (für `npx prettier` und die Block-Validierung)
- Python 3. Das Tooling (`wordpress-default-editor`) liegt im Repo unter
  `.agents/skills/wordpress-default-editor/`; der Block-Validator installiert
  seine npm-Pakete beim ersten Lauf selbst.

- Zum lokalen Deployen (für die Deploy-Action nicht nötig): git-ignorierte `.env`-Datei mit `WP_USER`, `WP_APP_PASS`
  (WordPress Application Password), `WP_SITE`, `WP_REST_ROOT="wp-json"`

  Bricht einmal jeder Deploy-Befehl mit `HTTP Error 404` ab, obwohl die Website
  normal läuft, fehlen die Rewrite-Regeln für `/wp-json/`. Dann in wp-admin
  einmal **Einstellungen → Permalinks → Speichern** klicken, ohne etwas zu
  ändern.

## Die richtige Datei finden

Die Seite ist aus HTML-Dateien in `data/` aufgebaut:

| Was du ändern willst                 | Wo es liegt                                                           |
| ------------------------------------ | --------------------------------------------------------------------- |
| Startseite                           | `data/sections/` (nummerierte Dateien, in Reihenfolge zusammengefügt) |
| Über uns                             | `data/pages/ueber-uns/`                                               |
| Vorsitz (Startseite und Über uns)    | `data/patterns/vorsitz.html`                                          |
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

1. Öffne die Datei in einem Plain-Text-Editor wie VS Code oder Sublime (Word
   und Pages gehen nicht).

2. Suche den Text, den du ändern willst. Block-HTML sieht so aus:

   ```html
   <!-- wp:paragraph -->
   <p>Hier steht der Text, den du ändern möchtest.</p>
   <!-- /wp:paragraph -->
   ```

3. Ändere **nur den Text zwischen den HTML-Tags**. Die `<!-- wp:... -->`-
   Kommentare sind Gutenberg-Block-Markierungen und bleiben, wie sie sind.

4. Umlaute: ä, ö, ü, ß schreiben statt ae, oe, ue, ss. Ausnahme sind URL-Slugs
   wie `?pagename=ueber-uns`.

5. Bindestriche in Block-Kommentaren: In den JSON-Strings der
   `<!-- wp:... -->`-Kommentare ist ein doppelter Bindestrich als `\u002d\u002d`
   escaped (z. B. `var(\u002d\u002dstuv-muted)`), weil `--` in HTML-Kommentaren
   verboten ist. Übernimm das Muster aus der bestehenden Datei unverändert und
   „korrigiere“ es nie zu `--`.

## Warum manche Absätze im Editor „ohne Wert“ dastehen

Bei vielen Absätzen stehen Schriftgröße und Farbe nicht am Block, sondern an
einer Klasse in `data/styles/component.css`: `.stuv-body-muted` für den grauen
Fließtext in Karten und Listen, `.stuv-kicker` für die kleine rote
Überschrift-Zeile über einer Sektion. Der Block trägt nur noch die Klasse.

Beim Ändern von Text merkst du davon nichts. Siehst du aber im Editor in der
rechten Seitenleiste unter **Farbe** oder **Typografie** nach, steht dort „kein
Wert festgelegt“, obwohl der Absatz auf der Seite grau und in seiner Größe
erscheint. Der Wert kommt aus dem Stylesheet, und die Seitenleiste zeigt nur,
was am Block selbst hängt.

Das hat zwei Folgen:

- Über die Seitenleiste lässt sich die Farbe eines solchen Absatzes nicht mehr
  umstellen. Wer sie ändern will, ändert die Klasse in `component.css` und
  damit die Farbe überall auf einmal. Genau dafür gibt es die Klasse.
- Setzt jemand über die Seitenleiste doch eine Farbe, gewinnt sie gegen die
  Klasse, und dieser eine Absatz weicht vom Rest ab. Im Zweifel die Farbe dort
  wieder entfernen („zurücksetzen“), statt eine passende anzuklicken.

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

Der Vorsitz steht nur einmal, in `data/patterns/vorsitz.html`: ein
synchronisiertes Muster, das Startseite und Über uns per
`<!-- wp:block {"ref":212} /-->` einbinden. Nach einer Änderung dort das Ziel
`pattern-vorsitz` deployen, die beiden Seiten nicht.

Neuen Namen und E-Mail-Adresse eintragen. Das umgebende Markup unverändert
lassen.

## Ein Bild ersetzen

1. Neues Bild unter einem **neuen Dateinamen** nach `data/media/` legen
   (bevorzugt `.webp`). Den alten Dateinamen nicht wiederverwenden: Der
   Media-Deploy überspringt bereits hochgeladene Dateinamen ohne Meldung
   (Details in `AGENTS.md` unter „Media“).

2. `media` deployen. Die Ausgabe zeigt die endgültige URL des Uploads:

   ```bash
   source .env
   python3 .agents/skills/wordpress-default-editor/scripts/deploy.py \
     --manifest data/manifest.json media
   ```

   Ausgabe z. B.:
   `neues-bild.webp -> https://stuv-heidenheim.de/wp-content/uploads/neues-bild.webp (id 123)`

   Den Pfad aus der Ausgabe kopieren statt ihn zu raten. WordPress legt
   Dateien ohne Monatsordner ab (die Einstellung „Meine Uploads in monats- und
   jahresbasierten Ordnern organisieren" ist deaktiviert).

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
   Produktions-Domain funktionieren. Alles andere unverändert lassen; der
   Deploy schreibt nichts automatisch um.

5. Die Seite deployen (siehe Abschnitt Deploy).

## Google-Kalender ändern

Der StuV-Google-Kalender erscheint an drei Stellen, alle mit derselben
Kalender-ID (`c_05fa...@group.calendar.google.com`, URL-encodiert im
Query-Parameter):

| Stelle                                     | Datei                                  | Form                                                                   |
| ------------------------------------------ | -------------------------------------- | ---------------------------------------------------------------------- |
| Startseite, „Was wir bieten"               | `data/sections/02-was-wir-bieten.html` | kompaktes Embed, `mode=AGENDA`, 380px hoch, ohne Titel/Navigation/Tabs |
| Events-Seite                               | `data/pages/events/02-upcoming.html`   | volles Embed, 600px hoch                                               |
| Events-Seite, Button „Kalender abonnieren" | `data/pages/events/02-upcoming.html`   | Link auf `calendar.google.com/calendar/render?cid=...`                 |

**Kalender wechseln:** Die Kalender-ID steht an fünf Stellen fest im Markup: in
beiden `<iframe data-stuv-src>`, den beiden Fallback-Links darunter und im
Abonnieren-Link. Ersetze alle fünf, sonst zeigen sie unterschiedliche Kalender.

Die wichtigsten Embed-Parameter (die volle Liste steht in den
Google-Kalender-Einstellungen unter „Kalender einbetten"):

- `ctz=Europe%2FBerlin`: Zeitzone
- `mode=AGENDA`: Listenansicht statt Monatsraster (nur im kompakten Embed)
- `showTitle=0&showNav=0&showDate=0&showPrint=0&showTabs=0&showCalendars=0&showTz=0`:
  blendet Googles eigene Bedienelemente aus, damit das Embed wie eine Komponente
  der Seite aussieht und nicht wie ein eingebetteter Google-Kalender
- `wkst=2`: Wochenstart Montag
- `hl=de`: deutsche Sprache
- `bgcolor=%23fcfcfc&color=%23E2001A`: Hintergrund- und Akzentfarbe. Google
  Kalender liest keine CSS-Variablen des Elternfensters, die Werte hängen also
  nicht an den `--stuv-*`-Tokens. Für eine andere Farbe die Hex-Werte direkt in
  der URL ändern.

Beide Iframes sind `wp:html`-Blöcke und keine nativen Gutenberg-Embeds. Der
native Embed-Block schreibt immer ein echtes `src`-Attribut, und das darf hier
nicht im Markup stehen: Der Kalender lädt erst auf Klick über `data-stuv-src`
(siehe `stuv-dsgvo` in `docs/plugins.md`).

`scrolling="no"` fehlt mit Absicht: Auf schmalen Viewports staucht Google die
Agenda in höhere Zeilen, und ohne Scrollen käme man an den überlaufenden Inhalt
nicht heran. Unterhalb von 639px setzt `component.css` zusätzlich eine
`min-height`.

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

WPForms ist ein Drittanbieter-Plugin auf dem Host. Anders als
`stuv-mensa`/`stuv-theme`/`stuv-dsgvo` gehört es nicht zu `wp-plugin/` und ist
nicht in diesem Repo versioniert (siehe `docs/plugins.md`). Daraus folgt:

- Felder, Pflichtangaben, Bestätigungstext und Benachrichtigungs-E-Mail
  bearbeitest du ausschließlich in wp-admin → WPForms → Formular bearbeiten.
  Nichts davon steht in diesem Repo: Für ein neues Feld speicherst du im
  WPForms-Builder und deployst diese Seite nicht.
- Das Aussehen (Card-Rahmen, Eingabefelder, Button) steht in den
  `.stuv-wpforms`-Regeln in `data/styles/component.css` und geht wie jede
  andere Komponentenklasse über `global-styles` raus.
- In dieses Repo gehören nur die Formular-ID im Shortcode und die umgebende
  Karte. Den Rest liefert das Plugin zur Laufzeit aus der Datenbank.

**Styling-Eigenheit:** WPForms' eigenes `wpforms-full.min.css` lädt nach
`component.css` und gewinnt bei gleicher Selektor-Spezifität. Die
`.stuv-wpforms`-Regeln wiederholen deshalb die volle Ahnenkette
(`.stuv-wpforms .wpforms-container-full .wpforms-form ...`), damit sie WPForms
allein über die Spezifität schlagen, ohne `!important`. Greift eine neue Regel
hier nicht, ist der Selektor meist zu kurz.

**Neues Formular hinzufügen:** in wp-admin bauen, ID notieren und das Muster
oben mit der neuen ID in die Zielseite einsetzen.

## Formatieren

Nach dem Bearbeiten alle Dateien mit Prettier formatieren:

```bash
npx prettier --write .
```

Das ist Repo-Konvention und vor jedem Commit Pflicht. Ein Format-Lauf ändert
die Bytes aller Deploy-Ziele; das ist normal (`docs/testing.md`).

## Blöcke validieren

Gutenberg-Blöcke müssen dem Format entsprechen, das der Editor erwartet. Prüfe
die geänderten Dateien mit dem Aufruf aus `docs/testing.md` unter
„Block-Validierung“.

## Deploy

Ein Push auf `main`, der etwas unter `data/` ändert, startet die Action
**Deploy**. Sie wartet auf eine Freigabe: Ein Reviewer klickt im Lauf unter
**Actions** auf **Review deployments → Approve**. Dann deployt sie alle Ziele,
die von der Live-Seite abweichen, und prüft danach das Ergebnis. Von Hand geht
es unter **Actions → Deploy → Run workflow**. Hat jemand ein Ziel in wp-admin
geändert, bricht sie ab, statt die Änderung zu überschreiben. Was sie genau
macht und wie es dann weitergeht, steht in `docs/ai-workflow.md`.

### Lokal deployen

Ohne die Action geht es mit dem Skill und der `.env` (Voraussetzungen oben).
Vor jedem Deploy erst einen Trockenlauf machen (prüft lokal, ohne den Server zu
kontaktieren):

```bash
source .env
SKILL=.agents/skills/wordpress-default-editor
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json all --dry-run
```

Ausgabe prüfen. Wenn alles passt, die geänderten Ziele deployen:

```bash
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json <zielname>
```

Zielnamen aus `data/manifest.json`: `homepage`, `ueber-uns`, `events`,
`studentenleben`, `kontakt`, `kummer-karsten`, `linktree`, `header`, `footer`,
`global-styles`, `media`, `pattern-vorsitz`.

- Bild geändert: zuerst `media`, dann die Seite deployen.
- Farben oder Styles geändert: `global-styles` deployen.
- Header oder Footer geändert: `header` bzw. `footer` deployen.

Nach dem Deploy die Live-Seite aufrufen und die Änderung prüfen. Alle Prüfungen
stehen in `docs/testing.md`.
