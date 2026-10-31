# PKM mit LLM-Wiki – Umsetzungsplan

**Bezug:** [Spezifikation v0.10](spezifikation.md) · **Stand:** 31.10.2026

Dieser Plan zerlegt die Spezifikation in umsetzbare Arbeitspakete mit Ergebnissen, Tests und Abnahmekriterien. Abschnittsnummern in Klammern (z. B. „5.4“) verweisen auf die Spezifikation.

---

## 1. Überblick

| Phase | Inhalt | Ergebnis | Aufwand (PT) |
|---|---|---|---|
| 0 | Klärung der Unstimmigkeiten, Projektgerüst, Testumgebung | Lauffähiges, leeres Paket mit CI | 1 |
| 1 | Grundbibliothek: Konfiguration, Pfade, Text/Hash, Frontmatter, Abschnitte, IDs, Git-Schicht, `pkm init` | Fundament für alles Weitere | 4 |
| 2 | Vault-Modell, Adressierung, Suchindex, lesende MCP-Tools | Abfragen aus Chats | 3 |
| 3 | Schreibende MCP-Tools inkl. Versionierung und Commit | Ablegen und Aktualisieren aus Chats | 3,5 |
| 4 | Pflege-CLI: `ids`, `versions`, `pending`, `mark`, `sha`, `show`, `history`, `restore`, `index`, `status`, `reindex` | Pflege-Grundlage | 3 |
| 5 | Belege: Parser, Auflösung, `show_citations`, `fix-/sync-citations`, `lint`, `doctor` | Rückverfolgbarkeit | 4 |
| 6 | Skills `pkm-access`, `pkm-wiki`, Projekt „PKM-Pflege“, Einrichtung auf dem Mac | Erster echter Ingest-Lauf | 2 |
| 7 | Manuelle Abnahme (14), Nacharbeiten | Freigabe | 1,5 |
| 8 | Später, nur auf Anweisung: geplante Aufgabe | Automatische Verarbeitung | 0,5 |
| | | **Summe** | **≈ 22,5** |

**Umfang:** Die Spezifikation nennt „rund 550 Zeilen“ für den Server. Realistisch für Server + CLI + Belege + Lint sind **2.500–3.500 Zeilen Code** plus etwa ebenso viel Testcode. Die Schätzung oben geht davon aus.

**Kritischer Pfad:** Phase 1 (Git-Schicht, Hashes, Frontmatter) → Phase 3 (Versionierung) → Phase 4 (`pending`/`mark`) → Phase 6. Phase 2 und 5 lassen sich teilweise parallel zu 3 bzw. 4 bearbeiten.

---

## 2. Klärungen vor Beginn (Phase 0)

Beim Durcharbeiten der Spezifikation sind einige Stellen aufgefallen, die sich widersprechen oder offen lassen, wie etwas genau funktioniert. Der Plan nimmt jeweils die rechte Spalte als Arbeitsannahme; sie sollte vor Phase 1 bestätigt und in die Spezifikation (v0.11) übernommen werden.

