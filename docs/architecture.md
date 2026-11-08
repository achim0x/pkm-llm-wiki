# PKM with LLM wiki – Architecture and installation

This document describes the architecture of the PKM with LLM wiki and, in detail, how it is
installed on the PKM host. The binding requirements are in the (German)
[specification](specification.md), sections 2, 5.4, 5.5, 7, 8 and 15.1; the step-by-step guide for
users is [installation.md](installation.md) (German: [installation.de.md](installation.de.md)).

## Contents

- [1. Overview](#1-overview)
  - [1.1 Locations](#11-locations)
- [2. Installation at a glance](#2-installation-at-a-glance)
- [3. The installers](#3-the-installers)
  - [3.1 install.sh (macOS, Linux)](#31-installsh-macos-linux)
  - [3.2 install.ps1 (Windows)](#32-installps1-windows)
  - [3.3 What the installers change](#33-what-the-installers-change)
- [4. pkm setup](#4-pkm-setup)
  - [4.1 Flow](#41-flow)
  - [4.2 Configuration file and lookup](#42-configuration-file-and-lookup)
  - [4.3 Claude Desktop configuration](#43-claude-desktop-configuration)
  - [4.4 Files created or changed](#44-files-created-or-changed)
- [5. Version control is optional](#5-version-control-is-optional)
- [6. Runtime: how Claude Desktop uses the servers](#6-runtime-how-claude-desktop-uses-the-servers)
- [7. Manual installation](#7-manual-installation)
- [8. Verification and releases](#8-verification-and-releases)
- [9. pkm-tools: package structure](#9-pkm-tools-package-structure)
- [10. Entry points](#10-entry-points)
  - [10.1 pkm-mcp and pkm-maintenance-mcp](#101-pkm-mcp-and-pkm-maintenance-mcp)
  - [10.2 pkm (CLI)](#102-pkm-cli)
- [11. Service and the write path](#11-service-and-the-write-path)
- [12. Vault model, text and hashes](#12-vault-model-text-and-hashes)
- [13. Search index](#13-search-index)
- [14. Maintenance and citations](#14-maintenance-and-citations)
- [15. Images](#15-images)
- [16. Configuration, setup and environment checks](#16-configuration-setup-and-environment-checks)

## 1. Overview

The PKM is a folder of Markdown files (the **vault**). Usually a cloud storage service synchronizes
it to all devices; this is optional – the vault can also be a purely local folder on a single
computer. Exactly one computer, the **PKM host** (Mac or Windows), runs everything that writes:
the two MCP servers used by Claude Desktop, the command line tool `pkm` and – optionally – Git for
the version history. Other devices only edit the Markdown files, typically with Obsidian; Obsidian is
optional as well (any Markdown editor works).

```mermaid
flowchart LR
    subgraph Devices["Other devices"]
        OBS2["Obsidian, optional"]
    end
    subgraph Cloud["Cloud storage, optional (Nextcloud, OneDrive, Google Drive, Dropbox, iCloud Drive, ...)"]
        SYNC(("sync"))
    end
    subgraph Host["PKM host (Mac or Windows)"]
        CD["Claude Desktop / Cowork"]
        MCP["pkm-mcp<br/>(chats)"]
        PFL["pkm-maintenance-mcp<br/>(maintenance)"]
        CLI["pkm<br/>(CLI, setup)"]
        VAULT[("Vault<br/>documents/ wiki/ scratch/<br/>.pkm/state.json")]
        subgraph App["App folder (outside the cloud folder)"]
            CFG["config.toml"]
            GIT[("git/<br/>optional")]
            IDX[("index.db<br/>search cache")]
            SK["skills/*.zip"]
        end
        OBS1["Obsidian, optional"]
    end
    CD -- "stdio" --> MCP
    CD -- "stdio" --> PFL
    MCP --> VAULT
    PFL --> VAULT
    CLI --> VAULT
    MCP --> IDX
    MCP -.->|"if version control is on"| GIT
    PFL -.->|"if version control is on"| GIT
    MCP --> CFG
    PFL --> CFG
    CLI --> CFG
    OBS1 --> VAULT
    VAULT <--> SYNC
    SYNC <--> OBS2
```

| Component | Role |
|---|---|
| `pkm-mcp` | MCP server for all chats: search, read, create and continue documents, citations, images |
| `pkm-maintenance-mcp` | MCP server for the maintenance project: `begin_maintenance`, `write_wiki_page`, `set_document_metadata`, `rename_document`, `move_images`, `fix_images`, `extract_images`, `finish_maintenance` plus the reading tools |
| `pkm` | CLI for setup, checks (`doctor`, `lint`) and troubleshooting; contains the same maintenance building blocks |
| Skills `pkm-access`, `pkm-wiki` | Instructions for Claude in normal chats and in the maintenance project |
| Vault | Markdown files in the cloud folder (or a local folder without cloud storage); never contains `.git` or the search index |
| App folder | `config.toml`, Git directory, search index and skill ZIP files – outside every cloud folder |
| Git (optional) | One commit per document version; history, diff, restore, revertable agent runs |

All three programs come from one Python package, `pkm-tools`. They do not call an LLM and open no
network connections; the content work is done by Claude in Claude Desktop.

### 1.1 Locations

| Item | macOS | Windows | Linux (tests, CI) |
|---|---|---|---|
| Programs | `~/.local/bin/pkm`, `pkm-mcp`, `pkm-maintenance-mcp` | `%USERPROFILE%\.local\bin\*.exe` | `~/.local/bin/` |
| App folder | `~/Library/Application Support/pkm/` | `%APPDATA%\pkm\` | `$XDG_DATA_HOME/pkm` or `~/.local/share/pkm/` |
| Configuration | `<app folder>/config.toml` (or `PKM_CONFIG`) | same | same |
| Git directory | `<app folder>/git/` (or `PKM_GIT_DIR`) | same | same |
| Search index | `<app folder>/index.db` (or `PKM_CACHE_DIR`) | same | same |
| Skill ZIP files | `<app folder>/skills/` | same | same |
| Claude Desktop configuration | `~/Library/Application Support/Claude/claude_desktop_config.json` | `%APPDATA%\Claude\claude_desktop_config.json` | `~/.config/Claude/claude_desktop_config.json` |

## 2. Installation at a glance

The user runs one command; everything else is guided by `pkm setup`.

| Platform | Command |
|---|---|
| macOS (also Linux) | `curl -LsSf https://raw.githubusercontent.com/achim0x/pkm-llm-wiki/main/install.sh \| sh` |
| Windows (PowerShell) | `powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/achim0x/pkm-llm-wiki/main/install.ps1 \| iex"` |

```mermaid
flowchart TD
    A(["User runs the installer"]) --> B{"uv installed?"}
    B -- "no" --> C["Install uv<br/>(astral.sh installer, ~/.local/bin)"]
    B -- "yes" --> D
    C --> D{"git --version works?"}
    D -- "yes" --> E["Message: version control will be on"]
    D -- "no" --> F["Note: PKM runs without version control,<br/>install Git and run setup again to turn it on"]
    E --> G["Download the repository ZIP<br/>(PKM_ARCHIVE or GitHub main)"]
    F --> G
    G --> H["Unpack to a temporary folder,<br/>find pkm-tools/"]
    H --> I["uv tool install --force --reinstall pkm-tools<br/>-> pkm, pkm-mcp, pkm-maintenance-mcp"]
    I --> J["Remove the temporary folder"]
    J --> K[["pkm setup<br/>(section 4)"]]
    K --> L{"pkm doctor without errors?"}
    L -- "yes" --> M(["Done: upload skills, create project,<br/>restart Claude Desktop and Obsidian"])
    L -- "no" --> N(["Errors are listed;<br/>fix them and run pkm setup again"])
```

After the installer the user does three things by hand, because Claude Desktop offers no interface
for them: upload the two skill ZIP files, create the project "PKM Maintenance" with the printed
instructions, and restart Claude Desktop (and Obsidian, if used, so that it reads the new settings).

## 3. The installers

### 3.1 `install.sh` (macOS, Linux)

1. **uv.** Uses `uv` from `PATH` or `~/.local/bin/uv`; otherwise installs it with the official
   installer (`curl -LsSf https://astral.sh/uv/install.sh | sh`). `uv` brings a suitable Python, so
   Python does not have to be installed.
2. **Git check.** Runs `git --version`. On macOS `/usr/bin/git` exists even without the developer
   tools but only shows an installation prompt; the check therefore runs the program instead of
   looking for the file. Without Git the installer prints a note and continues. It never installs
   Git itself.
3. **Download.** Fetches the ZIP archive of the repository (default
   `https://github.com/achim0x/pkm-llm-wiki/archive/refs/heads/main.zip`, overridable with
   `PKM_ARCHIVE`, e.g. for a branch or a local file in CI) into a temporary folder and unpacks it.
   The archive is used instead of `uv tool install git+https://…` because that would require Git,
   and uv ignores the `subdirectory` of archive URLs.
4. **Package.** `uv tool install --force --reinstall <unpacked>/pkm-tools` creates an isolated
   environment for the package and links `pkm`, `pkm-mcp` and `pkm-maintenance-mcp` into
   `~/.local/bin`. The temporary folder is removed on exit.
5. **Setup.** Starts `~/.local/bin/pkm setup` and passes all arguments of the installer on. When
   the installer was started via `curl … | sh`, standard input is the script itself; the answers
   are then read from `/dev/tty`.
6. Prints a hint to run `uv tool update-shell` if `pkm` is not found in a new terminal.

The script uses `set -eu`; it fails if a step fails, including `pkm setup` reporting errors.

### 3.2 `install.ps1` (Windows)

Same steps with PowerShell means: `Get-Command uv`, the uv PowerShell installer,
`Get-Command git`, `Invoke-WebRequest` (or `Copy-Item` if `PKM_ARCHIVE` is a local path),
`Expand-Archive`, `uv tool install`, and `pkm.exe setup`. Arguments for `pkm setup` are passed via
`$env:PKM_SETUP_ARGS` because `irm … | iex` cannot pass arguments. If `pkm setup` reports errors,
the script throws (instead of `exit`, which would close an interactive PowerShell session).

### 3.3 What the installers change

Only two things without asking: the installation of `uv` (if missing) and of the package
`pkm-tools`. Everything that touches the vault, the Git configuration or Claude Desktop happens in
`pkm setup`, with questions where existing data would change.

**Updating** means running the installer again: it reinstalls the package from the current archive
and runs `pkm setup`, which changes nothing that is already in place. Afterwards the skill ZIP files
should be uploaded again.

## 4. `pkm setup`

`pkm setup` (module `setupwiz.py`) is an interactive, idempotent wizard. It starts by collecting an
existing configuration from the environment, the `env` blocks of the PKM entries in Claude Desktop
(where installations from before `pkm setup` kept their settings; `is_pkm_entry()` recognizes them
by the names `pkm`/`pkm-maintenance` or by the programs `pkm-mcp`/`pkm-maintenance-mcp`) and `config.toml`,
in this order of precedence, for all keys of `CONFIG_KEYS`. If none of them sets `PKM_ROOT`, the
vault is read from `core.worktree` in the config of the Git directory (`worktree_of()`), provided the
folder contains `.pkm/state.json`. It shows them with their
source and, if confirmed, takes them over as defaults and into `config.toml`; this keeps e.g. a
custom `PKM_GIT_DIR` and so the version history. If declined, an existing `config.toml` is backed up
and the setup starts anew. After `pkm init` (which never overwrites an existing `CLAUDE.md`) the
wizard compares the vault's `CLAUDE.md` with the template of the installed version; if it differs,
it asks whether to replace it (backup to `<app folder>/backups/`, commit with Git) or writes the
template as `CLAUDE.md.new` next to it. An old Claude Desktop entry `pkm-pflege` is replaced by
`pkm-maintenance` in the Claude Desktop step. End of input counts as an empty answer (the default). Every answer can be given
in advance as an option; `--yes` accepts all defaults and confirmations (used by the installers in
CI).

| Option | Meaning |
|---|---|
| `--vault <folder>` | Vault folder (absolute path) |
| `--vault-name <name>` | Name of the Obsidian vault (default: folder name), for `obsidian://` links |
| `--git-name`, `--git-email` | Git identity for the PKM repo if none is set |
| `--language en\|de` | Main language of documents created in chat and of the wiki (`PKM_LANGUAGE`, default `en`) |
| `--yes` | Take defaults, confirm everything |
| `--claude-config <file>` | Path of `claude_desktop_config.json` (default per OS) |
| `--skills-dir <folder>` | Target folder of the skill ZIP files |
| `--json` | Print the result as JSON (messages go to standard error) |

### 4.1 Flow

```mermaid
flowchart TD
    S(["pkm setup"]) --> EX{"existing settings?<br/>environment, Claude Desktop env,<br/>config.toml, Git directory"}
    EX -- "no" --> V
    EX -- "yes" --> EX1{"show them,<br/>take them over?"}
    EX1 -- "yes" --> EX2["adopted values = defaults,<br/>written to config.toml"]
    EX1 -- "no" --> EX3["back up config.toml,<br/>start a new configuration"]
    EX2 --> V
    EX3 --> V["Vault folder:<br/>--vault, PKM_ROOT or adopted value<br/>or a vault above the current folder"]
    V --> V1{"absolute path?"}
    V1 -- "no" --> X1(["config_error"])
    V1 -- "yes" --> V2{"folder exists?"}
    V2 -- "no" --> V3{"create it?"}
    V3 -- "no" --> X2(["config_error"])
    V3 -- "yes" --> V4["mkdir"]
    V2 -- "yes" --> CS
    V4 --> CS["Detect the cloud service;<br/>warn about online-only files"]
    CS --> G{"Git found and working?<br/>(PKM_GIT, PATH, usual locations)"}
    G -- "no" --> G0["Note: no version control<br/>PKM_VERSIONING = false"]
    G -- "yes" --> G1["PKM_VERSIONING = true<br/>PKM_GIT = path"]
    G0 --> L["Language of chat documents and wiki:<br/>--language, previous value or en<br/>PKM_LANGUAGE = en | de"]
    G1 --> L
    L --> W["Write config.toml<br/>(other keys are kept)"]
    W --> I["pkm init:<br/>structure, CLAUDE.md, .gitignore, state.json,<br/>.obsidian/app.json, .obsidian/types.json"]
    I --> R{"version control on?"}
    R -- "no" --> SM
    R -- "yes" --> R1["Create the Git repo outside the vault<br/>core.autocrlf=false"]
    R1 --> ID{"user.name and user.email set?"}
    ID -- "no" --> ID1["Ask for name and e-mail,<br/>set them for the PKM repo only"]
    ID -- "yes" --> GPG
    ID1 --> GPG["commit.gpgsign=false for the PKM repo"]
    GPG --> IC{"initial commit exists?"}
    IC -- "no" --> IC1["pkm init again:<br/>commit pkm: init"]
    IC -- "yes" --> SM
    IC1 --> SM{"CLAUDE.md in the vault<br/>differs from the template?"}
    SM -- "no" --> CD
    SM -- "yes" --> SM1{"replace it?"}
    SM1 -- "yes" --> SM2["back up to app folder/backups,<br/>write template, commit (with Git)"]
    SM1 -- "no" --> SM3["write the template<br/>as CLAUDE.md.new"]
    SM2 --> CD
    SM3 --> CD["Check claude_desktop_config.json,<br/>change it only with permission<br/>(section 4.3)"]
    CD --> SKZ["Write pkm-access.zip and pkm-wiki.zip"]
    SKZ --> PI["Print the project instructions<br/>for PKM Maintenance"]
    PI --> DR["pkm doctor --short"]
    DR --> E{"errors?"}
    E -- "no" --> OK(["Setup finished, exit code 0"])
    E -- "yes" --> NOK(["Errors listed, exit code 1"])
```

### 4.2 Configuration file and lookup

`pkm setup` writes `config.toml` with flat keys named like the environment variables of
specification 7.1, for example:

```toml
# PKM configuration, written by `pkm setup`. Environment variables take precedence.

PKM_GIT = "/usr/bin/git"
PKM_LANGUAGE = "en"
PKM_ROOT = "/Users/name/Nextcloud/Vault"
PKM_VAULT_NAME = "Vault"
PKM_VERSIONING = true
```

`PKM_LANGUAGE` (`en` or `de`) is the main language of documents created in chat and of the wiki.
The servers `pkm` and `pkm-maintenance` read it at start (`configured_language()`, which falls back to `en` if the setting is missing or
invalid, so the server always starts) and appends a sentence to its MCP instructions naming the
language and its section names (`Result`, `Decisions`, `Open points`, `Context / rationale` or
`Ergebnis`, `Entscheidungen`, `Offene Punkte`, `Kontext / Begründung`); `pkm-maintenance`
(`wiki_language_instructions()`) names the wiki sections and the summary label (`Summary`, `Content`,
`Contradictions / open questions`, `See also`, `Citations` or `Kurzfassung`, `Inhalt`,
`Widersprüche / offene Fragen`, `Siehe auch`, `Belege`). The skills `pkm-access` and `pkm-wiki`
follow these instructions; the tools accept both variants. The generated wiki files (`index.md`,
`_status.md`, the heading of a new `log.md`) take their fixed texts from `wikitexts.py` in the wiki
language.

Every program (server or CLI) resolves its configuration the same way:

```mermaid
flowchart LR
    A["Environment variables"] -->|"take precedence"| M(("merged<br/>settings"))
    B["config.toml<br/>(PKM_CONFIG or app folder)"] --> M
    C["Defaults<br/>(app folder, Europe/Berlin, 200 KB, ...)"] --> M
    M --> R{"PKM_ROOT set?"}
    R -- "no (CLI)" --> S["Search upwards for .pkm/state.json"]
    R -- "yes" --> CFG["Config"]
    S --> CFG
    M --> GX{"PKM_GIT set?"}
    GX -- "no" --> GF["find_git(): PATH, /opt/homebrew/bin, /usr/local/bin,<br/>/usr/bin, C:/Program Files/Git/cmd<br/>(first one where git --version works)"]
    GX -- "yes" --> CFG
    GF --> CFG
```

Because the vault path and the Git program are in `config.toml`, the entries in Claude Desktop need
neither `env` nor `PATH`. This matters because Claude Desktop starts MCP servers with a minimal
environment without the user's shell profile.

### 4.3 Claude Desktop configuration

`pkm setup` first checks whether `pkm` and `pkm-maintenance` are already entered as needed. Only if an
entry is missing or different does it show the change and ask **once** whether it may change the
file. If the answer is no, nothing is changed and the entries are printed so that the user can add
them by hand (in Claude Desktop: Settings > Developer > Edit Config). With `--yes` the answer is yes.

```mermaid
flowchart TD
    A["Find pkm-mcp and pkm-maintenance-mcp<br/>(next to pkm, else PATH)"] --> F{"programs found?"}
    F -- "no" --> SK(["Warning, status skipped"])
    F -- "yes" --> B["Read claude_desktop_config.json<br/>(missing file = empty)"]
    B --> P{"valid JSON?"}
    P -- "no" --> W["Warning, file unchanged"]
    W --> MAN
    P -- "yes" --> C{"pkm and pkm-maintenance<br/>entered as needed?"}
    C -- "yes" --> OK(["Already entered: status unchanged,<br/>no question"])
    C -- "no" --> SHOW["Show missing entries and<br/>differing entries (old and new)"]
    SHOW --> ASK{"May pkm setup change<br/>the configuration?"}
    ASK -- "yes" --> BAK["Backup claude_desktop_config.json.DATE.bak<br/>(if the file exists)"]
    BAK --> WR["Add or replace only pkm and pkm-maintenance,<br/>write the file: status changed"]
    ASK -- "no" --> MAN["Print the JSON entries for entering by hand<br/>status declined or unreadable"]
    WR --> RS(["Restart Claude Desktop"])
    MAN --> RS
```

Other servers and all other keys of the file are kept. An entry looks like this:

```json
{
  "mcpServers": {
    "pkm": { "command": "/Users/name/.local/bin/pkm-mcp" },
    "pkm-maintenance": { "command": "/Users/name/.local/bin/pkm-maintenance-mcp" }
  }
}
```

Only if the configuration file is not in the default app folder does `pkm setup` add
`"env": {"PKM_CONFIG": "<file>"}`.

### 4.4 Files created or changed

| File | Created/changed by | Notes |
|---|---|---|
| `<app folder>/config.toml` | `pkm setup` | Merged with existing keys |
| `<vault>/documents/_inbox/`, `wiki/…`, `scratch/`, `pkm_img_import/`, `.pkm/` | `pkm init` | Only missing folders |
| `<vault>/CLAUDE.md`, `wiki/index.md`, `wiki/log.md`, `wiki/_status.md`, `.pkm/state.json` | `pkm init` | Only if missing |
| `<vault>/.gitignore` | `pkm init` | Created, or missing `scratch/` and `pkm_img_import/` added |
| `<vault>/.obsidian/app.json` | `pkm init` | Missing settings of specification 13 added; different values kept and reported |
| `<vault>/.obsidian/types.json` | `pkm init` | Missing property types added; different types kept and reported |
| `<app folder>/git/` | `pkm init` | Only with version control; local `user.name`/`user.email` if asked, `commit.gpgsign=false`, `core.autocrlf=false` |
| `claude_desktop_config.json` (+ `.bak`) | `pkm setup`, only with permission | Section 4.3 |
| `<app folder>/skills/pkm-access.zip`, `pkm-wiki.zip` | `pkm setup` | Built from the skills inside the package |

## 5. Version control is optional

`PKM_VERSIONING` decides whether Git is used. `pkm setup` sets it from the Git check; an explicit
environment variable overrides it.

| Function | With Git (`PKM_VERSIONING = true`) | Without Git (`false`) |
|---|---|---|
| Writing tools | New version, one commit per change (`commit: <hash>`) | New version number, no commit (`commit: null`) |
| `history`, `read` with `version`, `pkm show`, `restore_document` | Available | `not_versioned` with a hint how to turn it on |
| Manual changes in Obsidian | Committed as a version by `pkm versions` (start of each maintenance run) | Detected by `pending` via the hashes in `state.json` |
| `pkm commit-wiki`, agent commit in `finish_maintenance` | One commit for `wiki/` and `state.json` | Nothing to commit (`status: unchanged`) |
| Citations of an older version | Checked against the text of that version from Git | Checked against the current text if the cited section is unchanged; otherwise `newer_version` |
| Write lock | `<git dir>/pkm.lock` | `<cache dir>/pkm.lock` |
| `pkm doctor` | Git found, repo, identity, signing | Note `versioning` (not an error) |

**Turning it on later:**

```mermaid
sequenceDiagram
    actor U as User
    participant S as pkm setup
    participant G as Git
    participant M as Maintenance run
    U->>U: install Git
    U->>S: run pkm setup again
    S->>S: find_git() succeeds, PKM_VERSIONING = true
    S->>G: create repo outside the vault, identity, gpgsign off
    S->>G: commit "pkm: init" (base files)
    U->>M: "Process new documents"
    M->>G: pkm versions: commit every document with its current version ("first version by hand")
    Note over G: From now on every change is a version with a commit;<br/>there is no history for the time before
```

## 6. Runtime: how Claude Desktop uses the servers

```mermaid
sequenceDiagram
    participant CD as Claude Desktop
    participant S as pkm-mcp
    participant C as config.toml
    participant V as Vault
    participant G as Git (optional)
    CD->>S: start process (command from claude_desktop_config.json)
    S->>C: read settings (environment first)
    CD->>S: initialize, tools/list
    CD->>S: read(target)
    S->>V: load, normalize, hash
    S-->>CD: content with placeholders, hash, sections
    CD->>S: rewrite_document(target, content, expected_hash)
    S->>V: check hash, write atomically (version + 1)
    alt version control on
        S->>G: commit only this file (PKM-Id, PKM-Version, PKM-Source)
    end
    S-->>CD: status changed, version, commit or null, diff
```

The servers run only while Claude Desktop is open on the PKM host; Cowork reaches them through the
desktop app. `pkm-maintenance` should only be enabled in maintenance conversations, because Claude Desktop
cannot restrict a server to one project.

## 7. Manual installation

For special cases the steps of the installer can be done by hand (details in
[installation.md](installation.md), appendix A):

1. Install `uv`.
2. Install the package: with Git directly from GitHub
   (`uv tool install "git+https://github.com/achim0x/pkm-llm-wiki#subdirectory=pkm-tools"`,
   later `uv tool upgrade pkm-tools`), or from an unpacked ZIP of the repository
   (`uv tool install --force <unpacked>/pkm-tools`).
3. Run `pkm setup` – or write `config.toml` by hand, run `pkm init` and add the two entries to
   `claude_desktop_config.json`.

## 8. Verification and releases

- **CI** (`.github/workflows/pkm-tools.yml`): ruff, pylint and the test suite on Linux, macOS and
  Windows (Python 3.12). A second job `installer` builds a ZIP of the commit with `git archive`, runs
  `install.sh` (Linux, macOS) or `install.ps1` (Windows) with `PKM_ARCHIVE` pointing to it and
  `pkm setup --yes` with a temporary `--claude-config`, and finally `pkm doctor --short`. The tests `test_setup.py` and
  `test_no_git.py` cover the wizard (with and without Git, repeated runs, existing Claude Desktop
  configuration, missing identity) and the operation without version control.
- **Releases** (`.github/workflows/release.yml`): for every tag `v*` a GitHub release with the wheel
  of `pkm-tools` and the two skill ZIP files.
- The one-line installers download from the branch `main`; changes on other branches reach users
  only after a merge (or with `PKM_ARCHIVE` pointing to the branch archive).

## 9. pkm-tools: package structure

`pkm-tools` is one Python package (`src/pkm/`, about 13,800 lines in 40 modules) with three entry
points. The modules form layers; a module only uses modules of the same or a lower layer (lower
modules refer to the service façade and the writer only for type hints, under `TYPE_CHECKING`).

```mermaid
flowchart TB
    subgraph EP["Entry points"]
        direction LR
        mcp_server["mcp_server<br/>pkm-mcp"]
        maintenance_server["maintenance_server<br/>pkm-maintenance-mcp"]
        cli["cli<br/>pkm"]
    end
    subgraph APP["Application"]
        direction LR
        service["service<br/>(facade)"]
        maintrun["maintrun<br/>(maintenance run)"]
        setupwiz["setupwiz<br/>(pkm setup)"]
    end
    subgraph DOM["Domain"]
        direction LR
        writer["writer"]
        maint["maint"]
        citations["citations / citeraise"]
        lint["lint / imagelint / doctor"]
        wikigen["wikigen"]
        img["images / imagescan /<br/>imagefix / docimages / assets"]
        index["index"]
    end
    subgraph MODEL["Model and storage"]
        direction LR
        vault["vault"]
        state["state"]
        gitlayer["gitlayer"]
        vaultinit["vaultinit"]
        cloudsync["cloudsync"]
    end
    subgraph BASE["Foundation"]
        direction LR
        text["normalize / parse / hashes /<br/>frontmatter / pagetext / appendtext"]
        meta["schema / ids / paths"]
        sys["config / errors / fsutil / diffs"]
    end
    EP --> APP
    APP --> DOM
    DOM --> MODEL
    MODEL --> BASE
    DOM --> BASE
```

| Layer | Modules | Responsibility |
|---|---|---|
| Entry points | `mcp_server`, `maintenance_server`, `cli` | Thin wrappers: register tools or subcommands, turn `PkmError` into a status, log calls |
| Application | `service`, `maintrun`, `setupwiz` | One method per tool or command; the maintenance run in three steps; the setup wizard |
| Domain | `writer`, `docimages`, `maint`, `citations`, `citeraise`, `lint`, `imagelint`, `doctor`, `wikigen`, `images`, `imagescan`, `imagefix`, `assets`, `index` | Writing with versions, maintenance commands, citations, checks, generated wiki files, images, search |
| Model and storage | `vault`, `state`, `gitlayer`, `vaultinit`, `cloudsync` | Files in the vault, processing state, Git with a separate directory, vault structure, cloud storage |
| Foundation | `normalize`, `parse`, `hashes`, `frontmatter`, `pagetext`, `appendtext`, `schema`, `ids`, `paths`, `config`, `errors`, `fsutil`, `diffs` | Text normalization, sections and hashes (spec 4.8), frontmatter schema (4.1), IDs, safe paths, configuration, atomic files |

Common rules: no network access, no LLM calls, no background processes; every domain error is a
`PkmError` with a machine-readable `status` (e.g. `conflict`, `not_versioned`); files are written
atomically (`fsutil`); all writes go through one lock file.

## 10. Entry points

### 10.1 `pkm-mcp` and `pkm-maintenance-mcp`

```mermaid
flowchart LR
    subgraph mcp["MCP layer"]
        mcp_server["mcp_server<br/>register_read_tools()<br/>register_write_tools()<br/>call(), image_content()"]
        maintenance_server["maintenance_server<br/>register maintenance tools"]
    end
    SDK["mcp SDK<br/>(FastMCP / MCPServer, stdio)"]
    service["service.Service"]
    maintrun["maintrun"]
    config["config.Config"]
    log[(".pkm/mcp.log")]
    maintenance_server -- "reuses read tools" --> mcp_server
    mcp_server --> SDK
    maintenance_server --> SDK
    mcp_server --> service
    maintenance_server --> maintrun
    maintrun --> service
    mcp_server --> config
    mcp_server --> log
```

Both servers are built from the same functions: `pkm-maintenance-mcp` registers the reading tools of
`pkm-mcp` (`register_read_tools`) plus the maintenance tools, but none of the document writing tools.
Every tool goes through `call()`:

```mermaid
sequenceDiagram
    participant C as Claude Desktop
    participant T as Tool function
    participant K as call()
    participant S as Service (created once)
    participant L as mcp.log
    C->>T: tools/call (arguments)
    T->>K: call(name, Service.method, **arguments)
    K->>S: get_service() on first use: Config.from_env()
    K->>S: method(**arguments)
    alt success
        S-->>K: result dict
    else PkmError
        S-->>K: raises PkmError
        K->>K: result = {status, message, ...}
    end
    K->>L: append one JSON line (tool, arguments, status)
    K-->>T: result
    T-->>C: JSON (read_image: also image content)
```

### 10.2 `pkm` (CLI)

```mermaid
flowchart LR
    cli["cli<br/>build_parser(), main()"]
    setupwiz["setupwiz"]
    service["service"]
    maint["maint.Maintenance"]
    other["citations, lint, doctor,<br/>wikigen, vaultinit,<br/>docimages, imagefix"]
    config["config"]
    cli -- "pkm setup" --> setupwiz
    cli -- "all other commands" --> config
    cli --> service
    cli --> maint
    cli --> other
```

`main()` writes UTF-8 (Windows uses cp1252 for pipes), parses the subcommand, builds `Config` (for
all commands except `setup`), runs the command and prints JSON. The exit code is 1 for any status
other than `ok`, `changed`, `created`, `unchanged` and `proposal`.

## 11. Service and the write path

```mermaid
flowchart TB
    service["service.Service<br/>search, read, history, show_citations,<br/>create/rewrite/append/edit, restore, ..."]
    subgraph write["Write path"]
        writer["writer.Writer<br/>lock, change, finish,<br/>create_document, ..."]
        appendtext["appendtext<br/>insert into sections"]
        docimages["docimages<br/>placeholders, new images"]
        diffs["diffs"]
    end
    subgraph read["Read path"]
        vault["vault.Vault / Doc"]
        index["index.SearchIndex"]
        citations["citations"]
    end
    gitlayer["gitlayer.Git"]
    state["state"]
    service --> writer
    service --> vault
    service --> index
    service --> citations
    service --> gitlayer
    service --> state
    writer --> appendtext
    writer --> docimages
    writer --> diffs
    writer --> vault
    writer --> gitlayer
```

Every changing tool (`rewrite_document`, `append_to_document`, `edit_document`, `add_image`,
`fix_images`, `update_frontmatter`, `restore_document`) runs through `Writer.change()`:

```mermaid
flowchart TD
    A(["change(target, expected_hash, transform)"]) --> L["Take the write lock<br/>(git dir or cache dir)"]
    L --> E["editable_doc(): resolve the target,<br/>only documents/ and scratch/, only Markdown"]
    E --> V{"versioned area and<br/>version control on?"}
    V -- "yes" --> G["require_git()<br/>(git_unavailable)"]
    V -- "no" --> H
    G --> H{"expected_hash = current hash?"}
    H -- "no" --> X1(["conflict"])
    H -- "yes" --> U{"version control on and<br/>file differs from last commit?"}
    U -- "yes" --> UC["commit the manual state first<br/>(PKM-Source: user)"]
    U -- "no" --> T
    UC --> T["transform(doc): new full text"]
    T --> I["check data URIs (nonconforming_image)<br/>place new images at their placeholders"]
    I --> S{"scratch/?"}
    S -- "yes" --> FS["finish_scratch(): write,<br/>no version, no commit"]
    S -- "no" --> F{"text changed?"}
    F -- "no" --> UN(["unchanged"])
    F -- "yes" --> FN["version + 1, date_updated,<br/>size and frontmatter check"]
    FN --> W["write atomically"]
    W --> C{"version control on?"}
    C -- "yes" --> CM["commit only this file (+ new images)<br/>reset the file on failure"]
    C -- "no" --> R
    CM --> R(["changed: version, new_hash,<br/>commit or null, diff"])
    FS --> R
```

## 12. Vault model, text and hashes

```mermaid
flowchart TB
    vault["vault<br/>Vault: iter_files, load, resolve<br/>Doc, summary_of, extract_links"]
    subgraph text["Text processing (spec 4.8)"]
        normalize["normalize<br/>UTF-8, LF, NFC"]
        parse["parse<br/>frontmatter, sections,<br/>duplicate suffixes"]
        hashes["hashes<br/>file, body, meta,<br/>section hashes"]
        pagetext["pagetext<br/>statements, footnotes"]
        frontmatter["frontmatter<br/>line-wise fields"]
    end
    subgraph meta["Schema and names"]
        schema["schema<br/>field order, kinds, tags"]
        ids["ids<br/>d-YYYYMMDD-HHMM-xxxx"]
        paths["paths<br/>safe_resolve, slugify,<br/>platform-safe names"]
    end
    config["config"]
    vault --> normalize
    vault --> parse
    vault --> hashes
    vault --> paths
    vault --> ids
    vault --> schema
    vault --> config
    hashes --> parse
    hashes --> schema
    frontmatter --> parse
    frontmatter --> schema
```

Loading a Markdown file always produces the same normalized view, independent of the operating
system and the editor:

```mermaid
flowchart LR
    B["bytes from disk"] --> N{"valid UTF-8?"}
    N -- "no" --> E1(["Doc with error invalid_encoding"])
    N -- "yes" --> T["normalize: no BOM, LF, NFC"]
    T --> P["parse: split frontmatter,<br/>YAML, sections level 1-2,<br/>keys with #2 suffixes"]
    P --> F{"frontmatter valid?"}
    F -- "no" --> E2["error invalid_frontmatter<br/>(text stays readable)"]
    F -- "yes" --> H["hashes: file_hash, body_hash,<br/>meta_hash, one hash per section"]
    E2 --> D(["Doc"])
    H --> D
```

Targets (`target` of every tool) are resolved by `Vault.resolve()` in this order: `id:` (via the
index, otherwise a scan), a path with `/`, a short name (file name without extension), and finally
`short_citation`. Several matches give `ambiguous` with candidates.

## 13. Search index

```mermaid
flowchart LR
    index["index.SearchIndex<br/>refresh, rebuild, search,<br/>find_id, backlinks"]
    sqlite[("SQLite FTS5<br/>PKM_CACHE_DIR/index.db")]
    vault["vault"]
    images["images.strip_images"]
    paths["paths.transliterate"]
    schema["schema.citation_key"]
    index --> sqlite
    index --> vault
    index --> images
    index --> paths
    index --> schema
```

```mermaid
flowchart TD
    Q(["search(query, scope)"]) --> O{"index opens and<br/>schema matches?"}
    O -- "no (damaged)" --> RB["delete and rebuild"]
    O -- "yes" --> RF
    RB --> RF["refresh: compare mtime and size,<br/>reindex changed files, drop deleted ones"]
    RF --> T["query terms: lower case,<br/>without diacritics, prefix search"]
    T --> A["FTS query: all terms (AND)"]
    A --> H{"hits?"}
    H -- "no" --> OR["FTS query: any term (OR)"]
    H -- "yes" --> R
    OR --> R(["hits ranked by BM25<br/>(title 5, aliases/tags 3, summary 2),<br/>with snippet"])
```

The index is a cache only: it never lives in the vault, can be deleted at any time and is rebuilt
when it is damaged. Text is indexed twice (original and with umlauts spelled out), so "Ueberlauf"
finds "Überlauf". Images are indexed only by their alt text.

## 14. Maintenance and citations

```mermaid
flowchart TB
    maintrun["maintrun<br/>begin_maintenance, write_wiki_page,<br/>set_document_metadata, rename_document,<br/>move_images, finish_maintenance"]
    inboxnames["inboxnames<br/>name proposals in the inbox,<br/>rename_document"]
    imageplace["imageplace<br/>image files into &lt;document&gt;_img/,<br/>move_images"]
    maint["maint.Maintenance<br/>ids, versions, pending, mark,<br/>sha, fix-frontmatter, commit-wiki"]
    subgraph cit["Citations"]
        citations["citations<br/>parse, resolve, show,<br/>fix-/sync-citations"]
        citeraise["citeraise<br/>raise v: of unchanged sections"]
    end
    subgraph checks["Checks"]
        lint["lint"]
        imagelint["imagelint"]
        doctor["doctor"]
    end
    wikigen["wikigen<br/>index.md, _status.md"]
    state["state<br/>state.json, classify"]
    assets["assets<br/>image files per document"]
    cloudsync["cloudsync<br/>conflict copies"]
    maintrun --> maint
    maintrun --> inboxnames
    maintrun --> imageplace
    inboxnames --> imageplace
    maintrun --> citations
    maintrun --> citeraise
    maintrun --> lint
    maintrun --> doctor
    maintrun --> wikigen
    maint --> state
    maint --> assets
    maint --> cloudsync
    citeraise --> citations
    lint --> citations
    lint --> imagelint
    lint --> cloudsync
    imagelint --> assets
    wikigen --> maint
```

A maintenance run (skill `pkm-wiki`) consists of three tool steps; the content work in between is
done by Claude:

```mermaid
flowchart TD
    B(["begin_maintenance"]) --> D{"doctor --short:<br/>errors?"}
    D -- "yes" --> BL(["blocked: nothing changed"])
    D -- "no" --> V["versions: commit manual changes<br/>(without Git: nothing)"]
    V --> I["ids: missing id/version"]
    I --> P["pending: new, changed, meta_changed,<br/>moved, deleted, problems,<br/>missing_fields, image_issues"]
    P --> M{"moved documents?"}
    M -- "yes" --> FC["fix-citations"]
    M -- "no" --> DUP
    FC --> DUP{"duplicate IDs?"}
    DUP -- "yes" --> ND(["needs_decision"])
    DUP -- "no" --> OK(["ok: pending, known_tags"])
    OK --> W["Claude reads documents and writes pages<br/>write_wiki_page (no commit)"]
    W --> F(["finish_maintenance"])
    F --> F1["fix-citations, raise versions,<br/>sync-citations (sources)"]
    F1 --> F2["mark processed documents<br/>(pages from the footnotes), remove deleted"]
    F2 --> F3["append wiki/log.md, build index.md<br/>and _status.md (with questions)"]
    F3 --> F4["lint (optional report)"]
    F4 --> F5["commit-wiki: agent commit<br/>(without Git: nothing)"]
```

`pending` compares each document with its entry in `state.json` (`state.classify`): equal body and
meta hash means processed; only a different meta hash gives `meta_changed`; otherwise `changed` with
the changed, added, removed and renamed sections. This works with and without Git.

## 15. Images

```mermaid
flowchart TB
    docimages["docimages<br/>place new images, placeholders in read,<br/>read_image, fix_document"]
    images["images<br/>find images, SVG sanitizing,<br/>PNG/JPEG checks, encoding"]
    imagescan["imagescan<br/>data URIs in every notation"]
    imagefix["imagefix<br/>findings, proposals, fixes,<br/>notation-only comparison"]
    assets["assets<br/>image files of documents,<br/>orphaned attachments"]
    imagelint["imagelint<br/>lint checks"]
    writer["writer"]
    maint["maint"]
    writer --> docimages
    docimages --> images
    docimages --> imagefix
    imagefix --> images
    imagefix --> imagescan
    images --> imagescan
    maint --> assets
    maint --> imagefix
    imagelint --> imagefix
    imagelint --> assets
    assets --> images
```

```mermaid
flowchart TD
    A(["writing tool with images or<br/>text containing data URIs"]) --> B["imagescan: find data URIs<br/>(inline, angle, reference, HTML)"]
    B --> C{"new data URIs conform<br/>to spec 4.9?"}
    C -- "no, fix_images not set" --> X(["nonconforming_image with findings<br/>and proposal; nothing written"])
    C -- "no, fix_images: true" --> FX["imagefix: rewrite in the 4.9 form"]
    C -- "yes" --> P
    FX --> P{"image placeholders in the text?"}
    P -- "no" --> W(["continue writing"])
    P -- "yes" --> S["images.prepare_image: read the source<br/>(svg, png_base64, import_path)"]
    S --> CH["sanitize SVG / check PNG, JPEG<br/>(remove metadata)"]
    CH --> M{"mode auto: size up to 24 KB<br/>or area scratch/?"}
    M -- "yes" --> IN["embed as data URI<br/>title pkm:name"]
    M -- "no" --> FI["write file to &lt;document&gt;_img/<br/>(identical file reused;<br/>same commit as the document)"]
    IN --> W
    FI --> W
```

`read` shows embedded images as placeholders `![alt](pkm-image:name "…")`; when the text comes back,
`docimages` puts the original bytes in again, so Base64 never passes through the model.

**Attachments** (`assets.AssetMap`): every Markdown document's linked images are resolved to files
(relative to the document, from the vault root, ignoring case, by Obsidian's shortest path, by bare
name). A resolved file is an attachment of the document wherever it lies; `pending` reports it with
the document (`images`, `images_changed`), never as an entry of its own, and `finish_maintenance`
skips it in `processed`. Standalone files are classified by path and hash (`maint._pending_files`):
`changed` for the same path with new content, `moved` only if the old path is gone, duplicates
neither; image files that only moved (same hash) appear as `images_moved`, and the earlier text is
compared with the recorded hashes (`assets._recorded_hash`), so a pure move is `image_notation_only`.
New image files go to `config.image_folder(doc)` (`<document name>_img/` next to the document), and
`imagefix.store_image` reuses an identical file there. `imageplace` plans and carries out moving the
image files of a document into that folder (generic names from the alt text, links adjusted, one agent
commit) for `move_images` and `rename_document`; `namelint` reports `naming` (inbox) and
`image_location` (other documents) with the same plan.

**Size limit and extract:** `writeguard.check_size` measures the text without data URIs; frontmatter
changes and `fix_images` skip it, and `confirm_large` (after the user's confirmation) skips it for a
single call of the four writing tools. `writeguard.check_shortening` is the shortening protection. `imagefix.extract_text` (``fix_images`` with ``extract``) writes
embedded raster images unchanged to files; `imagefix.canonical` compares linked files by hash, so the
follow-up run sees `image_notation_only` and `citeraise` raises the citations.

## 16. Configuration, setup and environment checks

```mermaid
flowchart TB
    setupwiz["setupwiz<br/>Setup.run(), build_skill_zips,<br/>find_program"]
    config["config<br/>Config.from_env, ImageConfig,<br/>read/write config.toml, find_git"]
    vaultinit["vaultinit<br/>init_vault, .gitignore,<br/>types.json, app.json"]
    doctor["doctor<br/>environment checks"]
    cloudsync["cloudsync<br/>cloud folders, online-only files"]
    gitlayer["gitlayer"]
    templates[("templates/<br/>CLAUDE.md, gitignore")]
    skills[("skills/<br/>pkm-access, pkm-wiki")]
    setupwiz --> config
    setupwiz --> vaultinit
    setupwiz --> doctor
    setupwiz --> cloudsync
    setupwiz --> gitlayer
    setupwiz --> skills
    vaultinit --> templates
    vaultinit --> gitlayer
    vaultinit --> config
    doctor --> cloudsync
    doctor --> vaultinit
    doctor --> config
```

The flows of `pkm setup` and of the configuration lookup are in sections 4.1 and 4.2. `pkm doctor`
groups its checks into paths (vault, cache directory, cloud folders, online-only files, conflict
copies, import folder, `.gitignore`), Git (only with version control: program, Git directory outside
any cloud folder, repo, identity, signing) and Obsidian (`app.json`, `types.json`); errors make the
status `error`, warnings and notes do not.
