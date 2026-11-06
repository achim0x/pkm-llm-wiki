# PKM mit LLM-Wiki – Implementierungsspezifikation

**Version:** 0.28 (Entwurf zum Review) · **Stand:** 05.11.2026

> **Änderungen in 0.28**
> - **`CLAUDE.md` aktualisieren:** `pkm setup` erkennt eine vom aktuellen Template abweichende `CLAUDE.md` im Vault und bietet an, sie zu ersetzen (Sicherung außerhalb des Vaults, Commit) oder die Vorlage als `CLAUDE.md.new` daneben zu legen (15.1).
> - **Wiki-Sprache:** `PKM_LANGUAGE` gilt auch für das Wiki. Der Pflege-Server nennt Sprache, Abschnittsnamen und das Label der ersten Zeile in seinen Anweisungen (Deutsch: Kurzfassung, Inhalt, Widersprüche / offene Fragen, Siehe auch, Belege); der Skill `pkm-wiki` schreibt neue Wiki-Seiten, Log-Einträge und Berichte in dieser Sprache, bestehende Seiten behalten ihre Sprache. Erzeugte Dateien bleiben englisch (4.2, 7.1, 9, 15.1).
> - **Englische Namen für den Pflege-Server:** `pkm-pflege` heißt jetzt `pkm-maintenance` (Programm `pkm-maintenance-mcp`, Modul `maintenance_server.py`), das Claude-Projekt „PKM Maintenance“. `pkm-pflege-mcp` bleibt als Alias, damit bestehende Einträge weiter laufen; `pkm setup` ersetzt den alten Eintrag in Claude Desktop nach Rückfrage (7.6, 7.7, 11, 15.1).

> **Änderungen in 0.27**
> - **Dokumentsprache wählbar:** `pkm setup` fragt, ob im Chat erzeugte Dokumente hauptsächlich englisch oder deutsch sein sollen (`PKM_LANGUAGE`, `en` oder `de`, Standard `en`, Option `--language`). Der Server `pkm` nennt die Sprache und die passenden Abschnittsnamen in seinen Anweisungen; der Skill `pkm-access` schreibt neue Dokumente in dieser Sprache, fortgeführte Dokumente behalten ihre Sprache. Werkzeuge, Pflege und Wiki sind davon unabhängig (4.1, 6.2, 7.1, 8, 10, 15.1).
> - **Vorhandene Konfiguration übernehmen:** `pkm setup` sucht zuerst Einstellungen in Umgebungsvariablen, in den `env`-Blöcken der Einträge `pkm` und `pkm-pflege` von Claude Desktop (Installationen vor `pkm setup`) und in `config.toml`, zeigt sie mit Herkunft und übernimmt sie nach Bestätigung (z. B. `PKM_GIT_DIR`, damit der Verlauf erhalten bleibt). Bei „nein“ beginnt es neu und sichert eine vorhandene `config.toml` (15.1).

> **Änderungen in 0.26**
> - **Git ist optional.** Ohne Git läuft das PKM ohne Versionsverwaltung: Dokumente bekommen weiter IDs und Versionsnummern, geschrieben wird ohne Commit, Änderungen von Hand erkennt der Pflegelauf über die Hashes in `state.json`. Verlauf, Diff, alte Versionen und Wiederherstellen gibt es dann nicht (`not_versioned`). Nachrüsten: Git installieren und `pkm setup` erneut ausführen (5.4, 7.1–7.3, 8, 12, 16).
> - **Obsidian ist optional** (Klarstellung): Der Vault ist reines Markdown und lässt sich mit jedem Editor bearbeiten. Obsidian bleibt das empfohlene Frontend; ohne Obsidian entfällt nur das automatische Umschreiben von Links beim Verschieben (5.1, 5.5, 13).
> - **Einfachere Installation umgesetzt** (15.1): Installer `install.sh`/`install.ps1`, Assistent `pkm setup`, Konfigurationsdatei `config.toml`, Obsidian-Einstellungen durch `pkm init`, Skill-ZIPs im Paket und an jeder Release. Abweichend vom Plan installiert der Installer Git nicht, sondern weist nur darauf hin, und lädt das Paket als ZIP-Archiv (funktioniert ohne Git) (7.1, 7.6, 8, 13, 15.1).

> **Änderungen in 0.25**
> - **Cloud-Speicher allgemein statt Nextcloud:** Der Vault kann in jedem Ordner liegen, den ein Cloud-Dienst als normalen lokalen Ordner synchronisiert (Nextcloud/ownCloud, OneDrive, Google Drive, Dropbox, iCloud Drive, Box, pCloud, Syncthing …). Alle Stellen, die bisher Nextcloud nannten, gelten für den Cloud-Ordner allgemein (2, 3, 5.3, 5.5, 7.1, 7.6, 8, 10, 12, 13, 16).
> - **Konfliktkopien aller bekannten Dienste** werden erkannt: am Dateinamen (z. B. „conflicted copy“, „[Conflict]“, „.sync-conflict-…“, „Konflikt-Kopie“) und als Kopie neben dem Original mit derselben Dokument-ID (OneDrive „-RECHNERNAME“, iCloud „ 2“, „ (1)“, „Kopie von …“). Ohne gleiche ID ist eine solche Datei ein eigenes Dokument (5.3, 5.5).
> - **Dateien „nur online“:** Der Vault muss vollständig lokal vorliegen. `pkm doctor` meldet Platzhalter-Dateien (`vault_online_only`) und erkennt Cloud-Ordner aller bekannten Dienste für Git-Verzeichnis und Suchindex (5.5, 8).
> - Einstellungen je Dienst in 5.5; `.gitignore` enthält Hilfsdateien der verbreiteten Dienste (12).
> - Geplant: einfachere Installation (15.1, Schritt 8; umgesetzt in 0.26).

