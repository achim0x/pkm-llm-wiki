"""Verarbeitungsstand ``.pkm/state.json`` und Vergleich nach Spezifikation 4.6 und 4.8.

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
# along with this program.  If not, see <https://gnu.org>.

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
    """``state.json`` lesen.

    Args:
        cfg: Konfiguration.

    Returns:
        Den Stand mit mindestens dem Schlüssel ``documents``; leer, wenn die Datei fehlt.

    Raises:
        PkmError: ``invalid_state``, wenn die Datei nicht lesbar ist.
    """
    data: dict[str, Any] = {"version": FORMAT, "documents": {}}
    p = cfg.state_path
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PkmError("invalid_state", f"state.json nicht lesbar: {exc}") from exc
        data.setdefault("documents", {})
    return data


def state_key(doc: Doc) -> str | None:
    """Schlüssel eines Dokuments in ``state.json``.

    Args:
        doc: Dokument.

    Returns:
        Die ID bei Markdown, ``sha:<hash>`` bei Anhängen, ``None`` ohne ID.
    """
    return f"sha:{doc.bin_hash}" if doc.kind == "bin" else doc.id


def section_changes(old: dict[str, str], new: dict[str, str]) -> list[dict[str, str]]:
    """Abschnittsvergleich nach 4.8: ``added``, ``removed``, ``changed``, ``renamed``.

    Ein entfallener und ein neuer Inhalt mit gleichem Hash gelten als ``renamed``. Das erkennt
    auch Verschiebungen der Duplikat-Nummerierung (``Notizen#2`` → ``Notizen``).

    Args:
        old: Abschnitts-Hashes der verarbeiteten Version.
        new: Abschnitts-Hashes der aktuellen Version.

    Returns:
        Änderungen je Abschnitt mit ``key``, ``change`` und bei ``renamed`` ``from``.
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
        # Bereits als changed gemeldete Schlüssel nicht doppelt als removed melden.
        if o not in consumed and (o not in new or o in renamed):
            changes.append({"key": o, "change": "removed"})
    return changes


def classify(doc: Doc, entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """Verarbeitungsstand eines Dokuments bestimmen.

    Args:
        doc: Aktuelles Dokument.
        entry: Eintrag aus ``state.json`` oder ``None``.

    Returns:
        ``None``, wenn der aktuelle Stand verarbeitet ist; sonst ein Wörterbuch mit
        ``category`` (``new``, ``changed``, ``meta_changed`` oder ``invalid``) und Details.
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
