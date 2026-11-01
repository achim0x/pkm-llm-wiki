# PKM – Schema und Regeln

Dieses Verzeichnis ist ein persönliches Wissensmanagement (PKM) mit LLM-Wiki.

## Bereiche
- `documents/` gehört dem Nutzer. Neue Dokumente aus Chats landen in `documents/_inbox/`.
- `wiki/` gehört dem Pflege-Agenten (Skill `pkm-wiki`). Aus Chats nur lesbar.
- `.pkm/state.json` hält den Verarbeitungsstand.

## Dokumente
- Pflichtfelder im Frontmatter: `id` (`d-YYYYMMDD-HHMM-xxxx`) und `version` (ab 1).
- `id`, `version`, `created`, `updated` setzen nur pkm-mcp bzw. die `pkm`-CLI.
- Jede Version ist genau ein Git-Commit (`PKM-Id`, `PKM-Version`, `PKM-Source`).

## Wiki
- Jede Sachaussage endet mit einer Fußnote auf ein Dokument in `documents/`:
  `[^b1]: [[<pfad>#<anker>]] · „<zitat>“ · id:<id> · v:<version> · sha:<6 zeichen>`
- Wiki-Seiten gelten nicht als Beleg. Nichts erfinden, Lücken als offene Frage markieren.
- Sprache: Deutsch. Schnittstellen-Namen englisch.

Änderungen an dieser Datei nur nach Zustimmung des Nutzers.
