# AI-Workflow

Die meisten Änderungen an diesem Repo macht ein KI-Agent, konkret
[Claude Code](https://claude.com/claude-code). Das erklärt einige Teile der
Struktur, die sonst willkürlich wirken: die Datei `AGENTS.md` im
Wurzelverzeichnis und die Deploy-Skripte, die woanders liegen.

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

## Warum das Tooling nicht in diesem Repo liegt

`deploy.py`, der REST-Client und der Block-Validator liegen in einem eigenen,
generischen Skill-Repository. Für diese Site gibt es davon einen
[ZIP-Schnappschuss zum Herunterladen](https://stuv-heidenheim.de/wp-content/uploads/wordpress-default-editor.zip),
entpackt nach `~/.claude/skills/`.

Das Tooling ist nicht StuV-spezifisch: Es bearbeitet jede WordPress-Site mit
Block-Editor über die REST-API. Läge es hier, könnte es nur dieses eine Repo
nutzen. Die Aufteilung entspricht der zwischen einem Programm und seinen Daten:

```
Skill-Repository          →  das Tool (generisch, mehrere Sites)
dieses Repository         →  der Inhalt   (nur StuV, mehrere Tools)
```

Ohne ausgecheckten Skill kannst du hier also nichts deployen (Voraussetzungen in
`docs/content-editing.md`).

## Der Skill `wordpress-default-editor`

Ein „Skill“ ist ein Markdown-Dokument mit einer Anleitung, die der Agent lädt,
wenn sie zur Aufgabe passt, hier zusammen mit den Skripten, die sie beschreibt.
Der Skill wird in einem separaten Repository gepflegt (ZIP-Schnappschuss siehe
oben) und enthält alles Lauffähige:

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

## Warum kein Auto-Deploy

Keine GitHub Action deployt bei einem Push. Einen Deploy löst ein Mensch per
Befehl aus, nach einem Dry-Run und mit Blick auf das Ergebnis.

An diesem Repo arbeiten wechselnde StuV-Mitglieder, keine Vollzeit-Entwickler.
Mit Auto-Deploy stünde jeder unbedachte Commit sofort auf der öffentlichen
Seite.

Geprüft wird dagegen auch automatisch: `.github/workflows/checks.yml` führt bei
jedem Push die Prüfungen aus `docs/testing.md` aus. Der Lauf liest nur, braucht
kein Secret und schreibt nichts auf die Seite. Ein roter Lauf heißt: erst
reparieren, dann deployen.
