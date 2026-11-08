"""Lint checks for images (specification 4.9, 8).

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
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from . import docimages, imagefix, images
from .assets import AssetMap, known_assets
from .errors import PkmError
from .imagescan import non_image_data_links
from .state import load_state
from .vault import Doc

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

IMG_QUOTE_RE = re.compile(r"^\[img:(?P<name>[a-z0-9-]+)\]$")
GENERIC_ALT = {
    "image", "images", "img", "bild", "bilder", "picture", "pic", "photo", "foto", "figure", "fig", "abbildung",
    "abb", "grafik", "graphic", "graphics", "screenshot", "icon", "logo", "untitled", "alt", "alt text", "diagram",
    "diagramm", "chart",
}
GENERIC_ALT_RE = re.compile(r"^(?:img|image|bild|dsc|dcim|pxl|photo|foto|screenshot|pasted image|figure|fig|abb)"
                            r"[\s_.-]*\d[\w .-]*$|\.(?:png|jpe?g|gif|webp|svg)$", re.IGNORECASE)
LARGE_EMBEDDED_KB = 32
HASH_NAME_RE = re.compile(r"^[0-9a-f]{12,}$|^[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)

# Classes *********************************************************************

# Functions *******************************************************************


def is_generic_alt(alt: str) -> bool:
    """Check whether an alt text says nothing about the image (lint ``generic_alt_text``).

    Args:
        alt: Alt text (without ``|width``).

    Returns:
        ``True`` for words like "Image" or "Bild", file names and numbered names like ``IMG_068``.
    """
    text = " ".join(alt.split()).strip(" .:")
    return text.casefold() in GENERIC_ALT or bool(GENERIC_ALT_RE.search(text))


def generic_file_name(name: str) -> bool:
    """Check whether an image file name says nothing about the content (``IMG_013.png``, ``image.png``, hashes).

    Args:
        name: File name.

    Returns:
        ``True`` for generic names.
    """
    stem = PurePosixPath(name).stem
    return is_generic_alt(stem) or bool(HASH_NAME_RE.match(stem)) or bool(re.fullmatch(r"[\d\s_.-]+", stem))


def image_files(doc: Doc, amap: AssetMap | None) -> dict[str, tuple[str | None, images.ImageRef]]:
    """Image name → (path of the linked file or ``None`` for embedded images, image) of a document.

    Args:
        doc: Document.
        amap: Links of all documents (``None``: no files are resolved).

    Returns:
        Mapping in text order.
    """
    refs = images.find_images(doc.text or "")
    return {r.name: (None if r.inline or amap is None else amap.resolve(doc.rel, r), r) for r in refs}


def image_quote(quote: str | None) -> str | None:
    """Image name from an image quote ``[img:<name>]``.

    Args:
        quote: Quote of a citation.

    Returns:
        The image name or ``None`` if the quote is not an image reference.
    """
    m = IMG_QUOTE_RE.match((quote or "").strip())
    return m.group("name") if m else None


def has_image(text: str | None, name: str) -> bool:
    """Check whether a text contains an image with this name.

    Args:
        text: Section text of the cited version.
        name: Image name.

    Returns:
        ``True`` if the image exists.
    """
    return any(r.name == name for r in images.find_images(text or ""))


def _generic_alt_detail(doc: Doc, ref: images.ImageRef, amap: AssetMap | None, ctx: dict[str, Any]) -> dict[str, Any]:
    """Details of a ``generic_alt_text`` finding: file, section and whether the file keeps a generic name.

    Args:
        doc: Document.
        ref: Image with a generic alt text.
        amap: Links of all documents (``None`` for wiki pages without file resolution).
        ctx: ``section_of`` (position → section), ``named`` (files with a meaningful alt text in the document),
            ``referenced`` (file → documents).

    Returns:
        ``file`` (vault path, ``None`` when embedded), ``section``, ``file_keeps_generic_name`` (the file would
        be listed by ``move_images`` under ``generic_names_kept``) and ``name_from_other_link`` (another link of
        the document with a meaningful alt text names the file).
    """
    file = None if ref.inline or amap is None else amap.resolve(doc.rel, ref)
    detail: dict[str, Any] = {"file": file, "section": ctx["section_of"](ref.start)}
    if file is not None:
        only_here = ctx["referenced"].get(file) == [doc.rel]
        detail["name_from_other_link"] = file in ctx["named"]
        detail["file_keeps_generic_name"] = (generic_file_name(PurePosixPath(file).name) and only_here
                                             and file not in ctx["named"])
    return detail


def _content_hints(add: Any, doc: Doc, body: str, amap: AssetMap | None) -> None:
    """Hints ``generic_alt_text`` (with file and section) and ``large_embedded_image`` for a document.

    Args:
        add: ``Report.add``.
        doc: Document or wiki page.
        body: Body.
        amap: Links of all documents (``None``: files are not resolved).
    """
    all_refs = images.find_images(body)
    ctx = {"section_of": docimages.section_of(doc, body),
           "named": {amap.resolve(doc.rel, r) for r in all_refs if not r.inline and r.alt
                     and not is_generic_alt(r.alt)} if amap is not None else set(),
           "referenced": amap.referenced() if amap is not None else {}}
    for ref in all_refs:
        if ref.alt and is_generic_alt(ref.alt):
            detail = _generic_alt_detail(doc, ref, amap, ctx)
            add("generic_alt_text", "info", doc.rel, f"Image \"{ref.name}\" has a generic alt text \"{ref.alt}\"; "
                "propose a description of the image" + (" (alt_texts of move_images, key: file or image name)."
                                                        if detail["file"] else "."),
                image=ref.name, alt=ref.alt, **detail)
        size = len(ref.data()) if ref.inline and ref.fmt in imagefix.RASTER_FORMATS else 0
        if size > LARGE_EMBEDDED_KB * 1024:
            add("large_embedded_image", "info", doc.rel, f"Embedded image \"{ref.name}\" has {size // 1024} KB; "
                "propose fix_images with extract (stores it as a file, after confirmation).", image=ref.name,
                size_kb=size // 1024)


def _check_refs(add: Any, doc: Doc, limits: Any, amap: AssetMap | None = None) -> None:
    """Check the images of a Markdown document.

    Embedded images: nonconforming data URIs (``nonconforming_image`` with problem codes, 4.9) and other
    data URIs (``unsupported_type``). Linked files: duplicate names, missing alt text.

    Args:
        add: ``Report.add``.
        doc: Document or wiki page.
        limits: Image limits.
        amap: Links of all documents (to name the file of an image).
    """
    body = doc.body or ""
    refs = [r for r in images.find_images(body) if not r.inline]
    for name, n in Counter(r.name for r in refs if r.named).items():
        if n > 1:
            add("image_duplicate_name", "warning", doc.rel, f"Image name '{name}' occurs {n} times.", image=name)
    for ref in refs:
        if not ref.alt:
            add("image_without_alt", "info", doc.rel, f"Image \"{ref.name}\" without alt text.", image=ref.name)
    _content_hints(add, doc, body, amap)
    for issue in imagefix.image_issues(body, limits, wiki=doc.area == "wiki"):
        severe = {"svg_unsafe", "invalid_data"} & set(issue["problems"])
        add("nonconforming_image", "error" if severe else "warning", doc.rel,
            f"Image \"{issue['ref']}\" (line {issue['line']}) does not conform to 4.9: {', '.join(issue['problems'])}"
            + (". Fix after confirmation with pkm fix-images or fix_images." if issue["fixable"] else "."),
            image=issue["ref"], problems=issue["problems"], fixable=issue["fixable"])
    for pos, mime in non_image_data_links(body):
        line = body.count("\n", 0, pos) + 1
        add("unsupported_type", "warning", doc.rel,
            f"Data URI of type {mime} (line {line}) is neither displayed nor fixed.")


def check_images(add: Any, svc: Service, docs: list[Doc], pages: list[Doc]) -> None:
    """All image checks from 8 (``pkm lint``, images).

    Args:
        add: ``Report.add``.
        svc: Service.
        docs: Files from ``documents/``.
        pages: Wiki pages.
    """
    amap = AssetMap(svc, docs)
    for doc in [*docs, *pages]:
        if doc.kind == "md" and doc.parsed is not None and not doc.error:
            _check_refs(add, doc, svc.cfg.images, amap if doc.rel.startswith("documents/") else None)
        elif doc.kind == "bin" and doc.rel.lower().endswith(".svg"):
            problems = images.svg_problems(svc.vault.path(doc.rel).read_text(encoding="utf-8", errors="replace"))
            if problems:
                add("svg_unsafe", "error", doc.rel, f"SVG file not sanitized: {', '.join(problems)}.")
    try:
        entries = load_state(svc.cfg)["documents"]
    except PkmError:
        entries = {}
    for rel in amap.orphans(known_assets(entries)):
        add("orphaned_attachment", "info", rel, "Orphaned attachment: no document links to this image file.")
    referenced = amap.referenced()
    by_hash: dict[str, list[str]] = {}
    for doc in docs:
        if doc.kind == "bin" and doc.bin_hash and doc.rel.lower().endswith(images.IMAGE_EXTENSIONS):
            by_hash.setdefault(doc.bin_hash, []).append(doc.rel)
    for paths in by_hash.values():
        if len(paths) > 1:
            paths = sorted(paths)
            add("duplicate_image", "info", paths[0], f"The same image is stored {len(paths)} times: "
                + ", ".join(paths) + ". Propose to link one file and delete the others.", paths=paths,
                linked_by={p: referenced.get(p, []) for p in paths})

# Main ************************************************************************
