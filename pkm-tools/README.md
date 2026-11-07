# pkm-tools

MCP servers `pkm-mcp` (chats) and `pkm-maintenance-mcp` (wiki maintenance) as well as the CLI `pkm` for the PKM with LLM wiki.
Basis: [specification](../docs/specification.md), [implementation plan](../docs/implementation-plan.md).

## Status

| Phase | Content | Status |
|---|---|---|
| 0 | Scaffold, tests, CI | done |
| 1 | Normalization/sections/hashes (4.8), frontmatter, IDs, Git layer, `pkm init` | done |
| 2 | Addressing, search index, reading MCP tools | done |
| 3 | Writing MCP tools with versioning | done |
| 4 | Maintenance CLI | done |
| 5 | Citations, `lint`, `doctor` | done |
| 6 | Skills, vault template, setup guide | done |
| 7 | Acceptance: protocol and simulation done, run on the Mac open | in progress |
| 8 | Automation (scheduled task), only on instruction | open |

**MCP tools:** `search`, `read`, `history`, `read_index`, `list_unprocessed`, `create_document`,
`rewrite_document`, `append_to_document`, `edit_document`, `update_frontmatter`, `restore_document`,
`show_citations`.

**Images (4.9):** `create_document`, `rewrite_document`, `append_to_document`, `edit_document` with
`images`, plus `add_image` and `read_image` (also in `pkm-maintenance-mcp`). Modules `images.py` (detection,
SVG sanitizing, PNG check, encoding, placeholders), `docimages.py` (insertion, files, `read`,
`read_image`), `assets.py` (associated image files, `state.json` `assets`, orphaned attachments),
`imagelint.py`.

**Data URIs (0.24):** `imagescan.py` (detection in every notation), `imagefix.py` (finding codes,
proposal, fix, comparison "only the image notation"), `citeraise.py` (raising citations). Writing
tools with `fix_images`/`image_alt`, tool `fix_images` in both servers, CLI `pkm fix-images`.

**MCP tools of `pkm-maintenance-mcp`:** the reading tools as well as `begin_maintenance` (doctor, versions, ids,
pending with `missing_fields`, `known_tags`, fix-citations), `set_document_metadata` (only `title`,
`context`, `tags`, `kind`, `short_citation` after confirmation; new version with `PKM-Source: agent`),
`write_wiki_page` (only `wiki/topics|entities|summaries|syntheses/`, with
`expected_hash`, without commit) and `finish_maintenance` (fix-/sync-citations, mark with the pages
determined from the citations, raise citations of unchanged sections to the new version, log, index,
status, lint, commit-wiki).

`read` (both servers) supports `section`, `offset`/`max_chars` and `content: false`; above 40,000 characters
without these parameters `content` is left out (`content_omitted`).

**CLI:** `pkm --version`, `pkm setup`, `init`, `ids`, `versions`, `pending`, `mark <id>… [--pages <page>…] [--remove]`,
`sha <target> [--section <key>] [--full]`, `index`, `status [--question <text>]…`,
`commit-wiki -m <text>`, `fix-frontmatter [<target>…] [--all]`, `fix-images [<target>…] [--all] [--apply]`,
`history <target> [--diff <from> [<to>]]`, `show <target> --version <n> [--section <key>]`,
`restore <target> --version <n>`, `reindex`, `fix-citations [<page>…]`, `sync-citations [<page>…]`,
`lint [--report]`, `doctor [--short]`.

**Skills:** `src/pkm/skills/pkm-access/SKILL.md` (normal chats), `src/pkm/skills/pkm-wiki/SKILL.md`
(maintenance project); part of the package, `pkm setup` packs them as ZIP files.

**Installation (15.1):** `install.sh` / `install.ps1` in the repository root install uv and the package
from the GitHub archive (works without Git) and start `pkm setup` (`setupwiz.py`): vault folder, Git
check, language of chat documents and wiki (`PKM_LANGUAGE`, `en`/`de`), existing configuration (shown and taken over after asking), `config.toml`, `pkm init`, comparison of the
vault's `CLAUDE.md` with the template (replaced after asking with a backup outside the vault, otherwise
written as `CLAUDE.md.new`), check of the entries in `claude_desktop_config.json` (changed only after asking, with
backup; the old entry `pkm-pflege` is replaced; otherwise the entries are printed for entering by hand), skill ZIPs, project instructions, `pkm doctor`. The workflow `release.yml` attaches the
skill ZIPs and the wheel to every release tag `v*`.
**Setup:** [docs/installation.md](../docs/installation.md) (German: [docs/installation.de.md](../docs/installation.de.md)). **Acceptance:** [docs/acceptance.md](../docs/acceptance.md)
(simulation of steps 1–9 and 11: `tests/test_acceptance_simulation.py`; step 10 and all
`scratch/` cases: `tests/test_scratch.py`).

