"""Bilder in Dokumenten (Spezifikation 4.9): erkennen, prüfen, bereinigen, kodieren, Platzhalter.

PNG und SVG. Kleine Bilder werden als Data-URI eingebettet (PNG Base64, SVG URL-kodiert), größere als
Datei abgelegt. Base64 gelangt nie in den Kontext des Modells: ``read`` zeigt Platzhalter, die beim
Schreiben byte-genau zurückübersetzt werden.

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

import base64
import binascii
import hashlib
import posixpath
import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, unquote

from .errors import PkmError
from .paths import slugify

# Variables *******************************************************************

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_TEXT_CHUNKS = (b"tEXt", b"iTXt", b"zTXt")
PNG_MAX_PIXELS = 8000
IMAGE_EXTENSIONS = (".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp")
NEW_FORMATS = ("png", "svg", "jpg")
IMPORT_SUFFIXES = {".png": "png", ".svg": "svg", ".jpg": "jpg", ".jpeg": "jpg"}
JPEG_SOI = b"\xff\xd8"
JPEG_DROP = (0xE1, 0xED, 0xFE)  # EXIF/XMP, Photoshop/IPTC, Kommentar
JPEG_SOF = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
EXIF_ORIENTATION = 0x0112
MODES = ("auto", "inline", "file")
PLACEHOLDER_SCHEME = "pkm-image:"
MD_IMAGE_RE = re.compile(r'!\[(?P<alt>[^\]\n]*)\]\((?P<url>[^\s)]+)(?:[ \t]+"(?P<title>[^"\n]*)")?\)')
WIKI_IMAGE_RE = re.compile(
    r"!\[\[(?P<path>[^\]|#\n]+?\.(?:png|svg|jpe?g|gif|webp))(?:\|(?P<opt>[^\]\n]*))?\]\]", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r'!\[[^\]\n]*\]\(pkm-image:(?P<name>[a-z0-9-]+)(?:[ \t]+"[^"\n]*")?\)')
NEW_IMAGE_RE = re.compile(r"\{\{image:(?P<name>[^}\s]+)\}\}")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SVG_FORBIDDEN = (
    (re.compile(r"<!DOCTYPE|<!ENTITY", re.IGNORECASE), "DOCTYPE/Entities"),
    (re.compile(r"<\?xml-stylesheet", re.IGNORECASE), "xml-stylesheet"),
    (re.compile(r"<(?:[\w-]+:)?script\b", re.IGNORECASE), "<script>"),
    (re.compile(r"<(?:[\w-]+:)?foreignObject\b", re.IGNORECASE), "<foreignObject>"),
    (re.compile(r"""\son[a-z]+\s*=""", re.IGNORECASE), "Ereignis-Attribut"),
    (re.compile(r"""(?:xlink:)?href\s*=\s*["'](?!#)""", re.IGNORECASE), "externer Verweis"),
    (re.compile(r"url\(\s*['\"]?(?!#)[a-z]+:", re.IGNORECASE), "externer Verweis in CSS"),
    (re.compile(r"data:image/(?!svg)", re.IGNORECASE), "eingebettete Rastergrafik"),
)
URL_UNSAFE = set('%#<>" \n\r\t()[]{}|\\^`')
DROP_ELEMENTS = ("script", "foreignObject", "metadata")

# Classes *********************************************************************


@dataclass
class ImageRef:  # pylint: disable=too-many-instance-attributes
    """Ein Bild im Text eines Dokuments.

    Attributes:
        name: Bildname (``pkm:<name>`` oder abgeleitet).
        alt: Alternativtext (ohne ``|breite``).
        raw: Exakter Markdown-Text des Bildes.
        start: Startposition im Text.
        end: Endposition im Text.
        inline: Eingebettet (Data-URI) statt Datei.
        fmt: Format (``png``, ``svg``, ``jpg`` …).
        link: Verweis wie geschrieben (Data-URI bzw. Pfad).
        named: Ob der Name als ``pkm:<name>`` im Text steht.
    """

    name: str
    alt: str
    raw: str
    start: int
    end: int
    inline: bool
    fmt: str
    link: str
    named: bool

    def data(self) -> bytes:
        """Inhalt eines eingebetteten Bildes.

        Returns:
            Dekodierte Bytes (leer bei Dateien oder unlesbaren Data-URIs).
        """
        return decode_data_uri(self.link)[1] if self.inline else b""


