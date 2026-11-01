# pkm-tools

MCP-Server `pkm-mcp` und CLI `pkm` für das PKM mit LLM-Wiki.
Grundlage: [Spezifikation](../docs/spezifikation.md), [Umsetzungsplan](../docs/umsetzungsplan.md).

## Stand

| Phase | Inhalt | Stand |
|---|---|---|
| 0 | Gerüst, Tests, CI | fertig |
| 1 | Normalisierung/Abschnitte/Hashes (4.8), Frontmatter, IDs, Git-Schicht, `pkm init` | fertig |
| 2 | Adressierung, Suchindex, lesende MCP-Tools | fertig |
| 3 | Schreibende MCP-Tools mit Versionierung | fertig |
| 4 | Pflege-CLI | fertig |
| 5 | Belege, `lint`, `doctor` | fertig |
| 6 | Skills, Vault-Vorlage, Einrichtungsanleitung | fertig |
| 7 | Abnahme: Protokoll und Simulation fertig, Durchführung auf dem Mac offen | in Arbeit |
| 8 | Automatik (geplante Aufgabe), nur auf Anweisung | offen |

**MCP-Tools:** `search`, `read`, `history`, `read_index`, `list_unprocessed`, `create_document`,
`rewrite_document`, `append_to_document`, `edit_document`, `update_frontmatter`, `restore_document`,
`show_citations`.

**CLI:** `pkm init`, `ids`, `versions`, `pending`, `mark <id>… [--pages <page>…] [--remove]`,
`sha <target> [--section <key>] [--full]`, `index`, `status [--question <text>]…`,
`commit-wiki -m <text>`, `history <target> [--diff <von> [<bis>]]`,
`show <target> --version <n> [--section <key>]`, `restore <target> --version <n>`, `reindex`,
`fix-citations [<page>…]`, `sync-citations [<page>…]`, `lint [--report]`, `doctor [--short]`.

**Skills:** `skills/pkm-access/SKILL.md` (normale Chats), `skills/pkm-wiki/SKILL.md` (Pflegeprojekt).
**Einrichtung:** [docs/einrichtung.md](../docs/einrichtung.md). **Abnahme:** [docs/abnahme.md](../docs/abnahme.md)
(Simulation der Schritte 1–9 und 11: `tests/test_acceptance_simulation.py`; Schritt 10 und alle
`scratch/`-Fälle: `tests/test_scratch.py`).

## Abweichungen und Ergänzungen zur Spezifikation

- Fehlt `PKM_ROOT`, sucht die CLI den Vault vom aktuellen Ordner aufwärts (erster Ordner mit
  `.pkm/state.json`). Der MCP-Server braucht `PKM_ROOT` weiterhin in seiner Konfiguration.

- Das `mcp`-SDK 2.x heißt `MCPServer` statt `FastMCP`; der Server unterstützt beide Versionen.
- Ändert ein Aufruf nichts (z. B. `edit_document` mit `old == new`), kommt `status: unchanged`
  ohne neue Version und ohne Commit.
- Zusätzliche Fehlerwerte: `forbidden` (Ziel nicht änderbar), `protected_field`, `too_large`,
  `git_unavailable`, `commit_failed`, `index_unavailable`, `invalid_argument`, `invalid_path`.
- Ändert der MCP-Server ein Dokument ohne ID (von Hand angelegt), vergibt er zuerst ID und
  Version 1 und committet diesen Stand mit `PKM-Source: user`.
- `pkm versions` committet auch Anhänge (neu, per Hash verschoben, gelöscht) und gelöschte
  Dokumente, damit der Arbeitsbaum sauber bleibt. Anhänge haben keine `PKM-Id`.
- `pkm mark --remove <key>` entfernt Einträge aus `state.json` (z. B. nach Verarbeitung eines
  gelöschten Dokuments). `pkm status --question` nimmt Rückfragen in `_status.md` auf.
- `show_citations` mit `statement`: Liegt das Textstück vor einer Fußnotengruppe, werden nur diese
  Belege geliefert, sonst die des ganzen Absatzes.
- Status von Belegen: `missing` vor `newer_version` vor `moved` vor `ok`. Ist ein Original verschoben
  *und* geändert, ist der Status `newer_version`; `lint` meldet zusätzlich `citation_moved`.
- Belegpflicht prüft `lint` in den Abschnitten „Inhalt“ und „Widersprüche / offene Fragen“
  (`citations.CONTENT_SECTIONS`).
- `pkm lint --report` schreibt den Bericht nach `wiki/_lint/YYYY-MM-DD.md`. `pkm doctor` warnt
  zusätzlich, wenn `commit.gpgsign` aktiv ist.
- Alle schreibenden Vorgänge (MCP und CLI) sind über eine Sperrdatei im Git-Verzeichnis
  serialisiert.

## Entwicklung

Alle Python-Befehle laufen in einer projektlokalen `.venv` (nie im System-Python):

```bash
cd pkm-tools
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
```

Prüfen vor jedem Commit:

```bash
./.venv/bin/python -m ruff check .
./.venv/bin/python -m pylint --rcfile=.pylintrc src tests
./.venv/bin/python -m pytest -q
```

### Coding-Standard

- PEP 8, Typannotationen, Zeilenlänge 120.
- pylint ohne Warnungen und Fehler mit der `.pylintrc` im Paket (Google-Stil).
- Jede Python-Datei beginnt mit Modul-Docstring (inkl. `Author`), GPL-Lizenzkopf und den
  Abschnitten `Imports`, `Variables`, `Classes`, `Functions`, `Main` in dieser Reihenfolge.
- Docstrings für Module, Klassen, Funktionen und Methoden mit `Args`/`Returns`
  (Testfunktionen: ein Satz, was geprüft wird).
- Genau ein `return` je Funktion bzw. Methode.
- Wenige, begründete `pylint: disable` nur dort, wo die Schnittstelle der Spezifikation es
  erzwingt (z. B. zehn Parameter von `create_document`, Parametername `set`) oder bei
  Datenklassen mit vielen Feldern.

Die Tests laufen auch unter Linux. Alle Pfade werden über Umgebungsvariablen gesetzt
(`PKM_ROOT`, `PKM_GIT_DIR`, `PKM_CACHE_DIR`, …), siehe Spezifikation 7.1.

## Lizenz

GNU General Public License v3.0 oder später, siehe [LICENSE](LICENSE).
