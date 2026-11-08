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

from . import images
from .assets import AssetMap
from .config import image_folder
from .errors import PkmError
from .frontmatter import set_fields_linewise
from .gitlayer import build_message
from .imagefix import IMAGE_STEM_MAX, document_date
from .imagelint import generic_file_name, image_files, is_generic_alt
from .paths import slug_words
from .vault import Doc

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

ID_DATE_RE = re.compile(r"^d-(\d{4})(\d{2})(\d{2})-")
KEEP_FOLDERS = ("documents", "documents/_inbox", "documents/_attachments")

# Classes *********************************************************************


@dataclass
class Placement:  # pylint: disable=too-many-instance-attributes
    """Planned changes for a document: new path, moved image files, adjusted links.

    Attributes:
        doc: Document before the change.
        new_rel: New path of the document (same as ``doc.rel`` if it is not renamed).
        moves: Image files ``{from, to}``.
        kept: Image files that stay ``{path, reason}`` (``shared``: other documents link to them too).
        links: Changed links ``{from, to}``.
        text: New text of the document.
        generic_kept: Image files that keep a generic name because their alt text says nothing.
        alts: New alt texts per file (``alt_texts`` of the tool).
    """

    doc: Doc
    new_rel: str
    moves: list[dict[str, str]] = field(default_factory=list)
    kept: list[dict[str, str]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    text: str = ""
    generic_kept: list[str] = field(default_factory=list)
    alts: dict[str, str] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        """Whether nothing changes.

        Returns:
            ``True`` without a new path and without moves.
        """
        return self.new_rel == self.doc.rel and not self.moves and not self.alts


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
        if path and ref.alt and path not in out and not re.fullmatch(r"\d+(?:x\d+)?", ref.alt.strip()):
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


def _given_alts(paths: list[str], alt_texts: dict[str, str] | None, names: dict[str, str]) -> dict[str, str]:
    """Assign the alt texts given by the user to image files (key: path, file name or image name).

    Args:
        paths: Image files of the document.
        alt_texts: File path, file name or image name (``image-2``, as lint reports it) → alt text.
        names: Image name → path of its file.

    Returns:
        Path → alt text.

    Raises:
        PkmError: ``invalid_argument`` for keys that match no image file of the document or empty texts.
    """
    out: dict[str, str] = {}
    unknown = []
    for key, value in (alt_texts or {}).items():
        match = [p for p in paths if p == key or PurePosixPath(p).name.casefold() == key.casefold()]
        match = match or ([names[key]] if key in names else [])
        text = " ".join(str(value).split())
        if len(match) != 1 or not text:
            unknown.append(key)
        else:
            out[match[0]] = text
    if unknown:
        raise PkmError("invalid_argument", "alt_texts: unknown image files or empty texts: " + ", ".join(unknown),
                       unknown=unknown)
    return out


def _file_name(path: str, alt: str, date: str) -> str:
    """File name of an image in its new place: generic names are replaced by the alt text, if it says something.

    Args:
        path: Current path.
        alt: Alt text.
        date: ``YYYY-MM-DD`` of the document.

    Returns:
        ``<alt-text-slug>_<date>.<ext>`` or the current file name.
    """
    name = PurePosixPath(path).name
    if generic_file_name(name) and alt and not is_generic_alt(alt):
        name = f"{slug_words(alt, IMAGE_STEM_MAX)}_{date}{PurePosixPath(name).suffix.lower()}"
    return name


def plan_images(svc: Service, doc: Doc, amap: AssetMap, new_rel: str,
                alt_texts: dict[str, str] | None = None) -> Placement:
    """Plan moving the image files of a document into ``<new name>_img/``.

    Files that other documents link to as well stay where they are (``kept``). Files with a generic
    name get ``<alt text>_<date>.<ext>`` (4.9), if the alt text says something; otherwise they are listed in
    ``generic_kept``. ``alt_texts`` sets alt texts (and with them the file names) in the same step.

    Args:
        svc: Service.
        doc: Document.
        amap: Links of all documents.
        new_rel: New path of the document.
        alt_texts: File path or file name → new alt text (only after confirmation by the user).

    Returns:
        The plan with the adjusted text.
    """
    target = image_folder(new_rel)
    referenced = amap.referenced()
    paths = sorted(amap.links.get(doc.rel, {}))
    plan = Placement(doc, new_rel, alts=_given_alts(paths, alt_texts, {n: p for n, (p, _) in
                                                                      image_files(doc, amap).items() if p}))
    alts = {**_alts(doc, amap), **plan.alts}
    date = name_date(svc, doc)
    taken = {r.casefold() for r in svc.vault.iter_files(("documents",))}
    for path in paths:
        wanted = f"{target}/{_file_name(path, alts.get(path, ''), date)}"
        if generic_file_name(wanted) and referenced.get(path) == [doc.rel]:
            plan.generic_kept.append(path)
        if referenced.get(path) != [doc.rel]:
            if str(PurePosixPath(path).parent) != target:
                plan.kept.append({"path": path, "reason": "shared"})
        elif wanted != path:
            to = _unique(wanted, taken, path)
            taken.discard(path.casefold())
            taken.add(to.casefold())
            plan.moves.append({"from": path, "to": to})
    plan.text, plan.links = relink(doc, amap, plan, svc.cfg.images.link_style)
    return plan


def _new_image(ref: images.ImageRef, new_file: str, new_rel: str, style: str,
               new_alt: str | None = None) -> tuple[str, str]:
    """Markdown image for a moved file, always in the configured link style (``PKM_LINK_STYLE``, 4.9).

    An Obsidian embed ``![[path|option]]`` becomes a Markdown image ``![option](./…)`` (a width like ``300``
    as ``![|300](./…)``), because embeds cannot hold a link relative to the document.

    Args:
        ref: Image.
        new_file: New path of the file.
        new_rel: New path of the document.
        style: ``relative`` (default, ``./<document name>_img/…``) or ``absolute``.
        new_alt: New alt text (a width like ``|300`` stays).

    Returns:
        Tuple of (new Markdown text of the image, new link).
    """
    link = images.file_link(new_rel, new_file, style)
    if ref.raw.startswith("![["):
        option = ref.raw[3:-2].split("|", 1)[1] if "|" in ref.raw else ""
        width = re.fullmatch(r"\d+(?:x\d+)?", option.strip())
        alt = (new_alt or "") + f"|{option}" if width else (new_alt if new_alt is not None else option)
        raw = f"![{alt}]({link})"
    else:
        old_alt = ref.raw[2:ref.raw.index("](")]
        width = old_alt.split("|", 1)[1] if "|" in old_alt else None
        alt = old_alt if new_alt is None else new_alt + (f"|{width}" if width else "")
        raw = f"![{alt}]({link}" + ref.raw[ref.raw.index("](") + 2 + len(ref.link):]
    return raw, link


def relink(doc: Doc, amap: AssetMap, plan: Placement, style: str = "relative") -> tuple[str, list[dict[str, str]]]:
    """Adjust the links to moved image files (and the alt texts given in ``plan.alts``).

    Args:
        doc: Document.
        amap: Links of all documents.
        plan: Plan with moves and new alt texts.
        style: Link style (``PKM_LINK_STYLE``).

    Returns:
        Tuple of (new text, changed links ``{from, to}``).
    """
    text = doc.text or ""
    target_of = {m["from"]: m["to"] for m in plan.moves}
    changes: list[dict[str, str]] = []
    for ref in reversed(images.find_images(text)):
        path = None if ref.inline else amap.resolve(doc.rel, ref)
        if path and (path in target_of or path in plan.alts):
            raw, new = _new_image(ref, target_of.get(path, path), plan.new_rel, style, plan.alts.get(path))
            text = text[:ref.start] + raw + text[ref.end:]
            if new != ref.link:
                changes.insert(0, {"from": ref.link, "to": new})
    return text, changes


def summary(plan: Placement) -> dict[str, Any]:
    """Plan as a tool answer (without the text).

    Args:
        plan: Plan.

    Returns:
        ``images_moved``, ``kept``, ``links``, ``alt_texts`` (set), ``generic_names_kept`` with a hint.
    """
    out: dict[str, Any] = {"images_moved": plan.moves, "kept": plan.kept, "links": plan.links}
    if plan.alts:
        out["alt_texts"] = plan.alts
    if plan.generic_kept:
        out["generic_names_kept"] = plan.generic_kept
        out["hint"] = (f"{len(plan.generic_kept)} image files keep their generic names because their alt text says "
                       "nothing: view them with read_image and propose alt texts (alt_texts) first.")
    return out


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


def move_images(svc: Service, target: str, expected_hash: str, apply: bool = False,
                alt_texts: dict[str, str] | None = None) -> dict[str, Any]:
    """Tool ``move_images``: move the image files of a document into ``<document name>_img/`` (after confirmation).

    Args:
        svc: Service.
        target: Document in ``documents/`` (path, wikilink or ``id:``).
        expected_hash: ``hash`` from ``read``.
        apply: Carry out; without it only the proposal.
        alt_texts: File path or file name → alt text; sets the alt text and names the file after it.

    Returns:
        ``status`` ``proposal``, ``moved`` or ``unchanged``, with ``path``, ``images_moved``, ``kept``, ``links``,
        ``generic_names_kept``.

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
        plan = plan_images(svc, doc, AssetMap(svc, docs), doc.rel, alt_texts)
        result: dict[str, Any] = {"status": "unchanged", "path": rel, **summary(plan)}
        if not plan.empty:
            result = {"status": "moved" if apply else "proposal", "path": rel, **summary(plan)}
            if apply:
                note = f"image files moved to {image_folder(rel)}/" + (", alt texts set" if plan.alts else "")
                result |= apply_plan(svc, plan, note)
    return result

# Main ************************************************************************
