---
name: pkm-access
description: Use the personal knowledge management (PKM) from normal chats – via the MCP tools of the server "pkm". Use for "put this into the PKM", "save the result", "continue this in the document about …", "update my document …", "what does my wiki know about …", "where does this come from?", "what has changed?", "undo that", "correct in the wiki …", "make a quick note …", "put this on my todo list", "tick off …", "what is on my list?".
---

# Using the PKM from chats

The PKM consists of `documents/` (the user's documents) and `wiki/` (a wiki with citations
compiled by the maintenance agent). From chats the wiki is **read-only**. Documents are created
and changed with the tools of the MCP server `pkm`; every change results in a new version
with a Git commit. Version control is optional: without Git the version number still counts up,
but there is no commit, no history and nothing to restore (`commit: null`, see `not_versioned`).

## Basic rule – without exception

**Every writing call** (`create_document`, `rewrite_document`, `append_to_document`,
`edit_document`, `update_frontmatter`, `add_image`, `fix_images`, `restore_document`) happens only **after a draft
has been shown and confirmed by the user**. This also applies when the user says "directly", "just
save it" or similar: then show the draft briefly and have it confirmed quickly.

Targets (`target`) can be a path, a wikilink, `id:d-…` or a short citation from
`short_citation` (e.g. `EN 61000-4-6:2014`). After the first contact with a document
always use the **ID** – the location can change.

## Filing something new

1. Condense the result into the sections of the **document language** that the instructions of the
   server `pkm` name (set during installation, `PKM_LANGUAGE`):
   - English: `## Result`, `## Decisions`, `## Open points`, `## Context / rationale`
   - German: `## Ergebnis`, `## Entscheidungen`, `## Offene Punkte`, `## Kontext / Begründung`

   Write title and text in that language, even if the chat is in another language. Only if the
   user explicitly asks for another language, use that one. Include only what is reliable, mark
   hypotheses as such.
2. Propose a title, `tags` (lower case, hyphens) and possibly `related`. When creating, pass
   `toolchain` with your own model name and `pkm-mcp`, e.g.
   `"Claude Opus 5.5 (pkm-mcp)"`. For standards or laws pass `kind` (`standard`/`regulation`) and,
   if known, `short_citation` and `date_document`.
3. First check whether a document already exists: `search` with `scope: "documents"`.
   If there is one on the same question, ask whether it should be updated (see below).
4. **Show the draft**, after confirmation `create_document` (`content` without frontmatter,
   `context` e.g. "Chat: <topic>").
5. Tell the user ID, path and version. Keep the ID in the chat history.

## Continued discussion (default: update the document)

1. Find the document: use the ID from this chat, otherwise `search` (`scope: "documents"`).
   One hit → have it confirmed briefly; several → ask. Unclear whether continuation or
   new topic → ask. Rule of thumb: same question = update, new
   subtopic = new document with `related` to the old one.
2. `read(id:…)` – returns content, `version` and `hash`.
   Large document (`content_omitted`, or recognized beforehand with `content: false` from `content_length`):
   read sections one by one with `section` and change them only with `edit_document` or
   `append_to_document`, **never** `rewrite_document` with a part of the content.
3. Create a new version that shows the **current overall state**. Keep the language and the
   section names of the document (the German names in brackets):
   - Rephrase "Result" ("Ergebnis").
   - "Decisions" ("Entscheidungen"): replace changed ones, add new ones. Do not leave anything "outdated".
   - "Open points" ("Offene Punkte"): remove done ones, add new ones.
   - "Context / rationale" ("Kontext / Begründung"): add the reasons for changes where needed.
4. Show **before/after per section** plus a one-line change note
   (e.g. "Sensor: float switch instead of ultrasound"). Have it confirmed.
5. Several sections affected → **one** `rewrite_document` with `expected_hash` and `note`.
   Small, targeted change → `edit_document` or `append_to_document`.
6. Briefly name the new version and the diff.

