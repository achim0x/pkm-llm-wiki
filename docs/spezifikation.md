# PKM mit LLM-Wiki – Implementierungsspezifikation

**Version:** 0.18 (Entwurf zum Review) · **Stand:** 01.11.2026

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
- **einen Ablagebereich** hat, in dem Dokumente manuell oder per MCP landen und in Obsidian frei sortiert werden,
- daraus von einem LLM-Agenten ein **kompiliertes Wiki** aufbauen lässt (Zusammenfassungen, Themen, Querverweise) mit **Belegen auf die Originaldokumente**,
- aus **beliebigen Claude-Desktop-Chats** erlaubt:
  1. Ergebnisse einer Diskussion als neues Dokument abzulegen,
  2. bestehende Dokumente zu aktualisieren, etwa wenn eine Diskussion fortgeführt wird, mit Versionsnummer und vollständigem Verlauf in Git,
  3. das kompilierte Wissen abzufragen und auf Nachfrage die Originale zu nennen,
- die Wiki-Pflege in einem **eigenen Claude-Desktop-Projekt** mit direktem Ordnerzugriff erledigt.

### Leitprinzipien

1. **Zwei Bereiche, zwei Besitzer:** `documents/` gehört dem Nutzer (Pflege per Hand oder per MCP auf seine Anweisung). `wiki/` gehört dem Pflege-Agenten.
2. **Schreibwege aus Chats sind technisch begrenzt:** Der MCP-Server legt neue Dateien nur in `documents/_inbox/` an. Er ändert nur bestehende Markdown-Dateien in `documents/`. Er löscht und verschiebt nichts. Jede Änderung ergibt eine neue Version und einen Git-Commit, ist also jederzeit umkehrbar. `wiki/` ist aus Chats nur lesbar. Ausnahme ist der Bereich `scratch/` für kurzlebige Notizen: Dort darf der Server anlegen und ändern, ohne Version und ohne Commit (3). Diese Grenzen stehen im Code.
3. **Dokumente bleiben aufgeräumt:** Ein Dokument zeigt immer den aktuellen Stand. Die Geschichte liegt in Git, erreichbar über die Versionsnummer.
4. **Der Pflege-Agent fasst Dokumente nicht an**, mit zwei Ausnahmen: Er trägt `id` nach und erhöht `version` bei Änderungen, die von Hand gemacht wurden.
5. **Rückverfolgbarkeit:** Jede Aussage im Wiki verweist auf das Originaldokument (Abschnitt bzw. Seite, Zitat, ID, Version). Wiki-Seiten untereinander gelten nicht als Beleg.
6. **Identität statt Pfad:** Dokumente werden über ihre ID gefunden. Pfade dürfen sich jederzeit ändern.
7. **Alles ist Markdown plus Git.** Der Suchindex ist ein Wegwerf-Cache.
8. **Keine LLM-Aufrufe im Server:** Der MCP-Server ist deterministisch. Die Intelligenz liegt beim Agenten.
9. **Kurzlebiges bleibt draußen:** Notizen und Todo-Listen in `scratch/` werden nie ins Wiki übernommen und nie versioniert. Soll etwas daraus dauerhaft werden, wird es nach `documents/` verschoben.

---

## 2. Architektur im Überblick

```
┌──────────────────────────────┐        ┌───────────────────────────────┐
│  Beliebiger Claude-Chat      │        │  Claude-Projekt „PKM-Pflege“  │
│  (+ Skill pkm-access)        │        │  (+ Skill pkm-wiki,           │
│                              │        │   Ordner verbunden)           │
└──────────┬───────────────────┘        └───────────────┬───────────────┘
           │ MCP (stdio, lokal)                         │ Dateizugriff + Shell
           ▼                                            ▼
┌──────────────────────────────┐        ┌───────────────────────────────┐
│  pkm-mcp (Python)            │        │  pkm CLI (gleiches Paket)     │
│  schreiben (nur documents/,  │        │  ids, versions, pending,      │
│   je Änderung 1 Git-Commit): │        │  …-citations, index, status,  │
│   create_document            │        │  lint, history, restore, …    │
│   rewrite_document           │        └───────────────┬───────────────┘
│   append_to_document         │                        │
│   edit_document              │                        │
│   update_frontmatter         │                        │
│   restore_document           │                        │
│  lesen: search, read,        │                        │
│   history, show_citations,   │                        │
│   read_index,                │                        │
│   list_unprocessed           │                        │
└──────────┬───────────────────┘                        │
           ▼                                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Vault  <PKM_ROOT>  (Nextcloud-Ordner, in Obsidian geöffnet)         │
│  documents/  (inkl. _inbox/)     wiki/     CLAUDE.md     .pkm/       │
└──────────────────────────────────────────────────────────────────────┘
```

| Komponente | Art | Zweck |
|---|---|---|
| **Vault** | Ordner mit Git-Repo (Pflicht) | Einzige Datenquelle (Single Source of Truth), Versionsgeschichte |
| **pkm-mcp** | lokaler MCP-Server (Python, stdio) | Ablegen, Aktualisieren und Versionsverlauf von Dokumenten, Abfragen des Wikis, Belege aus jedem Chat |
| **pkm CLI** | Kommandozeile, gleiches Python-Paket | Deterministische Helfer für die Pflege |
| **Skill `pkm-wiki`** | Claude-Skill | Regeln und Abläufe der Wiki-Pflege |
| **Skill `pkm-access`** | Claude-Skill (schlank) | Wann und wie Chats die MCP-Tools nutzen |
| **Projekt „PKM-Pflege“** | Projekt in Claude Desktop | Ort, an dem die Pflege läuft (Ordner verbunden) |
| **Geplante Aufgabe** (optional) | z. B. täglich | Neue und geänderte Dokumente automatisch verarbeiten |

---

## 3. Ordnerstruktur und Besitzrechte

```
<PKM_ROOT>/
├── documents/                # Ablage des Nutzers, frei sortierbar
│   ├── _inbox/             # Standardziel für pkm-mcp und den Web Clipper
│   ├── _attachments/            # Bilder aus Web-Clips (Obsidian-Anhangordner)
│   ├── haus/
│   │   ├── zisterne.md
│   │   └── datenblatt-tank.pdf
│   └── …                     # beliebige Unterordner
├── scratch/                  # kurzlebige Notizen, Todo-Listen: nicht in Git, nie ins Wiki
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

Außerhalb der Nextcloud, nur auf dem Mac:
~/Library/Application Support/pkm/
├── git/                      # Git-Verzeichnis des Vaults (PKM_GIT_DIR)
└── index.db                  # Suchindex, Cache (PKM_CACHE_DIR)
```

| Bereich | Nutzer (Obsidian) | pkm-mcp (Chat, auf Anweisung des Nutzers) | Pflege-Agent |
|---|---|---|---|
| `documents/_inbox/` | alles | neu anlegen, ändern | lesen, `id`/`version` setzen |
| `documents/**` (übrige) | alles | ändern (nur `.md`) | lesen, `id`/`version` setzen |
| `wiki/` | lesen | **nur lesen** | lesen und schreiben |
| `CLAUDE.md` | lesen und schreiben | – | Änderungen nur nach Zustimmung |
| `scratch/**` | alles | neu anlegen, ändern (nur `.md`), ohne Version und Commit | **ignoriert** |
| `.pkm/` | – | `mcp.log` (nur anhängen) | `state.json` |

Ein Dokument ist „unverarbeitet“, solange seine aktuelle Version nicht in `state.json` als verarbeitet steht. Wo es innerhalb von `documents/` liegt, ist dafür egal.

