# PKM with LLM wiki – Installation and setup

[Deutsch](installation.de.md) · **English**

This guide sets up the PKM on the **PKM host** (specification 5.5, 7.6, 11, 13, 15.1). How the
installer and `pkm setup` work inside is described in [architecture.md](architecture.md) (with flow
diagrams).
The PKM host is the one computer that runs Claude Desktop, the MCP servers `pkm-mcp` and
`pkm-maintenance-mcp`, the CLI `pkm` and (with Git) the version history. It can be a **Mac** or a
**Windows PC**; both are equally supported. Other devices (optional) only need the client of the
cloud storage and a Markdown editor, e.g. Obsidian.

**Exactly one PKM host per vault.** The version history lives locally on this computer and is not
synchronized. A second PKM host for the same vault would create a second, diverging history.

Summary:

1. Run the installer (installs uv and the package, starts `pkm setup`).
2. Answer the questions of `pkm setup` (vault folder, language, possibly Git name and
   e-mail).
3. Upload the two skill ZIP files in Claude Desktop.
4. Create the project "PKM Maintenance".
5. Restart Claude Desktop (and Obsidian, if you use it).

Placeholders:

| Placeholder | Mac | Windows |
|---|---|---|
| `<HOME>` | home directory, e.g. `/Users/name` | user folder, e.g. `C:\Users\name` |
| `<VAULT>` | vault folder; with cloud storage inside the folder of the service, otherwise any local folder | same |
| `<APPDIR>` | `<HOME>/Library/Application Support/pkm` | `%APPDATA%\pkm`, e.g. `C:\Users\name\AppData\Roaming\pkm` |

`<APPDIR>` contains the configuration file `config.toml`, the Git directory (`<APPDIR>/git`), the
search index (`<APPDIR>/index.db`) and the skill ZIP files (`<APPDIR>/skills`). It is deliberately
outside the vault and any cloud folder.

---

## 1. Requirements

- **Claude Desktop** (required).
- **Obsidian is optional**, but recommended. The vault consists of normal Markdown files; you can
  read and edit them with any editor. Obsidian adds wikilinks, backlinks, display of properties and
  embedded images, the graph view and automatic rewriting of links when moving files. Without
  Obsidian, keep in mind when moving documents: the maintenance run fixes citations and wikilinks in
  wiki pages (`fix-citations`), but not the links in your own documents. `pkm init` still creates
  the files under `.obsidian/`; without Obsidian they do no harm.
- **Cloud storage is optional.** The PKM also works purely locally: the vault is then a normal
  folder on the PKM host, and you work only on this computer. Cloud storage (Nextcloud, OneDrive,
  Google Drive, Dropbox, iCloud Drive, Syncthing …) is only needed if you also want to use the vault
  on other computers or your phone; then the vault lives in the folder of the service (section 7). A
  local vault can be moved into the cloud folder later; then run `pkm setup` again and give the new
  location.
