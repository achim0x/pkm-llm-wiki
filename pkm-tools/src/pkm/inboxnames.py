"""Names of new documents in the inbox (specification 4.1, 4.9): proposal and renaming after confirmation.

A Markdown document in ``documents/_inbox/`` that was not created from a chat (e.g. copied in by
hand, from Obsidian or a conversion) gets a proposal for a name following the convention
``<slug>_YYYY-MM-DD.md``. A folder next to it that holds only its image files is renamed along to
``<new name>_img/``, and the links in the document are adjusted.

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
from urllib.parse import quote, unquote

from . import images
from .assets import IMAGE_DIR_SUFFIX, AssetMap
from .errors import PkmError
from .frontmatter import set_fields_linewise
from .gitlayer import build_message
from .imagefix import document_date
from .maint import Maintenance
from .paths import MAX_NAME, fit_stem, slugify
from .vault import Doc, extract_links, link_key

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

INBOX = "documents/_inbox/"
CONFORMING_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*_\d{4}-\d{2}-\d{2}\.md$")
ID_DATE_RE = re.compile(r"^d-(\d{4})(\d{2})(\d{2})-")

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


def name_date(svc: Service, doc: Doc) -> str:
    """Date for the name: ``date_markdown``, otherwise the day the ID was assigned, otherwise today.

    Args:
        svc: Service.
        doc: Document.

    Returns:
        ``YYYY-MM-DD``.
    """
    m = ID_DATE_RE.match(doc.id or "")
    return document_date(doc.meta) or (f"{m[1]}-{m[2]}-{m[3]}" if m else svc.now().strftime("%Y-%m-%d"))


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


def _image_folders(svc: Service, doc: Doc, amap: AssetMap, new_rel: str) -> tuple[list[dict[str, str]], list[dict]]:
    """Folders next to the document that hold only its image files, with their new name.

    Args:
        svc: Service.
        doc: Document.
        amap: Links of all documents.
        new_rel: New path of the document.

    Returns:
        Tuple of (moves ``{from, to}``, kept folders ``{folder, reason}`` with ``shared`` or ``target_exists``).
    """
    parent = str(PurePosixPath(doc.rel).parent)
    referenced = amap.referenced()
    target = f"{parent}/{PurePosixPath(new_rel).stem}{IMAGE_DIR_SUFFIX}"
    moves: list[dict[str, str]] = []
    kept: list[dict[str, str]] = []
    for folder in sorted({str(PurePosixPath(p).parent) for p in amap.links.get(doc.rel, {})}):
        if str(PurePosixPath(folder).parent) != parent or folder == target:
            continue
        files = [r for r in svc.vault.iter_files(("documents",)) if r.startswith(folder + "/")]
        if not all(referenced.get(r) == [doc.rel] for r in files):
            kept.append({"folder": folder, "reason": "shared"})
        elif moves or (svc.vault.path(target).exists() and folder.casefold() != target.casefold()):
            kept.append({"folder": folder, "reason": "target_exists"})
        else:
            moves.append({"from": folder, "to": target})
    return moves, kept


def _new_link(ref: images.ImageRef, path: str, new_file: str, new_rel: str) -> str:
    """Link to a moved image file, in the form of the old link.

    Args:
        ref: Image.
        path: Old path of the file.
        new_file: New path of the file.
        new_rel: New path of the document.

    Returns:
        New link as written in the text (Obsidian embed: path from the vault root; Markdown:
        from the vault root if the old link was written that way, otherwise relative to the document).
    """
    old = unquote(ref.link.strip("<>"))
    if ref.raw.startswith("![["):
        link = new_file
    elif old.lstrip("/") == path:
        link = ("/" if old.startswith("/") else "") + quote(new_file, safe="/._-~")
    else:
        link = images.relative_link(new_rel, new_file)
    return link


def _relink(text: str, doc: Doc, amap: AssetMap, moves: list[dict[str, str]], new_rel: str) -> tuple[str, list]:
    """Adjust links to image files in moved folders.

    Args:
        text: Full text of the document.
        doc: Document.
        amap: Links of all documents.
        moves: Folder moves.
        new_rel: New path of the document.

    Returns:
        Tuple of (new text, changed links ``{from, to}``).
    """
    changes: list[dict[str, str]] = []
    for ref in reversed(images.find_images(text)):
        path = None if ref.inline else amap.resolve(doc.rel, ref)
        move = next((m for m in moves if path and path.startswith(m["from"] + "/")), None)
        bare = "/" not in unquote(ref.link) and ref.raw.startswith("![[")
        if path and move and not bare:
            new = _new_link(ref, path, move["to"] + path[len(move["from"]):], new_rel)
            opener = "[[" if ref.raw.startswith("![[") else "]("
            raw = ref.raw.replace(f"{opener}{ref.link}", f"{opener}{new}", 1)
            text = text[:ref.start] + raw + text[ref.end:]
            changes.insert(0, {"from": ref.link, "to": new})
    return text, changes


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


def plan(svc: Service, doc: Doc, docs: list[Doc], amap: AssetMap, stem: str | None = None) -> dict[str, Any] | None:
    """Renaming proposal for a Markdown document in the inbox.

    Args:
        svc: Service.
        doc: Document.
        docs: All documents.
        amap: Links of all documents.
        stem: Desired name instead of the title (normalized like a slug).

    Returns:
        ``{path, to, image_folders, kept_folders, links, linked_from, text}`` or ``None`` if the
        name already conforms (and no name is given) or the document is not in the inbox.
    """
    result = None
    if doc.rel.startswith(INBOX) and doc.kind == "md" and not doc.error and (stem or not conforming(doc.rel)):
        to = _free_path(svc, str(PurePosixPath(doc.rel).parent), slugify(stem or doc.title, MAX_NAME),
                        f"_{name_date(svc, doc)}", doc.rel)
        moves, kept = _image_folders(svc, doc, amap, to)
        text, links = _relink(doc.text or "", doc, amap, moves, to)
        if to != doc.rel or moves:
            result = {"path": doc.rel, "to": to, "image_folders": moves, "kept_folders": kept, "links": links,
                      "linked_from": linked_from(docs, doc), "text": text}
    return result


def add_rename_proposals(svc: Service, new_docs: list[dict[str, Any]]) -> None:
    """Add ``rename`` (proposal without text) to new Markdown documents in the inbox with a nonconforming name.

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
            proposal = plan(svc, doc, docs, amap) if doc is not None else None
            if proposal:
                entry["rename"] = {k: v for k, v in proposal.items() if k not in ("path", "text")}


