# SEO-Plugin `stuv-seo` (Plan)

Datum: 2026-08-05

> **Stand 2026-08-19:** Zwei Verweise in diesem Plan sind seit dem Wiki-Umzug
> überholt. `tools/gen_docs_page.py` und das `docs`-Deploy-Target existieren
> nicht mehr — die Doku wird mit `tools/export_docs_wiki.py` exportiert und von
> Hand ins BookStack-Wiki eingefügt. `docs/not-public/todo.md` ist repo-intern
> und liegt nicht in diesem Repository. Mit `/docs/` ist außerdem eine Seite
> weggefallen: Wo unten „acht Seiten“ steht, sind es jetzt **sieben**.

## Ausgangslage

Das Audit vom 2026-08-05 fand auf allen acht Seiten von `dev.stuv-heidenheim.de`
null `meta name="description"`, null Open Graph, null Twitter Card und null
JSON-LD — derselbe Stand wie auf der abgelösten Elementor-Seite. Jeder Link, den
jemand in WhatsApp oder Instagram teilt, erscheint als graue Zeile ohne Bild und
ohne Beschreibung. Für eine StuV ist genau das der Hauptverbreitungsweg.

Kopfzeilen-Ausgabe kann nicht aus dem Block-HTML dieses Repos kommen
(`unfiltered_html`-Regel in `AGENTS.md`), also ist es ein Plugin. Kein Yoast,
kein RankMath: Die Überarbeitung hat die Startseite von 49 Stylesheets und 34
Skripten auf 2 und 6 gebracht, und beide Plugins geben davon einen Teil zurück.
Ihre Oberfläche setzt außerdem eine Person voraus, die SEO-Dashboards liest —
der StuV-Vorstand wechselt jährlich.

Das wird das **vierte** Plugin in `wp-plugin/`. `stuv-dsgvo` ist das
Vorbild für Form und Umfang.

## Entscheidungen

### E1 — Admin-Oberfläche: Metabox plus Einstellungsseite, kein Sidebar-Panel

Pro Seite eine klassische Metabox (`add_meta_box`), sitewide eine
Einstellungsseite unter Einstellungen → StuV SEO. Beides reines PHP, dazu eine
kleine `assets/admin.js` für Zeichenzähler und Medienauswahl.

Die Alternative wäre ein Panel in der Seitenleiste des Block-Editors
(`PluginDocumentSettingPanel`). Preis dafür, ausgeschrieben:

- **Mit Build-Schritt (JSX):** `package.json`, `@wordpress/scripts`,
  `node_modules`, ein gebautes `build/index.js`, das entweder eingecheckt oder
  in `build.sh` erzeugt wird. Das wäre die **erste npm-Abhängigkeit des Repos**
  — die Regel „keine npm-Abhängigkeiten“ (`docs/plugins.md`, `AGENTS.md`) fiele
  für einen Textarea und eine Checkbox. Prettier läuft heute über `npx` genau
  deshalb.
- **Ohne Build-Schritt:** `wp.element.createElement` von Hand, also React ohne
  JSX. Kein npm, aber unlesbarer Code, der auf Editor-Globals sitzt, die sich
  zwischen WP-Versionen verschieben (`wp.editPost.PluginDocumentSettingPanel`
  ist seit 6.6 zugunsten von `wp.editor.…` veraltet). Für ein Repo, dessen
  Wartung jährlich die Hände wechselt, ist das die teuerste Variante.

`add_meta_box` und die Settings API sind seit über fünfzehn Jahren stabil und
brauchen null Werkzeug. Der Preis der Metabox: Sie erscheint im Block-Editor
**unterhalb** der Seite, nicht in der Seitenleiste. Das ist der bewusst
akzeptierte Nachteil — und für eine Person, die einmal im Jahr eine Beschreibung
ändert, ist ein sichtbarer Kasten unter dem Text vermutlich auffindbarer als ein
zugeklapptes Panel.

Gespeichert wird trotzdem über `register_post_meta` mit `show_in_rest`. Das ist
kein Widerspruch: Die Registrierung gibt Sanitizer, `auth_callback` und
REST-Lesbarkeit, die Metabox ist nur die Eingabe dazu.

### E2 — Beschreibungen leben in der Datenbank, nicht im Manifest

`docs/not-public/todo.md` §0.4 will ein `seo`-Objekt je Target im Manifest,
„damit Titel und Description versioniert sind statt nur im Plugin zu leben“. Die
Titel-Hälfte ist gegenstandslos (siehe E3). Für die Description lautet die
Entscheidung: **Datenbank, und die Todo-Zeile wird gestrichen statt umgesetzt.**

Gründe:

- Randbedingung 1 verlangt, dass ein Vorstandsmitglied ohne Git-Zugang die
  Beschreibung ändern kann. Ein Wert im Repo plus ein Wert in der Datenbank ist
  ein System mit zwei Schreibern und keinem Schiedsrichter.
