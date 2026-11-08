"""Names of new documents in the inbox (specification 4.1, 4.9): proposal and renaming after confirmation.

A Markdown document in ``documents/_inbox/`` that was not created from a chat (e.g. copied in by
hand, from Obsidian or a conversion) gets a proposal for a name following the convention
``<slug>_YYYY-MM-DD.md``. Its image files move along into ``<new name>_img/`` (``imageplace``).

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

from .assets import AssetMap
from .errors import PkmError
from .imageplace import Placement, apply_plan, name_date, plan_images, summary
from .maint import Maintenance
from .pagetext import DEF_RE
from .paths import MAX_NAME, fit_stem, slug_words, title_slug
from .vault import Doc, extract_links, link_key

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

INBOX = "documents/_inbox/"
CONFORMING_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*_\d{4}-\d{2}-\d{2}\.md$")

# Classes *********************************************************************

# Functions *******************************************************************


def conforming(rel: str) -> bool:
    """Check whether a file name follows the convention for new documents (``<slug>_YYYY-MM-DD.md``).

    Args:
        rel: Path of the document.

    Returns:
        ``True`` if the name conforms (a suffix like ``-2`` before the date is part of the slug).
    """
    name = PurePosixPath(rel).name
    return bool(CONFORMING_RE.match(name)) and len(name) <= MAX_NAME


CLEAN_STEM_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def needs_rename(rel: str) -> bool:
    """Check whether a document name breaks the naming rules (4.1).

    In the inbox the name must follow ``<slug>_YYYY-MM-DD.md``; elsewhere in ``documents/`` it must only be
    lower case with hyphens (filing may rename freely, e.g. ``zisterne.md``).

    Args:
        rel: Path of a Markdown document.

    Returns:
        ``True`` if a renaming should be proposed.
    """
    stem = PurePosixPath(rel).name[:-3] if rel.lower().endswith(".md") else PurePosixPath(rel).stem
    return not conforming(rel) if rel.startswith(INBOX) else not CLEAN_STEM_RE.match(stem)


def _free_path(svc: Service, folder: str, stem: str, tail: str, own: str) -> str:
    """Free path ``<folder>/<stem>[-n]<tail>.md``; the document's own path counts as free.

    Args:
        svc: Service.
        folder: Folder of the document.
        stem: Slug.
        tail: ``_YYYY-MM-DD``.
        own: Current path of the document.

    Returns:
        Path with at most ``MAX_NAME`` characters in the name (only the slug is shortened).
    """
    taken = {r.casefold() for r in svc.vault.iter_files(("documents",)) if r.casefold() != own.casefold()}

    def busy(rel: str) -> bool:
        """Whether a path is taken by another file.

        Args:
            rel: Candidate.

        Returns:
            ``True`` if taken.
        """
        same = rel.casefold() == own.casefold()
        return not same and (rel.casefold() in taken or svc.vault.path(rel).exists())

    n = 1
    rel = f"{folder}/{fit_stem(stem, tail + '.md')}{tail}.md"
    while busy(rel):
        n += 1
        rel = f"{folder}/{fit_stem(stem, f'-{n}{tail}.md')}-{n}{tail}.md"
    return rel


def proposed_path(svc: Service, doc: Doc, stem: str | None = None) -> str:
    """New path of a document in the inbox after the naming convention.

    Args:
        svc: Service.
        doc: Document.
        stem: Desired name instead of the title.

    Returns:
        ``<folder>/<slug>_YYYY-MM-DD.md`` (or the current path if it conforms and no name is given). Without
        ``stem`` the slug comes from the title without subtitle; at most ``PKM_SLUG_MAX`` characters, cut at a
        word boundary.
    """
    result = doc.rel
    if stem or needs_rename(doc.rel):
        slug = slug_words(stem, svc.cfg.slug_max) if stem else title_slug(doc.title, svc.cfg.slug_max)
        result = _free_path(svc, str(PurePosixPath(doc.rel).parent), slug, f"_{name_date(svc, doc)}", doc.rel)
    return result


def cited_by(svc: Service, doc: Doc) -> list[dict[str, Any]]:
    """Wiki pages that cite or link a document, with the number of citations.

    The renaming does not change wiki pages; ``finish_maintenance`` (and ``begin_maintenance`` in the next run)
    move the citations to the new path via the document ID.

    Args:
        svc: Service.
        doc: Document.

    Returns:
        ``[{page, citations}]`` sorted by page (``citations`` 0 for pure links).
    """
    keys = doc.link_keys()
    id_mark = f"id:{doc.id}" if doc.id else None
    out = []
    for rel in svc.vault.iter_files(("wiki",)):
        if not rel.lower().endswith(".md"):
            continue
        page = svc.vault.load(rel)
        if page.error or page.parsed is None:
            continue
        n = 0
        for line in page.body.splitlines():
            m = DEF_RE.match(line)
            if m and ((id_mark and re.search(rf"{re.escape(id_mark)}(?![\w-])", m.group(2)))
                      or any(link_key(t) in keys for t in extract_links(m.group(2)))):
                n += 1
        if n or any(link_key(t) in keys for t in extract_links(page.body)):
            out.append({"page": rel[:-3], "citations": n})
    return sorted(out, key=lambda e: e["page"])


def linked_from(docs: list[Doc], doc: Doc) -> list[str]:
    """Documents whose wikilinks point to a document (they are not changed by the renaming).

    Args:
        docs: All documents.
        doc: Target.

    Returns:
        Paths, sorted.
    """
    keys = doc.link_keys()
    return sorted(d.rel for d in docs if d.kind == "md" and d.rel != doc.rel
                  and any(link_key(t) in keys for t in extract_links(d.body)))


def plan(svc: Service, doc: Doc, amap: AssetMap, stem: str | None = None,
         alt_texts: dict[str, str] | None = None) -> Placement | None:
    """Renaming plan for a Markdown document in ``documents/``, with its image files.

    Args:
        svc: Service.
        doc: Document.
        amap: Links of all documents.
        stem: Desired name instead of the title (normalized like a slug).
        alt_texts: New alt texts per image file (see ``imageplace.plan_images``).

    Returns:
        The plan, or ``None`` outside ``documents/`` or if the name already follows the rules (and no name is
        given).
    """
    result = None
    if doc.rel.startswith("documents/") and doc.kind == "md" and not doc.error and (stem or needs_rename(doc.rel)):
        result = plan_images(svc, doc, amap, proposed_path(svc, doc, stem), alt_texts)
    return result


def _answer(svc: Service, placement: Placement, docs: list[Doc]) -> dict[str, Any]:
    """Proposal as data (without the text).

    Args:
        svc: Service.
        placement: Plan.
        docs: All documents.

    Returns:
        ``to``, ``images_moved``, ``kept``, ``links``, ``linked_from`` (documents), ``cited_by`` (wiki pages with
        the number of citations), ``citations`` (total) and ``generic_names_kept``.
    """
    pages = cited_by(svc, placement.doc)
    return {"to": placement.new_rel, **summary(placement), "linked_from": linked_from(docs, placement.doc),
            "cited_by": pages, "citations": sum(p["citations"] for p in pages)}


def add_rename_proposals(svc: Service, new_docs: list[dict[str, Any]]) -> None:
    """Add ``rename`` to new Markdown documents in the inbox with a nonconforming name.

    Args:
        svc: Service.
        new_docs: Entries of ``pending.new``.
    """
    wanted = [e for e in new_docs if str(e.get("path") or "").startswith(INBOX)
              and str(e.get("path")).lower().endswith(".md") and not conforming(str(e.get("path")))]
    if wanted:
        docs = Maintenance(svc).documents()[0]
        amap = AssetMap(svc, docs)
        by_rel = {d.rel: d for d in docs}
        for entry in wanted:
            doc = by_rel.get(entry["path"])
            placement = plan(svc, doc, amap) if doc is not None else None
            if placement is not None and not placement.empty:
                entry["rename"] = _answer(svc, placement, docs)


def rename_inbox_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    svc: Service, target: str, expected_hash: str, apply: bool = False, stem: str | None = None,
    alt_texts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Tool ``rename_document``: name a document after the naming rules (only after confirmation).

    In the inbox the name follows ``<slug>_YYYY-MM-DD.md``; elsewhere in ``documents/`` a name with capital
    letters, spaces or other characters gets the same form (4.1, 9.8). The image files move along.

    Args:
        svc: Service.
        target: Markdown document in ``documents/`` (path, wikilink or ``id:``).
        expected_hash: ``hash`` from ``read``.
        apply: Carry out; without it only the proposal.
        stem: Desired name instead of the title (becomes a slug; date and suffix are added).
        alt_texts: File path or file name → alt text for image files (names follow the alt text).

    Returns:
        ``status`` ``proposal``, ``renamed`` or ``unchanged`` (name already conforms), with ``from``, ``path``,
        ``images_moved``, ``kept``, ``links``, ``linked_from``, ``cited_by``, ``citations``.

    Raises:
        PkmError: ``forbidden`` outside ``documents/`` or for non-Markdown files, ``conflict`` for a wrong hash.
    """
    rel = svc.resolve(target, ("documents",))
    if not rel.startswith("documents/") or not rel.lower().endswith(".md"):
        raise PkmError("forbidden", "Only Markdown documents in documents/ can be renamed.", path=rel)
    writer = svc.writer
    with writer.lock():
        doc = writer.editable_doc(rel)
        writer.require_git()
        writer.check_hash(doc, expected_hash)
        if apply:
            doc = writer.commit_user_state(doc)
        docs = Maintenance(svc).documents()[0]
        placement = plan(svc, doc, AssetMap(svc, docs), stem, alt_texts)
        result: dict[str, Any] = {"status": "unchanged", "path": rel, "reason": "name_conforms"}
        if placement is not None and not placement.empty:
            answer = _answer(svc, placement, docs)
            result = {"status": "renamed" if apply else "proposal", "from": rel, "path": answer.pop("to"), **answer}
            if apply:
                result |= apply_plan(svc, placement, f"renamed: {rel} → {placement.new_rel}")
    return result

# Main ************************************************************************
