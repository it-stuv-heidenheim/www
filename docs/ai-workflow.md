# AI-Workflow

Dieses Repo wird überwiegend mit KI-Agents bearbeitet — konkret mit
[Claude Code](https://claude.com/claude-code). Das erklärt einen Teil der
Struktur, der sonst willkürlich wirkt: die Datei `AGENTS.md` im
Wurzelverzeichnis, das Verzeichnis `docs/superpowers/`, und den Umstand, dass
die Deploy-Skripte nicht in diesem Repo liegen.

Dieses Dokument **erklärt** das System. Es ist keine Anweisung an den Agent —
das ist `AGENTS.md`.

## Die Rollenverteilung

| Datei             | Adressat    | Sprache  | Zweck                                                                |
| ----------------- | ----------- | -------- | -------------------------------------------------------------------- |
| `AGENTS.md`       | der Agent   | Englisch | Anweisung: Konventionen, Deploy-Befehle, Fallstricke                 |
| `docs/*.md`       | Menschen    | Deutsch  | Erklärung: wie die Site aufgebaut ist, wie man sie bearbeitet        |
| `CLAUDE.md`       | Claude Code | —        | Einzeiler, der `AGENTS.md` einbindet (Claude Code liest `CLAUDE.md`) |
| `.claude/skills/` | der Agent   | Englisch | Verfahren: wiederverwendbare Arbeitsabläufe für dieses Repo          |

`AGENTS.md` weist an, `docs/` erklärt. Wer beides vermischt, bekommt zwei
Dokumente über dieselbe Sache, die auseinanderdriften.

`AGENTS.md` wird bei jeder Agent-Sitzung automatisch geladen und kostet damit
Kontext. Es enthält deshalb nur, was ein Agent zwingend wissen muss, um nichts
kaputtzumachen: Fallstricke, exakte Befehle, harte Regeln. Alles Erklärende
gehört hierher.

## Warum das Tooling nicht in diesem Repo liegt

Dieses Repo enthält **kein lauffähiges WordPress-Tooling** — kein `deploy.py`,
keinen REST-Client, keinen Block-Validator. Die liegen im separaten, generischen
Skill-Repository. Für diese Site steht die Tooling-Fassung als
[herunterladbarer ZIP-Schnappschuss](/wp-content/uploads/wordpress-default-editor.zip)
bereit, entpackt nach `~/.claude/skills/`.

Der Grund ist Wiederverwendbarkeit: Das Tooling ist nicht StuV-spezifisch. Es
bearbeitet _irgendeine_ WordPress-Site mit dem Block-Editor über die REST-API.
Läge es hier, wäre es an dieses eine Repo gefesselt. Die Aufteilung ist
dieselbe wie zwischen einem Programm und seinen Daten:

```
Skill-Repository          →  das Tool (generisch, mehrere Sites)
dieses Repository         →  der Inhalt   (nur StuV, mehrere Tools)
```

Praktische Konsequenz: **Ohne ausgechecktes Skill-Repo kann man hier nichts
deployen.** Siehe Voraussetzungen in `docs/content-editing.md`.

## Die Skills

Ein „Skill“ ist ein Markdown-Dokument mit einer Anleitung, die der Agent bei
passender Gelegenheit lädt. Drei Sorten sind hier im Spiel:

### 1. `wordpress-default-editor` — das Tool

Extern; als [herunterladbarer ZIP-Schnappschuss](/wp-content/uploads/wordpress-default-editor.zip)
verfügbar, gepflegt in einem separaten Repository. Enthält alles
Lauffähige:

| Skript                           | Zweck                                                             |
| -------------------------------- | ----------------------------------------------------------------- |
| `wp_block_api.py`                | REST-Client (Auth, Backup, User-Agent für Cloudflare)             |
| `deploy.py`                      | Deployer, gesteuert von `data/manifest.json`                      |
| `rollback.py`                    | Deploy rückgängig machen (nicht für Medien)                       |
| `upload_media.py`                | Bild-Upload                                                       |
| `fix_has_text_color.py`          | Nachrüsten fehlender `has-text-color`-Klassen                     |
| `verify_global_css.py`           | Prüft, ob WordPress das deployte CSS unbeschädigt gespeichert hat |
| `blockcheck/validate_blocks.cjs` | Gutenberg-Block-Validator                                         |

### 2. `improving-code` — das Verfahren für dieses Repo

Repo-lokal, in `.claude/skills/improving-code/`. Beschreibt, was „bessere
Qualität“ hier konkret heißt (weniger Duplikation, Wiederverwendung
existierender `.stuv-*`-Klassen und Patterns statt neuer) und schreibt einen
Nachweis vor: Eine Aufräumaktion muss ein verifizierter No-Op auf dem
deployten Content sein, oder die Abweichung muss benannt werden.

Repo-lokal, weil es Wissen über _diesen_ Content kodiert — Block-HTML,
`component.css`, Design-Tokens. Für eine andere Site wäre es falsch.

### 3. `superpowers` — der Prozess

Global installiert, nicht Teil dieses Repos. Ein Satz allgemeiner Verfahren
für Softwarearbeit; hier sichtbar wird davon vor allem der Zyklus, der
`docs/superpowers/` füllt.

## Der Zyklus: Brainstorm → Spec → Plan → Execute

Größere Änderungen laufen nicht als „Agent, bau mal“, sondern in vier Schritten
mit Freigaben dazwischen:

```
Brainstorm  →  Spec                  →  Plan                  →  Execute
(Dialog)       docs/superpowers/       docs/superpowers/         Code + Verifikation
               specs/*-design.md       plans/*.md
```

1. **Brainstorm** — Dialog über Zweck, Randbedingungen, Alternativen. Ergebnis
   ist eine Entscheidung, kein Code.
2. **Spec** (`docs/superpowers/specs/JJJJ-MM-TT-thema-design.md`) — das
   _Was_ und _Warum_. Wird vor dem Plan freigegeben.
3. **Plan** (`docs/superpowers/plans/JJJJ-MM-TT-thema.md`) — das _Wie_,
   aufgeteilt in abhakbare Schritte mit Verifikationsbefehlen.
4. **Execute** — der Plan wird Schritt für Schritt abgearbeitet.

Die teuren Fehler entstehen beim Missverstehen, nicht beim Tippen. Spec und
Plan sind Haltepunkte, an denen ein Missverständnis noch einen Absatz kostet
und nicht 600 Zeilen.

Nicht jede Änderung braucht das. Ein Tippfehler, ein neuer Termin, ein
ausgetauschtes Foto — direkt machen. Die Schwelle ist ungefähr: Sobald es eine
Entscheidung gibt, die man falsch treffen kann, lohnt der Dialog.

### Lebenszyklus von Specs und Plans

**Erledigte Specs und Plans werden aus dem Verzeichnisbaum gelöscht**
(Präzedenzfall: Commit `6a19d0a`). `docs/superpowers/` listet damit offene
Arbeit — was dort liegt, ist noch nicht umgesetzt.

Gelöscht heißt nicht weg: Die Dateien bleiben in der Git-Historie. Ein Verweis
auf ein erledigtes Spec wird deshalb als Befehl geschrieben, nicht als Pfad:

```bash
git show 6a19d0a^:docs/superpowers/specs/2026-07-13-mensa-live-menu-design.md
```

Ein nackter Pfad sieht aus wie eine existierende Datei und verrottet unbemerkt
— genau das war einmal der Fall: Vier Verweise in `AGENTS.md` und `docs/todo.md`
zeigten monatelang ins Leere, und ein noch offener Plan (Logo-Umstellung)
wurde beim Aufräumen mitgelöscht. Deshalb: **vor dem Löschen den Baum nach
Verweisen durchsuchen.**

## Was ein Agent hier nicht ohne Rückfrage darf

Diese Grenzen stehen als harte Regeln in `AGENTS.md`. Sie sind alle aus Schaden
entstanden:

- **Kein Headless-Browser ohne Freigabe** — Puppeteer/Playwright, auch
  `tools/export_pdfs.mjs`. Ein Lauf installiert Chrome (mehrere hundert MB)
  und ruft die Live-Site auf.
- **Umlaute nie pauschal ersetzen** — ein `ae→ä`-Suchen-und-Ersetzen zerstört
  `neue` und `Wohnungssuche`. URL-Slugs müssen Digraphen bleiben
  (`?pagename=ueber-uns`).
- **Generierte Dateien nie von Hand bearbeiten** — die Karten-Blöcke und der
  Icon-CSS-Abschnitt werden beim nächsten Generatorlauf stillschweigend
  überschrieben. Siehe `docs/tools.md`.
- **Kein `--force` bei Medien** — WordPress benennt die Datei um, die alte URL
  bleibt tot. Siehe `docs/tools.md`.

## Warum kein CI

Es gibt keine GitHub Action, die bei Push deployt. Ein Deploy ist ein Befehl,
den ein Mensch auslöst, nach einem Dry-Run und mit Blick auf das Ergebnis.

Die Zielgruppe dieses Repos sind wechselnde StuV-Mitglieder, nicht
Vollzeit-Entwickler. Ein Auto-Deploy würde bedeuten, dass ein unbedachter
Commit sofort auf der öffentlichen Seite steht.

Die Prüfungen laufen lokal, von Hand — siehe `docs/testing.md`.
