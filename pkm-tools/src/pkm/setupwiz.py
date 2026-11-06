"""``pkm setup``: guided installation (specification 15.1).

Asks for the vault folder, checks Git (without Git the PKM runs without version control), asks for the
language of documents created in chat, writes ``config.toml``, runs ``pkm init``, enters the servers in
the configuration of Claude Desktop, builds the skill ZIP files and finally runs ``pkm doctor``. It can be
run again at any time.

    Author: Achim0x
"""

# *****************************************************************************
# Copyright (c) Achim0x - https://github.com/achim0x/
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# *****************************************************************************

# Imports *********************************************************************

from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any

from .cloudsync import cloud_service, online_only_files
from .config import (
    CONFIG_FILE,
    CONFIG_KEYS,
    DEFAULT_LANGUAGE,
    DOC_LANGUAGES,
    Config,
    default_app_dir,
    find_git,
    find_vault,
    parse_language,
    read_config_file,
    write_config_file,
)
from .doctor import doctor
from .errors import PkmError
from .gitlayer import Git
from .service import Service
from .vaultinit import init_vault

# Variables *******************************************************************

SKILLS = ("pkm-access", "pkm-wiki")
SERVERS = {"pkm": "pkm-mcp", "pkm-pflege": "pkm-pflege-mcp"}
NO_GIT_HINT = (
    "Git was not found. The PKM works without version control: documents get IDs and version numbers, "
    "but there is no history, no diff and no restoring of earlier versions. To turn version control on "
    "later, install Git (https://git-scm.com/install/) and run `pkm setup` again."
)
PROJECT_INSTRUCTIONS = (
    "This is the maintenance project for the PKM. Use the skill `pkm-wiki` and the tools of the server "
    "`pkm-pflege`. You do not change documents in `documents/`."
)

# Classes *********************************************************************


@dataclass
class SetupOptions:  # pylint: disable=too-many-instance-attributes
    """Answers that can be given in advance (command line); missing ones are asked.

    Attributes:
        vault: Vault folder.
        vault_name: Name of the Obsidian vault (default: folder name).
        git_name: Git user name for the PKM repo if no identity is set.
        git_email: Git e-mail address for the PKM repo if no identity is set.
        yes: Accept all defaults and confirmations without asking.
        claude_config: Path of ``claude_desktop_config.json`` (default per operating system).
        skills_dir: Target folder for the skill ZIP files (default ``<app folder>/skills``).
        language: Main language of documents created in chat, ``en`` or ``de``.
    """

    vault: str | None = None
    vault_name: str | None = None
    git_name: str | None = None
    git_email: str | None = None
    yes: bool = False
    claude_config: str | None = None
    skills_dir: str | None = None
    language: str | None = None


