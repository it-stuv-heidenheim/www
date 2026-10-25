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
(`docs/testing.md`). Welche Skripte es gibt und was sie tun, steht in seiner
`SKILL.md` unter „Scripts“.

Die Grenzen für den Agent stehen in `AGENTS.md`, und jede ist aus einem Schaden
entstanden, etwa eine von Hand bearbeitete generierte Datei oder ein Bild, das
als `-1`-Kopie neben dem alten landete (`docs/tools.md`).

## Deploy per GitHub Action

Deployt wird über die Action **Deploy** (`.github/workflows/deploy.yml`), nicht
mehr vom eigenen Rechner. Gestartet wird sie nur von Hand, unter **Actions →
Deploy → Run workflow** oder mit `gh workflow run deploy.yml`. Andere Branches
deployen nie.

Ein Push auf `main` startet nur die Prüfungen. So können mehrere Commits auf
`main` liegen, bevor jemand deployt, und ein einziger Lauf bringt sie alle auf
die Seite. Bis dahin meldet die Action **Monitor** täglich eine Warnung, dass
die Seite hinter `main` liegt (`docs/testing.md`). Früher startete jeder Push
einen Deploy; wer nicht jeden freigab, hatte bald eine Schlange wartender Läufe,
in der der älteste alle anderen aufhielt.

Geschrieben wird erst nach einer Freigabe: Das Environment `production` hat
**Required reviewers**, und der Deploy-Job wartet, bis einer von ihnen unter
**Review deployments** auf **Approve** klickt. An diesem Repo arbeiten
wechselnde StuV-Mitglieder, keine Vollzeit-Entwickler. Ohne die Freigabe
könnte jeder mit Schreibrechten einen unfertigen Stand auf die öffentliche Seite
bringen. Die Action ersetzt
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
  prüfen (nur noch Formatierung?) und einen neuen Lauf mit dem Ziel unter
  **overwrite** starten.
- **Verwerfen:** einen neuen Lauf starten und das Ziel unter **overwrite**
  eintragen. Die Änderung ist dann weg, das Backup im Artefakt bleibt.

Die Freigabe kommt vor dieser Prüfung. Wer freigibt, muss also nicht selbst
nachsehen, ob in wp-admin etwas geändert wurde.

### Was ein Lauf macht

1. Alle Prüfungen aus `checks.yml`, darunter der Dry-Run.
2. Warten auf die Freigabe.
3. `deploy.py`, mit denselben Zielen und `--overwrite` wie lokal. Es vergleicht
   jedes Ziel mit der Live-Seite und teilt die abweichenden in `BEHIND` und
   `EDITED` ein (siehe oben). Mit `changed` (Standard) nimmt es alle
   abweichenden. Ist eines der zu schreibenden Ziele `EDITED` und steht nicht
   unter `overwrite`, bricht es ab, bevor es schreibt. `media` läuft immer mit,
   lädt aber nur Dateien hoch, die noch nicht in der Mediathek liegen. Statt
   `changed` gehen auch `all` oder einzelne Zielnamen, mit Leerzeichen
   getrennt. Jedes geschriebene Ziel liest es sofort zurück und bricht ab,
   wenn die Seite es nicht so ausliefert; nach `global-styles` prüft es auch
   die `markers` aus `data/manifest.json`.
4. Die Backups vor dem Schreiben als Artefakt `wp-backup-<Nummer>`, 30 Tage
   lang (Rollback in `docs/testing.md`).

Die Action deployt mit dem Skill aus demselben Commit wie der Inhalt. Es läuft
immer nur ein Deploy, und ein Lauf, der auf seine Freigabe wartet, zählt dabei
mit: Ein zweiter Lauf wartet hinter ihm. Einen Lauf, den du nicht freigeben
willst, deshalb unter **Review deployments** ablehnen, statt ihn liegen zu
lassen; sonst bricht GitHub ihn erst nach 30 Tagen ab.

Nicht über die Action laufen: ein Bild unter derselben URL ersetzen
(`replace_media()`, `AGENTS.md` unter „Media“) und die Plugins (ZIP-Upload in
wp-admin, `docs/plugins.md`). Hängt eine Inhaltsänderung an einem Plugin (etwa
`stuv-events` mit `global-styles`, `homepage` und `events`), erst das ZIP
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
  denn ohne sie deployt jeder Lauf ohne Rückfrage.

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

Allerdings kann jeder, der einen Workflow auf `main` pusht, dieses Passwort ohne
Freigabe benutzen. Deshalb ein eigener Benutzer, den man sperren kann, ohne den
Deploy-Zugang anzufassen.
