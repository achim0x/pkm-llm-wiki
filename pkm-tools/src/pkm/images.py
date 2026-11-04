"""Images in documents (specification 4.9): detect, check, sanitize, encode, placeholders.

PNG and SVG. Small images are embedded as data URIs (PNG Base64, SVG URL-encoded), larger ones are
stored as files. Base64 never reaches the model's context: ``read`` shows placeholders that are
translated back byte for byte when writing.

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
from .imagescan import DataOccurrence, find_data_images
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
JPEG_DROP = (0xE1, 0xED, 0xFE)  # EXIF/XMP, Photoshop/IPTC, comment
JPEG_SOF = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
EXIF_ORIENTATION = 0x0112
MODES = ("auto", "inline", "file")
PLACEHOLDER_SCHEME = "pkm-image:"
MD_IMAGE_RE = re.compile(r'!\[(?P<alt>[^\]\n]*)\]\((?P<url>[^\s)]+)(?:[ \t]+"(?P<title>[^"\n]*)")?\)')
WIKI_IMAGE_RE = re.compile(
    r"!\[\[(?P<path>[^\]|#\n]+?\.(?:png|svg|jpe?g|gif|webp))(?:\|(?P<opt>[^\]\n]*))?\]\]", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r'!\[(?P<alt>[^\]\n]*)\]\(pkm-image:(?P<name>[a-z0-9-]+)(?:[ \t]+"[^"\n]*")?\)')
TOKEN_RE = re.compile(r"pkm-image:(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)")
NEW_IMAGE_RE = re.compile(r"\{\{image:(?P<name>[^}\s]+)\}\}")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SVG_FORBIDDEN = (
    (re.compile(r"<!DOCTYPE|<!ENTITY", re.IGNORECASE), "DOCTYPE/Entities"),
    (re.compile(r"<\?xml-stylesheet", re.IGNORECASE), "xml-stylesheet"),
    (re.compile(r"<(?:[\w-]+:)?script\b", re.IGNORECASE), "<script>"),
    (re.compile(r"<(?:[\w-]+:)?foreignObject\b", re.IGNORECASE), "<foreignObject>"),
    (re.compile(r"""\son[a-z]+\s*=""", re.IGNORECASE), "event attribute"),
    (re.compile(r"""(?:xlink:)?href\s*=\s*["'](?!#)""", re.IGNORECASE), "external reference"),
    (re.compile(r"url\(\s*['\"]?(?!#)[a-z]+:", re.IGNORECASE), "external reference in CSS"),
    (re.compile(r"data:image/(?!svg)", re.IGNORECASE), "embedded raster image"),
)
URL_UNSAFE = set('%#<>" \n\r\t()[]{}|\\^`')
DROP_ELEMENTS = ("script", "foreignObject", "metadata")

# Classes *********************************************************************