- Die Description ist derselbe Datentyp wie der Titel: kurze Prosa, gepflegt von
  der Person, die die Seite schreibt, ohne Kopplung an das Block-Markup. Der
  Titel hat diese Eigenschaften bereits — datenbankeigen, in wp-admin
  bearbeitbar, für `verify_deploy.py` unsichtbar, von keinem Deploy angefasst.
  Die Description bekommt dieselben.
- `verify_deploy.py` vergleicht `content.raw` gegen die zusammengefügten
  Quellen. Post-Meta taucht darin nicht auf, also bleibt die Prüfung grün.
  Würden Beschreibungen deployt, machte jede Bearbeitung in wp-admin daraus
  **permanente Drift** — genau der Fehlermodus, an dem `"style":{}` gescheitert
  ist (`AGENTS.md`): Dauerrauschen, das echte Drift zudeckt.
- `deploy.py` schreibt `content` und `status`. Ein REST-`POST` ohne `meta`-Feld
  lässt Post-Meta unangetastet. Deploy kann eine Vorstandsbearbeitung also nicht
  überschreiben — nicht weil wir aufpassen, sondern weil das Feld nie im Aufruf
  steht.

Die Variante „Repo-Wert als Seed, Post-Meta überschreibt“ wird verworfen: Wer
sieht dann, dass eine Seite vom committeten Wert abgewichen ist? Nur ein neues
Werkzeug, das REST liest — und REST-lesende Skripte gehören laut `AGENTS.md`
nicht nach `tools/`, sondern ins Skill-Repo. Ein Vergleichsskript in einem
anderen Repository, das eine Drift meldet, die niemand auflösen darf, ist keine
Versionierung, sondern eine zweite Baustelle.

Was dadurch verloren geht, ehrlich benannt: Acht handgeschriebene Beschreibungen
stehen dann nur in der Datenbank. Absicherung ist das Site-Backup und der
WordPress-Export (Werkzeuge → Daten exportieren), der Post-Meta mitnimmt —
dieselbe Absicherung wie für die Seitentitel und die WPForms-Formulare. Falls
§0.5 („Formulare nach `data/forms/` exportieren“) je umgesetzt wird, kann ein
SEO-Export im selben Mechanismus mitfahren — als **Schnappschuss, nie als
Quelle**.

### E3 — Titel: nichts im Plugin, kein Gegenargument gefunden

Vorgabe war, Titel außen vor zu lassen; der Auftrag ließ Gegenrede zu. Es gibt
keine. Core liefert bereits `<Seite> – <blogname>`, `post_title` ist frei
editierbar, und weil alle Seiten `page-no-title` verwenden, speist er praktisch
nur `<title>`. Ein Plugin-Override dupliziert ein funktionierendes Feld und
schafft die Frage „welcher von beiden gewinnt“, wo heute keine ist. Das
Titelmuster selbst ist Core-Verhalten (`wp_get_document_title()`), nicht
Theme-Code — es gibt nichts zu überschreiben.

Eine Lücke bleibt trotzdem: Niemand sieht, ob ein Titel über 60 Zeichen liegt.
Antwort darauf ist Diagnose statt Kontrolle — die Einstellungsseite zeigt je
Seite die Titellänge **schreibgeschützt** an (Schritt 6). Damit erfüllt der Plan
die Absicht von §0.4, ohne den Titel anzufassen.

### E4 — Canonical: nichts tun

Core hängt `rel_canonical()` an `wp_head` und gibt für singuläre Ansichten — und
die statische Startseite ist eine — einen korrekten `<link rel="canonical">`
aus, gebaut aus `home_url()`. Der zeigt heute auf den Staging-Host und nach dem
DNS-Umzug automatisch auf Produktion. Ein zweites Canonical wäre schlimmer als
keins.

Also: **kein Canonical-Code im Plugin**, aber ein Prüfschritt vor dem Rest
(Schritt 0). Fehlt das Tag wider Erwarten, ist die Reparatur, Core wieder
einzuhängen, nicht ein eigenes zu schreiben. `og:url` kommt aus
`wp_get_canonical_url()`, damit die beiden nicht auseinanderlaufen können.

### E5 — Fold-ins

| Fold-in                            | Urteil   | Kurzbegründung                                                                               |
| ---------------------------------- | -------- | -------------------------------------------------------------------------------------------- |
| `robots.txt` über `robots_txt`     | **Ja**   | Aber praktisch leer; einziger Inhalt ist der Staging-Riegel. Siehe unten.                    |
| Search-Console-Verifikation        | **Ja**   | Ein Feld, eine Zeile Ausgabe, überlebt den Amtswechsel besser als ein DNS-TXT-Record.        |
| Staging `noindex`                  | **Ja**   | Nimmt den „Haken vergessen“-Fehlermodus. Invertiert Randbedingung 2 — nginx bleibt der Gurt. |
| Staging → Canonical auf Produktion | **Nein** | Widersprüchliches Signal zu `noindex`, und heute zeigt es auf eine Domain ohne Inhalt.       |
| 301-Karte für alte Slugs           | **Ja**   | Eigene Datei, nur bei 404. Aber: Die Slug-Liste existiert noch nicht (siehe Risiken).        |
| `fetchpriority`-Korrektur          | **Nein** | Quellseitiger Inhaltsfix — das Header-Markup ist handgeschrieben, nicht generiert.           |

