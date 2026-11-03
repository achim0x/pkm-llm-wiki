"""Lint-Prüfungen für Bilder (Spezifikation 4.9, 8).

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
from collections import Counter
from typing import TYPE_CHECKING, Any

from . import imagefix, images
from .assets import AssetMap, known_assets
from .errors import PkmError
from .imagescan import non_image_data_links
from .state import load_state
from .vault import Doc

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

IMG_QUOTE_RE = re.compile(r"^\[img:(?P<name>[a-z0-9-]+)\]$")

# Classes *********************************************************************

# Functions *******************************************************************


def image_quote(quote: str | None) -> str | None:
    """Bildname aus einem Bild-Zitat ``[img:<name>]``.

    Args:
        quote: Zitat eines Belegs.

    Returns:
        Der Bildname oder ``None``, wenn das Zitat kein Bildverweis ist.
    """
    m = IMG_QUOTE_RE.match((quote or "").strip())
    return m.group("name") if m else None


def has_image(text: str | None, name: str) -> bool:
    """Prüfen, ob ein Text ein Bild mit diesem Namen enthält.

    Args:
        text: Abschnittstext der belegten Version.
        name: Bildname.

    Returns:
        ``True``, wenn es das Bild gibt.
    """
    return any(r.name == name for r in images.find_images(text or ""))


def _check_refs(add: Any, doc: Doc, limits: Any) -> None:
    """Bilder eines Markdown-Dokuments prüfen.

    Eingebettete Bilder: abweichende Data-URIs (``nonconforming_image`` mit Befundcodes, 4.9) und andere
    Data-URIs (``unsupported_type``). Verlinkte Dateien: doppelte Namen, fehlender Alternativtext.

    Args:
        add: ``Report.add``.
        doc: Dokument oder Wiki-Seite.
        limits: Bildgrenzen.
    """
    body = doc.body or ""
    refs = [r for r in images.find_images(body) if not r.inline]
    for name, n in Counter(r.name for r in refs if r.named).items():
        if n > 1:
            add("image_duplicate_name", "warning", doc.rel, f"Bildname „{name}“ kommt {n}-mal vor.", image=name)
    for ref in refs:
        if not ref.alt:
            add("image_without_alt", "info", doc.rel, f"Bild „{ref.name}“ ohne Alternativtext.", image=ref.name)
    for issue in imagefix.image_issues(body, limits, wiki=doc.area == "wiki"):
        severe = {"svg_unsafe", "invalid_data"} & set(issue["problems"])
        add("nonconforming_image", "error" if severe else "warning", doc.rel,
            f"Bild „{issue['ref']}“ (Zeile {issue['line']}) entspricht nicht 4.9: {', '.join(issue['problems'])}"
            + (". Korrektur nach Bestätigung mit pkm fix-images bzw. fix_images." if issue["fixable"] else "."),
            image=issue["ref"], problems=issue["problems"], fixable=issue["fixable"])
    for pos, mime in non_image_data_links(body):
        line = body.count("\n", 0, pos) + 1
        add("unsupported_type", "warning", doc.rel,
            f"Data-URI vom Typ {mime} (Zeile {line}) wird weder dargestellt noch korrigiert.")


def check_images(add: Any, svc: Service, docs: list[Doc], pages: list[Doc]) -> None:
    """Alle Bildprüfungen aus 8 (``pkm lint``, Bilder).

    Args:
        add: ``Report.add``.
        svc: Dienst.
        docs: Dateien aus ``documents/``.
        pages: Wiki-Seiten.
    """
    for doc in [*docs, *pages]:
        if doc.kind == "md" and doc.parsed is not None and not doc.error:
            _check_refs(add, doc, svc.cfg.images)
        elif doc.kind == "bin" and doc.rel.lower().endswith(".svg"):
            problems = images.svg_problems(svc.vault.path(doc.rel).read_text(encoding="utf-8", errors="replace"))
            if problems:
                add("svg_unsafe", "error", doc.rel, f"SVG-Datei nicht bereinigt: {', '.join(problems)}.")
    try:
        entries = load_state(svc.cfg)["documents"]
    except PkmError:
        entries = {}
    for rel in AssetMap(svc, docs).orphans(known_assets(entries)):
        add("orphaned_attachment", "info", rel, "Verwaister Anhang: kein Dokument verweist auf diese Bilddatei.")

# Main ************************************************************************