@dataclass
class PreparedImage:
    """Ein neues Bild, geprüft und kodiert, bereit zum Einsetzen.

    Attributes:
        name: Bildname.
        alt: Alternativtext.
        fmt: ``png`` oder ``svg``.
        data: Bereinigte Bytes.
        mode: ``inline`` oder ``file``.
    """

    name: str
    alt: str
    fmt: str
    data: bytes
    mode: str

    def markdown(self, link: str) -> str:
        """Markdown-Zeile des Bildes.

        Args:
            link: Data-URI oder relativer Pfad zur Datei.

        Returns:
            ``![alt](link "pkm:name")``.
        """
        return f'![{self.alt}]({link} "pkm:{self.name}")'

    def data_uri(self) -> str:
        """Bild als Data-URI.

        Returns:
            PNG als Base64-, SVG als URL-kodierte Data-URI.
        """
        uri = svg_data_uri(self.data.decode("utf-8")) if self.fmt == "svg" else png_data_uri(self.data)
        return uri.replace("data:image/png;", "data:image/jpeg;", 1) if self.fmt == "jpg" else uri

    def info(self) -> dict[str, Any]:
        """Kurzinfo für Rückgaben.

        Returns:
            Name, Format, Modus, Größe in Bytes und Hash.
        """
        return {"name": self.name, "format": self.fmt, "mode": self.mode, "size": len(self.data),
                "hash": hashlib.sha256(self.data).hexdigest()}

# Functions *******************************************************************


# Erkennen ********************************************************************
def find_images(text: str) -> list[ImageRef]:
    """Bilder im Text finden: Markdown-Bilder (Data-URI oder Datei) und Obsidian-Einbettungen.

    Bilder mit ``http(s):``-Adresse zählen nicht. Bilder ohne ``pkm:``-Namen bekommen einen
    abgeleiteten Namen (Alternativtext, sonst ``bild-<n>``), der nicht in die Datei geschrieben wird.

    Args:
        text: Markdown (Body oder Abschnitt).

    Returns:
        Bilder in Textreihenfolge.
    """
    found: list[tuple[int, int, str, str, str | None]] = []
    for m in MD_IMAGE_RE.finditer(text):
        url = m.group("url")
        if url.startswith("data:image/") or PurePosixPath(unquote(url).lower()).suffix in IMAGE_EXTENSIONS:
            if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.IGNORECASE) and not url.startswith(PLACEHOLDER_SCHEME):
                found.append((m.start(), m.end(), m.group("alt"), url, m.group("title")))
    for m in WIKI_IMAGE_RE.finditer(text):
        found.append((m.start(), m.end(), m.group("opt") or "", m.group("path"), None))
    refs: list[ImageRef] = []
    used: set[str] = set()
    for n, (start, end, alt, url, title) in enumerate(sorted(found), start=1):
        named = bool(title and title.startswith("pkm:") and NAME_RE.match(title[4:]))
        name = title[4:] if named and title else _derived_name(alt, n, used)
        used.add(name)
        inline = url.startswith("data:image/")
        fmt = _format_of(url)
        refs.append(ImageRef(name, alt.split("|", 1)[0].strip(), text[start:end], start, end, inline, fmt, url, named))
    return refs


def _derived_name(alt: str, n: int, used: set[str]) -> str:
    """Bildnamen ableiten (aus dem Alternativtext, sonst ``bild-<n>``), eindeutig im Dokument.

    Args:
        alt: Alternativtext (ggf. mit ``|breite``).
        n: Position des Bildes im Dokument.
        used: Bereits vergebene Namen.

    Returns:
        Der Name.
    """
    base = alt.split("|", 1)[0].strip()
    name = slugify(base, 60) if base and not base.isdigit() else f"bild-{n}"
    candidate, k = name, 1
    while candidate in used:
        k += 1
        candidate = f"{name}-{k}"
    return candidate


def _format_of(url: str) -> str:
    """Format eines Bildverweises.

    Args:
        url: Data-URI oder Pfad.

    Returns:
        ``png``, ``svg``, ``jpg`` … (leer, wenn unbekannt).
    """
    m = re.match(r"data:image/([a-z0-9.+-]+)", url, re.IGNORECASE)
    fmt = m.group(1).lower() if m else PurePosixPath(unquote(url).lower()).suffix.lstrip(".")
    return {"svg+xml": "svg", "jpeg": "jpg"}.get(fmt, fmt)


