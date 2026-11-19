"""Backups of documents before they are overwritten without version control (specification 5.4, 7.5).

With Git every change is a version and can be undone. Without Git (``PKM_VERSIONING`` off, or in
``scratch/``) a tool that overwrites a file first copies the previous content to
``<PKM_CACHE_DIR>/backups/documents/<date>/<path>.<time>.bak``. Backups older than ``BACKUP_DAYS`` days
are removed.

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

import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

# Variables *******************************************************************

BACKUP_DAYS = 30
BACKUP_AREAS = ("documents/", "scratch/")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Classes *********************************************************************

# Functions *******************************************************************


def backup_folder(cfg: Config) -> Path:
    """Folder of the document backups.

    Args:
        cfg: Configuration.

    Returns:
        ``<PKM_CACHE_DIR>/backups/documents``.
    """
    return cfg.cache_dir / "backups" / "documents"


def needs_backup(cfg: Config, rel: str) -> bool:
    """Whether overwriting a file needs a backup (no Git version for it).

    Args:
        cfg: Configuration.
        rel: Path in the vault.

    Returns:
        ``True`` for files in ``scratch/`` and, without version control, in ``documents/``.
    """
    return rel.startswith("scratch/") or (not cfg.versioning and rel.startswith(BACKUP_AREAS))


def backup_before_write(cfg: Config, rel: str, now: datetime) -> Path | None:
    """Copy the current content of a file before it is overwritten (only where there is no Git version).

    Args:
        cfg: Configuration.
        rel: Path in the vault.
        now: Current time (local time of the PKM).

    Returns:
        Path of the backup, or ``None`` if none was needed (file new, or versioned with Git).
    """
    source = cfg.root / rel
    backup = None
    if needs_backup(cfg, rel) and source.is_file():
        day = backup_folder(cfg) / now.strftime("%Y-%m-%d")
        backup = day / f"{rel}.{now.strftime('%H%M%S')}.bak"
        n = 1
        while backup.exists():
            n += 1
            backup = day / f"{rel}.{now.strftime('%H%M%S')}-{n}.bak"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup)
        prune(cfg, now)
    return backup


def prune(cfg: Config, now: datetime, days: int = BACKUP_DAYS) -> list[str]:
    """Remove backup folders older than ``days`` days.

    Args:
        cfg: Configuration.
        now: Current time.
        days: Days to keep.

    Returns:
        Names of the removed day folders.
    """
    removed = []
    limit = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    folder = backup_folder(cfg)
    for day in sorted(folder.iterdir()) if folder.is_dir() else []:
        if day.is_dir() and DAY_RE.match(day.name) and day.name < limit:
            shutil.rmtree(day, ignore_errors=True)
            removed.append(day.name)
    return removed

# Main ************************************************************************