**Bereich `scratch/`** (kurzlebige Notizen und Todo-Listen):
- **Nie im Wiki:** Ingest, `pending`, Belege, Index und Status beachten `scratch/` nicht. Auch Lint ignoriert den Bereich vollständig, prüft aber weiterhin im Wiki, dass kein Beleg auf `scratch/` zeigt.
- **Nicht in Git:** `scratch/` steht in `.gitignore` und wird nur über Nextcloud synchronisiert. Es gibt keine Versionsnummer, keinen Commit und keinen Verlauf. Als Rückfallebene für versehentliche Änderungen dienen die Dateiversionen der Nextcloud.
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
kind: standard
id: d-20261101-0915-m3qa
version: 1
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
| `context` | Text | nein | Chat | Anlass, z. B. Chat-Titel |
| `tags` | Tags (Liste) | nein | Chat bzw. Nutzer | Schlagwörter, Kleinbuchstaben mit Bindestrich, ohne Leerzeichen. Obsidian zeigt nur dieses Feld in Tag-Ansicht, Tag-Suche und Graph an |
| `related` | Liste (Links) | nein | Chat bzw. Nutzer | Verwandte Dokumente |
| `kind` | Text | nein | Umwandlung bzw. Chat | Art des Dokuments: `note` (Standardwert, wenn das Feld fehlt), `standard` (Normen und Standards), `regulation` (Gesetze und Verordnungen) oder `correction` (Korrekturwunsch für das Wiki, 9.1) |

**Regeln:**

