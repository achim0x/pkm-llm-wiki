# PKM mit LLM-Wiki – Umsetzungsplan

**Bezug:** [Spezifikation v0.28](specification.md) (Phasen 0–6 ursprünglich zu v0.12) · **Stand:** 05.11.2026 · **Plan-Version:** 4

Dieser Plan zerlegt die Spezifikation in umsetzbare Arbeitspakete mit Ergebnissen, Tests und Abnahmekriterien. Abschnittsnummern in Klammern (z. B. „5.4“) verweisen auf die Spezifikation.

> **Änderungen in Plan-Version 4**
> - Phasen 0–6 und 7a–7c umgesetzt; neue Phase 7d (Englisch, Cloud-Speicher allgemein, Git optional, vereinfachte Installation, Spezifikation 0.25–0.26) und Phase 7e (Abnahme mit neuer Installation). Architektur und Installationsablauf beschreibt [architecture.md](architecture.md).
> - Risiken und Zuordnung an Cloud-Speicher allgemein und den Betrieb ohne Git angepasst.
>
> **Änderungen in Plan-Version 3**
> - K1 revidiert: Der Suchindex (SQLite) liegt in `PKM_CACHE_DIR` außerhalb der Nextcloud, nur `mcp.log` liegt in `.pkm/`. `pkm doctor` und der Server prüfen, dass `PKM_CACHE_DIR` nicht im Vault oder im Nextcloud-Ordner liegt.
> - K6, K10, K11 wie vorgeschlagen entschieden. Keine Klärungen mehr offen.
>
> **Änderungen in Plan-Version 2**
> - Bezug auf Spezifikation 0.11: Normalisierung, Abschnitte und Hashes nach 4.8 (`_preamble`, `Text#2`, `file_hash`/`body_hash`/`meta_hash`), `pending` mit `meta_changed` und `renamed`, Beleg-Feld `§:`.
> - Klärungen K1–K12 entschieden bzw. durch 0.11 erledigt (Abschnitt 2).
> - Aufwand leicht erhöht (Phase 1 und 4) wegen der genaueren Hash- und `pending`-Regeln.

---

## 1. Überblick

| Phase | Inhalt | Ergebnis | Aufwand (PT) |
|---|---|---|---|
| 0 | Gerüst, Testumgebung | Lauffähiges, leeres Paket mit CI | 1 |
| 1 | Grundbibliothek: Konfiguration, Pfade, Normalisierung/Abschnitte/Hashes nach 4.8, Frontmatter, IDs, Git-Schicht, `pkm init` | Fundament für alles Weitere | 4,5 |
| 2 | Vault-Modell, Adressierung, Suchindex, lesende MCP-Tools | Abfragen aus Chats | 3 |
| 3 | Schreibende MCP-Tools inkl. Versionierung und Commit | Ablegen und Aktualisieren aus Chats | 3,5 |
| 4 | Pflege-CLI: `ids`, `versions`, `pending`, `mark`, `sha`, `show`, `history`, `restore`, `index`, `status`, `reindex`, `commit-wiki` | Pflege-Grundlage | 3,5 |
| 5 | Belege: Parser, Auflösung, `show_citations`, `fix-/sync-citations`, `lint`, `doctor` | Rückverfolgbarkeit | 4 |
| 6 | Skills `pkm-access`, `pkm-wiki`, Projekt „PKM Maintenance“, Einrichtung auf dem PKM-Rechner (Mac oder Windows) | Erster echter Ingest-Lauf | 2 |
| 7 | Manuelle Abnahme (14), Nacharbeiten | Freigabe | 1,5 |
| 7a–7d | Nacharbeiten aus Abnahme und Spezifikation 0.13–0.26 (Pflege über MCP, Bilder, Windows, Englisch, Cloud-Speicher, Git optional, Installation) | umgesetzt | – |
| 8 | Später, nur auf Anweisung: geplante Aufgabe | Automatische Verarbeitung | 0,5 |
| | | **Summe** | **≈ 23,5** |

**Umfang:** Die Spezifikation nennt „rund 550 Zeilen“ für den Server. Realistisch für Server + CLI + Belege + Lint sind **2.500–3.500 Zeilen Code** plus etwa ebenso viel Testcode. Die Schätzung oben geht davon aus.

**Kritischer Pfad:** Phase 1 (Normalisierung/Hashes, Frontmatter, Git-Schicht) → Phase 3 (Versionierung) → Phase 4 (`pending`/`mark`) → Phase 6. Phase 2 und 5 lassen sich teilweise parallel zu 3 bzw. 4 bearbeiten.

---

## 2. Klärungen

### 2.1 Entschieden

| # | Thema | Entscheidung | Folge für die Umsetzung |
|---|---|---|---|
| K1 | Ort von Suchindex und Protokoll | Suchindex **`PKM_CACHE_DIR/index.db`** (außerhalb des Cloud-Ordners, Standard `~/Library/Application Support/pkm`), Protokoll **`.pkm/mcp.log`** | `PKM_CACHE_DIR` darf nicht in `PKM_ROOT` oder im Nextcloud-Ordner liegen, siehe Hinweis unten. `.gitignore` erhält `.pkm/mcp.log` |
| K2 | Wert für Änderungen von Hand | `user` (`chat` \| `user` \| `agent`) | einheitlich in Commits, `history`, CLI |
| K3 | Commits von `pkm ids` | **je Dokument ein Commit** (`doc: <title> v1`, `PKM-Source: agent`), kein Sammel-Commit | Commit-Tabelle in 12 anpassen |
| K4 | Definition `hash`/`expected_hash` | durch Spezifikation 0.11, Abschnitt 4.8 | – |
| K5 | Vorspann, doppelte Überschriften | durch 4.8 (`_preamble`, `Text#2`) | – |
| K7 | Schonfrist für gerade bearbeitete Dateien bei `pkm versions` | **vorerst nicht umgesetzt** | Risiko bleibt bestehen (Abschnitt 6) |
| K8 | Frontmatter-Erhalt | Serverfelder (`id`, `version`, `created`, `updated`) **zeilengenau** ersetzen; `update_frontmatter` darf neu serialisieren (Reihenfolge erhalten, `allow_unicode`, `sort_keys=False`) | Kommentare gehen nur bei `update_frontmatter` verloren, im Skill erwähnt |
| K9 | Kürzungsschutz bei Dokumenten ohne Standardabschnitte | durch 4.8 (Schlüsselvergleich, normalisierter Body) | – |
| K12 | Agenten-Commit | neuer Befehl **`pkm commit-wiki --message "…"`**, committet nur `wiki/` und `.pkm/state.json` | in 4.7 und 8 aufnehmen |