**`robots.txt` (ja, aber minimal).** Der Filter kommt, der Standardinhalt ist
leer. Core setzt die `Sitemap:`-Zeile seit 5.5 selbst, `wp-admin` ist bereits
gesperrt, und Suchergebnisseiten sind seit 5.7 über `wp_robots_noindex_search()`
schon `noindex` — eine `Disallow`-Zeile dafür wäre Doppelung. Der Grund, den
Filter trotzdem zu nehmen: Ohne SFTP kommt niemand an eine echte `robots.txt`,
also gibt es sonst keinen wartbaren Ort für die eine Regel, die wirklich nötig
ist — `Disallow: /` auf allem, was nicht der Produktionshost ist. Auf Produktion
gibt das Plugin an `robots.txt` nichts aus. Deaktivieren stellt die
Core-Standardausgabe wieder her.

**Staging-`noindex` (ja, mit offener Inversion).** Der Riegel entscheidet nicht
über eine Datenbank-Option, sondern über eine **Konstante im Code**:
`STUV_SEO_PRODUCTION_HOSTS = ['stuv-heidenheim.de', 'www.stuv-heidenheim.de']`,
verglichen gegen den Host aus `home_url()` (nicht gegen `$_SERVER['HTTP_HOST']`,
der aus dem Request kommt). Unbekannter Host ⇒ `noindex` — fail-closed. Auf
Staging entfällt zusätzlich die Sitemap (`wp_sitemaps_enabled`). Das dreht
Randbedingung 2 um: Deaktivieren macht Staging indexierbar. Deshalb bleibt der
nginx-`X-Robots-Tag` auf `dev.` bestehen; das Plugin ist der zweite Riegel, nicht
der einzige. Der Haken unter Einstellungen → Lesen bleibt nebenbei zulässig,
verliert aber seine tragende Rolle.

**Canonical auf Produktion (nein).** `noindex` ist eine Anweisung, `canonical`
ein Hinweis; beides gleichzeitig auf verschiedene Ziele zu setzen ist genau das
widersprüchliche Signal, das der Auftrag bei „`noindex` plus Sitemap-Eintrag“
zu Recht rügt. Dazu kommt: Solange Produktion nicht ausgeliefert wird, zeigte
das Canonical auf eine Adresse ohne Inhalt. Nach dem Umzug ist es überflüssig,
weil dann Produktion selbst ausliefert.

**301-Karte (ja, eigene Datei).** `inc/redirects.php`, eingehängt auf
`template_redirect` und **nur** dann aktiv, wenn `is_404()` — damit kostet sie
auf jedem normalen Request nichts und berührt die Meta-Schicht an keiner Stelle.
Das entkräftet den Einwand „das ist keine `wp_head`-Sache“: Als reine
404-Auffangschicht ist sie eine eigene Ebene mit eigener Datei und eigenem Test.
Deaktivieren bringt die 404er zurück — schlechter, nicht kaputt. Ausgeliefert
wird zuerst mit **302**, damit ein Fehler nicht in Browser-Caches einbrennt;
nach der Prüfung Umstellung auf 301.

**`fetchpriority` (nein).** Der Auftrag stellt das Logo als
Template-Part-Problem dar, das nur ein Filter lösen kann. Das trifft hier nicht
zu: `data/header_blocks.html` ist handgeschriebenes Markup in einem
`wp:html`-Block, nichts daran wird generiert (generiert sind nur Karten und
Icon-CSS, `docs/tools.md`). Damit fällt der Punkt unter die Regel, die der
Auftrag selbst für den Hero-WebP-Tausch aufstellt: quellseitiger Inhaltsfix, und
ein Laufzeitfilter würde falsches Block-HTML dauerhaft übertünchen. Der
eigentliche Gewinn — `fetchpriority="high"` auf dem LCP-Bild, dem Hero-Cover —
ist ohnehin ein Attribut in `data/sections/01-hero.html`. Das gehört zum
Hero-WebP-Todo (§0.1), nicht hierher. **Vorbehalt:** Erst prüfen, ob Core ein
handgeschriebenes `fetchpriority` stehen lässt; überschreibt Core es, kommt der
Punkt als Filter zurück und bekommt `inc/loading.php`. Prüfbefehl in Schritt 0.

### E6 — Deaktivierbarkeit

Randbedingung 2, aufgeschlüsselt wie die Tabelle in `docs/plugins.md`:

| Bestandteil             | Bei Deaktivierung                                              |
| ----------------------- | -------------------------------------------------------------- |
| Meta/OG/Twitter         | Tags fehlen. Seiten rendern unverändert.                       |
| JSON-LD                 | Fehlt. Kein sichtbarer Unterschied.                            |
| `noindex` je Seite      | `/docs/` und `/linktree/` werden wieder indexierbar.           |
| Sitemap-Ausschluss      | Beide Seiten stehen wieder in `wp-sitemap.xml`.                |
| 301-Karte               | Alte URLs geben wieder 404.                                    |
| Staging-Riegel          | **Staging wird indexierbar** — dafür der nginx-`X-Robots-Tag`. |
| Metabox / Einstellungen | Verschwinden. Die gespeicherten Werte bleiben liegen.          |

