# Neue Seite anlegen

1. **Inhalt:** `data/pages/<slug>/01-….html` anlegen (Slug klein, Bindestriche, keine Umlaute), am einfachsten eine bestehende Seite kopieren, z. B. `data/pages/kontakt/01-pageheader.html`. Der Deploy fügt alle `*.html` des Verzeichnisses in Dateinamen-Reihenfolge zu einer Seite zusammen.
2. **WordPress:** In wp-admin Seiten → Erstellen, nur den Titel eingeben (er erscheint nicht), Template `page-no-title`, veröffentlichen. Keinen Inhalt eingeben: Eine leere Seite überschreibt der Deploy, Inhalt hält er für eine wp-admin-Bearbeitung (`EDITED`) und bricht ab. Die ID steht in der URL (`post.php?post=99`).
3. **Manifest:** in `data/manifest.json` eintragen:

   ```json
   "dein-slug": {
     "type": "structural",
     "endpoint": "pages",
     "id": 99,
     "source": "pages/dein-slug",
     "status": "publish"
   }
   ```

4. **Prüfen:** `npx prettier --write .`, dann die Checks aus [testing.md](testing.md).
5. **Deployen:**

   ```bash
   source .env
   SKILL=.agents/skills/wordpress-default-editor
   python3 $SKILL/scripts/deploy.py --manifest data/manifest.json dein-slug --dry-run
   python3 $SKILL/scripts/deploy.py --manifest data/manifest.json dein-slug
   ```

6. **Verlinken:** Menüeintrag in `data/header_blocks.html` (Ziel `header`) oder Links von anderen Seiten; dann `https://stuv-heidenheim.de/<slug>/` ansehen.