**Hinweis zu K1:** Die SQLite-Datei darf nie synchronisiert werden (5.5). Deshalb:
- Der Server prüft beim Start, dass `PKM_CACHE_DIR` nicht innerhalb von `PKM_ROOT` liegt (nach `resolve()`). Liegt es dort, legt er keinen Index an und meldet einen klaren Fehler; die lesenden Tools ohne Suche funktionieren weiter.
- `pkm doctor` prüft das ebenfalls und warnt zusätzlich, wenn `PKM_CACHE_DIR` in einem Cloud-Ordner liegt (seit 0.25 für alle bekannten Dienste, `cloudsync.py`).
- Der Index ist ein Wegwerf-Cache. Fehlt er oder ist er beschädigt, wird er neu aufgebaut (7.4).
- `mcp.log` liegt in `.pkm/` und wird mit synchronisiert, aber nicht in Git aufgenommen. Es ist eine reine Textdatei, die nur auf dem Mac angehängt wird.

### 2.2 Weitere Entscheidungen (wie vorgeschlagen)

| # | Stelle | Entscheidung |
|---|---|---|
| K6 | `pkm versions` „erkennt auch Verschiebungen und committet sie mit“ | Verschiebe-Commit enthält alten und neuen Pfad derselben ID. Neue Version nur bei geändertem `body_hash` oder `meta_hash`, sonst Commit `doc: <title> moved` ohne Versionssprung |
| K10 | Kurzname-Auflösung `[[zisterne]]` | Dateiname ohne Endung, Vergleich in NFC und ohne Groß-/Kleinschreibung; mehr als ein Treffer → `ambiguous` |
| K11 | Konfiguration auf Nicht-macOS | Defaults abhängig von `sys.platform`; alle Pfade per Umgebungsvariable überschreibbar. Nur für Tests/CI, produktiv nur macOS |

Damit ist keine Klärung mehr offen.

### 2.3 Anpassungen in der Spezifikation (erledigt in 0.12)

- 3 (Ordnerbaum), 5.5, 7.1: `mcp.log` unter `.pkm/`, `index.db` bleibt in `PKM_CACHE_DIR` (Beschreibung von `PKM_CACHE_DIR` auf „Suchindex“ kürzen); 7.4 erste Zeile „`.pkm/index.db`“ → „`PKM_CACHE_DIR/index.db`“; Prüfung „`PKM_CACHE_DIR` nicht im Vault/Nextcloud“ in 7.1 und 8 (`doctor`) aufnehmen (K1).
- 7.3 `history`: `source` „chat/nutzer/agent“ → `chat`/`user`/`agent` (K2).
- 12: Commit `pkm: add missing ids` ersetzen durch einen Commit je Dokument (K3); `.gitignore` um `.pkm/mcp.log` ergänzen (K1).
- 4.7 und 8: `pkm commit-wiki` aufnehmen (K12).
- 4.1 bzw. 7.2: Hinweis zur Frontmatter-Behandlung (K8).
- 8 `pkm versions`: Verhalten bei Verschiebungen (K6); 7.1 Adressierung: Kurznamen ohne Groß-/Kleinschreibung (K10).

---

## 3. Paketaufbau

Ein Python-Paket `pkm-tools` mit den Einstiegspunkten `pkm`, `pkm-mcp` und (seit 7a) `pkm-maintenance-mcp`. Ursprünglich installierbar über `uvx --from <pfad>`; seit 7d über die Installer `install.sh`/`install.ps1` und `pkm setup` (Spezifikation 15.1, [architecture.md](architecture.md)).

```
pkm-tools/
├── pyproject.toml            # deps: mcp, pyyaml · dev: pytest, pytest-cov, ruff
├── src/pkm/
│   ├── config.py             # Umgebungsvariablen, Defaults (7.1, K11)
│   ├── paths.py              # Pfadprüfung, NFC, Slug, Konfliktkopien, Case-Kollisionen (5.5, 7.5)
│   ├── normalize.py          # 4.8 Schritt 1: UTF-8/BOM, LF, NFC, End-LF; invalid_encoding
│   ├── parse.py              # 4.8 Schritt 2–3: Frontmatter, Body, Codezäune, Abschnitte, Schlüssel
│   ├── hashes.py             # 4.8 Schritt 4: hash/file_hash, Abschnitts-, body-, meta-, Binär-Hash
│   ├── frontmatter.py        # zeilengenaues Setzen der Serverfelder, Neuserialisierung (K8)
│   ├── ids.py                # ID-Erzeugung d-YYYYMMDD-HHMM-xxxx (4.1)
│   ├── gitlayer.py           # git --git-dir/--work-tree, Commit mit Trailern, Log nach PKM-Id
│   ├── vault.py              # Dokumentmodell, Bestandsaufnahme, Adressierung (7.1)
│   ├── index.py              # SQLite FTS5 in PKM_CACHE_DIR/index.db (7.4, K1)
│   ├── state.py              # state.json, pending-Berechnung (4.6, 4.8)
│   ├── writer.py             # gemeinsame Schreiblogik: Hash-Schutz, Versionierung, Commit, Rollback (7.2)
│   ├── citations.py          # Parser inkl. §:, Auflösung (5.2), fix/sync
│   ├── wiki.py               # index.md, _status.md, Kurzfassung extrahieren (4.3, 4.4)
│   ├── lint.py, doctor.py
│   ├── mcp_server.py         # FastMCP, dünne Hülle über die Module
│   ├── cli.py                # argparse, JSON-Ausgabe
│   └── templates/            # CLAUDE.md, .gitignore, leere Wiki-Dateien
├── skills/
│   ├── pkm-access/SKILL.md
│   └── pkm-wiki/SKILL.md
└── tests/
    ├── conftest.py           # Fixture: temporärer Vault + getrenntes Git-Verzeichnis
    ├── vectors/              # feste Testvektoren für 4.8 (Eingabe + erwartete Hashes als JSON)
    └── test_*.py
```