Kein Shortcode, kein Block, keine CSS-Klasse, keine Rewrite-Rule, keine Tabelle,
kein Transient, **keine Zeile in `data/**.html`, die davon abhängt**. Das ist
prüfbar (Schritt 12) und der Unterschied zu `stuv-theme`, das die Seite bewusst
im Hellmodus einfriert.

### E7 — `uninstall.php` löscht nichts

Die Datei kommt, ihr Rumpf löscht weder Post-Meta noch Optionen. Begründung:

- „Plugin löschen“ ist in wp-admin ein Klick neben „Deaktivieren“, und der
  Update-Dialog („vorhandene Version ersetzen?“) verleitet dazu, stattdessen erst
  zu löschen. Acht handgeschriebene Beschreibungen dafür zu verlieren, ist ein
  schlechter Tausch.
- Die Daten sind klein (rund 24 Zeilen in `wp_postmeta`, eine Option), ohne das
  Plugin völlig inert, und teuer nachzuproduzieren — es ist Prosa, kein Cache.
  Ein Cache oder ein Transient wäre das Gegenbeispiel; davon gibt es hier keinen.
- Die Datei existiert trotzdem, weil ihr Fehlen wie ein Versehen aussieht und die
  nächste Person eine Löschschleife einbaut. Fünf Zeilen Code, ein Absatz
  Begründung.

## Dateien

```
wp-plugin/stuv-seo/
├── stuv-seo.php            Bootstrap: Header, Konstanten, requires, Hooks
├── inc/
│   ├── pure/tags.php       PUR: Werte -> geordnete Tag-Liste
│   ├── pure/faq.php        PUR: geparste Blöcke -> Frage/Antwort-Paare
│   ├── pure/routes.php     PUR: Pfad + Karte -> Ziel oder null
│   ├── meta.php            register_post_meta, Sanitizer, Lesezugriffe
│   ├── admin.php           Metabox, Einstellungsseite, Enqueue
│   ├── head.php            wp_head: Description, OG, Twitter, Verifikation
│   ├── jsonld.php          @graph bauen und ausgeben
│   ├── robots.php          wp_robots, Sitemap-Provider, robots_txt, Staging
│   └── redirects.php       404-Auffang plus die Slug-Karte
├── assets/
│   └── admin.js            Zeichenzähler und Medienauswahl (nur wp-admin)
└── uninstall.php           No-Op mit Begründung
```

`inc/pure/` ist die Testfläche: Diese drei Dateien dürfen **keine**
WordPress-Funktion aufrufen, damit `php wp-plugin/tests/test_*.php` sie ohne
WordPress laden kann — dasselbe Muster wie `stuv-mensa/inc/normalize.php`. Die
Naht ist bewusst so gelegt, dass Escaping außerhalb bleibt: Die pure Schicht gibt
**Datenstrukturen** zurück (`[['property' => 'og:title', 'content' => '…'], …]`),
das Escaping mit `esc_attr()` macht `head.php`.

Speicherorte:

- `_stuv_seo_description` (string), `_stuv_seo_og_image` (int, Attachment-ID),
  `_stuv_seo_noindex` (bool) je Seite. Unterstrich-Präfix heißt „geschützt“,
  also braucht `register_post_meta` einen `auth_callback`
  (`current_user_can('edit_page', $post_id)`).
- Option `stuv_seo_settings` (Array): `og_image`, `google_verification`.
- Produktionshosts als **Konstante im Code**, nicht als Option (E5).

## Schritte

### 0. Prämissen prüfen, bevor irgendetwas gebaut wird

- [ ] Kopfzeilen einer Unterseite und der Startseite abrufen; Cache umgehen
      (`WP-Optimize` liefert sonst eine alte Kopie, `AGENTS.md`):
      `bash
HOST="$(printf '%s' "$WP_SITE" | sed -E 's#^https?://##')"
for p in "" kummer-karsten/ docs/; do
curl -sS -A "stuv-check/1.0" "https://$HOST/$p?cb=$(date +%s)" \
| grep -iE "<title>|rel=.canonical|og:|twitter:|name=.robots|ld\+json|fetchpriority"
done
`
- [ ] Erwartet: genau **ein** Canonical je Seite (bestätigt E4), `robots` nur
      mit `max-image-preview:large`, kein OG, kein JSON-LD.
- [ ] Notieren, welches `<img>` `fetchpriority="high"` trägt. Trägt es das Logo,
      testweise `fetchpriority="low"` im Header-Markup ergänzen und prüfen, ob
      Core es stehen lässt — das entscheidet, ob E5 beim „Nein“ bleibt.
- [ ] `https://$HOST/wp-sitemap.xml` abrufen und die aktuellen Provider notieren
      (Ausgangsstand für Schritt 7).

### 1. Gerüst