@dataclass
class ImageRef:  # pylint: disable=too-many-instance-attributes
    """An image in the text of a document.

    Attributes:
        name: Image name (``pkm:<name>`` or derived).
        alt: Alt text (without ``|width``).
        raw: Exact Markdown text of the image.
        start: Start position in the text.
        end: End position in the text.
        inline: Embedded (data URI) instead of a file.
        fmt: Format (``png``, ``svg``, ``jpg`` …).
        link: Reference as written (data URI or path).
        named: Whether the name is in the text as ``pkm:<name>``.
        occ: Occurrence for embedded images (notation, position of the URI, reference) or ``None``.
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
    occ: DataOccurrence | None = None

    @property
    def full_placeholder(self) -> bool:
        """Whether the image appears in ``read`` as a whole placeholder (notation per 4.9).

        Returns:
            ``True`` for ``![alt](data:… "…")`` without whitespace in the URI; otherwise only the URI is replaced.
        """
        return self.occ is not None and self.occ.notation == "inline" and bool(MD_IMAGE_RE.fullmatch(self.raw))

    def data(self) -> bytes:
        """Content of an embedded image.

        Returns:
            Decoded bytes (empty for files or unreadable data URIs).
        """
        return decode_data_uri(self.link)[1] if self.inline else b""


@dataclass
class PreparedImage:
    """A new image, checked and encoded, ready to insert.

    Attributes:
        name: Image name.
        alt: Alt text.
        fmt: ``png`` or ``svg``.
        data: Sanitized bytes.
        mode: ``inline`` or ``file``.
    """

    name: str
    alt: str
    fmt: str
    data: bytes
    mode: str

    def markdown(self, link: str) -> str:
        """Markdown line of the image.

        Args:
            link: Data URI or relative path to the file.

        Returns:
            ``![alt](link "pkm:name")``.
        """
        return f'![{self.alt}]({link} "pkm:{self.name}")'

    def data_uri(self) -> str:
        """Image as a data URI.

        Returns:
            PNG as a Base64 data URI, SVG as a URL-encoded one.
        """
        uri = svg_data_uri(self.data.decode("utf-8")) if self.fmt == "svg" else png_data_uri(self.data)
        return uri.replace("data:image/png;", "data:image/jpeg;", 1) if self.fmt == "jpg" else uri

    def info(self) -> dict[str, Any]:
        """Short info for return values.

        Returns:
            Name, format, mode, size in bytes and hash.
        """
        return {"name": self.name, "format": self.fmt, "mode": self.mode, "size": len(self.data),
                "hash": hashlib.sha256(self.data).hexdigest()}

# Functions *******************************************************************


# Detecting *******************************************************************
def find_images(text: str) -> list[ImageRef]:
    """Find images in the text: Markdown images (data URI or file) and Obsidian embeds.

    Images with an ``http(s):`` address do not count. Images without a ``pkm:`` name get a
    derived name (alt text, otherwise ``image-<n>``) that is not written to the file.

    Args:
        text: Markdown (body or section).

    Returns:
        Images in text order.
    """
    found: list[tuple[int, int, str, str, str | None, DataOccurrence | None]] = []
    for m in MD_IMAGE_RE.finditer(text):
        url = m.group("url")
        if not url.lower().startswith("data:") and PurePosixPath(unquote(url).lower()).suffix in IMAGE_EXTENSIONS:
            if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.IGNORECASE) and not url.startswith(PLACEHOLDER_SCHEME):
                found.append((m.start(), m.end(), m.group("alt"), url, m.group("title"), None))
    for m in WIKI_IMAGE_RE.finditer(text):
        found.append((m.start(), m.end(), m.group("opt") or "", m.group("path"), None, None))
    for occ in find_data_images(text):
        if occ.notation != "reference" or occ.usages:
            found.append((occ.start, occ.end, occ.alt, text[occ.uri_start:occ.uri_end], occ.title, occ))
    refs: list[ImageRef] = []
    used: set[str] = {t[4][4:] for t in found if t[4] and t[4].startswith("pkm:") and NAME_RE.match(t[4][4:])}
    for n, (start, end, alt, url, title, occ) in enumerate(sorted(found, key=lambda t: t[0]), start=1):
        named = bool(title and title.startswith("pkm:") and NAME_RE.match(title[4:]))
        name = title[4:] if named and title else _derived_name(alt, n, used)
        used.add(name)
        refs.append(ImageRef(name, alt.split("|", 1)[0].strip(), text[start:end], start, end, occ is not None,
                             _format_of(url), url, named, occ))
    return refs


def _derived_name(alt: str, n: int, used: set[str]) -> str:
    """Derive an image name (from the alt text, otherwise ``image-<n>``), unique in the document.

    Args:
        alt: Alt text (possibly with ``|width``).
        n: Position of the image in the document.
        used: Names already assigned.

    Returns:
        The name.
    """
    base = alt.split("|", 1)[0].strip()
    name = slugify(base, 40) if base and not base.isdigit() else f"image-{n}"
    candidate, k = name, 1
    while candidate in used:
        k += 1
        candidate = f"{name}-{k}"
    return candidate


def _format_of(url: str) -> str:
    """Format of an image reference.

    Args:
        url: Data URI or path.

    Returns:
        ``png``, ``svg``, ``jpg`` … (empty if unknown).
    """
    m = re.match(r"data:image/([a-z0-9.+-]+)", url, re.IGNORECASE)
    fmt = m.group(1).lower() if m else PurePosixPath(unquote(url).lower()).suffix.lstrip(".")
    return {"svg+xml": "svg", "jpeg": "jpg"}.get(fmt, fmt)


def link_target(ref: ImageRef, doc_rel: str) -> str | None:
    """Vault path of a linked image file (Markdown link relative to the document).

    Args:
        ref: Image.
        doc_rel: Path of the document in the vault.

    Returns:
        Path in the vault; ``None`` for embedded images. Obsidian embeds without a folder return
        the name as written (resolved via the file inventory).
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
    """Markdown link from the document to a file in the vault.

    Args:
        doc_rel: Path of the document.
        file_rel: Path of the file.

    Returns:
        Relative path, e.g. ``../_attachments/photo_2026-11-03.png`` (spaces encoded).
    """
    rel = posixpath.relpath(file_rel, posixpath.dirname(doc_rel) or ".")
    return quote(rel, safe="/._-~")


