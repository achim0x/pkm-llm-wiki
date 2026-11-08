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
from .ipaddrs import IP_FIELD, classification, find_ips
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
LABEL_ONLY_RE = re.compile(r"^(?:sources?|quellen?|belege?|citations?|references?)?\s*:?\s*$", re.IGNORECASE)
IP_UNCLASSIFIED = "ip_addresses_unclassified"
IP_COMPARISON = "ip_comparison"

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


def _sentence_hint(add: Any, page: Doc, sec: Any, sentence: str, definitions: dict[str, Citation]) -> None:
    """``cross_source_statement`` for one sentence (lines without a statement of their own are skipped).

    Args:
        add: ``Report.add``.
        page: Wiki page.
        sec: Section.
        sentence: Raw sentence with footnote marks.
        definitions: Footnote definitions of the page.
    """
    text = LIST_ITEM_RE.sub("", REF_RE.sub("", sentence)).strip()
    labels = list(dict.fromkeys(r.group(1) for r in REF_RE.finditer(sentence)))
    docs = sorted({s for s in (_source(definitions.get(lb)) for lb in labels) if s})
    if len(docs) >= 2 and not LABEL_ONLY_RE.match(text):
        detail = {"section": sec.base, "footnotes": labels, "documents": docs, "text": text[:PREVIEW]}
        if (sec.base or "").casefold() in CONTRADICTION_SECTIONS:
            add(CHECK, "warning", page.rel, f"Statement in contradictions section combines sources "
                f"{' and '.join(docs)}; check that one source makes this connection itself.", **detail)
        else:
            add(CHECK, "info", page.rel, f"Statement combines sources {' and '.join(docs)}; check attribution.",
                **detail)


def _ip_hint(add: Any, page: Doc, unit: str, definitions: dict[str, Citation], classes: dict[str, str]) -> None:
    """``ip_comparison``: an entry in the contradictions section with an IP address and citations of two or more
    documents, at least one of them not classified as ``concrete``.

    Args:
        add: ``Report.add``.
        page: Wiki page.
        unit: Raw list item or paragraph.
        definitions: Footnote definitions of the page.
        classes: Document ID → classification of its IP addresses.
    """
    ips = find_ips(REF_RE.sub("", unit))
    docs = sorted({s for s in (_source(definitions.get(r.group(1))) for r in REF_RE.finditer(unit)) if s})
    loose = [d for d in docs if classes.get(d) != "concrete"]
    if ips and len(docs) >= 2 and loose:
        add(IP_COMPARISON, "info", page.rel, f"Contradiction with IP addresses ({', '.join(ips[:3])}) between "
            f"documents not both classified as concrete ({', '.join(loose)}); IP addresses may be placeholders – "
            "remove the entry or ask the user.", ips=ips, documents=docs, not_concrete=loose)


def _page_hints(add: Any, page: Doc, classes: dict[str, str]) -> None:
    """``cross_source_statement`` and ``ip_comparison`` for one page.

    Args:
        add: ``Report.add``.
        page: Wiki page.
        classes: Document ID → classification of its IP addresses.
    """
    assert page.parsed is not None
    definitions = parse_page(page).definitions
    lines = body_lines(page.parsed.body)
    def_lines = {i for i, ln in enumerate(lines) if DEF_RE.match(ln)}
    for sec in page.parsed.sections:
        start = sec.start + (1 if sec.heading is not None else 0)
        for block in section_blocks(lines, range(start, sec.end), def_lines):
            if not block or block[0][1].lstrip().startswith("|"):
                continue
            for unit in _units(block):
                if (sec.base or "").casefold() in CONTRADICTION_SECTIONS:
                    _ip_hint(add, page, unit, definitions, classes)
                if OK_MARK not in unit:
                    for sentence in sentences(unit):
                        _sentence_hint(add, page, sec, sentence, definitions)


def _document_hints(add: Any, docs: list[Doc]) -> dict[str, str]:
    """``ip_addresses_unclassified`` for documents with IP addresses and without the field ``ip_addresses``.

    Args:
        add: ``Report.add``.
        docs: Files from ``documents/``.

    Returns:
        Document ID → classification (``placeholder`` / ``concrete``) of the classified documents.
    """
    classes: dict[str, str] = {}
    for doc in docs:
        if doc.kind != "md" or doc.error or doc.parsed is None:
            continue
        value = classification(doc.meta)
        if value and doc.id:
            classes[doc.id] = value
        found = [] if value else find_ips(doc.body or "")
        if found:
            add(IP_UNCLASSIFIED, "info", doc.rel, f"Document with IP addresses ({', '.join(found[:3])}) without "
                f"{IP_FIELD}: ask the user whether they are concrete or placeholders and propose "
                f"{IP_FIELD}: placeholder | concrete.", found=found)
    return classes


def check_sources(add: Any, pages: list[Doc], docs: list[Doc] | None = None) -> None:
    """Source fidelity checks for wiki pages below ``wiki/topics|entities|summaries|syntheses/`` and IP hints.

    Args:
        add: ``Report.add``.
        pages: Wiki pages.
        docs: Files from ``documents/`` (for ``ip_addresses_unclassified`` and the classifications).
    """
    classes = _document_hints(add, docs or [])
    for page in pages:
        if page.error or page.parsed is None or not page.rel.startswith(CHECKED_DIRS):
            continue
        if not _ignored(page):
            _page_hints(add, page, classes)
        if page.rel.startswith("wiki/syntheses/"):
            body = (page.body or "").casefold()
            if not page.meta.get("confidence") or not any(m in body for m in OWN_MARKERS):
                add(SYNTHESIS_CHECK, "info", page.rel, "Synthesis page without marker for own interpretation "
                    "(confidence and the line \"Own interpretation, not stated in the sources.\").")

# Main ************************************************************************
