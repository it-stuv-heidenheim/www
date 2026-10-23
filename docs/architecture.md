# Architektur

Die StuV-Website ([stuv-heidenheim.de](https://stuv-heidenheim.de)) läuft auf
WordPress mit dem Block-Theme Twenty Twenty-Five. Dieses Repo ist ihre
Content-Quelle: Seiteninhalte, Design-Tokens und Komponenten-CSS liegen hier als
Dateien, und ein Deploy schreibt sie über die REST-API auf die Live-Site.

## Verzeichnisstruktur

| Pfad                        | Zweck                                                                                                                                                                |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data/sections/`            | Startseiten-Sektionen, in Dateinamen-Reihenfolge zusammengefügt (Page-ID 9)                                                                                          |
| `data/pages/<slug>/`        | Unterseiten: `ueber-uns`, `events`, `studentenleben`, `kontakt`, `kummer-karsten`, `linktree`                                                                        |
| `data/patterns/`            | Synchronisierte Muster (Vorsitz), eingebunden per `wp:block`                                                                                                         |
| `data/header_blocks.html`   | Header-Template-Part                                                                                                                                                 |
| `data/footer_blocks.html`   | Footer-Template-Part                                                                                                                                                 |
| `data/global-styles.json`   | Design-Tokens (Layout-Breiten, Farbpalette, Typografie)                                                                                                              |
| `data/styles/component.css` | Komponentenklassen (`.stuv-card`, `.stuv-icon-box`, `.stuv-button-*`) + Dark-Mode-Regeln                                                                             |
| `data/media/`               | Bilder (WebP/JPG/PNG), deployt über das `media`-Ziel                                                                                                                 |
| `data/maps/`                | Kartendefinitionen für `tools/gen_map.py`                                                                                                                            |
| `data/site-state.json`      | Abbild dessen, was nur in wp-admin eingestellt wird (`docs/testing.md`, „Überwachung“); wird nicht deployt                                                           |
| `data/manifest.json`        | Deploy-Ziele: Name → REST-Endpunkt, ID, Quelldatei                                                                                                                   |
| `.agents/skills/`           | Das Deploy-Tooling: Skill `wordpress-default-editor` (`docs/ai-workflow.md`)                                                                                         |
| `tools/`                    | Generatoren und Hilfsskripte (`docs/tools.md`)                                                                                                                       |
| `wp-plugin/`                | Drei WordPress-Plugins: `stuv-mensa` (Live-Speiseplan), `stuv-theme` (Dark-Mode-Toggle) und `stuv-dsgvo` (Klick-zum-Laden für die Kalender), siehe `docs/plugins.md` |
| `docs/`                     | Diese Doku, gelesen auf GitHub                                                                                                                                       |

## Was nicht in diesem Repo liegt

- WordPress-Core und Theme-Dateien. Theme (Twenty Twenty-Five) und Plugins sind
  auf dem Host installiert. `wp-plugin/` versioniert nur den Quellcode der
  eigenen Plugins; die installierten Kopien sind Artefakte.
- Code von Drittanbieter-Plugins. WPForms (Kontakt- und
  Kummer-Karsten-Formular) läuft komplett auf dem Host. In den Seiteninhalten
  stehen nur Formular-ID und Wrapper-Markup (`docs/content-editing.md`), das
  Aussehen steht in `data/styles/component.css`.
  The SEO Framework liefert Meta-Beschreibung, Open Graph, Twitter Card,
  JSON-LD und `sitemap.xml`. Beschreibungen und Vorschaubild werden in wp-admin
  gepflegt und liegen in der Datenbank.
- Was nur in wp-admin eingestellt wird: Einstellungen, Seitentitel, Slugs und
  Templates, aktive Plugins, Dateien der Mediathek, die nicht aus
  `data/media/` kommen, die SEO-Texte und die Felder der
  Formulare. Bearbeitet wird das in wp-admin, nicht hier. `data/site-state.json`
  hält aber fest, wie es gerade aussieht, und die Action **Monitor** meldet
  jede Abweichung (`docs/testing.md`). Ginge die Datenbank verloren, steht dort,
  was neu einzutragen ist.
- Was weder die REST-API noch die Seite zeigt, fehlt auch in diesem Abbild: vor
  allem die Benachrichtigungen der Formulare, also wer eine Nachricht bekommt,
  dazu die Einstellungen von WP-Optimize, AIOS und UpdraftPlus. Die
  Formular-Empfänger stehen absichtlich nicht im öffentlichen Repo. Dafür gibt
  es zwei Sicherungen außerhalb: die Backups von UpdraftPlus (in wp-admin
  prüfen, ob sie auf einem externen Speicher landen und nicht nur auf dem
  Server) und ein Export der Formulare (WPForms → Werkzeuge → Exportieren), den
  jemand aus dem Vorsitz nach jeder Formularänderung an einem eigenen Ort ablegt.
- Ein Build-Schritt. Die Content-Dateien gehen unverändert über die REST-API
  raus; es gibt keinen Static-Site-Generator.

Die übrige Doku ist im [README](../README.md) verlinkt.
