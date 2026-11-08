---
name: pkm-wiki
description: Maintenance of the PKM wiki via the MCP server "pkm-maintenance" (project "PKM Maintenance") – process new and changed documents (ingest), lint, wiki questions in the maintenance project, adjust the schema. Use for "process new documents", "ingest", "lint", "check the wiki", "what does the wiki say about …" in the maintenance project.
---

# Maintaining the PKM wiki

You work with the tools of the MCP server **`pkm-maintenance`**. It runs on the user's PKM host;
you need neither a shell nor the CLI `pkm` (there is none in Cowork).

| Tool | Purpose |
|---|---|
| `begin_maintenance` | Preparation: check the environment, manual changes as versions, missing IDs, `pending` (new documents with `missing_fields`), `known_tags`, fix citations of moved documents |
| `read`, `history`, `search`, `read_index`, `show_citations`, `list_unprocessed` | Read documents, versions, diffs and wiki pages |
| `read_image` | View images (PNG as an image, SVG as text) |
| `write_wiki_page` | Create or completely replace a wiki page (without commit) |
| `set_document_metadata` | Only after confirmation: enter `title`, `context`, `tags`, `kind`, `short_citation` of a document |
| `rename_document` | Only after confirmation: rename a document after the naming rules (inbox, or a name with capitals/spaces elsewhere), with its image files |
| `move_images` | Only after confirmation: move the image files of a document into `<document name>_img/` next to it, optionally with new alt texts (`alt_texts`) |
| `fix_images` | Only after confirmation: fix the notation of nonconforming image data URIs of a document |
| `extract_images` | Only after confirmation: store large embedded images of a document as files in `<document name>_img/` (same as `fix_images` with `extract: true`) |
| `finish_maintenance` | Finish: citations (moved, renamed, `v:` raised for unchanged sections), `sources`, processing state, log, index, status, lint, agent commit |

**Version:** `begin_maintenance` returns `tools_version` (installed pkm-tools). If a tool lacks a
parameter this skill names, the client shows an older tool list: tell the user the version and to restart
Claude Desktop (in Cowork reconnect the computer). For storing images as files use `extract_images`.

**Language:** `begin_maintenance` returns the **wiki language** under `wiki_language` (`code`, `name`,
`summary_label`, `sections`; set during installation, `PKM_LANGUAGE`); the server instructions name it
too, but do not reach you in every client. New wiki pages and summaries, the log entry and the report
are written in it, with these names:

| | English (`en`) | German (`de`) |
|---|---|---|
| First line | `> **Summary:** …` | `> **Kurzfassung:** …` |
| Sections | `## Content`, `## Contradictions / open questions`, `## See also`, `## Citations` | `## Inhalt`, `## Widersprüche / offene Fragen`, `## Siehe auch`, `## Belege` |

When you update an existing page, keep its language and section names (do not mix languages on
one page). Quotes in citations stay literal, in the language of the document. Field names,
values and tool parameters stay English.

## Fixed rules

- Version control with Git is optional. Without it (`history` and `read` with `version` return
  `not_versioned`, `finish_maintenance` makes no commit) the flows stay the same; old versions
  simply cannot be read.

- `wiki/` belongs to you. `documents/` belongs to the user: change, move or delete **nothing**
  there. `id`/`version` are set by `begin_maintenance`. The only other exception: `title`,
  `context`, `tags`, `kind`, `short_citation` – only after **explicit confirmation** by the
  user in the chat and only with `set_document_metadata` (see "Frontmatter proposals"). You do not
  use the document tools of the server `pkm` (`create_document`, `edit_document`, `update_frontmatter` …)
  in maintenance. Likewise only after confirmation: the image notation with `fix_images`
  (see "Fixing data URIs") the name of a document with `rename_document`
  and the place of image files with `move_images` (see "Names and image locations").
- `scratch/` (short-lived notes, todo lists) is **neither read nor processed**. No
  citation points to a file there. If a note is moved to `documents/`, it is a new document in the
  next run; moved from `documents/` to `scratch/` it acts like a deletion.
- **Delete nothing** in the wiki. Add, update or mark statements and citations as
  outdated.
- **No statement without a citation** of a document in `documents/`. Wiki pages are not citations.
  Copy quotes **literally** from the given version. Invent nothing; mark gaps as open
  questions.
