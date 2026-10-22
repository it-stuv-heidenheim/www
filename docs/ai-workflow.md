# AI-Workflow

Die meisten Änderungen an diesem Repo macht ein KI-Agent, konkret
[Claude Code](https://claude.com/claude-code). Das erklärt einige Teile der
Struktur, die sonst willkürlich wirken: die Datei `AGENTS.md` im
Wurzelverzeichnis und die Deploy-Skripte unter `.agents/skills/`.

Dieses Dokument erklärt das System. Die Anweisungen an den Agent stehen in
`AGENTS.md`.

## Die Rollenverteilung

| Datei       | Adressat  | Sprache  | Zweck                                                         |
| ----------- | --------- | -------- | ------------------------------------------------------------- |
| `AGENTS.md` | der Agent | Englisch | Anweisung: Konventionen, Deploy-Befehle, Fallstricke          |
| `docs/*.md` | Menschen  | Deutsch  | Erklärung: wie die Site aufgebaut ist, wie man sie bearbeitet |

Wer Anweisung und Erklärung mischt, hat am Ende zwei Dokumente über dieselbe
Sache, die auseinanderdriften.

Der Agent lädt `AGENTS.md` in jeder Sitzung, und jede Zeile darin kostet
Kontext. Die Datei enthält deshalb nur, was ein Agent wissen muss, um nichts
kaputtzumachen: Fallstricke, exakte Befehle, harte Regeln. Erklärungen gehören
nach `docs/`.

## Warum das Tooling unter `.agents/skills/` liegt

`deploy.py`, der REST-Client und der Block-Validator liegen in
`.agents/skills/wordpress-default-editor/`, dem werkzeugunabhängigen Ort für
die Skills eines Projekts, so wie `AGENTS.md` der werkzeugunabhängige Ort für
die Anweisungen ist; für Menschen sind es gewöhnliche Python- und Node-Skripte,
aufgerufen aus dem Wurzelverzeichnis.

Bis Oktober 2026 lag der Skill in einem privaten Skill-Repository, und dieses
Repo trug einen ZIP-Schnappschuss davon. Seit er hier liegt, sieht jeder, mit
welchem Stand deployt wird, und eine Änderung am Tooling landet im selben
Commit wie der Inhalt, der sie braucht.

Das Tooling selbst ist nicht StuV-spezifisch: Es bearbeitet jede WordPress-Site
mit Block-Editor über die REST-API. Was nur für diese Site gilt, gehört nach
`data/manifest.json`, `AGENTS.md` oder `docs/`, nicht in den Skill.

## Der Skill `wordpress-default-editor`

Ein „Skill“ ist ein Markdown-Dokument mit einer Anleitung, die der Agent lädt,
wenn sie zur Aufgabe passt, hier zusammen mit den Skripten, die sie beschreibt.
Der Skill enthält alles Lauffähige, dazu eigene Tests unter `tests/`
(`docs/testing.md`):

| Skript                           | Zweck                                                             |
| -------------------------------- | ----------------------------------------------------------------- |
| `wp_block_api.py`                | REST-Client (Auth, Backup, eigener User-Agent)                    |
| `deploy.py`                      | Deployer, gesteuert von `data/manifest.json`                      |
| `rollback.py`                    | Deploy rückgängig machen (nicht für Medien)                       |
| `upload_media.py`                | Bild-Upload                                                       |
| `fix_has_text_color.py`          | Nachrüsten fehlender `has-text-color`-Klassen                     |
| `verify_global_css.py`           | Prüft, ob WordPress das deployte CSS unbeschädigt gespeichert hat |
| `blockcheck/validate_blocks.cjs` | Gutenberg-Block-Validator                                         |

## Was ein Agent hier nicht darf

Diese Grenzen stehen in `AGENTS.md`, und jede ist aus einem Schaden entstanden:

- Generierte Dateien nie von Hand bearbeiten. Der nächste Generatorlauf
  überschreibt die Karten-Blöcke und den Icon-CSS-Abschnitt ohne Meldung
  (`docs/tools.md`).
- Kein `--force` bei Medien. WordPress legt dann eine umbenannte Datei an
  (`karte-…-1.webp`), auf die nichts verweist (`docs/tools.md`).

## Deploy per GitHub Action

Deployt wird über die Action **Deploy** (`.github/workflows/deploy.yml`), nicht
mehr vom eigenen Rechner. Sie startet nie von selbst: Ein Push deployt nichts.
Einen Deploy löst ein Mensch aus, unter **Actions → Deploy → Run workflow**, und
zwar nur vom Branch `main`.

An diesem Repo arbeiten wechselnde StuV-Mitglieder, keine Vollzeit-Entwickler.
Mit Auto-Deploy stünde jeder unbedachte Commit sofort auf der öffentlichen
Seite. Der Start per Hand hält diesen Schritt bewusst; die Action ersetzt nur
das lokale Skript, damit niemand dafür den Skill und eine `.env` mit
Zugangsdaten braucht.

Geprüft wird dagegen auch automatisch: `.github/workflows/checks.yml` führt bei
jedem Push die Prüfungen aus `docs/testing.md` aus. Der Lauf liest nur, braucht
kein Secret und schreibt nichts auf die Seite. Die Deploy-Action ruft dieselben
Prüfungen zuerst auf und deployt nur, wenn sie grün sind.

### Was ein Lauf macht

1. Alle Prüfungen aus `checks.yml`.
2. Den Dry-Run.
3. Die Ziele bestimmen. Mit `changed` (Standard) vergleicht
   `verify_deploy.py` jedes Ziel mit der Live-Seite und nimmt die, die
   abweichen. Der Diff steht im Log; er zeigt auch, was eine Änderung in
   wp-admin wäre, die der Deploy jetzt überschreibt. `media` läuft immer mit,
   lädt aber nur Dateien hoch, die noch nicht in der Mediathek liegen. Statt
   `changed` gehen auch `all` oder einzelne Zielnamen, mit Leerzeichen
   getrennt.
4. Den Deploy, danach `verify_deploy.py` für die deployten Ziele und nach
   `global-styles` auch `verify_global_css.py`.
5. Die Backups vor dem Schreiben als Artefakt `wp-backup-<Nummer>`, 30 Tage
   lang (Rollback in `docs/testing.md`).

Die Action deployt mit dem Skill aus demselben Commit wie der Inhalt.

Nicht über die Action laufen: ein Bild unter derselben URL ersetzen (löschen
und neu hochladen, `AGENTS.md` unter „Media“) und die Plugins (ZIP-Upload in
wp-admin, `docs/plugins.md`).

### Einmalige Einrichtung

Unter **Settings → Environments** ein Environment `production` anlegen:

- **Deployment branches**: nur `main`.
- **Variable** `WP_SITE` = `https://stuv-heidenheim.de` (mit Schema).
- **Secrets** `WP_USER` und `WP_APP_PASS`: ein eigener WordPress-Benutzer
  für die Action (Rolle Administrator, sonst darf er die Global Styles nicht
  schreiben) mit einem eigenen Application Password. So lässt sich der Zugang
  sperren, ohne jemandes persönlichen Login anzufassen.
- Optional **Required reviewers**: Dann wartet jeder Lauf vor dem Deploy auf
  eine Freigabe.

Starten darf die Action jeder mit Schreibrechten am Repo.
