"""Image files belonging to documents (specification 4.9): links, hashes, orphaned attachments.

An image file that a Markdown document in ``documents/`` links to belongs to that document:
it is not a standalone document, and a change to it is a change of the document.

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

import posixpath
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from . import hashes, images
from .vault import Doc

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

ATTACHMENTS_PREFIX = "documents/_attachments/"
IMAGE_DIR_SUFFIX = "_img"
IMAGE_SUFFIXES = (".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp")

# Classes *********************************************************************


class AssetMap:
    """Links of all Markdown documents in ``documents/`` to image files."""

    def __init__(self, svc: Service, docs: list[Doc]) -> None:
        """Collect references.

        Args:
            svc: Service.
            docs: Documents from ``documents/`` (Markdown and attachments).
        """
        self.svc = svc
        files = [d.rel for d in docs if d.kind == "bin"]
        self._by_name: dict[str, list[str]] = {}
        self._by_fold: dict[str, list[str]] = {}
        for rel in files:
            self._by_name.setdefault(PurePosixPath(rel).name.casefold(), []).append(rel)
            self._by_fold.setdefault(rel.casefold(), []).append(rel)
        self._files = set(files)
        self.links: dict[str, dict[str, list[str]]] = {}
        for doc in docs:
            if doc.kind == "md" and doc.parsed is not None and not doc.error:
                self.links[doc.rel] = self._doc_links(doc)

    def _exact(self, path: str) -> str | None:
        """Existing file for a vault path; without a match on the exact spelling also ignoring case.

        Args:
            path: Path in the vault.

        Returns:
            Existing path or ``None`` (also for several matches ignoring case).
        """
        matches = self._by_fold.get(path.casefold(), [])
        return path if path in self._files else (matches[0] if len(matches) == 1 else None)

    def _resolve(self, doc_rel: str, ref: images.ImageRef) -> str | None:
        """Path of the image file of a linked image, regardless of the folder it lies in.

        Tried in order: the link relative to the document (Markdown) or from the vault root
        (Obsidian), the other of the two, each also ignoring case (macOS and Windows do not
        distinguish it), then a unique file whose path ends with the link (Obsidian's shortest
        path), and for a bare file name a unique file with that name.

        Args:
            doc_rel: Path of the document.
            ref: Image.

        Returns:
            Existing path or ``None``.
        """
        target = images.link_target(ref, doc_rel)
        found = None
        if target:
            link = unquote(ref.link.strip("<>")).lstrip("/")
            relative = posixpath.normpath(posixpath.join(posixpath.dirname(doc_rel), link))
            for candidate in dict.fromkeys([target, relative, link]):
                found = found or self._exact(candidate)
            if found is None and "/" in link:
                tail = "/" + link.casefold()
                ends = [p for p in self._files if p.casefold().endswith(tail)]
                found = ends[0] if len(ends) == 1 else None
            if found is None and "/" not in link:
                matches = self._by_name.get(link.casefold(), [])
                found = matches[0] if len(matches) == 1 else None
        return found

    def _doc_links(self, doc: Doc) -> dict[str, list[str]]:
        """Image files of a document with the sections they appear in.

        Args:
            doc: Document.

        Returns:
            Path → section keys.
        """
        body = doc.body or ""
        sections = list(doc.parsed.sections) if doc.parsed is not None else []
        out: dict[str, list[str]] = {}
        for ref in images.find_images(body):
            path = None if ref.inline else self._resolve(doc.rel, ref)
            if path:
                line = body.count("\n", 0, ref.start)
                key = next((s.key for s in sections if s.start <= line < s.end), "")
                out.setdefault(path, []).append(key)
        return out

    def resolve(self, doc_rel: str, ref: images.ImageRef) -> str | None:
        """Path of the image file a linked image of a document points to.

        Args:
            doc_rel: Path of the document.
            ref: Image.

        Returns:
            Existing path or ``None`` (also for embedded images).
        """
        return None if ref.inline else self._resolve(doc_rel, ref)

    def link_hash(self, doc_rel: str, recorded: dict[str, str] | None = None) -> Any:
        """Function for ``imagefix.notation_only``: hash of the file of a linked image.

        Args:
            doc_rel: Path of the document the links are relative to.
            recorded: Hashes per path recorded earlier (``assets`` in ``state.json``); they take
                precedence over the current file (for the earlier state of a document).

        Returns:
            Function ``ImageRef`` → SHA-256 or ``None``.
        """
        def digest(ref: images.ImageRef) -> str | None:
            """Hash of the linked file.

            Args:
                ref: Image.

            Returns:
                SHA-256 or ``None`` if the file is not found.
            """
            path = self.resolve(doc_rel, ref)
            value = None
            if path is not None:
                value = (recorded or {}).get(path) or hashes.sha256_bytes(self.svc.vault.path(path).read_bytes())
            elif recorded and not ref.inline:
                value = _recorded_hash(doc_rel, ref, recorded)
            return value

        return digest

    def referenced(self) -> dict[str, list[str]]:
        """Image files with the documents that use them.

        Returns:
            Path of the file → paths of the documents.
        """
        out: dict[str, list[str]] = {}
        for doc_rel, links in self.links.items():
            for path in links:
                out.setdefault(path, []).append(doc_rel)
        return out

    def assets(self, doc_rel: str) -> dict[str, str]:
        """Linked image files of a document with their hash (for ``state.json``).

        Args:
            doc_rel: Path of the document.

        Returns:
            Path → SHA-256.
        """
        return {p: hashes.sha256_bytes(self.svc.vault.path(p).read_bytes())
                for p in sorted(self.links.get(doc_rel, {}))}

    def sections_for(self, doc_rel: str, paths: set[str]) -> list[str]:
        """Sections of a document that show one of the files.

        Args:
            doc_rel: Path of the document.
            paths: Image files.

        Returns:
            Section keys without duplicates.
        """
        links = self.links.get(doc_rel, {})
        return list(dict.fromkeys(k for p in sorted(paths) for k in links.get(p, [])))

    def orphans(self, known: set[str]) -> list[str]:
        """Orphaned attachments: image files without links that belonged to a document (in any folder) or
        lie in an attachment folder (``documents/_attachments/`` or a folder ``<document>_img/``).

        Args:
            known: Paths listed as ``assets`` in ``state.json``.

        Returns:
            Sorted paths.
        """
        used = set(self.referenced())
        return sorted(p for p in self._files if p not in used and p.lower().endswith(IMAGE_SUFFIXES)
                      and (p in known or in_attachment_folder(p)))

# Functions *******************************************************************


def in_attachment_folder(rel: str) -> bool:
    """Check whether a file lies in a folder meant for attachments.

    Args:
        rel: Path in the vault.

    Returns:
        ``True`` for ``documents/_attachments/`` and folders whose name ends in ``_img``.
    """
    return rel.startswith(ATTACHMENTS_PREFIX) or any(part.endswith(IMAGE_DIR_SUFFIX)
                                                    for part in PurePosixPath(rel).parts[1:-1])


def _recorded_hash(doc_rel: str, ref: images.ImageRef, recorded: dict[str, str]) -> str | None:
    """Recorded hash of an image file that no longer exists at the linked path (earlier state, moved files).

    Args:
        doc_rel: Path of the document.
        ref: Image of the earlier text.
        recorded: ``assets`` from ``state.json``.

    Returns:
        SHA-256 or ``None``.
    """
    link = unquote(ref.link.strip("<>")).lstrip("/")
    target = images.link_target(ref, doc_rel) or ""
    folded = {p.casefold(): h for p, h in recorded.items()}
    value = None
    for candidate in (target, posixpath.normpath(posixpath.join(posixpath.dirname(doc_rel), link)), link):
        value = value or folded.get(candidate.casefold())
    if value is None:
        ends = [h for p, h in folded.items() if p.endswith("/" + link.casefold()) or p == link.casefold()]
        value = ends[0] if len(ends) == 1 else None
    return value


def known_assets(entries: dict[str, Any]) -> set[str]:
    """All image files listed as belonging to a document in ``state.json``.

    Args:
        entries: ``documents`` from ``state.json``.

    Returns:
        Paths.
    """
    return {p for e in entries.values() for p in (e.get("assets") or {})}


def asset_changes(old: dict[str, str] | None, new: dict[str, str]) -> set[str]:
    """Changed, new or removed image files of a document.

    Args:
        old: ``assets`` from ``state.json`` (``None`` for entries without image tracking).
        new: Current ``assets``.

    Returns:
        Paths with a change (empty if ``old`` is missing).
    """
    changed: set[str] = set()
    if old is not None:
        changed = {p for p in set(old) | set(new) if old.get(p) != new.get(p)}
    return changed

# Main ************************************************************************
