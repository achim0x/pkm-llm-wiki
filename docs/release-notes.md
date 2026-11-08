# Release notes

## V0.3.0

Changes compared to `V0.2.2`. Specification now **0.29**. Prompted by the maintenance runs of
5/6 November 2026 (a workshop encyclopedia with 106 image files, an article with 2.2 MB of embedded
PNGs).

### Linked images are attachments, in any folder

- An image file that a document links to (Markdown image or `![[…]]`) is an attachment of that
  document wherever it lies: `documents/_attachments/`, a folder next to the document or elsewhere
  under `documents/`. Links are resolved relative to the document, from the vault root, ignoring
  case, by Obsidian's shortest path (`![[images/IMG_068.png]]`) and by bare file name, also in angle
  brackets with spaces.
- Attachments no longer appear as `pending` entries of their own: a new document lists them under
  `images`, a changed one under `images_changed` (`assets_changed` is still returned). They need no
  entry in `processed`; listed anyway, `finish_maintenance` skips them without the warning "no wiki
  page cites this document".
- Orphaned attachments are reported regardless of the folder.
- **Image files live next to their document**, in `<document name>_img/`, linked relative to the
  document (`./<document name>_img/…`), so document and images stay together when passed on. Applies
  to `mode: auto`/`file`, `add_image`, `import_path` and `fix_images`. `documents/_attachments/` is no
  longer a target (old files there stay valid); `pkm init` sets Obsidian's attachment folder to "Same
  folder as current file". Identical images in one document are stored only once.

### Standalone images by path and hash

- `moved` only if the recorded path no longer exists; the same path with new content is `changed`;
  the same image at two existing paths is a duplicate (no endless `moved`, lint `duplicate_image`).

### Size limit `PKM_MAX_KB`

- The limit applies to the text without data URIs (as `read` counts it), not to the file size.
  `set_document_metadata`, `update_frontmatter` and `fix_images` are exempt. `too_large` names the
  text size and the size of the embedded images separately and suggests `extract`.
- The user can override the limit for a single call: after explicit confirmation the chat repeats
  `create_document`, `rewrite_document`, `append_to_document` or `edit_document` with
  `confirm_large: true`. Wiki pages of the maintenance agent stay under the limit.

### `fix_images` with `extract`

- `extract: true` (optional `min_kb`, default 32) stores embedded raster images as files at the
  storage location and links them; the bytes, alt texts and image names stay. Without `apply` a
  proposal with the list of files and a diff, with `apply: true` a new version (`PKM-Fix:
  images-extract`). Only after confirmation. In the next run the document is `image_notation_only`
  and the citations stay valid. CLI: `pkm fix-images --extract [--min-kb N]`.

### Lint

- New info hints: `large_embedded_image` (> 32 KB, suggests `extract`), `generic_alt_text`
  ("Image", "Bild", file names like `IMG_068`), `duplicate_image`; `orphaned_attachment` now in any
  folder.

### Maintenance and skills

- `begin_maintenance` returns `wiki_language`, because server instructions do not reach the model in
  every client (e.g. Cowork).
- Skills `pkm-wiki` and `pkm-access` and the vault template `CLAUDE.md` describe attachments, the
  storage location and `extract`.

### After the test run (review of 7 November 2026)

- **No Base64 in tool answers:** diffs (also of `fix_images`, `rewrite_document`, `edit_document`,
  `restore_document`, `history`) and citation excerpts show embedded images as placeholders like
  `read`; overlong lines are cut. The answer of `fix_images` with `extract` at a 2 MB article stays
  below 10 KB.
- **Generated wiki files in the wiki language:** `wiki/index.md`, `wiki/_status.md` and the heading of
  a new `wiki/log.md` follow `PKM_LANGUAGE` (German: "Noch nicht verarbeitet", "Probleme" …). Lint
  reports stay English.
- **Lint `topic_without_page`** recognizes existing pages by their `tags` (topic, entity and synthesis
  pages) and by file name, title or alias.
- **Switching to attachments** after the update: a document whose images were standalone entries
  before is reported once with `assets_migrated: true` and `image_notation_only: true` instead of
  with all sections changed; processing it removes the old standalone entries.
- **File names of image files:** from the alt text, cut at a word boundary (at most 60 characters),
  dated with `date_markdown` of the document; the proposal already shows the real name. Image names
  and citations do not change.
- **Link style:** new option `PKM_LINK_STYLE` (`relative` or `absolute`); image links stay relative
  to the Markdown document by default, `absolute` writes paths from the vault root.
  `read_image` also finds images linked with a vault path or Obsidian's shortest path.
