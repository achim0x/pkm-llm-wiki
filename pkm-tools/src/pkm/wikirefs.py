"""References from the wiki to documents and image files (citations and plain wikilinks).

Used when renaming documents or moving image files (``rename_document``, ``move_images``, lint ``naming``
and ``image_location``): citations follow a renamed document via its ID in ``finish_maintenance``, plain
wikilinks on wiki pages do not. Generated files (``wiki/index.md``, ``wiki/_status.md``, ``wiki/log.md``)
are written anew in every run and are only named as ``regenerated``.

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
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from .pagetext import DEF_RE
from .vault import GENERATED, WIKILINK_RE, Doc, link_key

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


def _keys(doc: Doc | None, files: list[str]) -> set[str]:
    """Link keys of a document and of image files.

    Args:
        doc: Document or ``None``.
        files: Paths of image files.

    Returns:
        Casefolded keys (full path and name).
    """
    keys = set(doc.link_keys()) if doc is not None else set()
    for rel in files:
        keys |= {link_key(rel), link_key(PurePosixPath(rel).name)}
    return keys


def _count(body: str, keys: set[str], id_mark: str | None) -> tuple[int, int]:
    """Citations and plain wikilinks on one page.

    Args:
        body: Body of the page.
        keys: Link keys of the targets.
        id_mark: ``id:<id>`` of the document or ``None``.

    Returns:
        Tuple of (citations, plain links outside citation lines).
    """
    citations = links = 0
    for line in body.splitlines():
        m = DEF_RE.match(line)
        hits = sum(1 for w in WIKILINK_RE.finditer(line) if link_key(w.group(1)) in keys)
        if m:
            cited = bool(id_mark and re.search(rf"{re.escape(id_mark)}(?![\w-])", m.group(2)))
            citations += 1 if cited or hits else 0
        else:
            links += hits
    return citations, links


def wiki_references(svc: Service, doc: Doc | None = None, files: list[str] | None = None) -> dict[str, Any]:
    """Wiki pages that cite or link a document (or link image files).

    Args:
        svc: Service.
        doc: Document (citations via ``id:`` or link, plain links); ``None`` for image files only.
        files: Image files whose wikilinks count as plain links.

    Returns:
        ``cited_by`` (``[{page, citations}]``, only pages with citations), ``citations`` (total),
        ``linked_by_wiki`` (``[{page, links}]``, plain wikilinks outside citations; they are not adjusted),
        ``regenerated`` (generated files with a link, written anew by ``finish_maintenance``) and, if there
        are plain links, ``warning``.
    """
    keys = _keys(doc, files or [])
    id_mark = f"id:{doc.id}" if doc is not None and doc.id else None
    cited: list[dict[str, Any]] = []
    linked: list[dict[str, Any]] = []
    regenerated: list[str] = []
    for rel in sorted(svc.vault.iter_files(("wiki",))):
        if not rel.lower().endswith(".md") or rel.startswith("wiki/_lint/"):
            continue
        page = svc.vault.load(rel)
        if page.error or page.parsed is None:
            continue
        n_cit, n_links = _count(page.body, keys, id_mark)
        if rel in GENERATED:
            if n_cit or n_links:
                regenerated.append(rel[:-3])
            continue
        if n_cit:
            cited.append({"page": rel[:-3], "citations": n_cit})
        if n_links:
            linked.append({"page": rel[:-3], "links": n_links})
    result: dict[str, Any] = {"cited_by": cited, "citations": sum(c["citations"] for c in cited),
                              "linked_by_wiki": linked, "regenerated": regenerated}
    if linked:
        result["warning"] = ("Plain wikilinks on the pages in linked_by_wiki are not adjusted; fix them with "
                             "write_wiki_page afterwards. Citations follow via the ID with finish_maintenance.")
    return result

# Main ************************************************************************
