"""Lint hints on names and image locations (specification 8): ``naming`` and ``image_location``.

``naming`` (inbox): document names that do not follow ``<slug>_YYYY-MM-DD.md``, image folders that are
not called ``<document name>_img/`` and image files with generic names. ``image_location`` (all other
documents): image files outside ``<document name>_img/`` (e.g. still in ``documents/_attachments/``).
All hints are ``info``; the agent only proposes, it never renames by itself.

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

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from .assets import AssetMap
from .config import image_folder
from .imageplace import plan_images
from .inboxnames import INBOX, conforming, linked_from, needs_rename, proposed_path
from .vault import Doc
from .wikirefs import wiki_references

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


def _inbox_hints(add: Any, svc: Service, doc: Doc, docs: list[Doc], amap: AssetMap) -> None:
    """``naming`` hints for one document in the inbox: name, image folders, generic image names.

    Args:
        add: ``Report.add``.
        svc: Service.
        doc: Document in the inbox.
        docs: All documents.
        amap: Links of all documents.
    """
    new_rel = proposed_path(svc, doc)
    plan = plan_images(svc, doc, amap, new_rel)
    if not conforming(doc.rel):
        add("naming", "info", doc.rel,
            f"Name does not follow <slug>_YYYY-MM-DD.md; proposal: {PurePosixPath(new_rel).name}. Rename only "
            "after confirmation (rename_document).", kind="document",
            suggested_name=PurePosixPath(new_rel).name, **_references(svc, docs, doc))
    target = image_folder(new_rel)
    folders: dict[str, int] = {}
    for m in plan.moves:
        folder = str(PurePosixPath(m["from"]).parent)
        if folder != target and folder.startswith(INBOX):
            folders[folder] = folders.get(folder, 0) + 1
    for folder, n in sorted(folders.items()):
        add("naming", "info", folder, f"Image folder of {doc.rel} ({n} files) should be called "
            f"{PurePosixPath(target).name}/.", kind="folder", suggested_name=PurePosixPath(target).name,
            document=doc.rel)
    renamed = [{"path": m["from"], "suggested_name": PurePosixPath(m["to"]).name} for m in plan.moves
               if PurePosixPath(m["from"]).name != PurePosixPath(m["to"]).name]
    if renamed:
        add("naming", "info", doc.rel, f"{len(renamed)} image files with generic names (e.g. "
            f"{PurePosixPath(renamed[0]['path']).name}); names from the alt text proposed.", kind="images",
            files=renamed)


def _references(svc: Service, docs: list[Doc], doc: Doc) -> dict[str, Any]:
    """Documents and wiki pages that point to a document (for the hints on renaming).

    Args:
        svc: Service.
        docs: All documents.
        doc: Document.

    Returns:
        ``links`` (documents with wikilinks) and the references from the wiki (``cited_by``, ``citations``,
        ``linked_by_wiki``, ``regenerated``, possibly ``warning``).
    """
    return {"links": linked_from(docs, doc), **wiki_references(svc, doc)}


def _location_hint(add: Any, svc: Service, doc: Doc, docs: list[Doc], amap: AssetMap) -> None:
    """``image_location`` for a document outside the inbox; with a name against the rules, rename first.

    Args:
        add: ``Report.add``.
        svc: Service.
        doc: Document.
        docs: All documents.
        amap: Links of all documents.
    """
    rename = needs_rename(doc.rel)
    new_rel = proposed_path(svc, doc) if rename else doc.rel
    plan = plan_images(svc, doc, amap, new_rel)
    if plan.moves:
        folder = image_folder(new_rel)
        if rename:
            message = (f"{len(plan.moves)} image files outside an image folder of the document; its name breaks the "
                       f"naming rules: propose rename_document first ({PurePosixPath(new_rel).name}), the images "
                       f"move along into {PurePosixPath(folder).name}/.")
            extra: dict[str, Any] = {"suggested_name": PurePosixPath(new_rel).name, **_references(svc, docs, doc)}
        else:
            message = (f"{len(plan.moves)} image files outside {PurePosixPath(folder).name}/ (e.g. "
                       f"{plan.moves[0]['from']}); propose move_images.")
            extra = {}
        if plan.generic_kept:
            message += (f" {len(plan.generic_kept)} files keep generic names (alt text says nothing): propose alt "
                        "texts first (alt_texts).")
            extra["generic_names_kept"] = plan.generic_kept
        add("image_location", "info", doc.rel, message, target=folder, files=plan.moves,
            tool="rename_document" if rename else "move_images", **extra)


def check_names(add: Any, svc: Service, docs: list[Doc]) -> None:
    """Lint ``naming`` (inbox) and ``image_location`` (other documents).

    Args:
        add: ``Report.add``.
        svc: Service.
        docs: Files from ``documents/``.
    """
    amap = AssetMap(svc, docs)
    for doc in docs:
        if doc.kind != "md" or doc.error or doc.parsed is None:
            continue
        if doc.rel.startswith(INBOX):
            _inbox_hints(add, svc, doc, docs, amap)
        else:
            _location_hint(add, svc, doc, docs, amap)

# Main ************************************************************************