def strip_images(text: str) -> str:
    """Replace images by their alt text (for search and index; never Base64 or SVG content).

    Args:
        text: Markdown.

    Returns:
        Text in which every image only appears as its alt text.
    """
    out, pos = [], 0
    for ref in find_images(text):
        out += [text[pos:ref.start], ref.alt]
        pos = ref.end
    return "".join(out) + text[pos:]


# Placeholders ****************************************************************
def human_size(size: int) -> str:
    """Size for placeholders.

    Args:
        size: Bytes.

    Returns:
        E.g. ``3.2 KB`` or ``812 B``.
    """
    return f"{size} B" if size < 1024 else f"{size / 1024:.1f} KB"


def placeholder(ref: ImageRef) -> str:
    """Placeholder for an embedded image.

    Args:
        ref: Image.

    Returns:
        E.g. ``![Circuit diagram](pkm-image:circuit-diagram "svg, 3.2 KB, sha:ab12cd")``.
    """
    data = ref.data()
    sha = hashlib.sha256(data).hexdigest()[:6]
    alt = ref.raw[2:ref.raw.index("](")] if "](" in ref.raw else ref.alt
    return f'![{alt}]({PLACEHOLDER_SCHEME}{ref.name} "{ref.fmt}, {human_size(len(data))}, sha:{sha}")'


def to_placeholders(text: str) -> str:
    """Replace embedded images by placeholders (for ``read``).

    Args:
        text: Markdown.

    Returns:
        Text without data URIs.
    """
    spans: list[tuple[int, int, str]] = []
    for ref in find_images(text):
        if ref.full_placeholder:
            spans.append((ref.start, ref.end, placeholder(ref)))
        elif ref.inline and ref.occ is not None:
            spans.append((ref.occ.uri_start, ref.occ.uri_end, f"{PLACEHOLDER_SCHEME}{ref.name}"))
    out, pos = [], 0
    for start, end, repl in sorted(spans):
        out += [text[pos:start], repl]
        pos = end
    return "".join(out) + text[pos:]


def restore_placeholders(text: str, refs: list[ImageRef]) -> str:
    """Replace placeholders byte for byte by the originals (for ``rewrite_document``/``edit_document``).

    Args:
        text: New text with placeholders.
        refs: Images of the previous document.

    Returns:
        Text with the original images.

    Raises:
        PkmError: ``unknown_image`` for placeholders without an image.
    """
    by_name = {r.name: r for r in refs if r.inline}
    unknown = sorted({m.group("name") for m in TOKEN_RE.finditer(text)} - set(by_name))
    if unknown:
        raise PkmError("unknown_image", "Unknown image placeholders: " + ", ".join(unknown), images=unknown)

    def full(m: re.Match[str]) -> str:
        """Replace a whole placeholder.

        Args:
            m: Match.

        Returns:
            Original or image with the original URI.
        """
        ref = by_name[m.group("name")]
        return ref.raw if ref.full_placeholder else f"![{m.group('alt')}]({ref.link})"

    text = PLACEHOLDER_RE.sub(full, text)
    return TOKEN_RE.sub(lambda m: by_name[m.group("name")].link, text)


