"""Place the image files of a document in ``<document name>_img/`` next to it (specification 4.9).

Plans and carries out (only after confirmation by the user) moving the image files a document links
to into its image folder, naming files with generic names (``IMG_013.png``) after their alt text and
adjusting the links. Used by ``move_images`` and ``rename_document``.

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
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, unquote

from . import images
from .assets import AssetMap
from .config import image_folder
from .errors import PkmError
from .frontmatter import set_fields_linewise
from .gitlayer import build_message
from .imagefix import IMAGE_STEM_MAX, document_date
from .imagelint import is_generic_alt
from .paths import slug_words
from .vault import Doc

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

ID_DATE_RE = re.compile(r"^d-(\d{4})(\d{2})(\d{2})-")
HASH_NAME_RE = re.compile(r"^[0-9a-f]{12,}$|^[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)
KEEP_FOLDERS = ("documents", "documents/_inbox", "documents/_attachments")

# Classes *********************************************************************


@dataclass
class Placement:
    """Planned changes for a document: new path, moved image files, adjusted links.

    Attributes:
        doc: Document before the change.
        new_rel: New path of the document (same as ``doc.rel`` if it is not renamed).
        moves: Image files ``{from, to}``.
        kept: Image files that stay ``{path, reason}`` (``shared``: other documents link to them too).
        links: Changed links ``{from, to}``.
        text: New text of the document.
    """

    doc: Doc
    new_rel: str
    moves: list[dict[str, str]] = field(default_factory=list)
    kept: list[dict[str, str]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    text: str = ""

    @property
    def empty(self) -> bool:
        """Whether nothing changes.

        Returns:
            ``True`` without a new path and without moves.
        """
        return self.new_rel == self.doc.rel and not self.moves


# Functions *******************************************************************


def name_date(svc: Service, doc: Doc) -> str:
    """Date for file names: ``date_markdown``, otherwise the day the ID was assigned, otherwise today.

    Args:
        svc: Service.
        doc: Document.

    Returns:
        ``YYYY-MM-DD``.
    """
    m = ID_DATE_RE.match(doc.id or "")
    return document_date(doc.meta) or (f"{m[1]}-{m[2]}-{m[3]}" if m else svc.now().strftime("%Y-%m-%d"))


def generic_file_name(name: str) -> bool:
    """Check whether an image file name says nothing about the content (``IMG_013.png``, ``image.png``, hashes).

    Args:
        name: File name.

    Returns:
        ``True`` for generic names.
    """
    stem = PurePosixPath(name).stem
    return is_generic_alt(stem) or bool(HASH_NAME_RE.match(stem)) or bool(re.fullmatch(r"[\d\s_.-]+", stem))


def _alts(doc: Doc, amap: AssetMap) -> dict[str, str]:
    """First alt text per linked image file.

    Args:
        doc: Document.
        amap: Links of all documents.

    Returns:
        Path → alt text.
    """
    out: dict[str, str] = {}
    for ref in images.find_images(doc.text or ""):
        path = amap.resolve(doc.rel, ref)
        if path and ref.alt and path not in out:
            out[path] = ref.alt
    return out


def _unique(rel: str, taken: set[str], own: str) -> str:
    """Free path for an image file (suffix ``-2``, ``-3`` before the extension).

    Args:
        rel: Desired path.
        taken: Paths taken (casefolded).
        own: Current path of the file (counts as free).

    Returns:
        A free path.
    """
    p = PurePosixPath(rel)
    candidate, n = rel, 1
    while candidate.casefold() in taken and candidate.casefold() != own.casefold():
        n += 1
        candidate = str(p.with_name(f"{p.stem}-{n}{p.suffix}"))
    return candidate


def plan_images(svc: Service, doc: Doc, amap: AssetMap, new_rel: str) -> Placement:
    """Plan moving the image files of a document into ``<new name>_img/``.

    Files that other documents link to as well stay where they are (``kept``). Files with a generic
    name get ``<alt text>_<date>.<ext>`` (4.9), if the alt text says something.

    Args:
        svc: Service.
        doc: Document.
        amap: Links of all documents.
        new_rel: New path of the document.

    Returns:
        The plan with the adjusted text.
    """
    target = image_folder(new_rel)
    referenced = amap.referenced()
    alts = _alts(doc, amap)
    date = name_date(svc, doc)
    taken = {r.casefold() for r in svc.vault.iter_files(("documents",))}
    plan = Placement(doc, new_rel)
    for path in sorted(amap.links.get(doc.rel, {})):
        name = PurePosixPath(path).name
        alt = alts.get(path, "")
        if generic_file_name(name) and alt and not is_generic_alt(alt):
            name = f"{slug_words(alt, IMAGE_STEM_MAX)}_{date}{PurePosixPath(name).suffix.lower()}"
        wanted = f"{target}/{name}"
        if referenced.get(path) != [doc.rel]:
            if str(PurePosixPath(path).parent) != target:
                plan.kept.append({"path": path, "reason": "shared"})
        elif wanted != path:
            to = _unique(wanted, taken, path)
            taken.discard(path.casefold())
            taken.add(to.casefold())
            plan.moves.append({"from": path, "to": to})
    plan.text, plan.links = relink(doc, amap, plan.moves, new_rel)
    return plan


def _new_link(ref: images.ImageRef, path: str, new_file: str, new_rel: str) -> str | None:
    """Link to a moved image file, in the form of the old link.

    Args:
        ref: Image.
        path: Old path of the file.
        new_file: New path of the file.
        new_rel: New path of the document.

    Returns:
        New link as written in the text, or ``None`` if the old link stays valid (Obsidian embed with the
        bare, unchanged file name).
    """
    old = unquote(ref.link.strip("<>"))
    link: str | None
    if ref.raw.startswith("![["):
        same_name = PurePosixPath(path).name == PurePosixPath(new_file).name
        link = None if "/" not in old and same_name else new_file
    elif old.lstrip("/") == path:
        link = ("/" if old.startswith("/") else "") + quote(new_file, safe="/._-~")
    else:
        link = images.relative_link(new_rel, new_file)
    return link


def relink(doc: Doc, amap: AssetMap, moves: list[dict[str, str]], new_rel: str) -> tuple[str, list[dict[str, str]]]:
    """Adjust the links to moved image files (and relative links if the document itself moves).

    Args:
        doc: Document.
        amap: Links of all documents.
        moves: Moved image files.
        new_rel: New path of the document.

    Returns:
        Tuple of (new text, changed links ``{from, to}``).
    """
    text = doc.text or ""
    target_of = {m["from"]: m["to"] for m in moves}
    moved_doc = PurePosixPath(new_rel).parent != PurePosixPath(doc.rel).parent
    changes: list[dict[str, str]] = []
    for ref in reversed(images.find_images(text)):
        path = None if ref.inline else amap.resolve(doc.rel, ref)
        if path and (path in target_of or moved_doc):
            new = _new_link(ref, path, target_of.get(path, path), new_rel)
            if new is not None and new != ref.link:
                opener = "[[" if ref.raw.startswith("![[") else "]("
                raw = ref.raw.replace(f"{opener}{ref.link}", f"{opener}{new}", 1)
                text = text[:ref.start] + raw + text[ref.end:]
                changes.insert(0, {"from": ref.link, "to": new})
    return text, changes


def summary(plan: Placement) -> dict[str, Any]:
    """Plan as a tool answer (without the text).

    Args:
        plan: Plan.

    Returns:
        ``images_moved``, ``kept``, ``links``.
    """
    return {"images_moved": plan.moves, "kept": plan.kept, "links": plan.links}


def _tracked(svc: Service, paths: list[str]) -> list[str]:
    """Paths known to Git (only these can be committed as removed).

    Args:
        svc: Service.
        paths: Old paths.

    Returns:
        The tracked paths.
    """
    return [p for p in paths if svc.versioning and svc.writer.git.out("ls-files", "--", p).strip()]


def _move_files(svc: Service, plan: Placement, new_text: str) -> None:
    """Move image files and the document, write the new text, remove emptied folders.

    Args:
        svc: Service.
        plan: Plan.
        new_text: New text (with links and possibly version).
    """
    for m in plan.moves:
        dest = svc.vault.path(m["to"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        svc.vault.path(m["from"]).rename(dest)
    if plan.new_rel != plan.doc.rel:
        svc.vault.path(plan.doc.rel).rename(svc.vault.path(plan.new_rel))
    if new_text != (plan.doc.text or ""):
        svc.writer.write_atomic(plan.new_rel, new_text)
    for folder in sorted({str(PurePosixPath(m["from"]).parent) for m in plan.moves}, reverse=True):
        p = svc.vault.path(folder)
        if folder not in KEEP_FOLDERS and p.is_dir() and not any(p.iterdir()):
            p.rmdir()


def _undo(svc: Service, plan: Placement, raw: bytes) -> None:
    """Reverse ``_move_files`` as far as it got (after a failed commit).

    Args:
        svc: Service.
        plan: Plan.
        raw: Bytes of the document before the change.
    """
    new = svc.vault.path(plan.new_rel)
    if plan.new_rel != plan.doc.rel and new.exists():
        new.rename(svc.vault.path(plan.doc.rel))
    svc.vault.path(plan.doc.rel).write_bytes(raw)
    for m in reversed(plan.moves):
        if svc.vault.path(m["to"]).exists():
            svc.vault.path(m["from"]).parent.mkdir(parents=True, exist_ok=True)
            svc.vault.path(m["to"]).rename(svc.vault.path(m["from"]))


def apply_plan(svc: Service, plan: Placement, note: str) -> dict[str, Any]:
    """Carry out a plan and commit it (``PKM-Source: agent``).

    A pure move or renaming without a change of text is committed as ``moved`` without a new version;
    with adjusted links it is a new version. In the next run the document has ``image_notation_only``.

    Args:
        svc: Service.
        plan: Plan (the document is already committed in its current state).
        note: Change note.

    Returns:
        ``id``, ``version``, ``commit`` and ``new_hash``.

    Raises:
        PkmError: ``commit_failed`` (everything is then back in its old state).
    """
    doc = plan.doc
    text = plan.text
    version = doc.version or 1
    label = "moved"
    if text != (doc.text or ""):
        version += 1
        text = set_fields_linewise(text, {"version": version, "date_updated": svc.writer.now_stamp()})
        label = f"v{version}"
    old_paths = _tracked(svc, [doc.rel, *(m["from"] for m in plan.moves)])
    raw = svc.vault.path(doc.rel).read_bytes()
    _move_files(svc, plan, text)
    sha = ""
    if svc.versioning:
        paths = list(dict.fromkeys([plan.new_rel, *old_paths, *(m["to"] for m in plan.moves)]))
        try:
            sha = svc.writer.git.commit_paths(paths, build_message(doc.title, label, note, doc.id or "", version,
                                                                   "agent"))
        except PkmError as exc:
            _undo(svc, plan, raw)
            raise PkmError("commit_failed", f"Commit failed, changes undone. {exc.message}") from exc
    new_doc = svc.vault.load(plan.new_rel)
    return {"id": doc.id, "version": version, "commit": sha[:10] or None,
            "new_hash": new_doc.hashes.file_hash if new_doc.hashes else None}


def move_images(svc: Service, target: str, expected_hash: str, apply: bool = False) -> dict[str, Any]:
    """Tool ``move_images``: move the image files of a document into ``<document name>_img/`` (after confirmation).

    Args:
        svc: Service.
        target: Document in ``documents/`` (path, wikilink or ``id:``).
        expected_hash: ``hash`` from ``read``.
        apply: Carry out; without it only the proposal.

    Returns:
        ``status`` ``proposal``, ``moved`` or ``unchanged``, with ``path``, ``images_moved``, ``kept``, ``links``.

    Raises:
        PkmError: ``forbidden`` outside ``documents/``, ``conflict`` for a wrong hash.
    """
    from .maint import Maintenance  # pylint: disable=import-outside-toplevel  # maint is heavy, only here

    rel = svc.resolve(target, ("documents",))
    if not rel.startswith("documents/"):
        raise PkmError("forbidden", "Only documents in documents/ have image folders.", path=rel)
    writer = svc.writer
    with writer.lock():
        doc = writer.editable_doc(rel)
        writer.require_git()
        writer.check_hash(doc, expected_hash)
        if apply:
            doc = writer.commit_user_state(doc)
        docs = Maintenance(svc).documents()[0]
        plan = plan_images(svc, doc, AssetMap(svc, docs), doc.rel)
        result: dict[str, Any] = {"status": "unchanged", "path": rel, "kept": plan.kept}
        if not plan.empty:
            result = {"status": "moved" if apply else "proposal", "path": rel, **summary(plan)}
            if apply:
                result |= apply_plan(svc, plan, f"image files moved to {image_folder(rel)}/")
    return result

# Main ************************************************************************