**Dated continuation section** (`## Continuation YYYY-MM-DD`, German `## Fortsetzung YYYY-MM-DD`)
only if the user **explicitly** asks for it ("document it as a continuation", "with history in the
document"). Never propose it on your own. Then: `append_to_document` with the section (context, result,
decisions, open points; on the same day suffix "(2)"), mark revised decisions in the
original with `edit_document`:
` — *outdated on YYYY-MM-DD, see [[#Continuation YYYY-MM-DD]]*`.

## Small changes

`read` → `edit_document` / `append_to_document` / `update_frontmatter` → show before/after
→ have it confirmed → run → name version and diff.

- `append_to_document` with `section`: section key, e.g. `"Open points"`,
  `"_preamble"` (text before the first heading) or for duplicate headings `"Notes#2"`.
- `edit_document`: `old` must occur exactly once; include enough context.
- `update_frontmatter`: `id`, `version`, `date_markdown`, `date_updated` and `status_markdown`
  are protected. Caution:
  comments in the frontmatter are lost – mention this beforehand for documents with comments.

## Tool responses

| `status` | What to do |
|---|---|
| `created` / `changed` | Name the version (and possibly ID, path) |
| `unchanged` | There was nothing to change; say so |
| `conflict` | The file was changed in the meantime (e.g. in Obsidian). **Read it again**, rebuild the version on the current state, show the draft again. Never repeat blindly |
| `large_shortening` | Tell the user the listed `missing_sections` or the shortening and have it **explicitly** confirmed, then call again with `confirm_shortening: true` |
| `ambiguous` | Name the candidates and ask (for sections: use the key with suffix) |
| `not_found` | Check the target or passage, possibly `search` |
| `forbidden` | The target cannot be changed (e.g. `wiki/`); for wiki errors create a correction document |
| `not_versioned` | The file lies in `scratch/`, or version control is off (Git not installed): there is no history and nothing to restore. Say so; to turn it on the user installs Git and runs `pkm setup` again |
| `git_unavailable`, `commit_failed`, `invalid_frontmatter`, `invalid_encoding` | Report to the user; do not work around it |

## History

- "What has changed?" → `history` with the document as `target`, if needed with `diff_from` (and `diff_to`).
- "What was it like before?" → `read(target, version: n)`.
- "Undo that" → determine the previous version, show the draft (which version is
  restored), after confirmation `restore_document`. The history is kept.

## Queries

1. Broad question → `read_index`; otherwise `search` (default `scope` is `wiki`).
2. Open the best hits with `read` and answer with references to the wiki pages
   (`[[wiki/…]]`).
3. Mention documents on the topic with `processed: false` (via `search` with `scope: "documents"` or
   `list_unprocessed`) as "not yet in the wiki".
4. **When asked for sources** ("where does this come from?"): `show_citations` with the wiki page
   and the statement as `statement`, if needed `with_excerpt: true`. Per statement name:
   original, section/page, quote, cited and current version, status, Obsidian link.
   For `newer_version` show the current wording as well; for `missing` say that the
   original no longer exists (the wording comes from the history).
5. Without being asked, the wiki pages are enough. Offer the originals when the answer is needed
   for a decision.

## Images

- **Format:** draw diagrams, sketches, flow charts and circuit diagrams, measurement charts and your own graphics
  as **SVG**. Photos, screenshots and scans stay **PNG**. Never vectorize photos.
- **Filing:** when creating or changing via the parameter `images` (`create_document`,
  `rewrite_document`, `append_to_document`, `edit_document`), into an existing document also with
  `add_image`. The text contains `{{image:<name>}}` at the position. Per image: `name` (lower case,
  hyphens, unique), `alt` (alt text, one line, **always**) and exactly one source:
  `svg` (text), `png_base64` or `import_path`. Usually omit `mode` (`auto`: up to 24 KB
  embedded, otherwise a file at the configured storage location – `documents/_attachments/` or,
  with `PKM_IMAGE_FOLDER = "document"`, a folder `<document name>_img/` next to the document; the
  result names the path; in `scratch/` always embedded). An identical image is stored only once.
