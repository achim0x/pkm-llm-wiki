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

from .images import to_placeholders

# Variables *******************************************************************

MAX_LINE_CHARS = 2000  # longer diff lines are cut (safeguard for any remaining long content)

# Classes *********************************************************************

# Functions *******************************************************************


def unified_diff(old: str, new: str, a: str, b: str, max_lines: int | None = None) -> str:
    """Build a unified diff between two texts, without Base64 or SVG content.

    Embedded images appear as placeholders like in ``read`` (``pkm-image:<name> "png, 752.8 KB,
    sha:…"``), so a tool answer never carries data URIs. Lines longer than ``MAX_LINE_CHARS`` are cut.

    Args:
        old: Old text.
        new: New text.
        a: Label of the old version (e.g. ``v1``).
        b: Label of the new version (e.g. ``v2``).
        max_lines: Maximum number of lines; the rest is cut with a note.

    Returns:
        The diff as text (empty if both texts are equal).
    """
    old_view, new_view = to_placeholders(old), to_placeholders(new)
    lines = [_cut(line) for line in difflib.unified_diff(old_view.splitlines(keepends=True),
                                                          new_view.splitlines(keepends=True), a, b)]
    if max_lines is not None and len(lines) > max_lines:
        rest = len(lines) - max_lines
        lines = lines[:max_lines] + [f"… ({rest} more lines omitted)\n"]
    return "".join(lines)

def _cut(line: str) -> str:
    """Cut an overlong diff line.

    Args:
        line: Line including the line break.

    Returns:
        The line, or its start with a note on the omitted characters.
    """
    body = line.rstrip("\n")
    if len(body) > MAX_LINE_CHARS:
        line = f"{body[:MAX_LINE_CHARS]}… ({len(body) - MAX_LINE_CHARS} more characters)\n"
    return line

# Main ************************************************************************