> **Änderungen in 0.24**
> - **Prüfung von Data-URIs bei der Übernahme** (neuer Teil in 4.9): Jede Bild-Data-URI, die über ein Werkzeug, von Hand oder aus einer Wiki-Seite ins PKM kommt, wird auf Schreibweise, Kodierung, Bildnamen, Alternativtext, Größe und Sicherheit geprüft. Abweichungen werden mit Befundcodes und einem Korrekturvorschlag gemeldet. **Korrigiert wird nur nach Rückfrage**, nie automatisch und nie in unbeaufsichtigten Läufen. Anlass: SVG im Referenzstil mit nicht kodierten Zeichen (`[ref]: <data:image/svg+xml;utf8,<svg …>>`) zeigte Obsidian nicht an (4.9).
> - Schreibende Werkzeuge melden eine abweichende Data-URI im übergebenen Text mit dem neuen Status `nonconforming_image` und schreiben nichts. Nach Bestätigung korrigiert der Server mit `fix_images: true`. Abweichende Bilder, die schon im Dokument stehen, nennt die Rückgabe unter `image_warnings` (7.2).
> - Neues Werkzeug `fix_images` in `pkm-mcp` und `pkm-maintenance-mcp` für bestehende Dokumente: ohne `apply` nur Vorschlag mit Diff (Status `proposal`), mit `apply: true` neue Version, in der sich nur die Bildschreibweise ändert. Neuer CLI-Befehl `pkm fix-images`, nur auf Anweisung (3, 7.2, 7.7, 8).
> - `read` erkennt Data-URIs in jeder Schreibweise (auch Referenzstil, HTML, spitze Klammern) und ersetzt sie durch Platzhalter. `images` nennt je Bild `conforming` und `problems` (7.3).
> - `begin_maintenance` liefert Befunde je Dokument, der Pflege-Agent schlägt Korrekturen vor wie bei fehlenden Frontmatter-Feldern (9.1, 9.7). Belege auf Abschnitte, in denen sich nur die Bildschreibweise geändert hat, hebt `finish_maintenance` selbst an (4.9, 7.7). Lint meldet `nonconforming_image` (8).
> - Bestehende eingebettete PNG bleiben unverändert (Grundsatz 4). Bei ihnen wird nach Rückfrage nur eine Schreibweise korrigiert, die die Darstellung verhindert; die Bilddaten bleiben byte-gleich, ein Name wird nicht eingetragen (4.9).
>
> **Änderungen in 0.23**
> - **Importordner im Vault:** Standard für `PKM_IMPORT_DIR` ist der Ordner `pkm_img_import/` im Vault (statt `Downloads/pkm-import`). `pkm init` legt ihn an und trägt ihn in `.gitignore` ein. Wie `scratch/` ist er von Pflegelauf, Lint, Suche und Belegen ausgenommen und nicht in Git. Ein Ordner außerhalb des Vaults bleibt möglich, andere Ordner im Vault nicht (3, 4.9, 7.1, 7.2, 8, 10, 12, 13, 14, 16).
> - **JPEG wird übernommen:** `.jpg`/`.jpeg` aus dem Importordner werden wie PNG behandelt (eingebettet als `data:image/jpeg;base64` bzw. Datei `.jpg`). Metadaten (EXIF/XMP, IPTC, Kommentare) werden entfernt, die Ausrichtung bleibt erhalten (4.9, 7.2, 14).
>
> **Änderungen in 0.22**
> - **Windows als PKM-Rechner:** Der Rechner mit MCP-Servern, Git und Suchindex (PKM-Rechner) kann ein Mac **oder** ein Windows-PC sein, gleichwertig. Je Vault gibt es genau einen PKM-Rechner, alle anderen nutzen nur Obsidian. Standardordner unter Windows `%APPDATA%\pkm`, Git von git-scm.com, Konfiguration von Claude Desktop unter `%APPDATA%\Claude`, Datensicherung des Git-Verzeichnisses ausdrücklich einrichten (3, 5.5, 7.1, 7.6, 7.7, 11, 12, 13, 14, 16).
> - Tabellenzeilen `sha:` (4.2) sowie `pkm versions`, `pkm status`, `pkm lint` und `pkm doctor` (8) wieder vollständig, die Ergänzungen aus 0.21 sind angehängt.
> - Präzisierungen aus der Umsetzung der Bilder: `edit_document` hat `confirm_shortening` (Entfernen von Bildern), verwaist sind auch Bilddateien in `_attachments/` ohne Verweis, bei mehreren Dokumenten je Bilddatei enthält der Commit des ersten Dokuments das Bild (4.9, 7.2, 8).
>
> **Änderungen in 0.21**
> - **Bilder** (neuer Abschnitt 4.9): PNG und SVG, SVG bevorzugt. Bis 24 KB werden Bilder eingebettet (PNG als Base64-, SVG als URL-kodierte Data-URI), größere als Datei in `_attachments/` abgelegt, in `scratch/` immer eingebettet. Bestehende eingebettete PNG bleiben unverändert. Bilder gehören zu dem Dokument, das sie zeigt, und werden mit ihm versioniert und verarbeitet. Neue Werkzeuge `add_image` und `read_image`, neuer Parameter `images` für die schreibenden Werkzeuge, Importordner `PKM_IMPORT_DIR` für Bilder aus dem Chat (3, 4.2, 4.6, 4.7, 4.9, 7, 8, 9.1, 10, 13, 14).
>
> **Änderungen in 0.20**
> - **Lange Dateinamen:** Überschreitet ein erzeugter Dateiname die Grenze von 120 Zeichen (5.5), wird nur der Slug gekürzt, nie das Datum oder das Suffix bei Namensgleichheit (4.1, 7.2, 14).
>
> **Änderungen in 0.19** (Befunde aus den ersten Pflegeläufen)
> - **Dateinamen mit Datum am Ende:** Neue Dokumente aus Chats heißen `<slug>_YYYY-MM-DD.md`. Bei Namensgleichheit steht das Suffix vor dem Datum (`<slug>-2_YYYY-MM-DD.md`) (4.1, 7.2).
> - **Pflege über einen eigenen MCP-Server `pkm-maintenance-mcp` statt über Shell und CLI.** Claude Desktop bzw. Cowork führt Shell-Befehle nur in einer abgeschotteten Umgebung aus, in der `pkm`, Git und das Git-Verzeichnis fehlen. Der neue Server bündelt die Pflegebefehle in den Tools `begin_maintenance`, `write_wiki_page`, `set_document_metadata` und `finish_maintenance`. Er wird nur in Pflege-Unterhaltungen eingeschaltet. Die CLI bleibt für Einrichtung, Prüfung und Fehlersuche (1, 2, 3, 7.7, 8, 9, 11, 12, 15).
> - **Frontmatter-Vorschläge:** Fehlen bei neuen Dokumenten `title`, `context`, `tags` oder `kind`, schlägt der Pflege-Agent Werte vor. Nach ausdrücklicher Bestätigung trägt er `title`, `context`, `tags`, `kind` und `short_citation` ein (`set_document_metadata`), in unbeaufsichtigten Läufen nie (1, 3, 4.1, 7.7, 9.6).
> - **Feldreihenfolge:** Werkzeuge fügen fehlende Felder an der Stelle aus dem Schema ein statt am Ende. `update_frontmatter` schreibt in Schema-Reihenfolge. Einfache Listen stehen ohne Anführungszeichen (`tags: [a, b]`) (4.1, 7.2).
> - **`read` in Teilen:** neue Parameter `section`, `offset`/`max_chars` und `content`. Sehr große Inhalte kommen nur auf Anforderung (7.3).
> - **Lint ohne Fehlalarme:** Zwischenüberschriften, reine Hervorhebungs- und Link-Zeilen brauchen keinen Beleg, eine Tabelle gilt mit einer Fußnote direkt darunter als belegt. Belege auf Abschnitte ohne eigenen Text werden gemeldet (4.2, 4.8, 8).
> - **Belege beim Verschieben und bei neuen Versionen:** `fix-citations` schreibt auch Wikilinks im Seitentext um und findet verschobene Dokumente bei veraltetem Index. Belege auf unveränderte Abschnitte hebt der Abschluss des Pflegelaufs selbst auf die neue Version (5.2, 6.4, 8, 9.1).
> - **`CLAUDE.md`** ändert der Nutzer. `pkm versions` erfasst diese Änderungen als Commit mit `PKM-Source: user` (3, 8, 12).
>
> **Änderungen in 0.18**
> - **Neue Werte für `kind`:** `standard` für Normen und Standards, `regulation` für Gesetze und Verordnungen. Sie werden verarbeitet wie `note`. Lint gibt einen Hinweis bei umgewandelten Dokumenten ohne `kind` (4.1, 7, 8, 16).
>
> **Änderungen in 0.17**
> - **`date_markdown` und `date_updated` mit Uhrzeit:** Format `YYYY-MM-DDTHH:MM:SS` in Ortszeit ohne Zeitzonen-Angabe, Obsidian-Typ „Datum & Uhrzeit“. Das gilt auch für `date_updated` auf Wiki-Seiten, weil Obsidian Typen vault-weit pro Feldname festlegt. Ältere Werte nur mit Datum bleiben gültig (4.1, 13).
>
> **Änderungen in 0.16**
> - **Feldnamen ohne Leerzeichen:** `short citation` heißt jetzt `short_citation`. Die alte Schreibweise wird gelesen, Lint gibt einen Hinweis, `pkm fix-frontmatter` (bisher `quote-frontmatter`) benennt um, aber nur auf Anweisung (4.1, 8).
> - **`status_markdown` nur bei Normen und Standards, unverändert übernommen:** Server und CLI setzen es nicht mehr, Lint prüft es nicht, kein Werkzeug ändert es (auch `update_frontmatter` nicht). Die Sonderregeln in den Skills entfallen (4.1, 7.2, 9.5, 10).
>
> **Änderungen in 0.15**
> - **Frontmatter nach dem Schema der digitalisierten Normen:** `title`, `short citation`, `date_document`, `status_markdown`, `date_markdown`, `toolchain_markdown`. Ergänzt sind nur `id`, `version`, `date_updated`, `context`, `tags`, `related` und `kind`. Entfallen sind `created` (jetzt `date_markdown`), `updated` (jetzt `date_updated`), `source` (Herkunft jetzt in `toolchain_markdown`) und `topics` (jetzt `tags`) (4.1).
> - **Obsidian-Verträglichkeit:** Datumsfelder als `YYYY-MM-DD` ohne Zeitzone, Schlagwörter in `tags`, `source` bleibt frei für den Web Clipper, vault-weit einheitliche Property-Typen. Werte mit `: ` müssen in Anführungszeichen stehen. Neuer Befehl `pkm quote-frontmatter`, der nur auf Anweisung läuft (4.1, 8, 13).
> - `short citation` ist als Ziel in allen Werkzeugen verwendbar (7.1). `status_markdown` ändert sich nur auf ausdrückliche Anweisung (4.1, 9.5, 10).
>
> **Änderungen in 0.14**
> - **Neuer Bereich `scratch/`** für kurzlebige Notizen und Todo-Listen, neben `documents/` und `wiki/`. Er wird **nie ins Wiki übernommen**, steht **nicht in Git** (nur Nextcloud) und wird von Lint, Ingest und allen Pflegebefehlen ignoriert. Chats dürfen dort anlegen und ändern, ohne Version und ohne Commit (3, 7.1–7.4, 8, 9.5, 10, 12, 14, 16).
> - `create_document` hat den neuen Parameter `area` (`documents` | `scratch`). `search` kennt `scope: "scratch"`. Neuer Status `not_versioned` für `history` und `restore_document` in `scratch/`.
>
> **Änderungen in 0.13**
> - **Überschriften, deren Text auf `#` plus Ziffern endet** (z. B. „Version#2“), können mit dem Duplikat-Suffix kollidieren. Die Suffix-Vergabe überspringt jetzt belegte Schlüssel, und Lint meldet solche Überschriften: als Warnung bei Verwechslungsgefahr, als Fehler bei tatsächlicher Kollision (4.8, 8, 14, 16).
>
> **Änderungen in 0.12** (Entscheidungen aus dem Umsetzungsplan, Abschnitt 16)
> - **Suchindex nur in `PKM_CACHE_DIR`**, das außerhalb des Vaults und der Nextcloud liegen muss. Server und `pkm doctor` prüfen das. Das **Protokoll** `mcp.log` liegt in `.pkm/` (nicht in Git) (3, 5.5, 7.1, 7.4, 8, 12).
> - **`pkm ids` committet je Dokument einzeln** (`doc: <title> v1`, `PKM-Source: agent`). Der Sammel-Commit `pkm: add missing ids` entfällt (5.4, 8, 12).
> - **Neuer Befehl `pkm commit-wiki`** für den Agenten-Commit, der nur `wiki/` und `.pkm/state.json` erfasst (4.7, 8, 9.1, 12).
> - **Frontmatter:** Serverfelder werden zeilengenau ersetzt, der Rest bleibt unverändert. `update_frontmatter` schreibt das Frontmatter neu, Kommentare darin gehen dabei verloren (4.1, 7.2).
> - **`pkm versions` bei Verschiebungen:** ein Commit mit altem und neuem Pfad; neue Version nur bei geändertem Inhalt oder Metadaten (8).
> - **Kurznamen** werden ohne Groß- und Kleinschreibung aufgelöst (7.1).
> - **Plattform:** Alle Pfade sind per Umgebungsvariable überschreibbar, damit die Tests auch unter Linux laufen. Produktiv nur macOS (7.1).
> - `history`: `source` einheitlich `chat`, `user` oder `agent` (7.3).
>
> **Änderungen in 0.11**
> - **Hashes und Abschnitte exakt festgelegt** (neuer Abschnitt 4.8): Textnormalisierung, Erkennung von Frontmatter und Abschnitten (Ebene 1 und 2, außerhalb von Codeblöcken), Vorspann vor der ersten Überschrift als Abschnitt `_preamble`, doppelte Überschriften mit Schlüssel `Text#2`, `Text#3` sowie die genaue Eingabe von `hash`/`expected_hash`, `body_hash`, `meta_hash` und Abschnitts-Hashes.
> - `state.json` speichert `file_hash`, `body_hash` und `meta_hash` statt eines einzelnen `sha256`. `pending` erkennt zusätzlich umbenannte Abschnitte und reine Metadaten-Änderungen.
>
> **Änderungen in 0.10**
> - **Keine Startbefüllung.** Bestehende Skills oder andere Quellen werden nicht automatisch übernommen. Der Nutzer legt Wissen nach und nach selbst an, bei Bedarf per Chat (`create_document`) oder in Obsidian. Bestehende Skills bleiben unberührt und sind nicht Teil des Systems (15, 16).
>
> **Änderungen in 0.9**
> - **Schnittstelle durchgängig englisch:** Parameter, Rückgabefelder, Status- und Fehlerwerte, Frontmatter-Felder und -Werte, `state.json`, Commit-Zeilen, CLI-Befehle und Skill-Namen. Inhalte bleiben deutsch: Dokument- und Wiki-Texte, Überschriften, Änderungsnotizen und generierte Übersichten. Eine Übersicht der Namen steht im neuen Abschnitt 4.7.
>
> **Änderungen in 0.8**
> - Die Spezifikation ist **allgemein gehalten**: keine Personennamen, Pfade als Platzhalter (`<HOME>`, `<VAULT>`). Die Rolle heißt „Nutzer“, die Commit-Quelle `user`.
> - **MCP-Toolnamen englisch:** `create_document`, `rewrite_document`, `append_to_document`, `edit_document`, `update_frontmatter`, `restore_document`, `search`, `read`, `history`, `show_citations`, `read_index`, `list_unprocessed`. Parameter-, Feld- und CLI-Namen bleiben vorerst deutsch (16, noch offen).
> - Die Startbefüllung ist allgemein beschrieben (15).
>
> **Änderungen in 0.7** (Entscheidungen aus dem Review, Abschnitt 16)
> - **Ordnernamen englisch:** `documents/`, `documents/_inbox/`, `documents/_attachments/`, `wiki/topics/`, `entities/`, `summaries/`, `syntheses/`. Feld- und Toolnamen bleiben vorerst deutsch (siehe 16, noch offen).
> - **Vault in Nextcloud**, gelesen und bearbeitet auf Mac und Windows. MCP-Server, Pflege-Agent und Git laufen **nur auf dem Mac**. Das Git-Verzeichnis und der Suchindex liegen deshalb **außerhalb** des synchronisierten Ordners. Außerdem werden Dateinamen und Hashes plattformfest erzeugt (neuer Abschnitt 5.5).
> - **Immer erst ein Entwurf** vor jedem Schreibvorgang aus einem Chat, ohne Ausnahme.
> - **Pflege zunächst manuell**, die Automatik ist vorbereitet (Abschnitt 11).
> - **Git nur lokal**, kein Obsidian-Git-Plugin. Gesichert wird die Versionsgeschichte über Time Machine (Abschnitt 12).
> - **Startbefüllung** aus vorhandenem Wissen, z. B. bestehenden Skills (Abschnitt 15).
>
> **Änderungen in 0.6**
> - **Fortgeführte Diskussionen ändern das Dokument direkt.** Die Ergebnisse werden in die bestehenden Abschnitte eingearbeitet, das Dokument bleibt aufgeräumt. Datierte Fortsetzungsabschnitte gibt es nur noch auf ausdrückliche Anweisung (Abschnitt 6).
> - **Versionsnummer im Frontmatter** (`version`). Jede Änderung, ob per MCP oder von Hand, ergibt eine neue Version mit eigenem **Git-Commit**. Der Verlauf liegt in Git und nicht im Dokument (Abschnitte 5.4, 6, 12).
> - **MCP committet selbst** jede Änderung, einzeln und nur für die betroffene Datei. `.pkm/backup/` entfällt, Git ist jetzt Pflicht.
> - Neue Tools: `rewrite_document` (Inhalt komplett neu fassen, mit Schutz gegen versehentliches Kürzen), `history` (Versionen und Unterschiede) und `restore_document` (alte Version als neue Version zurückholen).
> - Belege nennen die **Version**, aus der sie stammen. `show_citations` kann den damaligen Wortlaut aus Git zeigen.
> - Der Pflege-Agent darf jetzt zwei Felder in Dokumenten setzen: `id` und `version`.
>
> Frühere Stände: 0.5 ein Ablagebereich, IDs · 0.4 Belege auf Originale · 0.3 Wiki aus Chats nur lesbar · 0.2 Ändern bestehender Dateien · 0.1 Erstentwurf

---

## 1. Ziel

Ein persönliches Wissensmanagement (PKM), das

- für Menschen lesbar bleibt: reines Markdown, Obsidian als Frontend, aber nicht als Voraussetzung,
- **einen Ablagebereich** hat, in dem Dokumente manuell oder per MCP landen und frei sortiert werden (üblicherweise in Obsidian),
- daraus von einem LLM-Agenten ein **kompiliertes Wiki** aufbauen lässt (Zusammenfassungen, Themen, Querverweise) mit **Belegen auf die Originaldokumente**,
- aus **beliebigen Claude-Desktop-Chats** erlaubt:
  1. Ergebnisse einer Diskussion als neues Dokument abzulegen,
  2. bestehende Dokumente zu aktualisieren, etwa wenn eine Diskussion fortgeführt wird, mit Versionsnummer und vollständigem Verlauf in Git,
  3. das kompilierte Wissen abzufragen und auf Nachfrage die Originale zu nennen,
- die Wiki-Pflege in einem **eigenen Claude-Desktop-Projekt** über einen eigenen, lokalen MCP-Server erledigt.

### Leitprinzipien

1. **Zwei Bereiche, zwei Besitzer:** `documents/` gehört dem Nutzer (Pflege per Hand oder per MCP auf seine Anweisung). `wiki/` gehört dem Pflege-Agenten.
2. **Schreibwege aus Chats sind technisch begrenzt:** Der MCP-Server legt neue Dateien nur in `documents/_inbox/` an. Er ändert nur bestehende Markdown-Dateien in `documents/`. Er löscht und verschiebt nichts. Jede Änderung ergibt eine neue Version und einen Git-Commit, ist also jederzeit umkehrbar. `wiki/` ist aus Chats nur lesbar. Ausnahme ist der Bereich `scratch/` für kurzlebige Notizen: Dort darf der Server anlegen und ändern, ohne Version und ohne Commit (3). Diese Grenzen stehen im Code.
3. **Dokumente bleiben aufgeräumt:** Ein Dokument zeigt immer den aktuellen Stand. Die Geschichte liegt in Git, erreichbar über die Versionsnummer.
4. **Der Pflege-Agent fasst Dokumente nicht an**, mit zwei Ausnahmen: Er trägt `id` nach und erhöht `version` bei Änderungen, die von Hand gemacht wurden. Außerdem darf er **nach ausdrücklicher Bestätigung** des Nutzers `title`, `context`, `tags`, `kind` und `short_citation` eintragen (9.6).
5. **Rückverfolgbarkeit:** Jede Aussage im Wiki verweist auf das Originaldokument (Abschnitt bzw. Seite, Zitat, ID, Version). Wiki-Seiten untereinander gelten nicht als Beleg.
6. **Identität statt Pfad:** Dokumente werden über ihre ID gefunden. Pfade dürfen sich jederzeit ändern.
7. **Alles ist Markdown plus Git.** Der Suchindex ist ein Wegwerf-Cache.
8. **Keine LLM-Aufrufe im Server:** Der MCP-Server ist deterministisch. Die Intelligenz liegt beim Agenten.
9. **Kurzlebiges bleibt draußen:** Notizen und Todo-Listen in `scratch/` werden nie ins Wiki übernommen und nie versioniert. Soll etwas daraus dauerhaft werden, wird es nach `documents/` verschoben.

---

## 2. Architektur im Überblick

```
┌──────────────────────────────┐        ┌───────────────────────────────┐
│  Beliebiger Claude-Chat      │        │  Claude-Projekt „PKM Maintenance“  │
│  (+ Skill pkm-access)        │        │  (Chat oder Cowork,           │
│                              │        │   + Skill pkm-wiki)           │
└──────────┬───────────────────┘        └───────────────┬───────────────┘
           │ MCP (stdio, lokal)                         │ MCP (stdio, lokal)
           ▼                                            ▼
┌──────────────────────────────┐        ┌───────────────────────────────┐
│  pkm-mcp (Python)            │        │  pkm-maintenance-mcp (gleiches     │
│  schreiben (nur documents/,  │        │   Paket)                      │
│   je Änderung 1 Git-Commit): │        │  begin_maintenance            │
│   create_document            │        │  write_wiki_page              │
│   rewrite_document           │        │  set_document_metadata        │
│   append_to_document         │        │  finish_maintenance           │
│   edit_document              │        │  + lesende Tools              │
│   update_frontmatter         │        └───────────────┬───────────────┘
│   restore_document           │                        │
│  lesen: search, read,        │        ┌───────────────┴───────────────┐
│   history, show_citations,   │        │  pkm CLI (Einrichtung,        │
│   read_index,                │        │   Prüfung, Fehlersuche)       │
│   list_unprocessed           │        └───────────────┬───────────────┘
└──────────┬───────────────────┘                        │
           ▼                                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Vault  <PKM_ROOT>  (Cloud-Ordner, optional in Obsidian geöffnet)    │
│  documents/  (inkl. _inbox/)     wiki/     CLAUDE.md     .pkm/       │
└──────────────────────────────────────────────────────────────────────┘
```

| Komponente | Art | Zweck |
|---|---|---|
| **Vault** | Ordner mit Git-Repo (Pflicht) | Einzige Datenquelle (Single Source of Truth), Versionsgeschichte |
| **pkm-mcp** | lokaler MCP-Server (Python, stdio) | Ablegen, Aktualisieren und Versionsverlauf von Dokumenten, Abfragen des Wikis, Belege aus jedem Chat |
| **pkm-maintenance-mcp** | lokaler MCP-Server (Python, stdio), gleiches Paket | Wiki-Pflege aus Claude Desktop bzw. Cowork: bündelt die deterministischen Pflegeschritte, schreibt Wiki-Seiten (7.7). Nur in Pflege-Unterhaltungen eingeschaltet |
| **pkm CLI** | Kommandozeile, gleiches Python-Paket | Einrichtung (`pkm init`), Prüfung (`doctor`, `lint`) und Fehlersuche. Dieselben Pflegebefehle einzeln |
| **Skill `pkm-wiki`** | Claude-Skill | Regeln und Abläufe der Wiki-Pflege |
| **Skill `pkm-access`** | Claude-Skill (schlank) | Wann und wie Chats die MCP-Tools nutzen |
| **Projekt „PKM Maintenance“** | Projekt in Claude Desktop (Chat oder Cowork) | Ort, an dem die Pflege läuft (Server `pkm-maintenance` eingeschaltet) |
| **Geplante Aufgabe** (optional) | z. B. täglich | Neue und geänderte Dokumente automatisch verarbeiten |

---

## 3. Ordnerstruktur und Besitzrechte

```
<PKM_ROOT>/
├── documents/                # Ablage des Nutzers, frei sortierbar
│   ├── _inbox/             # Standardziel für pkm-mcp und den Web Clipper
│   ├── _attachments/            # Bilddateien (über 24 KB, Web-Clips, von Obsidian eingefügt)
│   ├── haus/
│   │   ├── zisterne.md
│   │   └── datenblatt-tank.pdf
│   └── …                     # beliebige Unterordner
├── scratch/                  # kurzlebige Notizen, Todo-Listen: nicht in Git, nie ins Wiki
├── pkm_img_import/           # Übergabe von Bildern aus dem Chat (import_path): nicht in Git, nie ins Wiki
│   └── …                     # beliebige Unterordner
├── wiki/
│   ├── index.md              # Katalog: jede Seite mit Kurzfassung (generiert)
│   ├── _status.md            # unverarbeitete Dokumente, Einsortier-Hinweise (generiert)
│   ├── log.md                # Chronik aller Pflegevorgänge (nur anhängen)
│   ├── topics/               # Konzepte, Sachgebiete
│   ├── entities/           # Geräte, Software, Personen, Orte, Firmen
│   ├── summaries/    # eine Seite je verarbeitetem Dokument
│   ├── syntheses/            # Übersichten, Vergleiche, Entscheidungen
│   └── _lint/                # Lint-Berichte
├── CLAUDE.md                 # Schema: Konventionen und Regeln
├── .pkm/
│   ├── state.json            # Verarbeitungsstand (im Git)
│   └── mcp.log               # Protokoll aller MCP-Vorgänge (nicht im Git)
├── .obsidian/
└── .gitignore                # kein .git im Vault, siehe 5.5

Außerhalb des Cloud-Ordners, nur auf dem PKM-Rechner (5.5):
~/Library/Application Support/pkm/      (Mac)
%APPDATA%\pkm\                          (Windows)
├── git/                      # Git-Verzeichnis des Vaults (PKM_GIT_DIR)
└── index.db                  # Suchindex, Cache (PKM_CACHE_DIR)
```

| Bereich | Nutzer (Obsidian) | pkm-mcp (Chat, auf Anweisung des Nutzers) | Pflege-Agent |
|---|---|---|---|
| `documents/_inbox/` | alles | neu anlegen, ändern | lesen, `id`/`version` setzen; nach Bestätigung `title`, `context`, `tags`, `kind`, `short_citation` und Bildschreibweise (`fix_images`, 4.9) |
| `documents/**` (übrige) | alles | ändern (nur `.md`) | lesen, `id`/`version` setzen; nach Bestätigung `title`, `context`, `tags`, `kind`, `short_citation` und Bildschreibweise (`fix_images`, 4.9) |
| `wiki/` | lesen | **nur lesen** | lesen und schreiben |
| `CLAUDE.md` | lesen und schreiben (Änderungen committet `pkm versions`) | – | Änderungen nur nach Zustimmung |
| `scratch/**` | alles | neu anlegen, ändern (nur `.md`, Bilder immer eingebettet), ohne Version und Commit | **ignoriert** |
| `pkm_img_import/` | Bilder hineinlegen, aufräumen | nur lesen (`import_path`), kopiert ins Dokument | **ignoriert** |
| `.pkm/` | – | `mcp.log` (nur anhängen) | `state.json` (über `pkm-maintenance-mcp`) |

Ein Dokument ist „unverarbeitet“, solange seine aktuelle Version nicht in `state.json` als verarbeitet steht. Wo es innerhalb von `documents/` liegt, ist dafür egal.

**Bereich `scratch/`** (kurzlebige Notizen und Todo-Listen):
- **Nie im Wiki:** Ingest, `pending`, Belege, Index und Status beachten `scratch/` nicht. Auch Lint ignoriert den Bereich vollständig, prüft aber weiterhin im Wiki, dass kein Beleg auf `scratch/` zeigt.
- **Nicht in Git:** `scratch/` steht in `.gitignore` und wird nur über den Cloud-Speicher synchronisiert. Es gibt keine Versionsnummer, keinen Commit und keinen Verlauf. Als Rückfallebene für versehentliche Änderungen dienen die Dateiversionen des Cloud-Dienstes, sofern er welche anbietet.
- **Frontmatter optional:** Dateien in `scratch/` brauchen weder `id` noch `version`. `pkm ids` und `pkm versions` fassen sie nicht an.
- **Übernehmen ins Wiki:** Wird eine Notiz dauerhaft wichtig, verschiebt der Nutzer sie in Obsidian nach `documents/`. Beim nächsten Pflegelauf bekommt sie ID und `version: 1`, wird als neues Dokument committet und dann verarbeitet. Die umgekehrte Richtung (aus `documents/` nach `scratch/`) wirkt wie ein Löschen. Die Belege werden dann behandelt wie bei einem gelöschten Original (9.1).
- **Aufräumen** übernimmt der Nutzer in Obsidian. Löschen ist auch hier über den MCP-Server nicht möglich.

---

## 4. Dateiformate

### 4.1 Dokument

**Frontmatter** für Markdown-Dokumente. Die Feldnamen folgen dem Schema, das für die bereits digitalisierten Normen und Standards verwendet wird. Ergänzt sind nur die Felder, die das PKM zusätzlich braucht.

Dokument aus einem Chat:

```markdown
---
title: Zisterne – Überlaufsensor
date_markdown: 2026-10-31T23:40:12
toolchain_markdown: Claude Opus 5.5 (pkm-mcp)
id: d-20261031-2340-k7q2
version: 3
date_updated: 2026-11-02T19:05:00
context: "Chat: Füllstandsberechnung Tank 1"
tags: [zisterne, home-assistant]
related: ["[[documents/haus/zisterne]]"]
kind: note
---
```

Umgewandelte Norm nach `pkm fix-frontmatter` (Anführungszeichen um den Titel, weil er `: ` enthält) und dem ersten Pflegelauf (`id` und `version` hinzugekommen):

```markdown
---
title: "EN 61000-4-6 – Elektromagnetische Verträglichkeit (EMV) – Teil 4-6: Prüf- und Messverfahren – Störfestigkeit gegen leitungsgeführte Störgrößen, induziert durch hochfrequente Felder"
short_citation: EN 61000-4-6:2014
date_document: August 2014
status_markdown: draft
date_markdown: 2026-10-25T14:12:00
toolchain_markdown: Claude Opus 5.5, Docling V 2.96.1
id: d-20261101-0915-m3qa
version: 1
kind: standard
---
```

**Felder:**

| Feld | Obsidian-Typ | Pflicht | Gesetzt von | Inhalt |
|---|---|---|---|---|
| `title` | Text | empfohlen | Umwandlung bzw. Chat | Dokumenttitel. Bei umgewandelten Dokumenten (Normen, Datenblätter) **aus dem PDF** (Deckblatt oder Titelseite) **in der Sprache des Dokuments**: Bezeichnung, dann die Titelteile wie gedruckt, getrennt durch ` – ` (Halbgeviertstrich mit Leerzeichen). Bei Chat-Ergebnissen ein kurzer, sprechender Titel |
| `short_citation` | Text | nein | Umwandlung | Kurzbezeichnung mit Ausgabe oder Jahr wie gedruckt, z. B. `EN 61000-4-6:2014`, `RCC 319-14`, `TPS3808 Rev. M`. Kann als Ziel in allen Werkzeugen verwendet werden (Adressierung) |
| `date_document` | Text | nein | Umwandlung | Ausgabedatum **wie im PDF gedruckt**, in Sprache und Schreibweise des Dokuments, z. B. `August 2014`, `03/2025`. Bewusst Text, kein Datumsfeld |
| `status_markdown` | Text | nein | Umwandlung | **Nur bei Normen und Standards.** Status der Umwandlung, z. B. `draft`. Wird **unverändert übernommen**: Die Werkzeuge setzen, prüfen und interpretieren das Feld nicht und ändern es nie |
| `date_markdown` | Datum & Uhrzeit (`YYYY-MM-DDTHH:MM:SS`) | empfohlen | Umwandlung bzw. Server/CLI beim Anlegen | Datum und Uhrzeit, an dem die Markdown-Fassung entstanden ist (Umwandlung, Anlage per Chat). Spätere Änderungen und Review-Korrekturen ändern es **nicht** |
| `toolchain_markdown` | Text | empfohlen | Umwandlung bzw. Server/CLI beim Anlegen | Modell, das umgewandelt oder geschrieben hat, dazu die Werkzeuge. Bei Umwandlungen z. B. `Claude Opus 5.5, Docling V 2.96.1`, bei OCR zusätzlich die OCR-Engine (z. B. `Tesseract`). Bei Anlage per Chat z. B. `Claude Opus 5.5 (pkm-mcp)`, bei Web-Clips `Obsidian Web Clipper` |
| `id` | Text | **ja** | Server bzw. `pkm ids` | Feste Dokument-ID (5.3) |
| `version` | Zahl | ja | Server bzw. `pkm ids` | Versionsnummer, beginnt bei 1, steigt mit jeder Änderung um 1. Zu jeder Version gehört genau ein Git-Commit (5.4) |
| `date_updated` | Datum & Uhrzeit (`YYYY-MM-DDTHH:MM:SS`) | nein | Server bei jeder Version, `pkm versions` bei Änderungen von Hand | Datum und Uhrzeit der letzten Änderung |
| `context` | Text | nein | Chat bzw. Pflege-Agent nach Bestätigung | Anlass in einer Zeile, Form `"<Art>: <Inhalt>"` (Art: Chat, Podcast, Buch, Artikel, Recherche, Notiz), z. B. `"Chat: Füllstandsberechnung Tank 1"` |
| `tags` | Tags (Liste) | nein | Chat, Nutzer bzw. Pflege-Agent nach Bestätigung | Schlagwörter, Kleinbuchstaben mit Bindestrich, ohne Leerzeichen, Umlaute ausgeschrieben, vorhandene Tags wiederverwenden (4–8 je Dokument empfohlen). Werkzeuge vereinheitlichen beim Schreiben. Obsidian zeigt nur dieses Feld in Tag-Ansicht, Tag-Suche und Graph an |
| `related` | Liste (Links) | nein | Chat bzw. Nutzer | Verwandte Dokumente |
| `kind` | Text | nein | Umwandlung, Chat bzw. Pflege-Agent nach Bestätigung | Art des Dokuments: `note` (Standardwert, wenn das Feld fehlt), `standard` (Normen und Standards), `regulation` (Gesetze und Verordnungen) oder `correction` (Korrekturwunsch für das Wiki, 9.1) |

**Regeln:**

- **Reihenfolge:** Die Felder stehen in der Reihenfolge der Tabelle: die sechs Felder der Umwandlung (`title` bis `toolchain_markdown`), dann `id`, `version`, `date_updated`, `context`, `tags`, `related`, `kind`. Unbekannte Felder (z. B. `source`) folgen danach. Werkzeuge fügen ein fehlendes Feld **zeilengenau an seiner Stelle** ein: hinter dem letzten vorhandenen Feld, das in der Tabelle davor steht, sonst vor dem ersten nachfolgenden. Bestehende Zeilen bleiben, wo sie sind.
- **Bereits umgewandelte Dokumente** (z. B. Normen mit genau den sechs Feldern der Umwandlung) sind gültig, sofern ihr YAML gültig ist (siehe Anführungszeichen). Beim ersten Pflegelauf kommen nur `id` und `version: 1` hinzu, direkt hinter `toolchain_markdown`.
- **Feldnamen enthalten keine Leerzeichen.** Ältere umgewandelte Dokumente mit dem Feld `short_citation` (mit Leerzeichen) meldet Lint als Hinweis. `pkm fix-frontmatter` benennt es in `short_citation` um, aber nur auf ausdrückliche Anweisung (8). Bis dahin lesen die Werkzeuge beide Schreibweisen.
- **Datumsfelder mit Uhrzeit, ohne Zeitzone:** `date_markdown` und `date_updated` haben das Format `YYYY-MM-DDTHH:MM:SS` (Sekunden, keine Bruchteile) in Ortszeit (`PKM_TZ`, Standard `Europe/Berlin`). Das ist das Format, das Obsidian als „Datum & Uhrzeit“ erkennt (sortierbar, Auswahl im Kalender). Eine Zeitzonen-Angabe (`+01:00`, `Z`) wird nicht geschrieben, weil Obsidian sie in Datumsfeldern nicht unterstützt. Die Zeitzone ergibt sich aus der Konfiguration. Ältere Werte nur mit Datum (`YYYY-MM-DD`, z. B. aus früheren Umwandlungen) bleiben gültig und werden nicht ergänzt. `date_markdown` ändert sich ohnehin nie. Gilt auch für `date_updated` auf Wiki-Seiten (4.2), weil Obsidian den Typ vault-weit pro Feldname festlegt.
- **Vault-weite Typen:** Obsidian legt den Typ einer Property vault-weit pro Namen fest. Jedes Feld hat deshalb überall den Typ aus der Tabelle. `date_document` bleibt Text, weil es wie gedruckt übernommen wird.
- **Links in Properties** (`related`, `sources`) stehen immer in Anführungszeichen. Andere einfache Listen schreiben die Werkzeuge einzeilig ohne Anführungszeichen (`tags: [zisterne, home-assistant]`), sofern das eindeutig ist.
- **Nicht verwendet:** `source` bleibt frei für die Quell-URL, die der Obsidian Web Clipper schreibt (13). Die Werkzeuge werten es nicht aus, lassen es aber unverändert. Für die Herkunft dient `toolchain_markdown`.
- **Anführungszeichen bei `: `:** Enthält ein Wert die Zeichenfolge Doppelpunkt plus Leerzeichen (häufig in Normtiteln, z. B. „Teil 4-6: Prüf- und Messverfahren“) oder beginnt er mit einem YAML-Sonderzeichen (`- [ ] { } # & * ! | > ' " % @` bzw. `` ` ``), muss er in doppelten Anführungszeichen stehen. Sonst ist das YAML ungültig, und Obsidian sowie die Werkzeuge können das Frontmatter nicht lesen (`invalid_frontmatter`, 4.8). Werkzeuge setzen die Anführungszeichen beim Schreiben selbst. Bestehende Dateien meldet Lint als Fehler. `pkm fix-frontmatter` behebt das, aber **nur auf ausdrückliche Anweisung** des Nutzers (8).
- **Werte von `kind`:**

  | Wert | Verwendung | Wirkung auf die Pflege |
  |---|---|---|
  | `note` | Diskussionsergebnisse, Notizen, Web-Clips, sonstige Dokumente. Gilt, wenn `kind` fehlt | normal verarbeitet |
  | `standard` | Normen und Standards (z. B. EN-, IEC-, ISO-Normen, Werknormen) | normal verarbeitet |
  | `regulation` | Gesetze und Verordnungen (z. B. Gesetze, EU-Verordnungen, Richtlinien) | normal verarbeitet |
  | `correction` | Korrekturwunsch für das Wiki mit `related` auf die betroffene Seite | Vorrang vor älteren Quellen (9.1) |

  `standard` und `regulation` setzt die Umwandlung. Für bereits umgewandelte Dokumente ohne `kind` (erkennbar an `status_markdown`, `short_citation` oder `date_document`) gibt Lint einen Hinweis. Ergänzt wird `kind` vom Nutzer bzw. nach seiner Bestätigung vom Pflege-Agenten (9.6), nicht automatisch von den Werkzeugen, weil sie `standard` und `regulation` nicht sicher unterscheiden können. Andere Werte meldet Lint als Fehler.
- **Pflicht** für die Verarbeitung sind `id` und `version`. Bei Ablage per MCP setzt der Server `date_markdown`, `toolchain_markdown`, `id` und `version: 1`. Bei eigenen Dokumenten trägt der Agent `id` und `version` nach (5.3). Fehlen `title`, `context`, `tags` oder `kind`, schlägt er Werte vor und trägt sie erst nach Bestätigung ein (9.6). Fehlen `date_markdown` oder `toolchain_markdown`, meldet Lint einen Hinweis, ergänzt sie aber nicht. `status_markdown` wird nicht geprüft.
- **ID-Format:** `d-YYYYMMDD-HHMM-xxxx`. Das sind Zeitpunkt der Vergabe und vier Zufallszeichen aus `0-9a-z` ohne `0 1 l o`. Kollisionen prüft der Server gegen den Index.
- **Geschützte Felder:** `id`, `version`, `date_markdown` und `date_updated` werden ausschließlich von Server bzw. CLI gesetzt und sind über `update_frontmatter` nicht änderbar. `status_markdown` wird unverändert übernommen und ist über `update_frontmatter` ebenfalls nicht änderbar. Geändert wird es nur außerhalb der Werkzeuge, z. B. in Obsidian oder bei einer erneuten Umwandlung.
- **Frontmatter-Erhalt:** Server und CLI setzen Felder **zeilengenau**: Nur die betreffende Zeile wird ersetzt oder ergänzt, Reihenfolge, Formatierung und Kommentare der übrigen Zeilen bleiben erhalten. Nur `update_frontmatter` schreibt das Frontmatter vollständig neu, in der Reihenfolge der Tabelle (unbekannte Felder in ihrer bisherigen Reihenfolge danach, Umlaute bleiben lesbar). Kommentare im Frontmatter gehen dabei verloren.

**Gliederung von Chat-Ergebnissen** (Empfehlung des Skills, nicht erzwungen), in der **Dokumentsprache** (`PKM_LANGUAGE`, 7.1), die der Nutzer bei der Einrichtung wählt:

| Deutsch (`de`) | Englisch (`en`, Standard) |
|---|---|
| `## Ergebnis` | `## Result` |
| `## Entscheidungen` | `## Decisions` |
| `## Offene Punkte` | `## Open points` |
| `## Kontext / Begründung` | `## Context / rationale` |

Der Server `pkm` nennt die Dokumentsprache und diese Abschnittsnamen in seinen Anweisungen an den Chat. Neue Dokumente entstehen in dieser Sprache (Titel, Text, Abschnitte), auch wenn der Chat in einer anderen Sprache geführt wird. Nur wenn der Nutzer ausdrücklich eine andere Sprache verlangt, gilt diese. Fortgeführte Dokumente behalten ihre Sprache und ihre Abschnittsnamen. Die Beispiele in dieser Spezifikation verwenden die deutschen Namen. Werkzeuge und Pflege behandeln beide Varianten gleich. Für Wiki-Seiten gilt dieselbe Sprache (4.2).

Bei einer fortgeführten Diskussion werden diese Abschnitte **aktualisiert**, nicht ergänzt (Abschnitt 6). Das Dokument zeigt immer den aktuellen Stand.

**Dateinamen** in `_inbox/`: `<slug>_YYYY-MM-DD.md`, das Datum (Tag der Anlage) steht am Ende. Bei Namensgleichheit kommt ein Suffix vor das Datum: `<slug>-2_YYYY-MM-DD.md`. Ist der Name länger als 120 Zeichen (5.5), wird nur der Slug gekürzt, nie das Datum oder das Suffix. Beim Einsortieren darfst du sie frei umbenennen.

**Nicht-Markdown-Dateien** (PDF, Bilder) haben kein Frontmatter und keine Versionsnummer. Sie werden über ihren Inhalts-Hash identifiziert. Eine neue Fassung eines PDFs gilt als neues Dokument (Abschnitt 5).

### 4.2 Wiki-Seite mit Belegen

Neue Wiki-Seiten entstehen in der Sprache aus `PKM_LANGUAGE` (7.1), die der Server `pkm-maintenance` in seinen Anweisungen nennt; eine bestehende Seite behält bei Aktualisierungen ihre Sprache (keine gemischten Seiten). Zitate in Belegen bleiben wörtlich in der Sprache des Dokuments. Namen je Sprache:

| | Deutsch (`de`) | Englisch (`en`, Standard) |
|---|---|---|
| Erste Zeile | `> **Kurzfassung:** …` | `> **Summary:** …` |
| Abschnitte | `## Inhalt`, `## Widersprüche / offene Fragen`, `## Siehe auch`, `## Belege` | `## Content`, `## Contradictions / open questions`, `## See also`, `## Citations` |

Belegprüfung und Lint erkennen beide Varianten. Das Beispiel verwendet die deutschen Namen.

Dateiname: Kleinbuchstaben, Bindestriche, Umlaute ausgeschrieben (`regenwasser-ertrag.md`).

```markdown
---
type: topic            # topic | entity | summary | synthesis
title: Regenwasser-Ertrag
aliases: [Regenertrag, L/mm]
tags: [zisterne, wasser]
sources:              # aus den Belegen erzeugt (finish_maintenance bzw. pkm sync-citations), als Wikilinks
  - "[[documents/haus/zisterne]]"
  - "[[documents/haus/zisterne-ueberlaufsensor_2026-10-31]]"
  - "[[documents/haus/datenblatt-tank.pdf]]"
date_updated: 2026-11-02T21:10:00
confidence: high      # high | medium | low
---

> **Kurzfassung:** Ein bis drei Sätze. Diese Zeile landet in index.md und in den Suchtreffern.

## Inhalt
Die Dachfläche beträgt 92 m².[^b1] Der Überlauf wird per Schwimmerschalter erkannt.[^b2]
(Bis Version 2 war ein Ultraschallsensor vorgesehen.[^b3])
Der Tank fasst 6.500 L.[^b4]

## Widersprüche / offene Fragen
- Ältere Notiz nennt 85 m² Dachfläche.[^b5] Neuere Angabe (92 m²) wird verwendet.

## Siehe auch
- [[wiki/entities/tank-1]]

## Belege
[^b1]: [[documents/haus/zisterne#Dach]] · „Dachfläche laut Plan 92 m²“ · id:d-20261012-0915-x7mp · v:2 · sha:3f9a1c
[^b2]: [[documents/haus/zisterne-ueberlaufsensor_2026-10-31#Entscheidungen]] · „Schwimmerschalter statt Ultraschall“ · id:d-20261031-2340-k7q2 · v:3 · sha:8b21e0
[^b3]: [[documents/haus/zisterne-ueberlaufsensor_2026-10-31#Entscheidungen]] · „Ultraschallsensor am Deckel“ · id:d-20261031-2340-k7q2 · v:2 · sha:a1b2c3
[^b4]: [[documents/haus/datenblatt-tank.pdf#page=2]] · „Nutzvolumen 6500 l“ · sha:c07d44
[^b5]: [[documents/alt/haus-2023#Dach]] · „ca. 85 qm“ · id:d-20261101-0700-q4rt · v:1 · sha:51aa02
```

**Beleg-Format** (eine Zeile je Beleg):

```
[^b<n>]: [[<path>#<anchor>]] · „<quote>“ · id:<document-id> · v:<version> · sha:<6 chars>
```

| Teil | Pflicht | Bedeutung |
|---|---|---|
| `[[<path>…]]` | ja | Vollständiger Pfad im Vault. Bei Nicht-Markdown mit Endung. Nur Ziele in `documents/`. Obsidian hält diesen Link beim Verschieben selbst aktuell |
| `#<anchor>` | wenn möglich | Abschnittsschlüssel nach 4.8 ohne Duplikat-Suffix (`#Dach`) oder PDF-Seite (`#page=2`). Für den Vorspann (`_preamble`) entfällt der Anker |
| `§:<schlüssel>` | nur bei Duplikaten | Vollständiger Schlüssel mit Suffix (`§:Notizen#2`), wenn die Überschrift im Dokument mehrfach vorkommt. Steht direkt nach dem Link |
| `„<quote>“` | ja bei Text | Wörtliche Stelle aus dem Original in der genannten Version, höchstens 200 Zeichen |
| `id:` | bei Markdown | Feste Dokument-ID |
| `v:` | bei Markdown | Version des Dokuments, aus der die Aussage stammt. Über ID und Version ist der damalige Wortlaut in Git jederzeit abrufbar |
| `sha:` | ja | Die ersten 6 Zeichen des Abschnitts-Hashes (Markdown) bzw. des Datei-Hashes (PDF/Bild) in dieser Version, nach 4.8. Bei Bildern siehe 4.9 |

**Regeln:**
- Jede Sachaussage in „Inhalt“ und „Widersprüche“ endet mit mindestens einer Fußnote. Fasst ein Absatz mehrere Aussagen aus derselben Stelle zusammen, genügt eine Fußnote am Absatzende.
- **Keine Sachaussagen** und damit ohne Beleg erlaubt: Zwischenüberschriften (`###` …), Zeilen nur aus Hervorhebung (`**Die drei Rollen**`) und Zeilen nur aus Links, ggf. mit kurzer Beschriftung (`Details: [[wiki/…]]`).
- **Tabellen** gelten als ein Absatz. Belegt ist eine Tabelle durch Fußnoten in ihren Zellen oder durch eine Zeile direkt darunter, die nur aus Fußnoten besteht (`[^b3]` oder `Quelle: [^b3]`).
- Abschnitte ohne eigenen Text (z. B. eine H1 direkt vor dem ersten `##`) werden nicht belegt, sondern der Unterabschnitt mit dem Zitat (4.8).
- Fußnoten zeigen immer auf Dokumente in `documents/`, nie auf Wiki-Seiten.
- **Überholte Aussagen** behalten ihren Beleg auf die *alte* Version (`v:2` im Beispiel). Der Beleg bleibt gültig, weil Git den damaligen Wortlaut hält.
- Eigene Schlussfolgerungen des Agenten werden gekennzeichnet: „(abgeleitet aus [^b1] und [^b4])“.
- Seiten unter `wiki/summaries/` fassen genau ein Dokument in seiner aktuellen Version zusammen und belegen ihre Aussagen genauso.
- `sources` im Frontmatter wird nicht von Hand gepflegt, sondern beim Abschluss des Pflegelaufs (`finish_maintenance`, 7.7) bzw. von `pkm sync-citations` erzeugt.
- `confidence: low`, wenn Quellen sich widersprechen oder nur eine unsichere Quelle vorliegt.
- Überschriften („Inhalt“, „Belege“ …) und die Markierung „Kurzfassung“ sind Inhalt und bleiben deutsch. Die Werkzeuge hängen nicht davon ab: Belege werden am Fußnotenformat erkannt, die Kurzfassung als erstes Zitat (`>`) nach dem Frontmatter.

### 4.3 `wiki/index.md`

Wird beim Abschluss des Pflegelaufs (`finish_maintenance`) bzw. von `pkm index` erzeugt. Gruppiert nach `type`, eine Zeile je Seite:

```markdown
## Themen
- [[wiki/topics/regenwasser-ertrag]] – Kurzfassung … _(3 Quellen, 2026-11-02)_
```

### 4.4 `wiki/_status.md`

Wird nach jedem Pflegelauf von `finish_maintenance` bzw. `pkm status` erzeugt, Rückfragen aus dem Lauf inklusive:

```markdown
## Noch nicht verarbeitet (2)
- [[documents/_inbox/bewaesserung-zeitplan_2026-11-02]] – neu (v1)
- [[documents/haus/zisterne-ueberlaufsensor_2026-10-31]] – v2 → v3, geändert: „Entscheidungen“, „Offene Punkte“

## Noch im Eingang, bereits verarbeitet (1)
- [[documents/_inbox/regenmesser_2026-10-30]] → Vorschlag: documents/haus/

## Probleme (0)
```

### 4.5 `wiki/log.md`

Nur anhängen. `finish_maintenance` setzt die Überschrift mit Zeitstempel, Vorgang und Kurzangabe; der Agent liefert die Liste:

```markdown
## [2026-11-02 21:10] ingest | 1 neu, 1 geändert
- neu: wiki/summaries/bewaesserung-zeitplan
- aktualisiert: wiki/topics/regenwasser-ertrag, wiki/entities/tank-1
- überholt: „Ultraschallsensor“ → „Schwimmerschalter“ (zisterne-ueberlaufsensor v2 → v3)
```

### 4.6 `.pkm/state.json`

Schlüssel ist die Dokument-ID (Markdown) bzw. `sha:<voller hash>` (PDF/Bild):

```json
{
  "version": 3,
  "documents": {
    "d-20261031-2340-k7q2": {
      "path": "documents/haus/zisterne-ueberlaufsensor_2026-10-31.md",
      "processed_version": 3,
      "file_hash": "…",
      "body_hash": "…",
      "meta_hash": "…",
      "sections": {
        "_preamble": "9f0c2e…",
        "Ergebnis": "a1b2c3…",
        "Entscheidungen": "8b21e0…",
        "Offene Punkte": "d4e5f6…"
      },
      "processed_at": "2026-11-02T21:10:00+01:00",
      "assets": {"documents/_attachments/foto-einstieg_2026-11-03.png": "5d1f…"},
      "wiki_pages": ["wiki/topics/regenwasser-ertrag", "wiki/entities/tank-1"]
    },
    "sha:c07d44…": {
      "path": "documents/haus/datenblatt-tank.pdf",
      "processed_at": "2026-10-31T23:58:00+01:00",
      "wiki_pages": ["wiki/entities/tank-1"]
    }
  }
}
```

Alle Hashes werden voll (64 Hex-Zeichen) gespeichert, im Beispiel gekürzt. Was sie abdecken und wie daraus Änderungen abgeleitet werden, regelt 4.8. Der Agent verarbeitet nur geänderte Abschnitte.

### 4.7 Namensübersicht (Schnittstelle englisch, Inhalt deutsch)

| Bereich | Namen |
|---|---|
| Dokument-Frontmatter | `title`, `short_citation`, `date_document`, `status_markdown`, `date_markdown`, `toolchain_markdown`, `id`, `version`, `date_updated`, `context`, `tags`, `related`, `kind` (`note` \| `standard` \| `regulation` \| `correction`). Details in 4.1 |
| Wiki-Frontmatter | `type` (`topic` \| `entity` \| `summary` \| `synthesis`), `title`, `aliases`, `tags`, `sources`, `date_updated`, `confidence` (`high` \| `medium` \| `low`) |
| Beleg-Zeile | `§:` (nur bei Duplikaten), `id:`, `v:`, `sha:` |
| Commit-Zeilen | `PKM-Id`, `PKM-Version`, `PKM-Source` (`chat` \| `user` \| `agent`), `PKM-Fix` (`images`) |
| `state.json` | `documents`, `path`, `processed_version`, `file_hash`, `body_hash`, `meta_hash`, `sections`, `processed_at`, `wiki_pages` |
| Abschnitte | Schlüssel nach 4.8, reserviert `_preamble`, Duplikate `Text#2` |
| `pending`-Kategorien | `new`, `changed`, `meta_changed`, `moved`, `deleted`; je Abschnitt `added`, `removed`, `changed`, `renamed` |
| Bereiche (`area`, `scope`) | `documents`, `scratch`; zusätzlich `wiki` und `all` (= `wiki` + `documents`) bei `search` |
| MCP-Tools `pkm-mcp` | `create_document`, `rewrite_document`, `append_to_document`, `edit_document`, `update_frontmatter`, `add_image`, `fix_images`, `restore_document`, `search`, `read`, `read_image`, `history`, `show_citations`, `read_index`, `list_unprocessed` |
| MCP-Tools `pkm-maintenance-mcp` | `begin_maintenance`, `write_wiki_page`, `set_document_metadata`, `fix_images`, `finish_maintenance` sowie die lesenden Tools von `pkm-mcp` |
| Pflege-Rückgaben | `missing_fields`, `image_issues`, `known_tags`, `operation` (`ingest` \| `lint` \| `fix`), `processed`, `removed`, `questions` |
| Statuswerte | `ok`, `moved`, `newer_version`, `missing`, `created`, `changed`, `unchanged`, `conflict`, `ambiguous`, `not_found`, `large_shortening`, `invalid_frontmatter`, `invalid_encoding`, `not_versioned`, `svg_too_complex`, `too_large_for_inline`, `unknown_image`, `invalid_image`, `nonconforming_image`, `proposal`, `forbidden`, `protected_field`, `field_exists`, `blocked`, `needs_decision` |
| CLI | `pkm init`, `ids`, `versions`, `pending`, `history`, `show`, `fix-citations`, `sync-citations`, `sha`, `mark`, `index`, `status`, `lint`, `restore`, `reindex`, `commit-wiki`, `fix-frontmatter`, `fix-images`, `doctor` |
| Bild-Befunde (4.9) | `reference_style`, `html_img`, `angle_brackets`, `not_own_line`, `unencoded_chars`, `svg_parameters`, `svg_base64`, `base64_whitespace`, `media_type_mismatch`, `missing_name`, `invalid_name`, `duplicate_name`, `missing_alt`, `svg_unsafe`, `too_large_for_inline`, `unsupported_type`, `invalid_data`, `unused_definition`; Felder `image_issues`, `image_warnings`, `conforming`, `problems`, `proposal`, `fixable` |
| Skills | `pkm-wiki`, `pkm-access` |

Deutsch bleiben: Texte in Dokumenten und Wiki-Seiten, Überschriften, Änderungsnotizen (`note`), `wiki/log.md`, `wiki/_status.md` und Lint-Berichte.

### 4.8 Normalisierung, Abschnitte und Hashes

Alle Hashes sind **SHA-256**, geschrieben als 64 Hex-Zeichen in Kleinbuchstaben. Gespeichert und zwischen Tools übergeben wird immer der volle Hash. Belege (`sha:`) und Anzeigen nutzen die ersten 6 Zeichen, verglichen wird dann per Präfix.

#### Schritt 1: Text normalisieren

Gilt für alle Markdown-Dateien, bevor irgendein Hash berechnet oder ein Text verglichen wird:
1. Bytes als UTF-8 dekodieren und ein BOM am Anfang entfernen. Ist die Datei kein gültiges UTF-8, kommt `invalid_encoding`. Die Datei wird dann nicht verarbeitet, und Lint meldet sie.
2. Zeilenenden vereinheitlichen: CRLF und einzelnes CR werden zu LF.
3. Unicode-Normalform NFC herstellen.
4. Am Dateiende steht genau ein LF. Fehlt es, wird es ergänzt, mehrere werden auf eins gekürzt.

Der Server **schreibt** Dateien immer in dieser Form: UTF-8 ohne BOM, LF, NFC, ein abschließendes LF. Darüber hinaus wird nichts verändert. Leerzeichen innerhalb von Zeilen bleiben, wie sie sind.

#### Schritt 2: Datei zerlegen

- **Frontmatter:** liegt vor, wenn die erste Zeile genau `---` ist. Es endet an der nächsten Zeile, die genau `---` oder `...` lautet. Fehlt dieser Abschluss oder ist das YAML ungültig, kommt `invalid_frontmatter`: Lesende Tools liefern den Rohtext, schreibende verweigern, Lint meldet die Datei. Ausnahme: `pkm ids` legt bei Dateien *ohne* Frontmatter eines an (5.3), bei ungültigem Frontmatter tut es das nicht.
- **Body:** alles nach der Abschlusszeile des Frontmatters, bzw. die ganze Datei, wenn es keines gibt.
- **Abschnittsgrenzen:** ATX-Überschriften der **Ebene 1 oder 2** (`#` bzw. `##`, dann Leerzeichen oder Zeilenende, höchstens 3 Leerzeichen Einrückung), sofern sie **außerhalb eingezäunter Codeblöcke** stehen. Codeblöcke werden nach CommonMark-Regeln erkannt (Zaun aus ``` oder ~~~, schließender Zaun gleicher Art und mindestens gleicher Länge). Überschriften ab Ebene 3 gehören zum umgebenden Abschnitt. Setext-Überschriften (Textzeile mit `===` oder `---` darunter) sind keine Grenzen. Lint empfiehlt, sie durch ATX-Überschriften zu ersetzen.
- **Abschnitt:** eine Grenzüberschrift und alle folgenden Zeilen bis vor die nächste Grenze bzw. bis zum Dateiende.
- **Vorspann:** der Text zwischen Frontmatter und erster Grenze. Er ist ein eigener Abschnitt mit dem reservierten Schlüssel **`_preamble`**, sofern er nach der Abschnitts-Normalisierung (Schritt 4) nicht leer ist. In Belegen wird er ohne Anker verlinkt. In den Tools wird er mit `section: "_preamble"` angesprochen, `append_to_document` fügt dann am Ende des Vorspanns ein, also vor der ersten Überschrift.

#### Schritt 3: Abschnittsschlüssel

- Der **Schlüssel** ist der Überschriftentext. Dabei werden die führenden `#` mit dem folgenden Leerraum sowie eine schließende `#`-Folge (ATX-Abschluss) entfernt, Leerraum an den Enden gestrichen und innere Leerraumfolgen zu einem Leerzeichen zusammengefasst. Groß- und Kleinschreibung sowie Inline-Markdown bleiben erhalten. `## Offene  Punkte ##` ergibt also `Offene Punkte`.
- **Doppelte Überschriften** (gleicher Schlüssel, auch über Ebene 1 und 2 hinweg) werden in Dokumentreihenfolge nummeriert. Das erste Vorkommen behält den Text, weitere bekommen `#2`, `#3` …, also `Notizen`, `Notizen#2`, `Notizen#3`.
  - **Kollisionen mit wörtlichen Überschriften:** Endet ein Überschriftentext selbst auf `#` plus Ziffern (z. B. „Version#2“), ist dieser Text bereits ein belegter Schlüssel. Die Suffix-Vergabe überspringt deshalb jede Nummer, deren Schlüssel schon als wörtliche Überschrift im Dokument vorkommt. Beispiel: `## Version`, `## Version#2`, `## Version` ergibt die Schlüssel `Version`, `Version#2` (wörtlich) und `Version#3`. Damit bleibt jeder Schlüssel eindeutig und die Zuordnung deterministisch. Ändert sich allerdings die Menge der wörtlichen Überschriften, können sich Suffixe verschieben. `pending` erkennt das als `renamed` (gleicher Abschnitts-Hash).
  - In Tools gilt: `section: "Notizen"` meint immer das erste Vorkommen. Ein Schlüssel mit Suffix meint genau den Abschnitt, dem dieser Schlüssel nach den Regeln oben zugeordnet ist, im Normalfall also `Notizen#2` das zweite Vorkommen. Gibt es ein Duplikat und wird der Schlüssel ohne Suffix übergeben, liefern `append_to_document` und `rewrite_document` (bei der Kürzungsprüfung) den Hinweis `ambiguous` mit allen Kandidaten. Der Chat muss dann den Schlüssel mit Suffix verwenden.
  - In Belegen enthält der Link-Anker immer den Text **ohne** Suffix (`[[…#Notizen]]`), weil Obsidian `#Notizen#2` als Pfad zu einer Unterüberschrift „2“ deuten würde. Beim Klick springt Obsidian zum ersten Vorkommen. Den genauen Schlüssel trägt der Beleg in diesem Fall zusätzlich als Feld `§:Notizen#2`. Zusammen mit Zitat und Hash bleibt er eindeutig.
  - Lint warnt vor doppelten Überschriften der Ebenen 1 und 2 in Dokumenten sowie vor Überschriften mit Zeichen, die Obsidian-Anker brechen (`# ^ [ ] |`).
  - Lint meldet außerdem gesondert **Überschriften der Ebenen 1 und 2, deren Text auf `#` plus Ziffern endet** (Muster `#[0-9]+$` nach der Schlüssel-Normalisierung):
    - als **Warnung** (`heading_suffix_like`), wenn keine Kollision vorliegt, weil der Schlüssel mit einem Duplikat-Suffix verwechselt werden kann,
    - als **Fehler** (`heading_suffix_collision`), wenn im selben Dokument auch die Grundüberschrift vorkommt (z. B. `Version` und `Version#2`), weil dann nur die Überspring-Regel die Schlüssel auseinanderhält.

    Empfehlung in beiden Fällen: Überschrift umformulieren, z. B. „Version 2“ statt „Version#2“.
  - Die Werkzeuge erzeugen selbst keine Duplikate. Fortsetzungsabschnitte am selben Tag bekommen ` (2)` im *Text* (6.3).

#### Schritt 4: Hashes

| Hash | Eingabe | Zweck |
|---|---|---|
| **`hash`** (Rückgabe von `read` und Schreib-Tools, verlangt als `expected_hash`; in `state.json` als `file_hash`) | die **gesamte** normalisierte Datei einschließlich Frontmatter | Konfliktschutz. Jede Änderung, auch an `tags` oder an `date_updated`, ändert ihn |
| **Abschnitts-Hash** (`sections.<schlüssel>` in `state.json`, Präfix als `sha:` im Beleg) | der Abschnitt **ohne** seine Überschriftenzeile, normalisiert: jede Zeile rechts von Leerraum befreit, führende und abschließende Leerzeilen entfernt, Folgen von Leerzeilen zu einer einzigen zusammengefasst, Zeilen mit LF verbunden | Inhaltliche Änderungen je Abschnitt. Reine Leerraum-Änderungen lösen nichts aus. Ein leerer Abschnitt (etwa eine H1 direkt vor dem ersten `##`) hat den Hash des leeren Strings (`e3b0c4…`). `read` kennzeichnet ihn in `sections` mit `empty: true`, Lint warnt bei Belegen darauf (`citation_empty_section`) |
| **`body_hash`** | die Folge aller Abschnitte in Dokumentreihenfolge, je Abschnitt eine Zeile `<schlüssel>\t<abschnitts-hash>\n` | Schneller Test, ob sich am Inhalt überhaupt etwas geändert hat, Reihenfolge inklusive |
| **`meta_hash`** | kanonisches JSON (sortierte Schlüssel, UTF-8, ohne Leerraum) der Felder `title`, `short_citation`, `date_document`, `tags`, `related`, `kind`. Fehlende Felder fehlen auch im JSON. Werte gehen als Zeichenketten in ihrer Schreibweise im Frontmatter ein (ein Datum also als `2026-10-25`, nicht als Datumsobjekt), Listen als Listen solcher Zeichenketten | Inhaltlich relevante Metadaten. `id`, `version`, `status_markdown`, `date_markdown`, `date_updated`, `toolchain_markdown` und `context` sind bewusst ausgenommen. Eine Statusänderung von `draft` löst also keine Neuverarbeitung aus |
| **Datei-Hash binär** | die Rohbytes ohne Normalisierung | PDFs und Bilder |

#### Was daraus folgt

`pkm pending` vergleicht je Dokument mit `state.json`:
- `body_hash` und `meta_hash` unverändert: **nichts zu tun**, auch wenn sich `file_hash` geändert hat, etwa nur durch `date_updated`, `version` oder `status_markdown`.
- Nur `meta_hash` geändert: **`meta_changed`**. Dann werden nur Zusammenfassungsseite und Index angepasst.
- `body_hash` geändert: **`changed`**, mit dem Abschnittsvergleich:
  - Schlüssel neu: `added`. Schlüssel weg: `removed`. Gleicher Schlüssel, anderer Hash: `changed`.
  - Ein `removed` und ein `added` mit **gleichem Hash** werden zu **`renamed`** (alter → neuer Schlüssel) zusammengefasst. Der Pflegelauf (`fix-citations`) passt die Anker in den Belegen an. So werden auch Verschiebungen in der Duplikat-Nummerierung erkannt (`Notizen#2` → `Notizen`).
  - Nur die Reihenfolge geändert, alle Abschnitts-Hashes gleich: `changed` ohne betroffene Abschnitte. Es wird nur der Stand vermerkt, eine inhaltliche Verarbeitung findet nicht statt.

`edit_document` sucht `old` im **normalisierten Body** (Schritt 1). Auch `old` und `new` werden vorher normalisiert (LF, NFC), damit CRLF oder abweichende Unicode-Formen aus dem Chat nicht zu `not_found` führen. Die Kürzungsprüfung von `rewrite_document` (`large_shortening`) zählt Zeichen des normalisierten Bodys und vergleicht Abschnittsschlüssel nach Schritt 3.

### 4.9 Bilder

**Formate:** PNG, SVG und JPEG. JPEG übernehmen die Werkzeuge nur aus dem Importordner (`import_path`, Fotos) und behandeln es wie PNG. Andere Rasterformate (GIF, WebP) bleiben als Datei gültig, werden aber von den Werkzeugen nicht erzeugt oder eingebettet.

#### Grundsätze
1. **Ein Bild gehört zu dem Dokument, das es zeigt.** Ein eingebettetes oder verlinktes Bild ist Teil seines Dokuments und wird mit ihm versioniert und verarbeitet. Als eigenständiges Dokument gilt ein Bild nur, wenn kein Markdown-Dokument in `documents/` darauf verweist.
2. **SVG vor PNG**, sofern das Bild es zulässt: Diagramme, Ablauf- und Schaltpläne, Skizzen, Diagramme aus Messwerten, Symbole und alle vom Modell selbst erzeugten Grafiken werden SVG. Fotos, Screenshots, Scans und Bilder mit Farbverläufen oder vielen Details bleiben PNG bzw. JPEG (Fotos aus der Kamera). Fotos werden nie vektorisiert. Ein SVG ist **zu komplex** (`svg_too_complex`), wenn es nach der Bereinigung größer als `PKM_SVG_MAX_KB` (Standard 200 KB) ist oder eingebettete Rastergrafiken enthält. Dann ist PNG das passende Format.
3. **Klein wird eingebettet, groß wird Datei:** Kodierte Größe ≤ `PKM_INLINE_MAX_KB` (Standard **24 KB**) → eingebettet als Data-URI. Darüber oder mit `mode: file` → Datei `documents/_attachments/<bild-slug>_YYYY-MM-DD.png` bzw. `.svg` oder `.jpg`. Obergrenze je Bild `PKM_IMAGE_MAX_MB` (Standard 5 MB).
- **`scratch/`:** Bilder in Notizen werden **immer eingebettet**, unabhängig von der Größe (bis zur Obergrenze von `PKM_IMAGE_MAX_MB`). Dateien legt der Server dort nicht an, weil `scratch/` nicht versioniert ist.
4. **Bestehende eingebettete PNG bleiben unverändert.** Ein PNG, das schon als Base64-Data-URI in einem Dokument steht, wird von keinem Werkzeug angefasst: nicht ausgelagert, nicht neu kodiert, nicht bereinigt, auch wenn es die Grenze überschreitet. Fehlt ihm ein Bildname (`pkm:<name>`), wird keiner eingetragen. Die Werkzeuge leiten dann einen Namen ab, ohne ihn in die Datei zu schreiben (**abgeleiteter Name:** Alternativtext klein, Umlaute ausgeschrieben, alles außer Buchstaben und Ziffern zu Bindestrichen, höchstens 40 Zeichen; ohne Alternativtext `bild-<n>` nach Reihenfolge im Dokument; bei Gleichheit `-2`, `-3`). Dieselbe Regel gilt für jedes Bild ohne gültigen Bildnamen.
5. **Base64 kommt nicht in den Kontext des Modells.** `read` ersetzt eingebettete Bilder durch Platzhalter. Angesehen wird ein Bild über `read_image`.
6. **Jedes neue Bild hat einen Alternativtext.** Er dient als Beschreibung in Suche, Index und Belegen und als Ersatz, wo das Bild nicht dargestellt wird.

#### Schreibweise
Eingebettet und verlinkt wird mit der **Markdown-Bildsyntax**, weil Obsidians `![[…]]` keine Data-URIs kennt. Der Titel trägt den festen Bildnamen `pkm:<name>` (Kleinbuchstaben, Ziffern, Bindestriche, eindeutig im Dokument). Jedes Bild steht in einer eigenen Zeile.

```markdown
![Schaltplan Überlaufsensor](data:image/svg+xml,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20…%3C%2Fsvg%3E "pkm:schaltplan-ueberlauf")
![Display der Pumpensteuerung](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA… "pkm:display-pumpe")
![Foto Einstieg](../_attachments/foto-einstieg_2026-11-03.png "pkm:foto-einstieg")
```

- **PNG eingebettet:** `data:image/png;base64,<Base64 ohne Zeilenumbrüche>`.
- **SVG eingebettet:** `data:image/svg+xml,<URL-kodiertes SVG>`. Vor dem Kodieren wird das SVG bereinigt (Sicherheit, unten) und verkleinert (Kommentare und Metadaten entfernt, Leerraum zusammengefasst), doppelte Anführungszeichen in Attributen werden zu einfachen. Prozent-kodiert werden `%`, `#`, `<`, `>`, `"`, Leerzeichen, Zeilenumbrüche, `(`, `)`, `[`, `]`, `{`, `}`, `|`, `\`, `^` und `` ` ``.
- **Größe in Obsidian** optional im Alternativtext: `![Schaltplan|400](…)`.
- Von Hand eingefügte Obsidian-Einbettungen (`![[Pasted image ….png]]`) bleiben gültig und zählen als verlinktes Bild.

#### Prüfung bei der Übernahme

Jede **Bild-Data-URI** (`data:image/…`), die ins PKM kommt, wird geprüft. Anlass: Ein SVG im Referenzstil mit nicht kodierten Zeichen ist gültiges CommonMark, wird von Obsidian aber nicht angezeigt.

**Wo geprüft wird:**

| Übernahme | Prüfung durch | Bei Abweichung |
|---|---|---|
| Text, den ein schreibendes Werkzeug von `pkm-mcp` erhält (`content`, `text`, `new`), also Data-URIs, die der Chat direkt in den Text schreibt statt über `images` | Server beim Aufruf | `nonconforming_image`, nichts wird geschrieben (7.2) |
| Bilder, die schon im Dokument stehen und von der Änderung nicht berührt werden | Server beim Aufruf | Schreiben erfolgt, Rückgabe nennt sie unter `image_warnings` |
| Dokumente, die von Hand (Obsidian, Web Clipper, Kopie) nach `documents/` kommen oder dort geändert werden | `begin_maintenance` (`pending`) und `pkm lint` | Befunde mit Vorschlag im Bericht (9.7) |
| Wiki-Seiten des Pflege-Agenten | `write_wiki_page` | `nonconforming_image`; der Agent korrigiert seine Seite ohne Rückfrage (7.7) |

Data-URIs in Codeblöcken und Inline-Code sind Beispiele und werden nicht geprüft. `scratch/` wird von den Werkzeugen geprüft, aber nicht von Pflegelauf und Lint (3). Andere Data-URIs (z. B. `data:text/html` in Links) meldet Lint als `unsupported_type`; sie werden nie korrigiert und nie dargestellt.

**Befunde** (je Bild eine Liste `problems`):

| Code | Befund | Korrektur nach Rückfrage |
|---|---|---|
| `reference_style` | Bild im Referenzstil `![alt][ref]` mit Definition `[ref]: <data:…>` bzw. `[ref]: data:…` | Data-URI an die Stelle des Bildverweises, Definition entfernen. Wird dieselbe Definition mehrfach verwendet, kommt `ambiguous` mit den Fundstellen; der Nutzer wählt, welche Stelle das Bild behält (Bildnamen sind eindeutig) |
| `html_img` | `<img src="data:…">` | Markdown-Bildsyntax, Alternativtext aus `alt`, Breite aus `width` als `\|<breite>` im Alternativtext |
| `angle_brackets` | URI in spitzen Klammern `(<data:…>)` | Klammern entfernen, Inhalt nach 4.9 kodieren |
| `not_own_line` | Bild mitten im Text oder mehrere Bilder in einer Zeile | Bild in eine eigene Zeile, der umgebende Text bleibt unverändert |
| `unencoded_chars` | SVG mit nicht kodierten Zeichen aus der Liste unter „Schreibweise“ (z. B. Leerzeichen, `#`, `<`, `>`, `"`, `{`, `}`) | dekodieren und nach 4.9 neu kodieren |
| `svg_parameters` | Zusätze im Medientyp wie `;utf8` oder `;charset=utf-8` | entfernen |
| `svg_base64` | SVG als Base64 (`data:image/svg+xml;base64,`) | dekodieren, URL-kodiert neu schreiben |
| `base64_whitespace` | Zeilenumbrüche oder Leerzeichen im Base64 (PNG, JPEG) | entfernen; die dekodierten Bytes bleiben gleich |
| `media_type_mismatch` | angegebener Typ passt nicht zur Signatur (z. B. JPEG als `image/png`) | Typ nach der Signatur; die Bytes bleiben gleich |
| `missing_name` | kein Titel `pkm:<name>` | abgeleiteten Namen eintragen (Grundsatz 4) |
| `invalid_name`, `duplicate_name` | Name mit unzulässigen Zeichen bzw. doppelt im Dokument | gültiger, eindeutiger Name (Suffix `-2`, `-3`) |
| `missing_alt` | kein Alternativtext | Vorschlag aus Referenzname, Bildunterschrift, SVG-`<title>` oder umgebender Überschrift; der Nutzer bestätigt oder ändert ihn |
| `svg_unsafe` | SVG mit Inhalten, die die Bereinigung entfernt („Sicherheit“) | bereinigen; der Vorschlag nennt die entfernten Teile (`removed`) |
| `too_large_for_inline` | eingebettet über `PKM_INLINE_MAX_KB` | als Datei nach `documents/_attachments/` und verlinken (nicht in `scratch/`, dort bleibt es eingebettet) |
| `unsupported_type` | anderes Format (z. B. GIF, WebP) oder kein Bild | Bilder als Datei nach `documents/_attachments/`, Bytes unverändert, verlinken; andere Typen keine Korrektur |
| `invalid_data` | nicht dekodierbar oder kein gültiges Bild | keine Korrektur, nur Meldung |
| `unused_definition` | Referenzdefinition mit Data-URI, die nirgends verwendet wird | entfernen; das ist eine Kürzung und wird als solche bestätigt |

**Bestehende eingebettete PNG** (Grundsatz 4): Die Bilddaten werden nie neu kodiert, ausgelagert oder bereinigt, und es wird kein Name eingetragen. Gemeldet und nach Rückfrage korrigiert wird bei ihnen nur die Schreibweise (`reference_style`, `html_img`, `angle_brackets`, `base64_whitespace`, `media_type_mismatch`); die dekodierten Bytes bleiben gleich. `missing_name`, `missing_alt`, `not_own_line` und `too_large_for_inline` werden bei ihnen nicht gemeldet. Für JPEG gilt dasselbe.

**Vorschlag:** Jeder Befund kommt als Eintrag in `image_issues`: `ref` (Bildname bzw. abgeleiteter Name), `line`, `section`, `format`, `size`, `problems`, `fixable` und `proposal` (`name`, `alt`, `mode`, `removed`). Bei SVG wird das Bild im Vorschlag nach der Bereinigung gezeigt. Ist ein Befund nicht korrigierbar (`invalid_data`, andere Typen), ist `fixable: false`.

**Korrektur nur nach Rückfrage:**
1. Werkzeuge und Pflegelauf **melden und schlagen vor**, ändern aber nichts von sich aus.
2. Der Chat bzw. Agent zeigt Befunde und Vorschlag und fragt nach. Fehlt ein Alternativtext, wird er mit erfragt.
3. Erst nach ausdrücklicher Bestätigung korrigiert der Server: beim Schreiben mit `fix_images: true` (7.2), in bestehenden Dokumenten mit `fix_images` (`apply: true`), von Hand mit `pkm fix-images`. Geändert wird nur die Bildschreibweise, der übrige Text bleibt byte-genau erhalten.
4. Die Korrektur verwendet den **Namen, den `read` und die Belege schon kennen** (abgeleiteter Name), damit `[img:<name>]` gültig bleibt.
5. Ergebnis ist eine neue Version mit eigenem Commit (Notiz `Bilder nach 4.9 korrigiert`, Zeile `PKM-Fix: images`). In `scratch/` ohne Version und Commit.
6. **In unbeaufsichtigten Läufen wird nie korrigiert**; die Vorschläge gehen als Frage nach `wiki/_status.md`.

**Belege nach einer Korrektur:** Ein Abschnitt gilt als „nur in der Bildschreibweise geändert“, wenn er mit Platzhaltern `![<alt>](pkm-image:<name>)` (ohne Größe und Hash) gleich geblieben ist und die dekodierten Bilder gleich sind. SVG werden dafür nach der Bereinigung verglichen; hat die Bereinigung etwas entfernt (`svg_unsafe`), gilt das Bild als geändert. Belege auf solche Abschnitte hebt `finish_maintenance` selbst auf die neue Version (wie bei unveränderten Abschnitten, 6.4). `pending` meldet ein Dokument, das sich nur so geändert hat, als `changed` mit `image_notation_only: true`; der Agent muss es nicht neu verarbeiten.

#### Zugehörige und eigenständige Bilder
- **Eingebettete Bilder** sind Teil des Abschnitts, in dem sie stehen. Eine Änderung ändert den Abschnitts-Hash (4.8).
- **Verlinkte Bilddateien** führt `state.json` je Dokument unter `assets` (Pfad und Hash). Ändert sich eine Bilddatei, erzeugt `pkm versions` für jedes Dokument, das sie verwendet, eine neue Version (Commit mit Bild und Dokument, `PKM-Source: user`; bei mehreren Dokumenten enthält der Commit des ersten das Bild, die übrigen bekommen je einen eigenen Commit), und `pending` meldet das Dokument als `changed` mit den Abschnitten, die das Bild enthalten.
- **Zugehörige Bilddateien sind keine eigenständigen Dokumente:** kein `new`, keine eigene Zusammenfassung.
- **Verwaiste Bilder** (letzter Verweis entfernt, sowie Bilddateien in `documents/_attachments/` ohne Verweis) werden nicht automatisch eigenständig, sondern in `wiki/_status.md` unter „Verwaiste Anhänge“ gemeldet.
- **Eigenständige Bilder** (ohne Verweis, z. B. ein Foto allein in `_inbox/`) werden wie bisher über den Datei-Hash als eigenes Dokument verarbeitet.

#### Belege auf Bilder
| Bild | Beleg |
|---|---|
| eingebettet | Abschnitt des Dokuments, als Zitat der Bildverweis `[img:<name>]`, z. B. `[[documents/…/notiz#Aufbau]] · „[img:schaltplan-ueberlauf]“ · id:… · v:3 · sha:…` |
| zugehörige Datei | Abschnitt des einbettenden Dokuments mit `[img:<name>]`. Bei der Prüfung zählt zusätzlich der Bild-Hash aus `assets` |
| eigenständiges Bild | Link auf die Datei und Datei-Hash, wie bisher |

Lint prüft, dass `[img:<name>]` im Dokument der belegten Version existiert.

#### Bilder in Wiki-Seiten
- Wiki-Seiten dürfen Bilder aus Dokumenten zeigen, als Link auf die Bilddatei. Eingebettete Bilder werden nicht kopiert, sondern es wird auf das Dokument verwiesen. Jedes gezeigte Bild braucht eine Fußnote auf sein Dokument.
- Der Pflege-Agent darf eigene **SVG-Diagramme** eingebettet in Wiki-Seiten setzen. Sie gelten als Schlussfolgerung („abgeleitet aus [^b1], [^b3]“) und brauchen Belege für die dargestellten Werte.

#### Lesen und Suche
- `read` ersetzt eingebettete Bilder durch Platzhalter, z. B. `![Schaltplan Überlaufsensor](pkm-image:schaltplan-ueberlauf "svg, 3,2 KB, sha:ab12cd")`, und liefert die Liste `images` (Name, Alternativtext, Format, `inline`/`file`, Größe, Hash, Abschnitt, `conforming`, bei Abweichung `problems`). Das gilt für **jede** Schreibweise einer Data-URI: Im Referenzstil, in HTML oder in spitzen Klammern ersetzt `read` nur die URI selbst durch `pkm-image:<name>` und lässt die übrige Schreibweise stehen, damit Base64 und SVG-Inhalt nie in den Kontext kommen. Die 40.000-Zeichen-Grenze (7.3) zählt den Text mit Platzhaltern.
- Suche und Index nehmen nur den Alternativtext auf, nie Base64 oder SVG-Inhalt.
- `read_image` liefert ein Bild: PNG als Bild, SVG als Text (das Modell liest SVG direkt). Optional rastert der Server SVG (`PKM_SVG_RASTER`, zusätzliche Bibliothek).
- **Platzhalter beim Schreiben:** `rewrite_document` und `edit_document` arbeiten auf dem Text mit Platzhaltern. Der Server setzt jeden Platzhalter vor dem Speichern wieder durch das Original bzw. den Dateilink ein, byte-genau. Ein vorher vorhandenes Bild, das in der neuen Fassung fehlt, gilt als entfernt und wird wie eine Kürzung gemeldet (`large_shortening` mit Bildliste). Unbekannte Platzhalter ergeben `unknown_image`.

#### Sicherheit
- **SVG wird vor dem Speichern bereinigt:** entfernt bzw. abgelehnt werden `<script>`, Ereignis-Attribute (`on…`), `<foreignObject>`, externe Verweise (`href`/`xlink:href` auf `http(s):`, `file:` usw.), `<?xml-stylesheet?>`, DOCTYPE und Entities (Schutz vor XXE) sowie eingebettete Rastergrafiken. Erlaubt sind nur interne Verweise (`#id`).
- **Neue PNG** werden an der Signatur geprüft (höchstens 8.000 × 8.000 Pixel). Textblöcke in den Metadaten (`tEXt`, `iTXt`, `zTXt`) werden entfernt. Bestehende eingebettete PNG bleiben unangetastet (Grundsatz 4).
- **Neue JPEG** werden an der Struktur geprüft (höchstens 8.000 × 8.000 Pixel). Metadaten werden entfernt: EXIF und XMP (darin z. B. GPS-Position, Kamera, Aufnahmezeit), IPTC und Kommentare. Die EXIF-Ausrichtung bleibt als minimaler EXIF-Block erhalten, damit Fotos nicht gedreht erscheinen. Farbprofile (ICC) bleiben.
- Bild- und Dateinamen sind plattformfest.

---

## 5. Identität, Versionen und Git

### 5.1 Zuordnung beim Umsortieren

Drei Mechanismen greifen nacheinander. Jeder deckt die Fälle ab, die der vorherige nicht abdeckt. Ohne Obsidian entfällt Mechanismus 1; dann greifen 2 und 3, und `fix-citations` schreibt Belege, `sources` und Wikilinks in Wiki-Seiten auf den neuen Ort um. Links in den Dokumenten des Nutzers bleiben dann unverändert.

| # | Mechanismus | Deckt ab | Grenze |
|---|---|---|---|
| 1 | **Obsidian aktualisiert Links automatisch** beim Verschieben oder Umbenennen | Der Normalfall: Du sortierst in Obsidian. Belege und `sources` zeigen sofort auf den neuen Ort | Verschieben außerhalb von Obsidian |
| 2 | **Dokument-ID** im Frontmatter, in jedem Beleg mitgeführt | Markdown-Dateien, die außerhalb von Obsidian verschoben oder zwischen zwei Läufen verschoben *und* bearbeitet wurden | Nur Markdown |
| 3 | **Inhalts-Hash** in `state.json` | PDFs und Bilder, auch bei Umbenennung außerhalb von Obsidian | Eine neue Fassung eines PDFs gilt als neues Dokument |

### 5.2 Auflösung eines Belegs

(in `show_citations` und `fix-citations`)
1. Der Link-Pfad existiert und die ID stimmt (Markdown) bzw. der Hash stimmt (PDF/Bild): Das Dokument ist gefunden.
2. Sonst bei Markdown: Die ID im Index nachschlagen. Liefert der Index keinen vorhandenen Pfad (etwa weil er nach einem Verschieben außerhalb von Obsidian veraltet ist), wird der Vault durchsucht. Gefunden heißt **verschoben**.
3. Sonst bei PDF/Bild: Den Hash im Dateibestand nachschlagen. Gefunden heißt ebenfalls **verschoben**.
4. Sonst: **fehlt**.

Ist das Dokument gefunden, wird der Inhalt geprüft. Ist die Version im Beleg gleich der aktuellen Version, ist der Status `ok`. Ist sie älter und der Abschnitts-Hash unverändert, ist der Status ebenfalls `ok`. Ist sie älter und der Abschnitt geändert, ist der Status `newer_version` (Abschnitt 7.3).

### 5.3 Vergabe von ID und Version

- `create_document` setzt `id` und `version: 1` sofort.
- Für alle anderen Markdown-Dateien ohne ID schreibt `pkm ids` zu Beginn jedes Pflegelaufs `id` und `version: 1` ins Frontmatter. Fehlt ein Frontmatter, wird eines angelegt. Der übrige Inhalt bleibt byte-genau erhalten.
- **Doppelte IDs** entstehen z. B. durch Kopieren einer Datei. Lint meldet sie. Der Agent gibt nach Rückfrage der jüngeren Kopie eine neue ID und setzt deren Version auf 1.
- **Konfliktkopien des Cloud-Speichers** tragen ebenfalls die ID des Originals. Erkannt werden sie am Dateinamen (Muster der bekannten Dienste, 5.5) oder als Kopie neben dem Original mit abgeleitetem Namen und **derselben** ID. Sie werden **nicht** als neues Dokument behandelt. Der Agent verarbeitet sie nicht, sondern meldet sie, und der Nutzer führt die Fassungen in Obsidian zusammen (5.5).

### 5.4 Versionen und Commits

**Jede Version ist genau ein Git-Commit**, der nur die eine Datei enthält. Die Commit-Nachricht hat ein festes Format mit maschinenlesbaren Zeilen am Ende:

```
doc: Zisterne – Überlaufsensor v3

Sensor: Schwimmerschalter statt Ultraschall; Montageort geklärt

PKM-Id: d-20261031-2340-k7q2
PKM-Version: 3
PKM-Source: chat
```

`PKM-Source` ist `chat` (MCP), `user` (Änderung von Hand) oder `agent` (`pkm ids`, Duplikat-Auflösung, Metadaten nach Bestätigung über `set_document_metadata`, Bildschreibweise nach Bestätigung über `fix_images`). Korrekturen der Bildschreibweise tragen zusätzlich `PKM-Fix: images` (4.9). Über `git log --grep "PKM-Id: d-…"` findet man alle Versionen eines Dokuments, **unabhängig davon, wo es gerade liegt**.

**Wer erhöht die Version?**

| Änderung durch | Zeitpunkt | Ablauf |
|---|---|---|
| MCP (Chat) | sofort bei jeder Änderung | Der Server erhöht `version`, setzt `date_updated`, schreibt die Datei und committet mit `--only` genau diese Datei (mit `--git-dir`/`--work-tree`, 5.5). Andere offene Änderungen im Vault bleiben unberührt |
| Nutzer (Obsidian, Dateimanager) | nachgezogen | (a) Ändert danach der MCP-Server dieselbe Datei, committet er **vorher** den Stand des Nutzers als eigene Version (`PKM-Source: user`). (b) Spätestens zu Beginn des nächsten Pflegelaufs zieht `pkm versions` alle von Hand geänderten Dokumente nach, je Dokument eine Version |
| Agent | beim Pflegelauf | `pkm ids` (über `begin_maintenance`), Duplikat-Auflösung und nach Bestätigung `set_document_metadata`, je Dokument und Änderung ein Commit |

Mehrere Änderungen von Hand zwischen zwei Commits werden also zu **einer** Version zusammengefasst. Das ist gewollt, weil Obsidian Zwischenstände beim Tippen speichert.

**Voraussetzung:** Ein Git-Repo mit getrenntem Git-Verzeichnis (5.5) und gesetztem `user.name`/`user.email`. Ist die Versionsverwaltung eingeschaltet und fehlt Git, verweigert der Server alle schreibenden Tools mit einer klaren Fehlermeldung (`git_unavailable`). Die lesenden Tools funktionieren weiter.

**Ohne Versionsverwaltung (Git optional):** `pkm setup` prüft, ob Git installiert ist. Fehlt es, gibt der Assistent einen Hinweis aus und schaltet die Versionsverwaltung ab (`PKM_VERSIONING = false` in `config.toml`, 7.1). Das PKM läuft dann so:
- Schreibende Tools schreiben atomar wie sonst, aber ohne Commit (`commit: null`). `version` steigt bei jeder Änderung über die Tools weiter um 1, `id` und `version: 1` vergeben Server und `pkm ids` wie sonst.
- Änderungen von Hand bekommen keine eigene Version; `pkm versions` und `pkm commit-wiki` tun nichts. `pending` erkennt Änderungen wie immer über die Hashes in `state.json` (4.8).
- `history`, `read` mit `version`, `pkm show` und `restore_document` liefern `not_versioned` mit einem Hinweis, wie die Versionsverwaltung einzuschalten ist.
- Belege: Den Wortlaut einer älteren Version gibt es nicht. Nennt ein Beleg die aktuelle Version oder ist der belegte Abschnitt unverändert (`sha:`), prüft Lint gegen den aktuellen Text; sonst gilt der Status `newer_version` ohne Inhaltsprüfung. `cited_version_missing` entfällt.
- Die Schreibsperre liegt in `PKM_CACHE_DIR`. `pkm doctor` meldet die abgeschaltete Versionsverwaltung als Hinweis, nicht als Fehler.
- **Nachrüsten:** Git installieren und `pkm setup` erneut ausführen. Der Assistent schaltet die Versionsverwaltung ein, legt das Repo an und committet die Grunddateien (`pkm: init`). Die Dokumente committet `pkm versions` zu Beginn des nächsten Pflegelaufs (bzw. der Server vor der nächsten Änderung aus einem Chat) mit ihrer aktuellen Versionsnummer als Ausgangspunkt (`PKM-Source: user`, Notiz „first version by hand“); ein Verlauf für die Zeit davor entsteht nicht.

### 5.5 Cloud-Speicher, Mac und Windows

**PKM-Rechner:** Genau **ein** Rechner je Vault führt MCP-Server, Pflege-Agent, Git und Suchindex. Das kann ein Mac oder ein Windows-PC sein, beide Varianten sind gleichwertig. Alle anderen Rechner lesen und bearbeiten den Vault nur mit einem Editor, üblicherweise Obsidian (optional, 13).

| Rechner | Obsidian bzw. anderer Editor | MCP-Server, Pflege-Agent, Git |
|---|---|---|
| PKM-Rechner (Mac **oder** Windows) | lesen, bearbeiten | **ja** (einziger Ort) |
| weitere Rechner (Mac oder Windows) | lesen, bearbeiten | nein |

**Cloud-Speicher:** Der Vault liegt in einem Ordner, den ein Cloud-Dienst synchronisiert. Geeignet ist jeder Dienst, der einen **normalen lokalen Ordner** abgleicht, z. B. Nextcloud/ownCloud, OneDrive, Google Drive, Dropbox, iCloud Drive, Box, pCloud oder Syncthing. Die Werkzeuge sind dienstneutral; was sich je Dienst unterscheidet, steht unten unter „Einstellungen je Dienst“. Für alle Dienste gilt:
- **Vault vollständig lokal halten.** Der Pflegelauf liest jede Datei. Dateien, die nur als Platzhalter vorliegen („nur online“, „Dateien bei Bedarf“, „Streamen“), lösen Downloads aus oder fehlen ohne Verbindung. `pkm doctor` meldet sie (`vault_online_only`; macOS-Kennzeichen `SF_DATALESS`, unter Windows die Attribute für Offline- bzw. Abruf-Dateien).
- **Git-Verzeichnis und Suchindex nie im Cloud-Ordner** (siehe unten). `pkm doctor` erkennt Cloud-Ordner aller bekannten Dienste am Ordnernamen bzw. an ihren Markierungsdateien.
- **Ein PKM-Rechner je Vault**, unabhängig vom Dienst.

**Git-Verzeichnis außerhalb des Cloud-Ordners.** Ein `.git`-Ordner im synchronisierten Vault ist riskant. Cloud-Dienste übertragen die vielen kleinen Git-Dateien einzeln und nicht atomar. Halbe Stände, Sperrdateien oder Konfliktkopien können das Repo beschädigen. Deshalb arbeitet Git mit getrenntem Verzeichnis:

```
git --git-dir="$PKM_GIT_DIR" --work-tree="$PKM_ROOT" …
```

Im Vault gibt es kein `.git`, und die anderen Rechner sehen davon nichts. Aus demselben Grund liegt der Suchindex (SQLite) in `PKM_CACHE_DIR`. SQLite-Dateien eignen sich nicht für Dateisynchronisation. `PKM_CACHE_DIR` darf deshalb weder im Vault noch sonst in einem Cloud-Ordner liegen (7.1). Im Vault liegen nur zwei Dateien unter `.pkm/`: `state.json` ist klein, wird nur auf dem PKM-Rechner geschrieben und ist so in der Versionsgeschichte enthalten. `mcp.log` ist eine reine Textdatei, an die nur der PKM-Rechner anhängt. Sie wird mit synchronisiert, steht aber nicht in Git.

**Sync-Verzögerung und Konflikte**
- Änderungen von anderen Rechnern erreichen den PKM-Rechner erst nach dem Sync. Sobald sie angekommen sind, verhindert der Hash-Schutz, dass ein Chat einen veralteten Stand überschreibt.
- Schreibt ein Chat, *während* eine Änderung derselben Datei von einem anderen Rechner noch unterwegs ist, legt der Cloud-Dienst eine Konfliktkopie an. `pkm lint` und `pending` erkennen sie und melden sie (5.3), der Pflegelauf verarbeitet sie nicht. Der Nutzer führt die Fassungen in Obsidian zusammen und löscht die Kopie.
- **Erkennung am Namen** (ohne Rücksicht auf Groß- und Kleinschreibung): „conflicted copy“ (Nextcloud/ownCloud, Dropbox, Box, ältere Google-Drive-Clients), „(… conflict …)“, „[Conflict]“ bzw. „[Conflicted]“ (Google Drive, pCloud), „.sync-conflict-JJJJMMTT-HHMMSS“ (Syncthing), „case conflict“ (Dropbox), „Konflikt-Kopie“, „in Konflikt stehende Kopie“ und „(Konflikt …)“ (deutschsprachige Clients). Ein bloßes „Konflikt“ irgendwo im Namen genügt nicht, damit z. B. „Konfliktmanagement.md“ kein Fehlalarm ist.
- **Erkennung als Kopie neben dem Original:** Manche Dienste vergeben keinen eindeutigen Namen, sondern hängen etwas an (OneDrive „notiz-RECHNERNAME.md“, iCloud Drive „notiz 2.md“, Finder/Google Drive „notiz (1).md“, Google Drive „Kopie von notiz.md“). Eine solche Datei gilt nur dann als Konfliktkopie, wenn im selben Ordner das Original liegt **und beide dieselbe Dokument-ID tragen**. Sonst ist sie ein eigenes Dokument.
- Empfehlung: dasselbe Dokument nicht gleichzeitig auf einem anderen Rechner bearbeiten und per Chat ändern lassen.

**Plattformfeste Dateien**
- Vom Server erzeugte Dateinamen sind auf allen Systemen gültig: keine `\ / : * ? " < > |`, keine reservierten Windows-Namen (`CON`, `NUL`, `COM1` …), kein Punkt oder Leerzeichen am Ende, höchstens 120 Zeichen.
- Pfade werden intern in Unicode-NFC verglichen und gespeichert, weil macOS Dateinamen mit Umlauten teils als NFD liefert.
- Hashes werden über normalisierten Text berechnet (4.8: UTF-8 ohne BOM, LF, NFC). Eine Datei, die auf Windows mit CRLF gespeichert wird, gilt dadurch nicht als geändert.
- Zwei Dateien, die sich nur in Groß- und Kleinschreibung unterscheiden, meldet Lint als Fehler, weil sie unter macOS und Windows nicht unterscheidbar sind.

**Chats und MCP:** Die MCP-Server laufen nur auf dem PKM-Rechner und sind erreichbar, solange dort die Claude-Desktop-App läuft. Ein zweiter PKM-Rechner für denselben Vault ist bewusst nicht vorgesehen, sonst würden zwei Rechner eigene, abweichende Versionsgeschichten anlegen.

**Windows als PKM-Rechner:**
- Git wird nach <https://git-scm.com/install/> installiert (Option „Git from the command line and also from 3rd-party software“, dann steht Git im System-`PATH`). `pkm init` schaltet `core.autocrlf` für das PKM-Repo ab, damit Git Zeilenenden nie umwandelt.
- Schreibsperre über `msvcrt` statt `fcntl`. Atomares Ersetzen wiederholt `os.replace`, wenn eine Datei kurz gesperrt ist (Virenscanner, Sync-Client des Cloud-Dienstes, Indexdienst).
- Die Zeitzonendaten kommen aus dem Paket `tzdata`, weil Windows keine IANA-Datenbank mitbringt.
- Die automatischen Tests laufen auch unter Windows.

**Einstellungen je Dienst:** Ausnahmen von der Synchronisation sind nicht nötig, weil Git und Cache außerhalb liegen. Optional lassen sich `.obsidian/workspace*.json` ausschließen, da diese Dateien geräteabhängig sind. Wichtig ist, dass der Vault-Ordner dauerhaft lokal vorliegt:

| Dienst | Einstellung | Konfliktkopie (Beispiel) |
|---|---|---|
| Nextcloud / ownCloud | „Virtuelle Dateien“ für den Vault-Ordner aus. Dateiversionen dienen als Rückfallebene für `scratch/` | `notiz (conflicted copy 2026-11-04 120000).md` |
| OneDrive | „Dateien bei Bedarf“: Vault-Ordner auf „Immer auf diesem Gerät behalten“. Unter Windows wird „Dokumente“ oft automatisch nach OneDrive verschoben; das Git-Verzeichnis nie dorthin legen | `notiz-RECHNERNAME.md` (nur bei gleicher ID) |
| Google Drive | „Dateien spiegeln“ statt „Streamen“ bzw. Ordner offline verfügbar. Alte Dateiversionen nur begrenzt | `notiz [Conflict].md`, `notiz (1).md`, `Kopie von notiz.md` |
| Dropbox | Ordner nicht auf „Nur online“ | `notiz (Name's conflicted copy 2026-11-04).md` |
| iCloud Drive | „Mac-Speicher optimieren“ kann auslagern: Vault-Ordner „Heruntergeladen behalten“. Unter Windows nur eingeschränkt nutzbar | `notiz 2.md` (nur bei gleicher ID) |
| Syncthing | keine Platzhalter; synchronisiert nur, wenn beide Geräte gleichzeitig online sind | `notiz.sync-conflict-20261104-120000-ABCDEFG.md` |

Auf dem Mac verwalten OneDrive, Google Drive und iCloud Drive ihre Ordner über macOS (`~/Library/CloudStorage/…` bzw. `~/Library/Mobile Documents/…`). `PKM_ROOT` zeigt dann auf diesen Pfad.

---

## 6. Fortgeführte Diskussionen

**Grundsatz:** Eine fortgeführte Diskussion **aktualisiert das bestehende Dokument** dort, wo es inzwischen liegt. Neue Ergebnisse werden in die vorhandenen Abschnitte eingearbeitet, überholte Aussagen werden ersetzt. Das Dokument zeigt danach den aktuellen Stand ohne Verlaufsballast. Der Verlauf liegt in Git und ist über `version` und das Tool `history` erreichbar.

### 6.1 Dokument finden

| Situation | Vorgehen des Chats |
|---|---|
| Gleicher Chat, Dokument wurde darin abgelegt | Die ID aus der Rückgabe von `create_document` steht im Verlauf und wird direkt verwendet |
| Neuer Chat, der Nutzer nennt das Thema („führ das zum Überlaufsensor weiter“) | `search` im Bereich `documents` liefert Kandidaten mit Titel, Pfad, ID, Version und `date_updated`. Bei einem eindeutigen Treffer wird kurz bestätigt, bei mehreren wird nachgefragt |
| Unklar, ob Fortsetzung oder neues Thema | Nachfragen. Faustregel: Gleiche Fragestellung oder Entscheidung bedeutet aktualisieren. Neues Teilthema bedeutet neues Dokument mit `related` auf das alte |

Alle Tools akzeptieren statt eines Pfads auch `id:d-…`. Der aktuelle Ablageort ist also egal.

### 6.2 Aktualisieren (Standard)

1. `read(id:…)` liefert Inhalt, `version` und `hash`.
2. Der Chat erstellt die **neue Fassung** des Dokuments (Sprache und Abschnittsnamen des Dokuments bleiben, 4.1):
   - „Ergebnis“ neu formulieren, sodass es den Gesamtstand wiedergibt.
   - „Entscheidungen“: Geänderte Entscheidungen werden ersetzt, neue ergänzt. Ein Hinweis wie „überholt“ bleibt nicht stehen.
   - „Offene Punkte“: Erledigte Punkte werden entfernt, neue ergänzt.
   - „Kontext / Begründung“: Die Begründung für Änderungen wird ergänzt, soweit sie für das Verständnis des aktuellen Stands nötig ist.
3. Der Chat zeigt **die Änderungen als Vorher/Nachher** (pro Abschnitt) und eine **Änderungsnotiz** in einer Zeile, z. B. „Sensor: Schwimmerschalter statt Ultraschall“.
4. Nach Bestätigung ruft er das passende Tool auf:
   - **`rewrite_document`**, wenn mehrere Abschnitte betroffen sind (Normalfall bei Fortsetzungen),
   - **`edit_document`** bzw. **`append_to_document`** für kleine, gezielte Änderungen.
   
   Jede Änderung ergibt eine neue Version mit Commit. Mehrere kleine Änderungen derselben Fortsetzung sollen deshalb möglichst in **einem** Aufruf von `rewrite_document` gebündelt werden.
5. Rückgabe: neue Version und Diff. Der Chat nennt beides kurz.

**Hat der Nutzer die Datei inzwischen in Obsidian bearbeitet,** bricht das Tool mit `conflict` ab. Der Chat liest die Datei neu und baut die neue Fassung auf dem aktuellen Stand auf.

### 6.3 Fortsetzung als datierter Abschnitt (nur auf ausdrückliche Anweisung)

Nur wenn der Nutzer es ausdrücklich verlangt („als Fortsetzung dokumentieren“, „mit Verlauf im Dokument“, „neuen Abschnitt anhängen“):

1. Per `append_to_document` wird ein Abschnitt `## Fortsetzung YYYY-MM-DD` angehängt, mit Kontext und den Unterabschnitten Ergebnis, Entscheidungen und Offene Punkte. Bei mehreren am selben Tag kommt ein Zusatz wie `(2)` dazu.
2. Revidierte Entscheidungen im ursprünglichen Abschnitt werden per `edit_document` markiert: ` — *überholt am YYYY-MM-DD, siehe [[#Fortsetzung YYYY-MM-DD]]*`.
3. Die Versionierung läuft genauso wie in 6.2.

Diese Form ist nie Standard. Der Skill schlägt sie auch nicht von sich aus vor.

### 6.4 Was im Wiki passiert

1. `pending` (über `begin_maintenance`) meldet das Dokument mit `processed_version` → `version` und den geänderten Abschnitten.
2. Der Agent verarbeitet nur diese Abschnitte und vergleicht dazu die verarbeitete mit der aktuellen Version (`history` mit `diff_from`).
3. Betroffene Wiki-Aussagen werden auf den neuen Stand gebracht und mit Belegen auf die **neue Version** versehen.
4. Wo der frühere Stand für die Nachvollziehbarkeit wichtig ist, etwa bei einer geänderten Entscheidung, bleibt er als kurze Zeile „Bis Version n: …“ mit Beleg auf die **alte Version** stehen. Andernfalls wird er nur im Log vermerkt.
5. Belege auf unveränderte Abschnitte bleiben gültig. `finish_maintenance` hebt ihre Version am Ende des Laufs auf die aktuelle an (nur `v:`, `sha:` bleibt, weil der Abschnitt gleich ist). Das gilt auch für `meta_changed`.

---

## 7. MCP-Server `pkm-mcp`

### 7.1 Technik

- Python ≥ 3.11, offizielles `mcp`-SDK (FastMCP), Transport stdio
- Abhängigkeiten: `mcp`, `pyyaml`. Sonst Standardbibliothek (`sqlite3` mit FTS5, `subprocess` für `git`)
- Plattform: **macOS oder Windows**, je nach PKM-Rechner (5.5). `git` ist optional (5.4; macOS: Xcode Command Line Tools, Homebrew oder git-scm.com; Windows: git-scm.com). Die Standardpfade richten sich nach dem Betriebssystem; alle Pfade sind per Umgebungsvariable überschreibbar, damit die automatischen Tests auch unter Linux laufen
- Konfiguration über die Datei `config.toml` im Standardordner (macOS `~/Library/Application Support/pkm/`, Windows `%APPDATA%\pkm\`, andere Datei über `PKM_CONFIG`), geschrieben von `pkm setup`, mit flachen Schlüsseln wie die Umgebungsvariablen unten. Gesetzte Umgebungsvariablen haben Vorrang vor der Datei. Werte:
  - `PKM_ROOT` (Pflicht): absoluter Pfad zum Vault im Cloud-Ordner
  - `PKM_VERSIONING` (Standard `true`): Versionsverwaltung mit Git; `pkm setup` setzt `false`, wenn Git fehlt (5.4)
  - `PKM_LANGUAGE` (Standard `en`): Hauptsprache von im Chat erzeugten Dokumenten und vom Wiki, `en` (Englisch) oder `de` (Deutsch); auch die Namen `english`/`englisch`/`german`/`deutsch` werden angenommen, andere Werte sind ein Konfigurationsfehler. Die Server `pkm` und `pkm-maintenance` übernehmen sie beim Start in ihre Anweisungen (4.1, 4.2); eine Änderung wirkt nach einem Neustart von Claude Desktop
  - `PKM_GIT` (optional): Pfad des Git-Programms. Ohne Angabe wird Git im `PATH` und an den üblichen Orten gesucht (`/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`, `C:\Program Files\Git\cmd`); es zählt nur ein Git, das läuft (der Platzhalter `/usr/bin/git` auf macOS ohne Developer Tools zählt nicht)
  - `PKM_GIT_DIR` (Standard macOS `~/Library/Application Support/pkm/git`, Windows `%APPDATA%\pkm\git`): Git-Verzeichnis außerhalb des Cloud-Ordners
  - `PKM_CACHE_DIR` (Standard macOS `~/Library/Application Support/pkm`, Windows `%APPDATA%\pkm`): Suchindex. Muss außerhalb von `PKM_ROOT` und jedes Cloud-Ordners liegen. Liegt es nach `resolve()` innerhalb von `PKM_ROOT`, legt der Server keinen Index an und meldet einen Fehler. `search` ist dann nicht verfügbar, die übrigen lesenden Tools funktionieren weiter
  - `PKM_TZ` (Standard `Europe/Berlin`)
  - `PKM_MAX_KB` (Standard 200): Grenze für ein Dokument bzw. für den Text einer einzelnen Änderung
  - `PKM_VAULT_NAME` (optional): Name des Obsidian-Vaults, um klickbare `obsidian://`-Links zu liefern
  - `PKM_INLINE_MAX_KB` (Standard 24): Grenze für eingebettete Bilder, kodierte Größe (4.9)
  - `PKM_SVG_MAX_KB` (Standard 200): Komplexitätsgrenze für SVG
  - `PKM_IMAGE_MAX_MB` (Standard 5): Obergrenze je Bild
  - `PKM_IMAGE_PARAM_MAX_KB` (Standard 512): Obergrenze für `png_base64` in einem Aufruf
  - `PKM_IMPORT_DIR` (Standard `<PKM_ROOT>/pkm_img_import`): einziger Ordner, aus dem der Server Bilddateien übernimmt (`import_path`). Im Vault ist nur `pkm_img_import/` erlaubt (in `.gitignore`, von allen Pflegebefehlen ausgenommen wie `scratch/`); alternativ ein Ordner außerhalb des Vaults. Nur `.png`, `.svg`, `.jpg` und `.jpeg`, die Quelle wird kopiert, nicht gelöscht. Über den Cloud-Speicher lassen sich Bilder so auch von anderen Geräten (z. B. dem Smartphone) übergeben
  - `PKM_SVG_RASTER` (Standard `false`): SVG für `read_image` mit `as: image` rastern (zusätzliche Bibliothek, z. B. `resvg`)
  - `PKM_GIT_AUTHOR` (Standard `pkm-mcp <pkm@localhost>`): Autor der MCP-Commits, damit sie sich im Verlauf von denen des Nutzers unterscheiden
- Kein Netzwerk, keine LLM-Aufrufe, keine Hintergrundprozesse
- Umfang: rund 550 Zeilen plus Tests

**Adressierung:** Jeder Parameter `target` akzeptiert einen relativen Pfad (`documents/haus/zisterne.md`), einen Wikilink (`[[documents/haus/zisterne]]`, `[[zisterne]]`) oder eine ID (`id:d-20261031-2340-k7q2`) oder eine Kurzbezeichnung aus `short_citation` (z. B. `EN 61000-4-6:2014`). Ein Kurzname ist der Dateiname ohne Endung. Er wird in NFC und ohne Unterscheidung von Groß- und Kleinschreibung verglichen. Kurzbezeichnungen werden ebenso verglichen, zusätzlich mit zusammengefasstem Leerraum. Mehrdeutige Kurznamen oder Kurzbezeichnungen führen zum Fehler `ambiguous` mit Kandidatenliste. Pfade und Kurznamen können auch auf `scratch/` zeigen. IDs gibt es dort nicht.

### 7.2 Schreibende Tools

Gemeinsame Regeln:
- **Neuanlage** nur in `documents/_inbox/` bzw. in `scratch/` (`area: "scratch"`). **Änderungen** nur an bestehenden `.md`-Dateien unter `documents/` und `scratch/`.
- **Sonderregeln für `scratch/`:** Hash-Schutz, atomares Schreiben, Protokoll und Diff gelten wie überall. Es gibt aber **keine Versionierung und keinen Commit**: `version` wird nicht gesetzt oder erhöht, `note` wird ignoriert, `commit` und `version` fehlen in der Rückgabe. `date_updated` wird nur gesetzt, wenn die Datei ein Frontmatter hat (zeilengenau, 4.1). `rewrite_document` prüft die Kürzung auch hier.
- **Hash-Schutz:** Jede Änderung verlangt `expected_hash` aus `read` oder aus der vorherigen Schreib-Rückgabe. Bei Abweichung kommt `conflict` mit dem neuen Hash zurück.
- **Versionierung:** Jeder erfolgreiche Aufruf erhöht `version` um 1, setzt `date_updated` und erzeugt einen Commit nach 5.4. Weicht die Datei vom letzten Commit ab, weil sie von Hand geändert wurde, wird dieser Stand vorher als eigene Version committet.
- **Änderungsnotiz:** Jedes Tool hat den optionalen Parameter `note` (eine Zeile). Sie wird zur Commit-Nachricht. Ohne Notiz erzeugt der Server eine Standardnotiz aus Tool und Abschnitt.
- **Atomar:** Die Datei wird erst in eine temporäre Datei geschrieben und dann umbenannt. Schlägt der Commit fehl, wird die Datei zurückgesetzt und ein Fehler gemeldet.
- **Protokoll** in `.pkm/mcp.log` (nur anhängen, nicht in Git).
- **Rückgabe:** `{ id, path, status, version, new_hash, commit, diff }`. Der Diff ist ein Unified Diff, gekürzt auf 80 Zeilen.
- **Bilder:** `create_document`, `rewrite_document`, `append_to_document` und `edit_document` haben den optionalen Parameter `images`. Im Text steht an der gewünschten Stelle `{{image:<name>}}`. Der Server ersetzt den Platzhalter nach 4.9 durch eine eingebettete Data-URI oder legt eine Datei an und setzt den Link. Bilddatei und Dokument landen im selben Commit.

  | Feld je Bild | Typ | Pflicht | Beschreibung |
  |---|---|---|---|
  | `name` | string | ja | Bildname, wird zu `pkm:<name>` |
  | `alt` | string | ja | Alternativtext, eine Zeile |
  | `svg` | string | eins von drei | SVG als Text |
  | `png_base64` | string | eins von drei | PNG als Base64, höchstens `PKM_IMAGE_PARAM_MAX_KB` |
  | `import_path` | string | eins von drei | PNG-, JPEG- oder SVG-Datei in `PKM_IMPORT_DIR` (Dateiname genügt), sonst `forbidden` |
  | `mode` | enum `auto` \| `inline` \| `file` | nein | Standard `auto` (4.9). `inline` über der Grenze ergibt `too_large_for_inline`. In `scratch/` immer `inline` |

  Die Rückgabe nennt je Bild Format, Modus, Größe und Hash.
- **Data-URIs im Text** (4.9, „Prüfung bei der Übernahme“): Enthält `content`, `text` oder `new` eine Bild-Data-URI, prüft der Server sie, auch wenn sie formal richtig aussieht (Bereinigung, Größe, Name, Alternativtext). Weicht sie ab, kommt `nonconforming_image` mit `image_issues`, und es wird nichts geschrieben. Nach Bestätigung durch den Nutzer wiederholt der Chat den Aufruf mit `fix_images: true`; der Server schreibt die Bilder dann in der Form nach 4.9, Alternativtexte aus `image_alt` (Objekt Name → Text) gehen vor. Abweichende Bilder, die schon im Dokument stehen, blockieren nicht; die Rückgabe nennt sie unter `image_warnings`.

  | Parameter (alle schreibenden Tools außer `update_frontmatter` und `restore_document`) | Typ | Standard | Beschreibung |
  |---|---|---|---|
  | `fix_images` | bool | `false` | Abweichende Data-URIs im übergebenen Text nach 4.9 korrigieren. Nur nach Bestätigung |
  | `image_alt` | object | – | Alternativtexte für Bilder mit `missing_alt`, Schlüssel ist der Name aus `image_issues` |
- **Nicht angeboten:** Löschen, Umbenennen, Verschieben, jede Änderung in `wiki/`.

#### `create_document`
| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `title` | string | ja | Wird zu `title`. Daraus wird auch der Dateiname gebildet |
| `content` | string (Markdown) | ja | Ohne Frontmatter. Ein mitgeliefertes Frontmatter wird entfernt. Bild-Platzhalter `{{image:<name>}}` siehe 7.2 |
| `images` | list[object] | nein | Bilder zum Text (7.2, 4.9) |
| `tags` | list[string] | nein | Schlagwörter (Kleinbuchstaben, Bindestrich). Werden vereinheitlicht (4.1) |
| `short_citation` | string | nein | Kurzbezeichnung, z. B. `EN 61000-4-6:2014` |
| `date_document` | string | nein | Ausgabedatum wie gedruckt |
| `context` | string | nein | z. B. Chat-Titel |
| `related` | list[string] | nein | Ziele verwandter Dokumente (Pfad/Wikilink/ID) |
| `kind` | enum `note` \| `standard` \| `regulation` \| `correction` | nein | Standard `note` |
| `toolchain` | string | empfohlen | Wird zu `toolchain_markdown`, z. B. `Claude Opus 5.5 (pkm-mcp)`. Fehlt der Wert, schreibt der Server `pkm-mcp` |
| `area` | enum `documents` \| `scratch` | nein | Standard `documents` |
| `folder` | string | nein | Nur bei `area: "scratch"`: Unterordner in `scratch/` (wird angelegt, falls nötig). Standard ist die Wurzel von `scratch/` |

Ergebnis bei `documents`: Datei `documents/_inbox/<slug>_YYYY-MM-DD.md` (4.1) mit Frontmatter nach 4.1: `date_markdown` = jetzt, `toolchain_markdown`, `id`, `version: 1`. Commit `doc: <title> v1`. Bei Namensgleichheit kommt ein Suffix vor das Datum (`<slug>-2_YYYY-MM-DD.md`), es wird nie überschrieben. Zu lange Namen werden nur im Slug gekürzt (4.1).

Ergebnis bei `scratch`: Datei `scratch/[<folder>/]<slug>.md` mit kleinem Frontmatter (`title`, `date_markdown`, später `date_updated`), ohne `id`, `version` und Commit. `tags`, `related` und `kind` werden übernommen, falls angegeben. Bei Namensgleichheit wird ein Suffix angehängt.

#### `rewrite_document`
Ersetzt den **gesamten Inhalt** unterhalb des Frontmatters. Das ist der Normalfall bei fortgeführten Diskussionen.

| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `target` | string | ja | |
| `content` | string (Markdown) | ja | Neuer Inhalt ohne Frontmatter |
| `expected_hash` | string | ja | |
| `note` | string | empfohlen | Änderungsnotiz für den Verlauf |
| `confirm_shortening` | bool | nein | Standard `false` |

Schutz gegen versehentlichen Verlust: Ist der neue Inhalt kürzer als 60 % des alten oder fehlen Abschnitte (Schlüssel nach 4.8) des alten Inhalts, bricht das Tool mit `large_shortening` ab. Es nennt die betroffenen Abschnitte. Der Chat muss die Kürzung vom Nutzer bestätigen lassen und erneut mit `confirm_shortening: true` aufrufen. Das Frontmatter bleibt erhalten, nur die Serverfelder werden aktualisiert.

#### `append_to_document`
| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `target` | string | ja | |
| `text` | string | ja | Einzufügender Markdown-Text |
| `expected_hash` | string | ja | |
| `section` | string | nein | Exakter Überschriftentext. Der Text wird am Ende dieses Abschnitts eingefügt. Fehlt der Abschnitt, wird er am Dateiende als Ebene 2 angelegt. Ohne Angabe wird am Dateiende angehängt |
| `note` | string | nein | |

#### `edit_document`
| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `target` | string | ja | |
| `old` | string | ja | Muss genau einmal im Text vorkommen (außerhalb des Frontmatters). Sonst kommt `not_found` oder `ambiguous` mit Anzahl zurück |
| `new` | string | ja | Darf leer sein |
| `confirm_shortening` | bool | nein | Standard `false`. Bestätigt, dass die Änderung ein Bild entfernt (4.9) |
| `expected_hash` | string | ja | |
| `note` | string | nein | |

#### `update_frontmatter`
| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `target` | string | ja | |
| `set` | object | nein | Felder setzen oder überschreiben |
| `add` | object | nein | An Listenfelder anhängen, ohne Duplikate |
| `remove` | list[string] | nein | |
| `expected_hash` | string | ja | |
| `note` | string | nein | |

Geschützt: `id`, `version`, `date_markdown`, `date_updated`, `status_markdown`. Beim Schreiben werden Werte mit `: ` automatisch in Anführungszeichen gesetzt (4.1). Das Frontmatter wird vollständig neu geschrieben, in der Reihenfolge aus 4.1. Kommentare darin gehen verloren (4.1). Der Pflege-Agent benutzt dieses Tool nicht, sondern `set_document_metadata` (7.7).

#### `add_image`
Fügt ein Bild in ein bestehendes Dokument ein.

| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `target` | string | ja | |
| `expected_hash` | string | ja | |
| `image` | object | ja | ein Bild wie bei `images` (7.2) |
| `section` | string | nein | Abschnitt, an dessen Ende das Bild eingefügt wird. Ohne Angabe am Dateiende |
| `caption` | string | nein | Bildunterschrift als Zeile unter dem Bild |
| `note` | string | nein | |

Ergebnis wie bei `append_to_document`: neue Version mit Commit. In `scratch/` ohne Version und Commit, Bild immer eingebettet.

#### `fix_images`
Korrigiert die Schreibweise abweichender Bild-Data-URIs in einem bestehenden Dokument (4.9). Nur nach **ausdrücklicher Bestätigung** des Nutzers mit `apply: true`.

| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `target` | string | ja | Dokument in `documents/` oder `scratch/`. `wiki/` ergibt `forbidden` |
| `expected_hash` | string | ja | |
| `images` | list[string] | nein | Nur diese Bilder (Namen aus `image_issues`). Standard: alle korrigierbaren |
| `image_alt` | object | nein | Alternativtexte für Bilder mit `missing_alt` (Name → Text) |
| `apply` | bool | nein | Standard `false`: nur Vorschlag. `true`: schreiben |
| `confirm_shortening` | bool | nein | Bestätigt das Entfernen von `unused_definition` |
| `note` | string | nein | Standard `Bilder nach 4.9 korrigiert` |

- Ohne `apply`: Status `proposal` mit `image_issues` und einem Diff in Platzhalter-Schreibweise. Es wird nichts geschrieben.
- Mit `apply: true`: neue Version mit Commit (`PKM-Source: chat`, `PKM-Fix: images`), Rückgabe wie bei den anderen schreibenden Tools. Ohne Befunde `unchanged`. Nicht korrigierbare Befunde (`fixable: false`) bleiben stehen und werden genannt.
- Fehlt ein Alternativtext und ist keiner in `image_alt` angegeben, wird der Vorschlag aus `image_issues` übernommen, sofern der Nutzer ihn bestätigt hat; der Chat übergibt ihn dann ausdrücklich in `image_alt`.

#### `restore_document`
Holt den Inhalt einer früheren Version zurück, und zwar als **neue** Version. Die Geschichte wird nicht umgeschrieben. Für Dateien in `scratch/` kommt `not_versioned`.

| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `target` | string | ja | |
| `version` | int | ja | Wiederherzustellende Version |
| `expected_hash` | string | ja | |

Commit-Notiz: `wiederhergestellt aus v<n>`.

#### Korrekturen am Wiki

Das Wiki ist aus Chats nicht änderbar. Ein Korrekturwunsch wird per `create_document` mit `kind: correction` und `related: ["[[wiki/…]]"]` abgelegt. Der Inhalt nennt die falsche Aussage, die richtige Aussage und die Begründung. Der Pflege-Agent arbeitet die Korrektur ein (9.1).

### 7.3 Lesende Tools

#### `search`
| Parameter | Typ | Standard | Beschreibung |
|---|---|---|---|
| `query` | string | – | Suchbegriffe, Präfixsuche aktiv |
| `scope` | enum `wiki` \| `documents` \| `scratch` \| `all` | `wiki` | `all` umfasst `wiki` und `documents`. `scratch` wird nur durchsucht, wenn es ausdrücklich angegeben ist |
| `max_results` | int | 8 | höchstens 25 |

Rückgabe je Treffer: `id`, `version` (bei Dokumenten), `path`, `title`, `type`, `summary`, `snippet`, `score`, `date_updated`, `short_citation`, `processed` (bei Dokumenten: ob die aktuelle Version im Wiki eingearbeitet ist).

#### `read`
| Parameter | Typ | Beschreibung |
|---|---|---|
| `target` | string | Pfad, Wikilink oder ID |
| `version` | int | optional. Liest eine frühere Version aus Git (nur lesend) |
| `section` | string | optional. Nur dieser Abschnitt (Schlüssel nach 4.8) als `content`. Unbekannter Schlüssel: `not_found` mit der Liste der Abschnitte |
| `offset`, `max_chars` | int | optional. Seitenweises Lesen: `content` ab Zeichen `offset`, höchstens `max_chars` Zeichen. Rückgabe zusätzlich `truncated` und `next_offset` |
| `content` | bool | Standard `true`. Mit `false` nur Metadaten, `sections`, `hash` und `content_length` |

Rückgabe: `id`, `version`, `path`, `frontmatter`, `content`, `content_length`, `hash`, `editable`, `images` (4.9, mit `conforming` und `problems`), `sections` (je Abschnitt `key`, `level`, `sha`, bei leeren Abschnitten `empty: true`), `backlinks`, `links`. Ist der Inhalt größer als 40.000 Zeichen und weder `section` noch `offset`/`max_chars` angegeben, fehlt `content`, und die Rückgabe enthält `content_omitted: true` mit Hinweis. So wird nie stillschweigend nur ein Teil geliefert. Große Dokumente werden abschnittsweise gelesen und nur mit `edit_document` oder `append_to_document` geändert, nie mit `rewrite_document` aus einem Teilinhalt. Bei Wiki-Seiten zusätzlich `citations` (geparst, ohne Prüfung). Bei PDFs und Bildern nur Metadaten und Pfad. Lesbar sind `documents/`, `scratch/` und `wiki/`. In `scratch/` fehlen `id` und `version`, `editable` ist `true`.

#### `read_image`
| Parameter | Typ | Beschreibung |
|---|---|---|
| `target` | string | Dokument bzw. bei eigenständigen Bildern die Bilddatei |
| `image` | string | Bildname (bei eigenständigen Bildern weglassen) |
| `as` | enum `auto` \| `image` \| `svg_text` | `auto`: PNG als Bild, SVG als Text. `image` für SVG nur mit `PKM_SVG_RASTER` |

Rückgabe: das Bild (als Bildinhalt bzw. SVG-Text) mit Name, Alternativtext, Format, Größe und Hash. Verfügbar in `pkm-mcp` und `pkm-maintenance-mcp`. Damit lassen sich Bilder ohne verbundenen Vault-Ordner ansehen.

#### `history`
Für Dateien in `scratch/` kommt `not_versioned`.

| Parameter | Typ | Beschreibung |
|---|---|---|
| `target` | string | Dokument |
| `diff_from` | int | optional. Version, ab der verglichen wird |
| `diff_to` | int | optional. Standard ist die aktuelle Version |

Rückgabe: Liste der Versionen mit `version`, `date`, `source` (`chat` | `user` | `agent`), `note` und `commit`. Mit `diff_from` zusätzlich ein Unified Diff zwischen den Versionen. Grundlage sind die `PKM-Id`-Zeilen der Commits, deshalb funktioniert das auch nach Verschieben und Umbenennen.

#### `show_citations`
| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `target` | string | ja | Wiki-Seite |
| `statement` | string | nein | Textstück. Grenzt auf die Belege der Absätze ein, die diesen Text enthalten |
| `with_excerpt` | bool | nein | Lädt den Abschnitt aus dem Original in der **belegten Version** und, falls abweichend, zusätzlich in der aktuellen Version (je höchstens 1.500 Zeichen) |

Rückgabe je Beleg: `id`, `statement`, `original` (aktueller Pfad, aufgelöst nach 5.2), `anchor`, `quote`, `cited_version`, `current_version`, `status`, optional `cited_excerpt`, `current_excerpt` und `obsidian_link`.

| `status` | Bedeutung |
|---|---|
| `ok` | Original gefunden, belegter Abschnitt in der aktuellen Version unverändert |
| `moved` | Über ID oder Hash an neuem Ort gefunden. Der Link wird beim nächsten Pflegelauf korrigiert |
| `newer_version` | Abschnitt hat sich seit der belegten Version geändert. Der Beleg stimmt für seine Version, die Aussage ist aber eventuell überholt |
| `missing` | Original nicht auffindbar. Der Wortlaut ist bei Markdown trotzdem über Git abrufbar |

#### `read_index`
Gibt `wiki/index.md` zurück.

#### `list_unprocessed`
Liste der Dokumente, deren aktueller Stand noch nicht im Wiki eingearbeitet ist (nach 4.8, „Was daraus folgt“): ID, Titel, Pfad, `processed_version` → `version`, Kategorie und betroffene Abschnitte. Wird live berechnet.

### 7.4 Suchindex

- `PKM_CACHE_DIR/index.db`, FTS5 mit `unicode61 remove_diacritics 2`
- Bilder: nur ihr Alternativtext wird indexiert, nie Base64 oder SVG-Inhalt (4.9)
- Gewichte: Titel 5, Aliase/Tags/Themen 3, Kurzfassung 2, Text 1. Zusätzlich eine Tabelle `id → path, version` für die Auflösung nach 5.2
- `index.db` liegt in `PKM_CACHE_DIR`, nie im Vault oder in einem Cloud-Ordner (7.1)
- Der Index umfasst `wiki/`, `documents/` und `scratch/`. Welcher Bereich durchsucht wird, bestimmt `scope`
- Vor jeder Anfrage werden geänderte Dateien nachindexiert (Vergleich von `mtime` und Größe)
- Fehlt der Index oder ist er beschädigt, baut der Server ihn automatisch neu auf

### 7.5 Sicherheit

- Pfadprüfung mit `resolve()`. Kein `..`, keine absoluten Pfade, keine Symlinks nach außen. `import_path` nur innerhalb von `PKM_IMPORT_DIR`
- Bilder: SVG-Bereinigung und PNG-Prüfung nach 4.9
- `pkm-mcp` schreibt nur wie in 7.2 beschrieben. **Nie änderbar:** `wiki/`, `CLAUDE.md`, Nicht-Markdown-Dateien, alles außerhalb von `PKM_ROOT`
- `pkm-maintenance-mcp` schreibt nur wie in 7.7 beschrieben: Wiki-Seiten in den vier Seitenordnern, die generierten Dateien über `finish_maintenance`, `.pkm/state.json` und in Dokumenten nur `id`/`version` sowie die freigegebenen Metadaten. Löschen kann auch er nicht
- Git-Aufrufe nur mit fest vorgegebenen Argumenten (kein Durchreichen von Eingaben als Optionen). Pfade werden nach `--` übergeben
- Es gibt keine Git-Operation, die Geschichte umschreibt (`reset`, `rebase`, `push --force` usw.)
- Rückgaben enthalten nur relative Pfade
- Erzeugte Dateinamen sind plattformfest (5.5)

### 7.6 Einbindung in Claude Desktop

`pkm setup` prüft zuerst, ob beide Server in `claude_desktop_config.json` (macOS `~/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`) schon passend eingetragen sind. Fehlt ein Eintrag oder weicht er ab, zeigt es die Änderung und fragt, ob es die Datei ändern darf. Bei „ja“ entsteht eine Sicherungskopie, die Einträge werden ergänzt bzw. ersetzt und andere Einträge bleiben unverändert. Ein Eintrag mit dem alten Namen `pkm-pflege` (bis 0.2.0) wird dabei entfernt; das alte Programm `pkm-pflege-mcp` bleibt als Alias installiert, damit er bis dahin weiter läuft. Bei „nein“ (oder wenn die Datei kein gültiges JSON ist) ändert es nichts und zeigt den JSON-Text, den der Nutzer selbst unter `mcpServers` einträgt. Weil Vault-Pfad, Git und alle übrigen Werte in `config.toml` stehen, braucht ein Eintrag nur den absoluten Pfad des Programms:

```json
{
  "mcpServers": {
    "pkm": { "command": "<HOME>/.local/bin/pkm-mcp" },
    "pkm-maintenance": { "command": "<HOME>/.local/bin/pkm-maintenance-mcp" }
  }
}
```

Unter Windows heißen die Programme `pkm-mcp.exe` und `pkm-maintenance-mcp.exe` (in JSON jeden Backslash verdoppeln). JSON kennt weder `~` noch Umgebungsvariablen, deshalb absolute Pfade. Ein `env`-Block ist weiter möglich und hat Vorrang; `pkm setup` schreibt `PKM_CONFIG` nur hinein, wenn die Konfigurationsdatei nicht im Standardordner liegt. Die Server sind erreichbar, solange die Desktop-App auf dem PKM-Rechner läuft, auch aus Cowork.

### 7.7 MCP-Server `pkm-maintenance-mcp`

Zweiter lokaler Server aus demselben Paket für die Wiki-Pflege aus Claude Desktop bzw. Cowork. Grund: Cowork führt Shell-Befehle nur in einer abgeschotteten Umgebung aus (lokale VM bzw. Cloud), in der `pkm`, Git und das Git-Verzeichnis fehlen. MCP-Server dagegen laufen auf dem PKM-Rechner und sind über die Desktop-App erreichbar. Technik, Konfiguration, Sicherheit und Protokoll wie 7.1, 7.5 und 7.2. Keine LLM-Aufrufe: Der Server bündelt nur die deterministischen Schritte. Inhaltliche Arbeit (Seiten formulieren, Belege wählen) macht der Agent.

Der Server bietet die lesenden Tools aus 7.3 und fünf Pflege-Tools:

#### `begin_maintenance`
| Parameter | Typ | Standard | Beschreibung |
|---|---|---|---|
| `with_lint` | bool | `false` | Zusätzlich den Prüfbericht liefern (Ablauf „Lint“) |

Führt nacheinander aus: `doctor --short`, `versions`, `ids`, `pending` und bei Verschiebungen `fix-citations` (8). Rückgabe: `status`, `versions`, `ids`, `pending`, `fixed_citations`, `known_tags` und optional `lint`.
- `status: blocked`: Die Umgebung hat Fehler (z. B. Konfliktkopien, `.git` im Vault). Es wurde nichts geändert, `doctor` nennt die Fehler.
- `status: needs_decision`: Es gibt doppelte IDs. Der Agent fragt nach.
- `pending.new` enthält je Markdown-Dokument `missing_fields`: welche von `title`, `context`, `tags`, `kind` fehlen oder leer sind.
- `pending.new` und `pending.changed` enthalten je Markdown-Dokument mit abweichenden Data-URIs `image_issues` (4.9). Dokumente, die sich nur in der Bildschreibweise geändert haben, tragen `image_notation_only: true`.
- `known_tags`: alle Tags aus `documents/` und `wiki/` mit Häufigkeit, häufigste zuerst.

#### `write_wiki_page`
| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `path` | string | ja | Seite unter `wiki/topics/`, `wiki/entities/`, `wiki/summaries/` oder `wiki/syntheses/`, mit oder ohne `.md` |
| `content` | string | ja | Vollständiger Inhalt mit Frontmatter (4.2) |
| `expected_hash` | string | bei bestehenden Seiten | `hash` aus `read`. Bei neuen Seiten weglassen |

Legt die Seite an oder ersetzt sie vollständig, ohne Commit (den macht `finish_maintenance`). `wiki/index.md`, `wiki/_status.md`, `wiki/log.md`, `wiki/_lint/` und alles außerhalb der vier Seitenordner ergeben `forbidden`. Bestehende Seite ohne oder mit falschem `expected_hash` bzw. neue Seite mit `expected_hash` ergibt `conflict`. Abweichende Data-URIs (4.9) ergeben `nonconforming_image` mit `image_issues`; mit dem Parameter `fix_images: true` korrigiert der Server sie ohne Rückfrage, weil die Seite dem Agenten gehört. Rückgabe: `status` (`created`, `changed`, `unchanged`), `path`, neuer `hash`.

#### `set_document_metadata`
Nur nach **ausdrücklicher Bestätigung** des Nutzers (9.6).

| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `target` | string | ja | Dokument in `documents/` (Pfad, Wikilink, `id:` oder Kurzbezeichnung) |
| `expected_hash` | string | ja | `hash` aus `read` |
| `set` | object | nein | Felder setzen |
| `add` | object | nein | Nur `tags`: Werte anhängen |
| `overwrite` | bool | nein | Standard `false`. Vorhandene Werte nur auf ausdrücklichen Wunsch überschreiben |
| `note` | string | nein | Änderungsnotiz |

- **Whitelist:** `title`, `context`, `tags`, `kind`, `short_citation`. Andere Felder ergeben `protected_field`.
- Vorhandene, nicht leere Werte werden ohne `overwrite: true` nicht geändert (`field_exists` mit dem vorhandenen Wert). Entfernen ist nicht möglich.
- `kind` muss einer der Werte aus 4.1 sein. Tags werden vereinheitlicht (klein, Umlaute ausgeschrieben, Leerraum zu Bindestrich) und ohne Duplikate gespeichert. Leere Werte ergeben `invalid_argument`.
- Felder werden zeilengenau an ihrer Stelle nach 4.1 gesetzt. Das Ergebnis ist eine neue Version mit Commit und `PKM-Source: agent` (5.4), ohne Änderung `unchanged`.

#### `fix_images`
Wie `fix_images` in `pkm-mcp` (7.2), für Dokumente in `documents/`. Nur nach **ausdrücklicher Bestätigung** des Nutzers (9.7), nie in unbeaufsichtigten Läufen. Commit mit `PKM-Source: agent` und `PKM-Fix: images`. `scratch/` und `wiki/` ergeben `forbidden`.

#### `finish_maintenance`
| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `log_entry` | string | ja | Inhalt des Log-Eintrags (Markdown-Liste, 4.5) |
| `operation` | enum `ingest` \| `lint` \| `fix` | nein | Standard `ingest` |
| `log_title` | string | nein | Kurzangabe in der Log-Überschrift, z. B. `1 neu, 1 geändert` |
| `processed` | list[string] | nein | Verarbeitete Dokumente (IDs bzw. Pfade bei PDF/Bild) |
| `removed` | list[string] | nein | Schlüssel verarbeiteter gelöschter Dokumente |
| `questions` | list[string] | nein | Rückfragen für `wiki/_status.md` |
| `lint_report` | bool | nein | Prüfbericht nach `wiki/_lint/YYYY-MM-DD.md` schreiben |

Führt nacheinander aus: `fix-citations` (inkl. Wikilinks im Text), Anheben von Belegen auf unveränderte Abschnitte und auf Abschnitte, in denen sich nur die Bildschreibweise geändert hat (6.4, 4.9), `sync-citations`, `mark` für `processed` mit den belegenden Seiten (aus den Fußnoten ermittelt, Warnung bei Dokumenten ohne Beleg), Austragen von `removed`, Log-Eintrag, `index`, `status` mit `questions`, `lint` und `commit-wiki` (`pkm: <operation> <n> documents`). Rückgabe: Ergebnisse der Schritte, Lint-Bericht, Commit und Warnungen. Meldet Lint Fehler in den eigenen Seiten, behebt der Agent sie mit `write_wiki_page` und ruft `finish_maintenance` erneut mit `operation: fix` auf.

---

## 8. CLI `pkm`

Die CLI dient der Einrichtung, Prüfung und Fehlersuche. Der Pflege-Agent ruft sie nicht direkt auf, sondern nutzt `pkm-maintenance-mcp` (7.7), das dieselben Funktionen bündelt.

Alle Befehle außer `pkm reindex` ignorieren `scratch/` (3). `pkm doctor` prüft nur, dass `scratch/` in `.gitignore` steht.

| Befehl | Funktion |
|---|---|
| `pkm setup` | Geführte Einrichtung (15.1): vorhandene Konfiguration anzeigen und übernehmen, Vault-Ordner, Git-Prüfung (ohne Git Hinweis und Betrieb ohne Versionsverwaltung, 5.4), Git-Identität für das PKM-Repo, Sprache von Dokumenten und Wiki (`PKM_LANGUAGE`, 4.1, 4.2), `config.toml`, `pkm init`, Abgleich von `CLAUDE.md` mit der Vorlage (15.1), Einträge in Claude Desktop (7.6, alter Eintrag `pkm-pflege` wird ersetzt), Skill-ZIPs, Projektanweisung, `pkm doctor`. Wiederholbar; Optionen `--vault`, `--vault-name`, `--git-name`, `--git-email`, `--language`, `--yes`, `--claude-config`, `--skills-dir`, `--json` |
| `pkm init` | Legt Struktur, `CLAUDE.md`, `wiki/index.md`, `log.md`, `_status.md`, `state.json`, `.gitignore`, den Importordner `pkm_img_import/`, `.obsidian/types.json` (Property-Typen, 13) und `.obsidian/app.json` (Einstellungen aus 13; fehlende Werte ergänzt, abweichende gemeldet) an und initialisiert mit Versionsverwaltung das Git-Verzeichnis außerhalb des Vaults, falls nötig (idempotent) |
| `pkm ids` | Trägt fehlende `id`/`version` in Markdown-Dokumente ein und committet **je Dokument einzeln** (`doc: <title> v1`, `PKM-Source: agent`). Meldet doppelte IDs |
| `pkm versions` | Committet alle von Hand geänderten Dokumente als neue Version (je Dokument eine, `PKM-Source: user`). Erkennt auch Verschiebungen (Markdown über die ID, PDF/Bild über den Hash) und committet sie mit: ein Commit enthält dann alten und neuen Pfad. Eine neue Version entsteht nur, wenn sich `body_hash` oder `meta_hash` geändert hat (4.8). Reines Verschieben ergibt den Commit `doc: <title> moved` ohne Versionssprung. Eine von Hand geänderte `CLAUDE.md` wird als eigener Commit `pkm: CLAUDE.md geändert` mit `PKM-Source: user` erfasst Ändert sich eine verlinkte Bilddatei, erhält jedes Dokument, das sie verwendet, eine neue Version im selben Commit wie das Bild (4.9). Zugehörige Bilddateien werden nicht als eigenständige Dokumente geführt. |
| `pkm pending` | JSON-Liste der zu verarbeitenden Dokumente: `new`, `changed` (mit `processed_version` → `version` und geänderten Abschnitten), `moved` (alt → neu), `deleted` (mit betroffenen Wiki-Seiten) |
| `pkm history <target> [--diff <von> [<bis>]]` | Wie das MCP-Tool `history` |
| `pkm show <target> --version <n> [--section <name>]` | Inhalt einer früheren Version |
| `pkm fix-citations` | Korrigiert Links in Belegen, Anker umbenannter Abschnitte und `sources`, deren Ziel verschoben wurde, außerdem Wikilinks auf verschobene Originale im Seitentext. Wurde in Obsidian verschoben, hat Obsidian die Links schon aktualisiert; dann ändert sich nichts (`pages_changed: 0`) |
| `pkm sync-citations [<page>…]` | Erzeugt `sources` aus den Fußnoten neu |
| `pkm sha <target> [--section <key>] [--full]` | Abschnitts- oder Datei-Hash nach 4.8 (Standard: 6 Zeichen für Belege). Ohne `--section` werden alle Schlüssel mit Hash, `body_hash`, `meta_hash` und `file_hash` aufgelistet. Hilft bei der Fehlersuche |
| `pkm mark <id>… --pages <page>…` | Trägt verarbeitete Dokumente mit Version und Abschnitts-Hashes in `state.json` ein |
| `pkm index` | Erzeugt `wiki/index.md` neu |
| `pkm status` | Erzeugt `wiki/_status.md` neu, inklusive Einsortier-Vorschlägen für verarbeitete Dokumente im Eingang Meldet außerdem verwaiste Anhänge (Bilddateien ohne Verweis, 4.9). |
| `pkm lint` | JSON-Bericht. **Struktur:** kaputte Links, verwaiste Wiki-Seiten, fehlende Kurzfassung, fehlerhaftes Frontmatter, häufige Begriffe ohne Seite. **Belege:** Ziel fehlt oder verschoben, Anker fehlt, Zitat nicht in der belegten Version, Status `newer_version`, Beleg zeigt auf Wiki-Seite, Absatz ohne Fußnote (`statement_without_citation`, nicht für Zwischenüberschriften, reine Hervorhebungs- und Link-Zeilen und für Tabellen mit Fußnote direkt darunter, 4.2), Beleg auf einen Abschnitt ohne eigenen Text (`citation_empty_section`), Fußnote ohne Definition, `sources` nicht synchron. **Dokumente:** ohne ID oder Version, doppelte IDs, ungültiges YAML durch fehlende Anführungszeichen (Fehler, mit Hinweis auf `pkm fix-frontmatter`), fehlende Felder `date_markdown`/`toolchain_markdown` (Hinweis), Feld `short citation` mit Leerzeichen (Hinweis), umgewandeltes Dokument ohne `kind` (Hinweis), unbekannter Wert in `kind` (Fehler), Datumsfelder weder im Format `YYYY-MM-DDTHH:MM:SS` noch `YYYY-MM-DD` oder mit Zeitzonen-Angabe, `tags` mit Leerzeichen, `version` passt nicht zum Commit-Verlauf. **Plattform:** Konfliktkopien des Cloud-Speichers (5.5), nicht plattformfeste Dateinamen, Namen, die sich nur in Groß- und Kleinschreibung unterscheiden. **Überschriften (4.8):** Duplikate, Zeichen, die Anker brechen, Text auf `#` plus Ziffern (`heading_suffix_like` als Warnung, `heading_suffix_collision` als Fehler) **Bilder (4.9):** `[img:<name>]` in Belegen ohne Bild in der belegten Version, Bilder ohne Alternativtext (Hinweis, nicht bei bestehenden Base64-PNG), doppelte Bildnamen im Dokument, unbereinigtes SVG (Fehler), verwaiste Anhänge (Hinweis), abweichende Data-URIs `nonconforming_image` mit den Befundcodes (Warnung; Fehler bei `svg_unsafe` und `invalid_data`; mit Hinweis auf `pkm fix-images`). |
| `pkm restore <target> --version <n>` | Wie `restore_document` |
| `pkm reindex` | Baut den Suchindex neu auf |
| `pkm fix-frontmatter <target>… [--all]` | Repariert das Frontmatter zeilengenau, sonst ändert sich nichts: setzt Werte mit `: ` oder führenden YAML-Sonderzeichen in doppelte Anführungszeichen und benennt `short citation` in `short_citation` um. **Nur auf ausdrückliche Anweisung des Nutzers.** Ohne Ziel listet der Befehl nur die betroffenen Dateien auf. Jede geänderte Datei wird als neue Version committet (`PKM-Source: user`, weil der Nutzer es veranlasst hat) |
| `pkm fix-images <target>… [--all] [--apply] [--alt <name>=<text>]` | Korrigiert die Schreibweise abweichender Bild-Data-URIs nach 4.9, sonst ändert sich nichts. **Nur auf ausdrückliche Anweisung des Nutzers.** Ohne `--apply` zeigt der Befehl Befunde, Vorschläge und Diff, ohne Ziel listet er nur die betroffenen Dateien. Mit `--apply` wird jede geänderte Datei als neue Version committet (`PKM-Source: user`, `PKM-Fix: images`) |
| `pkm commit-wiki --message "<text>"` | Agenten-Commit am Ende eines Pflegelaufs (12). Committet ausschließlich `wiki/` und `.pkm/state.json`. Offene Änderungen in `documents/` bleiben unberührt |
| `pkm doctor` | Prüft die Umgebung: Git-Verzeichnis außerhalb des Vaults und erreichbar, `PKM_CACHE_DIR` außerhalb des Vaults, beide außerhalb jedes Cloud-Ordners (alle bekannten Dienste), kein `.git` im Vault, `user.name`/`user.email`, Schreibrechte, Konfliktkopien des Cloud-Speichers, Dateien „nur online“ im Vault (`vault_online_only`, Warnung), erkannter Dienst des Vaults (`vault_cloud`, Hinweis), Obsidian-Einstellungen aus Abschnitt 13 (soweit in `.obsidian/app.json` lesbar). Mit `--short` nur Fehler Prüft außerdem, dass `PKM_IMPORT_DIR` entweder `pkm_img_import/` im Vault (dann in `.gitignore`) oder ein Ordner außerhalb des Vaults ist. |

---

## 9. Skill `pkm-wiki` (Pflege, im Projekt)

**Beschreibung (Trigger):** Pflege des PKM-Wikis über den MCP-Server `pkm-maintenance`: neue und geänderte Dokumente verarbeiten, Lint, Wiki-Fragen im Pflegeprojekt.

Der Agent arbeitet ausschließlich über die Tools von `pkm-maintenance-mcp` (7.7). Eine Shell oder die CLI braucht er nicht. Neue Wiki-Seiten, Log-Eintrag und Bericht schreibt er in der Sprache, die der Server nennt (`PKM_LANGUAGE`, 4.2); bestehende Seiten behalten ihre Sprache.

### 9.1 Ablauf „Ingest“

1. `begin_maintenance`. Bei `blocked` wird abgebrochen und das Problem gemeldet. Bei `needs_decision` (doppelte IDs) fragt der Agent nach. Änderungen von Hand, auch die vom Windows-Rechner, sind danach als Versionen committet, fehlende IDs vergeben und Belege auf verschobene Dokumente korrigiert.
2. **Neue Dokumente:** mit `read` vollständig lesen (große Dokumente abschnittsweise, 7.3).
   1. Seite `wiki/summaries/<name>.md` mit `write_wiki_page` anlegen, mit Belegen.
   2. Über `read_index` (und bei Bedarf `search`) betroffene Seiten bestimmen. Höchstens 10–15 Themen-, Entitäts- und Syntheseseiten aktualisieren oder anlegen. Jede neue oder geänderte Aussage bekommt eine Fußnote nach 4.2. Werte für `id`, `v:` und `sha:` liefert `read` (`id`, `version`, `sections`).
   3. Querverweise in beide Richtungen setzen.
   4. Frontmatter prüfen (`missing_fields`) und Vorschläge erarbeiten (9.6). Noch nichts eintragen.
   5. Befunde zu Data-URIs (`image_issues`) für den Bericht übernehmen (9.7). Noch nichts korrigieren.
   6. Bestehende Seiten vor dem Ändern mit `read` lesen und deren `hash` als `expected_hash` an `write_wiki_page` geben.
3. **Geänderte Dokumente:** `history` mit `diff_from: <processed_version>` lesen und nur die geänderten Abschnitte verarbeiten (Abschnitt 6.4).
   1. Betroffene Wiki-Aussagen auf den neuen Stand bringen, mit Belegen auf die neue Version.
   2. Bei geänderten Entscheidungen oder Fakten den früheren Stand als „Bis Version n: …“ mit Beleg auf die alte Version behalten, sofern er für die Nachvollziehbarkeit wichtig ist.
   3. Belege auf unveränderte Abschnitte hebt `finish_maintenance` selbst an.
   4. Die Zusammenfassungsseite des Dokuments aktualisieren.
4. **Nur Metadaten geändert** (`meta_changed`): Zusammenfassungsseite anpassen. Die Belege hebt `finish_maintenance` an. **Nur Bildschreibweise geändert** (`image_notation_only`): nichts zu verarbeiten, das Dokument wird als `processed` gemeldet, die Belege hebt `finish_maintenance` an.
5. **Gelöschte Dokumente:** Betroffene Aussagen werden nicht gelöscht. Sie kommen unter „Widersprüche / offene Fragen“ mit dem Vermerk „Original nicht mehr vorhanden (letzter Stand in Git, v<n>)“, `confidence: low`, und im Bericht steht eine Rückfrage. Der Schlüssel geht an `finish_maintenance` als `removed`.
6. **Korrektur-Dokumente** (`kind: correction`): Die Korrektur des Nutzers hat Vorrang vor älteren Quellen und gilt selbst als Beleg. Die betroffene Wiki-Seite wird angepasst und die alte Aussage im Log als ersetzt vermerkt. Widerspricht die Korrektur einer Quelle, die neuer ist als sie selbst, fragt der Agent nach.
7. **Bilder:** Jedes neue oder geänderte Bild, eingebettet oder verlinkt, sieht sich der Agent mit `read_image` an. Er übernimmt den Inhalt in Worten und belegt ihn mit `[img:<name>]` (4.9). Zugehörige Bilder bekommen keine eigene Zusammenfassung, eigenständige wie bisher. **PDF:** `read` liefert nur Metadaten und `hash`. Den Inhalt liest der Agent, wenn der Vault-Ordner in der Unterhaltung verbunden ist. Sonst wird das PDF nicht als verarbeitet gemeldet und im Bericht genannt.
8. `finish_maintenance` mit `processed`, `removed`, `log_entry`, `log_title` und gegebenenfalls `questions` (7.7). Meldet Lint Fehler in den eigenen Seiten, werden sie behoben und `finish_maintenance` mit `operation: fix` erneut aufgerufen.
9. Kurzer Bericht im Chat: neue und geänderte Seiten, überholte Aussagen, Beleg-Probleme, Einsortier-Vorschläge, Rückfragen und je neuem Dokument mit fehlenden Feldern ein YAML-Block mit Vorschlägen und der Frage, ob er eingetragen werden soll (9.6), sowie je Dokument mit abweichenden Data-URIs die Befunde mit Korrekturvorschlag und der Frage, ob korrigiert werden soll (9.7).

**Grenzen:** Mehr als 10 Dokumente pro Lauf werden in Etappen verarbeitet. Nicht verarbeitete Dokumente werden nicht als `processed` gemeldet. Bei unklarer Einordnung fragt der Agent nach. Im unbeaufsichtigten Lauf entscheidet er konservativ und gibt Fragen über `questions` nach `wiki/_status.md` und ins Log.

### 9.2 Ablauf „Lint“

1. `begin_maintenance` mit `with_lint: true`.
2. **Selbst beheben** (mit `write_wiki_page`): kaputte Links mit eindeutigem Ziel, fehlende Kurzfassungen. Verschobene Belege, `sources` und Index erledigt `finish_maintenance`.
3. **Vorschlagen statt ausführen:** fehlende Frontmatter-Felder von Dokumenten (9.6), abweichende Data-URIs in Dokumenten (9.7), inhaltliche Widersprüche, Zusammenlegen von Seiten, neue Seiten, doppelte IDs, Belege mit `newer_version`, die nicht automatisch angehoben werden konnten.
4. `finish_maintenance` mit `operation: lint` und `lint_report: true` (Bericht nach `wiki/_lint/YYYY-MM-DD.md`) und einem Log-Eintrag.

### 9.3 Ablauf „Abfrage“ (im Projekt)

Erst den Index, dann die relevanten Seiten, dann die Antwort mit Verweisen auf die Wiki-Seiten. Auf Nachfrage nennt der Agent die Belege. Gute Antworten bietet er als Seite unter `syntheses/` an und legt sie nach Zustimmung mit `write_wiki_page` an (Abschluss mit `finish_maintenance`, `operation: fix`).

### 9.4 Ablauf „Schema anpassen“

Änderungen an `CLAUDE.md` schlägt der Agent als Diff vor. Geschrieben werden sie erst nach Zustimmung, und nur wenn der Vault-Ordner verbunden ist; sonst übernimmt der Nutzer die Änderung. `pkm versions` erfasst sie beim nächsten Lauf als Commit mit `PKM-Source: user`.

### 9.5 Feste Regeln

- Sprache: Deutsch.
- `scratch/` wird weder gelesen noch verarbeitet. Kein Beleg zeigt auf eine Datei dort.
- `status_markdown` unverändert lassen. Der Wert spielt für die Verarbeitung keine Rolle.
- In `documents/` setzt der Agent `id` und `version` (über `begin_maintenance`) und nach ausdrücklicher Bestätigung `title`, `context`, `tags`, `kind`, `short_citation` (über `set_document_metadata`, 9.6) sowie die Bildschreibweise (über `fix_images`, 9.7). Sonst ändert, verschiebt oder löscht er dort nichts. Die schreibenden Tools von `pkm-mcp` benutzt er in der Pflege nicht.
- Im Wiki nichts löschen. Aussagen und Belege werden ergänzt, aktualisiert oder als überholt gekennzeichnet.
- Keine Aussage ohne Beleg auf ein Dokument. Zitate in Belegen sind wörtlich aus der genannten Version kopiert. Nichts erfinden, Lücken als offene Frage markieren.
- Formate wie in Abschnitt 4.

### 9.6 Frontmatter-Vorschläge

Bei jedem **neuen** Dokument prüft der Agent das Frontmatter (`missing_fields` aus `begin_maintenance`, auch dünne Werte). Fehlen `title`, `context`, `tags` oder `kind`, schlägt er Werte als YAML-Block im Bericht vor:

- `title`: kurzer, sprechender Titel.
- `context`: eine Zeile `"<Art>: <Inhalt>"` (Art: Chat, Podcast, Buch, Artikel, Recherche, Notiz), wegen `: ` in doppelten Anführungszeichen.
- `tags`: 4–8 Stück, klein, Bindestriche, Umlaute ausgeschrieben. Vorhandene Tags (`known_tags`) werden wiederverwendet.
- `kind`: `note` (Standard), `standard` bzw. `regulation` (dann auch `short_citation` vorschlagen) oder `correction`.

Eingetragen wird erst nach **ausdrücklicher Bestätigung** des Nutzers im Chat: `read` → `hash` → `set_document_metadata`. Vorhandene Werte werden nicht überschrieben, außer der Nutzer will das ausdrücklich (`overwrite: true`). Bei `conflict` liest der Agent neu und meldet es. Jede Eintragung ist eine neue Version. Beim nächsten Lauf erscheint das Dokument als `meta_changed`. **In unbeaufsichtigten Läufen wird nie eingetragen;** die Vorschläge gehen als Frage nach `wiki/_status.md`.

### 9.7 Korrektur von Data-URIs

Meldet `begin_maintenance` oder Lint `image_issues` für ein Dokument, zeigt der Agent im Bericht je Bild Fundstelle (Abschnitt, Zeile), Befunde in Worten, den Vorschlag (Name, Alternativtext, eingebettet oder Datei, bei SVG das bereinigte Bild und entfernte Teile) und fragt, ob korrigiert werden soll. Fehlt ein Alternativtext, schlägt er einen vor und lässt ihn bestätigen oder ändern.

Korrigiert wird erst nach **ausdrücklicher Bestätigung**: `read` → `hash` → `fix_images` ohne `apply` (Vorschlag und Diff prüfen) → `fix_images` mit `apply: true` und `image_alt`. Bei `conflict` liest der Agent neu und meldet es. Nicht korrigierbare Befunde nennt er als offene Frage. Die Korrektur ist eine neue Version; beim nächsten Lauf erscheint das Dokument mit `image_notation_only` und braucht keine Neuverarbeitung. **In unbeaufsichtigten Läufen wird nie korrigiert;** die Vorschläge gehen als Frage nach `wiki/_status.md`. Bestehende eingebettete PNG behandelt der Agent nach 4.9 (nur Schreibweise, Bytes gleich, kein Name).

---

## 10. Skill `pkm-access` (für normale Chats)

**Beschreibung (Trigger):** Das PKM aus Chats nutzen: „leg das ins PKM“, „führ das im Dokument zu … weiter“, „aktualisier mein Dokument …“, „was weiß mein Wiki über …“, „woher stammt das?“, „was hat sich geändert?“, „korrigier im Wiki …“.

**Neu ablegen:**
1. Das Ergebnis verdichten (Ergebnis, Entscheidungen, Offene Punkte, Kontext), in der Dokumentsprache aus den Anweisungen des Servers (4.1). Nur Belastbares aufnehmen, Hypothesen kennzeichnen.
2. Titel, `tags` und gegebenenfalls `related` vorschlagen. `toolchain` mit dem eigenen Modellnamen und `pkm-mcp` übergeben.
3. Vorher prüfen, ob es zum Thema schon ein Dokument gibt (`search`, Bereich `documents`). Wenn ja, fragen, ob es aktualisiert werden soll (Abschnitt 6.1).
4. Den Entwurf zeigen und erst nach Bestätigung `create_document` aufrufen. Das gilt **ohne Ausnahme**, auch wenn der Nutzer „direkt“ sagt.
5. ID, Pfad und Version nennen.

**Grundregel:** Jeder schreibende Aufruf (ablegen, neufassen, ergänzen, bearbeiten, Frontmatter, Bilder korrigieren, wiederherstellen) erfolgt erst, nachdem ein Entwurf gezeigt und bestätigt wurde. Es gibt keine Ausnahme.

**Fortgeführte Diskussion:** Standard ist 6.2, also das Dokument aktualisieren, mit Vorher/Nachher pro Abschnitt, Änderungsnotiz und Bestätigung. 6.3 (datierter Abschnitt) **nur auf ausdrückliche Anweisung** und nie von sich aus vorschlagen.

**Bilder (4.9):**
- Diagramme, Skizzen und Schaltpläne zeichnet der Chat als **SVG**. Fotos und Screenshots bleiben PNG.
- Neue Bilder werden über `images` bzw. `add_image` abgelegt, immer mit Alternativtext und erst nach Entwurf und Bestätigung. Im Entwurf zeigt der Chat das Bild mit.
- **Im Chat hochgeladene Fotos oder Screenshots** kann der Chat nicht byte-genau weitergeben. Er bittet, die Datei in den Importordner `pkm_img_import/` im Vault zu legen (z. B. per Finder bzw. Explorer oder über die App des Cloud-Dienstes), und übernimmt sie mit `import_path`. Bei einfachen Grafiken bietet er alternativ eine SVG-Nachzeichnung an, gekennzeichnet als „nachgezeichnet“.
- Zum Ansehen eines Bildes dient `read_image`. Base64 wird nie in den Text übernommen.
- **Keine Data-URIs von Hand in den Text schreiben**, Bilder immer über `images` bzw. `add_image`.
- **`nonconforming_image`:** Befunde und Vorschlag aus `image_issues` dem Nutzer zeigen (bei SVG das Bild), fehlende Alternativtexte erfragen und erst nach Bestätigung den Aufruf mit `fix_images: true` (und `image_alt`) wiederholen, oder die Fassung mit `images` neu aufbauen.
- **Abweichende Bilder im Bestand** (`image_warnings` beim Schreiben, `conforming: false` in `read`): dem Nutzer nennen und die Korrektur anbieten. Nach Bestätigung `fix_images` ohne `apply` (Vorschlag zeigen), dann mit `apply: true`. Nie von sich aus korrigieren.
- Bestehende eingebettete PNG bleiben unverändert; bei ihnen wird nach Bestätigung höchstens die Schreibweise korrigiert (4.9).

**Große Dokumente:** Liefert `read` kein `content` (`content_omitted`), liest der Chat abschnittsweise (`section`) und ändert nur mit `edit_document` bzw. `append_to_document`, nie mit `rewrite_document` aus einem Teilinhalt (7.3).

**Kleine Änderungen:** `read` → `edit_document`/`append_to_document`/`update_frontmatter` → Vorher/Nachher zeigen → bestätigen lassen → ausführen → Version und Diff nennen. Bei `conflict` neu lesen, nie blind wiederholen. Bei `large_shortening` die betroffenen Abschnitte nennen und ausdrücklich bestätigen lassen.

**Verlauf:** Auf „was hat sich geändert?“ oder „wie war das vorher?“ das Tool `history` aufrufen, bei Bedarf mit Diff, oder `read` mit `version`. Auf „mach das rückgängig“ `restore_document` mit der vorherigen Version, nach Bestätigung.

**Abfragen:**
1. Bei einer breiten Frage `read_index`, sonst `search` (Bereich `wiki`).
2. Die Top-Treffer mit `read` öffnen und mit Verweis auf die Wiki-Seiten antworten.
3. Dokumente zum Thema, deren aktuelle Version noch nicht eingearbeitet ist (`processed: false`), werden als „noch nicht im Wiki“ erwähnt.
4. **Auf Nachfrage nach Quellen:** `show_citations` mit der Aussage aufrufen, bei Bedarf mit `with_excerpt`. Je Aussage Original, Abschnitt/Seite, Zitat, belegte und aktuelle Version, Status und Obsidian-Link nennen. Bei `newer_version` den aktuellen Wortlaut dazu zeigen.
5. Ohne Nachfrage genügen die Wiki-Seiten. Die Originale werden aber angeboten, wenn die Antwort für eine Entscheidung gebraucht wird.

**Korrekturen am Wiki:** immer als Dokument mit `kind: correction` (7.2), nie direkt.


**Notizen und Todo-Listen (`scratch/`):**
- Auslöser sind z. B. „notier mir kurz …“, „setz das auf meine Todo-Liste“, „hak … ab“ oder „was steht auf meiner Liste?“.
- Neue Notizen entstehen mit `create_document` und `area: "scratch"`. Bestehende Listen werden mit `append_to_document` bzw. `edit_document` geändert, etwa beim Abhaken (`- [ ]` → `- [x]`). Ist unklar, welche Liste gemeint ist, sucht der Chat mit `search` und `scope: "scratch"` und fragt bei mehreren Treffern nach.
- **Auch hier gilt die Grundregel:** erst Entwurf bzw. Vorher/Nachher zeigen, dann nach Bestätigung schreiben.
- Der Chat weist darauf hin, dass Inhalte in `scratch/` nicht ins Wiki übernommen werden. Soll etwas dauerhaft festgehalten werden, schlägt er stattdessen ein Dokument in `documents/` vor.
- Für eine Datei in `scratch/` nennt der Chat keine Version und keinen Commit.

---

## 11. Projekt „PKM Maintenance“ und Automatisierung

- **Projekt** in Claude Desktop (Chat oder Cowork) mit der Anweisung: „Dies ist das Pflegeprojekt für das PKM. Nutze den Skill `pkm-wiki` und die Tools des Servers `pkm-maintenance`. Dokumente in `documents/` änderst du nicht.“
- **Server:** In Pflege-Unterhaltungen ist `pkm-maintenance` eingeschaltet, in allen anderen ausgeschaltet (7.6). Der Agent arbeitet nur über dessen Tools (7.7). Die Shell in Cowork ist abgeschottet; dort gibt es weder `pkm` noch Git.
- **Ordnerzugriff (optional):** Wird der Vault im Chat über „+“ → „Ordner hinzufügen“ verbunden, kann der Agent auch PDFs und Bilder lesen. Für Markdown ist das nicht nötig.
- **Start: manuell.** Pflegeläufe werden im Projekt angestoßen („Verarbeite neue Dokumente“, „Lint“).
- **Automatik (vorbereitet, später):** eine geplante Aufgabe, z. B. täglich „Ingest, danach Lint“. Geplante Cowork-Aufgaben laufen in der Cloud und erreichen `pkm-maintenance` nur über die Desktop-App. Der PKM-Rechner muss dafür wach sein und die Claude-Desktop-App laufen; das ist vor dem Einschalten zu testen. Der Skill ist schon dafür ausgelegt: Im unbeaufsichtigten Lauf entscheidet er konservativ und schreibt Rückfragen in `wiki/_status.md` und ins Log, statt zu warten. Eingeschaltet wird die Automatik nur auf Anweisung des Nutzers.

---

## 12. Git

Git ist optional (seit 0.26, 5.4) und übernimmt, wenn vorhanden, zwei Aufgaben: die **Versionsgeschichte jedes Dokuments** und die **Nachvollziehbarkeit der Agentenarbeit**. Ohne Git entfallen alle Commits dieses Abschnitts.

**Commits nach Herkunft** (alle mit den Zeilen aus 5.4):

| Commit | Wer | Wann | Inhalt |
|---|---|---|---|
| `doc: <title> v<n>` | pkm-mcp | bei jeder Änderung aus einem Chat | genau ein Dokument |
| `doc: <title> v<n>` (Quelle `user`) | pkm-mcp bzw. `pkm versions` | vor einer MCP-Änderung bzw. zu Beginn eines Pflegelaufs | genau ein von Hand geändertes Dokument |
| `doc: <title> v1` (Quelle `agent`) | `pkm ids` (über `begin_maintenance`) | im Pflegelauf, falls nötig | genau ein Dokument, nur Frontmatter-Felder `id`/`version` |
| `doc: <title> v<n>` (Quelle `agent`) | `set_document_metadata` | nach Bestätigung des Nutzers | genau ein Dokument, nur `title`, `context`, `tags`, `kind`, `short_citation` |
| `pkm: CLAUDE.md changed` (Quelle `user`) | `pkm versions` | zu Beginn eines Pflegelaufs | nur `CLAUDE.md` |
| `pkm: ingest <n> documents` / `pkm: lint` / `pkm: fix` | Pflege-Agent über `finish_maintenance` (intern `commit-wiki`) | am Ende eines Laufs | nur `wiki/` und `.pkm/state.json` |

So bleibt sauber getrennt, was von dir, aus einem Chat oder vom Agenten stammt. Ein `git revert` auf einen Agenten-Commit trifft nur das Wiki.

- Das Git-Verzeichnis liegt außerhalb des Cloud-Ordners (5.5). Die Versionsgeschichte existiert damit **nur auf dem PKM-Rechner** und muss dort gesichert werden. **macOS:** Time Machine, denn `~/Library/Application Support/pkm/` ist darin enthalten. **Windows:** Der Dateiversionsverlauf sichert `%APPDATA%` standardmäßig nicht. `%APPDATA%\pkm\git` wird deshalb ausdrücklich in die Datensicherung aufgenommen, oder `PKM_GIT_DIR` zeigt von Anfang an auf einen gesicherten Ordner außerhalb jedes Cloud-Ordners. Der Suchindex ist ein Cache und muss nicht gesichert werden.
- `.gitignore`: `scratch/`, `pkm_img_import/`, `.obsidian/workspace*`, `.pkm/mcp.log`, Hilfsdateien der Cloud-Dienste und Programme (Nextcloud/ownCloud `.sync_*`, `.owncloudsync.log`, `*.part`; Dropbox `.dropbox`, `.dropbox.attr`; Syncthing `.stfolder`, `.stversions/`; Google Drive `.tmp.drivedownload/`, `.tmp.driveupload/`; iCloud `*.icloud`; Windows `desktop.ini`; Office-Sperrdateien `~$*`, `.~lock.*`; `.DS_Store`)
- Obsidian Git wird nicht verwendet. Das Plugin fände das Repo auch gar nicht, weil kein `.git` im Vault liegt.
- Kein Remote. Ein Push auf ein privates Remote (z. B. Gitea auf dem Homeserver) lässt sich später ohne Änderung am Konzept nachrüsten.

---

## 13. Obsidian-Einstellungen

**Obsidian ist optional.** Der Vault besteht aus reinem Markdown; jeder Editor kann ihn lesen und bearbeiten, und keine Funktion der Werkzeuge setzt Obsidian voraus. Obsidian ist das empfohlene Frontend (Wikilinks, Backlinks, Anzeige der Properties und eingebetteter Bilder, Graph). Ohne Obsidian entfällt das automatische Umschreiben von Links beim Verschieben (5.1, Mechanismus 1); die Dateien unter `.obsidian/` legt `pkm init` trotzdem an, sie stören nicht. Die folgenden Einstellungen gelten, wenn Obsidian genutzt wird.

`pkm init` trägt die folgenden Einstellungen in `.obsidian/app.json` ein, soweit sie fehlen; abweichende Werte bleiben und werden gemeldet. Obsidian liest die Datei nach einem Neustart.

- **Dateien & Links:**
  - „Interne Links automatisch aktualisieren“: **an** (Grundlage von 5.1)
  - „Neues Link-Format“: **Absoluter Pfad im Vault**, damit Belege eindeutig sind
  - „Wikilinks verwenden“: an
  - Anhang-Ordner: `documents/_attachments/`
- **Ausgeschlossene Dateien:** `.pkm/`, optional `pkm_img_import/` (dann tauchen Übergabebilder nicht in Suche und Graph auf)
- **Bilder:** Anhang-Ordner `documents/_attachments/` (siehe oben). Eingebettete Bilder (Data-URIs, 4.9) zeigt Obsidian im Lese- und Live-Vorschau-Modus an. Das ist vor der Umsetzung mit PNG und SVG, auch mit `|breite`, zu testen.
- **Web Clipper:** Zielordner `documents/_inbox/`. Die Vorlage des Clippers wird an 4.1 angepasst: `title` (Seitentitel), `source` (URL, wird von den Werkzeugen nicht ausgewertet), `date_document` (Veröffentlichungsdatum der Seite, falls vorhanden), `date_markdown` (Zeitpunkt des Clippens im Format `YYYY-MM-DDTHH:MM:SS`), `toolchain_markdown: Obsidian Web Clipper`, `tags`. Die Standardvorlage des Clippers verwendet teils andere Namen. Maßgeblich ist, was in den Einstellungen des Clippers eingestellt ist.
- **Property-Typen:** `pkm init` legt sie in `.obsidian/types.json` an bzw. ergänzt fehlende, ohne vom Nutzer gesetzte Typen zu ändern; `pkm doctor` meldet Abweichungen. Von Hand in Obsidian über das Symbol neben dem Feldnamen im Eigenschaften-Bereich einer Notiz: `date_markdown` und `date_updated` als **Datum & Uhrzeit**, `version` als **Zahl**, `related` und `sources` als **Liste**, alle übrigen eigenen Felder als **Text**. `tags` und `aliases` sind Obsidian-Standard.
- Optional: Dataview für Abfragen über das Frontmatter, Graph View (eingebaut)
- **Alle Rechner** (Mac und Windows) nutzen denselben Vault über den Cloud-Speicher. Die Einstellungen in `.obsidian/` werden mitsynchronisiert und gelten überall.
- Auf den **anderen Rechnern** (nicht PKM-Rechner) wird nur in Obsidian gelesen und bearbeitet. Änderungen von dort werden beim nächsten MCP-Zugriff auf die Datei bzw. beim nächsten Pflegelauf als Version mit `PKM-Source: user` übernommen.

---

## 14. Tests und Abnahme

**Automatisiert (pytest, mit temporärem Git-Repo):**
- Bilder (4.9): Einbetten bis 24 KB, Datei darüber, `scratch/` immer eingebettet, bestehende Base64-PNG byte-genau unverändert (auch über der Grenze und ohne Bildnamen), SVG-Bereinigung (Script, Ereignis-Attribute, externe Verweise, XXE), URL-Kodierung bricht keine Markdown-Syntax, Platzhalter in `read` und byte-genaue Rückübersetzung bei `rewrite_document`/`edit_document`, entfernte Bilder als `large_shortening`, `read_image` für PNG, JPEG und SVG, `import_path` nur aus `PKM_IMPORT_DIR`, JPEG ohne Metadaten mit erhaltener Ausrichtung, `pkm_img_import/` von `init` angelegt, in `.gitignore` und von Pflegelauf, Lint und Suche ausgenommen, zugehörige Bilder nicht als `new`, geänderte Bilddatei ergibt neue Version des Dokuments, verwaiste Anhänge, Index ohne Base64
- Data-URIs bei der Übernahme (4.9): jeder Befundcode positiv und negativ, darunter der Referenzstil mit `;utf8` und nicht kodierten Leerzeichen und `{}` (Testvektor aus der Praxis), HTML-`<img>`, spitze Klammern, Base64-SVG, Base64 mit Zeilenumbrüchen, falscher Medientyp, fehlender und doppelter Name, fehlender Alternativtext, unsicheres SVG, Data-URI in Codeblöcken und Inline-Code ignoriert. Schreibende Tools liefern `nonconforming_image` und schreiben nichts, mit `fix_images: true` entsteht die Form nach 4.9, übriger Text byte-genau. `image_warnings` blockieren nicht. `fix_images` ohne `apply` schreibt nichts (`proposal`), mit `apply` genau eine Version mit `PKM-Fix: images`, abgeleiteter Name bleibt erhalten, `[img:<name>]`-Belege bleiben gültig. Mehrfach verwendete Referenzdefinition ergibt `ambiguous`, `unused_definition` nur mit `confirm_shortening`. Bestehende Base64-PNG: nur Schreibweise, dekodierte Bytes gleich, kein Name eingetragen. `read` zeigt in jeder Schreibweise Platzhalter statt Base64 bzw. SVG und stellt sie beim Schreiben byte-genau wieder her. `pending` meldet `image_notation_only`, `finish_maintenance` hebt die Belege an, nicht aber bei entfernten SVG-Teilen. `write_wiki_page` lehnt abweichende Data-URIs ab, mit `fix_images: true` korrigiert. `pkm fix-images` ohne `--apply` ändert nichts
- Pfadprüfung, Neuanlage nur in `_inbox/`, Änderungen nur in `documents/**/*.md`, `wiki/` immer abgelehnt
- Adressierung über Pfad, Wikilink, Kurzname (auch in anderer Groß-/Kleinschreibung) und ID, einschließlich `ambiguous`
- ID-Vergabe: Format, Kollisionsprüfung, `pkm ids` bei Datei mit und ohne Frontmatter (Inhalt byte-genau erhalten, Kommentare im Frontmatter erhalten), je Dokument ein Commit, doppelte IDs
- Versionen: jede Schreiboperation erhöht `version` um genau 1 und erzeugt genau einen Commit nur dieser Datei mit korrekten Zeilen. Von Hand geänderter Stand wird vor der MCP-Änderung separat committet. `pkm versions` fasst mehrere Änderungen von Hand zu einer Version zusammen und committet reines Verschieben ohne Versionssprung, Verschieben mit Änderung als neue Version. `pkm commit-wiki` lässt offene Änderungen in `documents/` unberührt. Commit-Fehler setzen die Datei zurück
- `history` nach Verschieben und Umbenennen vollständig. `read` mit `version`. `restore_document` erzeugt eine neue Version
- Änderungs-Tools: Hash-Konflikt, `large_shortening` und Bestätigung, Einfügen in bestehenden und neuen Abschnitt, `old` nicht gefunden oder mehrdeutig, geschützte Felder, Diff
- Normalisierung und Hashes (4.8), mit festen Testvektoren: BOM, CRLF/CR, NFD-Text, fehlendes oder doppeltes LF am Ende, ungültiges UTF-8. Frontmatter fehlend, ungültig oder mit `...`-Abschluss. Überschriften in Codeblöcken (``` und ~~~, verschachtelte Zaunlängen), Setext, Ebene 3 innerhalb von Ebene 2, ATX-Abschluss, Einrückung bis 3 Leerzeichen. Vorspann leer und nicht leer. Duplikate über Ebene 1 und 2. Wörtliche Überschrift `Version#2` neben zwei `Version`: Schlüssel `Version`, `Version#2`, `Version#3`. Lint meldet `heading_suffix_like` bzw. `heading_suffix_collision`. Leerraum-Änderungen lassen Abschnitts-Hashes unverändert. Eine Frontmatter-Änderung nur an `date_updated` ändert `file_hash`, aber nicht `body_hash` und `meta_hash`
- `pending`: neu, `changed` mit `added`/`removed`/`changed`/`renamed` je Abschnitt, nur Reihenfolge, `meta_changed`, verschoben (per ID bzw. Hash), verschoben *und* geändert, gelöscht
- Tools: `section` mit `_preamble` und mit Duplikat-Suffix, `ambiguous` ohne Suffix, `edit_document` mit CRLF- bzw. NFD-Eingabe
- Belege: Parser (inkl. `v:` und `#page=`), alle Status von `show_citations`, Auszug aus alter und aktueller Version, `fix-citations`, `sync-citations`, alle Lint-Prüfungen positiv und negativ
- Suche: Umlaut-Toleranz, Gewichtung, inkrementelle Aktualisierung, Neuaufbau. `PKM_CACHE_DIR` innerhalb von `PKM_ROOT` wird abgelehnt
- Ohne Git: schreibende Tools verweigert, lesende funktionieren
- Frontmatter (4.1): die Norm aus dem Beispiel mit unquotiertem `: ` im Titel ergibt `invalid_frontmatter`, `pkm fix-frontmatter` macht sie gültig und ändert nur diese Zeile. Ein Dokument mit genau den sechs Umwandlungsfeldern bekommt durch `pkm ids` nur `id` und `version`, eingefügt hinter `toolchain_markdown`. Neue Felder landen an ihrer Stelle nach 4.1, `update_frontmatter` schreibt in dieser Reihenfolge. `short_citation` wird gelesen, geschrieben und als Ziel aufgelöst. Die alte Schreibweise `short citation` wird gelesen und von `pkm fix-frontmatter` umbenannt. `meta_hash` ändert sich nicht bei Änderung von `status_markdown`. Kein Werkzeug schreibt `status_markdown`. Datumswerte gehen als Zeichenkette in `meta_hash` ein. `date_markdown` und `date_updated` werden mit Uhrzeit ohne Zeitzone geschrieben, in Ortszeit nach `PKM_TZ`
- `scratch/`: Anlegen mit `area: "scratch"` und `folder`, Ändern ohne Version und Commit, `history`/`restore_document` liefern `not_versioned`, `search` findet `scratch/` nur mit `scope: "scratch"`, `pending`, `ids`, `versions` und `lint` ignorieren den Bereich, Lint meldet einen Beleg im Wiki, der auf `scratch/` zeigt, Verschieben von `scratch/` nach `documents/` ergibt beim nächsten Lauf `version: 1` und einen Commit
- Getrenntes Git-Verzeichnis: alle Git-Operationen mit `--git-dir`/`--work-tree`, im Vault entsteht nie ein `.git`
- Dateinamen: `create_document` erzeugt `<slug>_YYYY-MM-DD.md`, bei Namensgleichheit `<slug>-2_YYYY-MM-DD.md`. Bei sehr langen Titeln wird der Slug gekürzt, Datum und Suffix bleiben vollständig, der Name hat höchstens 120 Zeichen
- `pkm-maintenance-mcp`: vollständiger Lauf (ID vergeben, Seite schreiben, abschließen, danach nichts offen), `blocked` bei Fehlern der Umgebung, `write_wiki_page` lehnt generierte Dateien, Bereiche außerhalb der Seitenordner und `..` ab und prüft `expected_hash`, `finish_maintenance` ermittelt die Seiten aus den Fußnoten und trägt `removed` aus. `set_document_metadata`: Whitelist, `field_exists` ohne `overwrite`, ungültiges `kind`, Tag-Vereinheitlichung, Commit mit `PKM-Source: agent`. `begin_maintenance` liefert `missing_fields` und `known_tags`. `pkm versions` committet eine geänderte `CLAUDE.md`
- `read` mit `section`, `offset`/`max_chars`, `content: false` und `content_omitted` bei großen Inhalten. Leere Abschnitte mit `empty: true`
- Lint: keine Warnung für Zwischenüberschriften, Hervorhebungs- und Link-Zeilen und belegte Tabellen, weiterhin Warnung für unbelegte Tabellen und Sätze, `citation_empty_section`
- Verschieben außerhalb von Obsidian bei veraltetem Index: `fix-citations` schreibt Beleg und Wikilink im Text um. Belege auf unveränderte Abschnitte werden angehoben, Belege auf geänderte nicht
- Plattform: Tests laufen unter Linux, macOS und Windows. NFC/NFD-Pfade, CRLF-Datei ergibt denselben Hash wie LF, Windows-ungültige Zeichen und reservierte Namen im Slug ersetzt, Konfliktkopien erkannt und nicht verarbeitet, Groß-/Kleinschreibungs-Kollisionen gemeldet

**Abnahme (manuell):**
1. Aus einem Chat: „Leg das Ergebnis ins PKM.“ → Die Datei erscheint als `documents/_inbox/<slug>_YYYY-MM-DD.md` mit ID und `version: 1`, und es gibt einen Commit.
2. Im Pflegeprojekt (Server `pkm-maintenance` eingeschaltet): „Verarbeite neue Dokumente.“ → Zusammenfassung, Themenseiten mit Belegen (`v:1`), Index, Status, Log, Agenten-Commit, Vorschläge für fehlende Frontmatter-Felder. Nach Bestätigung werden sie eingetragen (neue Version mit `PKM-Source: agent`).
3. In Obsidian das Dokument einsortieren → Die Belege zeigen sofort auf den neuen Ort.
4. In einem neuen Chat: „Führ die Diskussion zum Überlaufsensor weiter …“ → Der Chat findet das Dokument, zeigt die Änderungen pro Abschnitt und eine Notiz und schreibt nach Bestätigung `version: 2`. Das Dokument enthält keinen Fortsetzungsabschnitt.
5. „Was hat sich geändert?“ → Verlauf v1 → v2 mit Notiz und Diff.
6. Nächster Pflegelauf → Nur die geänderten Abschnitte werden verarbeitet. Das Wiki zeigt den neuen Stand, bei einer geänderten Entscheidung zusätzlich „Bis Version 1: …“ mit Beleg auf v1.
7. „Woher stammt die Angabe …?“ → Original mit Abschnitt, Zitat, Version und Status `ok`.
8. „Dokumentiere das als Fortsetzung“ → Erst jetzt entsteht ein datierter Abschnitt.
9. Auf einem anderen Rechner (z. B. Windows, wenn der PKM-Rechner ein Mac ist) ein Dokument in Obsidian ändern → Nach dem Sync und einem Pflegelauf gibt es eine neue Version mit `PKM-Source: user`, und das Wiki ist aktualisiert.
10. Aus einem Chat: „Setz ‚Filter der Zisternenpumpe reinigen‘ auf meine Todo-Liste“ → Entwurf, dann ein Eintrag in `scratch/`. Es gibt keinen Commit, und nach einem Pflegelauf taucht der Eintrag nicht im Wiki auf.
11. In Obsidian ein SVG im Referenzstil mit `;utf8` und nicht kodierten Zeichen einfügen → Der Pflegelauf meldet die Befunde mit Vorschlag. Nach Bestätigung entsteht eine neue Version, Obsidian zeigt das Bild, Belege bleiben `ok`.
12. `pkm doctor` und `pkm lint` melden null Fehler.

---

## 15. Umsetzungsschritte

| # | Schritt | Ergebnis |
|---|---|---|
| 1 | Paketgerüst, `pkm init`, Frontmatter- und Abschnitts-Parser, ID-Vergabe, Git-Schicht (Commit mit Zeilen, Verlauf nach ID) | Grundbibliothek |
| 2 | MCP: lesende Tools inkl. `history`, Suchindex, Adressierung | Abfragen aus Chats |
| 3 | MCP: schreibende Tools inkl. `rewrite_document` und `restore_document` | Ablegen und Aktualisieren aus Chats |
| 4 | CLI: `ids`, `versions`, `pending`, `mark`, `sha`, `index`, `status` | Pflege-Grundlage |
| 5 | Belege: `show_citations`, `fix-citations`, `sync-citations`, `lint` | Rückverfolgbarkeit |
| 6 | Skills `pkm-access` und `pkm-wiki`, Projekt | Erster echter Ingest-Lauf |
| 6a | MCP-Server `pkm-maintenance-mcp` (7.7), Skill `pkm-wiki` darauf umgestellt | Pflege aus Claude Desktop bzw. Cowork ohne Shell |
| 7 | Später: geplante Aufgabe | Automatische Verarbeitung, erst auf Anweisung des Nutzers |
| 8 | Einfachere Installation (15.1, umgesetzt in 0.26) | Einrichtung mit einem Skript und `pkm setup` statt rund zehn Handschritten |

### 15.1 Einfachere Installation (umgesetzt in 0.26)

Vorher brauchte die Einrichtung rund zehn Handschritte. Jetzt: Installer ausführen, `pkm setup` beantworten, zwei ZIP-Dateien hochladen, Projekt anlegen, Claude Desktop und Obsidian neu starten.

1. **Assistent `pkm setup`** (interaktiv, idempotent, auf Mac und Windows, Optionen in 8):
   - sucht zuerst eine **vorhandene Konfiguration**: Umgebungsvariablen, die `env`-Blöcke der PKM-Einträge in Claude Desktop (dort lagen die Einstellungen vor `pkm setup`; erkannt an den Namen `pkm`/`pkm-maintenance` oder an den Programmen `pkm-mcp`/`pkm-maintenance-mcp`, auch unter anderem Namen) und `config.toml`, in dieser Rangfolge. Nennt keine Quelle `PKM_ROOT`, gilt der Vault aus `core.worktree` des Git-Verzeichnisses (`PKM_GIT_DIR` bzw. Standard), sofern dort `.pkm/state.json` liegt. Gefundene Werte (alle Schlüssel aus 7.1, z. B. `PKM_ROOT`, `PKM_GIT_DIR`, `PKM_CACHE_DIR`) zeigt es mit ihrer Herkunft; überdeckte Werte aus nachrangigen Quellen sind gekennzeichnet. Es fragt, ob es sie übernehmen soll (`--yes`: ja). Übernommen sind sie die Vorgaben der folgenden Fragen und kommen in `config.toml`, sodass ein vorhandenes Git-Verzeichnis samt Verlauf weiter genutzt wird, auch wenn die Einträge in Claude Desktop danach ohne `env` auskommen. Bei „nein“ beginnt die Einrichtung mit einer neuen Konfiguration; eine vorhandene `config.toml` wird vorher gesichert (`config.toml.<Zeit>.bak`). Geschlossene Eingabe (Dateiende) gilt bei jeder Frage als leere Antwort, also als Vorgabe;
   - fragt den Vault-Ordner ab (legt ihn nach Bestätigung an) und erkennt den Cloud-Dienst (5.5); warnt bei Dateien „nur online“;
   - prüft Git. **Fehlt Git, gibt er einen Hinweis aus und schaltet die Versionsverwaltung ab** (5.4). Ist Git da und fehlt die Identität, fragt er Name und E-Mail ab und setzt sie nur für das PKM-Repo; die Commit-Signierung schaltet er für das PKM-Repo ab;
   - fragt die Hauptsprache von im Chat erzeugten Dokumenten und vom Wiki ab (Englisch oder Deutsch, `PKM_LANGUAGE`, 4.1, 4.2; Vorgabe ist der bisherige Wert, sonst Englisch);
   - schreibt `config.toml` (7.1; andere Schlüssel in der Datei bleiben) und führt `pkm init` aus;
   - prüft `CLAUDE.md` im Vault: `pkm init` legt die Datei nur an, wenn sie fehlt. Weicht eine vorhandene von der Vorlage der installierten Version ab (ältere Fassung oder eigene Änderungen), fragt der Assistent, ob er sie ersetzen soll. Bei „ja“ sichert er die alte nach `<App-Ordner>/backups/` (außerhalb des Vaults), schreibt die Vorlage und committet sie mit Versionsverwaltung (`PKM-Source: user`). Bei „nein“ bleibt die Datei und die Vorlage kommt daneben als `CLAUDE.md.new` (wird von Pflege und Suche nicht erfasst, da außerhalb von `documents/` und `wiki/`);
   - prüft die Einträge in Claude Desktop (7.6); fehlen sie oder weichen sie ab, fragt es, ob es die Datei ändern darf (dann mit Sicherungskopie, andere Server bleiben), sonst zeigt es den Text zum Selbst-Eintragen;
   - baut die ZIP-Dateien der Skills `pkm-access` und `pkm-wiki` nach `<Standardordner>/skills/` (das Hochladen bleibt Handarbeit);
   - gibt die Projektanweisung für „PKM Maintenance“ aus (11) und endet mit `pkm doctor`.
2. **Konfigurationsdatei statt Umgebungsvariablen** (7.1): Der Eintrag in Claude Desktop braucht nur `command`, kein `env`; Git wird über `PKM_GIT` bzw. an den üblichen Orten gefunden, sodass auch `PATH` entfällt. `pkm doctor` nennt, welches Git verwendet wird und ob die Versionsverwaltung an ist.
3. **Obsidian-Einstellungen durch `pkm init`** (13): in `.obsidian/app.json`, wie die Property-Typen in `types.json`.
4. **Installation ohne Klonen:** Die Skills liegen im Paket (`pkm/skills/`). Der Installer lädt das ZIP-Archiv des Repositorys von GitHub und installiert daraus; das funktioniert ohne Git (`uv tool install git+…` bräuchte Git). Mit Git geht alternativ `uv tool install "git+https://github.com/achim0x/pkm-llm-wiki#subdirectory=pkm-tools"` (Aktualisieren mit `uv tool upgrade pkm-tools`). Jede GitHub-Release (Tag `v*`) enthält die Skill-ZIPs und das Paket als Wheel. PyPI bleibt optional für später.
5. **Installationsskripte** `install.sh` (Mac, auch Linux) und `install.ps1` (Windows), als Einzeiler aufrufbar: installieren uv, falls es fehlt, prüfen Git und geben **nur einen Hinweis** aus, wenn es fehlt (Git wird nicht installiert), installieren das Paket (4) und starten `pkm setup`. Außer uv und dem Paket ändern sie nichts ohne Rückfrage. Aktualisieren: Installer erneut ausführen. Die CI führt beide Installer auf macOS, Linux und Windows aus.

Nicht vorgesehen: eine reine Python-Git-Bibliothek statt Git (zu tiefer Eingriff in 5.4). Ein Erweiterungspaket (`.mcpb`) für Claude Desktop wird erst nach einer Prüfung der Unterstützung für Python-Server erwogen.

---

## 16. Entscheidungen

### Getroffen (Review vom 01.11.2026)

| # | Thema | Entscheidung | Umgesetzt in |
|---|---|---|---|
| 1 | Speicherort und Plattform | Vault in einem Cloud-Ordner (seit 0.25 jeder Dienst, der einen lokalen Ordner synchronisiert, Entscheidung 39; vorher Nextcloud). Gelesen und bearbeitet auf Mac und Windows, Agent und MCP nur auf dem PKM-Rechner (seit 0.22 Mac oder Windows, Entscheidung 36). In der Spezifikation stehen Platzhalter statt konkreter Pfade | 5.5, 7.1, 7.6, 12, 13 |
| 2 | Ordnernamen | Englisch | 3 und überall |
| 3 | Standardbereich der Chat-Suche | `wiki` | 7.3 |
| 4 | Bestätigung | Immer erst einen Entwurf zeigen, ohne Ausnahme | 10 |
| 5 | Automatik | Zunächst manuell, Automatik vorbereitet | 11, 15 |
| 6 | Git | Nur lokal, kein Obsidian Git | 12 |
| 7 | Startbefüllung | Keine. Wissen wird nach und nach bei Bedarf selbst angelegt. Bestehende Skills bleiben unberührt und werden nicht übernommen | 15 |
| 8 | Allgemeinheit | Keine Personennamen, Pfade als Platzhalter | überall |
| 9 | MCP-Toolnamen | Englisch | 2, 6, 7, 10 |
| 10 | Übrige Schnittstellen-Namen | Englisch (Parameter, Felder, Werte, CLI, Commit-Zeilen, Skills). Inhalte deutsch | 4.7 und überall |

### Getroffen (Umsetzungsplan, 01.11.2026)

| # | Thema | Entscheidung | Umgesetzt in |
|---|---|---|---|
| 11 | Suchindex und Protokoll | Index in `PKM_CACHE_DIR` außerhalb von Vault und Cloud-Ordner, geprüft von Server und `doctor`. Protokoll in `.pkm/mcp.log`, nicht in Git | 3, 5.5, 7.1, 7.2, 7.4, 8, 12 |
| 12 | Quelle bei Änderungen von Hand | `user` | 5.4, 7.3 |
| 13 | Commits von `pkm ids` | Je Dokument ein Commit, kein Sammel-Commit | 5.4, 8, 12 |
| 14 | Hashes und Abschnitte | Festgelegt in 4.8 | 4.8 |
| 15 | Schonfrist für gerade bearbeitete Dateien in `pkm versions` | Vorerst keine | – |
| 16 | Frontmatter-Erhalt | Serverfelder zeilengenau, `update_frontmatter` schreibt neu | 4.1, 7.2 |
| 17 | Verschieben in `pkm versions` | Ein Commit mit altem und neuem Pfad, neue Version nur bei geändertem Inhalt oder Metadaten | 8 |
| 18 | Kurznamen | Ohne Groß-/Kleinschreibung, mehrdeutig → `ambiguous` | 7.1 |
| 19 | Plattform für Tests | Pfade überschreibbar, Tests auch unter Linux, produktiv macOS oder Windows (36) | 7.1 |
| 20 | Agenten-Commit | `pkm commit-wiki`, nur `wiki/` und `.pkm/state.json` | 8, 9.1, 12 |
| 21 | Überschriften auf `#` plus Ziffern | Suffix-Vergabe überspringt belegte Schlüssel. Lint warnt (`heading_suffix_like`) bzw. meldet einen Fehler bei Kollision (`heading_suffix_collision`) | 4.8, 8, 14 |
| 22 | Bereich `scratch/` | Für kurzlebige Notizen und Todo-Listen. Nicht in Git, nie im Wiki, von Lint ignoriert. Chats dürfen anlegen und ändern (mit Entwurf), ohne Version und Commit | 3, 7, 8, 9.5, 10, 12 |
| 23 | Frontmatter | Schema der digitalisierten Normen (`title`, `short_citation`, `date_document`, `status_markdown`, `date_markdown`, `toolchain_markdown`), ergänzt um `id`, `version`, `date_updated`, `context`, `tags`, `related`, `kind`. Obsidian-taugliche Typen, Anführungszeichen bei `: ` | 4.1, 4.8, 7, 8, 13 |
| 24 | Feldnamen und `status_markdown` | Keine Leerzeichen in Feldnamen (`short_citation`). `status_markdown` nur bei Normen und Standards, unverändert übernommen, von keinem Werkzeug gesetzt oder geändert | 4.1, 7.2, 8 |
| 25 | Zeitangaben | `date_markdown` und `date_updated` mit Uhrzeit (`YYYY-MM-DDTHH:MM:SS`), Ortszeit ohne Zeitzone, Obsidian-Typ „Datum & Uhrzeit“. Datum-only-Werte bleiben gültig | 4.1, 13 |
| 26 | Werte von `kind` | `note`, `standard` (Normen und Standards), `regulation` (Gesetze und Verordnungen), `correction`. Verarbeitung von `standard` und `regulation` wie `note` | 4.1, 7.2, 8 |

### Getroffen (Pflegeläufe, 02.–03.11.2026)

| # | Thema | Entscheidung | Umgesetzt in |
|---|---|---|---|
| 27 | Pflege ohne Shell | Eigener lokaler MCP-Server `pkm-maintenance-mcp` mit `begin_maintenance`, `write_wiki_page`, `set_document_metadata`, `finish_maintenance`. Nur in Pflege-Unterhaltungen eingeschaltet (organisatorische statt technischer Grenze). CLI nur noch für Einrichtung, Prüfung, Fehlersuche | 2, 7.6, 7.7, 8, 9, 11 |
| 28 | Frontmatter-Vorschläge | Agent schlägt `title`, `context`, `tags`, `kind` vor und trägt sie mit `short_citation` nur nach ausdrücklicher Bestätigung ein, nie unbeaufsichtigt, kein Überschreiben ohne ausdrücklichen Wunsch | 1, 3, 4.1, 7.7, 9.6 |
| 29 | Feldreihenfolge | Neue Felder an ihrer Stelle nach 4.1 statt am Ende, `update_frontmatter` in Schema-Reihenfolge, einfache Listen ohne Anführungszeichen | 4.1, 7.2 |
| 30 | Dateinamen aus Chats | `<slug>_YYYY-MM-DD.md`, Suffix bei Namensgleichheit vor dem Datum | 4.1, 7.2 |
| 31 | Große Dokumente | `read` mit `section`, `offset`/`max_chars`, `content: false`; über 40.000 Zeichen Inhalt nur auf Anforderung | 7.3, 10 |
| 32 | Belege | Strukturzeilen und belegte Tabellen ohne Lint-Warnung, Warnung bei Belegen auf leere Abschnitte, Anheben von `v:` bei unverändertem Abschnitt im Abschluss des Laufs, Wikilinks im Text werden beim Verschieben mit korrigiert | 4.2, 4.8, 5.2, 6.4, 8 |
| 33 | `CLAUDE.md` in Git | Änderungen des Nutzers erfasst `pkm versions` als Commit mit `PKM-Source: user` | 3, 8, 12 |
| 34 | Lange Dateinamen | Nur der Slug wird gekürzt, nie Datum oder Suffix | 4.1, 14 |
| 35 | Bilder | PNG und SVG, SVG bevorzugt, bis 24 KB eingebettet (PNG Base64, SVG URL-kodiert), sonst Datei. `scratch/` immer eingebettet. Bestehende Base64-PNG unverändert. Bilder gehören zum Dokument. `add_image`, `read_image`, Importordner. Kein Befehl zum nachträglichen Einbetten bestehender Anhänge | 4.9, 7, 8, 9.1, 10 |
| 36 | Windows als PKM-Rechner | Gleichwertig zum Mac, genau ein PKM-Rechner je Vault. Git von git-scm.com, Standardordner `%APPDATA%\pkm`, Datensicherung des Git-Verzeichnisses ausdrücklich einrichten | 5.5, 7.1, 7.6, 12, 13 |
| 37 | Importordner und JPEG | Importordner `pkm_img_import/` im Vault (nicht in Git, von der Pflege ausgenommen), Ordner außerhalb weiter möglich. JPEG wird übernommen, Metadaten entfernt, Ausrichtung erhalten | 3, 4.9, 7.1, 8, 10, 12 |
| 38 | Data-URIs bei der Übernahme | Jede Bild-Data-URI wird geprüft (Werkzeuge, Pflegelauf, Lint, Wiki-Seiten). Abweichungen werden mit Befund und Vorschlag gemeldet und **nur nach Rückfrage** korrigiert (`fix_images: true`, Tool `fix_images`, `pkm fix-images`), nie unbeaufsichtigt. Nur die Bildschreibweise ändert sich, abgeleitete Namen bleiben, Belege werden angehoben. Bestehende Base64-PNG: nur Schreibweise, Bytes gleich, kein Name | 3, 4.7, 4.9, 5.4, 7.2, 7.3, 7.7, 8, 9.1, 9.2, 9.7, 10, 14 |
| 39 | Cloud-Speicher allgemein | Jeder Dienst, der einen normalen lokalen Ordner synchronisiert. Vault vollständig lokal (keine Platzhalter), Git-Verzeichnis und Suchindex außerhalb jedes Cloud-Ordners. Konfliktkopien aller bekannten Dienste werden am Namen oder als Kopie mit gleicher ID neben dem Original erkannt und nicht verarbeitet | 5.3, 5.5, 7.1, 8, 12 |
| 40 | Git optional, einfachere Installation | Fehlt Git, läuft das PKM ohne Versionsverwaltung (IDs und Versionsnummern ja, Commits, Verlauf und Wiederherstellen nein); nachrüsten durch Git installieren und `pkm setup` erneut ausführen. Installation mit Installer und `pkm setup`, Konfiguration in `config.toml`, Obsidian-Einstellungen durch `pkm init`, Skills im Paket | 5.4, 7.1, 7.6, 8, 13, 15.1 |
| 41 | Sprache von Dokumenten und Wiki | Der Nutzer wählt bei der Einrichtung, ob im Chat erzeugte Dokumente und das Wiki hauptsächlich englisch oder deutsch sind (`PKM_LANGUAGE`). Beide Server geben die Sprache und die Abschnittsnamen in ihren Anweisungen weiter; bestehende Dokumente und Seiten behalten ihre Sprache. Werkzeuge erkennen beide Varianten, erzeugte Dateien bleiben englisch | 4.1, 4.2, 7.1, 9, 10, 15.1 |
| 42 | Vorhandene Konfiguration übernehmen | `pkm setup` zeigt Einstellungen aus Umgebung, Claude Desktop (`env`) und `config.toml` und übernimmt sie nach Bestätigung nach `config.toml`. So bleiben bei einer Aktualisierung (auch von einer Installation vor `pkm setup`) Git-Verzeichnis, Suchindex und übrige Werte erhalten | 7.1, 7.6, 15.1 |
| 43 | Englische Namen für den Pflege-Server | `pkm-maintenance` / `pkm-maintenance-mcp` statt `pkm-pflege` / `pkm-pflege-mcp`, Projekt „PKM Maintenance“. Der alte Programmname bleibt als Alias, `pkm setup` ersetzt den alten Eintrag in Claude Desktop nach Rückfrage | 7.6, 7.7, 11, 15.1 |
| 44 | `CLAUDE.md` aktualisieren | `pkm init` überschreibt `CLAUDE.md` nie. `pkm setup` bietet bei Abweichung von der Vorlage an, sie zu ersetzen (Sicherung außerhalb des Vaults, Commit) oder die Vorlage als `CLAUDE.md.new` daneben zu legen; eigene Änderungen gehen so nicht verloren | 15.1 |

### Noch offen

Keine.