- **Draft first, then write:** show the image in the draft (render SVG directly).
- **Photos or screenshots uploaded in the chat** cannot be passed on byte for byte. Ask the
  user to put the file (PNG or JPEG) into the folder `pkm_img_import/` in the vault (Finder,
  Explorer or the cloud storage app) and import it with `import_path` (the file name is enough). For simple
  graphics alternatively offer an SVG redrawing, marked as "redrawn" in the alt text.
- **Reading:** `read` shows embedded images as placeholders `![…](pkm-image:<name> "…")` and
  lists them under `images`. View them with `read_image` (`target`, `image`). Never copy Base64 or SVG content
  into a text.
- **Changing:** leave placeholders in `rewrite_document`/`edit_document` unchanged, the
  server inserts the originals again. If an image is missing in the new version, the result is
  `large_shortening` with `removed_images` – remove it only after confirmation with `confirm_shortening`.
  `unknown_image`: the placeholder name is wrong.
- **Never write data URIs into the text by hand**, always pass images via `images` or `add_image`.
- **`nonconforming_image`:** the text contained a data URI that does not conform to the form (findings
  in `image_issues`, e.g. `reference_style`, `unencoded_chars`, `missing_name`, `missing_alt`).
  Show the findings and the proposal to the user (for SVG the image), ask for missing alt texts and
  repeat the call with `fix_images: true` and `image_alt` (`{name: text}`) only after confirmation
  – or rebuild the version with `images`.
- **Nonconforming images in the existing text** (`image_warnings` when writing, `conforming: false` in `read`):
  tell the user and offer the fix. After confirmation `fix_images` without `apply`
  (show proposal and diff), then with `apply: true`. Never fix on your own.
- Existing embedded PNGs stay unchanged; for them at most the notation is fixed after
  confirmation – or, also only after confirmation, they are stored as files (see next point).
- **`too_large`** names the text size (without embedded images, the limit applies to it) and the size of the
  embedded images separately. Tell the user the size (`text_kb`, limit `max_kb`) and ask whether the document
  should still become that large; **only after explicit confirmation** repeat the same call with
  `confirm_large: true`. Otherwise propose splitting the content into several documents. **Large embedded images** (lint `large_embedded_image`, or `too_large` for a
  document with little text): offer to store them as files with `fix_images` and `extract: true` (optionally
  `min_kb`, default 32). After confirmation first without `apply` (show the list `files` and the diff),
  then with `apply: true`. The bytes and the image names stay, citations stay valid. Frontmatter changes
  (`update_frontmatter`) are not limited by `PKM_MAX_KB`.
- Errors: `svg_too_complex` (then PNG),
  `too_large_for_inline` (then `mode: auto`), `invalid_image`, `forbidden` (`import_path`
  outside the import folder).

## Notes and todo lists (`scratch/`)

For short-lived things there is the area `scratch/`: it is **never taken into the wiki** and **not
versioned** (no commit, no history).

- Triggers: "make a quick note …", "put this on my todo list", "tick off …", "what is on
  my list?".
- **New note:** `create_document` with `area: "scratch"` (optionally `folder`, e.g. `"todo"`).
- **Change an existing list:** `append_to_document` or `edit_document`, e.g. when ticking off
  `- [ ]` → `- [x]`. If it is unclear which list is meant: `search` with `scope: "scratch"`, for
  several hits ask.
- **The basic rule applies here too:** show the draft or before/after first, then write after
  confirmation.
- Point out that content in `scratch/` does not go into the wiki. If something should be kept
  permanently, propose a document in `documents/` instead (or have the note moved to
  `documents/` in Obsidian).
- For files in `scratch/` **do not name a version or a commit**. `history` and
  `restore_document` return `not_versioned` there.
- `search` searches `scratch/` only with `scope: "scratch"`.

## Corrections to the wiki

Never directly. Always as a document: show a draft with the wrong statement, the correct statement and
the rationale, after confirmation `create_document` with `kind: "correction"` and
`related: ["[[wiki/…]]"]` (affected wiki page). The maintenance agent incorporates it.
