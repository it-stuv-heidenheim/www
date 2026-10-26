# Inhalte bearbeiten

Texte, Namen, Fotos und Links ändern, ohne WordPress-Wissen; Git und Kommandozeile genügen. Nötig sind Node.js (Prettier, Block-Validierung) und Python 3. Nur zum lokalen Deployen: eine git-ignorierte `.env` mit `WP_USER`, `WP_APP_PASS` (Application Password), `WP_SITE` und `WP_REST_ROOT="wp-json"`.

Bricht jeder Deploy mit `HTTP Error 404` ab, obwohl die Seite läuft: in wp-admin **Einstellungen → Permalinks → Speichern** klicken.

## Wo was liegt

| Inhalt                            | Datei                                                |
| --------------------------------- | ---------------------------------------------------- |
| Startseite                        | `data/sections/` (nummeriert, in Reihenfolge)        |
| Unterseiten                       | `data/pages/<slug>/`                                 |
| Vorsitz (Startseite und Über uns) | `data/patterns/vorsitz.html`                         |
| Header, Footer                    | `data/header_blocks.html`, `data/footer_blocks.html` |
| Farben und Schrift                | `data/global-styles.json`                            |
| Komponenten-Styles                | `data/styles/component.css`                          |
| Bilder                            | `data/media/`                                        |

## Text

In einem Texteditor (nicht Word) nur den Text zwischen den Tags ändern; die `<!-- wp:… -->`-Kommentare bleiben, wie sie sind:

```html
<!-- wp:paragraph -->
<p>Hier steht der Text.</p>
<!-- /wp:paragraph -->
```

- Umlaute ausschreiben (ä, ö, ü, ß), außer in URL-Slugs wie `ueber-uns`.
- In den JSON-Strings der Block-Kommentare ist `--` als `\u002d\u002d` geschrieben (z. B. `var(\u002d\u002dstuv-muted)`), weil `--` in HTML-Kommentaren verboten ist. Nie zu `--` „korrigieren“.
- Viele Absätze haben Farbe und Größe aus einer Klasse (`.stuv-body-muted`, `.stuv-section-intro`), deshalb zeigt die Editor-Seitenleiste „kein Wert“. Geändert wird die Klasse in `component.css`. Eine in der Seitenleiste gesetzte Farbe gewinnt und weicht dann ab, also lieber zurücksetzen.
- Der Vorsitz steht nur in `data/patterns/vorsitz.html` (synchronisiertes Muster 212, `<!-- wp:block {"ref":212} /-->`); deployt wird `pattern-vorsitz`, nicht die Seiten.

## Bild ersetzen

1. Das neue Bild unter einem **neuen Dateinamen** nach `data/media/` legen, möglichst WebP. Ein alter Name wird beim Media-Deploy übersprungen (`AGENTS.md`, „Media“).
2. `media` deployen; die Ausgabe nennt die URL (`neues-bild.webp -> https://…/wp-content/uploads/neues-bild.webp (id 123)`):

   ```bash
   source .env
   python3 .agents/skills/wordpress-default-editor/scripts/deploy.py --manifest data/manifest.json media
   ```

3. In der Seitendatei `src` (ohne Host, ab `/wp-content/`, damit Staging und Produktion funktionieren) und `alt` ändern, dann die Seite deployen.

Fotos mit `stuv-media` (Seitenkopf, Eventarten-Karten, Leiste „Mitmachen“) bekommen ihr Seitenverhältnis vom Block. Vorher zuschneiden: WebP, 1200 px breit im Seitenkopf, 960 px in Karten, 640 px in der Leiste, ohne Metadaten (`magick … -strip`, wegen GPS-Koordinaten). Erkennbare Personen nur mit deren Einverständnis.

## Nach einer Wahl

Am besten mit dem alten Vorsitz in einem Durchgang abarbeiten.