- [ ] `wp-plugin/stuv-seo/stuv-seo.php` mit Plugin-Header nach dem Muster von
      `stuv-dsgvo`: deutscher `Description`-Text, der ausdrücklich sagt, was
      Deaktivieren bewirkt („die Tags fehlen dann einfach“), `Requires PHP: 8.0`,
      `Version`, `ABSPATH`-Guard, Versionskonstante.
- [ ] `STUV_SEO_PRODUCTION_HOSTS` als Konstante, plus
      `stuv_seo_is_production(): bool` über `wp_parse_url(home_url(), PHP_URL_HOST)`.
- [ ] `build.sh`: `stuv-seo` in die Standardliste aufnehmen (die Liste hat dann
      vier Einträge — erledigt zugleich die `AGENTS.md`-Zeile aus §0.5).
- [ ] Verifikation: `./wp-plugin/build.sh stuv-seo && unzip -l wp-plugin/stuv-seo.zip`

### 2. Pure Schicht: Tags

- [ ] `inc/pure/tags.php` mit `stuv_seo_meta_tags(array $v): array`. Eingabe:
      `description`, `title`, `url`, `site_name`, `image` (URL, `width`,
      `height`, `alt`), `locale`, `verification`. Ausgabe: geordnete Liste aus
      `['meta' => 'name'|'property', 'key' => …, 'content' => …]`.
- [ ] Regeln, die der Test festnagelt: leere Werte erzeugen **kein** Tag; die
      Description wird nur normalisiert (Tags weg, Whitespace zusammengezogen),
      **nie** gekürzt — stille Kürzung fremden Textes ist der falsche Umgang; ist
      keine Description gesetzt, entfällt sowohl `description` als auch
      `og:description`, es wird nichts aus dem Seiteninhalt zusammengeschustert.
- [ ] Twitter bleibt bewusst kurz: nur `twitter:card = summary_large_image` und
      `twitter:image:alt`. Titel, Beschreibung und Bild liest X laut eigener
      Dokumentation aus den OG-Tags; ein zweiter Satz derselben Strings kann nur
      auseinanderlaufen. Kein `twitter:site` — es gibt kein Konto.
- [ ] `og:locale` aus `get_locale()` (liefert hier `de_DE`), nicht hartkodiert;
      die pure Funktion bekommt den Wert übergeben.
- [ ] `og:type` ist `website` auf allen Seiten. `article` würde
      Veröffentlichungs- und Änderungsdaten versprechen, die hier nichts
      bedeuten.

### 3. Pure Schicht: FAQ

- [ ] `inc/pure/faq.php` mit `stuv_seo_faq_pairs(array $blocks): array`. Eingabe
      ist die Ausgabe von `parse_blocks()` (verschachtelte Arrays, kein WP
      nötig), Ausgabe eine Liste aus `['question' => …, 'answer' => …]`.
- [ ] Rekursiv durch `innerBlocks` laufen, `core/details` einsammeln, die Frage
      aus `<summary>…</summary>` ziehen, die Antwort ist der Rest des
      `innerHTML`. Extraktion mit `preg_match` und `strip_tags` — **nicht** mit
      `wp_strip_all_tags` oder `WP_HTML_Tag_Processor`, sonst ist die Datei nicht
      mehr WordPress-frei.
- [ ] Details ohne `<summary>` oder ohne Antworttext werden übersprungen, nicht
      halb ausgegeben.
- [ ] **Erwartungsmanagement, gehört in den Datei-Kommentar:** Google zeigt
      FAQ-Rich-Results seit August 2023 nur noch für Behörden- und
      Gesundheitsseiten. Das Markup bleibt trotzdem sinnvoll — es ist gültige
      strukturierte Daten, die andere Konsumenten (Assistenten, Aggregatoren)
      lesen —, aber niemand soll später enttäuscht suchen, wo die Aufklappliste in
      den Suchergebnissen bleibt. Der Preis ist ohnehin null, weil abgeleitet.

### 4. Pure Schicht: Routen

- [ ] `inc/pure/routes.php` mit `stuv_seo_redirect_target(string $path, array $map): ?string`.
- [ ] Normalisierung im Test festgenagelt: Query-String weg, Groß-/Kleinschreibung
      egal, mit und ohne führenden/abschließenden Schrägstrich derselbe Treffer.
- [ ] Selbstschutz: Zeigt ein Eintrag auf sich selbst, gibt die Funktion `null`
      zurück statt einer Schleife.
- [ ] Unbekannter Pfad ⇒ `null` ⇒ der Aufrufer lässt den 404 stehen.

### 5. WordPress-Anbindung: Meta und Ausgabe

- [ ] `inc/meta.php`: drei `register_post_meta`-Aufrufe für `page`, jeweils mit
      `single`, `type`, `show_in_rest`, `sanitize_callback` und `auth_callback`.
