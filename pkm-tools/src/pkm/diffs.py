"""Unified diffs for tool results and history.

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
    """Build a unified diff between two texts.

    Args:
        old: Old text.
        new: New text.
        a: Label of the old version (e.g. ``v1``).
        b: Label of the new version (e.g. ``v2``).
        max_lines: Maximum number of lines; the rest is cut with a note.

    Returns:
        The diff as text (empty if both texts are equal).
    """
    lines = list(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), a, b))
    if max_lines is not None and len(lines) > max_lines:
        rest = len(lines) - max_lines
        lines = lines[:max_lines] + [f"… ({rest} more lines omitted)\n"]
    return "".join(lines)

# Main ************************************************************************