| # | Stelle | Problem | Vorschlag |
|---|---|---|---|
| K1 | 7.2 „Protokoll in `.pkm/mcp.log`“, 7.4 „`.pkm/index.db`“ | Widerspricht 3 und 5.5 (beides in `PKM_CACHE_DIR`) | Überall `PKM_CACHE_DIR/mcp.log` und `PKM_CACHE_DIR/index.db` |
| K2 | 7.3 `history`: `source` „chat/nutzer/agent“ | Widerspricht 4.7 (`user`) | `chat` \| `user` \| `agent` |
| K3 | 5.4 „Jede Version ist genau ein Commit, der nur die eine Datei enthält“ vs. 12 `pkm: add missing ids` | Ein Sammel-Commit für viele Dokumente widerspricht der Regel und erschwert `history` | `pkm ids` committet **je Dokument** (`doc: <title> v1`, `PKM-Source: agent`). Kein Sammel-Commit |
| K4 | `hash` / `expected_hash` | Nicht definiert, worüber gehasht wird | SHA-256 über die **ganze Datei** (inkl. Frontmatter), Text in UTF-8 mit LF-Zeilenenden, ohne BOM; Ausgabe als Hex (voll). Kurz-`sha:` in Belegen = erste 6 Hex-Zeichen des Abschnitts-Hashes |
| K5 | Abschnitts-Hashes (4.6) | Text vor der ersten `##`-Überschrift und doppelte Überschriften ungeklärt | Text zwischen Frontmatter und erster `##` gilt als Abschnitt `""` (Präambel). Doppelte Überschriften erhalten Schlüssel `Name`, `Name (2)` …. Abschnitts-Hash umfasst Überschrift + Inhalt bis zur nächsten `##`, ohne abschließende Leerzeilen |
| K6 | `pkm versions` „erkennt auch Verschiebungen und committet sie mit“ | Ein Verschiebe-Commit enthält zwei Pfade | Erlaubt: Verschiebe-Commit enthält alten (gelöscht) und neuen Pfad derselben ID; zählt als eine Version nur, wenn sich der Inhalt geändert hat, sonst Commit `doc: <title> moved` ohne Versionssprung |
| K7 | `version` erhöhen bei Änderungen von Hand | `pkm versions` schreibt in eine Nutzerdatei, die gleichzeitig per Nextcloud synchronisiert werden kann | Schreibvorgang atomar, nur Zeile `version:`/`updated:` ändern; vorher auf Konfliktkopien prüfen (doctor) und Datei nicht anfassen, deren `mtime` jünger als 60 s ist (Datei wird gerade bearbeitet/synchronisiert) |
| K8 | `update_frontmatter`, Frontmatter-Erhalt | PyYAML-Roundtrip verliert Formatierung/Kommentare (Beispiel 4.1 hat Kommentare) | Serverfelder (`id`, `version`, `updated`, `created`) per **zeilengenauer Ersetzung**; `update_frontmatter` darf das Frontmatter neu serialisieren (Reihenfolge erhalten, `allow_unicode`, `sort_keys=False`). Kommentare gehen dabei verloren – im Skill erwähnen |
| K9 | Dokumente ohne `## Ergebnis` usw. | `rewrite_document`-Schutz „fehlende Ebene-2-Abschnitte“ | Vergleich über Abschnittsnamen (K5); Präambel zählt nicht |
| K10 | Kurzname-Auflösung `[[zisterne]]` | Obsidian-Regel „kürzester eindeutiger Pfad“ | Kurzname = Dateiname ohne Endung, Vergleich in NFC und ohne Groß-/Kleinschreibung; mehr als ein Treffer → `ambiguous` |
| K11 | Konfiguration auf Nicht-macOS | Tests/CI laufen auch unter Linux | Defaults abhängig von `sys.platform`; alle Pfade per Umgebungsvariable überschreibbar. Produktiv nur macOS |
| K12 | `wiki/log.md` und Agenten-Commit | Der Agent schreibt das Wiki selbst (Dateizugriff), committet aber wer? | Neuer CLI-Befehl **`pkm commit-wiki --message "…"`**: committet ausschließlich `wiki/` und `.pkm/state.json` (Pathspec), sodass offene Dokumentänderungen unberührt bleiben. Ergänzt 4.7/8 |

---

## 3. Paketaufbau

Ein Python-Paket `pkm-tools` mit zwei Einstiegspunkten (`pkm`, `pkm-mcp`), installierbar über `uvx --from <pfad>` (7.6).