def link_target(ref: ImageRef, doc_rel: str) -> str | None:
    """Vault-Pfad einer verlinkten Bilddatei (Markdown-Link relativ zum Dokument).

    Args:
        ref: Bild.
        doc_rel: Pfad des Dokuments im Vault.

    Returns:
        Pfad im Vault; ``None`` bei eingebetteten Bildern. Obsidian-Einbettungen ohne Ordner liefern
        den Namen wie geschrieben (Auflösung über den Dateibestand).
    """
    target = None
    if not ref.inline:
        link = unquote(ref.link.strip("<>"))
        if ref.raw.startswith("![["):
            target = link.lstrip("/")
        elif link.startswith("/"):
            target = link.lstrip("/")
        else:
            target = posixpath.normpath(posixpath.join(posixpath.dirname(doc_rel), link))
    return target


def relative_link(doc_rel: str, file_rel: str) -> str:
    """Markdown-Link vom Dokument auf eine Datei im Vault.

    Args:
        doc_rel: Pfad des Dokuments.
        file_rel: Pfad der Datei.

    Returns:
        Relativer Pfad, z. B. ``../_attachments/foto_2026-11-03.png`` (Leerzeichen kodiert).
    """
    rel = posixpath.relpath(file_rel, posixpath.dirname(doc_rel) or ".")
    return quote(rel, safe="/._-~")


def strip_images(text: str) -> str:
    """Bilder durch ihren Alternativtext ersetzen (für Suche und Index; nie Base64 oder SVG-Inhalt).

    Args:
        text: Markdown.

    Returns:
        Text, in dem jedes Bild nur noch als Alternativtext steht.
    """
    out, pos = [], 0
    for ref in find_images(text):
        out += [text[pos:ref.start], ref.alt]
        pos = ref.end
    return "".join(out) + text[pos:]


# Platzhalter *****************************************************************
def human_size(size: int) -> str:
    """Größe für Platzhalter.

    Args:
        size: Bytes.

    Returns:
        Z. B. ``3,2 KB`` oder ``812 B``.
    """
    return f"{size} B" if size < 1024 else f"{size / 1024:.1f} KB".replace(".", ",")


def placeholder(ref: ImageRef) -> str:
    """Platzhalter für ein eingebettetes Bild.

    Args:
        ref: Bild.

    Returns:
        Z. B. ``![Schaltplan](pkm-image:schaltplan "svg, 3,2 KB, sha:ab12cd")``.
    """
    data = ref.data()
    sha = hashlib.sha256(data).hexdigest()[:6]
    alt = ref.raw[2:ref.raw.index("](")] if "](" in ref.raw else ref.alt
    return f'![{alt}]({PLACEHOLDER_SCHEME}{ref.name} "{ref.fmt}, {human_size(len(data))}, sha:{sha}")'


def to_placeholders(text: str) -> str:
    """Eingebettete Bilder durch Platzhalter ersetzen (für ``read``).

    Args:
        text: Markdown.

    Returns:
        Text ohne Data-URIs.
    """
    out, pos = [], 0
    for ref in find_images(text):
        if ref.inline:
            out += [text[pos:ref.start], placeholder(ref)]
            pos = ref.end
    return "".join(out) + text[pos:]


def restore_placeholders(text: str, refs: list[ImageRef]) -> str:
    """Platzhalter byte-genau durch die Originale ersetzen (für ``rewrite_document``/``edit_document``).

    Args:
        text: Neuer Text mit Platzhaltern.
        refs: Bilder des bisherigen Dokuments.

    Returns:
        Text mit den ursprünglichen Bildern.

    Raises:
        PkmError: ``unknown_image`` bei Platzhaltern ohne Bild.
    """
    by_name = {r.name: r for r in refs if r.inline}
    unknown = sorted({m.group("name") for m in PLACEHOLDER_RE.finditer(text)} - set(by_name))
    if unknown:
        raise PkmError("unknown_image", "Unbekannte Bild-Platzhalter: " + ", ".join(unknown), images=unknown)
    return PLACEHOLDER_RE.sub(lambda m: by_name[m.group("name")].raw, text)


