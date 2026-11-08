"""Lint for source fidelity (specification 8, 9.5): statements that combine several sources.

A sentence or list item whose footnotes cite two or more different documents may relate statements
that no source relates itself. ``cross_source_statement`` reports them (``warning`` in the section
"Contradictions / open questions", otherwise ``info``); ``synthesis_unmarked`` reports synthesis pages
without the marker for an own interpretation. Only hints: the agent checks the wording.

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
from typing import Any

from .citations import Citation, parse_page
from .config import WIKI_SECTIONS
from .pagetext import DEF_RE, LIST_ITEM_RE, REF_RE, section_blocks
from .parse import body_lines
from .vault import Doc

# Variables *******************************************************************

CHECK = "cross_source_statement"
SYNTHESIS_CHECK = "synthesis_unmarked"
OK_MARK = "<!-- lint: cross-source ok -->"
CHECKED_DIRS = ("wiki/topics/", "wiki/entities/", "wiki/summaries/", "wiki/syntheses/")
CONTRADICTION_SECTIONS = {sections[1].casefold() for _, sections in WIKI_SECTIONS.values()}
SENTENCE_END_RE = re.compile(r"[.;!?](?:\[\^[^\]\s]+\])*(?=\s|$)")
OWN_MARKERS = ("own interpretation", "eigene einordnung")
PREVIEW = 120

# Classes *********************************************************************

# Functions *******************************************************************


def _units(block: list[tuple[int, str]]) -> list[str]:
    """Paragraph as units: every list item on its own, otherwise the whole paragraph (raw text).

    Args:
        block: Lines of the paragraph as (index, text).

    Returns:
        Raw texts with footnote marks.
    """
    if not any(LIST_ITEM_RE.match(t) for _, t in block):
        return [" ".join(t.strip() for _, t in block)]
    items: list[str] = []
    for _, text in block:
        if LIST_ITEM_RE.match(text) or not items:
            items.append(text.strip())
        else:
            items[-1] += " " + text.strip()
    return items


def sentences(unit: str) -> list[str]:
    """Split a paragraph or list item into sentences, each with the footnotes directly after it.

    Args:
        unit: Raw text.

    Returns:
        Sentences up to ``.``, ``;``, ``!`` or ``?`` (with the following footnote marks).
    """
    out, pos = [], 0
    for m in SENTENCE_END_RE.finditer(unit):
        out.append(unit[pos:m.end()].strip())
        pos = m.end()
    rest = unit[pos:].strip()
    return [s for s in [*out, rest] if s]


def _source(cit: Citation | None) -> str | None:
    """Source of a citation: the document ID, otherwise the cited file.

    Args:
        cit: Citation or ``None``.

    Returns:
        ``d-…`` or a path, ``None`` if unknown.
    """
    return None if cit is None else (cit.doc_id or cit.target_rel or cit.path)


def _ignored(page: Doc) -> bool:
    """Whether the page switches the check off (``lint_ignore: [cross_source_statement]``).

    Args:
        page: Wiki page.

    Returns:
        ``True`` if switched off.
    """
    ignore = page.meta.get("lint_ignore")
    return isinstance(ignore, list) and CHECK in {str(v) for v in ignore}


def _page_hints(add: Any, page: Doc) -> None:
    """``cross_source_statement`` for one page.

    Args:
        add: ``Report.add``.
        page: Wiki page.
    """
    assert page.parsed is not None
    definitions = parse_page(page).definitions
    lines = body_lines(page.parsed.body)
    def_lines = {i for i, ln in enumerate(lines) if DEF_RE.match(ln)}
    for sec in page.parsed.sections:
        contradictions = (sec.base or "").casefold() in CONTRADICTION_SECTIONS
        start = sec.start + (1 if sec.heading is not None else 0)
        for block in section_blocks(lines, range(start, sec.end), def_lines):
            if not block or block[0][1].lstrip().startswith("|"):
                continue
            for unit in _units(block):
                if OK_MARK in unit:
                    continue
                for sentence in sentences(unit):
                    labels = list(dict.fromkeys(r.group(1) for r in REF_RE.finditer(sentence)))
                    docs = sorted({s for s in (_source(definitions.get(lb)) for lb in labels) if s})
                    if len(docs) < 2:
                        continue
                    text = LIST_ITEM_RE.sub("", REF_RE.sub("", sentence)).strip()[:PREVIEW]
                    if contradictions:
                        add(CHECK, "warning", page.rel, f"Statement in contradictions section combines sources "
                            f"{' and '.join(docs)}; check that one source makes this connection itself.",
                            section=sec.base, footnotes=labels, documents=docs, text=text)
                    else:
                        add(CHECK, "info", page.rel, f"Statement combines sources {' and '.join(docs)}; check "
                            "attribution.", section=sec.base, footnotes=labels, documents=docs, text=text)


def check_sources(add: Any, pages: list[Doc]) -> None:
    """Source fidelity checks for wiki pages below ``wiki/topics|entities|summaries|syntheses/``.

    Args:
        add: ``Report.add``.
        pages: Wiki pages.
    """
    for page in pages:
        if page.error or page.parsed is None or not page.rel.startswith(CHECKED_DIRS):
            continue
        if not _ignored(page):
            _page_hints(add, page)
        if page.rel.startswith("wiki/syntheses/"):
            body = (page.body or "").casefold()
            if not page.meta.get("confidence") or not any(m in body for m in OWN_MARKERS):
                add(SYNTHESIS_CHECK, "info", page.rel, "Synthesis page without marker for own interpretation "
                    "(confidence and the line \"Own interpretation, not stated in the sources.\").")

# Main ************************************************************************