- **Source fidelity** (see the section of that name): state only what the sources say; never
  combine statements from different documents into a new claim.
- Change `CLAUDE.md` only with the user's consent.
- Leave `status_markdown` unchanged. The value plays no role in processing.
- If lint reports `invalid_frontmatter`, propose the command `pkm fix-frontmatter` to the user
  (they run it themselves in the terminal).
- Documents with `kind: standard` or `regulation` are processed like `note`. In citations and
  summaries of standards name the short citation (`short_citation`).
- `wiki/index.md`, `wiki/_status.md`, `wiki/log.md` and `sources` in the frontmatter are generated by
  `finish_maintenance`; `write_wiki_page` rejects these files.

## Frontmatter proposals

For every **new** document check the frontmatter (`missing_fields` from `begin_maintenance`,
also thin values). Proposals as a YAML block in the report, **do not enter anything yet**:

- `title`: a descriptive title.
- `context`: one line `"<kind>: <content>"` (kind: chat, podcast, book, article, research, note),
  in double quotes because of `: `.
- `tags`: 4–8, lower case, hyphens, umlauts spelled out; reuse existing tags from
  `known_tags`.
- `kind`: `note` (default) | `standard` / `regulation` (then also propose `short_citation`) |
  `correction`.

After explicit confirmation: `read` → `hash` → `set_document_metadata` (`set` with the
confirmed fields, `add` only for further `tags`). Do not overwrite existing values;
`overwrite: true` only if the user explicitly wants it. On `conflict` read again and tell the
user; on `field_exists` name the existing value and ask. Every entry
is a new version of the document; in the next run it appears as `meta_changed`.

## Names and image locations

**Conventions:** new documents are named `<slug>_YYYY-MM-DD.md` (slug from the title: lower case,
hyphens, umlauts spelled out; date = `date_markdown`). Image files of a document live in
`<document name>_img/` next to it, named after their alt text (`<alt-text-slug>_YYYY-MM-DD.png`),
linked relative to the document (`./<document name>_img/…`). `documents/_attachments/` only holds old
files.

**Names in the inbox:** for a **new** Markdown document in `documents/_inbox/` whose name does not
follow the convention (copied in by hand, from Obsidian, a conversion …), `begin_maintenance` returns a
proposal under `pending.new[].rename`: `to` (new path), `images_moved` (its image files move into
`<new name>_img/`, generic names like `IMG_013.png` get names from the alt text), `kept` (files other
documents link to as well stay), `links` (adjusted image links), `linked_from` (documents whose
wikilinks point to it; they are not changed – name them), `cited_by` and `citations` (wiki pages with
citations of it and their number), `linked_by_wiki` (wiki pages with plain wikilinks to it or to its
image files, e.g. "See also"; with a `warning`) and `regenerated` (generated files like `wiki/_status`
that are written anew anyway – no action). The renaming does not change wiki pages: citations follow
via the document ID in `finish_maintenance` (and in the next `begin_maintenance`); the plain wikilinks
from `linked_by_wiki` you fix yourself with `write_wiki_page` after the renaming. `move_images` names
wiki pages linking a moved image file the same way. Lint reports the same as `naming`
(kinds `document`, `folder`, `images`).

**Image locations:** lint `image_location` names documents whose image files lie outside
`<document name>_img/` (old files in `documents/_attachments/`, folders like `images/`, or an image
folder left behind in `_inbox/` after the user filed the document – Obsidian does not move it). If the
name of the document itself breaks the rules (capitals, spaces, underscores, e.g.
`Ultimate_Workshop_Exercise_Encyclopedia.md`), the hint has `tool: rename_document` and a
`suggested_name`: propose renaming the document; its images move along into the new image folder.
Otherwise `tool: move_images`.

**Generic image names:** image files like `IMG_066.png` whose alt text says nothing ("Image") keep
their names (`generic_names_kept` with a `hint`). View them with `read_image`, propose alt texts and,
after confirmation, pass them as `alt_texts` (`{file path, file name or image name: alt text}`) to
`move_images` or `rename_document`. Lint `generic_alt_text` names per image the `file`, the `section`,
`file_keeps_generic_name` (the file stays generic, as in `generic_names_kept`) and `name_from_other_link`
(another link with a meaningful alt text already names the file). With `alt_texts` alt text and file name are set in the same step (a new version with content
changes, so process the document in the next run).