- **Names in the inbox:** a new Markdown document in `documents/_inbox/` whose name does not follow
  `<slug>_YYYY-MM-DD.md` (copied in by hand, from Obsidian or a conversion) gets a name proposal in
  `begin_maintenance` (`rename`) and in `wiki/_status.md`. After confirmation the new maintenance tool
  `rename_document` renames it; its image files move into `<new name>_img/` and the image links are
  adjusted, in one commit. Never in unattended runs.
- **Tool lists:** if a client still shows a tool without its new parameters (e.g. `extract`), it
  shows a cached list: quit and restart Claude Desktop (in Cowork reconnect the computer).

### After the second test run (review of 8 November 2026)

- **Images always beside the document** (`<document name>_img/`, see above); the option
  `PKM_IMAGE_FOLDER` is gone and ignored if still set.
- **Relative image links start with `./`** for files below the folder of the document
  (`./sandbox_img/schema.png`).
- **Moving image files by hand:** if only image files moved (same bytes) and the links were adjusted,
  `pending` reports the document with `image_notation_only: true`; `images_changed` lists only image
  files with new content (current paths), moves are listed under `images_moved` (`from`, `to`),
  removed files under `images_removed`.
- **New maintenance tool `move_images`** (only after confirmation): moves the image files of a
  document into `<document name>_img/` (old files in `documents/_attachments/`, folders like
  `images/`, an image folder left behind in `_inbox/` after filing), names files with generic names
  (`IMG_013.png`) after their alt text, adjusts the links and removes emptied folders, in one commit.
  Files other documents link to stay. `rename_document` does the same for the renamed document.
- **New lint hints** (`info`): `naming` for `_inbox/` (document name, image folder name, generic image
  file names, each with a proposal) and `image_location` for image files outside
  `<document name>_img/`. The skill `pkm-wiki` lists name proposals in the report like frontmatter
  proposals and never asks where to file a document.
- **`topic_without_page`:** a tag is covered only by the file name, title or an alias of a wiki page or
  as the **first** tag of a topic, entity or synthesis page; further tags of a page about another
  topic no longer count.
- **`begin_maintenance` returns `tools_version`.** If a client keeps showing an old tool list (e.g.
  `fix_images` without `extract`) even after a restart, it probably starts another installation;
  the troubleshooting table in the installation guide shows how to check.
- **`CLAUDE.md` template:** naming rules for files, folders and image files; the first line of a wiki
  page follows the wiki language (`> **Kurzfassung:** …` in German).

### After the third test run (review of 8 November 2026, afternoon)

- **Shorter name proposals:** without `name`, `rename_document` and lint `naming` drop the subtitle
  (text after ` – `, ` - ` or `: `) and cut the name at a word boundary to `PKM_SLUG_MAX` characters
  (new option, default 40): `training-from-the-back-of-the-room_2026-11-07.md`. The same limit applies to
  new documents created from the chat (`create_document`, not notes in `scratch/`), which keep their subtitle.
- **Always relative image links when moving:** `move_images` and `rename_document` write
  `./<document name>_img/…` (the configured `PKM_LINK_STYLE`) whatever the old link looked like;
  Obsidian embeds `![[…]]` become Markdown images (`![[x.png|300]]` → `![|300](./…)`).
- **New tool `extract_images`** in both servers: the same as `fix_images` with `extract: true`.
  Clients keep a cached schema of a known tool, so `extract`/`min_kb` of `fix_images` may stay
  invisible; a new tool name always shows its full schema.
- **`topic_without_page`:** a tag also counts as covered if it occurs as whole words in the file name or
  title of a topic, entity or synthesis page (`sandboxing` in `sandboxing-von-ki-agenten`).

### After the fourth test run (review of 8 November 2026, evening)

- **Citing wiki pages in rename proposals:** `rename_document` and lint `naming` list the wiki pages that
  cite or link the document (`cited_by`, with the number of citations) and the total (`citations`).
  Wiki pages are not changed by the renaming; the citations follow via the document ID in
  `finish_maintenance`.
- **Renaming outside the inbox:** `rename_document` also renames documents in other folders whose
  name breaks the naming rules (capitals, spaces, underscores). Lint `image_location` then proposes
  renaming first (`tool: rename_document`, `suggested_name`), so document and image folder end up in
  lower case, e.g. `ultimate-workshop-exercise-encyclopedia_2026-11-04.md` with
  `…_2026-11-04_img/`.