class Setup:  # pylint: disable=too-many-instance-attributes
    """Guided installation; every step is idempotent."""

    def __init__(self, opts: SetupOptions, ask: Callable[[str], str] = input, say: Callable[[str], None] = print,
                 env: Mapping[str, str] | None = None, git_finder: Callable[[], str | None] = find_git) -> None:
        """Create the setup.

        Args:
            opts: Answers given in advance.
            ask: Function for questions (returns the answer).
            say: Function for output.
            env: Environment variables; ``os.environ`` if omitted.
            git_finder: Function that finds the Git program (replaceable in tests).
        """
        self.opts = opts
        self.ask = ask
        self.say = say
        self.env = dict(os.environ if env is None else env)
        self.git_finder = git_finder
        self.config_path = Path(self.env.get("PKM_CONFIG") or self._app_dir() / CONFIG_FILE).expanduser()
        self.warnings: list[str] = []
        self.adopted: dict[str, str] = {}

    # Questions ****************************************************************

    def _app_dir(self) -> Path:
        """Default folder for configuration, Git directory and search index.

        Returns:
            The folder for the home directory of the environment.
        """
        return default_app_dir(Path(self.env["HOME"]) if self.env.get("HOME") else None)

    def _question(self, text: str, default: str | None) -> str:
        """Ask a question; with ``yes`` the default is taken.

        Args:
            text: Question.
            default: Default answer or ``None``.

        Returns:
            The answer (default for an empty answer).
        """
        answer = ""
        if not self.opts.yes:
            answer = self._read(f"{text}{f' [{default}]' if default else ''}: ")
        return answer or (default or "")

    def _read(self, prompt: str) -> str:
        """Read an answer; closed input (end of file) counts as an empty answer.

        Args:
            prompt: Question with the default.

        Returns:
            The answer without surrounding blanks.
        """
        try:
            answer = self.ask(prompt).strip()
        except EOFError:
            self.say("")
            answer = ""
        return answer

    def _confirm(self, text: str) -> bool:
        """Ask for a confirmation (default yes).

        Args:
            text: Question.

        Returns:
            ``True`` for yes.
        """
        return self.opts.yes or self._read(f"{text} [Y/n]: ").lower() in ("", "y", "yes", "j", "ja")

    # Steps ********************************************************************

    def _existing(self) -> dict[str, list[tuple[str, str]]]:
        """Collect the settings of an existing configuration.

        Sources in order of precedence: environment variables, the ``env`` blocks of the entries
        ``pkm`` and ``pkm-pflege`` in Claude Desktop (where installations before ``pkm setup`` kept
        their settings) and ``config.toml``.

        Returns:
            Key → list of (value, source), the value that applies first.
        """
        sources: list[tuple[str, Mapping[str, Any]]] = [("environment", self.env)]
        claude = self._read_claude(self._claude_config_path()) or {}
        servers = claude.get("mcpServers") if isinstance(claude.get("mcpServers"), dict) else {}
        for name in SERVERS:
            entry = servers.get(name) if isinstance(servers.get(name), dict) else {}
            block = entry.get("env") if isinstance(entry.get("env"), dict) else {}
            sources.append((f"Claude Desktop ({name})", block))
        try:
            sources.append((str(self.config_path), read_config_file(self.config_path)))
        except PkmError as exc:
            self.warn(exc.message)
        found: dict[str, list[tuple[str, str]]] = {}
        for source, values in sources:
            for key in CONFIG_KEYS:
                value = values.get(key)
                if value not in (None, "") and not any(v == str(value) for v, _ in found.get(key, [])):
                    found.setdefault(key, []).append((str(value), source))
        return found

    def _adopt(self) -> None:
        """Show an existing configuration and take it over if confirmed.

        Taken over, its values are the defaults of the questions and are written to ``config.toml``
        (e.g. ``PKM_GIT_DIR``, so the existing version history stays in use). Otherwise the setup
        starts with a new configuration; an existing ``config.toml`` is backed up first.
        """
        found = self._existing()
        if found:
            lines = []
            for key in CONFIG_KEYS:
                for i, (value, source) in enumerate(found.get(key, [])):
                    note = "" if i == 0 else "  (not used, overridden by the line above)"
                    lines.append(f"  {key} = {value}   [{source}]{note}")
            self.say("Existing configuration found:\n" + "\n".join(lines))
            if self._confirm("Take over this configuration?"):
                self.adopted = {key: values[0][0] for key, values in found.items()}
                self.say("Existing configuration taken over.")
            elif self.config_path.is_file():
                self.say(f"Starting with a new configuration; backup of the old one: {backup_file(self.config_path)}")

    def _known(self, key: str) -> str | None:
        """Value of a taken-over setting.

        Args:
            key: Configuration key.

        Returns:
            The value or ``None``.
        """
        return self.adopted.get(key) or None

    def _vault(self) -> Path:
        """Determine the vault folder (create it if confirmed).

        Returns:
            Absolute path of the vault.

        Raises:
            PkmError: ``config_error`` without a usable folder.
        """
        known = self.env.get("PKM_ROOT") or self._known("PKM_ROOT")
        found = find_vault(Path.cwd())
        default = known or (str(found) if found else None)
        answer = self.opts.vault or self._question(
            "Vault folder (absolute path; inside your cloud storage folder if you use one)", default)
        root = Path(answer).expanduser() if answer else None
        if root is None or not root.is_absolute():
            raise PkmError("config_error", "Please give the vault folder as an absolute path.")
        if not root.is_dir():
            if not self._confirm(f"{root} does not exist. Create it?"):
                raise PkmError("config_error", f"Vault folder missing: {root}")
            root.mkdir(parents=True)
        service = cloud_service(root)
        self.say(f"Vault: {root} ({service or 'no recognized cloud folder'}).")
        online = online_only_files(root, limit=5)
        if online:
            self.warn(f"Files only available online in the vault (e.g. {online[0]}): keep the vault folder "
                       "available on this device in the settings of your cloud storage.")
        return root

    def _git(self) -> str | None:
        """Check whether Git is installed.

        Returns:
            Path of the Git program or ``None`` (then without version control).
        """
        given = self.env.get("PKM_GIT") or self._known("PKM_GIT")
        exe = given if given and Path(given).is_file() else None
        exe = exe or self.git_finder()
        if exe:
            self.say(f"Git: {exe} - version control is on.")
        else:
            self.warn(NO_GIT_HINT)
        return exe

    def _language(self) -> str:
        """Ask for the main language of documents created in chat.

        Returns:
            ``en`` or ``de``.

        Raises:
            PkmError: ``config_error`` for an unknown language.
        """
        known = self.env.get("PKM_LANGUAGE") or self._known("PKM_LANGUAGE")
        answer = self.opts.language or self._question(
            "Main language of documents created in chat (en = English, de = German)",
            parse_language(known) if known else DEFAULT_LANGUAGE)
        language = parse_language(answer)
        self.say(f"Document language: {DOC_LANGUAGES[language][0]}.")
        return language

    def _write_config(self, root: Path, git_exe: str | None, language: str = DEFAULT_LANGUAGE) -> dict[str, str]:
        """Write ``config.toml``; other keys in the file are kept.

        Args:
            root: Vault folder.
            git_exe: Git program or ``None``.
            language: Document language ``en`` or ``de``.

        Returns:
            Environment for the configuration of this setup.
        """
        values: dict[str, str | bool] = dict(self.adopted)
        values.update({"PKM_ROOT": str(root),
                       "PKM_VAULT_NAME": self.opts.vault_name or self._known("PKM_VAULT_NAME") or root.name,
                       "PKM_VERSIONING": git_exe is not None, "PKM_LANGUAGE": language})
        if git_exe:
            values["PKM_GIT"] = git_exe
        else:
            values.pop("PKM_GIT", None)
        write_config_file(self.config_path, values)
        self.say(f"Configuration written: {self.config_path}")
        overridden = [k for k, v in values.items() if k in self.env and k != "PKM_VERSIONING" and self.env[k] != str(v)]
        if overridden:
            self.warn("Environment variables take precedence over the configuration file: " + ", ".join(overridden))
        return {**self.env, "PKM_CONFIG": str(self.config_path),
                **{k: ("true" if v else "false") if isinstance(v, bool) else str(v) for k, v in values.items()}}

    def _identity(self, cfg: Config) -> None:
        """Set a missing Git identity for the PKM repo and switch commit signing off there.

        Args:
            cfg: Configuration (with version control).
        """
        git = Git(cfg.git_dir, cfg.root, exe=cfg.git_exe)
        if not (git.config_get("user.name") and git.config_get("user.email")):
            name = self.opts.git_name or self._question("Git user name for the version history", None)
            email = self.opts.git_email or self._question("Git e-mail address for the version history", None)
            if name and email:
                git.run("config", "user.name", name)
                git.run("config", "user.email", email)
                self.say("Git identity set for the PKM repo.")
            else:
                self.warn("Git identity missing: the server refuses writing tools until user.name and "
                           "user.email are set (run `pkm setup` again).")
        git.run("config", "commit.gpgsign", "false")

    def _claude_config_path(self) -> Path:
        """Path of the configuration of Claude Desktop.

        Returns:
            ``claude_desktop_config.json`` of the operating system or the given path.
        """
        home = Path(self.env["HOME"]) if self.env.get("HOME") else Path.home()
        if self.opts.claude_config:
            path = Path(self.opts.claude_config).expanduser()
        elif sys.platform == "darwin":
            path = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        elif sys.platform.startswith("win"):
            base = Path(self.env.get("APPDATA") or home / "AppData" / "Roaming")
            path = base / "Claude" / "claude_desktop_config.json"
        else:
            path = home / ".config" / "Claude" / "claude_desktop_config.json"
        return path

    def _server_entries(self) -> dict[str, dict[str, Any]]:
        """Entries for the two MCP servers.

        Returns:
            Server name → entry with the absolute path of the program; ``PKM_CONFIG`` only for a
            configuration file outside the default folder.
        """
        entries: dict[str, dict[str, Any]] = {}
        for name, program in SERVERS.items():
            path = find_program(program)
            if path is None:
                self.warn(f"Program {program} not found; install the package with `uv tool install` first.")
                continue
            entry: dict[str, Any] = {"command": path}
            if self.config_path != self._app_dir() / CONFIG_FILE:
                entry["env"] = {"PKM_CONFIG": str(self.config_path)}
            entries[name] = entry
        return entries

    def _read_claude(self, path: Path) -> dict[str, Any] | None:
        """Read the configuration of Claude Desktop.

        Args:
            path: Path of ``claude_desktop_config.json``.

        Returns:
            The content (empty if the file is missing) or ``None`` if it is not valid JSON.
        """
        data: dict[str, Any] | None = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8") or "{}")
                data = loaded if isinstance(loaded, dict) else None
            except (OSError, ValueError):
                data = None
        return data

    def _claude(self) -> dict[str, Any]:
        """Check the entries in the configuration of Claude Desktop and update them only with permission.

        First checks whether ``pkm`` and ``pkm-pflege`` are already entered as needed. If something is
        missing or different, it shows the changes and asks whether it may change the file (backup
        first). If the answer is no (or the file cannot be read), it shows the entries for entering
        them by hand.

        Returns:
            Path, ``status`` (``unchanged``, ``changed``, ``declined``, ``unreadable`` or ``skipped`` if the
            programs are not found), missing and
            differing entries and, if the user enters them by hand, the text to enter (``manual``).
        """
        path = self._claude_config_path()
        entries = self._server_entries()
        data = self._read_claude(path)
        servers = (data or {}).get("mcpServers") or {}
        missing = [n for n in entries if n not in servers]
        differing = [n for n, entry in entries.items() if n in servers and servers[n] != entry]
        result: dict[str, Any] = {"path": str(path), "status": "unchanged", "missing": missing,
                                  "differing": differing, "manual": None}
        if not entries:
            result["status"] = "skipped"
        elif data is None:
            self.warn(f"{path} is not valid JSON; Claude Desktop was not changed.")
            result.update(status="unreadable", manual=self._manual_claude(path, entries))
        elif not missing and not differing:
            self.say(f"Claude Desktop: the servers {', '.join(entries)} are already entered ({path}).")
        else:
            for name in missing:
                self.say(f"Claude Desktop: server {name} is missing; new entry: {json.dumps(entries[name])}")
            for name in differing:
                self.say(f"Claude Desktop: server {name} is entered as {json.dumps(servers[name])}; "
                         f"new entry: {json.dumps(entries[name])}")
            if self._confirm(f"May pkm setup change the Claude Desktop configuration {path}? "
                             "(Other servers stay, a backup is made first.)"):
                data.setdefault("mcpServers", {}).update({n: entries[n] for n in missing + differing})
                self._write_claude(path, data)
                result["status"] = "changed"
            else:
                result.update(status="declined", manual=self._manual_claude(path, entries))
        return result

    def _manual_claude(self, path: Path, entries: dict[str, dict[str, Any]]) -> str:
        """Show the entries for Claude Desktop so that the user can enter them by hand.

        Args:
            path: Path of ``claude_desktop_config.json``.
            entries: Server name → entry.

        Returns:
            The JSON text to enter.
        """
        text = json.dumps({"mcpServers": entries}, indent=2, ensure_ascii=False)
        self.say(f"Enter the following by hand in {path} (in Claude Desktop: Settings > Developer > "
                 "Edit Config). If the file already has \"mcpServers\", add only the two entries inside it "
                 "and keep the other servers. Then restart Claude Desktop.\n" + text)
        return text

    def _write_claude(self, path: Path, data: dict[str, Any]) -> None:
        """Write the configuration of Claude Desktop, with a backup of an existing file.

        Args:
            path: Path of the file.
            data: New content.
        """
        if path.is_file():
            self.say(f"Backup of the Claude Desktop configuration: {backup_file(path)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        self.say(f"Claude Desktop configured: {path} (restart Claude Desktop).")

    def _skills(self) -> list[str]:
        """Build the skill ZIP files.

        Returns:
            Paths of the ZIP files.
        """
        target = Path(self.opts.skills_dir).expanduser() if self.opts.skills_dir else self._app_dir() / "skills"
        paths = [str(p) for p in build_skill_zips(target)]
        self.say("Skills: upload these files in Claude Desktop (Settings > Capabilities > Skills):\n  "
                 + "\n  ".join(paths))
        return paths

    def warn(self, text: str) -> None:
        """Output a note and remember it.

        Args:
            text: Note.
        """
        self.warnings.append(text)
        self.say(f"Note: {text}")

    # Flow *********************************************************************

    def run(self) -> dict[str, Any]:
        """Run all steps.

        Returns:
            Results of the steps, notes and the result of ``pkm doctor``.
        """
        self._adopt()
        root = self._vault()
        git_exe = self._git()
        language = self._language()
        env = self._write_config(root, git_exe, language)
        cfg = Config.from_env(env)
        init = init_vault(cfg)
        if cfg.versioning:
            self._identity(cfg)
            if init["commit"] is None:
                init = init_vault(cfg)
        claude = self._claude()
        skills = self._skills()
        self.say("Project \"PKM-Pflege\" in Claude Desktop - project instructions:\n  " + PROJECT_INSTRUCTIONS)
        check = doctor(Service(cfg), short=True)
        for c in check["checks"]:
            self.say(f"Error: {c['message']}")
        self.say("Setup finished." if not check["errors"] else "Setup finished with errors (see above, `pkm doctor`).")
        return {"status": "ok" if not check["errors"] else "error", "root": str(root),
                "config_file": str(self.config_path), "versioning": cfg.versioning, "git": git_exe,
                "language": cfg.language,
                "init": init, "claude": claude, "skills": skills, "warnings": self.warnings, "doctor": check}

# Functions *******************************************************************


def backup_file(path: Path) -> Path:
    """Copy a file to ``<name>.<timestamp>.bak`` next to it.

    Args:
        path: Existing file.

    Returns:
        Path of the backup.
    """
    stem = f"{path.name}.{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    backup = path.with_name(f"{stem}.bak")
    n = 1
    while backup.exists():
        n += 1
        backup = path.with_name(f"{stem}-{n}.bak")
    shutil.copy2(path, backup)
    return backup


def find_program(name: str) -> str | None:
    """Find an installed program of the package (next to the running ``pkm`` or in ``PATH``).

    Args:
        name: Program name without extension.

    Returns:
        Absolute path or ``None``.
    """
    exe = name + (".exe" if sys.platform.startswith("win") else "")
    candidates = [Path(sys.argv[0]).absolute().parent / exe, Path(sys.executable).parent / exe]
    found = next((str(p) for p in candidates if p.is_file()), None)
    return found or shutil.which(name)


def build_skill_zips(target: Path) -> list[Path]:
    """Pack the skills of the package as ZIP files (folder name as top level, as Claude Desktop expects).

    Args:
        target: Target folder.

    Returns:
        Paths of the ZIP files.
    """
    target.mkdir(parents=True, exist_ok=True)
    root = resources.files("pkm").joinpath("skills")
    out = []
    for skill in SKILLS:
        path = target / f"{skill}.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in sorted(root.joinpath(skill).iterdir(), key=lambda i: i.name):
                if item.is_file():
                    zf.writestr(f"{skill}/{item.name}", item.read_bytes())
        out.append(path)
    return out

# Main ************************************************************************
