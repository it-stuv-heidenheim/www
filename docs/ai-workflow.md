# AI-Workflow

Die meisten Änderungen an diesem Repo macht ein KI-Agent, konkret
[Claude Code](https://claude.com/claude-code). Das erklärt einige Teile der
Struktur, die sonst willkürlich wirken: die Datei `AGENTS.md` im
Wurzelverzeichnis, das Verzeichnis `docs/superpowers/` und die Deploy-Skripte,
die woanders liegen.

Dieses Dokument erklärt das System. Die Anweisungen an den Agent stehen in
`AGENTS.md`.

## Die Rollenverteilung

| Datei             | Adressat  | Sprache  | Zweck                                                         |
| ----------------- | --------- | -------- | ------------------------------------------------------------- |
| `AGENTS.md`       | der Agent | Englisch | Anweisung: Konventionen, Deploy-Befehle, Fallstricke          |
| `docs/*.md`       | Menschen  | Deutsch  | Erklärung: wie die Site aufgebaut ist, wie man sie bearbeitet |
| `.agents/skills/` | der Agent | Englisch | Verfahren: wiederverwendbare Arbeitsabläufe für dieses Repo   |

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

## Die Skills

Ein „Skill“ ist ein Markdown-Dokument mit einer Anleitung, die der Agent lädt,
wenn sie zur Aufgabe passt. Drei Sorten kommen hier vor.

### 1. `wordpress-default-editor`: das Tool

Extern, gepflegt in einem separaten Repository (ZIP-Schnappschuss siehe oben).
Enthält alles Lauffähige:

| Skript                           | Zweck                                                             |
| -------------------------------- | ----------------------------------------------------------------- |
| `wp_block_api.py`                | REST-Client (Auth, Backup, eigener User-Agent)                    |
| `deploy.py`                      | Deployer, gesteuert von `data/manifest.json`                      |
| `rollback.py`                    | Deploy rückgängig machen (nicht für Medien)                       |
| `upload_media.py`                | Bild-Upload                                                       |
| `fix_has_text_color.py`          | Nachrüsten fehlender `has-text-color`-Klassen                     |
| `verify_global_css.py`           | Prüft, ob WordPress das deployte CSS unbeschädigt gespeichert hat |
| `blockcheck/validate_blocks.cjs` | Gutenberg-Block-Validator                                         |

### 2. `improving-code`: das Verfahren für dieses Repo

Liegt in `.agents/skills/improving-code/`. Der Skill legt fest, was „bessere
Qualität“ hier heißt (weniger Duplikation, vorhandene `.stuv-*`-Klassen und
Patterns wiederverwenden statt neue anlegen), und verlangt einen Nachweis: Eine
Aufräumaktion muss auf dem deployten Content ein verifizierter No-Op sein, oder
die Abweichung muss benannt werden.

Er liegt im Repo, weil er Wissen über diesen Content enthält (Block-HTML,
`component.css`, Design-Tokens). Für eine andere Site wäre er falsch.

### 3. `superpowers`: der Prozess

Global installiert, nicht Teil dieses Repos. Eine Sammlung allgemeiner Verfahren
für Softwarearbeit; hier sieht man davon vor allem den Zyklus, der
`docs/superpowers/` füllt.

## Der Zyklus: Brainstorm → Spec → Plan → Execute

Größere Änderungen laufen in vier Schritten, mit Freigaben dazwischen:

```
Brainstorm  →  Spec                  →  Plan                  →  Execute
(Dialog)       docs/superpowers/       docs/superpowers/         Code + Verifikation
               specs/*-design.md       plans/*.md
```

1. Brainstorm: Dialog über Zweck, Randbedingungen und Alternativen. Am Ende
   steht eine Entscheidung; Code entsteht hier noch keiner.
2. Spec (`docs/superpowers/specs/JJJJ-MM-TT-thema-design.md`): das _Was_ und
   _Warum_. Wird vor dem Plan freigegeben.
3. Plan (`docs/superpowers/plans/JJJJ-MM-TT-thema.md`): das _Wie_, aufgeteilt
   in abhakbare Schritte mit Verifikationsbefehlen.
4. Execute: Der Agent arbeitet den Plan Schritt für Schritt ab.

Teuer wird es, wenn der Agent die Aufgabe missversteht. An Spec und Plan fällt
ein Missverständnis auf, solange es einen Absatz kostet statt 600 Zeilen Code.

Einen Tippfehler, einen neuen Termin oder ein ausgetauschtes Foto erledigt man
direkt. Der Dialog lohnt sich ungefähr ab dem Punkt, an dem eine Entscheidung
ansteht, die man falsch treffen kann.

### Lebenszyklus von Specs und Plans

Ist ein Spec oder Plan umgesetzt, wird die Datei aus dem Verzeichnisbaum
gelöscht (Präzedenzfall: Commit `6a19d0a`). Was in `docs/superpowers/` liegt,
ist also noch offen.

In der Git-Historie bleiben die Dateien erhalten. Einen Verweis auf ein
erledigtes Spec schreibt man deshalb als Befehl und nicht als Pfad:

```bash
git show 6a19d0a^:docs/superpowers/specs/2026-07-13-mensa-live-menu-design.md
```

Ein nackter Pfad sähe aus wie eine existierende Datei und liefe unbemerkt ins
Leere. Vor dem Löschen also den Baum nach Verweisen durchsuchen.

## Was ein Agent hier nicht ohne Rückfrage darf

Diese Grenzen stehen als harte Regeln in `AGENTS.md`, und jede ist aus einem
Schaden entstanden:

- Headless-Browser (Puppeteer, Playwright) nur mit Freigabe. Ein Lauf
  installiert oft Chrome (mehrere hundert MB) und ruft die Live-Site auf.
- Umlaute nie pauschal ersetzen. Ein Suchen-und-Ersetzen `ae→ä` zerstört `neue`
  und `Wohnungssuche`, und URL-Slugs müssen Digraphen bleiben
  (`?pagename=ueber-uns`).
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
