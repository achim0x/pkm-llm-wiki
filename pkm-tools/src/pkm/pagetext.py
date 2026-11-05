"""Text structure of wiki pages: footnote patterns, paragraphs, tables and structural lines.

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

# Variables *******************************************************************

DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:[ \t]*(.*)$")
REF_RE = re.compile(r"\[\^([^\]\s]+)\](?!:)")
LIST_ITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
SUBHEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
EMPHASIS_ONLY_RE = re.compile(r"^\s*(?:[-*+]\s+)?(\*\*|__|\*|_)[^*_]+\1\s*:?\s*$")
ANY_LINK_RE = re.compile(r"!?\[\[[^\]]*\]\]|\[[^\]]*\]\([^)]*\)")
LINK_LABEL_RE = re.compile(r"^[\w ./-]{1,30}:$")

# Classes *********************************************************************

# Functions *******************************************************************


def is_structural_line(line: str) -> bool:
    """Lines without a statement of their own: subheading, emphasis only, links only.

    Args:
        line: Line of the body.

    Returns:
        ``True`` for ``### …``, ``**Text**`` (also as a list item) and lines that consist only of links,
        optionally with a short label such as ``Details:``.
    """
    rest = LIST_ITEM_RE.sub("", line, count=1)
    links_only = False
    if ANY_LINK_RE.search(rest) and not REF_RE.search(rest):
        remainder = ANY_LINK_RE.sub("", rest).strip(" \t,;·–-")
        links_only = not remainder or bool(LINK_LABEL_RE.match(remainder))
    return bool(SUBHEADING_RE.match(line) or EMPHASIS_ONLY_RE.match(line)) or links_only


def section_blocks(lines: list[str], rows: range, def_lines: set[int]) -> list[list[tuple[int, str]] | None]:
    """Split the lines of a section into paragraphs.

    Args:
        lines: Lines of the body.
        rows: Line indexes of the section (without the heading).
        def_lines: Lines with footnote definitions.

    Returns:
        Paragraphs as lists of (index, text); ``None`` marks a structural line that separates
        paragraphs and does not join a table with a following citation line.
    """
    blocks: list[list[tuple[int, str]] | None] = []
    block: list[tuple[int, str]] = []
    for i in rows:
        structural = i not in def_lines and lines[i].strip() and is_structural_line(lines[i])
        if i in def_lines or not lines[i].strip() or structural:
            blocks += [block] if block else []
            blocks += [None] if structural else []
            block = []
        else:
            block.append((i, lines[i]))
    return blocks + ([block] if block else [])


def _is_table(block: list[tuple[int, str]] | None) -> bool:
    """Check whether a paragraph is a Markdown table.

    Args:
        block: Paragraph or ``None``.

    Returns:
        ``True`` if all lines start with ``|``.
    """
    return bool(block) and all(t.lstrip().startswith("|") for _, t in block or [])


def _is_ref_only(block: list[tuple[int, str]] | None) -> bool:
    """Check whether a paragraph consists only of footnote markers (optionally with "Source:").

    Args:
        block: Paragraph or ``None``.

    Returns:
        ``True`` for lines like ``[^b1][^b2]`` or ``Source: [^b1]``.
    """
    text = " ".join(t for _, t in block or [])
    rest = REF_RE.sub("", text).strip(" \t.,;:")
    return bool(block) and bool(REF_RE.search(text)) and (not rest or bool(LINK_LABEL_RE.match(rest + ":")))


def merge_table_refs(blocks: list[list[tuple[int, str]] | None]) -> list[list[tuple[int, str]] | None]:
    """Join a table with a directly following citation line into one statement.

    Args:
        blocks: Paragraphs from ``section_blocks``.

    Returns:
        Paragraphs; a table and its citation line form one paragraph.
    """
    out: list[list[tuple[int, str]] | None] = []
    for block in blocks:
        if out and _is_table(out[-1]) and _is_ref_only(block):
            out[-1] = [*(out[-1] or []), *(block or [])]
        else:
            out.append(block)
    return out

# Main ************************************************************************