- **`fix_images` points to `extract_images`** for storing images as files; `extract`/`min_kb` stay
  for compatibility only. The skills use `extract_images`.
- **Generic image names:** files that keep a generic name because their alt text says nothing are
  listed under `generic_names_kept` with a hint. The new parameter `alt_texts` of `move_images` and
  `rename_document` (`{file name or path: alt text}`, only after confirmation) sets the alt text and
  the file name in one step.

### Showing the installed version

- `pkm --version` prints the installed version (`pkm-tools 0.3.0`). `pkm setup` prints it as its
  first line, and `pkm doctor` reports it as `version` (so it is also visible in
  `begin_maintenance`). (Finished after the tag `v0.2.2`, so it is part of this release.)

### Upgrading from V0.2.2

1. Run the installer again.
2. In `pkm setup`, confirm taking over the existing configuration and let it update `CLAUDE.md`
   (or merge `CLAUDE.md.new`). Remove `PKM_IMAGE_FOLDER` from `config.toml` if present (it is ignored).
   Image files of existing documents stay where they are; lint `image_location` proposes `move_images`.
3. Upload the new skill ZIPs (`pkm-access`, `pkm-wiki`) in Claude Desktop and restart it.
4. Check `PKM_LANGUAGE` in `config.toml`: with `"de"` new wiki pages are German.

## V0.2.2

Changes compared to `V0.2.1`. Specification now **0.28**.

### Wiki language

- The language setting `PKM_LANGUAGE` now applies to the wiki too. The question in `pkm setup`
  and `--language` name chat documents and the wiki.
- The maintenance server names the wiki language, the section names and the summary label in its
  instructions (German: Kurzfassung, Inhalt, Widersprüche / offene Fragen, Siehe auch, Belege;
  English: Summary, Content, Contradictions / open questions, See also, Citations). The skill
  `pkm-wiki` writes new wiki pages, summaries, log entries and reports in that language; existing
  pages keep their language, quotes in citations stay literal.
- Citation checks and lint accept both variants. Generated files (`index.md`, `_status.md`, lint
  reports) stay English.

### English names for the maintenance server

- The second MCP server is now called `pkm-maintenance` (program `pkm-maintenance-mcp`, module
  `maintenance_server.py`) instead of `pkm-pflege` (`pkm-pflege-mcp`, `pflege_server.py`); the
  Claude project is called "PKM Maintenance" instead of "PKM-Pflege".
- The old program name `pkm-pflege-mcp` stays as an alias, so existing Claude Desktop entries keep
  working until `pkm setup` runs. `pkm setup` replaces the old entry `pkm-pflege` with
  `pkm-maintenance` (after asking; other servers stay).
- The name of the Claude project does not matter to the tools; rename "PKM-Pflege" to
  "PKM Maintenance" if you like.

### Updating `CLAUDE.md` in the vault

- `pkm init` creates `CLAUDE.md` only if it is missing, so older vaults kept the text of their
  first installation. `pkm setup` now compares it with the template of the installed version. If
  it differs (older version or own edits), it asks whether to replace it: yes backs up the old file
  to `<app folder>/backups/` (outside the vault), writes the template and commits it with Git; no
  keeps the file and writes the template next to it as `CLAUDE.md.new` to merge by hand.

### Upgrading from V0.2.1

1. Run the installer again.
2. In `pkm setup`, confirm taking over the existing configuration and the language, let it
   replace the old Claude Desktop entry `pkm-pflege` with `pkm-maintenance` and update `CLAUDE.md`
   (or merge `CLAUDE.md.new` by hand if you have own edits).
3. Upload the new skill ZIPs (`pkm-access`, `pkm-wiki`) in Claude Desktop and restart Claude Desktop.

For an upgrade from V0.2.0 or older, see also the notes of V0.2.1.

## V0.2.1

Changes compared to `V0.2.0`. Specification now **0.27**.

### Document language

- `pkm setup` asks whether documents created in chat should be mainly in English or German
  (`PKM_LANGUAGE` in `config.toml`, `en` or `de`, default `en`, option `--language`).
- The server `pkm` names the language and its section names in its instructions (German:
  Ergebnis, Entscheidungen, Offene Punkte, Kontext / Begründung). The skill `pkm-access` writes new
  documents in that language; continued documents keep theirs. Tools, maintenance and wiki do not
  depend on it.

### Taking over an existing configuration