def image_summary(text: str, section_of: Any = None) -> list[dict[str, Any]]:
    """Liste der Bilder für ``read``.

    Args:
        text: Markdown.
        section_of: Funktion Position → Abschnittsschlüssel (optional).

    Returns:
        Je Bild Name, Alternativtext, Format, ``inline``/``file``, Größe, Hash (bei eingebetteten),
        Verweis (bei Dateien) und Abschnitt.
    """
    result = []
    for ref in find_images(text):
        entry: dict[str, Any] = {"name": ref.name, "alt": ref.alt, "format": ref.fmt,
                                 "mode": "inline" if ref.inline else "file"}
        if ref.inline:
            data = ref.data()
            entry.update(size=len(data), hash=hashlib.sha256(data).hexdigest())
        else:
            entry["link"] = ref.link
        if section_of is not None:
            entry["section"] = section_of(ref.start)
        result.append(entry)
    return result


# Kodierung *******************************************************************
def decode_data_uri(url: str) -> tuple[str, bytes]:
    """Data-URI dekodieren.

    Args:
        url: ``data:image/…``.

    Returns:
        Tupel aus (Format, Bytes); Bytes leer, wenn nicht dekodierbar.
    """
    head, _, payload = url.partition(",")
    data = b""
    try:
        data = base64.b64decode(payload, validate=False) if head.endswith(";base64") else unquote(payload).encode(
            "utf-8")
    except (binascii.Error, ValueError):
        data = b""
    return _format_of(url), data


def png_data_uri(data: bytes) -> str:
    """PNG als Base64-Data-URI.

    Args:
        data: PNG-Bytes.

    Returns:
        ``data:image/png;base64,…`` ohne Zeilenumbrüche.
    """
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def svg_data_uri(svg: str) -> str:
    """SVG als URL-kodierte Data-URI (4.9): doppelte Anführungszeichen in Attributen werden einfache.

    Args:
        svg: Bereinigtes, verkleinertes SVG.

    Returns:
        ``data:image/svg+xml,…``.
    """
    single = re.sub(r'(\s[\w:.-]+)="([^"]*)"', lambda m: f"{m.group(1)}='{m.group(2).replace(chr(39), '&apos;')}'",
                    svg)
    return "data:image/svg+xml," + "".join(f"%{ord(ch):02X}" if ch in URL_UNSAFE else ch for ch in single)


def svg_problems(svg: str) -> list[str]:
    """Unsichere Bestandteile eines SVG finden (4.9, Sicherheit).

    Args:
        svg: SVG-Text.

    Returns:
        Beschreibungen der Funde (leer, wenn sauber).
    """
    return [label for rx, label in SVG_FORBIDDEN if rx.search(svg)]


def _local(tag: str) -> str:
    """Lokalen Namen eines Elements oder Attributs ohne Namensraum.

    Args:
        tag: ``{ns}name`` oder ``name``.

    Returns:
        ``name``.
    """
    return tag.rsplit("}", 1)[-1]


def _clean_tree(root: ET.Element) -> None:
    """Unsichere Elemente und Attribute entfernen (rekursiv).

    Args:
        root: SVG-Wurzel.

    Raises:
        PkmError: ``svg_too_complex`` bei eingebetteten Rastergrafiken.
    """
    for parent in list(root.iter()):
        for child in list(parent):
            href = child.get(f"{{{XLINK_NS}}}href") or child.get("href") or ""
            if _local(child.tag) == "image" and href.startswith("data:") and "svg" not in href[:20]:
                raise PkmError("svg_too_complex", "Das SVG enthält eingebettete Rastergrafiken; dafür PNG verwenden.")
            if _local(child.tag) in DROP_ELEMENTS or (_local(child.tag) == "style" and svg_problems(child.text or "")):
                parent.remove(child)
        for key in list(parent.attrib):
            value = parent.attrib[key]
            name = _local(key).lower()
            if name.startswith("on") or (name == "href" and not value.startswith("#")) or svg_problems(
                    f" x='{value}'" if "url(" in value else ""):
                del parent.attrib[key]


