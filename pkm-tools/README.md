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
| 5–8 | Belege, Skills, Abnahme | offen |

**MCP-Tools:** `search`, `read`, `history`, `read_index`, `list_unprocessed`, `create_document`,
`rewrite_document`, `append_to_document`, `edit_document`, `update_frontmatter`, `restore_document`.
`show_citations` folgt mit Phase 5.

**CLI:** `pkm init`, `ids`, `versions`, `pending`, `mark <id>… [--pages <page>…] [--remove]`,
`sha <target> [--section <key>] [--full]`, `index`, `status [--question <text>]…`,
`commit-wiki -m <text>`, `history <target> [--diff <von> [<bis>]]`,
`show <target> --version <n> [--section <key>]`, `restore <target> --version <n>`, `reindex`.

## Abweichungen und Ergänzungen zur Spezifikation

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
- Alle schreibenden Vorgänge (MCP und CLI) sind über eine Sperrdatei im Git-Verzeichnis
  serialisiert.

## Entwicklung

```bash
cd pkm-tools
pip install -e ".[dev]"
pytest
ruff check .
```

Die Tests laufen auch unter Linux. Alle Pfade werden über Umgebungsvariablen gesetzt
(`PKM_ROOT`, `PKM_GIT_DIR`, `PKM_CACHE_DIR`, …), siehe Spezifikation 7.1.