- `pkm setup` first looks for settings in environment variables, in the `env` blocks of the PKM
  entries in Claude Desktop (installations from before `pkm setup` kept them there) and in
  `config.toml`, shows them with their source and offers to take them over.
- PKM entries in Claude Desktop are also recognized under other names by their programs
  (`pkm-mcp`, `pkm-pflege-mcp`). If no source names the vault, it is read from the existing Git
  directory (`core.worktree`).
- Taken over, the values are the defaults of the questions and are written to `config.toml`, so a
  custom `PKM_GIT_DIR` and with it the version history stay in use. Declined, the setup starts anew
  and backs up `config.toml`.
- Closed input (end of file) no longer makes `pkm setup` fail; it takes the defaults.

### Documentation

- Development installation from a local clone (editable `uv tool install`, test vault with its own
  Git directory and search index): [installation.md](installation.md), appendix B.

### Upgrading from V0.2.0 or older

1. Run the installer again.
2. In `pkm setup`, confirm taking over the existing configuration and choose the document language.
3. Upload the new skill ZIP of `pkm-access` in Claude Desktop and restart Claude Desktop.

## V0.2.0

Changes compared to `V0.1.0` (specification 0.18). Specification now **0.26**, implementation
plan version 4.

### Highlights

- **One-command installation** with `install.sh` / `install.ps1` and the new setup wizard
  `pkm setup` – no Git and no manual editing of JSON needed.
- **Git is optional**: without Git the PKM runs without version history (`PKM_VERSIONING`).
- **Images** in documents: PNG, JPEG and SVG, inline or as attachments, with checks and fixes.
- **Windows** is an equivalent PKM host next to the Mac.
- **Any cloud storage** (or none): conflict copies of all common services are detected.
- **English throughout**: code, messages, generated vault files and skills; German section
  names are still accepted.
- **Obsidian and cloud storage are optional.**

### Installation and setup

- New installers `install.sh` (Mac/Linux) and `install.ps1` (Windows): install `uv`, download the
  repository archive from GitHub (works without Git), install `pkm-tools` and start `pkm setup`.
  `PKM_ARCHIVE` and `PKM_SETUP_ARGS` allow a local archive and non-interactive runs.
- New command **`pkm setup`** (repeatable): vault folder (`--vault`), Git check and identity,
  `config.toml`, `pkm init`, Claude Desktop entries, skill ZIPs, project instructions for
  "PKM-Pflege", `pkm doctor`.
- Claude Desktop: `pkm setup` first checks whether `pkm` and `pkm-pflege` are already entered
  correctly. Only if not does it show the change and ask once for permission (backup, other
  servers kept). If you answer no, it prints the JSON entries to enter by hand. `--yes` answers
  all questions with yes; `--claude-config` points to another file.
- Configuration in **`config.toml`** in the app folder (`PKM_CONFIG`); environment variables take
  precedence.
- Git is searched via `PKM_GIT`, `PATH` and the usual install locations; only a working Git is used.
- `pkm init` writes Obsidian settings to `.obsidian/app.json` and Obsidian property types.
- Skills are part of the Python package (`src/pkm/skills/`).
- Release workflow `release.yml` attaches skill ZIPs and the wheel to every tag `v*`.
- Manual installation without installer is documented step by step
  ([installation.md](installation.md), appendix A).

### Operation without Git

- `PKM_VERSIONING=off` (set by `pkm setup` when Git is missing): writing tools write without
  commit but still count `version:` up.
- `history`, `read(version)`, `show`, `restore` return `not_versioned`; `pkm versions` and
  `commit-wiki` do nothing; `pending` detects manual changes via hashes.
- Citations of older versions are checked against the current text if the cited section is
  unchanged. The write lock lives in `PKM_CACHE_DIR`. `pkm doctor` reports a note, not an error.
- If Git is added later, the next maintenance run commits the documents.

### Images (specification 0.21, 0.23, 0.24)

- New tools `add_image` and `read_image` (also in `pkm-pflege`), new parameter `images` with
  `{{image:<name>}}` markers for create/rewrite/append/edit.
- SVG is sanitized and minified, PNG validated and stripped of text chunks, **JPEG** import with
  metadata removed (orientation kept).
- Small images stay inline as data URIs, large ones go to `_attachments/` and are committed with
  the document; `read` shows placeholders that are restored byte for byte.
- Default import folder `<vault>/pkm_img_import/` (created by `pkm init`, in `.gitignore`,
  ignored by maintenance, lint and search).