- [ ] **Vorsitz** (`data/patterns/vorsitz.html`): Vorname, Foto, Zitat ersetzen; bei anderer Personenzahl eine ganze `stuv-card`-Gruppe kopieren oder löschen. Fotos 480 × 480 px, neuer Name (`vorsitz-2027-lena.jpg`, nie einen alten wiederverwenden), `alt` „Porträt von Lena“. Nur mit Einverständnis.
- [ ] **Referate** (`data/pages/ueber-uns/02-referate.html`) ändern sich nur, wenn eines dazukommt oder wegfällt. Anker sind Linkziele (`#event`, `#sport`); `test_content.py` meldet tote Links. Neue oder weggefallene Kanäle in `CONTACTS` (`tools/test_content.py`) pflegen.
- [ ] Prüfen ([testing.md](testing.md)), deployen (`changed` nimmt `media`, `pattern-vorsitz`, `ueber-uns`), Startseite und Über uns ansehen, auch auf dem Handy.
- [ ] **Alte Fotos** bleiben unter ihrer URL abrufbar: aus `data/media/` löschen und committen, nach dem Deploy auch in wp-admin unter **Medien**. `tools/site_state.py` darf sie danach nicht mehr unter `media_not_in_repo` nennen.
- [ ] WPForms-Empfänger von Kontakt und Kummer Karsten umstellen, frischen Export ablegen ([architecture.md](architecture.md)).
- [ ] WordPress-Konten und Application Passwords der Ausgeschiedenen löschen (die der Actions bleiben); GitHub-Zugriff und Reviewer von `production` anpassen.

## Google-Kalender

Die Kalender-ID (`c_05fa…@group.calendar.google.com`) steht fünfmal im Markup: in den beiden `<iframe data-stuv-src>` (Startseite `data/sections/02-was-wir-bieten.html`, kompakt mit `mode=AGENDA`, 380px; Events `data/pages/events/02-upcoming.html`, 600px), den beiden Fallback-Links und dem Abonnieren-Link (`calendar/render?cid=…`). Beim Wechsel alle fünf ersetzen.

Parameter: `ctz=Europe%2FBerlin`, `wkst=2` (Montag), `hl=de`, `show…=0` (blendet Googles Bedienelemente aus), `bgcolor=%23fcfcfc&color=%23E2001A` (Hex-Werte, Google liest keine CSS-Variablen).

Die Iframes sind `wp:html`-Blöcke, weil der native Embed-Block immer ein `src` schreibt ([plugins.md](plugins.md), `stuv-dsgvo`). `scrolling="no"` fehlt absichtlich: Auf schmalen Bildschirmen braucht die Agenda Scrollen.

## Formulare (WPForms)

| Seite          | Datei                                    | Formular-ID |
| -------------- | ---------------------------------------- | ----------- |
| Kontakt        | `data/pages/kontakt/03-form.html`        | 129         |
| Kummer Karsten | `data/pages/kummer-karsten/03-form.html` | 132         |

```html
<!-- wp:group {"className":"stuv-card stuv-wpforms"} -->
<div class="wp-block-group stuv-card stuv-wpforms">
  <!-- wp:shortcode -->
  [wpforms id="129"]
  <!-- /wp:shortcode -->
</div>
<!-- /wp:group -->
```

Felder, Pflichtangaben, Bestätigungstext und Empfänger nur in wp-admin → WPForms; ins Repo gehören nur ID und Karte. Neues Formular: in wp-admin bauen, ID in dieses Muster. Das Aussehen steht in den `.stuv-wpforms`-Regeln (`global-styles`). WPForms' CSS lädt später, deshalb wiederholen die Regeln die volle Ahnenkette (`.stuv-wpforms .wpforms-container-full .wpforms-form …`) statt `!important`; greift eine Regel nicht, ist der Selektor meist zu kurz.

## Formatieren, prüfen, deployen

`npx prettier --write .` und die Prüfungen aus [testing.md](testing.md). Ein Push startet nur die Prüfungen; live geht es über die Action **Deploy** (**Actions → Deploy → Run workflow**, dann **Review deployments → Approve**). Sie nimmt alles, was von der Live-Seite abweicht, und bricht bei wp-admin-Änderungen ab ([ai-workflow.md](ai-workflow.md)).

Lokal:

```bash
source .env
SKILL=.agents/skills/wordpress-default-editor
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json all --dry-run
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json changed   # oder Zielnamen
```

Ziele: `homepage`, `ueber-uns`, `events`, `studentenleben`, `kontakt`, `kummer-karsten`, `linktree`, `header`, `footer`, `global-styles`, `media`, `pattern-vorsitz`. Ein in wp-admin geändertes Ziel nur mit `--overwrite <ziel>`. Danach die Live-Seite ansehen.
