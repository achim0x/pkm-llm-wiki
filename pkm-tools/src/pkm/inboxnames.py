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
from .paths import MAX_NAME, fit_stem, slugify
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
        ``<folder>/<slug>_YYYY-MM-DD.md`` (or the current path if it conforms and no name is given).
    """
    result = doc.rel
    if stem or not conforming(doc.rel):
        result = _free_path(svc, str(PurePosixPath(doc.rel).parent), slugify(stem or doc.title, MAX_NAME),
                            f"_{name_date(svc, doc)}", doc.rel)
    return result


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


def plan(svc: Service, doc: Doc, amap: AssetMap, stem: str | None = None) -> Placement | None:
    """Renaming plan for a Markdown document in the inbox, with its image files.

    Args:
        svc: Service.
        doc: Document.
        amap: Links of all documents.
        stem: Desired name instead of the title (normalized like a slug).

    Returns:
        The plan, or ``None`` outside the inbox or if the name already conforms (and no name is given).
    """
    result = None
    if doc.rel.startswith(INBOX) and doc.kind == "md" and not doc.error and (stem or not conforming(doc.rel)):
        result = plan_images(svc, doc, amap, proposed_path(svc, doc, stem))
    return result


def _answer(placement: Placement, docs: list[Doc]) -> dict[str, Any]:
    """Proposal as data (without the text).

    Args:
        placement: Plan.
        docs: All documents.

    Returns:
        ``to``, ``images_moved``, ``kept``, ``links``, ``linked_from``.
    """
    return {"to": placement.new_rel, **summary(placement), "linked_from": linked_from(docs, placement.doc)}


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
                entry["rename"] = _answer(placement, docs)


def rename_inbox_document(
    svc: Service, target: str, expected_hash: str, apply: bool = False, stem: str | None = None
) -> dict[str, Any]:
    """Tool ``rename_document``: name a document in the inbox after the convention (only after confirmation).

    Args:
        svc: Service.
        target: Document in ``documents/_inbox/`` (path, wikilink or ``id:``).
        expected_hash: ``hash`` from ``read``.
        apply: Carry out; without it only the proposal.
        stem: Desired name instead of the title (becomes a slug; date and suffix are added).

    Returns:
        ``status`` ``proposal``, ``renamed`` or ``unchanged`` (name already conforms), with ``from``, ``path``,
        ``images_moved``, ``kept``, ``links``, ``linked_from``.

    Raises:
        PkmError: ``forbidden`` outside the inbox or for non-Markdown files, ``conflict`` for a wrong hash.
    """
    rel = svc.resolve(target, ("documents",))
    if not rel.startswith(INBOX) or not rel.lower().endswith(".md"):
        raise PkmError("forbidden", "Only Markdown documents in documents/_inbox/ can be renamed.", path=rel)
    writer = svc.writer
    with writer.lock():
        doc = writer.editable_doc(rel)
        writer.require_git()
        writer.check_hash(doc, expected_hash)
        if apply:
            doc = writer.commit_user_state(doc)
        docs = Maintenance(svc).documents()[0]
        placement = plan(svc, doc, AssetMap(svc, docs), stem)
        result: dict[str, Any] = {"status": "unchanged", "path": rel, "reason": "name_conforms"}
        if placement is not None and not placement.empty:
            answer = _answer(placement, docs)
            result = {"status": "renamed" if apply else "proposal", "from": rel, "path": answer.pop("to"), **answer}
            if apply:
                result |= apply_plan(svc, placement, f"renamed: {rel} → {placement.new_rel}")
    return result

# Main ************************************************************************
