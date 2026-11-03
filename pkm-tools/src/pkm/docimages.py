"""Bilder in Dokumenten schreiben und lesen (Spezifikation 4.9, 7.2, 7.3): Einsetzen neuer Bilder,
Ablage als Datei, Platzhalter in ``read`` und ``read_image``.

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

import hashlib
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from . import images
from .appendtext import count_overlapping
from .errors import PkmError
from .fsutil import write_bytes_atomic
from .paths import MAX_NAME, slugify

if TYPE_CHECKING:
    from .vault import Doc
    from .writer import Writer

# Variables *******************************************************************

ATTACHMENTS = "documents/_attachments"
AS_VALUES = ("auto", "image", "svg_text")
MIME = {"png": "png", "jpg": "jpeg", "gif": "gif", "webp": "webp"}

# Classes *********************************************************************

# Functions *******************************************************************


# Schreiben *******************************************************************
def has_image_markers(text: str) -> bool:
    """Prüfen, ob ein Text Platzhalter für neue Bilder enthält.

    Args:
        text: Neuer Text.

    Returns:
        ``True`` bei ``{{image:…}}``.
    """
    return bool(images.NEW_IMAGE_RE.search(text))


def place_images(
    writer: Writer, doc: Doc, text: str, specs: list[dict[str, Any]] | None
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Neue Bilder prüfen und an den Platzhaltern ``{{image:<name>}}`` einsetzen.

    Eingebettete Bilder werden Data-URIs, große bzw. ``mode: file`` werden Dateien in
    ``documents/_attachments/`` (in ``scratch/`` immer eingebettet).

    Args:
        writer: Writer (für Konfiguration, Vault und freie Dateinamen).
        doc: Dokument (vorher), bestimmt Ort und Bereich.
        text: Neuer Gesamttext mit Platzhaltern.
        specs: Bildangaben aus dem Werkzeugaufruf.

    Returns:
        Tupel aus (Text mit Bildern, neu geschriebene Bilddateien, Infos je Bild).

    Raises:
        PkmError: Fehler aus ``images.prepare_image`` und ``images.check_new_names``.
    """
    files: list[str] = []
    infos: list[dict[str, Any]] = []
    if specs or has_image_markers(text):
        prepared = [images.prepare_image(s, writer.cfg.images, scratch=not doc.versioned) for s in specs or []]
        images.check_new_names(text, prepared, images.find_images(doc.parsed.body if doc.parsed else ""))
        lines: dict[str, str] = {}
        try:
            for img in prepared:
                link = img.data_uri()
                if img.mode == "file":
                    rel = writer.free_name(ATTACHMENTS, slugify(img.name, MAX_NAME),
                                           f"_{writer.svc.now().date().isoformat()}", f".{img.fmt}")
                    write_bytes_atomic(writer.vault.path(rel), img.data)
                    files.append(rel)
                    link = images.relative_link(doc.rel, rel)
                lines[img.name] = img.markdown(link)
                infos.append({**img.info(), **({"path": files[-1]} if img.mode == "file" else {})})
        except PkmError:
            remove_files(writer, files)
            raise
        text = images.insert_new_images(text, lines)
    return text, files, infos


def remove_files(writer: Writer, files: list[str]) -> None:
    """Neu geschriebene Bilddateien wieder entfernen (nach einem Fehler).

    Args:
        writer: Writer.
        files: Relative Pfade.
    """
    for rel in files:
        writer.vault.path(rel).unlink(missing_ok=True)


def restore_body(old_body: str, new_body: str) -> str:
    """Platzhalter eingebetteter Bilder im neuen Body durch die Originale ersetzen.

    Args:
        old_body: Bisheriger Body.
        new_body: Neuer Body mit Platzhaltern.

    Returns:
        Body mit den ursprünglichen Bildern.
    """
    return images.restore_placeholders(new_body, images.find_images(old_body))


def removed_images(old_body: str, new_body: str) -> list[str]:
    """Bilder, die im neuen Body fehlen.

    Args:
        old_body: Bisheriger Body.
        new_body: Neuer Body (Originale bereits eingesetzt).

    Returns:
        Namen der entfernten Bilder.
    """
    new_keys = {r.link if r.inline else r.raw for r in images.find_images(new_body)}
    return [r.name for r in images.find_images(old_body) if (r.link if r.inline else r.raw) not in new_keys]


def edit_view(body: str, old: str, new: str) -> str:
    """``edit_document`` auf dem Text mit Platzhaltern ausführen und die Bilder wieder einsetzen.

    Args:
        body: Bisheriger Body.
        old: Textstelle (genau einmal in der Platzhalter-Ansicht).
        new: Ersatz.

    Returns:
        Neuer Body mit den ursprünglichen Bildern.

    Raises:
        PkmError: ``not_found`` oder ``ambiguous``.
    """
    view = images.to_placeholders(body)
    n = count_overlapping(view, old)
    if n == 0:
        raise PkmError("not_found", "Die Textstelle `old` kommt im Dokument nicht vor.")
    if n > 1:
        raise PkmError("ambiguous", f"Die Textstelle `old` kommt {n}-mal vor.", count=n)
    return restore_body(body, view.replace(old, new, 1))


