"""Zugehörige Bilddateien von Dokumenten (Spezifikation 4.9): Verweise, Hashes, verwaiste Anhänge.

Eine Bilddatei, auf die ein Markdown-Dokument in ``documents/`` verweist, gehört zu diesem Dokument:
Sie ist kein eigenständiges Dokument, ihre Änderung ist eine Änderung des Dokuments.

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

from . import hashes, images
from .vault import Doc

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

ATTACHMENTS_PREFIX = "documents/_attachments/"
IMAGE_SUFFIXES = (".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp")

# Classes *********************************************************************


class AssetMap:
    """Verweise aller Markdown-Dokumente in ``documents/`` auf Bilddateien."""

    def __init__(self, svc: Service, docs: list[Doc]) -> None:
        """Verweise einsammeln.

        Args:
            svc: Dienst.
            docs: Dokumente aus ``documents/`` (Markdown und Anhänge).
        """
        self.svc = svc
        files = [d.rel for d in docs if d.kind == "bin"]
        self._by_name: dict[str, list[str]] = {}
        for rel in files:
            self._by_name.setdefault(PurePosixPath(rel).name.casefold(), []).append(rel)
        self._files = set(files)
        self.links: dict[str, dict[str, list[str]]] = {}
        for doc in docs:
            if doc.kind == "md" and doc.parsed is not None and not doc.error:
                self.links[doc.rel] = self._doc_links(doc)

    def _resolve(self, doc_rel: str, ref: images.ImageRef) -> str | None:
        """Pfad der Bilddatei eines verlinkten Bildes.

        Args:
            doc_rel: Pfad des Dokuments.
            ref: Bild.

        Returns:
            Vorhandener Pfad oder ``None``.
        """
        target = images.link_target(ref, doc_rel)
        found = target if target in self._files else None
        if found is None and target and "/" not in target:
            matches = self._by_name.get(target.casefold(), [])
            found = matches[0] if len(matches) == 1 else None
        return found

    def _doc_links(self, doc: Doc) -> dict[str, list[str]]:
        """Bilddateien eines Dokuments mit den Abschnitten, in denen sie stehen.

        Args:
            doc: Dokument.

        Returns:
            Pfad → Abschnittsschlüssel.
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

    def referenced(self) -> dict[str, list[str]]:
        """Bilddateien mit den Dokumenten, die sie verwenden.

        Returns:
            Pfad der Datei → Pfade der Dokumente.
        """
        out: dict[str, list[str]] = {}
        for doc_rel, links in self.links.items():
            for path in links:
                out.setdefault(path, []).append(doc_rel)
        return out

    def assets(self, doc_rel: str) -> dict[str, str]:
        """Verlinkte Bilddateien eines Dokuments mit ihrem Hash (für ``state.json``).

        Args:
            doc_rel: Pfad des Dokuments.

        Returns:
            Pfad → SHA-256.
        """
        return {p: hashes.sha256_bytes(self.svc.vault.path(p).read_bytes())
                for p in sorted(self.links.get(doc_rel, {}))}

    def sections_for(self, doc_rel: str, paths: set[str]) -> list[str]:
        """Abschnitte eines Dokuments, die eine der Dateien zeigen.

        Args:
            doc_rel: Pfad des Dokuments.
            paths: Bilddateien.

        Returns:
            Abschnittsschlüssel ohne Duplikate.
        """
        links = self.links.get(doc_rel, {})
        return list(dict.fromkeys(k for p in sorted(paths) for k in links.get(p, [])))

    def orphans(self, known: set[str]) -> list[str]:
        """Verwaiste Anhänge: Bilddateien ohne Verweis, die früher zugehörig waren oder in ``_attachments/`` liegen.

        Args:
            known: Pfade, die in ``state.json`` als ``assets`` geführt sind.

        Returns:
            Sortierte Pfade.
        """
        used = set(self.referenced())
        return sorted(p for p in self._files if p not in used and p.lower().endswith(IMAGE_SUFFIXES)
                      and (p in known or p.startswith(ATTACHMENTS_PREFIX)))

# Functions *******************************************************************


def known_assets(entries: dict[str, Any]) -> set[str]:
    """Alle Bilddateien, die in ``state.json`` als zugehörig geführt sind.

    Args:
        entries: ``documents`` aus ``state.json``.

    Returns:
        Pfade.
    """
    return {p for e in entries.values() for p in (e.get("assets") or {})}


def asset_changes(old: dict[str, str] | None, new: dict[str, str]) -> set[str]:
    """Geänderte, neue oder entfernte zugehörige Bilddateien.

    Args:
        old: ``assets`` aus ``state.json`` (``None`` bei Einträgen ohne Bildverfolgung).
        new: Aktuelle ``assets``.

    Returns:
        Pfade mit Änderung (leer, wenn ``old`` fehlt).
    """
    changed: set[str] = set()
    if old is not None:
        changed = {p for p in set(old) | set(new) if old.get(p) != new.get(p)}
    return changed

# Main ************************************************************************