- Data URIs are detected in every notation (inline, angle brackets, reference style, HTML `img`).
  Nonconforming ones are rejected with `nonconforming_image` and fixed only on request
  (`fix_images=true`, tool `fix_images`, CLI **`pkm fix-images`**).
- Maintenance: changed linked image files create new versions of the documents using them;
  orphaned attachments appear in `_status.md` and lint. Lint checks `[img:<name>]` citations,
  alt text, duplicate names and unsafe SVG.

### Maintenance and wiki (specification 0.19, 0.20)

- New tool `set_document_metadata` in `pkm-pflege` (title, context, tags, kind, short citation –
  after confirmation); `begin_maintenance` reports missing fields and known tags.
- Frontmatter fields are kept in schema order; simple lists without quotes.
- `read` can return single sections and parts (`section`, `offset`/`max_chars`, `content=false`);
  very long content is omitted unless requested.
- Lint: fewer false alarms (subheadings, emphasis/link-only lines, tables with footnote), new
  warning `citation_empty_section`.
- `fix-citations` rewrites wikilinks of moved documents; `finish_maintenance` raises citation
  versions on unchanged sections and on sections changed only in image notation.
- `pkm versions` commits hand edits of `CLAUDE.md` as user commits.
- Inbox file names now end with the date: `<slug>_YYYY-MM-DD.md` (on collision
  `<slug>-2_YYYY-MM-DD.md`). Only the slug of long file names is shortened.

### Cloud storage (specification 0.25)

- Conflict copies of Nextcloud/ownCloud, Dropbox, Google Drive, OneDrive, iCloud, Syncthing,
  pCloud, Box and German clients are detected, by name or as same-ID copies next to the original.
  The old pattern matching any "Konflikt" was narrowed to avoid false positives.
- `pkm doctor` recognizes cloud folders of all services, the vault's service and online-only files.
- A purely local vault without cloud storage is supported.

### Windows

- Windows as PKM host: default folder `%APPDATA%\pkm`, lock via `msvcrt`, `os.replace` with
  retries, `core.autocrlf=false` in the PKM repository, dependency `tzdata`, UTF-8 output of the CLI.
- CI tests on Linux, macOS and Windows (Python 3.12) and runs both installers on all three systems.

### Language

- Source code, messages, CLI help, MCP tool descriptions, commit notes and generated files
  (`wiki/index.md`, `wiki/_status.md`, `wiki/log.md`, lint reports) are in English.
- Wiki pages use English sections (`Content`, `Contradictions / open questions`, `See also`,
  `Citations`); the German names are still accepted.

### Documentation

- `README.md` is bilingual (English, then German); new English installation guide
  [installation.md](installation.md) next to the German [installation.de.md](installation.de.md).
- New [architecture.md](architecture.md) (English) with installation flow and pkm-tools internals,
  Mermaid diagrams.
- Files in `docs/` renamed to English: `specification.md`, `implementation-plan.md`,
  `acceptance.md`, `installation.de.md` (contents still German).
- Acceptance protocol with step 0 (installer and `pkm setup`) and checks without Git.

### Incompatible changes

- Generated vault files and new wiki pages are in English. Existing German pages keep working.
- New inbox file names have the date at the end.
- Skills are no longer in `pkm-tools/skills/` but in the package; repack them with `pkm setup`.
- Links to the old file names in `docs/` (`spezifikation.md`, `umsetzungsplan.md`, `abnahme.md`,
  `einrichtung.md`) no longer work.

### Upgrading from V0.1.0

1. Run the installer again (manual update: [installation.md](installation.md), appendix A.3).
2. Run `pkm setup`: it creates `config.toml`, checks the Claude Desktop
   entries, repacks the skill ZIPs and runs `pkm init` (import folder, `.gitignore`,
   Obsidian settings) and `pkm doctor`.
3. Upload the new skill ZIPs in Claude Desktop and restart Claude Desktop.

## V0.1.0

### Add pkm-pflege MCP server for wiki maintenance

Claude Desktop/Cowork run shell commands only in an isolated environment without pkm, git or the
git directory, so the CLI-based maintenance flow cannot run there. A second local MCP server
`pkm-pflege-mcp` bundles the deterministic steps into three tools:

- `begin_maintenance` (doctor, versions, ids, pending, fix-citations),
- `write_wiki_page` (wiki page dirs only, with `expected_hash`, no commit) and
- `finish_maintenance` (citations, mark with pages derived from footnotes, log, index, status,
  lint, commit-wiki).

Skill pkm-wiki, setup guide, READMEs and plan describe the new flow.