- **Git is optional.** With Git every document gets a complete version history (`history`, diffs,
  restoring old versions, undoing maintenance runs with `git revert`). Without Git the PKM runs
  without version control: documents still get IDs and version numbers, the maintenance run detects
  changes via hashes, but there is no history and nothing to restore. Git can be added at any time
  (section 3).

  Installing Git, if wanted: <https://git-scm.com/install/>. On the Mac `xcode-select --install` is
  enough, on Windows `winget install Git.Git` (keep the default option "Git from the command line and
  also from 3rd-party software").
- Python does not have to be installed; the installer brings `uv`, which manages a suitable Python
  version.

## 2. Installation

There are three ways:

| Way | For whom | Where described |
|---|---|---|
| **Installer** (recommended) | The normal case: one command, then `pkm setup` guides you through the setup | this section and section 3 |
| **Manual installation** | If you want to run and see every step yourself, do not want to run scripts from the internet, or need a different setup (e.g. other folders) | [Appendix A](#appendix-a-manual-installation) |
| **Development installation** | If you want to change the code or the skills: the programs run directly from a local clone of the repository | [Appendix B](#appendix-b-development-installation) |

All ways lead to the same result; they can also be combined (e.g. install the package by hand and
then run `pkm setup`).

### 2.1 With the installer

Mac (Terminal):

```bash
curl -LsSf https://raw.githubusercontent.com/achim0x/pkm-llm-wiki/main/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/achim0x/pkm-llm-wiki/main/install.ps1 | iex"
```

The installer

1. installs `uv` to `<HOME>/.local/bin` if it is missing,
2. checks whether Git is available and prints a note otherwise,
3. downloads `pkm-tools` from GitHub and installs the commands `pkm`, `pkm-mcp` and
   `pkm-maintenance-mcp` to `<HOME>/.local/bin` (on Windows with the extension `.exe`),
4. starts `pkm setup` (section 3).

Apart from `uv` and the package the installer changes nothing without asking. **Updating:** run the
installer again; `pkm setup` offers to take over the existing configuration (section 3), also
from an installation made before `pkm setup` existed. If a new terminal reports that `pkm` is not found, run `uv tool update-shell` once.

Installation without the installer: [Appendix A](#appendix-a-manual-installation).

## 3. `pkm setup`

`pkm setup` guides you through the setup and can be run again at any time; every step is idempotent.

1. **Check for an existing configuration:** `pkm setup` looks for settings in the environment
   variables, in the PKM entries of Claude Desktop (installations from before `pkm setup` kept them
   in an `env` block there; recognized by the names `pkm`/`pkm-maintenance` or by the programs
   `pkm-mcp`/`pkm-maintenance-mcp`) and in `config.toml`. If none of them names the vault, it is read from
   the existing Git directory (which records the vault folder). If it finds any settings (e.g.
   `PKM_ROOT`, `PKM_GIT_DIR`, `PKM_CACHE_DIR`), it shows them with their source and asks whether to
   **take them over**. Yes: the values become the defaults of the following questions and are
   written to `config.toml`, so an existing Git directory and its history stay in use. No: the setup
   starts with a new configuration; an existing `config.toml` is backed up first
   (`config.toml.<time>.bak`).
2. Ask for the **vault folder** (absolute path; with cloud storage inside the folder of the service;
   created if it is missing). The cloud service is detected as well; files that exist only online
   are reported (section 7).
3. **Check Git.** If Git is available, version control is turned on. If the Git identity is
   missing, `pkm setup` asks for name and e-mail and sets them for the PKM repo only; commit signing
   is turned off for the PKM repo. **If Git is missing**, a note is shown and the PKM runs without
   version control.
4. Ask for the **language**: should documents created in chat and the wiki be mainly in English or
   German (`en` or `de`, default English or the previous answer; option `--language`)? The servers
   `pkm` and `pkm-maintenance` tell Claude this language and the matching section names (chat documents:
   Result, Decisions, Open points, Context / rationale or Ergebnis, Entscheidungen, Offene Punkte,
   Kontext / Begründung; wiki pages: Summary, Content, … or Kurzfassung, Inhalt, …). Existing
   documents and wiki pages keep their language; generated files such as `index.md` stay English. To change it later, run `pkm setup` again and restart Claude
   Desktop.
5. Write the **configuration file** `<APPDIR>/config.toml` (vault path, vault name, version control
   on or off, path of Git, language). Servers and CLI read it; environment variables take precedence.
6. Run **`pkm init`**: folder structure, `CLAUDE.md`, `.gitignore`, `.pkm/state.json`, Obsidian
   settings (`.obsidian/app.json`) and property types (`.obsidian/types.json`), with Git also the
   repo outside the vault with a first commit. Existing notes stay unchanged. If the vault already
   has a `CLAUDE.md` that differs from the template of this version (older version or own edits),
   `pkm setup` asks whether to replace it. Yes: the old file is backed up to `<APPDIR>/backups/`
   (outside the vault), the template is written and, with Git, committed. No: the file stays and the
   template is written next to it as `CLAUDE.md.new` to merge by hand (delete it afterwards).
7. **Check Claude Desktop:** `pkm setup` checks whether the servers `pkm` and `pkm-maintenance` are
   already entered as needed in `claude_desktop_config.json` (with `command` only, nothing else). If
   an entry is missing or different, the wizard shows the change and **asks whether it may change
   the file**. On "yes" it makes a backup and enters the servers; other servers stay unchanged. On
   "no" it changes nothing and shows the JSON text that you enter yourself under `mcpServers` (in
   Claude Desktop: Settings → Developer → "Edit Config"). If the file is not valid JSON, it is left
   alone and the text is shown as well. An entry with the old name `pkm-pflege` (up to version
   0.2.1) is replaced by `pkm-maintenance` in the same step.
8. Write the **skill ZIP files** to `<APPDIR>/skills/` (section 4).
9. Print the **project instructions** for "PKM Maintenance" (section 5).
10. Run **`pkm doctor`** and name any errors.

Options (all optional): `--vault <folder>`, `--vault-name <name>`, `--git-name <name>`,
`--git-email <address>`, `--language en|de`, `--yes` (defaults without asking), `--claude-config <file>`,
`--skills-dir <folder>`, `--json`.

**Turning version control on later:** install Git (section 1) and run `pkm setup` again. The wizard
finds Git, creates the repo and commits the base files (`pkm: init`). The documents go into Git with
their current version number at the start of the next maintenance run (`pkm versions`) or before
their next change from a chat (note "first version by hand"). There is no history for the time
before.

**After `pkm setup`:** quit Claude Desktop completely (on Windows also in the notification area of the
taskbar) and start it again. In a chat the 15 `pkm` tools appear among the tools (`search`, `read`,
`read_image`, `history`, `show_citations`, `read_index`, `list_unprocessed`, `create_document`,
`rewrite_document`, `append_to_document`, `edit_document`, `update_frontmatter`, `add_image`,
`fix_images`, `restore_document`) as well as the server `pkm-maintenance`.

**Enable `pkm-maintenance` only for maintenance.** Claude Desktop makes servers available to all
conversations; they cannot be restricted to a project. Therefore turn `pkm-maintenance` off in normal
conversations in the tools menu of the conversation and enable it only in maintenance conversations.
The server writes only to `wiki/` and `.pkm/state.json`, on documents only `id`/`version` and, after
your confirmation, `title`, `context`, `tags`, `kind`, `short_citation`. With Git every maintenance
run is an agent commit of its own and can be undone with `git revert`.

## 4. Uploading the skills

`pkm setup` creates `<APPDIR>/skills/pkm-access.zip` and `pkm-wiki.zip` (they are also attached to
every GitHub release). In Claude Desktop, upload and enable both files in the settings for skills
(depending on the app version "Settings → Capabilities → Skills"):

- `pkm-access` – for all normal chats (filing, continuing, queries, sources).
- `pkm-wiki` – for the maintenance project.

After an update upload the skills again (replace the old ones). Other existing skills stay
untouched.

## 5. Project "PKM Maintenance"

Maintenance runs in Claude Desktop (chat or Cowork) through the server `pkm-maintenance`. No shell on this
computer is needed.

1. Create a project "PKM Maintenance" in Claude Desktop.
2. Project instructions (also printed by `pkm setup`):

   > This is the maintenance project for the PKM. Use the skill `pkm-wiki` and the tools of the
   > server `pkm-maintenance`. You do not change documents in `documents/`.

3. Enable the server `pkm-maintenance` in the maintenance conversation.
4. Optionally connect the vault folder ("+" → "Add folder"). This is only needed so that Claude can
   read the content of PDFs and images; it reads Markdown via `read`.
5. Maintenance runs are started by hand: "Process new documents", "Lint". A scheduled task (daily
   "ingest, then lint") is set up only later and only on explicit instruction. Scheduled Cowork tasks
   run in the cloud and presumably reach `pkm-maintenance` only while this computer is on and Claude
   Desktop is open.

## 6. Obsidian (optional)

Without Obsidian this section does not apply. With Obsidian, open the vault folder as a vault.
`pkm init` (via `pkm setup`) writes the settings of specification 13 to `.obsidian/app.json`;
Obsidian picks them up after a restart:

| Setting | Value |
|---|---|
| Files & links → Automatically update internal links | on |
| Files & links → New link format | Absolute path in vault |
| Files & links → Use [[Wikilinks]] | on |
| Files & links → Default location for new attachments | `documents/_attachments` |
| Files & links → Excluded files | `.pkm/` |

Missing values are added; different values that you set stay and are reported as a warning
(`pkm init`, `pkm doctor`). Likewise `pkm init` creates or completes the **property types** in
`.obsidian/types.json`:

| Field | Type |
|---|---|
| `date_markdown`, `date_updated` | Date & time |
| `version` | Number |
| `related`, `sources` | List |
| `title`, `short_citation`, `date_document`, `status_markdown`, `toolchain_markdown`, `id`, `context`, `kind` | Text |
| `tags`, `aliases` | Obsidian default |

If Obsidian runs during `pkm setup`, restart it afterwards. A type can be changed by hand in the
properties area of a note via the icon left of the field name, or in the sidebar **All properties**
with a right click.

**Web Clipper (optional):** [Obsidian Web Clipper](https://obsidian.md/clipper) is not an Obsidian
plugin but a browser extension (Chrome, Firefox, Safari, Edge). Its settings are in the extension
itself (icon in the browser toolbar → gear):

- General → Vaults: enter the name of the vault.
- Templates → default template → *Note location*: `documents/_inbox`.

Also adapt the template to the schema: `title` (page title), `source` (URL), `date_document`
(publication date, if any), `date_markdown` (time of clipping in the format `YYYY-MM-DDTHH:MM:SS`),
`toolchain_markdown: Obsidian Web Clipper`, `tags`.

**Putting already converted standards into the vault:** titles of standards often contain `: ` and
must then be in quotes. `pkm lint` shows affected files, `pkm fix-frontmatter` lists them, and with
a target or `--all` it repairs them.

**Images:** the server imports photos and screenshots from a chat only from the import folder
`pkm_img_import/` in the vault (PNG, JPEG, SVG). It is not in Git and excluded from maintenance,
lint and search; if the vault is in cloud storage, you can also put images there from your phone.
Obsidian shows embedded images (data URIs) in reading and live preview mode. After the setup, have
a chat create a document with an embedded PNG and SVG once and check it in Obsidian.

Optional: Dataview, Graph view. The settings in `.obsidian/` are synchronized to the other devices
via the cloud storage as well. Do not use the Obsidian Git plugin.

## 7. Cloud storage (optional)

Without cloud storage this section does not apply; `pkm setup` then reports "no recognized cloud
folder", which is not an error. Every service that synchronizes a normal local folder is suitable
(Nextcloud/ownCloud, OneDrive, Google Drive, Dropbox, iCloud Drive, Syncthing …). Above all, keep
the **vault folder always local** (no files "online only"). What to watch out for per service is in
the README under "Cloud storage: pitfalls" and in specification 5.5.

No exclusions from the synchronization are needed, because Git and the search index are outside.
Optionally exclude `.obsidian/workspace*.json` (device-specific files).

## 8. Backup

With Git the version history exists only on the PKM host under `<APPDIR>/git`. Include this folder
in your backup; the search index (`<APPDIR>/index.db`) is only a cache and may be missing. Without
Git the cloud storage (with its file versions, if the service offers them) backs up the vault; there
is no history of its own then.

- **Mac:** Time Machine backs up `~/Library/Application Support/pkm/` automatically.
- **Windows:** File History does **not** back up `AppData` by default. Either add
  `%APPDATA%\pkm\git` explicitly to a backup program, or put the Git directory from the start into a
  backed-up folder outside any cloud folder, e.g. `C:\Users\name\pkm-git`: add the line
  `PKM_GIT_DIR = "C:\\Users\\name\\pkm-git"` to `<APPDIR>\config.toml` and run `pkm setup` again.

## 9. Trial run

With three to five documents of your own (there is no initial content):

1. **File from a chat:** "Put the result into the PKM." → confirm the draft → file in
   `documents/_inbox/` with `id` and `version: 1`.
2. **Own note:** create a note under `documents/…` (without frontmatter).
3. **PDF:** put a data sheet into `documents/…`.
4. **Maintenance run** in the project: "Process new documents." → summaries, topic pages with
   citations, index, status, log (with Git also an agent commit).
5. **Filing** (move the document out of `_inbox/`, preferably in Obsidian) → citations point to the
   new location.
6. **Continue** in a new chat: "Continue the discussion about …" → before/after, confirmation,
   `version: 2`.
7. **Sources:** "Where does the statement … come from?" → original, section, quote, version, status.
8. Finally: `pkm doctor` and `pkm lint` without errors.

The complete acceptance protocol is in [acceptance.md](acceptance.md) (German) and section 14 of the
specification.

## 10. Troubleshooting

| Problem | Check |
|---|---|
| Which version is installed? | `pkm --version`; `pkm setup` prints it as its first line and `pkm doctor` reports it as `version` (also seen in `begin_maintenance`). `uv tool list` shows the version uv installed (with an editable install it can be outdated) |
| Tools do not appear in Claude Desktop | Run `pkm setup` again (it enters the servers), quit Claude Desktop completely and restart it, log of Claude Desktop |
| `git_unavailable` | `pkm doctor`: Git found, repo present, identity set. Git uninstalled? Run `pkm setup` again (turns version control off) |
| `not_versioned` for `history`/`restore_document` | Version control is off (no Git) or the file is in `scratch/` |
| `commit_failed` | Signing (`commit.gpgsign`), write permissions; the file was reset |
| `conflict` | The file was changed in the meantime (e.g. in Obsidian or by sync) – read it again |
| `config_error` | Check `<APPDIR>/config.toml` or run `pkm setup` again |
| The search finds nothing new | `pkm reindex` (the index is only a cache) |
| Conflict copies ("conflicted copy" …) | Merge them, delete the copy, then `pkm versions` |

Logs of Claude Desktop: Mac `~/Library/Logs/Claude/`, Windows `%APPDATA%\Claude\logs\`. Log of all
MCP operations: `<VAULT>/.pkm/mcp.log`. `pkm doctor` also shows whether version control is on and
which Git is used.

View the version history directly (with Git):

Mac:

```bash
git --git-dir="<HOME>/Library/Application Support/pkm/git" --work-tree="<VAULT>" log --oneline
```

Windows:

```powershell
git --git-dir="$env:APPDATA\pkm\git" --work-tree="<VAULT>" log --oneline
```

---

## Appendix A: Manual installation

This guide replaces the installer and `pkm setup` completely. Every step can be checked on its own.
If you only want to install the package by hand, do steps A.1–A.3 and then run `pkm setup`
(section 3).

### A.1 Install uv

`uv` installs the package into an environment of its own and brings a suitable Python version.

Mac:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then open a new terminal. Check:

```bash
uv --version
```

### A.2 Git (optional)

With Git you get version control; without Git the PKM runs without it (section 1). Check whether Git
is available and runs (on the Mac without the developer tools an installation dialog appears
instead):

```bash
git --version
```

Step A.4 needs the path of Git. Mac:

```bash
command -v git
```

Windows:

```powershell
(Get-Command git).Source
```

### A.3 Install the package

Option 1 – with Git directly from GitHub (update later with `uv tool upgrade pkm-tools`):

```bash
uv tool install "git+https://github.com/achim0x/pkm-llm-wiki#subdirectory=pkm-tools"
```

Option 2 – without Git: download the repository as a ZIP from GitHub ("Code" → "Download ZIP"),
unpack it and install the folder `pkm-tools` (update: new ZIP, same command):

```bash
uv tool install --force --reinstall <UNPACKED>/pkm-tools
```

Afterwards `pkm`, `pkm-mcp` and `pkm-maintenance-mcp` are in `<HOME>/.local/bin` (Windows with `.exe`).
If a new terminal reports that `pkm` is not found:

```bash
uv tool update-shell
```

Check:

```bash
pkm --help
```

### A.4 Create the configuration file

Create `<APPDIR>/config.toml` (create the folder `<APPDIR>` if needed). The keys are named like the
environment variables of specification 7.1.

Mac, e.g. `~/Library/Application Support/pkm/config.toml`:

```toml
PKM_ROOT = "/Users/name/Nextcloud/Vault"
PKM_VAULT_NAME = "Vault"
PKM_VERSIONING = true
PKM_GIT = "/usr/bin/git"
PKM_LANGUAGE = "en"
```

Windows, e.g. `%APPDATA%\pkm\config.toml` (paths in single quotes, so the backslashes stay as they
are):

```toml
PKM_ROOT = 'C:\Users\name\Nextcloud\Vault'
PKM_VAULT_NAME = "Vault"
PKM_VERSIONING = true
PKM_GIT = 'C:\Program Files\Git\cmd\git.exe'
PKM_LANGUAGE = "en"
```

- `PKM_ROOT`: absolute path of the vault folder (with cloud storage inside the folder of the
  service, otherwise a local folder).
- `PKM_VERSIONING = false` if Git is missing or should not be used; `PKM_GIT` is then omitted.
- `PKM_LANGUAGE`: main language of documents created in chat and of the wiki, `"en"` (English,
  default) or `"de"` (German).
- Further optional keys: `PKM_GIT_DIR`, `PKM_CACHE_DIR` (both never in a cloud folder), `PKM_TZ`,
  `PKM_MAX_KB` (200, text without embedded images), `PKM_GIT_AUTHOR`, `PKM_IMPORT_DIR`,
  `PKM_IMAGE_FOLDER` (`attachments` = `documents/_attachments/`, or `document` = `<document name>_img/`
  next to the document), `PKM_INLINE_MAX_KB` (24), `PKM_SVG_MAX_KB` (200),
  `PKM_IMAGE_MAX_MB` (5), `PKM_IMAGE_PARAM_MAX_KB` (512), `PKM_SVG_RASTER` (`false`; to rasterize SVG
  also install the package `cairosvg`).
- A file at another location is selected with the environment variable `PKM_CONFIG`; it must then
  also be in the entry for Claude Desktop (A.7).

### A.5 Create the vault

```bash
pkm init
```

`pkm init` creates the folder structure, `CLAUDE.md`, `.gitignore`, `.pkm/state.json`,
`.obsidian/app.json` and `.obsidian/types.json` and, with `PKM_VERSIONING = true`, the Git directory
under `<APPDIR>/git`. Existing notes stay unchanged.

### A.6 Git identity and signing (only with Git)

Without name and e-mail the server refuses all writing tools. If no global identity is set, set it
for the PKM repo (Mac):

```bash
git --git-dir="$HOME/Library/Application Support/pkm/git" config user.name "First Last"
```

```bash
git --git-dir="$HOME/Library/Application Support/pkm/git" config user.email "name@example.org"
```

Windows:

```powershell
git --git-dir="$env:APPDATA\pkm\git" config user.name "First Last"
```

```powershell
git --git-dir="$env:APPDATA\pkm\git" config user.email "name@example.org"
```

Turn commit signing off for the PKM repo (otherwise commits from Claude Desktop fail if the signing
key is not reachable there). Mac:

```bash
git --git-dir="$HOME/Library/Application Support/pkm/git" config commit.gpgsign false
```

Windows:

```powershell
git --git-dir="$env:APPDATA\pkm\git" config commit.gpgsign false
```

If the identity was missing during `pkm init`, there is no first commit yet; then run `pkm init`
once more.

### A.7 Claude Desktop

Open `claude_desktop_config.json` (in Claude Desktop: Settings → Developer → "Edit Config"; Mac
`<HOME>/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`) and add the two entries
under `mcpServers`. Other servers stay. All paths absolute.

Mac:

```json
{
  "mcpServers": {
    "pkm": { "command": "/Users/name/.local/bin/pkm-mcp" },
    "pkm-maintenance": { "command": "/Users/name/.local/bin/pkm-maintenance-mcp" }
  }
}
```

Windows (double every backslash in JSON):

```json
{
  "mcpServers": {
    "pkm": { "command": "C:\\Users\\name\\.local\\bin\\pkm-mcp.exe" },
    "pkm-maintenance": { "command": "C:\\Users\\name\\.local\\bin\\pkm-maintenance-mcp.exe" }
  }
}
```

If `config.toml` is not in the default folder, add `"env": { "PKM_CONFIG": "<path of config.toml>" }`
to both entries. Environment variables in `env` take precedence over `config.toml`. Then quit Claude
Desktop completely and start it again.

### A.8 Pack and upload the skills

The skills are in the package under `pkm/skills/` (in the repository `pkm-tools/src/pkm/skills/`).
Ready-made ZIP files are attached to every GitHub release; to pack them yourself (in the unpacked or
cloned repository):

Mac:

```bash
cd <REPO>/pkm-tools/src/pkm/skills && zip -r pkm-access.zip pkm-access && zip -r pkm-wiki.zip pkm-wiki
```

Windows:

```powershell
cd <REPO>\pkm-tools\src\pkm\skills; Compress-Archive -Force pkm-access pkm-access.zip; Compress-Archive -Force pkm-wiki pkm-wiki.zip
```

Upload both ZIP files in Claude Desktop (section 4).

### A.9 Finish

```bash
pkm doctor
```

Expected: `"status": "ok"`. Then continue with section 5 (project "PKM Maintenance") and, if used,
section 6 (restart Obsidian so that it reads the settings from `app.json`).

**Updating:** reinstall the package (A.3), pack and upload the skills again (A.8). The other steps
stay valid.

## Appendix B: Development installation

For working on the PKM itself: the package is installed **editable** from a local clone of the
repository. The programs `pkm`, `pkm-mcp` and `pkm-maintenance-mcp` then load the code and the skills
directly from `<REPO>/pkm-tools/src/pkm`; a change in the clone needs no new installation.
Requirements as in section 1, plus Git for cloning; uv as in A.1.

### B.1 Install

```bash
git clone https://github.com/achim0x/pkm-llm-wiki.git <REPO>
```

```bash
uv tool install --editable <REPO>/pkm-tools
```

On Windows the same commands with `<REPO>\pkm-tools`. Then set up as usual:

```bash
pkm setup
```

`pkm setup` (section 3) asks for the vault, checks Git, asks for the language, writes
`config.toml`, enters the servers in Claude Desktop and builds the skill ZIP files – from the skills
in the clone. Continue with sections 4–6.

### B.2 Working with it

| Change | What to do |
|---|---|
| Python code | Takes effect the next time a program starts. For the MCP servers: quit Claude Desktop completely and start it again |
| Skills (`pkm-tools/src/pkm/skills/`) | Run `pkm setup` again (packs the ZIP files anew), upload them in Claude Desktop again (section 4) |
| Other branch (`git checkout …`) | The installed programs use the code of the branch that is checked out; restart Claude Desktop |
| Dependencies in `pyproject.toml` | Install again: `uv tool install --editable --force <REPO>/pkm-tools` |

Tests and checks run in a separate environment `<REPO>/pkm-tools/.venv` (see the
[pkm-tools README](../pkm-tools/README.md)); it does not affect the installed programs.

**Use a test vault** while you develop, so that your real vault and its history stay untouched. It
needs its own configuration file with its **own Git directory and search index**; otherwise the
test vault would use the Git directory of the real one (both default to the app folder). Create
`<HOME>/pkm-dev/config.toml` first (absolute paths, outside any cloud folder; forward slashes also
work on Windows):

```toml
PKM_GIT_DIR = "<HOME>/pkm-dev/git"
PKM_CACHE_DIR = "<HOME>/pkm-dev/cache"
```

Then run `pkm setup` with this file (it keeps the two keys and adds the rest):

```bash
PKM_CONFIG=<HOME>/pkm-dev/config.toml pkm setup --vault <HOME>/pkm-dev/vault
```

Windows (PowerShell):

```powershell
$env:PKM_CONFIG = "<HOME>\pkm-dev\config.toml"; pkm setup --vault <HOME>\pkm-dev\vault
```

`pkm setup` enters `PKM_CONFIG` in the Claude Desktop entries, so Claude Desktop then works with the
test vault. To switch back to the real vault, run `pkm setup` again without `PKM_CONFIG` (in
PowerShell first `Remove-Item Env:PKM_CONFIG`).

### B.3 Back to a normal installation

Run the installer again (section 2.1) or install the package without `--editable` (A.3). Both
replace the editable installation; configuration and vault stay as they are.

**Installing a fixed state of the clone** instead (without editable): the installer also takes a
local ZIP of the repository, e.g. `git -C <REPO> archive --format=zip --prefix=pkm-llm-wiki/ -o
<HOME>/pkm.zip HEAD` and then `PKM_ARCHIVE=file://<HOME>/pkm.zip sh <REPO>/install.sh` (Windows:
`$env:PKM_ARCHIVE = "<HOME>\pkm.zip"` before `install.ps1`).
