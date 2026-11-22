# Release notes

## V0.3.5

Changes compared to `V0.3.4`. Specification now **0.34**.

- **Existing Markdown files are filed unchanged:** when you hand over a Markdown file (or a finished
  Markdown text) in the chat and ask to put it into the PKM, Claude files its content as it is – no
  summary, no restructuring into the sections for chat results, no translation. Title, tags and
  similar fields come from the file's frontmatter. A summary only if you ask for it. Skill
  `pkm-access` and the instructions of the server `pkm` say so.
- **Upload the skill `pkm-access` again** in Claude Desktop after the update.

## V0.3.4

Changes compared to `V0.3.3`. Specification now **0.33**.

- **Skills folder opens after the setup:** at the end of an interactive `pkm setup` (also when started
  by the installer) the folder with the skill ZIP files opens in Explorer (Windows) or Finder (macOS),
  so they can be uploaded to Claude Desktop right away. Not with `--yes`, `--json` or the new option
  `--no-open`; if the folder cannot be opened, its path is shown.
- **Clearer closing text of `pkm setup`:** it explains the two remaining steps (upload the skills,
  create the project "PKM Maintenance" with its instructions in the right side bar) and links to the
  usage and installation instructions on GitHub.
- **Check of the Claude Desktop entries:** `pkm setup` also shows the path of
  `claude_desktop_config.json` and the entries for `pkm` and `pkm-maintenance`, with the request to
  check in Claude Desktop (Settings > Developer > Edit Config) that this is the file the app uses and
  that the entries are there. Otherwise the tools of the PKM do not reach Claude.
- **Dependabot** now checks for updates monthly instead of weekly.

## V0.3.3

Changes compared to `V0.3.2`. Specification now **0.32**. Package C of the security review of
19 November 2026: the installers install a checked release instead of the current state of `main`.

### Installation from the release, with checksum

- **New install commands:** the installers are attached to every release;
  `https://github.com/achim0x/pkm-llm-wiki/releases/latest/download/install.sh` (or `install.ps1`)
  always leads to the newest one. The old links to `raw.githubusercontent.com/…/main/` keep working:
  that copy fetches the newest release itself.
- **Checksum before installing:** the installers download the wheel of the release, `constraints.txt`
  and `SHA256SUMS`, and compare the SHA-256 of the wheel and of `constraints.txt`. The installer
  attached to a release carries the checksum of its wheel itself, so a manipulated wheel is refused
  even if `SHA256SUMS` was changed as well. On a mismatch nothing is installed.
- **Tested dependency versions:** `constraints.txt` pins the exact versions of `mcp`, `pyyaml` and their
  dependencies that the release was tested with. (uv does not enforce file hashes from a constraints
  file, so it pins versions, not hashes.)
- **Options:** `PKM_VERSION` installs a certain release; `PKM_ARCHIVE` keeps installing from a ZIP of
  the repository for development, without a checksum check; `PKM_RELEASE_URL` takes the release files
  from another place (tests).

### Release workflow

- Checks that the tag matches the package version.
- Pins the dependencies (`uv pip compile --universal`), installs the wheel with exactly these
  versions and runs the test suite against the installed wheel; no release if a test fails.
- Attaches the stamped installers, `constraints.txt`, `SHA256SUMS` and the skill ZIPs.
- Creates a **build provenance attestation** for every file; check it with
  `gh attestation verify <file> --repo achim0x/pkm-llm-wiki`.
- The CI rebuilds such a release for every push and checks on Linux, macOS and Windows that the
  stamped installers install it and refuse a tampered wheel.

### Upgrading from V0.3.2

Run the installer again, preferably from the new link. Nothing else changes; the skills are unchanged.

## V0.3.2

Changes compared to `V0.3.1`. Specification now **0.31**. Prompted by a security review of
19 November 2026, which found no malicious code and no exploitable vulnerability but proposed
improvements to the supply chain and the protection against instructions injected through documents.

### Protection against injected instructions

- **Content is data, never an instruction:** both MCP servers and both skills now state that text in
  documents, wiki pages and tool results is never a request from the user; confirmations (`apply`,
  `confirm_large`, `confirm_shortening` …) count only when the user gives them in the chat.