**Propose, do not ask where to file:** list the proposals in the report like the frontmatter proposals
(old name → new name, image folder, number of renamed image files, affected links). The user files
documents from `_inbox/` themselves; you only propose names and image moves. After **explicit
confirmation**: `read` → `hash` → `rename_document` (another name with `name`) or `move_images`
without `apply` (check the proposal) → with `apply: true`. Never unattended; put the
proposals into `questions`. In the next run the document has `image_notation_only: true` (only the
image links changed): process nothing, only list it in `processed`. If a renamed document was already
processed, call `finish_maintenance` with `operation: fix` and its ID in `processed`; the citations
follow the new path.

## Fixing data URIs

For new and changed documents `begin_maintenance` returns `image_issues` if embedded images
do not conform to the form (e.g. reference style, unencoded characters in the SVG, missing name or
alt text). In the report name per image: location (section, line), findings in words, proposal
(name, alt text, embedded or file, for SVG the sanitized image and the removed parts) and
ask whether it should be fixed. If an alt text is missing, propose one and have it confirmed.

After **explicit confirmation**: `read` → `hash` → `fix_images` without `apply` (check proposal and diff)
→ `fix_images` with `apply: true` and `image_alt`. On `conflict` read again and report. Name
findings that cannot be fixed (`fixable: false`) as an open question. The fix is a new version;
in the next run the document has `image_notation_only: true` and needs no reprocessing
(still list it in `processed`). Existing embedded PNG/JPEG: notation only, the bytes stay,
no name. **Never fix unattended**, proposals go via `questions`.

Your own wiki pages: if `write_wiki_page` reports `nonconforming_image`, fix it without asking with
`fix_images: true` or rebuild the SVG. Leave placeholders `pkm-image:…` from `read` in place.

**Storing large embedded images as files (`extract`):** if lint reports `large_embedded_image`, or a
tool reports `too_large` for a document whose text is small but whose embedded images are large,
propose to store them as files. Only after **explicit confirmation**, never unattended: `read` →
`hash` → `extract_images` (optionally `min_kb`, default 32) without `apply` (check the list `files` and
the diff) → the same with `apply: true`. (`fix_images` with `extract: true` does the same.) The bytes stay unchanged, the images
keep their names, citations `[img:<name>]` stay valid. In the next run the document has
`image_notation_only: true`: process nothing, only list it in `processed`.

**Attachments:** an image file that a document links to (Markdown link or `![[…]]`) is an attachment of
that document, in whatever folder it lies (`<document>_img/` next to the document, old files in
`documents/_attachments/` or elsewhere). Attachments never appear as `pending` entries of their own: a new
document lists them under `images`, a changed one names image files with new content under
`images_changed`, moved files (same bytes) under `images_moved` and removed ones under `images_removed`.
If the user only moved image files and adjusted the links, the document has `image_notation_only: true`.
They get **no entry in `processed`** and no summary of their own. Only images that no document links
to are standalone sources. A document reported once with `assets_migrated: true` (images that were
standalone before are now its attachments, the text is unchanged) needs no processing: only list it
in `processed`.

## Source fidelity

- Wiki pages state what the sources say – nothing more. Every statement must be supported by its
  citation on its own.
- **No new claims from combining sources.** A sentence may relate statements from two different
  documents ("contradicts", "fits", "reinforces", "conflicts with", "in tension with") only if one
  of the sources makes that connection itself. Otherwise keep the statements separate, each with
  its own citation.
- **Attribute visibly.** If a section draws on several sources, start each statement with its
  source ("According to <author> …", "The document on <topic> says …"). Never place a statement
  from source B directly after one from source A so that it reads as A's.
- **"Contradictions / open questions"** (German: „Widersprüche / offene Fragen“) contains only:
  (a) contradictions between sources about the *same* subject, (b) open points or uncertainties
  named in a document, (c) outdated or time-dependent values the document itself marks. No own
  conclusions, no constructed tensions.
- **Own interpretation only on request.** Proposals for own interpretations (e.g. risks that follow
  from combining two sources) go into the run report as a question to the user. Only after
  confirmation write them to `wiki/syntheses/` with `confidence: low` and the line
  "Own interpretation, not stated in the sources." (German: „Eigene Einordnung, nicht aus den
  Quellen.“).