def sanitize_svg(svg: str, max_kb: int) -> str:
    """SVG bereinigen und verkleinern (4.9).

    Args:
        svg: SVG-Text.
        max_kb: Komplexitätsgrenze nach der Bereinigung.

    Returns:
        Bereinigtes SVG ohne Kommentare, Metadaten und überflüssigen Leerraum.

    Raises:
        PkmError: ``invalid_image`` bei DOCTYPE/Entities oder ungültigem XML, ``svg_too_complex`` bei
            Rastergrafiken oder Überschreiten der Grenze.
    """
    if re.search(r"<!DOCTYPE|<!ENTITY", svg, re.IGNORECASE):
        raise PkmError("invalid_image", "SVG mit DOCTYPE oder Entities wird nicht angenommen (XXE-Schutz).")
    text = re.sub(r"<\?xml[^>]*\?>", "", svg).strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise PkmError("invalid_image", f"Kein gültiges SVG: {exc}") from exc
    if _local(root.tag) != "svg":
        raise PkmError("invalid_image", "Die Wurzel ist kein <svg>-Element.")
    _clean_tree(root)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    out = ET.tostring(root, encoding="unicode")
    out = re.sub(r">\s+<", "><", re.sub(r"\s+", " ", out)).strip()
    problems = svg_problems(out)
    if problems:
        raise PkmError("invalid_image", "SVG nicht bereinigbar: " + ", ".join(problems))
    if len(out.encode("utf-8")) > max_kb * 1024:
        raise PkmError("svg_too_complex", f"Das SVG ist größer als {max_kb} KB; dafür PNG verwenden.")
    return out


def clean_png(data: bytes) -> bytes:
    """Neues PNG prüfen und Textblöcke entfernen (4.9).

    Args:
        data: PNG-Bytes.

    Returns:
        PNG ohne ``tEXt``/``iTXt``/``zTXt``.

    Raises:
        PkmError: ``invalid_image`` bei ungültiger Signatur, Struktur oder mehr als 8.000 × 8.000 Pixeln.
    """
    if not data.startswith(PNG_SIGNATURE):
        raise PkmError("invalid_image", "Keine PNG-Datei (Signatur fehlt).")
    pos, chunks, width, height, ended = len(PNG_SIGNATURE), [PNG_SIGNATURE], 0, 0, False
    while pos + 12 <= len(data) and not ended:
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos:pos + 12 + length]
        if len(chunk) != 12 + length:
            break
        if kind == b"IHDR":
            width, height = struct.unpack(">II", chunk[8:16])
        ended = kind == b"IEND"
        if kind not in PNG_TEXT_CHUNKS:
            chunks.append(chunk)
        pos += 12 + length
    if not ended or not width or not height:
        raise PkmError("invalid_image", "PNG ist unvollständig oder beschädigt.")
    if width > PNG_MAX_PIXELS or height > PNG_MAX_PIXELS:
        raise PkmError("invalid_image", f"PNG ist größer als {PNG_MAX_PIXELS} × {PNG_MAX_PIXELS} Pixel.")
    return b"".join(chunks)


def _exif_orientation(tiff: bytes) -> int | None:
    """Ausrichtung (Tag 0x0112) aus einem EXIF-TIFF-Block lesen.

    Args:
        tiff: Inhalt des EXIF-Blocks nach ``Exif\\0\\0``.

    Returns:
        Wert 1–8 oder ``None``.
    """
    value = None
    try:
        endian = {b"II": "<", b"MM": ">"}[tiff[:2]]
        ifd = struct.unpack(endian + "I", tiff[4:8])[0]
        count = struct.unpack(endian + "H", tiff[ifd:ifd + 2])[0]
        for i in range(count):
            entry = tiff[ifd + 2 + 12 * i: ifd + 14 + 12 * i]
            if struct.unpack(endian + "H", entry[:2])[0] == EXIF_ORIENTATION:
                value = struct.unpack(endian + "H", entry[8:10])[0]
    except (KeyError, struct.error):
        value = None
    return value if value in range(1, 9) else None


def _orientation_segment(orientation: int) -> bytes:
    """Minimalen EXIF-Block erzeugen, der nur die Ausrichtung enthält.

    Args:
        orientation: Wert 2–8.

    Returns:
        APP1-Segment.
    """
    tiff = (b"MM\x00\x2a" + struct.pack(">I", 8) + struct.pack(">H", 1)
            + struct.pack(">HHIHH", EXIF_ORIENTATION, 3, 1, orientation, 0) + struct.pack(">I", 0))
    payload = b"Exif\x00\x00" + tiff
    return b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload


