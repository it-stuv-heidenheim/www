# Website der StuV DHBW Heidenheim

Die WordPress-Site der Studierendenvertretung (StuV) der DHBW Heidenheim besteht aus Gutenberg-Block-HTML, Design-Tokens und Komponenten-CSS. Deployt wird über die WordPress-REST-API.

## Anfangen

- [Architektur-Übersicht](docs/architecture.md), wenn du neu hier bist
- [Inhalte bearbeiten](docs/content-editing.md)
- [Neue Seite anlegen](docs/adding-a-page.md)

## Nachschlagen

- [Design-System](docs/design-system.md): Farben, Schrift, Karten, Buttons
- [Werkzeuge](docs/tools.md): Landkarten und Icons
- [Plugins](docs/plugins.md): Speiseplan, Dark Mode, Kalender
- [Prüfen und Testen](docs/testing.md): was vor einem Deploy zu prüfen ist
- [AI-Workflow](docs/ai-workflow.md): warum das Repo so aufgebaut ist

## Drumherum

- Deploy, Rollback und Validierung liegen im `wordpress-default-editor`-Skill unter `.agents/skills/`. Deployt wird über die GitHub Action **Deploy**: Man startet sie von Hand, ein Reviewer gibt sie frei.
- `AGENTS.md` ist die Arbeitsanleitung für Agents.
- Die Vorgängerseite, eine Next.js-App und Quelle des Designs, ist seit dem 2026-07-10 separat archiviert.