- [ ] `inc/head.php`: auf `wp_head` (Priorität 2, damit die Tags oben stehen);
      Werte einsammeln (Post-Meta, sonst Option, sonst nichts), an
      `stuv_seo_meta_tags()` geben, Ergebnis mit `esc_attr()` ausgeben. `og:url`
      aus `wp_get_canonical_url()`. Bild-URL absolut über `wp_get_attachment_image_src()`
      — `og:image` verträgt keine wurzelrelative URL, und über `home_url()`
      gebaut zeigt sie nach dem DNS-Umzug automatisch auf Produktion.
- [ ] `inc/jsonld.php`: `@graph` bauen, ausgeben mit
      `wp_json_encode($graph, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP)`.
      `JSON_HEX_TAG` ist nicht Kosmetik: Die Werte kommen aus in wp-admin
      editierbaren Feldern, und ohne die Flags könnte ein `</script>` darin den
      Block verlassen.
- [ ] Drei Knoten, mehr nicht: - `Organization` (nur auf der Startseite, `@id` = `home_url('/#organization')`):
      Name, URL, `logo` als `ImageObject` auf `stuv-dhbw-logo-q.png` (1342×320),
      `email` `vorsitz@stuv-heidenheim.de`, `address` als `PostalAddress`
      (Marienstraße 20, 89518 Heidenheim an der Brenz, BW, DE),
      `parentOrganization` als `CollegeOrUniversity` „DHBW Heidenheim“,
      `sameAs` mit Instagram und WhatsApp-Community. - `FAQPage` auf `/kummer-karsten/`, gespeist aus Schritt 3. - `Event` **nicht jetzt** (siehe „Nicht in diesem Plan“).
- [ ] Erweiterungspunkt: `apply_filters('stuv_seo_jsonld_graph', $nodes)` vor der
      Ausgabe. Damit kann die spätere `/events/`-Arbeit `Event`-Knoten
      beisteuern, ohne dieses Plugin anzufassen.

### 6. Admin

- [ ] `inc/admin.php`: Metabox „SEO“ auf `page`, Kontext `normal`, mit Nonce und
      `save_post_page`-Handler, der `current_user_can('edit_page')` prüft und
      Autosaves überspringt. Drei Felder: Beschreibung (Textarea), Vorschaubild
      (Medienauswahl), „Von Suchmaschinen ausschließen“ (Checkbox mit dem
      Hinweistext, dass die Seite dadurch **auch** aus der Sitemap fällt).
- [ ] Einstellungsseite unter Einstellungen → StuV SEO (`manage_options`), Felder
      über die Settings API: Standard-Vorschaubild und
      Google-Search-Console-Token.
- [ ] Darunter eine **Startcheckliste**, eine Tabelle über alle Seiten:
      Titellänge (nur Anzeige, E3), Länge der Beschreibung mit Warnung über 160
      Zeichen, Vorschaubild gesetzt?, `noindex`?. Eine `WP_Query` über
      `post_type=page`; das ist der Ersatz für ein SEO-Dashboard und der einzige
      Ort, an dem ein neuer Vorstand sieht, was noch fehlt.
- [ ] `assets/admin.js`: Zeichenzähler unter der Textarea und `wp.media`-Auswahl
      für die beiden Bildfelder. Nur auf `post.php`, `post-new.php` (Post-Typ
      `page`) und der Einstellungsseite laden, mit `wp_enqueue_media()`. Kein
      Build, keine Abhängigkeit außer den Core-Handles.

### 7. Robots, Sitemap, Staging

- [ ] `inc/robots.php`, alles über `wp_robots` (die 5.7er API), nicht über
      handgeschriebene `<meta>`-Zeilen: - Seite mit `_stuv_seo_noindex` ⇒ `wp_robots_no_robots()` ⇒ `noindex,
follow`. Genau das verlangt §0.1 für `/docs/`. - Nicht-Produktionshost ⇒ ebenfalls `noindex`, zusätzlich
      `add_filter('wp_sitemaps_enabled', '__return_false')` und `Disallow: /`
      über `robots_txt`.
- [ ] `wp_sitemaps_posts_query_args`: für `$post_type === 'page'` die IDs mit
      gesetztem Flag als `post__not_in` ergänzen. **Das ist die Hälfte, die man
      vergisst** — `noindex` allein lässt beide Seiten in `wp-sitemap.xml` stehen,
      also ein widersprüchliches Signal, und wer den Haken setzt, denkt nicht an
      einen zweiten Handgriff.
- [ ] `wp_sitemaps_add_provider`: `users` und `taxonomies` abschalten. Die Site
      hat einen Autor und keine Archivseiten, die jemand finden soll.
- [ ] Verifikation:
      `bash
curl -sS -A "stuv-check/1.0" "https://$HOST/wp-sitemap.xml?cb=$(date +%s)"
curl -sS -A "stuv-check/1.0" "https://$HOST/docs/?cb=$(date +%s)" | grep -i "name=.robots"
`
      Erwartet: `/docs/` und `/linktree/` fehlen in der Sitemap, die anderen sechs
      stehen drin; `/docs/` liefert `noindex, follow`.

### 8. 301-Karte

- [ ] `inc/redirects.php`: die Karte als `array<string,string>` am Dateikopf,
      Hook auf `template_redirect` mit `if (!is_404()) return;`,
      `wp_safe_redirect($target, 302)` plus `exit`.
