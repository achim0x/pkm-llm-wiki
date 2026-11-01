"""Unified Diffs für Rückgaben und Verlauf.

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

import difflib

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


def unified_diff(old: str, new: str, a: str, b: str, max_lines: int | None = None) -> str:
    """Unified Diff zwischen zwei Texten bilden.

    Args:
        old: Alter Text.
        new: Neuer Text.
        a: Bezeichnung der alten Fassung (z. B. ``v1``).
        b: Bezeichnung der neuen Fassung (z. B. ``v2``).
        max_lines: Höchstzahl an Zeilen; der Rest wird mit einem Hinweis gekürzt.

    Returns:
        Der Diff als Text (leer, wenn beide Texte gleich sind).
    """
    lines = list(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), a, b))
    if max_lines is not None and len(lines) > max_lines:
        rest = len(lines) - max_lines
        lines = lines[:max_lines] + [f"… ({rest} weitere Zeilen gekürzt)\n"]
    return "".join(lines)

# Main ************************************************************************