- If a source itself makes the connection between two documents, the sentence may cite both; mark it
  with `<!-- lint: cross-source ok -->` at the end of the line so that lint does not report it again.
  Lint reports sentences citing two or more documents as `cross_source_statement` (`warning` in
  "Contradictions / open questions", otherwise `info`) and synthesis pages without the marker as
  `synthesis_unmarked`.

## Formats

**Wiki page** (`wiki/topics/`, `wiki/entities/`, `wiki/summaries/`, `wiki/syntheses/`;
file name lower case, hyphens, umlauts spelled out: `rainwater-yield.md`):

```markdown
---
type: topic            # topic | entity | summary | synthesis
title: Rainwater yield
aliases: [Rain yield]
tags: [cistern, water]
sources: []            # generated by finish_maintenance
date_updated: 2026-11-02T21:10:00   # YYYY-MM-DDTHH:MM:SS, local time without time zone
confidence: high       # high | medium | low
---

> **Summary:** One to three sentences. Ends up in index.md and in the search hits.

## Content
The roof area is 92 m².[^b1]
(Up to version 2 an ultrasonic sensor was planned.[^b3])

## Contradictions / open questions
- An older note says 85 m².[^b5] The newer value (92 m²) is used.

## See also
- [[wiki/entities/tank-1]]

## Citations
[^b1]: [[documents/house/cistern#Roof]] · "Roof area according to plan 92 m²" · id:d-20261012-0915-x7mp · v:2 · sha:3f9a1c
[^b4]: [[documents/house/tank-datasheet.pdf#page=2]] · "Usable volume 6500 l" · sha:c07d44
[^b6]: [[documents/house/notes#Notes]] §:Notes#2 · "second note" · id:d-… · v:1 · sha:a6fd6c
```

Structure in "Content": subheadings (`###`), pure bold lines and pure link lines
are allowed and need no citation. Cite a table with a footnote in the
table or in a line directly below it (e.g. `[^b3]` or `Source: [^b3]`).

**Citation line:** `[^b<n>]: [[<path>#<anchor>]] · "<quote>" · id:<id> · v:<version> · sha:<6 characters>`
- Full path from the vault root, Markdown without `.md`, PDF/image with extension. Only `documents/`.
- Anchor = section key **without** duplicate suffix; for duplicate headings additionally
  `§:<key>` directly after the link. Text before the first heading: no anchor.
  PDF: `#page=<n>`.
- Quote ≤ 200 characters, literally from exactly this version.
- `id`, `v` and `sha` are in the response of **`read`**: `id`, `version` and under `sections`
  per section `key` and `sha`. For an older version `read` with `version`. For PDF/image: the
  first 6 characters of `hash` from `read`.
- **Citations of images:** embedded or associated image → section of the document, with the image
  reference as the quote: `[[documents/…/note#Setup]] · "[img:circuit-diagram]" · id:… · v:3 · sha:…`.
  Standalone image → link to the file and file hash.
- **Images in wiki pages:** show images from documents only as a link to the image file, with
  a footnote to the document; do not copy embedded images. You may embed your own SVG diagrams;
  they count as a conclusion ("derived from [^b1], [^b3]").
- Sections with `empty: true` (e.g. the H1 directly before the first `##`) have no text of
  their own: do not cite them, cite the subsection containing the quote.
- Large documents: `read` with `content: false` (metadata, `sections`, `content_length` only),
  then section by section with `section` or page by page with `offset`/`max_chars`. If `content` is missing
  with `content_omitted`, the document was too large for one call.
- Every factual statement in "Content" and "Contradictions / open questions" (German: "Inhalt",
  "Widersprüche / offene Fragen") ends with at least one
  footnote (a paragraph from the same passage: one footnote at the end of the paragraph is enough).
- Outdated statements keep their citation of the **old** version.
- `confidence: low` if sources contradict each other or there is only one uncertain source.

Both variants of the section names are recognized by the tools (citation checks, lint); the
example above uses the English ones.

**Summary** (`wiki/summaries/<file-name-of-the-document>.md`, `type: summary`): summarizes exactly
one document in its current version, with citations as above.