## Deviations from and additions to the specification

- **Version control is optional** (`PKM_VERSIONING`, set by `pkm setup` depending on whether Git is
  installed). Without it writing tools write without commit (`commit: null`) but still count `version` up,
  `history`, `read` with `version`, `show` and `restore_document` return `not_versioned`, `pkm versions`
  and `commit-wiki` do nothing, manual changes are found by `pending` via the hashes, citations of an
  older version are checked against the current text if the cited section is unchanged, and the write
  lock lives in `PKM_CACHE_DIR`.
- **Configuration file** `config.toml` in the app folder (or `PKM_CONFIG`) with the keys of the
  environment variables; environment variables take precedence. `PKM_GIT` names the Git program;
  otherwise it is searched in `PATH` and at the usual locations (only a Git that runs counts, so the
  macOS stub `/usr/bin/git` without developer tools does not).
- `pkm init` also writes the Obsidian settings of specification 13 to `.obsidian/app.json` (adds
  missing values, reports differing ones).

- **Language:** all output of the tools is English – messages, CLI help, MCP tool descriptions, commit
  notes, the generated files `wiki/index.md`, `wiki/_status.md`, `wiki/log.md` and lint reports, the
  vault schema `CLAUDE.md` and the skills (the specification asks for German content). The citation
  check also accepts the German section names of existing pages ("Inhalt", "Widersprüche / offene
  Fragen"). Image names derived without `pkm:<name>` are `image-<n>`.
- If `PKM_ROOT` is missing, the CLI searches the vault upwards from the current folder (first folder with
  `.pkm/state.json`). The MCP server still needs `PKM_ROOT` in its configuration.
- The `mcp` SDK 2.x calls it `MCPServer` instead of `FastMCP`; the server supports both versions.
- If a call changes nothing (e.g. `edit_document` with `old == new`), the result is `status: unchanged`
  without a new version and without a commit.
- Additional error values: `forbidden` (target cannot be changed), `protected_field`, `too_large`,
  `git_unavailable`, `commit_failed`, `index_unavailable`, `invalid_argument`, `invalid_path`.
- If the MCP server changes a document without ID (created by hand), it first assigns ID and
  version 1 and commits this state with `PKM-Source: user`.
- `pkm versions` also commits attachments (new, moved by hash, deleted) and deleted
  documents so that the working tree stays clean. Attachments have no `PKM-Id`.
- `pkm mark --remove <key>` removes entries from `state.json` (e.g. after processing a
  deleted document). `pkm status --question` adds questions to `_status.md`.
- `show_citations` with `statement`: if the piece of text lies before a footnote group, only these
  citations are returned, otherwise those of the whole paragraph.
- Status of citations: `missing` before `newer_version` before `moved` before `ok`. If an original is moved
  *and* changed, the status is `newer_version`; `lint` additionally reports `citation_moved`.
- `lint` checks the citation requirement in the sections "Content" and "Contradictions / open questions"
  (`citations.CONTENT_SECTIONS`, German names included).
- `pkm lint --report` writes the report to `wiki/_lint/YYYY-MM-DD.md`. `pkm doctor` additionally
  warns if `commit.gpgsign` is active.
- All writing operations (MCP and CLI) are serialized via a lock file in the Git directory.
- `pkm init` creates `.obsidian/types.json` with the property types of the schema or adds
  missing ones; existing types stay. `pkm doctor` warns about missing or differing types.
- **Maintenance via MCP instead of a shell:** Cowork/Claude Desktop offer no shell on the PKM host.
  Maintenance therefore runs via the second server `pkm-maintenance-mcp` (`maintrun.py`) with three
  tools instead of CLI calls. `pkm mark` determines the pages itself from the footnotes there.
  The server cannot be restricted to one project in Claude Desktop; it is only enabled in
  maintenance conversations.
- **Frontmatter:** new fields are inserted line by line at the position given by the schema
  (`title`, `short_citation`, `date_document`, `status_markdown`, `date_markdown`,
  `toolchain_markdown`, `id`, `version`, `date_updated`, `context`, `tags`, `related`, `kind`;
  unknown fields after them); `update_frontmatter` sorts the same way. Simple lists are written without
  quotes (`tags: [a, b]`), tags are normalized.
- `pkm versions` records a manually changed `CLAUDE.md` as a user commit.
- Lint `statement_without_citation` skips subheadings, pure bold and link lines;
  a table counts as cited if a footnote is in it or directly below it. Citations of
  sections without text of their own are reported as `citation_empty_section`; `read` marks such
  sections with `empty: true`.
- `fix-citations` also rewrites wikilinks in the page text for moved originals. If a file is moved in
  Obsidian, Obsidian updates the links itself; then `fix-citations` rightly reports
  `pages_changed: 0`.
- **Cloud storage (`cloudsync.py`):** conflict copies are detected for all known services – by
  name (Nextcloud/ownCloud, Dropbox, Google Drive, Syncthing, pCloud, Box, German clients) and as a copy
  next to the original with the same document ID (OneDrive `-COMPUTER`, iCloud ` 2`, ` (1)`, `Copy of`).
  The earlier pattern "Konflikt" anywhere in the name is narrower now (no false alarms for
  "Konfliktmanagement.md"). `pkm doctor` detects cloud folders of all services (`git_dir_cloud`,
  `cache_dir_cloud`, `vault_cloud`) and "online only" files (`vault_online_only`, macOS `SF_DATALESS`,
  Windows offline/recall attributes).
- **Import folder:** the default is `pkm_img_import/` in the vault (in `.gitignore`, excluded from all
  maintenance commands because `iter_files` only walks `documents/`, `wiki/` and `scratch/`). JPEG is imported,
  EXIF/XMP, IPTC and comments are removed, the orientation is kept as a minimal EXIF block.
- **Data URIs (0.24):** with `fix_images: true` or `apply: true` without `image_alt`, the proposal from
  `image_issues` is taken for missing alt texts (it was shown beforehand). A reference definition used
  more than once results in `ambiguous` with the lines when fixing; there is no choice of the
  position, the user adjusts the position in Obsidian. In wiki pages there is no
  size limit for embedded SVG and no files are created. "Only the image notation" is
  checked per section and for the whole body (reference definitions in other sections);
  raised citations get new `v:` and `sha:`.
- **Images:** `edit_document` additionally has `confirm_shortening`, because removing an image
  must be confirmed like a shortening. Image files in an attachment folder (`documents/_attachments/`
  or `<document>_img/`) without a reference also count as orphaned (not only formerly associated ones,
  which count in any folder). If a changed image file is used by
  several documents, the commit of the first document contains the image, the others
  get one commit each (one file per version commit, 5.4). SVG rasterizing via
  `cairosvg` instead of `resvg`. Already processed documents without `assets` in `state.json` are
  only watched for changed image files after the next record.
- **Windows as PKM host** (specification 5.5 only names the Mac): default folder
  `%APPDATA%\pkm`, lock via `msvcrt` instead of `fcntl`, `os.replace` with retries for
  locked files, `core.autocrlf=false` in the PKM repo, dependency `tzdata`. Setup in
  `docs/installation.md` (German: `docs/installation.de.md`).

## Development

All Python commands run in a project-local `.venv` (never in the system Python):

```bash
cd pkm-tools
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
```

Check before every commit:

```bash
./.venv/bin/python -m ruff check .
./.venv/bin/python -m pylint --rcfile=.pylintrc src tests
./.venv/bin/python -m pytest -q
```

### Coding standard

- PEP 8, type annotations, line length 120.
- pylint without warnings and errors with the `.pylintrc` in the package (Google style).
- Every Python file starts with a module docstring (incl. `Author`), the GPL license header and the
  sections `Imports`, `Variables`, `Classes`, `Functions`, `Main` in this order.
- Docstrings for modules, classes, functions and methods with `Args`/`Returns`
  (test functions: one sentence on what is checked).
- Exactly one `return` per function or method.
- Few, justified `pylint: disable` only where the interface of the specification
  forces it (e.g. ten parameters of `create_document`, parameter name `set`) or for
  data classes with many fields.
- Docstrings, comments, messages and generated text are English.

The tests run on Linux, macOS and Windows. All paths are set via environment variables
(`PKM_ROOT`, `PKM_GIT_DIR`, `PKM_CACHE_DIR`, …), see specification 7.1.

## License

GNU General Public License v3.0 or later, see [LICENSE](LICENSE).