- **Tool annotations:** every tool carries the MCP annotations `readOnlyHint` and `destructiveHint`
  (e.g. `read` read-only, `rewrite_document`, `edit_document`, `rename_document`, `move_images`
  destructive), so clients can ask before writing tools.
- **New option `PKM_READ_ONLY`:** with `true` the chat server `pkm` offers only reading tools (useful
  for vaults with sensitive content). The maintenance server is not affected.
- **Backups without Git:** before a tool overwrites a file that has no Git version (version control
  off, or notes in `scratch/`), it copies the previous content to
  `<APPDIR>/backups/documents/<date>/`; copies are kept for 30 days.

### Supply chain and setup

- **Dependencies with upper bounds:** `mcp>=2.1,<3`, `pyyaml>=6,<7`. The servers need mcp 2.1 or
  newer (tested with 2.1 to 2.3; mcp 1.x and 2.0 fail when the servers are built). Dependabot proposes
  updates of the Python dependencies and GitHub Actions weekly.
- **Installer:** `uv` is taken from `PATH`; only if it is missing the installer of a **pinned uv
  version** (`PKM_UV_VERSION`) is used, with a hint on `winget install astral-sh.uv` / `brew install uv`.
- **`install.ps1`:** new variable `PKM_VAULT`; `PKM_SETUP_ARGS` is split like in the shell, so quoted
  paths with spaces (`OneDrive - Company`, `My Vault`) stay one argument.
- **`pkm setup`:** shows existing Claude Desktop entries with masked `env` values (they may hold
  credentials) and no longer crashes if `mcpServers` is not an object – it then shows the entries for
  entering them by hand.
- Fixed: the server instructions recommended `fix_images` with `extract` instead of `extract_images`
  for `too_large`.

### Documentation

- README (en/de): new section "Security and privacy" (what reaches the LLM, what the servers do not
  do, injected instructions, read-only mode, uninstalling, reporting vulnerabilities).
- Installation guides (en/de): installation in two steps (download, check, run), explanation of
  `-ExecutionPolicy ByPass`, installer options, document backups without Git, new section 11
  "Uninstalling" (incl. the note that `<APPDIR>/git` holds the version history).
- New `SECURITY.md`: report vulnerabilities via GitHub's private vulnerability reporting.

### Upgrading from V0.3.1

1. Run the installer again.
2. Upload both skill ZIPs (`pkm-access`, `pkm-wiki`) in Claude Desktop and restart it.
3. Optional: `PKM_READ_ONLY = "true"` in `config.toml` for a read-only chat server.

## V0.3.1

Changes compared to `V0.3.0`. Specification now **0.30**. Prompted by an ingest that combined two
correctly cited statements from different documents into a new claim that no source makes, and by
IP address comparisons in the wiki that were based on placeholder addresses.

### Highlights

- The wiki states only what the sources say: no new claims from combining sources, visible
  attribution, own interpretations only on request and marked.
- New lint checks find sentences that combine sources and unmarked synthesis pages.
- IP addresses: the agent asks whether they are concrete or placeholders, keeps the answer in the
  frontmatter and derives nothing from them until then.

### Source fidelity

- **Rules** in the skill `pkm-wiki` (new section "Source fidelity") and in the `CLAUDE.md` template:
  - wiki pages state only what the sources say;
  - statements from different documents are related only if a source makes that connection itself;
  - each statement is visibly attributed to its source; in tables the citation goes into the row it
    supports, not into a collective "Sources:" line;
  - "Contradictions / open questions" only lists contradictions between sources on the same subject,
    open points named in documents and values the documents themselves mark as outdated;
  - own interpretations only on request, in `wiki/syntheses/` with `confidence: low` and the line
    "Own interpretation, not stated in the sources." – never in unattended runs.
- **Ingest:** before `finish_maintenance` the agent checks every sentence citing two or more documents
  and lists the checked sentences in the report.