**Log** (`wiki/log.md`): `finish_maintenance` appends the entry and builds the heading with a
timestamp from `operation` and `log_title` (here `log_title: "1 new, 1 changed"`). You only
deliver the list as `log_entry`:

```markdown
## [2026-11-02 21:10] ingest | 1 new, 1 changed
- new: wiki/summaries/irrigation-schedule
- updated: wiki/topics/rainwater-yield, wiki/entities/tank-1
- outdated: "ultrasonic sensor" → "float switch" (cistern-overflow-sensor v2 → v3)
```

## Flow "ingest" ("process new documents")

1. `begin_maintenance`.
   - `status: blocked` → report the error (`doctor`) and **stop**.
   - `status: needs_decision` → do not resolve duplicate IDs (`ids.duplicates`) yourself, but
     ask.
   - `pending` contains `new`, `changed`, `meta_changed`, `moved`, `deleted`, `problems`.
     More than 10 documents → process in stages (at most 10 each); simply do not list
     unprocessed documents in `processed`.
   - Moves are already fixed (`fixed_citations`).
2. **Names in the inbox:** take `rename` proposals of new documents into the report (see "Names and
   image locations"); rename only after confirmation.
3. **`new`**: read the document completely with `read`.
   1. Create `wiki/summaries/<name>.md` with `write_wiki_page`, with citations.
   2. Determine affected pages via `read_index` (and if needed `search`). Update or create at most
      10–15 topic, entity and synthesis pages. Every new or
      changed statement gets a footnote.
   3. Set cross-references in both directions ("See also").
   4. Check the frontmatter and work out proposals (see "Frontmatter proposals"), do not
      enter anything yet.
   5. Take findings on data URIs (`image_issues`) into the report, do not fix anything yet.
   6. Read existing pages with `read` before changing them and pass their `hash` as `expected_hash`
      to `write_wiki_page` (always write the whole page content). On `conflict` read
      again.
4. **`changed`**: process only the reported sections. Read the diff:
   `history` with `diff_from: <processed_version>`. Without version control (`not_versioned`)
   there is no diff: read the reported sections in their current version and compare them with
   the wiki pages.
   - `changed`/`added`: bring the affected statements up to date, citations of the **new
     version**.
   - Changed decision or fact: keep the earlier state as "Up to version n: …" with a citation of
     the **old** version if it matters for traceability; otherwise only
     note it in the log.
   - `removed`: check the affected statements (mark as outdated instead of deleting).
   - `renamed`: only adjust the anchors (done by `begin_maintenance`/`finish_maintenance`).
   - Empty section list (only the order changed): do nothing content-wise.
   - Citations of unchanged sections are raised to the new version by `finish_maintenance` itself
     (only `v:`; `sha:` stays).
   - Update the summary page of the document.
5. **`meta_changed`**: only adjust the summary page (title, topics, references). The citations
   are raised to the new version by `finish_maintenance`. **`image_notation_only`** (only the image notation
   changed): process nothing, only list it in `processed`; `finish_maintenance` raises the citations.
6. **`deleted`**: **do not delete** the affected statements (see `wiki_pages`), but note under
   "Contradictions / open questions": "Original no longer exists (last state in
   Git, v<n>; without version control: last processed v<n>)" (German page: „Original nicht mehr
   vorhanden (letzter Stand in Git, v<n>; ohne Versionsverwaltung: zuletzt verarbeitete v<n>)“), `confidence: low`, question in the report. List the key in `removed`.
7. **Corrections** (`kind: correction` in the frontmatter): the user's correction takes precedence over
   older sources and counts as a citation itself. Adjust the affected page (see `related`), note the
   old statement as replaced in the log. If the correction contradicts a **newer** source
   → ask.
8. **Images**: view every new or changed image (embedded or linked, see `images` in
   `read`, and `images`/`images_changed` in `pending`) with `read_image`. Take over the content in
   words and cite it with `[img:<name>]` as the quote. Attachments get no summary and no `processed`
   entry of their own; standalone images (without a document that links to them) as before. **PDF**: `read` only returns size and `hash`.
   You read the content if the vault folder is connected in the conversation; otherwise do not list the PDF
   in `processed` and name it in the report.
9. **Check cross-source statements:** For every sentence with citations from two or more different
   documents, check whether one source makes the connection itself. If not, split the sentence or
   remove the connection (see "Source fidelity"). List such sentences in the run report.