- **Reihenfolge:** Die sechs Felder der Umwandlung (`title` bis `toolchain_markdown`) stehen in dieser Reihenfolge am Anfang. Die übrigen Felder folgen. Werkzeuge ergänzen fehlende Felder **am Ende** des Frontmatters (zeilengenau), damit bestehende Dateien ihre Reihenfolge behalten.
- **Bereits umgewandelte Dokumente** (z. B. Normen mit genau den sechs Feldern der Umwandlung) sind gültig, sofern ihr YAML gültig ist (siehe Anführungszeichen). Beim ersten Pflegelauf kommen nur `id` und `version: 1` hinzu.
- **Feldnamen enthalten keine Leerzeichen.** Ältere umgewandelte Dokumente mit dem Feld `short_citation` (mit Leerzeichen) meldet Lint als Hinweis. `pkm fix-frontmatter` benennt es in `short_citation` um, aber nur auf ausdrückliche Anweisung (8). Bis dahin lesen die Werkzeuge beide Schreibweisen.
- **Datumsfelder mit Uhrzeit, ohne Zeitzone:** `date_markdown` und `date_updated` haben das Format `YYYY-MM-DDTHH:MM:SS` (Sekunden, keine Bruchteile) in Ortszeit (`PKM_TZ`, Standard `Europe/Berlin`). Das ist das Format, das Obsidian als „Datum & Uhrzeit“ erkennt (sortierbar, Auswahl im Kalender). Eine Zeitzonen-Angabe (`+01:00`, `Z`) wird nicht geschrieben, weil Obsidian sie in Datumsfeldern nicht unterstützt. Die Zeitzone ergibt sich aus der Konfiguration. Ältere Werte nur mit Datum (`YYYY-MM-DD`, z. B. aus früheren Umwandlungen) bleiben gültig und werden nicht ergänzt. `date_markdown` ändert sich ohnehin nie. Gilt auch für `date_updated` auf Wiki-Seiten (4.2), weil Obsidian den Typ vault-weit pro Feldname festlegt.
- **Vault-weite Typen:** Obsidian legt den Typ einer Property vault-weit pro Namen fest. Jedes Feld hat deshalb überall den Typ aus der Tabelle. `date_document` bleibt Text, weil es wie gedruckt übernommen wird.
- **Links in Properties** (`related`, `sources`) stehen immer in Anführungszeichen.
- **Nicht verwendet:** `source` bleibt frei für die Quell-URL, die der Obsidian Web Clipper schreibt (13). Die Werkzeuge werten es nicht aus, lassen es aber unverändert. Für die Herkunft dient `toolchain_markdown`.
- **Anführungszeichen bei `: `:** Enthält ein Wert die Zeichenfolge Doppelpunkt plus Leerzeichen (häufig in Normtiteln, z. B. „Teil 4-6: Prüf- und Messverfahren“) oder beginnt er mit einem YAML-Sonderzeichen (`- [ ] { } # & * ! | > ' " % @` bzw. `` ` ``), muss er in doppelten Anführungszeichen stehen. Sonst ist das YAML ungültig, und Obsidian sowie die Werkzeuge können das Frontmatter nicht lesen (`invalid_frontmatter`, 4.8). Werkzeuge setzen die Anführungszeichen beim Schreiben selbst. Bestehende Dateien meldet Lint als Fehler. `pkm fix-frontmatter` behebt das, aber **nur auf ausdrückliche Anweisung** des Nutzers (8).
- **Werte von `kind`:**

  | Wert | Verwendung | Wirkung auf die Pflege |
  |---|---|---|
  | `note` | Diskussionsergebnisse, Notizen, Web-Clips, sonstige Dokumente. Gilt, wenn `kind` fehlt | normal verarbeitet |
  | `standard` | Normen und Standards (z. B. EN-, IEC-, ISO-Normen, Werknormen) | normal verarbeitet |
  | `regulation` | Gesetze und Verordnungen (z. B. Gesetze, EU-Verordnungen, Richtlinien) | normal verarbeitet |
  | `correction` | Korrekturwunsch für das Wiki mit `related` auf die betroffene Seite | Vorrang vor älteren Quellen (9.1) |

  `standard` und `regulation` setzt die Umwandlung. Für bereits umgewandelte Dokumente ohne `kind` (erkennbar an `status_markdown`, `short_citation` oder `date_document`) gibt Lint einen Hinweis. Ergänzt wird `kind` vom Nutzer, nicht von den Werkzeugen, weil sie `standard` und `regulation` nicht sicher unterscheiden können. Andere Werte meldet Lint als Fehler.
- **Pflicht** für die Verarbeitung sind `id` und `version`. Bei Ablage per MCP setzt der Server `date_markdown`, `toolchain_markdown`, `id` und `version: 1`. Bei eigenen Dokumenten trägt der Agent nur `id` und `version` nach (5.3). Fehlen `date_markdown` oder `toolchain_markdown`, meldet Lint einen Hinweis, ergänzt sie aber nicht. `status_markdown` wird nicht geprüft.
- **ID-Format:** `d-YYYYMMDD-HHMM-xxxx`. Das sind Zeitpunkt der Vergabe und vier Zufallszeichen aus `0-9a-z` ohne `0 1 l o`. Kollisionen prüft der Server gegen den Index.
- **Geschützte Felder:** `id`, `version`, `date_markdown` und `date_updated` werden ausschließlich von Server bzw. CLI gesetzt und sind über `update_frontmatter` nicht änderbar. `status_markdown` wird unverändert übernommen und ist über `update_frontmatter` ebenfalls nicht änderbar. Geändert wird es nur außerhalb der Werkzeuge, z. B. in Obsidian oder bei einer erneuten Umwandlung.
- **Frontmatter-Erhalt:** Server und CLI setzen Felder **zeilengenau**: Nur die betreffende Zeile wird ersetzt oder ergänzt, Reihenfolge, Formatierung und Kommentare der übrigen Zeilen bleiben erhalten. Nur `update_frontmatter` schreibt das Frontmatter vollständig neu (Feldreihenfolge bleibt, Umlaute bleiben lesbar). Kommentare im Frontmatter gehen dabei verloren.

**Gliederung von Chat-Ergebnissen** (Empfehlung des Skills, nicht erzwungen):

```markdown
## Ergebnis
## Entscheidungen
## Offene Punkte
## Kontext / Begründung
```

Bei einer fortgeführten Diskussion werden diese Abschnitte **aktualisiert**, nicht ergänzt (Abschnitt 6). Das Dokument zeigt immer den aktuellen Stand.

**Dateinamen** in `_inbox/`: `YYYY-MM-DD_<slug>.md`. Beim Einsortieren darfst du sie frei umbenennen.

**Nicht-Markdown-Dateien** (PDF, Bilder) haben kein Frontmatter und keine Versionsnummer. Sie werden über ihren Inhalts-Hash identifiziert. Eine neue Fassung eines PDFs gilt als neues Dokument (Abschnitt 5).

### 4.2 Wiki-Seite mit Belegen

Dateiname: Kleinbuchstaben, Bindestriche, Umlaute ausgeschrieben (`regenwasser-ertrag.md`).

```markdown
---
type: topic            # topic | entity | summary | synthesis
title: Regenwasser-Ertrag
aliases: [Regenertrag, L/mm]
tags: [zisterne, wasser]
sources:              # aus den Belegen erzeugt (pkm sync-citations), als Wikilinks
  - "[[documents/haus/zisterne]]"
  - "[[documents/haus/2026-10-31_zisterne-ueberlaufsensor]]"
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
[^b2]: [[documents/haus/2026-10-31_zisterne-ueberlaufsensor#Entscheidungen]] · „Schwimmerschalter statt Ultraschall“ · id:d-20261031-2340-k7q2 · v:3 · sha:8b21e0
[^b3]: [[documents/haus/2026-10-31_zisterne-ueberlaufsensor#Entscheidungen]] · „Ultraschallsensor am Deckel“ · id:d-20261031-2340-k7q2 · v:2 · sha:a1b2c3
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
| `sha:` | ja | Die ersten 6 Zeichen des Abschnitts-Hashes (Markdown) bzw. des Datei-Hashes (PDF/Bild) in dieser Version, nach 4.8 |

**Regeln:**
- Jede Sachaussage in „Inhalt“ und „Widersprüche“ endet mit mindestens einer Fußnote. Fasst ein Absatz mehrere Aussagen aus derselben Stelle zusammen, genügt eine Fußnote am Absatzende.
- Fußnoten zeigen immer auf Dokumente in `documents/`, nie auf Wiki-Seiten.
- **Überholte Aussagen** behalten ihren Beleg auf die *alte* Version (`v:2` im Beispiel). Der Beleg bleibt gültig, weil Git den damaligen Wortlaut hält.
- Eigene Schlussfolgerungen des Agenten werden gekennzeichnet: „(abgeleitet aus [^b1] und [^b4])“.
- Seiten unter `wiki/summaries/` fassen genau ein Dokument in seiner aktuellen Version zusammen und belegen ihre Aussagen genauso.
- `sources` im Frontmatter wird nicht von Hand gepflegt, sondern von `pkm sync-citations` erzeugt.
- `confidence: low`, wenn Quellen sich widersprechen oder nur eine unsichere Quelle vorliegt.
- Überschriften („Inhalt“, „Belege“ …) und die Markierung „Kurzfassung“ sind Inhalt und bleiben deutsch. Die Werkzeuge hängen nicht davon ab: Belege werden am Fußnotenformat erkannt, die Kurzfassung als erstes Zitat (`>`) nach dem Frontmatter.

### 4.3 `wiki/index.md`

Wird von `pkm index` erzeugt. Gruppiert nach `type`, eine Zeile je Seite:

```markdown
## Themen
- [[wiki/topics/regenwasser-ertrag]] – Kurzfassung … _(3 Quellen, 2026-11-02)_
```

### 4.4 `wiki/_status.md`

Wird von `pkm status` nach jedem Pflegelauf erzeugt:

```markdown
## Noch nicht verarbeitet (2)
- [[documents/_inbox/2026-11-02_bewaesserung-zeitplan]] – neu (v1)
- [[documents/haus/2026-10-31_zisterne-ueberlaufsensor]] – v2 → v3, geändert: „Entscheidungen“, „Offene Punkte“

## Noch im Eingang, bereits verarbeitet (1)
- [[documents/_inbox/2026-10-30_regenmesser]] → Vorschlag: documents/haus/

## Probleme (0)
```

### 4.5 `wiki/log.md`

Nur anhängen:

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
      "path": "documents/haus/2026-10-31_zisterne-ueberlaufsensor.md",
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
| Commit-Zeilen | `PKM-Id`, `PKM-Version`, `PKM-Source` (`chat` \| `user` \| `agent`) |
| `state.json` | `documents`, `path`, `processed_version`, `file_hash`, `body_hash`, `meta_hash`, `sections`, `processed_at`, `wiki_pages` |
| Abschnitte | Schlüssel nach 4.8, reserviert `_preamble`, Duplikate `Text#2` |
| `pending`-Kategorien | `new`, `changed`, `meta_changed`, `moved`, `deleted`; je Abschnitt `added`, `removed`, `changed`, `renamed` |
| Bereiche (`area`, `scope`) | `documents`, `scratch`; zusätzlich `wiki` und `all` (= `wiki` + `documents`) bei `search` |
| MCP-Tools | `create_document`, `rewrite_document`, `append_to_document`, `edit_document`, `update_frontmatter`, `restore_document`, `search`, `read`, `history`, `show_citations`, `read_index`, `list_unprocessed` |
| Statuswerte | `ok`, `moved`, `newer_version`, `missing`, `created`, `changed`, `conflict`, `ambiguous`, `not_found`, `large_shortening`, `invalid_frontmatter`, `invalid_encoding`, `not_versioned` |
| CLI | `pkm init`, `ids`, `versions`, `pending`, `history`, `show`, `fix-citations`, `sync-citations`, `sha`, `mark`, `index`, `status`, `lint`, `restore`, `reindex`, `commit-wiki`, `doctor` |
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
| **Abschnitts-Hash** (`sections.<schlüssel>` in `state.json`, Präfix als `sha:` im Beleg) | der Abschnitt **ohne** seine Überschriftenzeile, normalisiert: jede Zeile rechts von Leerraum befreit, führende und abschließende Leerzeilen entfernt, Folgen von Leerzeilen zu einer einzigen zusammengefasst, Zeilen mit LF verbunden | Inhaltliche Änderungen je Abschnitt. Reine Leerraum-Änderungen lösen nichts aus. Ein leerer Abschnitt hat den Hash des leeren Strings |
| **`body_hash`** | die Folge aller Abschnitte in Dokumentreihenfolge, je Abschnitt eine Zeile `<schlüssel>\t<abschnitts-hash>\n` | Schneller Test, ob sich am Inhalt überhaupt etwas geändert hat, Reihenfolge inklusive |
| **`meta_hash`** | kanonisches JSON (sortierte Schlüssel, UTF-8, ohne Leerraum) der Felder `title`, `short_citation`, `date_document`, `tags`, `related`, `kind`. Fehlende Felder fehlen auch im JSON. Werte gehen als Zeichenketten in ihrer Schreibweise im Frontmatter ein (ein Datum also als `2026-10-25`, nicht als Datumsobjekt), Listen als Listen solcher Zeichenketten | Inhaltlich relevante Metadaten. `id`, `version`, `status_markdown`, `date_markdown`, `date_updated`, `toolchain_markdown` und `context` sind bewusst ausgenommen. Eine Statusänderung von `draft` löst also keine Neuverarbeitung aus |
| **Datei-Hash binär** | die Rohbytes ohne Normalisierung | PDFs und Bilder |

#### Was daraus folgt

`pkm pending` vergleicht je Dokument mit `state.json`:
- `body_hash` und `meta_hash` unverändert: **nichts zu tun**, auch wenn sich `file_hash` geändert hat, etwa nur durch `date_updated`, `version` oder `status_markdown`.
- Nur `meta_hash` geändert: **`meta_changed`**. Dann werden nur Zusammenfassungsseite und Index angepasst.
- `body_hash` geändert: **`changed`**, mit dem Abschnittsvergleich:
  - Schlüssel neu: `added`. Schlüssel weg: `removed`. Gleicher Schlüssel, anderer Hash: `changed`.
  - Ein `removed` und ein `added` mit **gleichem Hash** werden zu **`renamed`** (alter → neuer Schlüssel) zusammengefasst. `pkm fix-citations` passt die Anker in den Belegen an. So werden auch Verschiebungen in der Duplikat-Nummerierung erkannt (`Notizen#2` → `Notizen`).
  - Nur die Reihenfolge geändert, alle Abschnitts-Hashes gleich: `changed` ohne betroffene Abschnitte. Es wird nur der Stand vermerkt, eine inhaltliche Verarbeitung findet nicht statt.

`edit_document` sucht `old` im **normalisierten Body** (Schritt 1). Auch `old` und `new` werden vorher normalisiert (LF, NFC), damit CRLF oder abweichende Unicode-Formen aus dem Chat nicht zu `not_found` führen. Die Kürzungsprüfung von `rewrite_document` (`large_shortening`) zählt Zeichen des normalisierten Bodys und vergleicht Abschnittsschlüssel nach Schritt 3.

---

## 5. Identität, Versionen und Git

### 5.1 Zuordnung beim Umsortieren

Drei Mechanismen greifen nacheinander. Jeder deckt die Fälle ab, die der vorherige nicht abdeckt.

| # | Mechanismus | Deckt ab | Grenze |
|---|---|---|---|
| 1 | **Obsidian aktualisiert Links automatisch** beim Verschieben oder Umbenennen | Der Normalfall: Du sortierst in Obsidian. Belege und `sources` zeigen sofort auf den neuen Ort | Verschieben außerhalb von Obsidian |
| 2 | **Dokument-ID** im Frontmatter, in jedem Beleg mitgeführt | Markdown-Dateien, die außerhalb von Obsidian verschoben oder zwischen zwei Läufen verschoben *und* bearbeitet wurden | Nur Markdown |
| 3 | **Inhalts-Hash** in `state.json` | PDFs und Bilder, auch bei Umbenennung außerhalb von Obsidian | Eine neue Fassung eines PDFs gilt als neues Dokument |

### 5.2 Auflösung eines Belegs

(in `show_citations` und `pkm fix-citations`)
1. Der Link-Pfad existiert und die ID stimmt (Markdown) bzw. der Hash stimmt (PDF/Bild): Das Dokument ist gefunden.
2. Sonst bei Markdown: Die ID im Index nachschlagen. Gefunden heißt **verschoben**.
3. Sonst bei PDF/Bild: Den Hash im Dateibestand nachschlagen. Gefunden heißt ebenfalls **verschoben**.
4. Sonst: **fehlt**.

Ist das Dokument gefunden, wird der Inhalt geprüft. Ist die Version im Beleg gleich der aktuellen Version, ist der Status `ok`. Ist sie älter und der Abschnitts-Hash unverändert, ist der Status ebenfalls `ok`. Ist sie älter und der Abschnitt geändert, ist der Status `newer_version` (Abschnitt 7.3).

### 5.3 Vergabe von ID und Version

- `create_document` setzt `id` und `version: 1` sofort.
- Für alle anderen Markdown-Dateien ohne ID schreibt `pkm ids` zu Beginn jedes Pflegelaufs `id` und `version: 1` ins Frontmatter. Fehlt ein Frontmatter, wird eines angelegt. Der übrige Inhalt bleibt byte-genau erhalten.
- **Doppelte IDs** entstehen z. B. durch Kopieren einer Datei. Lint meldet sie. Der Agent gibt nach Rückfrage der jüngeren Kopie eine neue ID und setzt deren Version auf 1.
- **Nextcloud-Konfliktkopien** (Dateiname enthält „conflicted copy“ bzw. „Konflikt“) tragen ebenfalls die ID des Originals. Sie werden **nicht** als neues Dokument behandelt. Der Agent verarbeitet sie nicht, sondern meldet sie, und der Nutzer führt die Fassungen in Obsidian zusammen (5.5).

### 5.4 Versionen und Commits

**Jede Version ist genau ein Git-Commit**, der nur die eine Datei enthält. Die Commit-Nachricht hat ein festes Format mit maschinenlesbaren Zeilen am Ende:

```
doc: Zisterne – Überlaufsensor v3

Sensor: Schwimmerschalter statt Ultraschall; Montageort geklärt

PKM-Id: d-20261031-2340-k7q2
PKM-Version: 3
PKM-Source: chat
```

`PKM-Source` ist `chat` (MCP), `user` (Änderung von Hand) oder `agent` (`pkm ids`, Duplikat-Auflösung). Über `git log --grep "PKM-Id: d-…"` findet man alle Versionen eines Dokuments, **unabhängig davon, wo es gerade liegt**.

**Wer erhöht die Version?**

| Änderung durch | Zeitpunkt | Ablauf |
|---|---|---|
| MCP (Chat) | sofort bei jeder Änderung | Der Server erhöht `version`, setzt `date_updated`, schreibt die Datei und committet mit `--only` genau diese Datei (mit `--git-dir`/`--work-tree`, 5.5). Andere offene Änderungen im Vault bleiben unberührt |
| Nutzer (Obsidian, Dateimanager) | nachgezogen | (a) Ändert danach der MCP-Server dieselbe Datei, committet er **vorher** den Stand des Nutzers als eigene Version (`PKM-Source: user`). (b) Spätestens zu Beginn des nächsten Pflegelaufs zieht `pkm versions` alle von Hand geänderten Dokumente nach, je Dokument eine Version |
| Agent | beim Pflegelauf | Nur `pkm ids` und die Duplikat-Auflösung, je Dokument ein Commit |

Mehrere Änderungen von Hand zwischen zwei Commits werden also zu **einer** Version zusammengefasst. Das ist gewollt, weil Obsidian Zwischenstände beim Tippen speichert.

**Voraussetzung:** Ein Git-Repo mit getrenntem Git-Verzeichnis (5.5) und gesetztem `user.name`/`user.email`. Fehlt Git, verweigert der Server alle schreibenden Tools mit einer klaren Fehlermeldung. Die lesenden Tools funktionieren weiter.

### 5.5 Nextcloud, Mac und Windows

| Rechner | Obsidian | MCP-Server, Pflege-Agent, Git |
|---|---|---|
| Mac | lesen, bearbeiten | **ja** (einziger Ort) |
| Windows | lesen, bearbeiten | nein |

**Git-Verzeichnis außerhalb der Nextcloud.** Ein `.git`-Ordner im synchronisierten Vault ist riskant. Nextcloud überträgt die vielen kleinen Git-Dateien einzeln und nicht atomar. Halbe Stände, Sperrdateien oder Konfliktkopien können das Repo beschädigen. Deshalb arbeitet Git mit getrenntem Verzeichnis:

```
git --git-dir="$PKM_GIT_DIR" --work-tree="$PKM_ROOT" …
```

Im Vault gibt es kein `.git`, und der Windows-Rechner sieht davon nichts. Aus demselben Grund liegt der Suchindex (SQLite) in `PKM_CACHE_DIR`. SQLite-Dateien eignen sich nicht für Dateisynchronisation. `PKM_CACHE_DIR` darf deshalb weder im Vault noch sonst im Nextcloud-Ordner liegen (7.1). Im Vault liegen nur zwei Dateien unter `.pkm/`: `state.json` ist klein, wird nur auf dem Mac geschrieben und ist so in der Versionsgeschichte enthalten. `mcp.log` ist eine reine Textdatei, an die nur der Mac anhängt. Sie wird mit synchronisiert, steht aber nicht in Git.

**Sync-Verzögerung und Konflikte**
- Änderungen vom Windows-Rechner erreichen den Mac erst nach dem Sync. Sobald sie angekommen sind, verhindert der Hash-Schutz, dass ein Chat einen veralteten Stand überschreibt.
- Schreibt ein Chat, *während* eine Windows-Änderung derselben Datei noch unterwegs ist, legt Nextcloud eine Konfliktkopie an. `pkm lint` erkennt sie am Dateinamen und an der doppelten ID und meldet sie (5.3). Der Nutzer führt die Fassungen in Obsidian zusammen.
- Empfehlung: dasselbe Dokument nicht gleichzeitig auf Windows bearbeiten und per Chat ändern lassen.

**Plattformfeste Dateien**
- Vom Server erzeugte Dateinamen sind auf allen Systemen gültig: keine `\ / : * ? " < > |`, keine reservierten Windows-Namen (`CON`, `NUL`, `COM1` …), kein Punkt oder Leerzeichen am Ende, höchstens 120 Zeichen.
- Pfade werden intern in Unicode-NFC verglichen und gespeichert, weil macOS Dateinamen mit Umlauten teils als NFD liefert.
- Hashes werden über normalisierten Text berechnet (4.8: UTF-8 ohne BOM, LF, NFC). Eine Datei, die auf Windows mit CRLF gespeichert wird, gilt dadurch nicht als geändert.
- Zwei Dateien, die sich nur in Groß- und Kleinschreibung unterscheiden, meldet Lint als Fehler, weil sie unter macOS und Windows nicht unterscheidbar sind.

**Chats und MCP:** Der MCP-Server läuft nur auf dem Mac und ist erreichbar, solange dort die Claude-Desktop-App läuft. Ein zweiter Server auf Windows ist bewusst nicht vorgesehen, sonst würden zwei Rechner in dieselbe Versionsgeschichte schreiben.

**Nextcloud-Einstellungen:** Es sind keine Ausnahmen nötig, weil Git und Cache außerhalb liegen. Optional lassen sich `.obsidian/workspace*.json` ausschließen, da diese Dateien geräteabhängig sind.

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
2. Der Chat erstellt die **neue Fassung** des Dokuments:
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

1. `pkm pending` meldet das Dokument mit `processed_version` → `version` und den geänderten Abschnitten.
2. Der Agent verarbeitet nur diese Abschnitte und vergleicht dazu die verarbeitete mit der aktuellen Version (`pkm history --diff`).
3. Betroffene Wiki-Aussagen werden auf den neuen Stand gebracht und mit Belegen auf die **neue Version** versehen.
4. Wo der frühere Stand für die Nachvollziehbarkeit wichtig ist, etwa bei einer geänderten Entscheidung, bleibt er als kurze Zeile „Bis Version n: …“ mit Beleg auf die **alte Version** stehen. Andernfalls wird er nur im Log vermerkt.
5. Belege auf unveränderte Abschnitte bleiben gültig. Ihre Version wird beim nächsten Durchgang auf die aktuelle angehoben.

---

## 7. MCP-Server `pkm-mcp`

### 7.1 Technik

- Python ≥ 3.11, offizielles `mcp`-SDK (FastMCP), Transport stdio
- Abhängigkeiten: `mcp`, `pyyaml`. Sonst Standardbibliothek (`sqlite3` mit FTS5, `subprocess` für `git`)
- Plattform: **macOS**, denn der Server läuft nur auf dem Mac (5.5). Voraussetzung ist `git` (Xcode Command Line Tools oder Homebrew). Die Standardpfade richten sich nach dem Betriebssystem; alle Pfade sind per Umgebungsvariable überschreibbar, damit die automatischen Tests auch unter Linux laufen
- Konfiguration über Umgebungsvariablen:
  - `PKM_ROOT` (Pflicht): absoluter Pfad zum Vault im Nextcloud-Ordner
  - `PKM_GIT_DIR` (Standard `~/Library/Application Support/pkm/git`): Git-Verzeichnis außerhalb der Nextcloud
  - `PKM_CACHE_DIR` (Standard `~/Library/Application Support/pkm`): Suchindex. Muss außerhalb von `PKM_ROOT` und des Nextcloud-Ordners liegen. Liegt es nach `resolve()` innerhalb von `PKM_ROOT`, legt der Server keinen Index an und meldet einen Fehler. `search` ist dann nicht verfügbar, die übrigen lesenden Tools funktionieren weiter
  - `PKM_TZ` (Standard `Europe/Berlin`)
  - `PKM_MAX_KB` (Standard 200): Grenze für ein Dokument bzw. für den Text einer einzelnen Änderung
  - `PKM_VAULT_NAME` (optional): Name des Obsidian-Vaults, um klickbare `obsidian://`-Links zu liefern
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
- **Nicht angeboten:** Löschen, Umbenennen, Verschieben, jede Änderung in `wiki/`.

#### `create_document`
| Parameter | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `title` | string | ja | Wird zu `title`. Daraus wird auch der Dateiname gebildet |
| `content` | string (Markdown) | ja | Ohne Frontmatter. Ein mitgeliefertes Frontmatter wird entfernt |
| `tags` | list[string] | nein | Schlagwörter (Kleinbuchstaben, Bindestrich) |
| `short_citation` | string | nein | Kurzbezeichnung, z. B. `EN 61000-4-6:2014` |
| `date_document` | string | nein | Ausgabedatum wie gedruckt |
| `context` | string | nein | z. B. Chat-Titel |
| `related` | list[string] | nein | Ziele verwandter Dokumente (Pfad/Wikilink/ID) |
| `kind` | enum `note` \| `standard` \| `regulation` \| `correction` | nein | Standard `note` |
| `toolchain` | string | empfohlen | Wird zu `toolchain_markdown`, z. B. `Claude Opus 5.5 (pkm-mcp)`. Fehlt der Wert, schreibt der Server `pkm-mcp` |
| `area` | enum `documents` \| `scratch` | nein | Standard `documents` |
| `folder` | string | nein | Nur bei `area: "scratch"`: Unterordner in `scratch/` (wird angelegt, falls nötig). Standard ist die Wurzel von `scratch/` |

Ergebnis bei `documents`: Frontmatter nach 4.1 mit `date_markdown` = jetzt, `toolchain_markdown`, `id`, `version: 1`. Commit `doc: <title> v1`. Bei Namensgleichheit wird ein Suffix angehängt, nie überschrieben.

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

Geschützt: `id`, `version`, `date_markdown`, `date_updated`, `status_markdown`. Beim Schreiben werden Werte mit `: ` automatisch in Anführungszeichen gesetzt (4.1). Das Frontmatter wird vollständig neu geschrieben, Kommentare darin gehen verloren (4.1).

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

Rückgabe: `id`, `version`, `path`, `frontmatter`, `content`, `hash`, `editable`, `sections`, `backlinks`, `links`. Bei Wiki-Seiten zusätzlich `citations` (geparst, ohne Prüfung). Bei PDFs und Bildern nur Metadaten und Pfad. Lesbar sind `documents/`, `scratch/` und `wiki/`. In `scratch/` fehlen `id` und `version`, `editable` ist `true`.

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
- Gewichte: Titel 5, Aliase/Tags/Themen 3, Kurzfassung 2, Text 1. Zusätzlich eine Tabelle `id → path, version` für die Auflösung nach 5.2
- `index.db` liegt in `PKM_CACHE_DIR`, nie im Vault oder im Nextcloud-Ordner (7.1)
- Der Index umfasst `wiki/`, `documents/` und `scratch/`. Welcher Bereich durchsucht wird, bestimmt `scope`
- Vor jeder Anfrage werden geänderte Dateien nachindexiert (Vergleich von `mtime` und Größe)
- Fehlt der Index oder ist er beschädigt, baut der Server ihn automatisch neu auf

### 7.5 Sicherheit

- Pfadprüfung mit `resolve()`. Kein `..`, keine absoluten Pfade, keine Symlinks nach außen
- Schreiben nur wie in 7.2 beschrieben. **Nie änderbar:** `wiki/`, `CLAUDE.md`, Nicht-Markdown-Dateien, alles außerhalb von `PKM_ROOT`
- Git-Aufrufe nur mit fest vorgegebenen Argumenten (kein Durchreichen von Eingaben als Optionen). Pfade werden nach `--` übergeben
- Es gibt keine Git-Operation, die Geschichte umschreibt (`reset`, `rebase`, `push --force` usw.)
- Rückgaben enthalten nur relative Pfade
- Erzeugte Dateinamen sind plattformfest (5.5)

### 7.6 Einbindung in Claude Desktop

```json
{
  "mcpServers": {
    "pkm": {
      "command": "<HOME>/.local/bin/uvx",
      "args": ["--from", "<PFAD_ZUM_PAKET>/pkm-tools", "pkm-mcp"],
      "env": {
        "PKM_ROOT": "<HOME>/Nextcloud/<VAULT>",
        "PKM_GIT_DIR": "<HOME>/Library/Application Support/pkm/git",
        "PKM_VAULT_NAME": "<VAULT>",
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

Die Datei liegt auf dem Mac unter `~/Library/Application Support/Claude/claude_desktop_config.json`. Platzhalter in spitzen Klammern sind durch absolute Pfade zu ersetzen (`<HOME>` = Home-Verzeichnis auf dem Mac, `<VAULT>` = Ordner- bzw. Vault-Name). JSON kennt weder `~` noch Umgebungsvariablen. `uvx` steht mit absolutem Pfad und `git` muss über `PATH` erreichbar sein, weil Claude Desktop MCP-Server mit minimaler Umgebung startet. Der Server ist erreichbar, solange die Desktop-App auf dem Mac läuft.

---

## 8. CLI `pkm`

Alle Befehle außer `pkm reindex` ignorieren `scratch/` (3). `pkm doctor` prüft nur, dass `scratch/` in `.gitignore` steht.

| Befehl | Funktion |
|---|---|
| `pkm init` | Legt Struktur, `CLAUDE.md`, `wiki/index.md`, `log.md`, `_status.md`, `state.json` und `.gitignore` an, initialisiert das Git-Verzeichnis außerhalb des Vaults, falls nötig (idempotent) |
| `pkm ids` | Trägt fehlende `id`/`version` in Markdown-Dokumente ein und committet **je Dokument einzeln** (`doc: <title> v1`, `PKM-Source: agent`). Meldet doppelte IDs |
| `pkm versions` | Committet alle von Hand geänderten Dokumente als neue Version (je Dokument eine, `PKM-Source: user`). Erkennt auch Verschiebungen (Markdown über die ID, PDF/Bild über den Hash) und committet sie mit: ein Commit enthält dann alten und neuen Pfad. Eine neue Version entsteht nur, wenn sich `body_hash` oder `meta_hash` geändert hat (4.8). Reines Verschieben ergibt den Commit `doc: <title> moved` ohne Versionssprung |
| `pkm pending` | JSON-Liste der zu verarbeitenden Dokumente: `new`, `changed` (mit `processed_version` → `version` und geänderten Abschnitten), `moved` (alt → neu), `deleted` (mit betroffenen Wiki-Seiten) |
| `pkm history <target> [--diff <von> [<bis>]]` | Wie das MCP-Tool `history` |
| `pkm show <target> --version <n> [--section <name>]` | Inhalt einer früheren Version |
| `pkm fix-citations` | Korrigiert Links in Belegen und `sources`, deren Ziel verschoben wurde |
| `pkm sync-citations [<page>…]` | Erzeugt `sources` aus den Fußnoten neu |
| `pkm sha <target> [--section <key>] [--full]` | Abschnitts- oder Datei-Hash nach 4.8 (Standard: 6 Zeichen für Belege). Ohne `--section` werden alle Schlüssel mit Hash, `body_hash`, `meta_hash` und `file_hash` aufgelistet. Hilft bei der Fehlersuche |
| `pkm mark <id>… --pages <page>…` | Trägt verarbeitete Dokumente mit Version und Abschnitts-Hashes in `state.json` ein |
| `pkm index` | Erzeugt `wiki/index.md` neu |
| `pkm status` | Erzeugt `wiki/_status.md` neu, inklusive Einsortier-Vorschlägen für verarbeitete Dokumente im Eingang |
| `pkm lint` | JSON-Bericht. **Struktur:** kaputte Links, verwaiste Wiki-Seiten, fehlende Kurzfassung, fehlerhaftes Frontmatter, häufige Begriffe ohne Seite. **Belege:** Ziel fehlt oder verschoben, Anker fehlt, Zitat nicht in der belegten Version, Status `newer_version`, Beleg zeigt auf Wiki-Seite, Absatz ohne Fußnote, Fußnote ohne Definition, `sources` nicht synchron. **Dokumente:** ohne ID oder Version, doppelte IDs, ungültiges YAML durch fehlende Anführungszeichen (Fehler, mit Hinweis auf `pkm fix-frontmatter`), fehlende Felder `date_markdown`/`toolchain_markdown` (Hinweis), Feld `short citation` mit Leerzeichen (Hinweis), umgewandeltes Dokument ohne `kind` (Hinweis), unbekannter Wert in `kind` (Fehler), Datumsfelder weder im Format `YYYY-MM-DDTHH:MM:SS` noch `YYYY-MM-DD` oder mit Zeitzonen-Angabe, `tags` mit Leerzeichen, `version` passt nicht zum Commit-Verlauf. **Plattform:** Nextcloud-Konfliktkopien, nicht plattformfeste Dateinamen, Namen, die sich nur in Groß- und Kleinschreibung unterscheiden. **Überschriften (4.8):** Duplikate, Zeichen, die Anker brechen, Text auf `#` plus Ziffern (`heading_suffix_like` als Warnung, `heading_suffix_collision` als Fehler) |
| `pkm restore <target> --version <n>` | Wie `restore_document` |
| `pkm reindex` | Baut den Suchindex neu auf |
| `pkm fix-frontmatter <target>… [--all]` | Repariert das Frontmatter zeilengenau, sonst ändert sich nichts: setzt Werte mit `: ` oder führenden YAML-Sonderzeichen in doppelte Anführungszeichen und benennt `short citation` in `short_citation` um. **Nur auf ausdrückliche Anweisung des Nutzers.** Ohne Ziel listet der Befehl nur die betroffenen Dateien auf. Jede geänderte Datei wird als neue Version committet (`PKM-Source: user`, weil der Nutzer es veranlasst hat) |
| `pkm commit-wiki --message "<text>"` | Agenten-Commit am Ende eines Pflegelaufs (12). Committet ausschließlich `wiki/` und `.pkm/state.json`. Offene Änderungen in `documents/` bleiben unberührt |
| `pkm doctor` | Prüft die Umgebung: Git-Verzeichnis außerhalb des Vaults und erreichbar, `PKM_CACHE_DIR` außerhalb des Vaults und des Nextcloud-Ordners, kein `.git` im Vault, `user.name`/`user.email`, Schreibrechte, Nextcloud-Konfliktkopien, Obsidian-Einstellungen aus Abschnitt 13 (soweit in `.obsidian/app.json` lesbar). Mit `--short` nur Fehler |

---

## 9. Skill `pkm-wiki` (Pflege, im Projekt)

**Beschreibung (Trigger):** Pflege des PKM-Wikis: neue und geänderte Dokumente verarbeiten, Lint, Wiki-Fragen im Pflegeprojekt.

### 9.1 Ablauf „Ingest“

1. `pkm doctor --short`. Bei Fehlern, etwa Konfliktkopien, wird abgebrochen und das Problem gemeldet. Danach `pkm versions`, damit Änderungen von Hand, auch die vom Windows-Rechner, als Versionen committet sind.
2. `pkm ids`, um fehlende IDs nachzutragen.
3. `pkm pending`.
4. `pkm fix-citations` für alle als `moved` gemeldeten Dokumente.
5. **Neue Dokumente:** vollständig lesen.
   1. Seite `wiki/summaries/<name>.md` anlegen, mit Belegen.
   2. Über `wiki/index.md` (und bei Bedarf über die Suche) betroffene Seiten bestimmen. Höchstens 10–15 Themen-, Entitäts- und Syntheseseiten aktualisieren oder anlegen. Jede neue oder geänderte Aussage bekommt eine Fußnote nach 4.2.
   3. Querverweise in beide Richtungen setzen.
6. **Geänderte Dokumente:** `pkm history --diff <processed_version>` lesen und nur die geänderten Abschnitte verarbeiten (Abschnitt 6.4).
   1. Betroffene Wiki-Aussagen auf den neuen Stand bringen, mit Belegen auf die neue Version.
   2. Bei geänderten Entscheidungen oder Fakten den früheren Stand als „Bis Version n: …“ mit Beleg auf die alte Version behalten, sofern er für die Nachvollziehbarkeit wichtig ist.
   3. Belege auf unveränderte Abschnitte auf die neue Version anheben (nur `v:` und `sha:`).
   4. Die Zusammenfassungsseite des Dokuments aktualisieren.
7. **Gelöschte Dokumente:** Betroffene Aussagen werden nicht gelöscht. Sie kommen unter „Widersprüche / offene Fragen“ mit dem Vermerk „Original nicht mehr vorhanden (letzter Stand in Git, v<n>)“, `confidence: low`, und im Bericht steht eine Rückfrage.
8. **Korrektur-Dokumente** (`kind: correction`): Die Korrektur des Nutzers hat Vorrang vor älteren Quellen und gilt selbst als Beleg. Die betroffene Wiki-Seite wird angepasst und die alte Aussage im Log als ersetzt vermerkt. Widerspricht die Korrektur einer Quelle, die neuer ist als sie selbst, fragt der Agent nach.
9. `pkm sync-citations`, `pkm mark …`, `pkm index`, `pkm status`.
10. Eintrag in `wiki/log.md`.
11. Commit des Agenten mit `pkm commit-wiki` (Abschnitt 12).
12. Kurzer Bericht im Chat: neue und geänderte Seiten, überholte Aussagen, Beleg-Probleme, Einsortier-Vorschläge, Rückfragen.

**Grenzen:** Mehr als 10 Dokumente pro Lauf werden in Etappen verarbeitet. Bei unklarer Einordnung fragt der Agent nach. Im unbeaufsichtigten Lauf entscheidet er konservativ und vermerkt die Frage im Log.

### 9.2 Ablauf „Lint“

1. `pkm lint`.
2. **Selbst beheben:** verschobene Belege, kaputte Links mit eindeutigem Ziel, fehlende Kurzfassungen, `sources`-Synchronisation, Index.
3. **Vorschlagen statt ausführen:** inhaltliche Widersprüche, Zusammenlegen von Seiten, neue Seiten, doppelte IDs, Belege mit `newer_version`, die nicht automatisch angehoben werden konnten.
4. Bericht nach `wiki/_lint/YYYY-MM-DD.md` und Eintrag im Log.

### 9.3 Ablauf „Abfrage“ (im Projekt)

Erst den Index, dann die relevanten Seiten, dann die Antwort mit Verweisen auf die Wiki-Seiten. Auf Nachfrage nennt der Agent die Belege. Gute Antworten bietet er als Seite unter `syntheses/` an.

### 9.4 Ablauf „Schema anpassen“

Änderungen an `CLAUDE.md` schlägt der Agent vor und schreibt sie erst nach Zustimmung.

### 9.5 Feste Regeln

- Sprache: Deutsch.
- `scratch/` wird weder gelesen noch verarbeitet. Kein Beleg zeigt auf eine Datei dort.
- `status_markdown` unverändert lassen. Der Wert spielt für die Verarbeitung keine Rolle.
- In `documents/` ausschließlich `id` und `version` setzen, und zwar nur über `pkm ids` und `pkm versions`. Sonst nichts ändern, verschieben oder löschen.
- Im Wiki nichts löschen. Aussagen und Belege werden ergänzt, aktualisiert oder als überholt gekennzeichnet.
- Keine Aussage ohne Beleg auf ein Dokument. Zitate in Belegen sind wörtlich aus der genannten Version kopiert. Nichts erfinden, Lücken als offene Frage markieren.
- Formate wie in Abschnitt 4.

---

## 10. Skill `pkm-access` (für normale Chats)

**Beschreibung (Trigger):** Das PKM aus Chats nutzen: „leg das ins PKM“, „führ das im Dokument zu … weiter“, „aktualisier mein Dokument …“, „was weiß mein Wiki über …“, „woher stammt das?“, „was hat sich geändert?“, „korrigier im Wiki …“.

**Neu ablegen:**
1. Das Ergebnis verdichten (Ergebnis, Entscheidungen, Offene Punkte, Kontext). Nur Belastbares aufnehmen, Hypothesen kennzeichnen.
2. Titel, `tags` und gegebenenfalls `related` vorschlagen. `toolchain` mit dem eigenen Modellnamen und `pkm-mcp` übergeben.
3. Vorher prüfen, ob es zum Thema schon ein Dokument gibt (`search`, Bereich `documents`). Wenn ja, fragen, ob es aktualisiert werden soll (Abschnitt 6.1).
4. Den Entwurf zeigen und erst nach Bestätigung `create_document` aufrufen. Das gilt **ohne Ausnahme**, auch wenn der Nutzer „direkt“ sagt.
5. ID, Pfad und Version nennen.

**Grundregel:** Jeder schreibende Aufruf (ablegen, neufassen, ergänzen, bearbeiten, Frontmatter, wiederherstellen) erfolgt erst, nachdem ein Entwurf gezeigt und bestätigt wurde. Es gibt keine Ausnahme.

**Fortgeführte Diskussion:** Standard ist 6.2, also das Dokument aktualisieren, mit Vorher/Nachher pro Abschnitt, Änderungsnotiz und Bestätigung. 6.3 (datierter Abschnitt) **nur auf ausdrückliche Anweisung** und nie von sich aus vorschlagen.

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

## 11. Projekt „PKM-Pflege“ und Automatisierung

- **Projekt** in Claude Desktop mit der Anweisung: „Dies ist das Pflegeprojekt für das PKM unter `<PKM_ROOT>`. Nutze den Skill `pkm-wiki`.“
- **Ordnerzugriff:** Der Vault wird im Chat über „+“ → „Add folder“ verbunden. Der Agent arbeitet über die Shell auf deinem Rechner und ruft dort die `pkm`-CLI auf.
- **Start: manuell.** Pflegeläufe werden im Projekt angestoßen („Verarbeite neue Dokumente“, „Lint“).
- **Automatik (vorbereitet, später):** eine geplante Aufgabe, z. B. täglich „Ingest, danach Lint“. Sie läuft auf dem Mac, der dafür wach sein muss, und die Claude-Desktop-App muss laufen. Der Skill ist schon dafür ausgelegt: Im unbeaufsichtigten Lauf entscheidet er konservativ und schreibt Rückfragen in `wiki/_status.md` und ins Log, statt zu warten. Eingeschaltet wird die Automatik nur auf Anweisung des Nutzers.

---

## 12. Git

Git ist Pflicht und übernimmt zwei Aufgaben: die **Versionsgeschichte jedes Dokuments** und die **Nachvollziehbarkeit der Agentenarbeit**.

**Commits nach Herkunft** (alle mit den Zeilen aus 5.4):

| Commit | Wer | Wann | Inhalt |
|---|---|---|---|
| `doc: <title> v<n>` | pkm-mcp | bei jeder Änderung aus einem Chat | genau ein Dokument |
| `doc: <title> v<n>` (Quelle `user`) | pkm-mcp bzw. `pkm versions` | vor einer MCP-Änderung bzw. zu Beginn eines Pflegelaufs | genau ein von Hand geändertes Dokument |
| `doc: <title> v1` (Quelle `agent`) | `pkm ids` | im Pflegelauf, falls nötig | genau ein Dokument, nur Frontmatter-Felder `id`/`version` |
| `pkm: ingest <n> documents` / `pkm: lint` | Pflege-Agent über `pkm commit-wiki` | am Ende eines Laufs | nur `wiki/` und `.pkm/state.json` |

So bleibt sauber getrennt, was von dir, aus einem Chat oder vom Agenten stammt. Ein `git revert` auf einen Agenten-Commit trifft nur das Wiki.

- Das Git-Verzeichnis liegt außerhalb der Nextcloud (5.5). Die Versionsgeschichte existiert damit **nur auf dem Mac**. Gesichert wird sie über **Time Machine**, denn `~/Library/Application Support/pkm/` ist darin enthalten.
- `.gitignore`: `scratch/`, `.obsidian/workspace*`, `.pkm/mcp.log`, Nextcloud-Hilfsdateien (`.sync_*`, `.owncloudsync.log`, `*.part`)
- Obsidian Git wird nicht verwendet. Das Plugin fände das Repo auch gar nicht, weil kein `.git` im Vault liegt.
- Kein Remote. Ein Push auf ein privates Remote (z. B. Gitea auf dem Homeserver) lässt sich später ohne Änderung am Konzept nachrüsten.

---

## 13. Obsidian-Einstellungen

- **Dateien & Links:**
  - „Interne Links automatisch aktualisieren“: **an** (Grundlage von 5.1)
  - „Neues Link-Format“: **Absoluter Pfad im Vault**, damit Belege eindeutig sind
  - „Wikilinks verwenden“: an
  - Anhang-Ordner: `documents/_attachments/`
- **Ausgeschlossene Dateien:** `.pkm/`
- **Web Clipper:** Zielordner `documents/_inbox/`. Die Vorlage des Clippers wird an 4.1 angepasst: `title` (Seitentitel), `source` (URL, wird von den Werkzeugen nicht ausgewertet), `date_document` (Veröffentlichungsdatum der Seite, falls vorhanden), `date_markdown` (Zeitpunkt des Clippens im Format `YYYY-MM-DDTHH:MM:SS`), `toolchain_markdown: Obsidian Web Clipper`, `tags`. Die Standardvorlage des Clippers verwendet teils andere Namen. Maßgeblich ist, was in den Einstellungen des Clippers eingestellt ist.
- **Property-Typen** einmalig in Obsidian festlegen (Einstellungen → Eigenschaften): `date_markdown` und `date_updated` als **Datum & Uhrzeit**, `version` als **Zahl**, `related` und `sources` als **Liste**, alle übrigen eigenen Felder als **Text**. `tags` und `aliases` sind Obsidian-Standard.
- Optional: Dataview für Abfragen über das Frontmatter, Graph View (eingebaut)
- **Mac und Windows** nutzen denselben Vault über Nextcloud. Die Einstellungen in `.obsidian/` werden mitsynchronisiert und gelten auf beiden Rechnern.
- Auf **Windows** wird nur in Obsidian gelesen und bearbeitet. Änderungen von dort werden beim nächsten MCP-Zugriff auf die Datei bzw. beim nächsten Pflegelauf als Version mit `PKM-Source: user` übernommen.

---

## 14. Tests und Abnahme

**Automatisiert (pytest, mit temporärem Git-Repo):**
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
- Frontmatter (4.1): die Norm aus dem Beispiel mit unquotiertem `: ` im Titel ergibt `invalid_frontmatter`, `pkm fix-frontmatter` macht sie gültig und ändert nur diese Zeile. Ein Dokument mit genau den sechs Umwandlungsfeldern bekommt durch `pkm ids` nur `id` und `version` am Ende angehängt. `short_citation` wird gelesen, geschrieben und als Ziel aufgelöst. Die alte Schreibweise `short citation` wird gelesen und von `pkm fix-frontmatter` umbenannt. `meta_hash` ändert sich nicht bei Änderung von `status_markdown`. Kein Werkzeug schreibt `status_markdown`. Datumswerte gehen als Zeichenkette in `meta_hash` ein. `date_markdown` und `date_updated` werden mit Uhrzeit ohne Zeitzone geschrieben, in Ortszeit nach `PKM_TZ`
- `scratch/`: Anlegen mit `area: "scratch"` und `folder`, Ändern ohne Version und Commit, `history`/`restore_document` liefern `not_versioned`, `search` findet `scratch/` nur mit `scope: "scratch"`, `pending`, `ids`, `versions` und `lint` ignorieren den Bereich, Lint meldet einen Beleg im Wiki, der auf `scratch/` zeigt, Verschieben von `scratch/` nach `documents/` ergibt beim nächsten Lauf `version: 1` und einen Commit
- Getrenntes Git-Verzeichnis: alle Git-Operationen mit `--git-dir`/`--work-tree`, im Vault entsteht nie ein `.git`
- Plattform: NFC/NFD-Pfade, CRLF-Datei ergibt denselben Hash wie LF, Windows-ungültige Zeichen und reservierte Namen im Slug ersetzt, Konfliktkopien erkannt und nicht verarbeitet, Groß-/Kleinschreibungs-Kollisionen gemeldet

**Abnahme (manuell):**
1. Aus einem Chat: „Leg das Ergebnis ins PKM.“ → Die Datei erscheint in `documents/_inbox/` mit ID und `version: 1`, und es gibt einen Commit.
2. Im Pflegeprojekt: „Verarbeite neue Dokumente.“ → Zusammenfassung, Themenseiten mit Belegen (`v:1`), Index, Status, Log, Agenten-Commit.
3. In Obsidian das Dokument einsortieren → Die Belege zeigen sofort auf den neuen Ort.
4. In einem neuen Chat: „Führ die Diskussion zum Überlaufsensor weiter …“ → Der Chat findet das Dokument, zeigt die Änderungen pro Abschnitt und eine Notiz und schreibt nach Bestätigung `version: 2`. Das Dokument enthält keinen Fortsetzungsabschnitt.
5. „Was hat sich geändert?“ → Verlauf v1 → v2 mit Notiz und Diff.
6. Nächster Pflegelauf → Nur die geänderten Abschnitte werden verarbeitet. Das Wiki zeigt den neuen Stand, bei einer geänderten Entscheidung zusätzlich „Bis Version 1: …“ mit Beleg auf v1.
7. „Woher stammt die Angabe …?“ → Original mit Abschnitt, Zitat, Version und Status `ok`.
8. „Dokumentiere das als Fortsetzung“ → Erst jetzt entsteht ein datierter Abschnitt.
9. Auf dem Windows-Rechner ein Dokument in Obsidian ändern → Nach dem Sync und einem Pflegelauf gibt es eine neue Version mit `PKM-Source: user`, und das Wiki ist aktualisiert.
10. Aus einem Chat: „Setz ‚Filter der Zisternenpumpe reinigen‘ auf meine Todo-Liste“ → Entwurf, dann ein Eintrag in `scratch/`. Es gibt keinen Commit, und nach einem Pflegelauf taucht der Eintrag nicht im Wiki auf.
11. `pkm doctor` und `pkm lint` melden null Fehler.

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
| 7 | Später: geplante Aufgabe | Automatische Verarbeitung, erst auf Anweisung des Nutzers |

---

## 16. Entscheidungen

### Getroffen (Review vom 01.11.2026)

| # | Thema | Entscheidung | Umgesetzt in |
|---|---|---|---|
| 1 | Speicherort und Plattform | Vault in einem Nextcloud-Ordner. Gelesen und bearbeitet auf Mac und Windows, Agent und MCP nur auf dem Mac. In der Spezifikation stehen Platzhalter statt konkreter Pfade | 5.5, 7.1, 7.6, 12, 13 |
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
| 11 | Suchindex und Protokoll | Index in `PKM_CACHE_DIR` außerhalb von Vault und Nextcloud, geprüft von Server und `doctor`. Protokoll in `.pkm/mcp.log`, nicht in Git | 3, 5.5, 7.1, 7.2, 7.4, 8, 12 |
| 12 | Quelle bei Änderungen von Hand | `user` | 5.4, 7.3 |
| 13 | Commits von `pkm ids` | Je Dokument ein Commit, kein Sammel-Commit | 5.4, 8, 12 |
| 14 | Hashes und Abschnitte | Festgelegt in 4.8 | 4.8 |
| 15 | Schonfrist für gerade bearbeitete Dateien in `pkm versions` | Vorerst keine | – |
| 16 | Frontmatter-Erhalt | Serverfelder zeilengenau, `update_frontmatter` schreibt neu | 4.1, 7.2 |
| 17 | Verschieben in `pkm versions` | Ein Commit mit altem und neuem Pfad, neue Version nur bei geändertem Inhalt oder Metadaten | 8 |
| 18 | Kurznamen | Ohne Groß-/Kleinschreibung, mehrdeutig → `ambiguous` | 7.1 |
| 19 | Plattform für Tests | Pfade überschreibbar, Tests auch unter Linux, produktiv nur macOS | 7.1 |
| 20 | Agenten-Commit | `pkm commit-wiki`, nur `wiki/` und `.pkm/state.json` | 8, 9.1, 12 |
| 21 | Überschriften auf `#` plus Ziffern | Suffix-Vergabe überspringt belegte Schlüssel. Lint warnt (`heading_suffix_like`) bzw. meldet einen Fehler bei Kollision (`heading_suffix_collision`) | 4.8, 8, 14 |
| 22 | Bereich `scratch/` | Für kurzlebige Notizen und Todo-Listen. Nicht in Git, nie im Wiki, von Lint ignoriert. Chats dürfen anlegen und ändern (mit Entwurf), ohne Version und Commit | 3, 7, 8, 9.5, 10, 12 |
| 23 | Frontmatter | Schema der digitalisierten Normen (`title`, `short_citation`, `date_document`, `status_markdown`, `date_markdown`, `toolchain_markdown`), ergänzt um `id`, `version`, `date_updated`, `context`, `tags`, `related`, `kind`. Obsidian-taugliche Typen, Anführungszeichen bei `: ` | 4.1, 4.8, 7, 8, 13 |
| 24 | Feldnamen und `status_markdown` | Keine Leerzeichen in Feldnamen (`short_citation`). `status_markdown` nur bei Normen und Standards, unverändert übernommen, von keinem Werkzeug gesetzt oder geändert | 4.1, 7.2, 8 |
| 25 | Zeitangaben | `date_markdown` und `date_updated` mit Uhrzeit (`YYYY-MM-DDTHH:MM:SS`), Ortszeit ohne Zeitzone, Obsidian-Typ „Datum & Uhrzeit“. Datum-only-Werte bleiben gültig | 4.1, 13 |
| 26 | Werte von `kind` | `note`, `standard` (Normen und Standards), `regulation` (Gesetze und Verordnungen), `correction`. Verarbeitung von `standard` und `regulation` wie `note` | 4.1, 7.2, 8 |

### Noch offen

Keine. Die Spezifikation ist bereit zur Umsetzung.
