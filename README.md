# StuV DHBW Heidenheim — Website

Inhalte der Live-WordPress-Site der Studierendenvertretung (StuV) DHBW
Heidenheim: Gutenberg-Block-HTML, Design-Tokens und Komponenten-CSS, deployt
über die WordPress-REST-API.

Die Doku steht auch im AStA-Wiki (BookStack):
[wiki.dhbw-asta.de](https://wiki.dhbw-asta.de/). Quelle bleibt das Markdown in
`docs/`; `tools/export_docs_wiki.py` bereitet es zum Einfügen in eine
Wiki-Seite auf.

**Anfangen**

- **Neu hier?** → [Architektur-Übersicht](docs/architecture.md)
- **Inhalte bearbeiten** → [Content Editing Guide](docs/content-editing.md)
- **Neue Seite anlegen** → [Seite hinzufügen](docs/adding-a-page.md)

**Nachschlagen**

- **Farben, Karten, Buttons** → [Design-System](docs/design-system.md)
- **Karten, Icons, PDF-Export** → [Werkzeuge](docs/tools.md)
- **Speiseplan, Dark-Mode** → [Plugins](docs/plugins.md)
- **Was vor dem Deploy prüfen?** → [Prüfen und Testen](docs/testing.md)
- **Warum sieht das Repo so aus?** → [AI-Workflow](docs/ai-workflow.md)

**Drumherum**

- **Tooling** (Deploy, Rollback, Validierung): `wordpress-default-editor`-Skill — ohne den lässt sich hier nichts deployen
- **Arbeitsanleitung für Agents**: `AGENTS.md`
- **Vorgänger** (Next.js-Design-Quelle, archiviert 2026-07-10): separat archiviert