- **New lint check `cross_source_statement`** for pages below `wiki/topics|entities|summaries|syntheses/`:
  a sentence or list item with citations from two or more documents is a `warning` in
  "Contradictions / open questions" and an `info` elsewhere (`detail`: `section`, `footnotes`,
  `documents`, start of the sentence). Several citations of the same document count once; lines
  without a statement of their own (e.g. "Sources: [^b1] [^b2]") and table rows are skipped.
  Exceptions: `<!-- lint: cross-source ok -->` at the line or `lint_ignore: [cross_source_statement]`
  in the frontmatter of the page.
- **New lint check `synthesis_unmarked`** (info): synthesis page without `confidence` or without the
  marker for an own interpretation.
- **`finish_maintenance`** returns the source fidelity findings of the pages changed in the run as
  `cross_source`.

### IP addresses: ask, then follow the answer

- **New frontmatter fields:** `ip_addresses` (`placeholder` | `concrete`) says whether the IP
  addresses in a document are placeholders or concrete; `ip_addresses_concrete: ["203.0.113.5"]` lists
  concrete exceptions in a `placeholder` document. Both are set only after the user's answer, via
  `set_document_metadata` (invalid values or addresses are `invalid_argument`).
- **Detection:**
  - special addresses (`0.0.0.0`, `127.0.0.0/8`, `169.254.0.0/16`, `255.255.255.255`, `::`, `::1`,
    `fe80::/10`) are ignored;
  - well-known public services (`PKM_IP_WELL_KNOWN`, new option; default `1.1.1.1`, `1.0.0.1`,
    `8.8.8.8`, `8.8.4.4`, `9.9.9.9` and others) are always concrete and raise no question;
  - an IPv4-like number only counts as an address in a network context (private or documentation
    range, port, prefix length, scheme or share path, code, network terms in the line) and never after
    "Abschnitt", "Kap.", "§", "DIN", "IEC" … – so section 61.3.6.1 of a standard is no address.
- **`begin_maintenance`** marks new documents with IP addresses, and changed ones whose addresses
  changed, with `ip_addresses`: `found` (at most 20), `classification` (`null` = unclassified),
  `unclassified`, `concrete` (exceptions) and `well_known`.
- **Skill `pkm-wiki`:** for addresses in `unclassified` the agent asks in the report (unattended: via
  `questions`) and proposes the fields. Until the answer and for placeholders nothing is derived from
  IP addresses; a contradiction about an address only if both documents hold it as concrete and mean
  the same host or network. IP addresses in `documents/` are never changed.
- **Lint** (`info`): `ip_addresses_unclassified` (document with addresses that have no
  classification) and `ip_comparison` (contradiction entry with an address that one of the cited
  documents does not hold as concrete).

### Upgrading from V0.3.0

1. Run the installer again.
2. In `pkm setup`, let it update `CLAUDE.md` (or merge `CLAUDE.md.new`).
3. Upload both new skill ZIPs (`pkm-wiki`, `pkm-access`) in Claude Desktop and restart it.
4. Run a lint and work through the hints `cross_source_statement`, `synthesis_unmarked`,
   `ip_addresses_unclassified` and `ip_comparison` on existing pages and documents.

## V0.3.0

Changes compared to `V0.2.2`. Specification now **0.29**. Prompted by the maintenance runs of
5/6 November 2026 (a workshop encyclopedia with 106 image files, an article with 2.2 MB of embedded
PNGs) and refined in four test rounds on 7 and 8 November 2026.

### Highlights

- Image files belong to their document, wherever they lie, and new ones are stored next to it in
  `<document name>_img/`, linked relative to the document (`./<document name>_img/…`).
- The size limit `PKM_MAX_KB` counts only the text; large embedded images can be stored as files
  (`extract_images`).
- New maintenance tools `rename_document` and `move_images` bring names and image folders in line
  with the naming rules – only after the user's confirmation.
- No Base64 in tool answers, generated wiki files in the wiki language, `pkm --version`.

### Images: attachments and storage location

- **Attachments in any folder:** an image file that a document links to (Markdown image or `![[…]]`)
  is an attachment of that document, wherever it lies. Links are resolved relative to the document,
  from the vault root, ignoring case, by Obsidian's shortest path (`![[images/IMG_068.png]]`) and by
  bare file name, also in angle brackets with spaces.