def image_summary(text: str, section_of: Any = None) -> list[dict[str, Any]]:
    """List of the images for ``read``.

    Args:
        text: Markdown.
        section_of: Function position → section key (optional).

    Returns:
        Per image name, alt text, format, ``inline``/``file``, size, hash (for embedded ones),
        reference (for files) and section.
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


# Encoding ********************************************************************
def decode_data_uri(url: str) -> tuple[str, bytes]:
    """Decode a data URI.

    Args:
        url: ``data:image/…``.

    Returns:
        Tuple of (format, bytes); bytes empty if not decodable.
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
    """PNG as a Base64 data URI.

    Args:
        data: PNG bytes.

    Returns:
        ``data:image/png;base64,…`` without line breaks.
    """
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def svg_data_uri(svg: str) -> str:
    """SVG as a URL-encoded data URI (4.9): double quotes in attributes become single quotes.

    Args:
        svg: Sanitized, minified SVG.

    Returns:
        ``data:image/svg+xml,…``.
    """
    single = re.sub(r'(\s[\w:.-]+)="([^"]*)"', lambda m: f"{m.group(1)}='{m.group(2).replace(chr(39), '&apos;')}'",
                    svg)
    return "data:image/svg+xml," + "".join(f"%{ord(ch):02X}" if ch in URL_UNSAFE else ch for ch in single)


def svg_problems(svg: str) -> list[str]:
    """Find unsafe parts of an SVG (4.9, security).

    Args:
        svg: SVG text.

    Returns:
        Descriptions of the findings (empty if clean).
    """
    return [label for rx, label in SVG_FORBIDDEN if rx.search(svg)]


def _local(tag: str) -> str:
    """Local name of an element or attribute without namespace.

    Args:
        tag: ``{ns}name`` or ``name``.

    Returns:
        ``name``.
    """
    return tag.rsplit("}", 1)[-1]


def _clean_tree(root: ET.Element) -> None:
    """Remove unsafe elements and attributes (recursively).

    Args:
        root: SVG root.

    Raises:
        PkmError: ``svg_too_complex`` for embedded raster images.
    """
    for parent in list(root.iter()):
        for child in list(parent):
            href = child.get(f"{{{XLINK_NS}}}href") or child.get("href") or ""
            if _local(child.tag) == "image" and href.startswith("data:") and "svg" not in href[:20]:
                raise PkmError("svg_too_complex", "The SVG contains embedded raster images; use PNG for that.")
            if _local(child.tag) in DROP_ELEMENTS or (_local(child.tag) == "style" and svg_problems(child.text or "")):
                parent.remove(child)
        for key in list(parent.attrib):
            value = parent.attrib[key]
            name = _local(key).lower()
            if name.startswith("on") or (name == "href" and not value.startswith("#")) or svg_problems(
                    f" x='{value}'" if "url(" in value else ""):
                del parent.attrib[key]


def sanitize_svg(svg: str, max_kb: int) -> str:
    """Sanitize and minify an SVG (4.9).

    Args:
        svg: SVG text.
        max_kb: Complexity limit after sanitizing.

    Returns:
        Sanitized SVG without comments, metadata and superfluous whitespace.

    Raises:
        PkmError: ``invalid_image`` for DOCTYPE/entities or invalid XML, ``svg_too_complex`` for
            raster images or exceeding the limit.
    """
    if re.search(r"<!DOCTYPE|<!ENTITY", svg, re.IGNORECASE):
        raise PkmError("invalid_image", "SVG with DOCTYPE or entities is not accepted (XXE protection).")
    text = re.sub(r"<\?xml[^>]*\?>", "", svg).strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise PkmError("invalid_image", f"Not a valid SVG: {exc}") from exc
    if _local(root.tag) != "svg":
        raise PkmError("invalid_image", "The root is not an <svg> element.")
    _clean_tree(root)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    out = ET.tostring(root, encoding="unicode")
    out = re.sub(r">\s+<", "><", re.sub(r"\s+", " ", out)).strip()
    problems = svg_problems(out)
    if problems:
        raise PkmError("invalid_image", "SVG cannot be sanitized: " + ", ".join(problems))
    if len(out.encode("utf-8")) > max_kb * 1024:
        raise PkmError("svg_too_complex", f"The SVG is larger than {max_kb} KB; use PNG for that.")
    return out


