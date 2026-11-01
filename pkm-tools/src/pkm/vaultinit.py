"""``pkm init``: Struktur anlegen und Git-Verzeichnis außerhalb des Vaults initialisieren.

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
from typing import Any

from .config import Config
from .errors import PkmError
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
    ".pkm",
]

# Classes *********************************************************************

# Functions *******************************************************************


def _template(name: str) -> str:
    """Vorlage aus dem Paket lesen.

    Args:
        name: Dateiname unter ``pkm/templates``.

    Returns:
        Inhalt der Vorlage.
    """
    return resources.files("pkm").joinpath("templates", name).read_text(encoding="utf-8")


def initial_files() -> dict[str, str]:
    """Dateien, die ``pkm init`` anlegt.

    Returns:
        Relativer Pfad → Inhalt.
    """
    return {
        "CLAUDE.md": _template("CLAUDE.md"),
        ".gitignore": _template("gitignore"),
        "wiki/index.md": "# Wiki-Index\n\n_Noch keine Seiten._\n",
        "wiki/log.md": "# Pflege-Log\n",
        "wiki/_status.md": "# Status\n\n## Noch nicht verarbeitet (0)\n",
        ".pkm/state.json": json.dumps({"version": STATE_FORMAT, "documents": {}}, indent=2) + "\n",
    }


def _create_structure(cfg: Config) -> tuple[list[str], list[str]]:
    """Fehlende Ordner und Dateien anlegen; vorhandene bleiben unverändert.

    Args:
        cfg: Konfiguration.

    Returns:
        Tupel aus (angelegte Ordner, angelegte Dateien).
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


def init_vault(cfg: Config) -> dict[str, Any]:
    """``pkm init`` (idempotent).

    Args:
        cfg: Konfiguration.

    Returns:
        Was angelegt wurde, ob das Repo neu ist, der Initial-Commit und Warnungen.

    Raises:
        PkmError: ``config_error``, wenn Git-Verzeichnis oder Suchindex im Vault liegen würden
            oder im Vault schon ein ``.git`` liegt.
    """
    for problem in (cfg.git_dir_problem(), cfg.cache_dir_problem()):
        if problem:
            raise PkmError("config_error", problem)
    if (cfg.root / ".git").exists():
        raise PkmError("config_error", "Im Vault liegt ein `.git`. Git muss außerhalb liegen (5.5).")
    created_dirs, created_files = _create_structure(cfg)
    git = Git(cfg.git_dir, cfg.root)
    repo_created = git.init()
    commit = None
    warnings: list[str] = []
    if not git.has_head():
        if git.config_get("user.name") and git.config_get("user.email"):
            paths = [rel for rel in initial_files() if (cfg.root / rel).exists()]
            commit = git.commit_paths(paths, "pkm: init\n")
        else:
            warnings.append("Git-Identität fehlt (user.name/user.email); Initial-Commit übersprungen.")
    return {
        "status": "ok",
        "root": str(cfg.root),
        "git_dir": str(cfg.git_dir),
        "created_dirs": created_dirs,
        "created_files": created_files,
        "repo_created": repo_created,
        "commit": commit,
        "warnings": warnings,
    }

# Main ************************************************************************
