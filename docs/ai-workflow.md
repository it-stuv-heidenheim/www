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
mehr vom eigenen Rechner. Sie startet bei jedem Push auf `main`, der etwas unter
`data/` oder an den Deploy-Skripten des Skills ändert, und von Hand unter
**Actions → Deploy → Run workflow**. Andere Branches deployen nie.

Geschrieben wird erst nach einer Freigabe: Das Environment `production` hat
**Required reviewers**, und der Deploy-Job wartet, bis einer von ihnen unter
**Review deployments** auf **Approve** klickt. An diesem Repo arbeiten
wechselnde StuV-Mitglieder, keine Vollzeit-Entwickler. Ohne die Freigabe stünde
jeder unbedachte Commit sofort auf der öffentlichen Seite. Die Action ersetzt
nur das lokale Skript, damit niemand dafür den Skill und eine `.env` mit
Zugangsdaten braucht.

Was jemand in wp-admin geändert hat, überschreibt die Action nicht stillschweigend.
Sie vergleicht jedes Ziel mit der Live-Seite und sucht den Live-Stand in der
Git-Historie. Steht er dort, hinkt die Seite nur hinterher (`BEHIND`), und der
Deploy verliert nichts. Steht er nirgends, kann er nur aus wp-admin kommen
(`EDITED`). Dann bricht der Lauf ab, bevor er irgendetwas schreibt, und der Diff
im Log zeigt die Änderung. Weiter geht es auf einem von zwei Wegen:

- **Übernehmen:** die Änderung aus dem Diff in die Dateien unter `data/`
  einarbeiten, committen und pushen. Weil WordPress Blöcke anders formatiert
  als Prettier, gilt das Ziel danach meist immer noch als `EDITED`. Den Diff
  prüfen (nur noch Formatierung?) und den Lauf von Hand mit dem Ziel unter
  **overwrite** starten.
- **Verwerfen:** den Lauf von Hand starten und das Ziel unter **overwrite**
  eintragen. Die Änderung ist dann weg, das Backup im Artefakt bleibt.

Die Freigabe kommt vor dieser Prüfung. Wer freigibt, muss also nicht selbst
nachsehen, ob in wp-admin etwas geändert wurde.

Geprüft wird dagegen auch automatisch: `.github/workflows/checks.yml` führt bei
jedem Push die Prüfungen aus `docs/testing.md` aus. Der Lauf liest nur, braucht
kein Secret und schreibt nichts auf die Seite. Die Deploy-Action ruft dieselben
Prüfungen zuerst auf und deployt nur, wenn sie grün sind.

### Was ein Lauf macht

1. Alle Prüfungen aus `checks.yml`.
2. Warten auf die Freigabe.
3. Den Dry-Run.
4. Die Ziele bestimmen. `verify_deploy.py --history` vergleicht jedes Ziel mit
   der Live-Seite und teilt die abweichenden in `BEHIND` und `EDITED` ein (siehe
   oben). Mit `changed` (Standard, bei einem Push immer) nimmt die Action alle
   abweichenden. Ist eines der zu schreibenden Ziele `EDITED` und steht nicht
   unter `overwrite`, bricht sie hier ab. `media` läuft immer mit, lädt aber
   nur Dateien hoch, die noch nicht in der Mediathek liegen. Statt `changed`
   gehen auch `all` oder einzelne Zielnamen, mit Leerzeichen getrennt.
5. Den Deploy, danach `verify_deploy.py` für die deployten Ziele und nach
   `global-styles` auch `verify_global_css.py`.
6. Die Backups vor dem Schreiben als Artefakt `wp-backup-<Nummer>`, 30 Tage
   lang (Rollback in `docs/testing.md`).

Die Action deployt mit dem Skill aus demselben Commit wie der Inhalt. Warten
mehrere Läufe, behält GitHub nur den neuesten; mit `changed` deckt er die Pushes
davor mit ab.

Nicht über die Action laufen: ein Bild unter derselben URL ersetzen (löschen
und neu hochladen, `AGENTS.md` unter „Media“) und die Plugins (ZIP-Upload in
wp-admin, `docs/plugins.md`). Hängt eine Inhaltsänderung an einem Plugin (etwa
`stuv-dsgvo` mit `global-styles`, `homepage` und `events`), erst das ZIP
hochladen und dann den Deploy freigeben.

### Einmalige Einrichtung

Unter **Settings → Environments** ein Environment `production` anlegen:

- **Deployment branches**: nur `main`.
- **Variable** `WP_SITE` = `https://stuv-heidenheim.de` (mit Schema).
- **Secrets** `WP_USER` und `WP_APP_PASS`: ein eigener WordPress-Benutzer
  für die Action (Rolle Administrator, sonst darf er die Global Styles nicht
  schreiben) mit einem eigenen Application Password. So lässt sich der Zugang
  sperren, ohne jemandes persönlichen Login anzufassen.
- **Required reviewers**: die Leute, die Deploys freigeben dürfen. Pflicht,
  denn ohne sie deployt jeder Push auf `main` sofort.

Starten darf die Action jeder mit Schreibrechten am Repo, freigeben nur die
Reviewer.

Für die Action **Monitor** (`docs/testing.md`) ein zweites Environment
`monitor` anlegen:

- **Deployment branches**: nur `main`.
- **Variable** `WP_SITE` wie oben.
- **Secrets** `WP_USER` und `WP_APP_PASS`: wieder ein eigener Benutzer mit
  eigenem Application Password, Rolle Administrator. Nur Administratoren lesen
  Template-Parts, Global Styles und die Plugin-Liste.
- **Keine Reviewer.** Die Action läuft täglich und schreibt nichts; mit
  Freigabe käme jeder Lauf erst an, wenn jemand klickt.

Der Preis: Wer einen Workflow auf `main` pusht, kann dieses Passwort ohne
Freigabe benutzen. Deshalb ein eigener Benutzer, den man sperren kann, ohne den
Deploy-Zugang anzufassen.
