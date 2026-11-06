# PKM – schema and rules

This folder is a personal knowledge management (PKM) system with an LLM wiki. Maintenance is
done by the skill `pkm-wiki` in the Claude project "PKM-Pflege". Change this file only with
the user's consent.

## Areas and ownership

| Area | Owned by | Who writes |
|---|---|---|
| `documents/` (incl. `_inbox/`, `_attachments/`) | user | user (Obsidian), pkm-mcp on the user's instruction; the agent `id`/`version` via `pkm ids`/`pkm versions` as well as `title`, `context`, `tags`, `kind`, `short_citation` after the user's confirmation |
| `wiki/` | maintenance agent | the agent only; read-only from chats |
| `scratch/` | user | user (Obsidian), pkm-mcp on instruction; without version and commit, never in the wiki, not in Git |
| `.pkm/state.json` | maintenance agent | `pkm mark` |
| `CLAUDE.md` | user | the agent only with consent; `pkm versions` records changes as a user commit |

New documents from chats and from the Web Clipper land in `documents/_inbox/`. Filing is done
freely in Obsidian; documents are found by their ID, not by their path.

## Documents

- Required frontmatter fields: `id` (`d-YYYYMMDD-HHMM-xxxx`) and `version` (from 1).
- Further fields (schema of the digitized standards, first in this order): `title`,
  `short_citation`, `date_document`, `status_markdown`, `date_markdown`, `toolchain_markdown`;
  then `id`, `version`, `date_updated`, `context`, `tags`, `related`,
  `kind` (`note` | `standard` | `regulation` | `correction`).
- `id`, `version`, `date_markdown`, `date_updated` are set only by pkm-mcp or the `pkm` CLI.
  `status_markdown` is taken over unchanged and changed by no tool.
- `context`: one line "<kind>: <content>" (kind: chat, podcast, book, article, research, note).
  `tags`: 4–8, lower case, hyphens, umlauts spelled out, reuse existing ones.
  If they are missing in new documents, the maintenance agent proposes values and enters them
  only after confirmation.
- Date fields `date_markdown`/`date_updated`: `YYYY-MM-DDTHH:MM:SS` in local time without time zone.
- Field names without spaces. Put values with `: ` or a leading YAML special character in double
  quotes. `source` is reserved for the Web Clipper.
- Every version is exactly one Git commit with the lines `PKM-Id`, `PKM-Version`,
  `PKM-Source` (`chat` | `user` | `agent`). The history lives in Git, not in the document.
- Images (4.9): PNG, JPEG and SVG (diagrams as SVG). Handover from the chat via `pkm_img_import/`
  (not in Git, never in the wiki). Up to 24 KB embedded as a data URI with the title
  `"pkm:<name>"`, larger ones as a file in `documents/_attachments/`. Every new image has an
  alt text. Existing embedded PNGs stay unchanged. Citations of images quote
  `[img:<name>]`.
- Recommended structure for chat results: `## Result`, `## Decisions`,
  `## Open points`, `## Context / rationale` – or, with the document language German
  (`PKM_LANGUAGE = "de"`), `## Ergebnis`, `## Entscheidungen`, `## Offene Punkte`,
  `## Kontext / Begründung`. Continuations update these sections and keep their language.
- Sections are headings of level 1 and 2 (`#`, `##`). Avoid duplicate headings, the
  characters `# ^ [ ] |` and headings that end in `#` plus digits ("Version#2" →
  better "Version 2").

## Wiki

- Page types: `wiki/topics/` (topic), `wiki/entities/` (entity), `wiki/summaries/` (summary,
  one page per document), `wiki/syntheses/` (synthesis).
- Frontmatter: `type`, `title`, `aliases`, `tags`, `sources` (generated), `date_updated`,
  `confidence` (`high` | `medium` | `low`).
- First line after the frontmatter: `> **Summary:** …`
- Every factual statement in "Content" and "Contradictions / open questions" ends with a
  footnote to a document in `documents/`:
  `[^b1]: [[<path>#<anchor>]] · "<quote>" · id:<id> · v:<version> · sha:<6 characters>`
  (PDF/image: `[[<path>.pdf#page=<n>]] · "<quote>" · sha:<6 characters>`).
- Wiki pages do not count as citations. Invent nothing, mark gaps as open questions.
- Nothing is deleted in the wiki; outdated statements keep their citation of the old version.
- Generated, do not change by hand: `wiki/index.md`, `wiki/_status.md`, `sources`.
- `wiki/log.md` is append-only.

## Language

Content, headings, change notes and reports: English. Interfaces (fields, values, tools,
CLI): English.
