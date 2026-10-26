# AI-Workflow

Die meisten Änderungen macht ein KI-Agent ([Claude Code](https://claude.com/claude-code)). `AGENTS.md` (Englisch) enthält seine Anweisungen, nur das Nötigste, weil jede Zeile Kontext kostet; `docs/` (Deutsch) erklärt für Menschen.

## Skill `wordpress-default-editor`

`.agents/skills/wordpress-default-editor/` enthält Anleitung (`SKILL.md`), Skripte (REST-Client, `deploy.py`, Block-Validator) und Tests. Er ist nicht StuV-spezifisch; was nur für diese Site gilt, steht in `data/manifest.json`, `AGENTS.md` oder `docs/`. Er liegt seit Oktober 2026 im Repo, damit Tooling und Inhalt im selben Commit landen.

## Deploy per GitHub Action

Die Action **Deploy** (`.github/workflows/deploy.yml`) startet nur von Hand (**Actions → Deploy → Run workflow** oder `gh workflow run deploy.yml`), nur auf `main`. Ein Push startet nur die Prüfungen; bis zum Deploy warnt **Monitor** täglich, dass die Seite hinter `main` liegt. Geschrieben wird erst, wenn ein **Required reviewer** des Environments `production` unter **Review deployments** freigibt: Es arbeiten wechselnde StuV-Mitglieder am Repo.

Ein Lauf:

1. Prüfungen aus `checks.yml`, darunter der Dry-Run.
2. Warten auf die Freigabe.
3. `deploy.py` mit den Zielen (Standard `changed`, sonst `all` oder Namen) und `--overwrite`. Jedes abweichende Ziel ist `BEHIND` (ein älterer Commit hatte den Live-Stand; nichts geht verloren) oder `EDITED` (kein Commit hatte ihn: eine wp-admin-Änderung). Ein `EDITED`-Ziel ohne `overwrite` stoppt den Lauf vor dem ersten Schreiben, der Diff steht im Log. `media` lädt nur neue Dateien hoch. Jedes Ziel wird zurückgelesen, bei `global-styles` auch die `markers`.
4. Backups als Artefakt `wp-backup-<Nummer>`, 30 Tage (Rollback: [testing.md](testing.md)).

Bei `EDITED`: die Änderung nach `data/` übernehmen, committen und, wenn der Diff danach nur noch Formatierung zeigt, mit dem Ziel unter **overwrite** neu starten. Oder verwerfen: gleich mit **overwrite** starten (das Backup bleibt).

Es läuft nur ein Deploy, ein auf Freigabe wartender zählt mit. Einen Lauf, den du nicht freigibst, unter **Review deployments** ablehnen, sonst blockiert er 30 Tage.

Nicht über die Action: ein Bild unter derselben URL ersetzen (`AGENTS.md`, „Media“) und Plugins ([plugins.md](plugins.md)). Hängt Inhalt an einem Plugin, erst das ZIP hochladen, dann freigeben.

## Einrichtung

Unter **Settings → Environments**, beide nur für den Branch `main`, mit der Variable `WP_SITE` = `https://stuv-heidenheim.de` und den Secrets `WP_USER`, `WP_APP_PASS` eines eigenen WordPress-Administrators (Application Password, einzeln sperrbar):

- `production`: **Required reviewers** sind Pflicht. Starten darf jeder mit Schreibrechten, freigeben nur Reviewer.
- `monitor`: ohne Reviewer (läuft täglich, schreibt nichts). Wer einen Workflow auf `main` pusht, kann dieses Passwort ohne Freigabe nutzen, deshalb ein eigener Benutzer.