**Grundsatz:** Alle fachliche Logik liegt in den Bibliotheksmodulen. MCP-Server und CLI sind dünne Hüllen. `restore_document` und `pkm restore`, `history` und `pkm history` teilen sich dieselbe Funktion. Alle Hash-Berechnungen laufen ausschließlich über `hashes.py`, damit Server, CLI und `state.json` nie auseinanderlaufen.

---

## 4. Phasen im Detail

### Phase 0 – Gerüst (1 PT)

- `pyproject.toml`, Ordnerstruktur, `ruff`, `pytest`.
- Test-Fixture `vault`: legt in `tmp_path` einen Vault und ein getrenntes Git-Verzeichnis an, setzt `user.name`/`user.email` lokal, `PKM_TZ=Europe/Berlin`.
- CI (GitHub Actions) auf `ubuntu-latest` und `macos-latest`, Python 3.11 und 3.12.

**Fertig, wenn:** `pytest` läuft grün mit einem Platzhaltertest auf beiden Plattformen.

### Phase 1 – Grundbibliothek (4,5 PT) · Spez. 15 Schritt 1

| Arbeitspaket | Inhalt | Tests |
|---|---|---|
| 1.1 `config` | `PKM_ROOT` Pflicht, übrige Defaults (7.1); `PKM_MAX_KB`, `PKM_GIT_AUTHOR`, `PKM_TZ`; `PKM_CACHE_DIR` (Index) und `.pkm/mcp.log` (K1); Prüfung „`PKM_CACHE_DIR` nicht innerhalb `PKM_ROOT`“ | fehlendes `PKM_ROOT` → klarer Fehler; `PKM_CACHE_DIR` im Vault → Fehler |
| 1.2 `paths` | `resolve()`-Prüfung gegen `PKM_ROOT`, keine Symlinks nach außen, NFC, Slug (Umlaute ausschreiben, ungültige Zeichen, reservierte Namen, ≤ 120 Zeichen, kein Punkt/Leerzeichen am Ende), Erkennung „conflicted copy“/„Konflikt“, Case-Kollisionen | `..`, absolute Pfade, Symlink nach außen, `CON.md`, NFD-Eingabe |
| 1.3 `normalize` | 4.8 Schritt 1: UTF-8 (sonst `invalid_encoding`), BOM weg, CRLF/CR → LF, NFC, genau ein End-LF; Schreibfunktion erzeugt immer diese Form | Testvektoren: BOM, CRLF, einzelnes CR, NFD, kein/doppeltes End-LF, ungültiges UTF-8 |
| 1.4 `parse` | 4.8 Schritt 2–3: Frontmatter (`---` … `---`/`...`, sonst `invalid_frontmatter`), Body, CommonMark-Codezäune (``` und ~~~, Zaunlänge), ATX-Überschriften Ebene 1/2 mit ≤ 3 Leerzeichen Einrückung, Setext ignorieren, `_preamble` (nur wenn nach Normalisierung nicht leer), Schlüsselbildung (ATX-Abschluss, Leerraum), Duplikate `#2`, `#3` über Ebene 1 und 2; Zeilenpositionen je Abschnitt für Schreib-Tools | Testvektoren: Überschrift im Codeblock, verschachtelte Zäune, Setext, `###` in `##`, `## Offene  Punkte ##`, Einrückung 4 Leerzeichen (keine Überschrift), Duplikate über Ebenen |
| 1.5 `hashes` | 4.8 Schritt 4: `file_hash`, Abschnitts-Hash (ohne Überschriftenzeile, rechts getrimmt, Leerzeilen zusammengefasst), `body_hash` (`<schlüssel>\t<hash>\n`), `meta_hash` (kanonisches JSON aus `title`, `topics`, `related`, `kind`), Binär-Hash; Präfixvergleich für 6 Zeichen | reine Leerraumänderung → Abschnitts-Hash gleich; nur `updated` geändert → `file_hash` anders, `body_hash`/`meta_hash` gleich; leerer Abschnitt = Hash von `""` |
| 1.6 `frontmatter` | Serverfelder zeilengenau setzen/ergänzen (K8), Frontmatter anlegen, wenn keines vorhanden, Rest unverändert; Neuserialisierung für `update_frontmatter` | Kommentare bleiben bei Serverfeldern erhalten; Datei ohne Frontmatter |
| 1.7 `ids` | Format, Alphabet `0-9a-z` ohne `0 1 l o`, Zeit in `PKM_TZ`, Kollisionsprüfung über Callback | Format-Regex, Kollision → neuer Versuch |
| 1.8 `gitlayer` | Aufruf immer mit `--git-dir`/`--work-tree`, feste Argumente, Pfade nach `--`; `add` + `commit --only` für genau die übergebenen Pfade; Nachricht mit Trailern `PKM-Id`/`PKM-Version`/`PKM-Source`; Autor über `--author`; `log --grep` nach ID inkl. `--name-status` (Pfad je Commit); `show <commit>:<pfad>`; „Datei weicht von HEAD ab“; Erkennung „kein Git“ | Commit enthält nur die eine Datei, andere offene Änderungen bleiben offen; Verlauf nach Umbenennung vollständig; im Vault entsteht nie `.git` |
| 1.9 `pkm init` | Ordnerstruktur (3), `CLAUDE.md`-Vorlage, `wiki/index.md`, `log.md`, `_status.md`, `.pkm/state.json`, `.gitignore` (12 + K1), Git-Verzeichnis mit `git --git-dir=… init` und `core.worktree` (nicht `--separate-git-dir`, das legt eine `.git`-Datei im Vault an); idempotent; Initial-Commit | zweimal ausführen → keine Änderung; kein `.git` im Vault |

Die Testvektoren für 4.8 werden als JSON-Dateien in `tests/vectors/` abgelegt (Eingabe, erwartete Abschnittsschlüssel, erwartete Hashes). Sie dienen gleichzeitig als ausführbare Ergänzung der Spezifikation.

**Fertig, wenn:** alle Tests aus 14 zu Pfaden, IDs, Normalisierung/Hashes, Plattform und getrenntem Git-Verzeichnis grün sind.

### Phase 2 – Lesen und Suche (3 PT) · Spez. 15 Schritt 2

| Arbeitspaket | Inhalt |
|---|---|
| 2.1 `vault` | Bestandsaufnahme von `documents/` und `wiki/` (Markdown und Anhänge), Dokumentmodell (Pfad, ID, Version, Titel, Frontmatter, Abschnitte, Hashes), Adressierung über Pfad / Wikilink / Kurzname / `id:` (K10), Fehler `not_found`/`ambiguous` mit Kandidaten; Dateien mit `invalid_encoding`/`invalid_frontmatter` werden mit Status geführt statt übersprungen |
| 2.2 `index` | SQLite in `PKM_CACHE_DIR/index.db` (K1), FTS5 `unicode61 remove_diacritics 2`, Spalten Titel/Aliase+Tags+Themen/Kurzfassung/Text mit `bm25`-Gewichten 5/3/2/1, Tabelle `docs(id, path, version, mtime, size, file_hash)`; vor jeder Anfrage inkrementell (mtime + Größe); bei Fehler/Schemaabweichung Neuaufbau; Präfixsuche durch `*` je Term, Eingabe für FTS escapen |
| 2.3 MCP-Server | FastMCP-Grundgerüst, Protokoll nach `.pkm/mcp.log`, einheitliche Fehlerobjekte |
| 2.4 Tools | `search` (Scope `wiki` Standard, max. 25, Feld `processed` aus `state.json`), `read` (inkl. `version` aus Git, `hash`, `editable`, `sections` mit Schlüsseln nach 4.8, `links`, `backlinks`; bei Wiki-Seiten `citations` – Parser kommt in Phase 5, bis dahin leer; bei `invalid_frontmatter` Rohtext), `history` (Liste + Diff zwischen Versionen), `read_index`, `list_unprocessed` (zunächst vereinfacht, in Phase 4 auf `state.pending` umgestellt) |

**Tests:** Adressierung inkl. `ambiguous`, Umlaut-Toleranz („Zisterne“ findet „zisterne“, „Ueberlauf“ findet „Überlauf“), Gewichtung (Titeltreffer vor Texttreffer), inkrementelle Aktualisierung, Neuaufbau nach Löschen oder Beschädigen von `index.db`, `read` mit alter Version, lesende Tools ohne Git funktionieren.

**Fertig, wenn:** Server lässt sich lokal mit dem MCP-Inspector starten und alle lesenden Tools liefern Ergebnisse auf einem Beispiel-Vault.

### Phase 3 – Schreibende Tools (3,5 PT) · Spez. 15 Schritt 3

Kern ist `writer.apply_change(target, transform, note, source="chat")`, über den alle Tools laufen:

1. Git vorhanden und konfiguriert? Sonst Fehler (5.4).
2. Ziel auflösen, Schreibrecht prüfen (nur `documents/**/*.md`; Neuanlage nur `_inbox/`). Bei `invalid_encoding`/`invalid_frontmatter` verweigern.
3. `expected_hash` gegen aktuellen `file_hash` → sonst `conflict` mit neuem Hash.
4. Weicht die Datei vom letzten Commit ab (Änderung von Hand), zuerst diesen Stand als eigene Version committen (`version` +1, `PKM-Source: user`).
5. Transformation auf den normalisierten Body anwenden, `PKM_MAX_KB` prüfen, `version` +1, `updated` setzen (zeilengenau, K8).
6. In Normalform atomar schreiben (temporäre Datei im selben Ordner + `os.replace`).
7. Commit nur dieser Datei. Bei Fehler: alte Bytes zurückschreiben, Index-Eintrag zurücksetzen (`git restore --staged`), Fehler melden.
8. Rückgabe `{id, path, status, version, new_hash, commit, diff}` (Diff ≤ 80 Zeilen), Protokolleintrag.

| Tool | Besonderheiten |
|---|---|
| `create_document` | Frontmatter im `content` entfernen, Slug + `_YYYY-MM-DD` (Datum am Ende), Suffix `-2`, `-3` bei Namensgleichheit, `related` auflösen und als Wikilinks speichern, `version: 1`, Commit `doc: <title> v1` |
| `rewrite_document` | `large_shortening` bei < 60 % Zeichen des normalisierten Bodys oder fehlenden Schlüsseln (4.8); Liste betroffener Abschnitte; `confirm_shortening` |
| `append_to_document` | Einfügen am Ende eines Abschnitts, `_preamble` = vor der ersten Überschrift, neuen `##`-Abschnitt anlegen, Dateiende; Schlüssel ohne Suffix bei Duplikat → `ambiguous` mit Kandidaten |
| `edit_document` | `old`/`new` vorher normalisieren (LF, NFC); `old` genau einmal im normalisierten Body, sonst `not_found` bzw. `ambiguous` mit Anzahl |
| `update_frontmatter` | `set`/`add`/`remove`, geschützte Felder abweisen, Neuserialisierung (K8) |
| `restore_document` | Body aus Version n; Frontmatter aktuell lassen, Serverfelder aktualisieren; Notiz `wiederhergestellt aus v<n>` |

**Tests (14):** jede Operation → `version` +1 und genau ein Commit nur dieser Datei mit korrekten Trailern; Handänderung wird vorher separat committet; Commit-Fehler (per Hook simuliert) setzt Datei zurück; `wiki/`, `CLAUDE.md`, PDF, Pfade außerhalb immer abgelehnt; Hash-Konflikt; `large_shortening` und Bestätigung; geschützte Felder; `section` mit `_preamble` und Duplikat-Suffix, `ambiguous` ohne Suffix; `edit_document` mit CRLF- bzw. NFD-Eingabe; ohne Git verweigert.

**Fertig, wenn:** Abnahmeschritte 1, 4, 5 aus 14 im Test-Vault per MCP-Inspector durchspielbar sind.

### Phase 4 – Pflege-CLI (3,5 PT) · Spez. 15 Schritt 4

| Befehl | Kernlogik |
|---|---|
| `pkm ids` | Markdown ohne `id`/`version` finden, Frontmatter ergänzen bzw. anlegen (nicht bei `invalid_frontmatter`), Rest unverändert; **je Dokument ein Commit** (K3); doppelte IDs nur melden |
| `pkm versions` | `git status` des Work-Trees für `documents/`: geänderte Markdown-Dateien → je Datei `version` +1 und Commit (`PKM-Source: user`); Verschiebungen über ID (Markdown) bzw. Binär-Hash (Anhänge) erkennen (K6); Konfliktkopien überspringen. Keine Schonfrist (K7) |
| `pkm pending` | Abgleich Bestand ↔ `state.json` nach 4.8: `new`, `changed` (je Abschnitt `added`/`removed`/`changed`/`renamed`; nur Reihenfolge → `changed` ohne Abschnitte), `meta_changed`, `moved`, `deleted` (mit `wiki_pages`); nichts melden, wenn `body_hash` und `meta_hash` gleich sind; JSON-Ausgabe |
| `pkm mark` | `processed_version`, `file_hash`, `body_hash`, `meta_hash`, `sections`, `processed_at`, `wiki_pages` in `state.json` |
| `pkm sha` | `--section <key>` (6 Zeichen, `--full` für 64); ohne `--section` alle Schlüssel mit Hash sowie `body_hash`, `meta_hash`, `file_hash` |
| `pkm show`, `pkm history`, `pkm restore` | wie MCP, gemeinsame Funktionen |
| `pkm index`, `pkm status` | `wiki/index.md` (gruppiert nach `type`, Kurzfassung, Quellenzahl, Datum), `wiki/_status.md` inkl. Einsortier-Vorschlag (Ordner, in dem die meisten Dokumente mit gleichen `topics` liegen) |
| `pkm reindex` | Index neu aufbauen |
| `pkm commit-wiki` | Agenten-Commit nur für `wiki/` und `.pkm/state.json` (K12) |

`list_unprocessed` im MCP-Server wird auf `state.pending` umgestellt (inkl. Kategorie und betroffener Abschnitte).

**Tests:** `pending` für neu, `changed` mit allen vier Abschnittsarten, nur Reihenfolge, `meta_changed`, nur `updated` geändert (→ nichts), verschoben per ID, verschoben per Hash, verschoben *und* geändert, gelöscht, Duplikat-Umnummerierung als `renamed`; `versions` fasst mehrere Handänderungen zu einer Version zusammen; `ids` lässt den Rest der Datei unverändert und erzeugt je Dokument einen Commit.

### Phase 5 – Belege, Lint, Doctor (4 PT) · Spez. 15 Schritt 5

| Arbeitspaket | Inhalt |
|---|---|
| 5.1 Parser | Fußnotenzeilen nach 4.2: `[[pfad#anker]]`, optional `§:<schlüssel>`, `„…“`, `id:`, `v:`, `sha:`, `#page=n`; Vorspann ohne Anker; Zuordnung Fußnote ↔ Absatz/Aussage |
| 5.2 Auflösung | Reihenfolge nach 5.2; Abschnitt über `§:` bzw. Anker (erstes Vorkommen); Status `ok`/`moved`/`newer_version`/`missing` über Präfixvergleich des Abschnitts-Hashes der belegten vs. aktuellen Version (alte Version aus Git) |
| 5.3 `show_citations` | Filter `statement`, `with_excerpt` (≤ 1.500 Zeichen je Auszug, belegte und aktuelle Version), `obsidian://`-Link wenn `PKM_VAULT_NAME` gesetzt; `read` liefert jetzt auch `citations` |
| 5.4 `fix-citations` | Link-Pfade in Fußnoten und `sources` auf aktuelle Orte umschreiben; Anker bzw. `§:` bei `renamed`-Abschnitten anpassen (nur `wiki/`) |
| 5.5 `sync-citations` | `sources` aus Fußnoten erzeugen (eindeutig, sortiert, Wikilinks) |
| 5.6 `lint` | Alle Prüfungen aus 8 plus aus 4.8: `invalid_encoding`, `invalid_frontmatter`, Setext-Überschriften, doppelte Überschriften Ebene 1/2, Überschriften mit `# ^ [ ] \|`; JSON-Bericht mit Schweregrad; jede Prüfung als eigene Funktion |
| 5.7 `doctor` | Umgebungsprüfungen aus 8, `--short`; zusätzlich `PKM_CACHE_DIR` außerhalb von Vault und Cloud-Ordner (K1) |

**Tests:** jede Lint-Prüfung positiv und negativ; alle Status von `show_citations`; Beleg mit `§:` auf Duplikat; Auszug aus alter und aktueller Version; Zitat-Prüfung gegen belegte Version (im normalisierten Text); Beleg auf Wiki-Seite wird gemeldet.

### Phase 6 – Skills, Projekt, Einrichtung (2 PT) · Spez. 15 Schritt 6

- **`skills/pkm-access/SKILL.md`** (schlank): Trigger aus 10; Grundregel „immer erst Entwurf, keine Ausnahme“; Abläufe Ablegen, Fortsetzen (6.2 Standard, 6.3 nur auf Anweisung), kleine Änderungen, Verlauf, Abfragen, Quellen, Korrekturen; Umgang mit `conflict`, `large_shortening` und `ambiguous` bei Abschnitten; Hinweis, dass `update_frontmatter` Kommentare im Frontmatter entfernt (K8).
- **`skills/pkm-wiki/SKILL.md`**: Abläufe Ingest (9.1, Schritt für Schritt mit CLI-Aufrufen, Abschluss mit `pkm commit-wiki`), Lint (9.2), Abfrage (9.3), Schema (9.4), feste Regeln (9.5), Beleg-Format mit Beispiel inkl. `§:`, Umgang mit `meta_changed` und `renamed`, Verhalten im unbeaufsichtigten Lauf.
- **`CLAUDE.md`-Vorlage** im Vault (über `pkm init`): Konventionen aus 4 und 9.5 in Kurzform.
- **Einrichtungsanleitung** `docs/installation.de.md`: ursprünglich `uv` installieren, Git-Identität, `pkm init`, `claude_desktop_config.json` (7.6) von Hand, Skills packen, Projekt „PKM Maintenance“, Obsidian-Einstellungen (13), `PKM_CACHE_DIR` außerhalb des Cloud-Ordners. Seit 7d ersetzt durch Installer und `pkm setup`.
- **Probelauf** mit 3–5 selbst angelegten Dokumenten (keine Startbefüllung, 16 Nr. 7).

### Phase 7 – Abnahme (1,5 PT)

Abnahmeschritte aus 14 auf dem Mac mit echtem Vault im Cloud-Speicher und Windows-Rechner durchgehen, Ergebnis je Schritt protokollieren (`docs/acceptance.md`). Fehler beheben, Skills nachschärfen (Formulierungen, die der Agent falsch versteht).

### Phase 7a – Pflege über MCP statt Shell (Befund aus der Abnahme)

**Befund:** Claude Desktop bzw. Cowork führt Shell-Befehle nur in einer abgeschotteten Umgebung aus (lokale VM, seit Oktober 2026 bei Pro/Max/Ultra in der Cloud). Darin fehlen `pkm`, Git und das Git-Verzeichnis; der Pflegeablauf aus 9.1 mit CLI-Aufrufen läuft dort nicht. Lokale MCP-Server erreicht Cowork dagegen über die Desktop-App.

**Umsetzung:** zweiter MCP-Server `pkm-maintenance-mcp` (`maintenance_server.py`, Logik in `maintrun.py`) mit den lesenden Tools und drei Pflege-Tools:

- `begin_maintenance`: `doctor --short` (bei Fehlern `blocked`), `versions`, `ids` (doppelte IDs → `needs_decision`), `pending`, bei Verschiebungen `fix-citations`; optional Lint.
- `write_wiki_page`: Seite unter `wiki/topics|entities|summaries|syntheses/` anlegen oder ersetzen, mit `expected_hash`, ohne Commit; generierte Dateien gesperrt.
- `finish_maintenance`: `fix-citations`, `sync-citations`, `mark` (Seiten aus den Fußnoten ermittelt), Austragen gelöschter Dokumente, Log-Eintrag mit Zeitstempel, `index`, `status` (mit Rückfragen), `lint`, `commit-wiki`.

Skill `pkm-wiki` und Einrichtung (Abschnitte 5 und 7) sind umgestellt; die CLI bleibt für Einrichtung und Fehlersuche. Offener Punkt: Claude Desktop kann einen Server nicht auf ein Projekt beschränken. `pkm-maintenance` wird nur in Pflege-Unterhaltungen eingeschaltet (organisatorische statt technischer Sperre); Spezifikation 7/9/11 entsprechend anpassen.

### Phase 7b – Änderungsauftrag aus den Pflegeläufen (2026-11-02)

- Frontmatter-Vorschläge: `begin_maintenance` liefert `missing_fields` und `known_tags`; neues Tool `set_document_metadata` (Whitelist `title`, `context`, `tags`, `kind`, `short_citation`, kein Überschreiben ohne `overwrite`, Tags vereinheitlicht, neue Version mit `PKM-Source: agent`). Skill `pkm-wiki` mit Abschnitt „Frontmatter-Vorschläge“; `CLAUDE.md`-Vorlage angepasst; `pkm versions` erfasst Änderungen an `CLAUDE.md`.
- Feldreihenfolge nach Schema bei allen Schreibwegen; einfache Listen ohne Anführungszeichen.
- Lint ohne Fehlalarme bei Zwischenüberschriften, Fett-, Link-Zeilen und belegten Tabellen; Warnung bei Belegen auf leere Abschnitte.
- `read` mit `section`, `offset`/`max_chars`, `content: false`; große Inhalte nur auf Anforderung.
- `fix-citations` schreibt Wikilinks im Text mit um und findet verschobene Dokumente auch bei veraltetem Index; `finish_maintenance` hebt Belege auf unveränderte Abschnitte auf die neue Version.

### Phase 7c – Spezifikation 0.20–0.22: lange Dateinamen, Bilder, Windows

- 0.20: Bei Namen über 120 Zeichen wird nur der Slug gekürzt (`paths.fit_stem`).
- 0.21 Bilder: `images.py`, `docimages.py`, `assets.py`, `imagelint.py`; Parameter `images`, Tools `add_image` und `read_image`; Platzhalter in `read`; Assets in `state.json`; geänderte Bilddateien als neue Version der Dokumente; verwaiste Anhänge in `_status.md`; Lint und Doctor erweitert; Index nur mit Alternativtext.
- 0.22: Windows als gleichwertiger PKM-Rechner in der Spezifikation.
- 0.24: Prüfung von Bild-Data-URIs bei der Übernahme in jeder Schreibweise (`imagescan.py`, `imagefix.py`, `citeraise.py`): Befunde mit Vorschlag, Korrektur nur nach Bestätigung (`fix_images` in Tools und als eigenes Tool, `pkm fix-images`), `image_issues`/`image_notation_only` im Pflegelauf, Anheben der Belege, Lint `nonconforming_image`.
- 0.23: Importordner `pkm_img_import/` im Vault (von `init` angelegt, in `.gitignore`, von der Pflege ausgenommen) und JPEG-Übernahme ohne Metadaten. CI testet nur noch Python 3.12.
- Offen: Anzeige eingebetteter PNG/SVG in Obsidian (auch mit `|breite`) am echten Vault testen.

### Phase 7d – Englisch, Cloud-Speicher, Git optional, einfachere Installation (Spezifikation 0.25–0.26)

- **Englisch:** Code, Meldungen, CLI-Hilfe, MCP-Beschreibungen, Commit-Notizen, generierte Vault-Dateien (`index.md`, `_status.md`, `log.md`, Lint-Berichte), Vorlage `CLAUDE.md`, Skills und README von `pkm-tools` sind englisch. Deutsche Abschnittsnamen bestehender Wiki-Seiten („Inhalt“, „Widersprüche / offene Fragen“) werden weiter erkannt. Die Spezifikation und die Dokumente unter `docs/` bleiben deutsch; `docs/architecture.md` ist englisch.
- **Cloud-Speicher allgemein** (0.25): Konfliktkopien aller bekannten Dienste (`cloudsync.py`), Cloud-Ordner aller Dienste für Git-Verzeichnis und Suchindex, Dateien „nur online“ (`pkm doctor`).
- **Git optional** (0.26): Schalter `PKM_VERSIONING`; ohne Git Schreiben ohne Commit, `not_versioned` für Verlauf und Wiederherstellen, `pkm versions`/`commit-wiki` ohne Wirkung, Änderungen über Hashes, Belege gegen den aktuellen Text. Nachrüsten: Git installieren, `pkm setup` erneut ausführen.
- **Einfachere Installation** (15.1): `config.toml` statt Umgebungsvariablen, Git-Suche (`PKM_GIT`, `PATH`, übliche Orte), `.obsidian/app.json` durch `pkm init`, Assistent `pkm setup` (`setupwiz.py`), Skills im Paket, Installer `install.sh`/`install.ps1` (laden das GitHub-Archiv, funktionieren ohne Git), Release-Workflow mit Skill-ZIPs und Wheel. Die CI führt beide Installer auf Linux, macOS und Windows aus.
- **Tests:** `test_no_git.py`, `test_setup.py`; 405 Tests auf allen drei Systemen grün.
- **Erledigt:** Merge auf `main`, Release `v0.2.0`.
- **Dokumentsprache** (0.27): `pkm setup` fragt, ob im Chat erzeugte Dokumente hauptsächlich englisch oder deutsch sind (`PKM_LANGUAGE`, Option `--language`); der Server `pkm` nennt Sprache und Abschnittsnamen in seinen Anweisungen, der Skill `pkm-access` folgt ihnen; ebenso `pkm-maintenance` mit Wiki-Sprache, Abschnittsnamen und Kurzfassungs-Label für den Skill `pkm-wiki` (`test_language.py`).
- **Erledigt:** Release `v0.2.1` (Dokumentsprache, vorhandene Konfiguration übernehmen, Entwicklungsinstallation).
- **Wiki-Sprache** (0.28): `PKM_LANGUAGE` gilt auch für das Wiki; der Pflege-Server nennt Sprache, Abschnittsnamen und Kurzfassungs-Label.
- **Englische Namen** (0.28): Pflege-Server `pkm-maintenance` (`pkm-maintenance-mcp`, `maintenance_server.py`), Projekt „PKM Maintenance“; `pkm-pflege-mcp` als Alias, `pkm setup` ersetzt den alten Eintrag (`test_setup.py`).
- **Version anzeigen** (0.28): `pkm --version`, Version in `pkm setup` und `pkm doctor`.
- **`CLAUDE.md` aktualisieren** (0.28): `pkm setup` vergleicht die `CLAUDE.md` des Vaults mit der Vorlage und bietet Ersetzen mit Sicherung und Commit oder `CLAUDE.md.new` an (`test_setup.py`).
- **Vorhandene Konfiguration übernehmen** (0.27): `pkm setup` zeigt Einstellungen aus Umgebung, `env`-Blöcken in Claude Desktop und `config.toml` und übernimmt sie nach Bestätigung (`test_setup_adopt.py`).

### Phase 7e – Abnahme mit der neuen Installation

Abnahme nach `docs/acceptance.md`, beginnend mit Schritt 0 (Installer und `pkm setup` auf dem echten PKM-Rechner) und den Zusatzprüfungen „Betrieb ohne Git“ an einem Testvault.

### Phase 8 – Automatik (später, 0,5 PT)

Erst auf ausdrückliche Anweisung: geplante Aufgabe „Ingest, danach Lint“ im Projekt. Voraussetzung: mehrere manuelle Läufe ohne Nacharbeit. Geplante Cowork-Aufgaben laufen in der Cloud und erreichen `pkm-maintenance` voraussichtlich nur bei laufendem PKM-Rechner mit geöffneter Desktop-App – vorher testen.

---

## 5. Teststrategie

- **Testvektoren für 4.8** als JSON in `tests/vectors/`: die Grundlage für alle Hash-abhängigen Funktionen. Ändert sich ein erwarteter Hash, ist das ein bewusster Formatwechsel und braucht eine Migration von `state.json`.
- **Einheitstests** je Modul (Phase 1, 5).
- **Integrationstests** mit echtem `git` in temporären Verzeichnissen; jede Schreiboperation prüft anschließend `git log`, `git show --name-only` und den Datei-Inhalt.
- **MCP-Tests** über die Tool-Funktionen direkt (ohne stdio) plus ein Rauchtest, der `pkm-mcp` per stdio startet und `tools/list` abfragt.
- **Plattformtests:** NFD-Dateinamen, CRLF, Case-Kollisionen (auf Linux nachstellbar), Konfliktkopien.
- **Golden Files** für `index.md`, `_status.md`, Lint-Bericht.
- Zielabdeckung ≥ 85 % für `parse`, `hashes`, `writer`, `gitlayer`, `state`, `citations`.
- Die Testliste aus Spezifikation 14 wird als Checkliste in den Testdateien geführt (Docstring mit Verweis).

---

## 6. Risiken und Gegenmaßnahmen

| Risiko | Auswirkung | Gegenmaßnahme |
|---|---|---|
| Cloud-Speicher synchronisiert während eines Schreibvorgangs | Konfliktkopie, doppelte ID | atomares Schreiben, Hash-Schutz, `doctor`/`lint` melden Konfliktkopien, Pflegelauf bricht ab (9.1) |
| `pkm versions` ändert eine Datei, die gerade auf Windows bearbeitet wird | Konfliktkopie | **bewusst in Kauf genommen (K7).** Nur zwei Zeilen werden geändert; Konfliktkopien meldet `lint`. Bei Bedarf Schonfrist nachrüsten |
| `PKM_CACHE_DIR` oder Git-Verzeichnis versehentlich in einen Cloud-Ordner gelegt (K1) | SQLite bzw. Git-Dateien werden synchronisiert und beschädigt | Server verweigert Index im Vault, `doctor` erkennt Cloud-Ordner aller bekannten Dienste |
| Vault-Dateien liegen nur online (Platzhalter) | Pflegelauf löst Downloads aus oder sieht Dateien nicht | `pkm setup` und `doctor` melden `vault_online_only`; Einstellung je Dienst (Spezifikation 5.5) |
| Git-Verzeichnis außerhalb des Vaults geht verloren | Verlauf weg, Belege `v:` nicht mehr prüfbar | Time Machine (12), `doctor` prüft Erreichbarkeit; später optional Remote |
| Claude Desktop startet MCP mit minimalem `PATH` | `git` nicht gefunden | `pkm setup` speichert den Git-Pfad in `config.toml` (`PKM_GIT`), Suche an den üblichen Orten, klare Fehlermeldung, `doctor` |
| Git fehlt auf dem PKM-Rechner | keine Versionsgeschichte | bewusst erlaubt (0.26): Betrieb ohne Versionsverwaltung mit Hinweis; nachrüstbar durch `pkm setup` |
| Installer ändert eine bestehende Claude-Desktop-Konfiguration | andere Server gehen verloren | nur Einträge `pkm`/`pkm-maintenance`, Sicherungskopie, Ersetzen erst nach Rückfrage |
| Hash-Regeln werden später geändert | alle Einträge in `state.json` gelten als geändert | Testvektoren, Feld `version` in `state.json` als Formatversion, Migration bei Bedarf |
| LLM hält Beleg-Format oder Regeln nicht ein | fehlerhafte Belege | `lint` als harte Kontrolle am Ende jedes Ingest, Skill mit Beispielen |
| Kontextgrenze beim Ingest | unvollständige Verarbeitung | Etappen à ≤ 10 Dokumente (9.1), Verarbeitung nur geänderter Abschnitte |

---

## 7. Zuordnung Spezifikation → Phase

| Spezifikation | Phase |
|---|---|
| 3 Ordnerstruktur, 12 `.gitignore`, `pkm init` | 1 |
| 4.1 Dokument, 5.3 IDs | 1, 4 |
| 4.2 Belege | 5 |
| 4.3–4.5 Index, Status, Log | 4 (Log schreibt der Agent, Phase 6) |
| 4.6 `state.json` | 4 |
| 4.8 Normalisierung, Abschnitte, Hashes | 1 (Grundlage), 3, 4, 5 |
| 5.1–5.2 Zuordnung, Auflösung | 2, 5 |
| 5.4 Versionen/Commits | 1, 3, 4 |
| 5.5 Cloud-Speicher/Plattform | 1, 5, 7d |
| 6 Fortgeführte Diskussionen | 3, 6 |
| 7.1–7.6 MCP | 2, 3, 6 |
| 8 CLI | 1, 4, 5 |
| 9, 10, 11 Skills, Projekt | 6, 8 |
| 13 Obsidian | 6 |
| 14 Tests/Abnahme | durchgehend, 7, 7e |
| 15.1 Einfachere Installation, Git optional (5.4) | 7d |

---

## 8. Nächste Schritte

1. Erledigt: Releases `v0.2.0` und `v0.2.1`; `v0.2.2` (Wiki-Sprache, englische Namen, `CLAUDE.md` aktualisieren) nach Merge von PR #3 taggen.
2. Abnahme nach Phase 7e auf dem PKM-Rechner (`docs/acceptance.md`, ab Schritt 0).
3. Befunde beheben; erst danach Phase 8 (Automatik) und nur auf Anweisung.