- [ ] Karte zunächst **leer** ausliefern. Die Slugs müssen vor dem Umzug aus der
      alten Site kommen (siehe Risiken) — erfunden werden sie nicht.
- [ ] Nach der Prüfung mit echten Slugs: 302 → 301 umstellen, in einem eigenen
      Commit.

### 9. Tests

- [ ] `wp-plugin/tests/test_seo_tags.php`, `test_seo_faq.php`,
      `test_seo_routes.php` — dieselbe `check()`-Harness wie
      `test_normalize.php`, `require` nur auf `inc/pure/*`.
- [ ] `test_seo_faq.php` bekommt eine handgeschriebene Block-Array-Fixture im
      Test selbst, keine Datei unter `fixtures/`: Die Fixtures dort sind
      Mitschnitte einer fremden API und müssen byte-genau bleiben; ein
      abgeschriebenes Block-Array ist etwas anderes und gehört zum Test.
- [ ] Kein `node --test`: `assets/admin.js` ist reiner DOM-Code gegen `wp.media`.
      Der wird von Hand geprüft, wie bei `stuv-theme` und `stuv-dsgvo` auch
      (`docs/testing.md`).
- [ ] Verifikation:
      `bash
php wp-plugin/tests/test_seo_tags.php
php wp-plugin/tests/test_seo_faq.php
php wp-plugin/tests/test_seo_routes.php
`

### 10. Bild für die Vorschau

- [ ] `data/media/og-default.jpg` anlegen: 1200×630, JPEG (nicht WebP — die
      Vorschaugeneratoren von WhatsApp und Instagram sind dort unzuverlässig),
      unter 300 KB, weil WhatsApp größere Bilder in der Vorschau überspringt.
      Motiv: Team-Hero oder Logo auf Markenfläche.
- [ ] Hochladen: `python3 $SKILL/scripts/deploy.py --manifest data/manifest.json media`
- [ ] In Einstellungen → StuV SEO als Standardbild setzen.
- [ ] **Nicht** `--force` benutzen; falls das Bild je ersetzt wird, gilt das
      Löschen-und-neu-hochladen-Rezept aus `AGENTS.md`.

### 11. Inhalte pflegen (in wp-admin, nicht im Repo)

- [ ] Für alle acht Seiten eine Beschreibung ≤ 155 Zeichen schreiben.
- [ ] `/docs/` und `/linktree/` auf `noindex` setzen.
- [ ] Wo ein eigenes Bild besser ist als das Standardbild (Events, Über uns),
      eines setzen.
- [ ] Search-Console-Property anlegen, Token eintragen, verifizieren, Sitemap
      einreichen.

### 12. Abnahme

- [ ] Kopfzeilen aller acht Seiten prüfen (Schleife aus Schritt 0, mit
      Cache-Buster). Erwartet: eine Description, ein Canonical (weiterhin nur
      Cores), OG-Satz vollständig, `twitter:card`, `og:locale` `de_DE`.
- [ ] JSON-LD durch den Rich-Results-Test und den Schema-Validator schicken:
      Startseite (`Organization`), `/kummer-karsten/` (`FAQPage`).
- [ ] **Echte WhatsApp-Nachricht** mit je einem Link auf Startseite und
      Kummer Karsten — der Validator ersetzt das nicht (§0.1 verlangt genau das).
      Dasselbe einmal in einer Instagram-DM.
- [ ] `X-Robots-Tag` auf `dev.` gegenprüfen: Der nginx-Gurt muss unabhängig vom
      Plugin greifen.
      `bash
curl -sSI -A "stuv-check/1.0" "https://$HOST/?cb=$(date +%s)" | grep -i x-robots
`
- [ ] **Deaktivierungsprobe** — die eigentliche Prüfung von Randbedingung 2:
      Plugin deaktivieren, alle acht Seiten aufrufen. Erwartet: identisches
      Layout, keine leere Fläche, keine Konsolenmeldung, nur fehlende Tags. Danach
      wieder aktivieren und stichprobenhaft prüfen, dass die Beschreibungen noch
      dastehen.
- [ ] `python3 $SKILL/scripts/verify_deploy.py --manifest data/manifest.json`
      muss weiterhin ohne Drift durchlaufen — das belegt E2: Post-Meta ist für
      den Abgleich unsichtbar.

### 13. Dokumentation und Todo

- [ ] `docs/plugins.md`: vierte Zeile in der Tabelle („Tags fehlen, sonst nichts“)
      und ein Abschnitt zum Plugin, inklusive der Staging-Inversion und des
      Grundes für E2.
- [ ] `docs/testing.md`: die drei neuen `php`-Aufrufe ergänzen.
- [ ] `AGENTS.md`: Abschnitt „The Plugins“ auf vier Plugins, „no argument builds
      both“ → „builds all four“ (§0.5), plus die E2-Regel in einem Satz:
      Beschreibungen leben in der Datenbank, `deploy.py` fasst sie nicht an.