- Attachments are no `pending` entries of their own: a new document lists them under `images`; a
  changed one names files with new content under `images_changed` (`assets_changed` is still
  returned), moved files (same bytes) under `images_moved` and removed ones under `images_removed`.
  They need no entry in `processed`; listed anyway, `finish_maintenance` skips them without the
  warning "no wiki page cites this document".
- **Storage location beside the document:** new image files (`mode: auto`/`file`, `add_image`,
  `import_path`, `extract_images`) go to `<document name>_img/` next to the document, so document and
  images stay together when passed on. Identical images in one document are stored once.
  `documents/_attachments/` is no longer a target; old files there stay valid. `pkm init` sets
  Obsidian's attachment folder to "Same folder as current file".
- **Link style** `PKM_LINK_STYLE` (new option): `relative` (default) writes `./<document name>_img/…`
  (or `../…` outside the document's folder), `absolute` writes paths from the vault root. Both are
  read.
- **File names of image files** come from the image name or, when fixing, extracting or moving, from
  the alt text: cut at a word boundary (at most 60 characters) and dated with `date_markdown` of the
  document, e.g. `foto-einstieg_2026-11-03.png`. Proposals already show the real names. Image names
  and citations (`[img:<name>]`) do not change.
- **Moving images by hand:** if only image files moved (same bytes) and the links were adjusted,
  `pending` reports the document with `image_notation_only: true` – nothing to process.
  `finish_maintenance` then raises all its citations to the new version (`sha:` too for the sections
  with changed image links), also after `rename_document` or `move_images` moved the document or its
  images; `raised_citations` names `version` and `sha_changed` per citation.
- **Switching an existing vault:** a document whose images were standalone entries before is reported
  once with `assets_migrated: true` and `image_notation_only: true`; processing it removes the old
  standalone entries.
- **Standalone images by path and hash:** `moved` only if the recorded path no longer exists; the same
  path with new content is `changed`; the same image at two paths is a duplicate (lint
  `duplicate_image`) instead of an endless `moved`.
- Orphaned attachments are reported regardless of the folder.

### Size limit and storing images as files

- `PKM_MAX_KB` applies to the text without data URIs (as `read` counts it), not to the file size.
  `set_document_metadata`, `update_frontmatter` and `fix_images` are exempt. `too_large` names the
  text size and the size of the embedded images separately.
- The user can override the limit for a single call: after explicit confirmation the chat repeats
  `create_document`, `rewrite_document`, `append_to_document` or `edit_document` with
  `confirm_large: true`. Wiki pages of the maintenance agent stay under the limit.
- **New tool `extract_images`** (both servers, only after confirmation): stores embedded raster images
  of at least `min_kb` (default 32 KB) as files in `<document name>_img/` and links them; bytes, alt
  texts and image names stay. Without `apply` a proposal with the list of files and a diff, with
  `apply: true` a new version (`PKM-Fix: images-extract`); in the next run the document is
  `image_notation_only`. `fix_images` with `extract: true` does the same and stays for compatibility
  (clients may keep showing an older schema of `fix_images`). CLI: `pkm fix-images --extract
  [--min-kb N]`.
- **No Base64 in tool answers:** diffs (of `fix_images`, `extract_images`, `rewrite_document`,
  `edit_document`, `restore_document`, `history`) and citation excerpts show embedded images as
  placeholders like `read`; overlong lines are cut.

### Names and image folders

- **Naming rules** (also in the `CLAUDE.md` template): file and folder names in `documents/` in lower
  case with hyphens, umlauts spelled out; new documents `<slug>_YYYY-MM-DD.md`; image files in
  `<document name>_img/`, named after their alt text.
- **Shorter names:** the name part of new documents from the chat (`create_document`) and of name
  proposals is cut at a word boundary to `PKM_SLUG_MAX` characters (new option, default 40). Name
  proposals also drop the subtitle (text after ` – `, ` - ` or `: `), e.g.
  `training-from-the-back-of-the-room_2026-11-07.md`. Notes in `scratch/` are not shortened.
- **Name proposals:** `begin_maintenance` returns `rename` for new Markdown documents in
  `documents/_inbox/` whose name does not follow the convention; `wiki/_status.md` shows it. Proposals
  list the image files that move along, the adjusted links, documents linking to it (`linked_from`)
  the wiki pages citing it with the number of citations (`cited_by`, `citations`), wiki pages with plain
  wikilinks to it or its image files (`linked_by_wiki`, with a warning: they are not adjusted) and generated
  files that are written anew anyway (`regenerated`, e.g. `wiki/_status`).
- **New maintenance tool `rename_document`** (only after confirmation, never unattended): renames a
  document in the inbox, or elsewhere if its name breaks the rules (capitals, spaces, underscores);
  `name` sets another name. Its image files move into `<new name>_img/`, links are adjusted, emptied
  folders removed – one commit. Wiki pages are not changed; their citations follow via the document ID
  in `finish_maintenance`.
- **New maintenance tool `move_images`** (only after confirmation): moves the image files of a document
  into `<document name>_img/` – old files in `documents/_attachments/`, folders like `images/`, or an
  image folder left behind in `_inbox/` after filing (Obsidian does not move it). Links always become
  `./<document name>_img/…`; Obsidian embeds become Markdown images (`![[x.png|300]]` →
  `![|300](./…)`). Files other documents link to stay (`kept`).
- **Generic image names** (`IMG_013.png`, `image.png`, hashes) get names from the alt text. Files whose
  alt text says nothing keep their name and are listed under `generic_names_kept`; the parameter
  `alt_texts` of both tools (`{file path, file name or image name: alt text}`) sets alt text and file
  name in one step.

### Lint

- New info hints:
  - `large_embedded_image` (embedded raster image over 32 KB, proposes `extract_images`),
  - `generic_alt_text` ("Image", "Bild", file names like `IMG_068`) with `file`, `section`,
    `file_keeps_generic_name` (the same set as `generic_names_kept`) and `name_from_other_link`,
  - `duplicate_image` (same image at several paths),
  - `naming` for `_inbox/` (document name, image folder name, generic image file names, each with a
    proposal and the citing wiki pages),
  - `image_location` (image files outside `<document name>_img/`; proposes `move_images`, or
    `rename_document` first if the document's name breaks the rules).
- `orphaned_attachment` in any folder.
- `topic_without_page`: a tag counts as covered by the file name, title or an alias of a wiki page, by
  the **first** tag of a topic, entity or synthesis page, or as whole words in the file name or title
  of such a page (`sandboxing` in `sandboxing-von-ki-agenten`). Further tags of a page about another
  topic do not count.

### Maintenance, wiki and skills

- `begin_maintenance` returns `wiki_language` (server instructions do not reach the model in every
  client, e.g. Cowork) and `tools_version` (the installed pkm-tools, to check the tool list a client
  shows).
- `wiki/index.md`, `wiki/_status.md` and the heading of a new `wiki/log.md` follow `PKM_LANGUAGE`
  (German: "Noch nicht verarbeitet", "Probleme" …). Lint reports stay English.
- Skill `pkm-wiki` lists name proposals in the report like frontmatter proposals and never asks where
  to file a document; skills `pkm-wiki` and `pkm-access` describe attachments, the storage location,
  `extract_images`, `rename_document` and `move_images`.
- `CLAUDE.md` template: naming rules; the first line of a wiki page follows the wiki language
  (`> **Kurzfassung:** …` in German).

### Showing the installed version

- `pkm --version` prints the installed version (`pkm-tools 0.3.0`). `pkm setup` prints it as its
  first line, and `pkm doctor` reports it as `version`. (Finished after the tag `v0.2.2`, so it is
  part of this release.)

### Upgrading from V0.2.2

1. Run the installer again.
2. In `pkm setup`, confirm taking over the existing configuration and let it update `CLAUDE.md`
   (or merge `CLAUDE.md.new`). Remove `PKM_IMAGE_FOLDER` from `config.toml` if present (it is
   ignored).
3. Upload the new skill ZIPs (`pkm-access`, `pkm-wiki`) in Claude Desktop and restart it; in Cowork
   reconnect the computer so the new tools appear.
4. Check `PKM_LANGUAGE` in `config.toml`: with `"de"` new wiki pages and generated wiki files are German.
5. Existing image files stay where they are. Run a lint: `image_location` and `naming` propose
   `move_images` and `rename_document`; carry them out only document by document after checking the
   proposals.

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
