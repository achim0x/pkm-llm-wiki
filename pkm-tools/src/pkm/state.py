"""Processing state ``.pkm/state.json`` and comparison according to specification 4.6 and 4.8.

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
from typing import Any

from .config import Config
from .errors import PkmError
from .vault import Doc

# Variables *******************************************************************

FORMAT = 1

# Classes *********************************************************************

# Functions *******************************************************************


def load_state(cfg: Config) -> dict[str, Any]:
    """Read ``state.json``.

    Args:
        cfg: Configuration.

    Returns:
        The state with at least the key ``documents``; empty if the file is missing.

    Raises:
        PkmError: ``invalid_state`` if the file cannot be read.
    """
    data: dict[str, Any] = {"version": FORMAT, "documents": {}}
    p = cfg.state_path
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PkmError("invalid_state", f"state.json cannot be read: {exc}") from exc
        data.setdefault("documents", {})
    return data


def state_key(doc: Doc) -> str | None:
    """Key of a document in ``state.json``.

    Args:
        doc: Document.

    Returns:
        The ID for Markdown, ``sha:<hash>`` for attachments, ``None`` without ID.
    """
    return f"sha:{doc.bin_hash}" if doc.kind == "bin" else doc.id


def section_changes(old: dict[str, str], new: dict[str, str]) -> list[dict[str, str]]:
    """Section comparison according to 4.8: ``added``, ``removed``, ``changed``, ``renamed``.

    A removed and an added content with the same hash count as ``renamed``. This also detects
    shifts of the duplicate numbering (``Notes#2`` → ``Notes``).

    Args:
        old: Section hashes of the processed version.
        new: Section hashes of the current version.

    Returns:
        Changes per section with ``key``, ``change`` and, for ``renamed``, ``from``.
    """
    same = {k for k in new if old.get(k) == new[k]}
    new_open = [k for k in new if k not in same]
    old_open = [k for k in old if k not in same]
    consumed: set[str] = set()
    renamed: dict[str, str] = {}
    for n in new_open:
        src = next((o for o in old_open if o != n and o not in consumed and old[o] == new[n]), None)
        if src is not None:
            consumed.add(src)
            renamed[n] = src
    changes: list[dict[str, str]] = []
    for n in new_open:
        if n in renamed:
            changes.append({"key": n, "change": "renamed", "from": renamed[n]})
        elif n in old and n not in consumed:
            changes.append({"key": n, "change": "changed"})
        else:
            changes.append({"key": n, "change": "added"})
    for o in old_open:
        # Do not report keys already reported as changed again as removed.
        if o not in consumed and (o not in new or o in renamed):
            changes.append({"key": o, "change": "removed"})
    return changes


def classify(doc: Doc, entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """Determine the processing state of a document.

    Args:
        doc: Current document.
        entry: Entry from ``state.json`` or ``None``.

    Returns:
        ``None`` if the current state is processed; otherwise a dictionary with
        ``category`` (``new``, ``changed``, ``meta_changed`` or ``invalid``) and details.
    """
    result: dict[str, Any] | None
    if doc.kind == "bin":
        result = None if entry else {"category": "new"}
    elif doc.hashes is None or doc.error:
        result = {"category": "invalid", "error": doc.error}
    elif not entry:
        result = {"category": "new", "version": doc.version}
    else:
        same_body = entry.get("body_hash") == doc.hashes.body_hash
        same_meta = entry.get("meta_hash") == doc.hashes.meta_hash
        base = {"processed_version": entry.get("processed_version"), "version": doc.version}
        if same_body and same_meta:
            result = None
        elif same_body:
            result = {"category": "meta_changed", **base}
        else:
            sections = section_changes(entry.get("sections") or {}, doc.hashes.sections)
            result = {"category": "changed", **base, "sections": sections}
    return result

# Main ************************************************************************