# Lesen ***********************************************************************
def section_of(doc: Doc, text: str) -> Any:
    """Funktion Textposition → Abschnittsschlüssel für den Body eines Dokuments.

    Args:
        doc: Dokument.
        text: Body.

    Returns:
        Funktion, die zu einer Position den Schlüssel liefert (``None`` ohne Abschnitte).
    """
    sections = list(doc.parsed.sections) if doc.parsed is not None else []

    def lookup(pos: int) -> str | None:
        """Abschnitt zu einer Position.

        Args:
            pos: Zeichenposition im Body.

        Returns:
            Abschnittsschlüssel oder ``None``.
        """
        line = text.count("\n", 0, pos)
        return next((s.key for s in sections if s.start <= line < s.end), None)

    return lookup


def read_view(doc: Doc, text: str, section: str | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Text für ``read``: eingebettete Bilder als Platzhalter, dazu die Bildliste.

    Args:
        doc: Dokument.
        text: Gelesener Text (Body oder ein Abschnitt).
        section: Schlüssel, wenn nur ein Abschnitt gelesen wird.

    Returns:
        Tupel aus (Text mit Platzhaltern, Bildliste des Bodys bzw. des Abschnitts).
    """
    body = doc.body or ""
    listed = images.image_summary(body, section_of(doc, body))
    return images.to_placeholders(text), [i for i in listed if section is None or i.get("section") == section]


def _resolve_file(svc: Any, doc_rel: str, ref: images.ImageRef) -> str:
    """Bilddatei eines verlinkten Bildes im Vault finden.

    Args:
        svc: Dienst.
        doc_rel: Pfad des Dokuments.
        ref: Bild.

    Returns:
        Relativer Pfad der Datei.

    Raises:
        PkmError: ``not_found``.
    """
    target = images.link_target(ref, doc_rel) or ""
    if not svc.vault.exists(target) and "/" not in target:
        matches = [r for r in svc.vault.iter_files(("documents",)) if PurePosixPath(r).name == target]
        target = matches[0] if len(matches) == 1 else target
    if not svc.vault.exists(target):
        raise PkmError("not_found", f"Bilddatei nicht gefunden: {ref.link}", image=ref.name)
    return target


def image_payload(svc: Any, target: str, image: str | None = None, as_: str = "auto") -> dict[str, Any]:
    """Tool ``read_image``: Bild eines Dokuments bzw. eigenständige Bilddatei.

    Args:
        svc: Dienst.
        target: Dokument bzw. Bilddatei.
        image: Bildname (bei eigenständigen Bildern weglassen).
        as_: ``auto`` (PNG als Bild, SVG als Text), ``image`` oder ``svg_text``.

    Returns:
        Name, Alternativtext, Format, Größe, Hash und je nach Format ``svg`` (Text) oder ``data``
        (Bytes, vom MCP-Server als Bildinhalt geliefert).

    Raises:
        PkmError: ``not_found``, ``invalid_argument`` (z. B. Rastern von SVG ohne ``PKM_SVG_RASTER``).
    """
    if as_ not in AS_VALUES:
        raise PkmError("invalid_argument", f"as muss eines von {', '.join(AS_VALUES)} sein.")
    rel = svc.resolve(target)
    meta: dict[str, Any] = {"status": "ok", "path": rel}
    if image is None:
        data = svc.vault.path(rel).read_bytes()
        fmt = PurePosixPath(rel).suffix.lower().lstrip(".")
        meta.update(name=PurePosixPath(rel).stem, alt="", format={"jpeg": "jpg"}.get(fmt, fmt), mode="file")
    else:
        doc = svc.vault.load(rel)
        ref = next((r for r in images.find_images(doc.body or "") if r.name == image), None)
        if ref is None:
            raise PkmError("unknown_image", f"Bild nicht gefunden: {image}",
                           images=[r.name for r in images.find_images(doc.body or "")])
        data = ref.data() if ref.inline else svc.vault.path(_resolve_file(svc, rel, ref)).read_bytes()
        meta.update(name=ref.name, alt=ref.alt, format=ref.fmt, mode="inline" if ref.inline else "file")
    meta.update(size=len(data), hash=hashlib.sha256(data).hexdigest())
    if meta["format"] == "svg" and as_ != "image":
        meta["svg"] = data.decode("utf-8", "replace")
    elif meta["format"] == "svg":
        meta["data"], meta["format"] = rasterize_svg(data, svc.cfg.images.svg_raster), "png"
    else:
        meta["data"] = data
    return meta


def rasterize_svg(data: bytes, enabled: bool) -> bytes:
    """SVG rastern (nur mit ``PKM_SVG_RASTER`` und installierter Bibliothek).

    Args:
        data: SVG-Bytes.
        enabled: ``PKM_SVG_RASTER``.

    Returns:
        PNG-Bytes.

    Raises:
        PkmError: ``invalid_argument``, wenn das Rastern nicht eingeschaltet oder nicht verfügbar ist.
    """
    if not enabled:
        raise PkmError("invalid_argument", "SVG-Rasterung ist nicht eingeschaltet (PKM_SVG_RASTER); as=svg_text "
                       "verwenden.")
    try:
        import cairosvg  # type: ignore[import-not-found]  # pylint: disable=import-outside-toplevel,import-error
    except ImportError as exc:
        raise PkmError("invalid_argument", "Für PKM_SVG_RASTER fehlt die Bibliothek cairosvg.") from exc
    return cairosvg.svg2png(bytestring=data)

# Main ************************************************************************