def clean_jpeg(data: bytes) -> bytes:
    """Neues JPEG prüfen und Metadaten entfernen (EXIF/XMP, IPTC, Kommentare); die Ausrichtung bleibt.

    Args:
        data: JPEG-Bytes.

    Returns:
        JPEG ohne Metadaten, bei gedrehten Fotos mit einem EXIF-Block nur für die Ausrichtung.

    Raises:
        PkmError: ``invalid_image`` bei ungültiger Struktur oder mehr als 8.000 × 8.000 Pixeln.
    """
    if not data.startswith(JPEG_SOI):
        raise PkmError("invalid_image", "Keine JPEG-Datei (Signatur fehlt).")
    pos, segments, size, orientation, scan = 2, [JPEG_SOI], (0, 0), None, False
    while pos + 4 <= len(data) and not scan and data[pos] == 0xFF:
        marker = data[pos + 1]
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        segment = data[pos:pos + 2 + length]
        if marker in JPEG_SOF and len(segment) >= 9:
            size = struct.unpack(">HH", segment[5:9])
        if marker == 0xE1 and segment[4:10] == b"Exif\x00\x00":
            orientation = _exif_orientation(segment[10:]) or orientation
        scan = marker == 0xDA
        if scan:
            segments.append(data[pos:])
        elif marker not in JPEG_DROP:
            segments.append(segment)
        pos += 2 + length
    if not scan or not all(size):
        raise PkmError("invalid_image", "JPEG ist unvollständig oder beschädigt.")
    if max(size) > PNG_MAX_PIXELS:
        raise PkmError("invalid_image", f"JPEG ist größer als {PNG_MAX_PIXELS} × {PNG_MAX_PIXELS} Pixel.")
    if orientation and orientation != 1:
        at = 2 if len(segments) > 1 and segments[1][:2] == b"\xff\xe0" else 1
        segments.insert(at, _orientation_segment(orientation))
    return b"".join(segments)


# Neue Bilder *****************************************************************
def _source_bytes(spec: dict[str, Any], limits: Any) -> tuple[str, bytes]:
    """Quelle eines neuen Bildes lesen (genau eine von ``svg``, ``png_base64``, ``import_path``).

    Args:
        spec: Bildangabe aus dem Werkzeugaufruf.
        limits: ``ImageConfig``.

    Returns:
        Tupel aus (Format, Bytes).

    Raises:
        PkmError: ``invalid_argument``, ``too_large`` oder ``forbidden`` (Pfad außerhalb von
            ``PKM_IMPORT_DIR``).
    """
    given = [k for k in ("svg", "png_base64", "import_path") if spec.get(k)]
    if len(given) != 1:
        raise PkmError("invalid_argument", "Je Bild genau eine Quelle: svg, png_base64 oder import_path.")
    if given[0] == "svg":
        result = ("svg", str(spec["svg"]).encode("utf-8"))
    elif given[0] == "png_base64":
        b64 = re.sub(r"\s+", "", str(spec["png_base64"]))
        if len(b64) > limits.param_max_kb * 1024:
            raise PkmError("too_large", f"png_base64 ist größer als {limits.param_max_kb} KB; import_path verwenden.")
        try:
            result = ("png", base64.b64decode(b64, validate=True))
        except (binascii.Error, ValueError) as exc:
            raise PkmError("invalid_image", "png_base64 ist kein gültiges Base64.") from exc
    else:
        result = _import_file(str(spec["import_path"]), limits)
    return result


def _import_file(path: str, limits: Any) -> tuple[str, bytes]:
    """Bilddatei aus ``PKM_IMPORT_DIR`` lesen (kopieren, nie löschen).

    Args:
        path: Dateiname oder Pfad.
        limits: ``ImageConfig``.

    Returns:
        Tupel aus (Format, Bytes).

    Raises:
        PkmError: ``forbidden`` außerhalb des Importordners, ``invalid_argument`` bei anderer Endung,
            ``not_found``.
    """
    base = Path(limits.import_dir).resolve() if limits.import_dir else None
    candidate = Path(path)
    full = (candidate if candidate.is_absolute() else (base or Path.cwd()) / candidate).resolve()
    if base is None or not full.is_relative_to(base):
        raise PkmError("forbidden", "Bilddateien werden nur aus PKM_IMPORT_DIR übernommen.", path=path)
    if full.suffix.lower() not in IMPORT_SUFFIXES:
        raise PkmError("invalid_argument", "Nur .png, .svg, .jpg und .jpeg werden übernommen.", path=path)
    if not full.is_file():
        raise PkmError("not_found", f"Datei nicht gefunden: {path}", path=path)
    return IMPORT_SUFFIXES[full.suffix.lower()], full.read_bytes()


