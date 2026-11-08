"""``pkm doctor`` (specification 8): check the environment.

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
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import __version__
from .cloudsync import cloud_service, conflict_copies, online_only_files
from .config import IMPORT_FOLDER
from .errors import PkmError
from .vaultinit import (
    OBSIDIAN_EXPECTED,
    PROPERTY_TYPES,
    TYPES_FILE,
    folder_ignored,
    property_type_conflicts,
    read_property_types,
    scratch_ignored,
)

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


def _check(name: str, ok: bool, ok_message: str, bad_message: str, severity: str = "error") -> dict[str, Any]:
    """Build a check result.

    Args:
        name: Name of the check.
        ok: Result.
        ok_message: Message on success.
        bad_message: Message on failure.
        severity: Severity on failure (``error`` or ``warning``).

    Returns:
        ``check``, ``ok``, ``severity`` (``ok`` on success) and ``message``.
    """
    return {"check": name, "ok": ok, "severity": "ok" if ok else severity, "message": ok_message if ok else bad_message}


def _git_checks(svc: Service) -> list[dict[str, Any]]:
    """Checks around git.

    Args:
        svc: Service.

    Returns:
        Check results; without version control only a note and the check for ``.git`` in the vault.
    """
    cfg = svc.cfg
    checks = [_check("no_dotgit_in_vault", not (cfg.root / ".git").exists(), "No .git in the vault.",
                     "The vault contains a .git (5.5).")]
    if svc.versioning:
        checks += _git_ready_checks(svc)
    else:
        checks.append(_check("versioning", True, "Version control is off (Git not installed). To turn it on, "
                             "install Git (https://git-scm.com/install/) and run `pkm setup` again.", ""))
    return checks


def _git_ready_checks(svc: Service) -> list[dict[str, Any]]:
    """Checks around git when version control is on.

    Args:
        svc: Service.

    Returns:
        Check results.
    """
    cfg, git = svc.cfg, svc.git
    git_dir_problem = cfg.git_dir_problem()
    git_cloud = cloud_service(cfg.git_dir)
    repo = git.installed() and git.is_repo()
    checks = [
        _check("git_installed", git.installed(), f"git found ({git.exe}).",
               "git not found: install Git or run `pkm setup` again to turn version control off."),
        _check("git_dir_outside", git_dir_problem is None, "Git directory is outside the vault.",
               git_dir_problem or ""),
        _check("git_dir_cloud", git_cloud is None, "Git directory is not in a cloud folder.",
               f"Git directory {cfg.git_dir} seems to be in a cloud folder ({git_cloud}); "
               "git files must not be synchronized."),
        _check("git_repo", repo, "Git repo reachable.", f"No Git repo at {cfg.git_dir} (pkm init)."),
    ]
    if repo:
        name, email = git.config_get("user.name"), git.config_get("user.email")
        signing = (git.config_get("commit.gpgsign") or "").lower() == "true"
        checks += [
            _check("git_identity", bool(name and email), f"Git identity: {name} <{email}>.",
                   "user.name/user.email missing."),
            _check("git_signing", not signing, "Commit signing off.",
                   "commit.gpgsign is on: commits fail if signing is not available in Claude Desktop "
                   "(signing key not reachable).", "warning"),
        ]
    return checks


def _conflicts(svc: Service) -> list[str]:
    """Conflict copies of all cloud services in the vault (by name and as copies with the same ID).

    Args:
        svc: Service.

    Returns:
        Sorted paths.
    """
    rels = list(svc.vault.iter_files())
    ids: dict[str, str | None] = {}
    for rel in rels:
        if rel.startswith("documents/") and rel.lower().endswith(".md"):
            try:
                ids[rel] = svc.vault.load(rel).id
            except PkmError:
                ids[rel] = None
    return sorted(conflict_copies(rels, ids))


def _path_checks(svc: Service) -> list[dict[str, Any]]:
    """Checks for vault, search index, write permissions, conflict copies and ``scratch/`` in ``.gitignore``.

    Args:
        svc: Service.

    Returns:
        Check results.
    """
    cfg = svc.cfg
    cache_problem = cfg.cache_dir_problem()
    cache_cloud = cloud_service(cfg.cache_dir)
    conflicts = _conflicts(svc)
    vault_cloud = cloud_service(cfg.root)
    online_only = online_only_files(cfg.root)
    checks = [
        _check("vault", cfg.root.is_dir(), f"Vault {cfg.root} exists.", f"Vault missing: {cfg.root}"),
        _check("cache_dir_outside", cache_problem is None, "PKM_CACHE_DIR is outside the vault.",
               cache_problem or ""),
        _check("cache_dir_cloud", cache_cloud is None, "PKM_CACHE_DIR is not in a cloud folder.",
               f"PKM_CACHE_DIR {cfg.cache_dir} seems to be in a cloud folder ({cache_cloud}); "
               "SQLite must not be synchronized."),
        _check("vault_cloud", True, f"Vault is in: {vault_cloud or 'no recognized cloud folder'}.", ""),
        _check("vault_online_only", not online_only, "All files of the vault are available locally.",
               f"Online-only files (placeholders): {', '.join(online_only)}. Always keep the vault folder local "
               "in the cloud service (OneDrive \"Always keep on this device\", Google Drive \"Mirror files\", iCloud "
               "\"Keep Downloaded\", Nextcloud virtual files off).", "warning"),
    ]
    for label, path in (("vault_writable", cfg.root), ("cache_writable", cfg.cache_dir)):
        ok = path.is_dir() and os.access(path, os.W_OK)
        checks.append(_check(label, ok, f"{path} writable.", f"{path} missing or not writable."))
    checks.append(_check("conflict_copies", not conflicts, "No conflict copies of the cloud storage.",
                         f"Conflict copies: {', '.join(conflicts)}"))
    import_problem = cfg.import_dir_problem()
    checks.append(_check("import_dir", import_problem is None, f"Import folder for images: {cfg.images.import_dir}.",
                         import_problem or ""))
    gitignore = cfg.root / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    checks.append(_check("scratch_ignored", scratch_ignored(text), "scratch/ is listed in .gitignore.",
                         "scratch/ missing in .gitignore (pkm init adds it)."))
    if cfg.import_in_vault:
        checks.append(_check("import_ignored", folder_ignored(text, IMPORT_FOLDER),
                             f"{IMPORT_FOLDER}/ is listed in .gitignore.",
                             f"{IMPORT_FOLDER}/ missing in .gitignore (pkm init adds it)."))
    return checks


def _obsidian_checks(root: Path) -> list[dict[str, Any]]:
    """Check Obsidian settings from ``.obsidian/app.json`` (13).

    Args:
        root: Vault root.

    Returns:
        Check results (deviations as warnings).
    """
    app = root / ".obsidian" / "app.json"
    data: dict[str, Any] | None = None
    if app.is_file():
        try:
            data = json.loads(app.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
    if not app.is_file():
        checks = [_check("obsidian_settings", True,
                         "No .obsidian/app.json found (Obsidian settings not checked).", "")]
    elif data is None:
        checks = [_check("obsidian_settings", False, "", ".obsidian/app.json cannot be read.", "warning")]
    else:
        checks = [
            _check(f"obsidian_{key}", data.get(key) == expected, f"{label}.",
                   f"Obsidian: {label} (currently {data.get(key)!r}).", "warning")
            for key, (expected, label) in OBSIDIAN_EXPECTED.items()
        ]
        ignored = any(str(f).strip("/") == ".pkm" for f in data.get("userIgnoreFilters") or [])
        checks.append(_check("obsidian_ignore_pkm", ignored, ".pkm/ is excluded in Obsidian.",
                             "Obsidian: add .pkm/ to \"Excluded files\".", "warning"))
    return checks


def _property_type_check(root: Path) -> dict[str, Any]:
    """Check Obsidian property types from ``.obsidian/types.json``.

    Args:
        root: Vault root.

    Returns:
        Check result (missing or differing types as a warning).
    """
    data = read_property_types(root)
    if data is None:
        check = _check("obsidian_property_types", False, "", f"{TYPES_FILE} cannot be read.", "warning")
    else:
        types = data.get("types") or {}
        missing = [k for k in PROPERTY_TYPES if k not in types]
        conflicts = property_type_conflicts(types)
        problems = [f"{k} missing" for k in missing] + [
            f"{k}={v} (expected {PROPERTY_TYPES[k]})" for k, v in conflicts.items()]
        check = _check("obsidian_property_types", not problems, "Obsidian property types match the schema.",
                       "Obsidian property types: " + ", ".join(problems)
                       + ". `pkm init` adds missing ones (restart Obsidian afterwards).", "warning")
    return check


def doctor(svc: Service, short: bool = False) -> dict[str, Any]:
    """``pkm doctor``: check the environment.

    Args:
        svc: Service.
        short: Output errors only.

    Returns:
        ``status`` (``error`` if there are errors), the installed ``version`` of pkm-tools, number of
        errors and warnings, and the checks.
    """
    checks = _path_checks(svc) + _git_checks(svc) + _obsidian_checks(svc.cfg.root)
    checks.append(_property_type_check(svc.cfg.root))
    errors = sum(1 for c in checks if c["severity"] == "error")
    warnings = sum(1 for c in checks if c["severity"] == "warning")
    shown = [c for c in checks if c["severity"] == "error"] if short else checks
    return {"status": "error" if errors else "ok", "version": __version__, "errors": errors, "warnings": warnings,
            "checks": shown}

# Main ************************************************************************