def clean_png(data: bytes) -> bytes:
    """Check a new PNG and remove text chunks (4.9).

    Args:
        data: PNG bytes.

    Returns:
        PNG without ``tEXt``/``iTXt``/``zTXt``.

    Raises:
        PkmError: ``invalid_image`` for an invalid signature, structure or more than 8,000 × 8,000 pixels.
    """
    if not data.startswith(PNG_SIGNATURE):
        raise PkmError("invalid_image", "Not a PNG file (signature missing).")
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
        raise PkmError("invalid_image", "PNG is incomplete or damaged.")
    if width > PNG_MAX_PIXELS or height > PNG_MAX_PIXELS:
        raise PkmError("invalid_image", f"PNG is larger than {PNG_MAX_PIXELS} × {PNG_MAX_PIXELS} pixels.")
    return b"".join(chunks)


def _exif_orientation(tiff: bytes) -> int | None:
    """Read the orientation (tag 0x0112) from an EXIF TIFF block.

    Args:
        tiff: Content of the EXIF block after ``Exif\\0\\0``.

    Returns:
        Value 1–8 or ``None``.
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
    """Create a minimal EXIF block that only contains the orientation.

    Args:
        orientation: Value 2–8.

    Returns:
        APP1-Segment.
    """
    tiff = (b"MM\x00\x2a" + struct.pack(">I", 8) + struct.pack(">H", 1)
            + struct.pack(">HHIHH", EXIF_ORIENTATION, 3, 1, orientation, 0) + struct.pack(">I", 0))
    payload = b"Exif\x00\x00" + tiff
    return b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload


def clean_jpeg(data: bytes) -> bytes:
    """Check a new JPEG and remove metadata (EXIF/XMP, IPTC, comments); the orientation is kept.

    Args:
        data: JPEG bytes.

    Returns:
        JPEG without metadata, for rotated photos with an EXIF block for the orientation only.

    Raises:
        PkmError: ``invalid_image`` for an invalid structure or more than 8,000 × 8,000 pixels.
    """
    if not data.startswith(JPEG_SOI):
        raise PkmError("invalid_image", "Not a JPEG file (signature missing).")
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
        raise PkmError("invalid_image", "JPEG is incomplete or damaged.")
    if max(size) > PNG_MAX_PIXELS:
        raise PkmError("invalid_image", f"JPEG is larger than {PNG_MAX_PIXELS} × {PNG_MAX_PIXELS} pixels.")
    if orientation and orientation != 1:
        at = 2 if len(segments) > 1 and segments[1][:2] == b"\xff\xe0" else 1
        segments.insert(at, _orientation_segment(orientation))
    return b"".join(segments)


# New images ******************************************************************
def _source_bytes(spec: dict[str, Any], limits: Any) -> tuple[str, bytes]:
    """Read the source of a new image (exactly one of ``svg``, ``png_base64``, ``import_path``).

    Args:
        spec: Image specification from the tool call.
        limits: ``ImageConfig``.

    Returns:
        Tuple of (format, bytes).

    Raises:
        PkmError: ``invalid_argument``, ``too_large`` or ``forbidden`` (path outside of
            ``PKM_IMPORT_DIR``).
    """
    given = [k for k in ("svg", "png_base64", "import_path") if spec.get(k)]
    if len(given) != 1:
        raise PkmError("invalid_argument", "Exactly one source per image: svg, png_base64 or import_path.")
    if given[0] == "svg":
        result = ("svg", str(spec["svg"]).encode("utf-8"))
    elif given[0] == "png_base64":
        b64 = re.sub(r"\s+", "", str(spec["png_base64"]))
        if len(b64) > limits.param_max_kb * 1024:
            raise PkmError("too_large", f"png_base64 is larger than {limits.param_max_kb} KB; use import_path.")
        try:
            result = ("png", base64.b64decode(b64, validate=True))
        except (binascii.Error, ValueError) as exc:
            raise PkmError("invalid_image", "png_base64 is not valid Base64.") from exc
    else:
        result = _import_file(str(spec["import_path"]), limits)
    return result


def _import_file(path: str, limits: Any) -> tuple[str, bytes]:
    """Read an image file from ``PKM_IMPORT_DIR`` (copy, never delete).

    Args:
        path: File name or path.
        limits: ``ImageConfig``.

    Returns:
        Tuple of (format, bytes).

    Raises:
        PkmError: ``forbidden`` outside the import folder, ``invalid_argument`` for another extension,
            ``not_found``.
    """
    base = Path(limits.import_dir).resolve() if limits.import_dir else None
    candidate = Path(path)
    full = (candidate if candidate.is_absolute() else (base or Path.cwd()) / candidate).resolve()
    if base is None or not full.is_relative_to(base):
        raise PkmError("forbidden", "Image files are only imported from PKM_IMPORT_DIR.", path=path)
    if full.suffix.lower() not in IMPORT_SUFFIXES:
        raise PkmError("invalid_argument", "Only .png, .svg, .jpg and .jpeg are imported.", path=path)
    if not full.is_file():
        raise PkmError("not_found", f"File not found: {path}", path=path)
    return IMPORT_SUFFIXES[full.suffix.lower()], full.read_bytes()


def prepare_image(spec: dict[str, Any], limits: Any, scratch: bool = False) -> PreparedImage:
    """Check and sanitize a new image and determine its mode (4.9).

    Args:
        spec: Image specification (``name``, ``alt``, source, optionally ``mode``).
        limits: ``ImageConfig``.
        scratch: Target lies in ``scratch/`` (then always embedded).

    Returns:
        The prepared image.

    Raises:
        PkmError: ``invalid_argument``, ``invalid_image``, ``svg_too_complex``, ``too_large``,
            ``too_large_for_inline``, ``forbidden``.
    """
    name = str(spec.get("name") or "").strip()
    alt = " ".join(str(spec.get("alt") or "").split()).replace("[", "(").replace("]", ")")
    mode = str(spec.get("mode") or "auto")
    if not NAME_RE.match(name):
        raise PkmError("invalid_argument", f"Invalid image name {name!r} (lower case letters, digits, hyphens).")
    if not alt:
        raise PkmError("invalid_argument", f"Image {name}: alt text missing.", image=name)
    if mode not in MODES:
        raise PkmError("invalid_argument", f"mode must be one of {', '.join(MODES)}.", image=name)
    fmt, data = _source_bytes(spec, limits)
    cleaners = {"svg": lambda d: sanitize_svg(d.decode("utf-8", "replace"), limits.svg_max_kb).encode("utf-8"),
                "png": clean_png, "jpg": clean_jpeg}
    data = cleaners[fmt](data)
    if len(data) > limits.image_max_mb * 1024 * 1024:
        raise PkmError("too_large", f"Image {name} is larger than {limits.image_max_mb} MB.", image=name)
    image = PreparedImage(name, alt, fmt, data, "inline")
    fits = len(image.data_uri()) <= limits.inline_max_kb * 1024
    if not scratch and mode == "inline" and not fits:
        raise PkmError("too_large_for_inline", f"Image {name} is too large for embedding "
                       f"(> {limits.inline_max_kb} KB); use mode auto or file.", image=name)
    if not scratch and (mode == "file" or (mode == "auto" and not fits)):
        image.mode = "file"
    return image


def check_new_names(text: str, images: list[PreparedImage], existing: list[ImageRef]) -> None:
    """Check placeholders ``{{image:<name>}}`` and image names.

    Args:
        text: New text with placeholders.
        images: New images.
        existing: Images that are already in the document.

    Raises:
        PkmError: ``invalid_argument`` for duplicate or already assigned names, ``unknown_image``
            for placeholders without an image, ``invalid_argument`` for images without a placeholder.
    """
    names = [i.name for i in images]
    used = {r.name for r in existing}
    wanted = [m.group("name") for m in NEW_IMAGE_RE.finditer(text)]
    if len(set(names)) != len(names) or set(names) & used:
        raise PkmError("invalid_argument", "Image names must be unique in the document.", images=names)
    if set(wanted) - set(names):
        raise PkmError("unknown_image", "Placeholders without an image: " + ", ".join(sorted(set(wanted) - set(names))))
    if set(names) - set(wanted):
        raise PkmError("invalid_argument", "Images without a placeholder {{image:<name>}} in the text: "
                       + ", ".join(sorted(set(names) - set(wanted))))


def insert_new_images(text: str, lines: dict[str, str]) -> str:
    """Replace placeholders ``{{image:<name>}}`` by the image lines.

    Args:
        text: Text with placeholders.
        lines: Image name → Markdown of the image.

    Returns:
        Text with images.
    """
    return NEW_IMAGE_RE.sub(lambda m: lines[m.group("name")], text)

# Main ************************************************************************
