# Architektur

WordPress mit dem Block-Theme Twenty Twenty-Five. Dieses Repo ist die Content-Quelle; ein Deploy schreibt sie über die REST-API auf die Live-Site. Es gibt keinen Build-Schritt.

| Pfad                        | Inhalt                                                                                     |
| --------------------------- | ------------------------------------------------------------------------------------------ |
| `data/sections/`            | Startseite (Page-ID 9), in Dateinamen-Reihenfolge zusammengefügt                           |
| `data/pages/<slug>/`        | Unterseiten                                                                                |
| `data/patterns/`            | Synchronisierte Muster (Vorsitz), eingebunden per `wp:block`                               |
| `data/header_blocks.html`   | Header-Template-Part (ebenso `footer_blocks.html`)                                         |
| `data/global-styles.json`   | Design-Tokens                                                                              |
| `data/styles/component.css` | Komponentenklassen und Dark Mode                                                           |
| `data/media/`, `data/maps/` | Bilder; Kartendefinitionen für `tools/gen_map.py`                                          |
| `data/manifest.json`        | Deploy-Ziele: Name → REST-Endpunkt, ID, Quelle                                             |
| `data/site-state.json`      | Abbild der wp-admin-Einstellungen ([testing.md](testing.md)), nicht deployt                |
| `.agents/skills/`           | Deploy-Tooling ([ai-workflow.md](ai-workflow.md))                                          |
| `tools/`                    | Generatoren und Prüfskripte ([tools.md](tools.md))                                         |
| `wp-plugin/`                | Plugins `stuv-mensa`, `stuv-events`, `stuv-theme`, `stuv-dsgvo` ([plugins.md](plugins.md)) |

## Nicht in diesem Repo

- WordPress-Core, Theme und Drittanbieter-Plugins. WPForms (Formulare): im Inhalt stehen nur Formular-ID und Wrapper, das Aussehen in `component.css`. The SEO Framework: Meta-Texte, Open Graph, JSON-LD, `sitemap.xml`, gepflegt in wp-admin.
- Was nur in wp-admin eingestellt wird (Einstellungen, Seitentitel, Slugs, Templates, Plugins, Mediathek, SEO-Texte, Formularfelder). `data/site-state.json` hält es fest, die Action **Monitor** meldet Abweichungen.
- Was auch dort fehlt: Formular-Empfänger (absichtlich, das Repo ist öffentlich) und die Einstellungen von WP-Optimize, AIOS und UpdraftPlus. Sicherung: UpdraftPlus-Backups auf externem Speicher und ein WPForms-Export (Werkzeuge → Exportieren), den der Vorsitz nach jeder Formularänderung ablegt.