```
pkm-tools/
├── pyproject.toml            # deps: mcp, pyyaml · dev: pytest, pytest-cov, ruff
├── src/pkm/
│   ├── config.py             # Umgebungsvariablen, Defaults (7.1, K11)
│   ├── paths.py              # Pfadprüfung, NFC, Slug, Konfliktkopien, Case-Kollisionen (5.5, 7.5)
│   ├── text.py               # LF-Normalisierung, Hashes (Datei, Abschnitt, kurz) (K4)
│   ├── frontmatter.py        # Parsen/Schreiben, byte-genaues Einfügen von id/version (K8)
│   ├── sections.py           # Ebene-2-Abschnitte, Anker, Präambel (K5)
│   ├── ids.py                # ID-Erzeugung d-YYYYMMDD-HHMM-xxxx (4.1)
│   ├── gitlayer.py           # git --git-dir/--work-tree, Commit mit Trailern, Log nach PKM-Id
│   ├── vault.py              # Dokumentmodell, Bestandsaufnahme, Adressierung (7.1)
│   ├── index.py              # SQLite FTS5, inkrementell (7.4)
│   ├── state.py              # state.json, pending-Berechnung (4.6, 8)
│   ├── writer.py             # gemeinsame Schreiblogik: Hash-Schutz, Versionierung, Commit, Rollback (7.2)
│   ├── citations.py          # Parser, Auflösung (5.2), fix/sync
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
    └── test_*.py
```

**Grundsatz:** Alle fachliche Logik liegt in den Bibliotheksmodulen. MCP-Server und CLI sind dünne Hüllen. `restore_document` und `pkm restore`, `history` und `pkm history` teilen sich dieselbe Funktion.

---

## 4. Phasen im Detail

### Phase 0 – Klärung und Gerüst (1 PT)

- Klärungen K1–K12 bestätigen, Spezifikation auf 0.11 heben.
- `pyproject.toml`, Ordnerstruktur, `ruff`, `pytest`.
- Test-Fixture `vault`: legt in `tmp_path` einen Vault und ein getrenntes Git-Verzeichnis an, setzt `user.name`/`user.email` lokal, `PKM_TZ=Europe/Berlin`.
- CI (GitHub Actions) auf `ubuntu-latest` und `macos-latest`, Python 3.11 und 3.12.

**Fertig, wenn:** `pytest` läuft grün mit einem Platzhaltertest auf beiden Plattformen.

### Phase 1 – Grundbibliothek (4 PT) · Spez. 15 Schritt 1