10. Finish with `finish_maintenance`:
   - `processed`: IDs (or paths for PDF/standalone image) of all documents processed in this run –
     also the moved ones and those changed only in their metadata. Not the attachments of a document
     (if listed anyway, they are skipped without a warning). The tool determines the citing pages
     from the footnotes; `warnings` names documents without a citation.
   - `removed`: keys of processed deleted documents.
   - `log_entry`, `log_title`, if needed `questions` (questions for `wiki/_status.md`).
   - If `lint` reports errors in your pages: fix them with `write_wiki_page` and
     call `finish_maintenance` again with `operation: fix` (without `processed`).
   - `cross_source` lists the source fidelity findings on the pages changed in this run: check each
     sentence again (split it or mark a connection a source makes itself) and name them in the report.
11. Short report in the chat: new/changed pages, outdated statements, citation problems,
   filing proposals (from `wiki/_status.md`), questions – and **for each new document with
   missing fields the YAML block** with the question whether it should be entered, as well as for each document
   with `image_issues` the findings with a fix proposal and the question whether it should be fixed,
   and the name proposals (`rename`) with the question whether to rename; the checked cross-source
   sentences (what was split or why a connection is in a source) and proposals for own
   interpretations as a question (only after confirmation into `wiki/syntheses/`, marked).

Conflict copies of the cloud storage are never processed; the user merges them in Obsidian.

## Flow "lint"

1. `begin_maintenance` with `with_lint: true` (result under `lint`).
2. **Fix yourself** (with `write_wiki_page`): broken links with a unique target, missing
   summaries. Moved citations, `sources` and the index are handled by `finish_maintenance`.
3. **Propose instead of doing:** missing frontmatter fields of documents (YAML block as
   under "Frontmatter proposals"), nonconforming data URIs (`nonconforming_image`, see "Fixing
   data URIs"), contradictions in content, merging pages, new
   pages, duplicate IDs, citations with `newer_version` that could not be raised
   automatically, hints on documents (you do not touch `documents/`). Image hints (all `info`):
   `large_embedded_image` → propose `extract_images`; `generic_alt_text` (alt text like
   "Image", "Bild" or a file name) → propose a description after viewing the image; `duplicate_image`
   (same image at several paths) → propose to link one file and delete the others;
   `orphaned_attachment` (no document links to it any more) → ask whether to delete or link it;
   `naming` (names in `_inbox/`) → propose `rename_document`; `image_location` (image files outside
   `<document name>_img/`) → propose the tool named in `tool` (`rename_document` or `move_images`).
   Source fidelity: `cross_source_statement` → check the sentence; if no source makes the connection,
   split it or remove the connection yourself (it is your page), otherwise mark it with
   `<!-- lint: cross-source ok -->`; `synthesis_unmarked` → add `confidence` and the marker if the page
   is an own interpretation, otherwise rewrite it so that every statement is a source's.
4. `finish_maintenance` with `operation: lint`, `lint_report: true` (report to
   `wiki/_lint/YYYY-MM-DD.md`) and a log entry.

## Flow "query" (in the project)

First `read_index`, then the relevant pages with `read`, then the answer with references to the
wiki pages. When asked, name the citations (`show_citations`; wording of old versions with
`read` and `version`). Offer good answers as a page below `wiki/syntheses/` (with citations of
documents, not of wiki pages) and after consent create it with `write_wiki_page` and finish with
`finish_maintenance` (`operation: fix`). Keep to "Source fidelity": what is your own conclusion
gets `confidence: low` and the line "Own interpretation, not stated in the sources."

## Flow "adjust the schema"

Propose changes to `CLAUDE.md` (as a diff). Write only after consent and only if the
vault folder is connected; otherwise the user makes the change themselves.

## Unattended run (scheduled task)

Do not wait for answers. **Never enter** frontmatter proposals, image fixes, renamings and image moves, but put them as a question via
`questions` into `wiki/_status.md`. Decide conservatively: for unclear filing, duplicates,
contradictions with newer sources or deleted originals **do nothing risky**, but
put the question via `questions` of `finish_maintenance` into `wiki/_status.md` and note it in the
log. Own interpretations are never written in unattended runs; they go into `questions` as well.
Still finish the run with `finish_maintenance`.
