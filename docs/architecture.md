# Architecture

Die StuV-Website ([stuv-heidenheim.de](https://stuv-heidenheim.de)) läuft auf
WordPress mit dem Twenty-Twenty-Five-Block-Theme. Dieses Repo ist die
**Content-Quelle** — Seiteninhalte, Design-Tokens und Komponenten-CSS liegen als
Dateien vor und werden per REST-API auf die Live-Site deployt.

## Verzeichnisstruktur

| Pfad                        | Zweck                                                                                                                                                                |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data/sections/`            | Startseiten-Sektionen, in Dateinamen-Reihenfolge zusammengefügt (Page-ID 10)                                                                                         |
| `data/pages/<slug>/`        | Unterseiten: `ueber-uns`, `events`, `studentenleben`, `kontakt`, `kummer-karsten`, `linktree`                                                                        |
| `data/header_blocks.html`   | Header-Template-Part                                                                                                                                                 |
| `data/footer_blocks.html`   | Footer-Template-Part                                                                                                                                                 |
| `data/global-styles.json`   | Design-Tokens (Layout-Breiten, Farbpalette, Typografie)                                                                                                              |
| `data/styles/component.css` | Komponentenklassen (`.stuv-card`, `.stuv-icon-box`, `.stuv-button-*`) + Dark-Mode-Regeln                                                                             |
| `data/media/`               | Bilder (WebP/JPG/PNG), deployt über das `media`-Ziel                                                                                                                 |
| `data/maps/`                | Kartendefinitionen für `tools/gen_map.py`                                                                                                                            |
| `data/manifest.json`        | Deploy-Ziele: Name → REST-Endpunkt, ID, Quelldatei                                                                                                                   |
| `tools/`                    | Generatoren und Hilfsskripte (`docs/tools.md`)                                                                                                                       |
| `wp-plugin/`                | Drei WordPress-Plugins: `stuv-mensa` (Live-Speiseplan), `stuv-theme` (Dark-Mode-Toggle) und `stuv-dsgvo` (Klick-zum-Laden für die Kalender), siehe `docs/plugins.md` |
| `docs/`                     | Diese Doku — Quelle für das AStA-Wiki (`wiki.dhbw-asta.de`), Export mit `tools/export_docs_wiki.py`                                                                  |
| `.claude/skills/`           | Repo-lokale Agent-Verfahren (`docs/ai-workflow.md`)                                                                                                                  |

## Was dieses Repo NICHT ist

- **Kein lauffähiges WordPress-Tooling.** Deploy-Skripte, Block-Validator und
  REST-Client liegen im `wordpress-default-editor`-Skill, hier als
  [herunterladbarer ZIP-Schnappschuss](/wp-content/uploads/wordpress-default-editor.zip)
  (entpackt nach `~/.claude/skills/wordpress-default-editor`).
- **Keine WordPress-Core- oder Theme-Dateien.** Theme (Twenty Twenty-Five) und
  Plugins sind auf dem Host installiert; `wp-plugin/` versioniert nur den
  Plugin-Quellcode, die installierten Kopien sind Artefakte.
- **Kein Drittanbieter-Plugin-Code.** WPForms (Kontakt- und
  Kummer-Karsten-Formular) läuft komplett auf dem Host, nirgends in diesem
  Repo versioniert — nur Formular-ID und Wrapper-Markup stehen in den
  Seiteninhalten (`docs/content-editing.md`), das Aussehen in
  `data/styles/component.css`.
- **Kein Build-Schritt.** Content-Dateien werden unverändert per REST-API
  deployt; es gibt keinen Static-Site-Generator.

## Wo steht was

| Thema                               | Doku                      |
| ----------------------------------- | ------------------------- |
| Inhalt ändern, deployen             | `docs/content-editing.md` |
| Neue Seite anlegen                  | `docs/adding-a-page.md`   |
| Farben, Schrift, Komponenten        | `docs/design-system.md`   |
| Generatoren (Karten, Icons)         | `docs/tools.md`           |
| Plugins (`mensa`, `theme`, `dsgvo`) | `docs/plugins.md`         |
| Prüfen und Testen                   | `docs/testing.md`         |
| Warum das Repo so aussieht          | `docs/ai-workflow.md`     |
| Agent-Referenz mit Fallstricken     | `AGENTS.md`               |
