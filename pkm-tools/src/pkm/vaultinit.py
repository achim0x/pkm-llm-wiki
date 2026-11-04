"""``pkm init``: create the structure and initialize the git directory outside the vault.

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
from importlib import resources
from pathlib import Path
from typing import Any

from .config import IMPORT_FOLDER, Config
from .errors import PkmError
from .fsutil import write_bytes_atomic
from .gitlayer import Git
from .state import FORMAT as STATE_FORMAT

# Variables *******************************************************************

DIRS = [
    "documents/_inbox",
    "documents/_attachments",
    "wiki/topics",
    "wiki/entities",
    "wiki/summaries",
    "wiki/syntheses",
    "wiki/_lint",
    "scratch",
    IMPORT_FOLDER,
    ".pkm",
]
SCRATCH_IGNORE = "scratch/"
IGNORED_FOLDERS = ("scratch", IMPORT_FOLDER)
TYPES_FILE = ".obsidian/types.json"
# Obsidian property types (vault-wide per field name); values as in Obsidian's types.json.
PROPERTY_TYPES = {
    "title": "text",
    "short_citation": "text",
    "date_document": "text",
    "status_markdown": "text",
    "date_markdown": "datetime",
    "toolchain_markdown": "text",
    "id": "text",
    "version": "number",
    "date_updated": "datetime",
    "context": "text",
    "related": "multitext",
    "kind": "text",
    "type": "text",
    "sources": "multitext",
    "confidence": "text",
}

# Classes *********************************************************************

# Functions *******************************************************************


def _template(name: str) -> str:
    """Read a template from the package.

    Args:
        name: File name below ``pkm/templates``.

    Returns:
        Content of the template.
    """
    return resources.files("pkm").joinpath("templates", name).read_text(encoding="utf-8")


def initial_files() -> dict[str, str]:
    """Files that ``pkm init`` creates.

    Returns:
        Relative path → content.
    """
    return {
        "CLAUDE.md": _template("CLAUDE.md"),
        ".gitignore": _template("gitignore"),
        "wiki/index.md": "# Wiki index\n\n_No pages yet._\n",
        "wiki/log.md": "# Maintenance log\n",
        "wiki/_status.md": "# Status\n\n## Not yet processed (0)\n",
        ".pkm/state.json": json.dumps({"version": STATE_FORMAT, "documents": {}}, indent=2) + "\n",
    }


def _create_structure(cfg: Config) -> tuple[list[str], list[str]]:
    """Create missing folders and files; existing ones stay unchanged.

    Args:
        cfg: Configuration.

    Returns:
        Tuple of (created folders, created files).
    """
    cfg.root.mkdir(parents=True, exist_ok=True)
    created_dirs = [d for d in DIRS if not (cfg.root / d).is_dir()]
    for d in created_dirs:
        (cfg.root / d).mkdir(parents=True)
    created_files = [rel for rel in initial_files() if not (cfg.root / rel).exists()]
    for rel in created_files:
        (cfg.root / rel).write_bytes(initial_files()[rel].encode("utf-8"))
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    return created_dirs, created_files


def ensure_scratch_ignored(cfg: Config) -> bool:
    """Add ``scratch/`` and ``pkm_img_import/`` to an existing ``.gitignore`` if they are missing.

    Args:
        cfg: Configuration.

    Returns:
        ``True`` if the file was extended.
    """
    p = cfg.root / ".gitignore"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    missing = [f"{name}/" for name in IGNORED_FOLDERS if not folder_ignored(text, name)]
    if missing:
        new = text + ("" if not text or text.endswith("\n") else "\n") + "".join(f"{m}\n" for m in missing)
        p.write_bytes(new.encode("utf-8"))
    return bool(missing)


def folder_ignored(gitignore_text: str, name: str) -> bool:
    """Check whether a ``.gitignore`` excludes a top-level folder.

    Args:
        gitignore_text: Content of the ``.gitignore``.
        name: Folder name without slash.

    Returns:
        ``True`` for a line ``name``, ``name/``, ``/name`` or ``/name/``.
    """
    return any(line.strip().strip("/") == name for line in gitignore_text.splitlines())


def scratch_ignored(gitignore_text: str) -> bool:
    """Check whether a ``.gitignore`` excludes the area ``scratch/``.

    Args:
        gitignore_text: Content of the ``.gitignore``.

    Returns:
        ``True`` if a line reads ``scratch/``, ``/scratch/``, ``scratch`` or ``/scratch``.
    """
    return any(line.strip().strip("/") == "scratch" for line in gitignore_text.splitlines())


def read_property_types(root: Path) -> dict[str, Any] | None:
    """Read Obsidian's ``.obsidian/types.json``.

    Args:
        root: Vault root.

    Returns:
        Content as a dictionary; ``{}`` if the file is missing; ``None`` if it cannot be read.
    """
    p = root / TYPES_FILE
    data: dict[str, Any] | None = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict) or not isinstance(data.get("types", {}), dict):
            data = None
    return data


def property_type_conflicts(types: dict[str, Any]) -> dict[str, str]:
    """Fields whose type in Obsidian differs from the PKM schema.

    Args:
        types: Section ``types`` from ``.obsidian/types.json``.

    Returns:
        Field name → configured type (only differing, existing entries).
    """
    return {k: str(v) for k, v in types.items() if k in PROPERTY_TYPES and v != PROPERTY_TYPES[k]}


def ensure_property_types(root: Path) -> dict[str, Any]:
    """Add missing property types to ``.obsidian/types.json``.

    Existing entries (also differing ones) stay unchanged; differences are reported.
    If Obsidian is open, it reads the file only after a restart.

    Args:
        root: Vault root.

    Returns:
        ``created`` (new file), ``added`` (added fields), ``conflicts`` (differing types)
        and ``warning`` (text or ``None``).
    """
    existed = (root / TYPES_FILE).is_file()
    data = read_property_types(root)
    result: dict[str, Any] = {"created": False, "added": [], "conflicts": {}, "warning": None}
    if data is None:
        result["warning"] = f"{TYPES_FILE} cannot be read; property types not added."
    else:
        types = dict(data.get("types") or {})
        added = [k for k in PROPERTY_TYPES if k not in types]
        conflicts = property_type_conflicts(types)
        if added:
            types.update({k: PROPERTY_TYPES[k] for k in added})
            data["types"] = types
            write_bytes_atomic(root / TYPES_FILE, (json.dumps(data, indent=2) + "\n").encode("utf-8"))
        if conflicts:
            result["warning"] = "Obsidian property types differ: " + ", ".join(
                f"{k}={v} (expected {PROPERTY_TYPES[k]})" for k, v in conflicts.items())
        result.update(created=bool(added) and not existed, added=added, conflicts=conflicts)
    return result


def init_vault(cfg: Config) -> dict[str, Any]:
    """``pkm init`` (idempotent).

    Args:
        cfg: Configuration.

    Returns:
        What was created or extended, whether the repo is new, the initial commit and warnings.

    Raises:
        PkmError: ``config_error`` if the git directory or the search index would be inside the vault
            or the vault already contains a ``.git``.
    """
    for problem in (cfg.git_dir_problem(), cfg.cache_dir_problem()):
        if problem:
            raise PkmError("config_error", problem)
    if (cfg.root / ".git").exists():
        raise PkmError("config_error", "The vault contains a `.git`. Git must live outside (5.5).")
    created_dirs, created_files = _create_structure(cfg)
    updated_files = [".gitignore"] if ".gitignore" not in created_files and ensure_scratch_ignored(cfg) else []
    types = ensure_property_types(cfg.root)
    if types["created"]:
        created_files.append(TYPES_FILE)
    elif types["added"]:
        updated_files.append(TYPES_FILE)
    git = Git(cfg.git_dir, cfg.root)
    repo_created = git.init()
    git.run("config", "core.autocrlf", "false")  # Git for Windows: never convert line endings
    commit = None
    warnings: list[str] = [types["warning"]] if types["warning"] else []
    if not git.has_head():
        if git.config_get("user.name") and git.config_get("user.email"):
            paths = [rel for rel in [*initial_files(), TYPES_FILE] if (cfg.root / rel).exists()]
            commit = git.commit_paths(paths, "pkm: init\n")
        else:
            warnings.append("Git identity missing (user.name/user.email); initial commit skipped.")
    return {
        "status": "ok",
        "root": str(cfg.root),
        "git_dir": str(cfg.git_dir),
        "created_dirs": created_dirs,
        "created_files": created_files,
        "updated_files": updated_files,
        "repo_created": repo_created,
        "commit": commit,
        "warnings": warnings,
    }

# Main ************************************************************************
