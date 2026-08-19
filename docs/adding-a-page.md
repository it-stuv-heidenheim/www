# Neue Seite anlegen

So erstellst du eine neue Unterseite auf der StuV-Website — von Null auf live.

## Voraussetzungen

- Git-Zugriff auf dieses Repo
- WordPress-Admin-Zugang (zum Anlegen der Seite in wp-admin)
- `.env`-Datei mit Deploy-Credentials
- Das `wordpress-default-editor`-Skill unter `~/.claude/skills/wordpress-default-editor`
  (siehe Voraussetzungen in `docs/content-editing.md`)
- Node.js für `npx prettier` und Block-Validierung

## Schritt 1: Verzeichnis und erste Content-Datei anlegen

URL-Slug wählen (Kleinbuchstaben, Bindestriche, keine Umlaute).
Verzeichnis und erste Datei erstellen:

```bash
mkdir -p data/pages/dein-slug
```

`data/pages/dein-slug/01-content.html` mit dem Seiteninhalt befüllen.
Eine existierende Seite als Vorlage nehmen — z. B.
`data/pages/kontakt/01-pageheader.html` kopieren und Text ersetzen:

```html
<!-- wp:group {"align":"full","style":{"spacing":{"padding":{"top":"var:preset|spacing|80","bottom":"var:preset|spacing|80"}}},"layout":{"type":"constrained"}} -->
<div
  class="wp-block-group alignfull"
  style="padding-top:var(--wp--preset--spacing--80);padding-bottom:var(--wp--preset--spacing--80)"
>
  <!-- wp:heading -->
  <h2 class="wp-block-heading">Deine Überschrift</h2>
  <!-- /wp:heading -->

  <!-- wp:paragraph -->
  <p>Dein Inhalt hier.</p>
  <!-- /wp:paragraph -->
</div>
<!-- /wp:group -->
```

Jede Datei wird mit ihren Geschwistern zusammengefügt (sortiert nach Dateiname)
und als eine Seite deployt. Weitere Dateien (`02-weiteres.html`,
`03-kontakt.html`) nach Bedarf hinzufügen.

## Schritt 2: Seite ins Manifest eintragen

Neuen Eintrag in `data/manifest.json` ergänzen:

```json
"dein-slug": {
  "type": "structural",
  "endpoint": "pages",
  "id": 99,
  "source": "pages/dein-slug",
  "status": "publish"
}
```

Das `id`-Feld muss mit der WordPress-Page-ID übereinstimmen (siehe Schritt 3).
Zunächst einen Platzhalter eintragen.

## Schritt 3: Seite in WordPress anlegen

1. In wp-admin einloggen.
2. Seiten → Erstellen.
3. Titel eingeben (erscheint nicht im Frontend wegen `page-no-title`-Template).
4. In der Seiten-Seitenleiste unter „Template“ die Vorlage `page-no-title`
   auswählen.
5. Veröffentlichen.
6. Page-ID aus der URL notieren:
   `wp-admin/post.php?post=99&action=edit` → ID ist `99`.
7. `data/manifest.json` mit der echten ID aktualisieren.

## Schritt 4: Formatieren und validieren

```bash
npx prettier --write .
```

Block-Validierung siehe `docs/testing.md` unter „Block-Validierung“.

## Schritt 5: Deployen

```bash
source .env
SKILL=~/.claude/skills/wordpress-default-editor
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json dein-slug --dry-run
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json dein-slug
```

## Schritt 6: Neue Seite verlinken

Navigationslink im Header oder von anderen Seiten aus setzen. Die URL lautet:

```
https://stuv-heidenheim.de/?pagename=dein-slug
```

Für einen Eintrag im Hauptmenü den Header-Block in
`data/header_blocks.html` bearbeiten und `header` deployen.

Danach die Live-URL besuchen und prüfen, ob die Seite korrekt gerendert wird.
Ob die Page-ID zur gemeinten WordPress-Seite gehört, zeigt erst der echte
Deploy plus der Blick auf die Seite — der Dry-Run prüft nur lokal.
