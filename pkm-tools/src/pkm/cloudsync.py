"""Cloud storage: detect conflict copies, cloud folders and placeholders for online-only files.

The vault can live in any folder a cloud service synchronizes (Nextcloud, ownCloud,
OneDrive, Google Drive, Dropbox, iCloud Drive, Box, pCloud, Syncthing …). These helpers are service-neutral:
they detect all known patterns automatically.

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

import os
import re
import stat
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

# Variables *******************************************************************

# Conflict copies by name (case-insensitive).
CONFLICT_NAME_RES = (
    re.compile(r"conflicted copy", re.IGNORECASE),  # Nextcloud, ownCloud, Dropbox, Box, Google Drive (older)
    re.compile(r"\((?:[^)]*\s)?conflict(?:ed)?\b[^)]*\)", re.IGNORECASE),  # "(conflict …)", "(… conflicted …)"
    re.compile(r"\[conflict(?:ed)?\]", re.IGNORECASE),  # Google Drive, pCloud
    re.compile(r"\.sync-conflict-\d{8}-\d{6}", re.IGNORECASE),  # Syncthing
    re.compile(r"case conflict", re.IGNORECASE),  # Dropbox (upper/lower case)
    re.compile(r"konflikt[- ]?kopie|in konflikt stehende kopie", re.IGNORECASE),  # German clients
    re.compile(r"\(konflikt[^)]*\)", re.IGNORECASE),
)
# Copies that count as conflict copies only together with the original and the same document ID.
NUMBERED_RE = re.compile(r"^(?P<base>.+?)(?: \((?P<n1>\d+)\)| (?P<n2>\d+))$")  # iCloud, Finder, Google Drive
COPY_OF_RE = re.compile(r"^(?:copy of|kopie von) (?P<base>.+)$", re.IGNORECASE)  # Google Drive
HOST_SUFFIX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*$")  # OneDrive: "-COMPUTERNAME"
CLOUD_DIR_RES = (
    ("Nextcloud", re.compile(r"nextcloud", re.IGNORECASE)),
    ("ownCloud", re.compile(r"owncloud", re.IGNORECASE)),
    ("OneDrive", re.compile(r"onedrive", re.IGNORECASE)),
    ("Google Drive", re.compile(r"google ?drive|^my drive$|^meine ablage$", re.IGNORECASE)),
    ("Dropbox", re.compile(r"dropbox", re.IGNORECASE)),
    ("iCloud Drive", re.compile(r"icloud|^mobile documents$", re.IGNORECASE)),
    ("Box", re.compile(r"^box$|^box sync$", re.IGNORECASE)),
    ("pCloud", re.compile(r"pcloud", re.IGNORECASE)),
    ("cloud storage (macOS)", re.compile(r"^cloudstorage$", re.IGNORECASE)),
)
CLOUD_MARKERS = (
    ("Nextcloud/ownCloud", ".owncloudsync.log"),
    ("Dropbox", ".dropbox"),
    ("Syncthing", ".stfolder"),
)
DATALESS = 0x40000000  # macOS SF_DATALESS (placeholders of iCloud, OneDrive, Google Drive …)
WIN_ONLINE_ONLY = 0x00001000 | 0x00040000 | 0x00400000  # OFFLINE, RECALL_ON_OPEN, RECALL_ON_DATA_ACCESS

# Classes *********************************************************************

# Functions *******************************************************************


def is_conflict_copy(name: str) -> bool:
    """Detect a conflict copy of a cloud service by its file name.

    Args:
        name: File name.

    Returns:
        ``True`` for known patterns (e.g. "conflicted copy", "[Conflict]", ".sync-conflict-…",
        "Konflikt-Kopie").
    """
    return any(rx.search(name) for rx in CONFLICT_NAME_RES)


def _base_candidates(stem: str) -> list[str]:
    """Possible original names for a copy without a unique conflict pattern.

    Args:
        stem: File name without extension.

    Returns:
        Candidates: without " (2)" or " 2", without "Copy of "/"Kopie von ", without an appended computer name.
    """
    out = []
    m = NUMBERED_RE.match(stem)
    if m:
        out.append(m.group("base"))
    m = COPY_OF_RE.match(stem)
    if m:
        out.append(m.group("base"))
    parts = stem.split("-")
    for i in range(1, len(parts)):
        host = "-".join(parts[i:])
        if HOST_SUFFIX_RE.match(host) and any(ch.isalpha() for ch in host):
            out.append("-".join(parts[:i]))
    return out


def sibling_conflicts(ids: dict[str, str | None]) -> set[str]:
    """Detect conflict copies without a unique name pattern (OneDrive, iCloud Drive, Google Drive).

    A file counts as a copy if an original with a derived name lies in the same folder
    (``note-MacBook.md``, ``note 2.md``, ``note (1).md``, ``Copy of note.md`` → ``note.md``) and
    both carry **the same document ID**. Without the same ID it is a document of its own.

    Args:
        ids: Relative path → document ID (``None`` without ID).

    Returns:
        Paths of the copies.
    """
    found: set[str] = set()
    for rel, doc_id in ids.items():
        if not doc_id:
            continue
        pure = PurePosixPath(rel)
        for base in _base_candidates(pure.stem):
            original = str(pure.with_name(base + pure.suffix))
            if original != rel and ids.get(original) == doc_id:
                found.add(rel)
    return found


def conflict_copies(rels: Iterable[str], ids: dict[str, str | None]) -> set[str]:
    """All conflict copies: detected by name, and copies with the same ID next to the original.

    Args:
        rels: Relative paths.
        ids: Path → document ID of the Markdown files.

    Returns:
        Paths of the conflict copies.
    """
    return {r for r in rels if is_conflict_copy(PurePosixPath(r).name)} | sibling_conflicts(ids)


def cloud_service(path: Path) -> str | None:
    """Detect whether a path lies in a synchronized cloud folder.

    Args:
        path: Path to check.

    Returns:
        Name of the service (e.g. ``OneDrive``) or ``None``.
    """
    found = None
    for p in [path, *path.parents]:
        found = next((name for name, rx in CLOUD_DIR_RES if rx.search(p.name)), None)
        if found is None:
            try:
                found = next((name for name, marker in CLOUD_MARKERS if (p / marker).exists()), None)
                found = found or ("Nextcloud/ownCloud" if any(p.glob(".sync_*.db")) else None)
            except OSError:
                found = None
        if found:
            break
    return found


def is_online_only(path: Path) -> bool:
    """Check whether a file exists only as a placeholder ("online only", "streaming", "files on demand").

    Args:
        path: File.

    Returns:
        ``True`` if the operating system marks the file as not available locally.
    """
    try:
        st = os.lstat(path)
    except OSError:
        st = None
    online = False
    if st is not None and stat.S_ISREG(st.st_mode):
        flags = getattr(st, "st_flags", 0)
        attrs = getattr(st, "st_file_attributes", 0)
        online = bool(flags & DATALESS) if sys.platform == "darwin" else bool(attrs & WIN_ONLINE_ONLY)
    return online


def online_only_files(root: Path, limit: int = 20) -> list[str]:
    """Files in the vault that exist only online (hidden folders excluded).

    Args:
        root: Vault root.
        limit: Maximum number of reported files.

    Returns:
        Relative paths (at most ``limit``).
    """
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        out += [str(PurePosixPath(Path(dirpath).relative_to(root).as_posix()) / f) for f in filenames
                if not f.startswith(".") and is_online_only(Path(dirpath) / f)]
        if len(out) >= limit:
            break
    return out[:limit]

# Main ************************************************************************
