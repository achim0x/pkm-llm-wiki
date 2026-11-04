"""Helpers for ``append_to_document``: insert text at the end of a section or of the preamble.

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

from .errors import PkmError
from .parse import PREAMBLE, Parsed, body_lines, normalize_key_input

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


def count_overlapping(haystack: str, needle: str) -> int:
    """Count occurrences, including overlapping ones.

    Args:
        haystack: Text.
        needle: Text to find (not empty).

    Returns:
        Number of occurrences.
    """
    n, start = 0, haystack.find(needle)
    while start >= 0:
        n += 1
        start = haystack.find(needle, start + 1)
    return n


def _insert_block(lines: list[str], after: int, block: list[str]) -> list[str]:
    """Insert a block after a line, with a blank line before and, if needed, after it.

    Args:
        lines: Body lines.
        after: Index of the line after which to insert.
        block: Lines to insert.

    Returns:
        New list of lines.
    """
    head, tail = lines[: after + 1], lines[after + 1 :]
    out = head + ([""] if head and head[-1].strip() else []) + block
    if tail and tail[0].strip():
        out.append("")
    return out + tail


def _last_nonblank(lines: list[str], start: int, end: int) -> int:
    """Last non-empty line within a range.

    Args:
        lines: Lines.
        start: First index.
        end: Index after the range.

    Returns:
        Index of the last non-empty line, otherwise ``start``.
    """
    return next((i for i in range(end - 1, start - 1, -1) if lines[i].strip()), start)


def _append_to_preamble(lines: list[str], parsed: Parsed, block: list[str]) -> list[str]:
    """Insert text at the end of the preamble (before the first heading).

    Args:
        lines: Body lines.
        parsed: Parsed document.
        block: Lines to insert.

    Returns:
        New list of lines.
    """
    sec = parsed.section(PREAMBLE)
    if sec is not None:
        out = _insert_block(lines, _last_nonblank(lines, sec.start, sec.end), block)
    else:
        first = parsed.sections[0].start if parsed.sections else len(lines)
        lead = next((i for i in range(first) if lines[i].strip()), first)
        out = lines[:lead] + block + ([""] if first < len(lines) else []) + lines[lead:]
    return out


def append_lines(parsed: Parsed, block: list[str], section: str | None) -> list[str]:
    """Compute the body lines after ``append_to_document``.

    Args:
        parsed: Parsed document.
        block: Lines to insert.
        section: Section key or ``None`` (end of file).

    Returns:
        New body lines.

    Raises:
        PkmError: ``ambiguous`` if the key without suffix points to duplicate headings.
    """
    lines = body_lines(parsed.body)
    key = normalize_key_input(section) if section is not None else None
    sec = parsed.section(key) if key is not None else None
    if key is None:
        out = _insert_block(lines, len(lines) - 1, block) if lines else block
    elif key == PREAMBLE:
        out = _append_to_preamble(lines, parsed, block)
    elif sec is None:
        new_section = [f"## {key}", "", *block]
        out = _insert_block(lines, len(lines) - 1, new_section) if lines else new_section
    else:
        dups = [s.key for s in parsed.sections if s.level and s.base == key and s.key != key]
        if "#" not in key and dups:
            raise PkmError(
                "ambiguous", f"Section \"{key}\" occurs more than once. Please give the key with suffix.",
                candidates=[key, *dups],
            )
        out = _insert_block(lines, _last_nonblank(lines, sec.start, sec.end), block)
    return out

# Main ************************************************************************
