# Release notes

## Unreleased

- **Document language:** `pkm setup` asks whether documents created in chat should be mainly in
  English or German (`PKM_LANGUAGE` in `config.toml`, `en` or `de`, default `en`, option
  `--language`). The server `pkm` names the language and its section names in its instructions
  (German: Ergebnis, Entscheidungen, Offene Punkte, Kontext / Begründung); the skill `pkm-access`
  writes new documents in that language, continued documents keep theirs. Specification 0.27.
- **Upgrading:** run `pkm setup` again (it asks for the language), upload the new skill ZIP of
  `pkm-access` and restart Claude Desktop.

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