def _tracked(svc: Service, paths: list[str]) -> list[str]:
    """Paths known to Git (only these can be committed as removed).

    Args:
        svc: Service.
        paths: Old paths of files and folders.

    Returns:
        The tracked paths.
    """
    return [p for p in paths if svc.writer.git.out("ls-files", "--", p).strip()]


def _move(svc: Service, doc: Doc, proposal: dict[str, Any], new_text: str) -> None:
    """Move image folders and the document, write the new text.

    Args:
        svc: Service.
        doc: Document.
        proposal: Result of ``plan``.
        new_text: New text (with links and possibly version).
    """
    for m in proposal["image_folders"]:
        svc.vault.path(m["from"]).rename(svc.vault.path(m["to"]))
    svc.vault.path(doc.rel).rename(svc.vault.path(proposal["to"]))
    if new_text != (doc.text or ""):
        svc.writer.write_atomic(proposal["to"], new_text)


def _undo(svc: Service, doc: Doc, proposal: dict[str, Any], raw: bytes) -> None:
    """Reverse ``_move`` as far as it got (after a failed commit).

    Args:
        svc: Service.
        doc: Document before the change.
        proposal: Result of ``plan``.
        raw: Bytes of the document before the change.
    """
    new = svc.vault.path(proposal["to"])
    if new.exists():
        new.rename(svc.vault.path(doc.rel))
    svc.vault.path(doc.rel).write_bytes(raw)
    for m in proposal["image_folders"]:
        if svc.vault.path(m["to"]).exists():
            svc.vault.path(m["to"]).rename(svc.vault.path(m["from"]))


def _apply(svc: Service, doc: Doc, proposal: dict[str, Any]) -> dict[str, Any]:
    """Carry out the renaming and commit it (``PKM-Source: agent``).

    Args:
        svc: Service.
        doc: Document (already committed in its current state).
        proposal: Result of ``plan``.

    Returns:
        ``version``, ``commit`` and ``new_hash``.

    Raises:
        PkmError: ``commit_failed`` (everything is then back in its old state).
    """
    text = proposal["text"]
    version = doc.version or 1
    label, note = "moved", f"renamed: {doc.rel} → {proposal['to']}"
    if text != (doc.text or ""):
        version += 1
        text = set_fields_linewise(text, {"version": version, "date_updated": svc.writer.now_stamp()})
        label, note = f"v{version}", note + ", image links adjusted"
    old_paths = _tracked(svc, [doc.rel, *(m["from"] for m in proposal["image_folders"])]) if svc.versioning else []
    raw = svc.vault.path(doc.rel).read_bytes()
    _move(svc, doc, proposal, text)
    sha = ""
    if svc.versioning:
        paths = [proposal["to"], *old_paths, *(m["to"] for m in proposal["image_folders"])]
        try:
            sha = svc.writer.git.commit_paths(list(dict.fromkeys(paths)),
                                              build_message(doc.title, label, note, doc.id or "", version, "agent"))
        except PkmError as exc:
            _undo(svc, doc, proposal, raw)
            raise PkmError("commit_failed", f"Commit failed, renaming undone. {exc.message}") from exc
    new_doc = svc.vault.load(proposal["to"])
    return {"version": version, "commit": sha[:10] or None,
            "new_hash": new_doc.hashes.file_hash if new_doc.hashes else None}


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
        ``image_folders``, ``kept_folders``, ``links``, ``linked_from``.

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
        proposal = plan(svc, doc, docs, AssetMap(svc, docs), stem)
        result: dict[str, Any] = {"status": "unchanged", "path": rel, "reason": "name_conforms"}
        if proposal:
            result = {"status": "renamed" if apply else "proposal", "from": rel, "path": proposal["to"],
                      **{k: proposal[k] for k in ("image_folders", "kept_folders", "links", "linked_from")}}
            if apply:
                result |= {"id": doc.id, **_apply(svc, doc, proposal)}
    return result

# Main ************************************************************************