- [ ] **Zwei-Schritt-Regel:** Doku-Änderung heißt Seite neu erzeugen und
      deployen:
      `bash
python3 tools/gen_docs_page.py --write
npx prettier --write .
python3 $SKILL/scripts/deploy.py --manifest data/manifest.json docs
`
- [ ] `docs/not-public/todo.md` aufräumen: §0.4-Zeile zum `seo`-Objekt im
      Manifest **streichen** mit Verweis auf diesen Plan (E2); erledigte Punkte
      aus §0.1 und §0.4 nach „Erledigt“ unter das heutige Datum; der
      `fetchpriority`-Punkt bleibt offen und wandert zum Hero-WebP-Todo (§0.1).

## Deploy-Reihenfolge

Anders als bei Karten oder DSGVO gibt es hier **keinen** gekoppelten
Mehrteiler — das Plugin berührt kein Block-HTML und kein CSS. Trotzdem eine
Reihenfolge, weil die Startcheckliste erst nach der Aktivierung existiert:

1. `data/media/og-default.jpg` committen → `deploy.py media`
2. `./wp-plugin/build.sh stuv-seo` → in wp-admin hochladen → aktivieren
3. Kopfzeilen sofort auf **einer** Seite prüfen (Schritt 12, erster Punkt), bevor
   irgendetwas gepflegt wird — falls doch ein zweites Canonical auftaucht, ist
   das der billigste Zeitpunkt für einen Rückzieher (Deaktivieren genügt, es gibt
   nichts zurückzurollen)
4. Felder in wp-admin füllen (Schritt 11)
5. Abnahme (Schritt 12)
6. Doku: `gen_docs_page.py --write` → `deploy.py docs`
7. Search Console: Sitemap einreichen, nach ein paar Tagen die Index-Abdeckung
   prüfen — `/docs/` und `/linktree/` dürfen nicht auftauchen

`rollback.py` spielt keine Rolle: Ein Plugin ist kein Deploy-Target. Der
Rückzieher ist „deaktivieren“, und weil nichts im Inhalt davon abhängt, ist er
folgenlos.

## Risiken und offene Abhängigkeiten

- **Die 301-Slug-Liste existiert nicht.** Der Auftrag verweist auf eine
  §0.4-Zeile mit „sieben alten Slugs“; in `docs/not-public/todo.md` steht sie
  nicht (§0.4 hat sechs Punkte, keiner davon Weiterleitungen), und auch keine
  frühere Fassung der Datei enthält sie. Die Slugs müssen deshalb **vor dem
  Umzug** aus der Elementor-Site geholt werden — Sitemap, Menüstruktur oder die
  Seitenliste in deren wp-admin. Nach dem Umzug sind sie nur noch über die
  Search Console rekonstruierbar. Bis dahin bleibt die Karte leer; der
  Mechanismus steht.
- **Der Instagram-Handle ist unklar.** `kontakt/02-wege.html:72` verlinkt
  `instagram.com/stuv_heidenheim`, `linktree/02-social.html:43` dagegen
  `www.instagram.com/stuvheidenheim/`. Einer führt ins Leere (Todo §4).
  `sameAs` ist eine maschinenlesbare Identitätsbehauptung — der Knoten wird erst
  ausgeliefert, wenn das geklärt ist. Bis dahin `Organization` ohne `sameAs`;
  das ist gültig.
- **Metaboxen im Block-Editor** werden nach dem REST-Speichern über ein
  verstecktes Formular nachgereicht. Etabliert und von Core unterstützt, aber
  wenn eine Beschreibung nach dem Speichern „verschwindet“, ist das die erste
  Spur — nicht der Sanitizer.
- **Der Staging-Riegel schützt nicht vor sich selbst.** Wird die Konstante beim
  Umzug nicht gepflegt oder heißt Produktion am Ende anders, bleibt die
  Produktionsseite auf `noindex` — die ungefährliche Richtung, aber jemand muss
  es merken. Deshalb steht die Index-Abdeckungsprüfung als letzter
  Deploy-Schritt.

## Nicht in diesem Plan

- **Titel-Override** (E3) und das Titelmuster; letzteres ist ein Feld unter
  Einstellungen → Allgemein.
- **`Event`-JSON-LD.** Es hängt an der §0.4-Aufgabe, `/events/` crawlbar zu
  machen: ICS serverseitig holen (Muster `stuv-mensa`), Liste rendern. Erst wenn
  es dort echte Termindaten gibt, gibt es etwas auszuzeichnen. Angeschlossen wird
  es über `stuv_seo_jsonld_graph` (Schritt 5) — diese Datei muss dafür nicht
  angefasst werden.
- **Favicon** (Customizer), **404-Seite** (Theme-Template),
  **WPForms-Zähler und Analytics** (§0.4, anderer Lebenszyklus — Messung
  hineinzumischen ist der Weg, auf dem ein Plugin unentfernbar wird),
  **`wp-image-<id>`-Nachtrag** und **Hero-WebP-Tausch** (quellseitige
  Inhaltsfixes).
- **CSS-Minify beim Deploy** (§0.1) — gehört ins Skill-Repo.