| Arbeitspaket | Inhalt | Tests |
|---|---|---|
| 1.1 `config` | `PKM_ROOT` Pflicht, übrige Defaults (7.1); `PKM_MAX_KB`, `PKM_GIT_AUTHOR` parsen | fehlendes `PKM_ROOT` → klarer Fehler |
| 1.2 `paths` | `resolve()`-Prüfung gegen `PKM_ROOT`, keine Symlinks nach außen, NFC-Normalisierung, Slug (Umlaute ausschreiben, ungültige Zeichen, reservierte Namen, ≤ 120 Zeichen, kein Punkt/Leerzeichen am Ende), Erkennung „conflicted copy“/„Konflikt“, Case-Kollisionen | `..`, absolute Pfade, Symlink nach außen, `CON.md`, NFD-Eingabe |
| 1.3 `text` | LF-Normalisierung, BOM entfernen, SHA-256, Kurz-Hash | CRLF- und LF-Datei ergeben denselben Hash |
| 1.4 `frontmatter` | Erkennen/Parsen, Feld zeilengenau setzen, Frontmatter anlegen, Rest byte-genau erhalten | Datei mit/ohne Frontmatter, Kommentare bleiben bei Serverfeldern erhalten |
| 1.5 `sections` | Split nach `##` (Codeblöcke beachten: `##` in ``` zählt nicht), Präambel, doppelte Namen, Abschnitts-Hashes | Codeblock mit `##`, doppelte Überschriften |
| 1.6 `ids` | Format, Alphabet ohne `0 1 l o`, Zeit in `PKM_TZ`, Kollisionsprüfung über Callback | Format-Regex, Kollision → neuer Versuch |
| 1.7 `gitlayer` | Aufruf immer mit `--git-dir`/`--work-tree`, Argumente fest, Pfade nach `--`; `add`+`commit --only` für genau die übergebenen Pfade; Commit-Nachricht mit Trailern `PKM-Id`/`PKM-Version`/`PKM-Source`; Autor über `--author`; `log --grep` nach ID (Ergebnis parsen inkl. Pfad je Commit über `--name-status`); `show <commit>:<pfad>`; Prüfung „Datei weicht von HEAD ab“; Erkennung „kein Git“ | Commit enthält nur die eine Datei, andere offene Änderungen bleiben offen; Verlauf nach Umbenennung vollständig; im Vault entsteht nie `.git` |
| 1.8 `pkm init` | Ordnerstruktur (3), `CLAUDE.md`-Vorlage, `wiki/index.md`, `log.md`, `_status.md`, `.pkm/state.json`, `.gitignore` (12), Git-Verzeichnis anlegen (`git init --separate-git-dir` vermeiden, da es eine `.git`-Datei im Vault erzeugt → stattdessen `git --git-dir=… init` mit `core.worktree`); idempotent; Initial-Commit | zweimal ausführen → keine Änderung; kein `.git` im Vault |

**Fertig, wenn:** alle Tests aus 14 zu Pfaden, IDs, Hashes, Plattform und getrenntem Git-Verzeichnis grün sind.

### Phase 2 – Lesen und Suche (3 PT) · Spez. 15 Schritt 2

| Arbeitspaket | Inhalt |
|---|---|
| 2.1 `vault` | Bestandsaufnahme von `documents/` und `wiki/` (Markdown und Anhänge), Dokumentmodell (Pfad, ID, Version, Titel, Frontmatter, Abschnitte, Hash), Adressierung über Pfad / Wikilink / Kurzname / `id:` (K10), Fehler `not_found`/`ambiguous` mit Kandidaten |
| 2.2 `index` | SQLite in `PKM_CACHE_DIR/index.db`, FTS5 `unicode61 remove_diacritics 2`, Spalten Titel/Aliase+Tags+Themen/Kurzfassung/Text mit `bm25`-Gewichten 5/3/2/1, Tabelle `docs(id, path, version, mtime, size, sha256)`; vor jeder Anfrage inkrementell (mtime+Größe); bei Fehler/Schemaabweichung Neuaufbau; Präfixsuche durch `*` je Term, Eingabe für FTS escapen |
| 2.3 MCP-Server | FastMCP-Grundgerüst, Logging nach `mcp.log`, einheitliche Fehlerobjekte |
| 2.4 Tools | `search` (Scope `wiki` Standard, max. 25, Feld `processed` aus `state.json`), `read` (inkl. `version` aus Git, `editable`, `sections`, `links`, `backlinks`, bei Wiki-Seiten `citations` – Parser kommt in Phase 5, bis dahin leer), `history` (Liste + Diff zwischen Versionen), `read_index`, `list_unprocessed` (nutzt `state.pending` aus Phase 4 – hier zunächst einfache Variante „Version ≠ processed_version“) |

**Tests:** Adressierung inkl. `ambiguous`, Umlaut-Toleranz („Zisterne“ findet „zisterne“, „Ueberlauf“ findet „Überlauf“), Gewichtung (Titeltreffer vor Texttreffer), inkrementelle Aktualisierung, Neuaufbau nach Löschen von `index.db`, `read` mit alter Version, lesende Tools ohne Git funktionieren.

**Fertig, wenn:** Server lässt sich lokal mit dem MCP-Inspector starten und alle lesenden Tools liefern Ergebnisse auf einem Beispiel-Vault.

### Phase 3 – Schreibende Tools (3,5 PT) · Spez. 15 Schritt 3

Kern ist `writer.apply_change(target, transform, note, source="chat")`, über den alle Tools laufen:

1. Git vorhanden und konfiguriert? Sonst Fehler (5.4).
2. Ziel auflösen, Schreibrecht prüfen (nur `documents/**/*.md`; Neuanlage nur `_inbox/`).
3. `expected_hash` gegen aktuellen Datei-Hash → sonst `conflict` mit neuem Hash.
4. Weicht die Datei vom letzten Commit ab (Änderung von Hand), zuerst diesen Stand als eigene Version committen (`version` +1, `PKM-Source: user`).
5. Transformation anwenden, `PKM_MAX_KB` prüfen, `version` +1, `updated` setzen.
6. Atomar schreiben (temporäre Datei im selben Ordner + `os.replace`).
7. Commit nur dieser Datei. Bei Fehler: alte Bytes zurückschreiben, Index-Eintrag zurücksetzen (`git restore --staged`), Fehler melden.
8. Rückgabe `{id, path, status, version, new_hash, commit, diff}` (Diff ≤ 80 Zeilen), Protokolleintrag.

| Tool | Besonderheiten |
|---|---|
| `create_document` | Frontmatter im `content` entfernen, Slug + `YYYY-MM-DD_`, Suffix `-2`, `-3` bei Namensgleichheit, `related` auflösen und als Wikilinks speichern, `version: 1`, Commit `doc: <title> v1` |
| `rewrite_document` | Schutz `large_shortening` (< 60 % Länge oder fehlende Abschnitte, K9), Liste betroffener Abschnitte, `confirm_shortening` |
| `append_to_document` | Einfügen am Ende eines Abschnitts / neuen `##`-Abschnitt anlegen / Dateiende |
| `edit_document` | `old` genau einmal außerhalb des Frontmatters, sonst `not_found` bzw. `ambiguous` mit Anzahl |
| `update_frontmatter` | `set`/`add`/`remove`, geschützte Felder abweisen |
| `restore_document` | Inhalt unterhalb des Frontmatters aus Version n; Frontmatter aktuell lassen, Serverfelder aktualisieren; Notiz `wiederhergestellt aus v<n>` |

**Tests (14):** jede Operation → `version` +1 und genau ein Commit nur dieser Datei mit korrekten Trailern; Handänderung wird vorher separat committet; Commit-Fehler (z. B. per Hook simuliert) setzt Datei zurück; `wiki/`, `CLAUDE.md`, PDF, Pfade außerhalb immer abgelehnt; Hash-Konflikt; `large_shortening` und Bestätigung; geschützte Felder; ohne Git verweigert.

**Fertig, wenn:** Abnahmeschritte 1, 4, 5 aus 14 im Test-Vault per MCP-Inspector durchspielbar sind.

### Phase 4 – Pflege-CLI (3 PT) · Spez. 15 Schritt 4

| Befehl | Kernlogik |
|---|---|
| `pkm ids` | Markdown ohne `id`/`version` finden, Frontmatter ergänzen (Rest byte-genau), je Dokument ein Commit (K3); doppelte IDs nur melden |
| `pkm versions` | `git status` des Work-Trees für `documents/`: geänderte Markdown-Dateien → je Datei `version` +1 und Commit (`PKM-Source: user`); Verschiebungen über ID (Markdown) bzw. Hash (Anhänge) erkennen (K6); Konfliktkopien und gerade bearbeitete Dateien überspringen (K7) |
| `pkm pending` | Abgleich Bestand ↔ `state.json`: `new`, `changed` (mit `processed_version` → `version` und geänderten Abschnitten über Abschnitts-Hashes), `moved`, `deleted` (mit `wiki_pages`); JSON-Ausgabe |
| `pkm mark` | Version, Datei- und Abschnitts-Hashes, `processed_at`, `wiki_pages` in `state.json` |
| `pkm sha` | Kurz-Hash für Abschnitt oder Datei (für neue Belege) |
| `pkm show`, `pkm history`, `pkm restore` | wie MCP, gemeinsame Funktionen |
| `pkm index`, `pkm status` | `wiki/index.md` (gruppiert nach `type`, Kurzfassung, Quellenzahl, Datum), `wiki/_status.md` inkl. Einsortier-Vorschlag (Ordner, in dem die meisten Dokumente mit gleichen `topics` liegen) |
| `pkm reindex` | Index neu aufbauen |
| `pkm commit-wiki` | Agenten-Commit nur für `wiki/` und `.pkm/state.json` (K12) |

`list_unprocessed` im MCP-Server wird auf `state.pending` umgestellt.

**Tests:** `pending` für neu, geändert (mit Abschnitten), verschoben per ID, verschoben per Hash, verschoben *und* geändert, gelöscht; `versions` fasst mehrere Handänderungen zu einer Version zusammen; `ids` byte-genau.

### Phase 5 – Belege, Lint, Doctor (4 PT) · Spez. 15 Schritt 5

| Arbeitspaket | Inhalt |
|---|---|
| 5.1 Parser | Fußnotenzeilen nach 4.2 (Regex für `[[pfad#anker]]`, `„…“`, `id:`, `v:`, `sha:`, `#page=n`), Zuordnung Fußnote ↔ Absatz/Aussage |
| 5.2 Auflösung | Reihenfolge nach 5.2; Status `ok`/`moved`/`newer_version`/`missing` über Abschnitts-Hash der belegten vs. aktuellen Version (alte Version aus Git) |
| 5.3 `show_citations` | Filter `statement`, `with_excerpt` (≤ 1.500 Zeichen je Auszug, belegte und aktuelle Version), `obsidian://`-Link wenn `PKM_VAULT_NAME` gesetzt; `read` liefert jetzt auch `citations` |
| 5.4 `fix-citations` | Link-Pfade in Fußnoten und `sources` auf aktuelle Orte umschreiben (nur `wiki/`) |
| 5.5 `sync-citations` | `sources` aus Fußnoten erzeugen (eindeutig, sortiert, Wikilinks) |
| 5.6 `lint` | Alle Prüfungen aus 8 (Struktur, Belege, Dokumente, Plattform), JSON-Bericht mit Schweregrad; jede Prüfung als eigene Funktion, damit sie einzeln testbar ist |
| 5.7 `doctor` | Umgebungsprüfungen aus 8, `--short` |

**Tests:** jede Lint-Prüfung positiv und negativ; alle Status von `show_citations`; Auszug aus alter und aktueller Version; Zitat-Prüfung gegen belegte Version; Beleg auf Wiki-Seite wird gemeldet.

### Phase 6 – Skills, Projekt, Einrichtung (2 PT) · Spez. 15 Schritt 6

- **`skills/pkm-access/SKILL.md`** (schlank): Trigger aus 10; Grundregel „immer erst Entwurf, keine Ausnahme“; Abläufe Ablegen, Fortsetzen (6.2 Standard, 6.3 nur auf Anweisung), kleine Änderungen, Verlauf, Abfragen, Quellen, Korrekturen; Umgang mit `conflict` und `large_shortening`.
- **`skills/pkm-wiki/SKILL.md`**: Abläufe Ingest (9.1, Schritt für Schritt mit CLI-Aufrufen), Lint (9.2), Abfrage (9.3), Schema (9.4), feste Regeln (9.5), Beleg-Format mit Beispiel, Verhalten im unbeaufsichtigten Lauf.
- **`CLAUDE.md`-Vorlage** im Vault (über `pkm init`): Konventionen aus 4 und 9.5 in Kurzform.
- **Einrichtungsanleitung** `docs/einrichtung.md`: `uv` installieren, Git-Identität, `pkm init`, `claude_desktop_config.json` (7.6), Skills installieren, Projekt „PKM-Pflege“ anlegen und Vault-Ordner verbinden, Obsidian-Einstellungen (13), optional Nextcloud-Ausschluss `.obsidian/workspace*.json`.
- **Probelauf** mit 3–5 selbst angelegten Dokumenten (keine Startbefüllung, 16 Nr. 7).

### Phase 7 – Abnahme (1,5 PT)

Abnahmeschritte 1–10 aus 14 auf dem Mac mit echtem Nextcloud-Vault und Windows-Rechner durchgehen, Ergebnis je Schritt protokollieren (`docs/abnahme.md`). Fehler beheben, Skills nachschärfen (Formulierungen, die der Agent falsch versteht).

### Phase 8 – Automatik (später, 0,5 PT)

Erst auf ausdrückliche Anweisung: geplante Aufgabe „Ingest, danach Lint“ im Projekt. Voraussetzung: mehrere manuelle Läufe ohne Nacharbeit.

---

## 5. Teststrategie

- **Einheitstests** je Modul (Phase 1, 5).
- **Integrationstests** mit echtem `git` in temporären Verzeichnissen; jede Schreiboperation prüft anschließend `git log`, `git show --name-only` und den Datei-Inhalt.
- **MCP-Tests** über die Tool-Funktionen direkt (ohne stdio) plus ein Rauchtest, der `pkm-mcp` per stdio startet und `tools/list` abfragt.
- **Plattformtests:** NFD-Dateinamen, CRLF, Case-Kollisionen (auf Linux nachstellbar), Konfliktkopien.
- **Golden Files** für `index.md`, `_status.md`, Lint-Bericht.
- Zielabdeckung ≥ 85 % für `writer`, `gitlayer`, `state`, `citations`.
- Testliste aus Spezifikation 14 wird als Checkliste in den Testdateien geführt (Docstring mit Verweis).

---

## 6. Risiken und Gegenmaßnahmen

| Risiko | Auswirkung | Gegenmaßnahme |
|---|---|---|
| Nextcloud synchronisiert während eines Schreibvorgangs | Konfliktkopie, doppelte ID | atomares Schreiben, Hash-Schutz, `doctor`/`lint` melden Konfliktkopien, Pflegelauf bricht ab (9.1) |
| `pkm versions` ändert eine Datei, die gerade auf Windows bearbeitet wird | Konflikt | mtime-Schonfrist (K7), nur zwei Zeilen ändern |
| Git-Verzeichnis außerhalb des Vaults geht verloren | Verlauf weg, Belege `v:` nicht mehr prüfbar | Time Machine (12), `doctor` prüft Erreichbarkeit; später optional Remote |
| Claude Desktop startet MCP mit minimalem `PATH` | `git` nicht gefunden | absoluter `uvx`-Pfad, `PATH` in Config (7.6), klare Fehlermeldung, `doctor` |
| LLM hält Beleg-Format oder Regeln nicht ein | fehlerhafte Belege | `lint` als harte Kontrolle am Ende jedes Ingest, Skill mit Beispielen |
| Frontmatter-Formatierung geht beim Neuschreiben verloren | Unruhe in Diffs | zeilengenaue Ersetzung der Serverfelder (K8) |
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
| 5.1–5.2 Zuordnung, Auflösung | 2, 5 |
| 5.4 Versionen/Commits | 1, 3, 4 |
| 5.5 Nextcloud/Plattform | 1, 5 |
| 6 Fortgeführte Diskussionen | 3, 6 |
| 7.1–7.6 MCP | 2, 3, 6 |
| 8 CLI | 1, 4, 5 |
| 9, 10, 11 Skills, Projekt | 6, 8 |
| 13 Obsidian | 6 |
| 14 Tests/Abnahme | durchgehend, 7 |

---

## 8. Nächste Schritte

1. Klärungen K1–K12 durchsehen und bestätigen bzw. korrigieren.
2. Phase 0 starten: Paketgerüst und Test-Fixture.
3. Phase 1 als erster größerer Meilenstein; danach kurzer Review der Git-Schicht, weil alle weiteren Phasen darauf aufbauen.
