# PKM – Schema und Regeln

Dieser Ordner ist ein persönliches Wissensmanagement (PKM) mit LLM-Wiki. Die Pflege
übernimmt der Skill `pkm-wiki` im Claude-Projekt „PKM-Pflege“. Änderungen an dieser Datei
nur nach Zustimmung des Nutzers.

## Bereiche und Besitz

| Bereich | Gehört | Wer schreibt |
|---|---|---|
| `documents/` (inkl. `_inbox/`, `_attachments/`) | Nutzer | Nutzer (Obsidian), pkm-mcp auf Anweisung des Nutzers; der Agent nur `id`/`version` über `pkm ids`/`pkm versions` |
| `wiki/` | Pflege-Agent | nur der Agent; aus Chats nur lesbar |
| `.pkm/state.json` | Pflege-Agent | `pkm mark` |
| `CLAUDE.md` | Nutzer | Agent nur nach Zustimmung |

Neue Dokumente aus Chats und vom Web Clipper landen in `documents/_inbox/`. Einsortiert wird
frei in Obsidian; Dokumente werden über ihre ID gefunden, nicht über den Pfad.

## Dokumente

- Frontmatter-Pflichtfelder: `id` (`d-YYYYMMDD-HHMM-xxxx`) und `version` (ab 1).
- Optional: `title`, `created`, `updated`, `source`, `context`, `topics`, `related`,
  `kind` (`note` | `correction`).
- `id`, `version`, `created`, `updated` setzen nur pkm-mcp bzw. die `pkm`-CLI.
- Jede Version ist genau ein Git-Commit mit den Zeilen `PKM-Id`, `PKM-Version`,
  `PKM-Source` (`chat` | `user` | `agent`). Der Verlauf liegt in Git, nicht im Dokument.
- Empfohlene Gliederung für Chat-Ergebnisse: `## Ergebnis`, `## Entscheidungen`,
  `## Offene Punkte`, `## Kontext / Begründung`. Fortsetzungen aktualisieren diese Abschnitte.
- Abschnitte sind Überschriften der Ebene 1 und 2 (`#`, `##`). Doppelte Überschriften, die
  Zeichen `# ^ [ ] |` und Überschriften, die auf `#` plus Ziffern enden („Version#2“ →
  besser „Version 2“), vermeiden.

## Wiki

- Seitentypen: `wiki/topics/` (topic), `wiki/entities/` (entity), `wiki/summaries/` (summary,
  eine Seite je Dokument), `wiki/syntheses/` (synthesis).
- Frontmatter: `type`, `title`, `aliases`, `tags`, `sources` (erzeugt), `updated`,
  `confidence` (`high` | `medium` | `low`).
- Erste Zeile nach dem Frontmatter: `> **Kurzfassung:** …`
- Jede Sachaussage in „Inhalt“ und „Widersprüche / offene Fragen“ endet mit einer Fußnote auf
  ein Dokument in `documents/`:
  `[^b1]: [[<pfad>#<anker>]] · „<zitat>“ · id:<id> · v:<version> · sha:<6 zeichen>`
  (PDF/Bild: `[[<pfad>.pdf#page=<n>]] · „<zitat>“ · sha:<6 zeichen>`).
- Wiki-Seiten gelten nicht als Beleg. Nichts erfinden, Lücken als offene Frage markieren.
- Im Wiki wird nichts gelöscht; überholte Aussagen behalten ihren Beleg auf die alte Version.
- Generiert, nicht von Hand ändern: `wiki/index.md`, `wiki/_status.md`, `sources`.
- `wiki/log.md` wird nur angehängt.

## Sprache

Inhalte, Überschriften, Änderungsnotizen und Berichte: Deutsch. Schnittstellen (Felder,
Werte, Tools, CLI): Englisch.