def prepare_image(spec: dict[str, Any], limits: Any, scratch: bool = False) -> PreparedImage:
    """Neues Bild prüfen, bereinigen und Modus bestimmen (4.9).

    Args:
        spec: Bildangabe (``name``, ``alt``, Quelle, optional ``mode``).
        limits: ``ImageConfig``.
        scratch: Ziel liegt in ``scratch/`` (dann immer eingebettet).

    Returns:
        Das vorbereitete Bild.

    Raises:
        PkmError: ``invalid_argument``, ``invalid_image``, ``svg_too_complex``, ``too_large``,
            ``too_large_for_inline``, ``forbidden``.
    """
    name = str(spec.get("name") or "").strip()
    alt = " ".join(str(spec.get("alt") or "").split()).replace("[", "(").replace("]", ")")
    mode = str(spec.get("mode") or "auto")
    if not NAME_RE.match(name):
        raise PkmError("invalid_argument", f"Ungültiger Bildname {name!r} (Kleinbuchstaben, Ziffern, Bindestriche).")
    if not alt:
        raise PkmError("invalid_argument", f"Bild {name}: Alternativtext fehlt.", image=name)
    if mode not in MODES:
        raise PkmError("invalid_argument", f"mode muss eines von {', '.join(MODES)} sein.", image=name)
    fmt, data = _source_bytes(spec, limits)
    cleaners = {"svg": lambda d: sanitize_svg(d.decode("utf-8", "replace"), limits.svg_max_kb).encode("utf-8"),
                "png": clean_png, "jpg": clean_jpeg}
    data = cleaners[fmt](data)
    if len(data) > limits.image_max_mb * 1024 * 1024:
        raise PkmError("too_large", f"Bild {name} ist größer als {limits.image_max_mb} MB.", image=name)
    image = PreparedImage(name, alt, fmt, data, "inline")
    fits = len(image.data_uri()) <= limits.inline_max_kb * 1024
    if not scratch and mode == "inline" and not fits:
        raise PkmError("too_large_for_inline", f"Bild {name} ist für das Einbetten zu groß "
                       f"(> {limits.inline_max_kb} KB); mode auto oder file verwenden.", image=name)
    if not scratch and (mode == "file" or (mode == "auto" and not fits)):
        image.mode = "file"
    return image


def check_new_names(text: str, images: list[PreparedImage], existing: list[ImageRef]) -> None:
    """Platzhalter ``{{image:<name>}}`` und Bildnamen prüfen.

    Args:
        text: Neuer Text mit Platzhaltern.
        images: Neue Bilder.
        existing: Bilder, die im Dokument schon stehen.

    Raises:
        PkmError: ``invalid_argument`` bei doppelten oder schon vergebenen Namen, ``unknown_image``
            bei Platzhaltern ohne Bild, ``invalid_argument`` bei Bildern ohne Platzhalter.
    """
    names = [i.name for i in images]
    used = {r.name for r in existing}
    wanted = [m.group("name") for m in NEW_IMAGE_RE.finditer(text)]
    if len(set(names)) != len(names) or set(names) & used:
        raise PkmError("invalid_argument", "Bildnamen müssen im Dokument eindeutig sein.", images=names)
    if set(wanted) - set(names):
        raise PkmError("unknown_image", "Platzhalter ohne Bild: " + ", ".join(sorted(set(wanted) - set(names))))
    if set(names) - set(wanted):
        raise PkmError("invalid_argument", "Bilder ohne Platzhalter {{image:<name>}} im Text: "
                       + ", ".join(sorted(set(names) - set(wanted))))


def insert_new_images(text: str, lines: dict[str, str]) -> str:
    """Platzhalter ``{{image:<name>}}`` durch die Bildzeilen ersetzen.

    Args:
        text: Text mit Platzhaltern.
        lines: Bildname → Markdown des Bildes.

    Returns:
        Text mit Bildern.
    """
    return NEW_IMAGE_RE.sub(lambda m: lines[m.group("name")], text)

# Main ************************************************************************
