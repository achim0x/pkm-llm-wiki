"""Textstruktur von Wiki-Seiten: Fußnoten-Muster, Absätze, Tabellen und strukturelle Zeilen.

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
    """Zeilen ohne eigene Sachaussage: Zwischenüberschrift, reine Hervorhebung, reine Link-Zeile.

    Args:
        line: Zeile im Body.

    Returns:
        ``True`` für ``### …``, ``**Text**`` (auch als Listeneintrag) und Zeilen, die nur aus Links
        bestehen, ggf. mit kurzer Beschriftung wie ``Details:``.
    """
    rest = LIST_ITEM_RE.sub("", line, count=1)
    links_only = False
    if ANY_LINK_RE.search(rest) and not REF_RE.search(rest):
        remainder = ANY_LINK_RE.sub("", rest).strip(" \t,;·–-")
        links_only = not remainder or bool(LINK_LABEL_RE.match(remainder))
    return bool(SUBHEADING_RE.match(line) or EMPHASIS_ONLY_RE.match(line)) or links_only


def section_blocks(lines: list[str], rows: range, def_lines: set[int]) -> list[list[tuple[int, str]] | None]:
    """Zeilen eines Abschnitts in Absätze zerlegen.

    Args:
        lines: Zeilen des Bodys.
        rows: Zeilenindizes des Abschnitts (ohne Überschrift).
        def_lines: Zeilen mit Fußnotendefinitionen.

    Returns:
        Absätze als Listen von (Index, Text); ``None`` markiert eine strukturelle Zeile, die
        Absätze trennt und eine Tabelle nicht mit einer folgenden Beleg-Zeile verbindet.
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
    """Prüfen, ob ein Absatz eine Markdown-Tabelle ist.

    Args:
        block: Absatz oder ``None``.

    Returns:
        ``True``, wenn alle Zeilen mit ``|`` beginnen.
    """
    return bool(block) and all(t.lstrip().startswith("|") for _, t in block or [])


def _is_ref_only(block: list[tuple[int, str]] | None) -> bool:
    """Prüfen, ob ein Absatz nur aus Fußnotenmarken besteht (ggf. mit „Quelle:“).

    Args:
        block: Absatz oder ``None``.

    Returns:
        ``True`` bei Zeilen wie ``[^b1][^b2]`` oder ``Quelle: [^b1]``.
    """
    text = " ".join(t for _, t in block or [])
    rest = REF_RE.sub("", text).strip(" \t.,;:")
    return bool(block) and bool(REF_RE.search(text)) and (not rest or bool(LINK_LABEL_RE.match(rest + ":")))


def merge_table_refs(blocks: list[list[tuple[int, str]] | None]) -> list[list[tuple[int, str]] | None]:
    """Tabelle mit einer direkt folgenden Beleg-Zeile zu einer Aussage verbinden.

    Args:
        blocks: Absätze aus ``section_blocks``.

    Returns:
        Absätze; eine Tabelle und ihre Beleg-Zeile bilden einen Absatz.
    """
    out: list[list[tuple[int, str]] | None] = []
    for block in blocks:
        if out and _is_table(out[-1]) and _is_ref_only(block):
            out[-1] = [*(out[-1] or []), *(block or [])]
        else:
            out.append(block)
    return out

# Main ************************************************************************
