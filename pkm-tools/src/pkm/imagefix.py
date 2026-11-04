"""Checking and fixing image data URIs (specification 4.9, "check on import").

``image_issues`` reports deviations with finding codes and a proposal; ``fix_text`` writes the images
in the form of 4.9. Fixes happen only after asking; these functions do not change files themselves,
except that ``fix_text`` creates image files in ``documents/_attachments/`` with a writer.

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
import hashlib
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from . import images
from .errors import PkmError
from .fsutil import write_bytes_atomic
from .imagescan import find_data_images
from .paths import MAX_NAME, slugify

if TYPE_CHECKING:
    from .config import ImageConfig
    from .writer import Writer

# Variables *******************************************************************

ATTACHMENTS = "documents/_attachments"
LEGACY_PROBLEMS = ("reference_style", "html_img", "angle_brackets", "base64_whitespace", "media_type_mismatch",
                   "invalid_data")
NOTATION_PROBLEMS = {"reference": "reference_style", "html": "html_img", "angle": "angle_brackets"}
MIME = {"png": "png", "jpg": "jpeg", "gif": "gif", "webp": "webp"}
SVG_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# Classes *********************************************************************


@dataclass
class Analysis:  # pylint: disable=too-many-instance-attributes
    """Check result of an embedded image.

    Attributes:
        ref: Image.
        problems: Finding codes.
        fmt: Format by signature (``png``, ``jpg``, ``svg``, ``gif``, ``webp`` or empty).
        data: Decoded bytes.
        legacy: Existing Base64 PNG/JPEG (only the notation is checked).
        removed: For SVG the parts that sanitizing removes.
        line: Line index (0-based) of the usage.
        fixable: Whether a fix is possible.
        note: Hint why no fix is possible.
    """

    ref: images.ImageRef
    problems: list[str] = field(default_factory=list)
    fmt: str = ""
    data: bytes = b""
    legacy: bool = False
    removed: list[str] = field(default_factory=list)
    line: int = 0
    fixable: bool = True
    note: str = ""

# Functions *******************************************************************


# Checking ********************************************************************
def _header(link: str) -> tuple[str, list[str], bool, str]:
    """Split the header of a data URI.

    Args:
        link: Data URI.

    Returns:
        Tuple of (media type, parameters without ``base64``, Base64, payload).
    """
    head, _, payload = link.partition(",")
    parts = [p.strip().lower() for p in head[5:].split(";")]
    return parts[0], [p for p in parts[1:] if p and p != "base64"], "base64" in parts[1:], payload


def signature(data: bytes) -> str:
    """Detect the format from the first bytes.

    Args:
        data: Bytes.

    Returns:
        ``png``, ``jpg``, ``gif``, ``webp``, ``svg`` or empty.
    """
    head = data[:512].lstrip().lower()
    fmt = ""
    if data.startswith(images.PNG_SIGNATURE):
        fmt = "png"
    elif data.startswith(b"\xff\xd8"):
        fmt = "jpg"
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        fmt = "gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        fmt = "webp"
    elif head.startswith(b"<") and b"<svg" in head:
        fmt = "svg"
    return fmt


def _decode(link: str) -> bytes:
    """Decode a data URI (also with whitespace in the Base64 and unencoded SVG).

    Args:
        link: Data URI.

    Returns:
        Bytes (empty if not decodable).
    """
    _, _, b64, payload = _header(link)
    try:
        data = base64.b64decode(re.sub(r"\s+", "", payload), validate=True) if b64 else unquote(payload).encode("utf-8")
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        data = b""
    return data


def _own_line(text: str, ref: images.ImageRef, starts: list[int]) -> bool:
    """Check whether an image stands alone in its line.

    Args:
        text: Markdown.
        ref: Image.
        starts: Start positions of all images.

    Returns:
        ``True`` if the line contains only whitespace besides the image.
    """
    line_start = text.rfind("\n", 0, ref.start) + 1
    line_end = text.find("\n", ref.end)
    line_end = len(text) if line_end < 0 else line_end
    others = [s for s in starts if line_start <= s < line_end and s != ref.start]
    return not (text[line_start:ref.start].strip() or text[ref.end:line_end].strip() or others)


def _svg_checks(a: Analysis, payload: str, params: list[str], b64: bool, limits: ImageConfig) -> None:
    """SVG-specific findings.

    Args:
        a: Check result (added to).
        payload: Payload of the URI.
        params: Parameters in the media type.
        b64: Base64-encoded.
        limits: Image limits.
    """
    if params:
        a.problems.append("svg_parameters")
    if b64:
        a.problems.append("svg_base64")
    elif any(ch in images.URL_UNSAFE for ch in re.sub(r"%[0-9A-Fa-f]{2}", "", payload)):
        a.problems.append("unencoded_chars")
    svg = a.data.decode("utf-8", "replace")
    a.removed = images.svg_problems(svg)
    if a.removed:
        a.problems.append("svg_unsafe")
    try:
        images.sanitize_svg(svg, limits.svg_max_kb)
    except PkmError as exc:
        if exc.status == "svg_too_complex" and "raster image" in exc.message:
            a.fixable, a.note = False, "SVG with an embedded raster image; store it again as PNG"
        elif exc.status == "svg_too_complex":
            a.problems.append("too_large_for_inline")
        else:
            a.problems.append("invalid_data")
            a.fixable, a.note = False, exc.message


def analyze(  # pylint: disable=too-many-arguments
    text: str, ref: images.ImageRef, limits: ImageConfig, *, legacy: bool, scratch: bool, wiki: bool,
    starts: list[int], names: dict[str, int],
) -> Analysis:
    """Check an embedded image per 4.9.

    Args:
        text: Markdown.
        ref: Image.
        limits: Image limits.
        legacy: Check existing Base64 PNG/JPEG only for the notation.
        scratch: Target lies in ``scratch/`` (no files).
        wiki: Wiki page (no files, no size limit).
        starts: Start positions of all images.
        names: Count per explicitly set image name.

    Returns:
        The check result.
    """
    occ = ref.occ
    mime, params, b64, payload = _header(ref.link)
    a = Analysis(ref, line=text.count("\n", 0, ref.start))
    a.data = _decode(ref.link)
    a.fmt = signature(a.data)
    declared = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/svg+xml": "svg",
                "image/gif": "gif", "image/webp": "webp"}.get(mime, "")
    if occ is not None and occ.notation in NOTATION_PROBLEMS:
        a.problems.append(NOTATION_PROBLEMS[occ.notation])
    a.legacy = legacy and b64 and a.fmt in ("png", "jpg")
    if not a.data or not a.fmt:
        a.problems.append("invalid_data")
        a.fixable, a.note = False, "not decodable or not an image"
    elif a.fmt in ("png", "jpg") and b64 and re.search(r"\s", payload):
        a.problems.append("base64_whitespace")
    if a.data and a.fmt and declared != a.fmt:
        a.problems.append("media_type_mismatch")
    if a.fmt == "svg":
        _svg_checks(a, payload, params, b64, limits)
    if a.fmt in ("gif", "webp"):
        a.problems.append("unsupported_type")
        a.fixable = a.fixable and not (scratch or wiki)
    if a.legacy:
        a.problems = [p for p in a.problems if p in LEGACY_PROBLEMS]
    elif a.fmt:
        _strict_checks(a, text, limits, scratch or wiki, starts, names)
    return a


def _strict_checks(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    a: Analysis, text: str, limits: ImageConfig, no_files: bool, starts: list[int],
                   names: dict[str, int]) -> None:
    """Checks for new images: line, name, alt text, size.

    Args:
        a: Check result (added to).
        text: Markdown.
        limits: Image limits.
        no_files: No files possible (``scratch/``, wiki).
        starts: Start positions of all images.
        names: Count per explicitly set image name.
    """
    ref = a.ref
    title = ref.occ.title if ref.occ is not None else None
    if not _own_line(text, ref, starts):
        a.problems.append("not_own_line")
    if not title or not title.startswith("pkm:"):
        a.problems.append("missing_name")
    elif not ref.named:
        a.problems.append("invalid_name")
    elif names.get(ref.name, 0) > 1:
        a.problems.append("duplicate_name")
    if not ref.alt:
        a.problems.append("missing_alt")
    if not no_files and a.fixable and a.fmt in ("png", "jpg", "svg") and "too_large_for_inline" not in a.problems:
        if len(_conforming_uri(a)) > limits.inline_max_kb * 1024:
            a.problems.append("too_large_for_inline")


def _conforming_uri(a: Analysis) -> str:
    """Data URI of the image in the form of 4.9.

    Args:
        a: Check result.

    Returns:
        Data URI (SVG sanitized; raster images with unchanged bytes).
    """
    if a.fmt == "svg":
        svg = images.sanitize_svg(a.data.decode("utf-8", "replace"), 10 ** 6)
        uri = images.svg_data_uri(svg)
    else:
        uri = f"data:image/{MIME.get(a.fmt, a.fmt)};base64," + base64.b64encode(a.data).decode("ascii")
    return uri


def _suggested_alt(a: Analysis, section_of: Any) -> str:
    """Proposal for a missing alt text.

    Args:
        a: Check result.
        section_of: Function position → section.

    Returns:
        Reference name, SVG ``<title>`` or surrounding heading (empty if nothing fits).
    """
    occ = a.ref.occ
    title = SVG_TITLE_RE.search(a.data.decode("utf-8", "replace")) if a.fmt == "svg" else None
    candidates = [occ.label if occ is not None and occ.label else "", title.group(1).strip() if title else "",
                  section_of(a.ref.start) or "" if section_of else ""]
    return next((c for c in candidates if c and c != "_preamble"), "")


def _issue(text: str, a: Analysis, section_of: Any, scratch: bool) -> dict[str, Any]:
    """Entry for ``image_issues``.

    Args:
        text: Markdown.
        a: Check result.
        section_of: Function position → section.
        scratch: Target in ``scratch/``.

    Returns:
        ``ref``, ``line``, ``section``, ``format``, ``size``, ``problems``, ``fixable``, ``proposal``.
    """
    occ = a.ref.occ
    many = occ is not None and len(occ.usages) > 1
    mode = "file" if not scratch and {"too_large_for_inline", "unsupported_type"} & set(a.problems) else "inline"
    proposal = {"name": a.ref.name, "alt": a.ref.alt or _suggested_alt(a, section_of),
                "mode": mode, "removed": a.removed}
    if a.legacy:
        proposal = {"name": None, "alt": a.ref.alt, "mode": "inline", "removed": []}
    entry: dict[str, Any] = {"ref": a.ref.name, "line": a.line + 1, "section": section_of(a.ref.start) if section_of
                             else None, "format": a.fmt, "size": len(a.data), "problems": a.problems,
                             "fixable": a.fixable, "proposal": proposal}
    if many:
        entry["note"] = "Reference used more than once: " + ", ".join(
            str(text.count("\n", 0, s) + 1) for s, _ in occ.usages) + " (lines); image possible in one place only"
    elif a.note:
        entry["note"] = a.note
    return entry


def analyses(  # pylint: disable=too-many-arguments
    text: str, limits: ImageConfig, *, legacy: bool = True, scratch: bool = False, wiki: bool = False,
             only_links: set[str] | None = None) -> list[Analysis]:
    """Check all embedded images of a text.

    Args:
        text: Markdown.
        limits: Image limits.
        legacy: Check existing Base64 PNG/JPEG only for the notation.
        scratch: Target in ``scratch/``.
        wiki: Wiki page.
        only_links: Check only images with these URIs (e.g. new ones in the given text).

    Returns:
        Check results of all checked images (also without findings).
    """
    refs = images.find_images(text)
    starts = [r.start for r in refs]
    names: dict[str, int] = {}
    for r in refs:
        if r.named:
            names[r.name] = names.get(r.name, 0) + 1
    return [analyze(text, r, limits, legacy=legacy, scratch=scratch, wiki=wiki, starts=starts, names=names)
            for r in refs if r.inline and (only_links is None or r.link in only_links)]


def unused_definitions(text: str) -> list[dict[str, Any]]:
    """Reference definitions with a data URI that are not used anywhere.

    Args:
        text: Markdown.

    Returns:
        Entries for ``image_issues`` (``problems: [unused_definition]``).
    """
    out = []
    for occ in find_data_images(text):
        if occ.notation == "reference" and not occ.usages and occ.def_span is not None:
            out.append({"ref": slugify(occ.label or "image", 40), "line": text.count("\n", 0, occ.def_span[0]) + 1,
                        "section": None, "format": "", "size": occ.uri_end - occ.uri_start,
                        "problems": ["unused_definition"], "fixable": True,
                        "proposal": {"name": None, "alt": "", "mode": "remove", "removed": ["definition"]}})
    return out


def image_issues(  # pylint: disable=too-many-arguments
    text: str, limits: ImageConfig, *, legacy: bool = True, scratch: bool = False, wiki: bool = False,
                 section_of: Any = None, only_links: set[str] | None = None) -> list[dict[str, Any]]:
    """Findings for nonconforming data URIs (4.9).

    Args:
        text: Markdown.
        limits: Image limits.
        legacy: Check existing Base64 PNG/JPEG only for the notation.
        scratch: Target in ``scratch/``.
        wiki: Wiki page.
        section_of: Function position → section.
        only_links: Check only images with these URIs.

    Returns:
        One entry per nonconforming image, plus unused definitions (only without ``only_links``).
    """
    found = [_issue(text, a, section_of, scratch)
             for a in analyses(text, limits, legacy=legacy, scratch=scratch, wiki=wiki, only_links=only_links)
             if a.problems]
    return found + (unused_definitions(text) if only_links is None else [])


# Fixing **********************************************************************
def _unique(name: str, used: set[str]) -> str:
    """Build a unique name (suffix ``-2``, ``-3``).

    Args:
        name: Desired name.
        used: Assigned names (added to).

    Returns:
        The name.
    """
    candidate, k = name, 1
    while candidate in used:
        k += 1
        candidate = f"{name}-{k}"
    used.add(candidate)
    return candidate


def _target_link(a: Analysis, writer: Writer | None, doc_rel: str, files: list[str]) -> str:
    """Storage as a file in ``documents/_attachments/`` (for dry runs only the future path).

    Args:
        a: Check result.
        writer: Writer or ``None`` (proposal without writing).
        doc_rel: Path of the document.
        files: Newly written files (added to).

    Returns:
        Relative link to the file.
    """
    stem = slugify(a.ref.name, MAX_NAME)
    if writer is None:
        rel = f"{ATTACHMENTS}/{stem}_YYYY-MM-DD.{a.fmt}"
    else:
        rel = writer.free_name(ATTACHMENTS, stem, f"_{writer.svc.now().date().isoformat()}", f".{a.fmt}")
        write_bytes_atomic(writer.vault.path(rel), a.data)
        files.append(rel)
    return images.relative_link(doc_rel, rel)


def _replacement(a: Analysis, ctx: dict[str, Any]) -> str:
    """Image in the form of 4.9.

    Args:
        a: Check result.
        ctx: ``writer``, ``doc_rel``, ``files``, ``used``, ``image_alt``, ``proposals``.

    Returns:
        Markdown of the image (without line breaks).
    """
    ref, occ = a.ref, a.ref.occ
    width = f"|{occ.width}" if occ is not None and occ.width else ""
    raw_alt = (occ.alt if occ is not None else ref.alt) or ""
    if a.legacy:
        title = f' "{occ.title}"' if occ is not None and occ.title else ""
        uri = f"data:image/{MIME[a.fmt]};base64," + base64.b64encode(a.data).decode("ascii")
        result = f"![{raw_alt}{width if '|' not in raw_alt else ''}]({uri}{title})"
    else:
        name = ref.name
        if "duplicate_name" in a.problems and name in ctx["kept"]:
            name = _unique(name, ctx["used"])
        ctx["kept"].add(name)
        alt = ctx["image_alt"].get(ref.name) or ref.alt or ctx["proposals"].get(ref.name, "")
        alt = " ".join(str(alt).split()).replace("[", "(").replace("]", ")")
        keep_width = raw_alt.split("|", 1)[1] if "|" in raw_alt else occ.width if occ is not None else None
        alt = f"{alt}|{keep_width}" if keep_width else alt
        to_file = not ctx["no_files"] and {"too_large_for_inline", "unsupported_type"} & set(a.problems)
        link = _target_link(a, ctx["writer"], ctx["doc_rel"], ctx["files"]) if to_file else _conforming_uri(a)
        result = f'![{alt}]({link} "pkm:{name}")'
    return result


def _line_wrapped(text: str, start: int, end: int, line: str) -> tuple[int, int, str]:
    """Frame the replacement so that the image stands in its own line; the surrounding text stays.

    Spaces directly before or after the image are replaced by the line break.

    Args:
        text: Markdown.
        start: Start of the image.
        end: End of the image.
        line: New image.

    Returns:
        Tuple of (start, end, replacement text).
    """
    before = text[text.rfind("\n", 0, start) + 1:start]
    after_end = text.find("\n", end)
    after = text[end:len(text) if after_end < 0 else after_end]
    if before.strip():
        start -= len(before) - len(before.rstrip(" \t"))
    if after.strip():
        end += len(after) - len(after.lstrip(" \t"))
    return start, end, ("\n" if before.strip() else "") + line + ("\n" if after.strip() else "")


def fix_text(  # pylint: disable=too-many-arguments,too-many-locals
    text: str, limits: ImageConfig, *, writer: Writer | None = None, doc_rel: str = "", names: list[str] | None = None,
    image_alt: dict[str, str] | None = None, confirm_shortening: bool = False, legacy: bool = True,
    scratch: bool = False, wiki: bool = False, only_links: set[str] | None = None,
) -> tuple[str, list[str]]:
    """Fix nonconforming data URIs per 4.9; the remaining text stays byte for byte.

    Args:
        text: Markdown.
        limits: Image limits.
        writer: Writer for creating image files (``None``: proposal only, no files).
        doc_rel: Path of the document.
        names: Only these images (names from ``image_issues``).
        image_alt: Alt texts per name.
        confirm_shortening: Removal of unused definitions confirmed.
        legacy: Fix existing Base64 PNG/JPEG only in the notation.
        scratch: Target in ``scratch/``.
        wiki: Wiki page.
        only_links: Only images with these URIs.

    Returns:
        Tuple of (new text, newly written image files).

    Raises:
        PkmError: ``ambiguous`` for references used more than once, ``large_shortening`` for
            unused definitions without confirmation.
    """
    found = [a for a in analyses(text, limits, legacy=legacy, scratch=scratch, wiki=wiki, only_links=only_links)
             if a.problems and a.fixable and (names is None or a.ref.name in names)]
    ctx: dict[str, Any] = {"writer": writer, "doc_rel": doc_rel, "files": [], "image_alt": dict(image_alt or {}),
                           "used": {r.name for r in images.find_images(text)}, "no_files": scratch or wiki,
                           "kept": set(),
                           "proposals": {i["ref"]: i["proposal"]["alt"] for i in image_issues(
                               text, limits, legacy=legacy, scratch=scratch, wiki=wiki, only_links=only_links)}}
    spans: list[tuple[int, int, str]] = []
    for a in found:
        occ = a.ref.occ
        if occ is not None and len(occ.usages) > 1:
            raise PkmError("ambiguous", f"Reference [{occ.label}] is used more than once; image names are unique.",
                           lines=[text.count("\n", 0, s) + 1 for s, _ in occ.usages], image=a.ref.name)
        spans.append(_line_wrapped(text, a.ref.start, a.ref.end, _replacement(a, ctx)))
        if occ is not None and occ.def_span is not None:
            spans.append((occ.def_span[0], occ.def_span[1], ""))
    unused = [u for u in unused_definitions(text) if only_links is None and (names is None or u["ref"] in names)]
    if unused and not confirm_shortening:
        raise PkmError("large_shortening", "Unused image definitions would be removed; please confirm "
                       "(confirm_shortening).", removed_images=[u["ref"] for u in unused])
    for occ in find_data_images(text) if unused else []:
        if occ.notation == "reference" and not occ.usages and occ.def_span is not None:
            spans.append((occ.def_span[0], occ.def_span[1], ""))
    out, pos = [], 0
    for start, end, repl in sorted(spans):
        out += [text[pos:start], repl]
        pos = end
    return "".join(out) + text[pos:], ctx["files"]


# Comparison ******************************************************************
def canonical(text: str, limits: ImageConfig) -> tuple[str, list[str]]:
    """Text for the comparison "only the image notation changed" (4.9, citations after a fix).

    Every embedded image becomes ``![<alt>](pkm-image:<name>)``, reference definitions are dropped,
    whitespace is collapsed. Plus the hashes of the decoded images (SVG after sanitizing;
    unsafe SVG get a marker of their own so that they count as changed).

    Args:
        text: Markdown (e.g. a section).
        limits: Image limits.

    Returns:
        Tuple of (canonical text, image hashes in order).
    """
    spans: list[tuple[int, int, str]] = []
    digests: list[str] = []
    for a in analyses(text, limits, legacy=True):
        spans.append((a.ref.start, a.ref.end, f"![{a.ref.alt}](pkm-image:{a.ref.name})"))
        if a.ref.occ is not None and a.ref.occ.def_span is not None:
            spans.append((a.ref.occ.def_span[0], a.ref.occ.def_span[1], ""))
        data = a.data
        if a.fmt == "svg":
            try:
                data = images.sanitize_svg(a.data.decode("utf-8", "replace"), 10 ** 6).encode("utf-8")
            except PkmError:
                data = a.data
        digests.append(("unsafe:" if a.removed else "") + hashlib.sha256(data).hexdigest())
    for occ in find_data_images(text):
        if occ.notation == "reference" and not occ.usages and occ.def_span is not None:
            spans.append((occ.def_span[0], occ.def_span[1], ""))
    out, pos = [], 0
    for start, end, repl in sorted(set(spans)):
        if start >= pos:
            out += [text[pos:start], repl]
            pos = end
    return " ".join(("".join(out) + text[pos:]).split()), digests


def body_notation_only(old: str, new: str, limits: ImageConfig) -> bool:
    """Check whether two whole bodies differ only in the image notation.

    Args:
        old: Earlier body.
        new: Current body.
        limits: Image limits.

    Returns:
        Like ``notation_only`` for the whole text (also covers references across sections).
    """
    return notation_only(old, new, limits)


def notation_only(old: str, new: str, limits: ImageConfig) -> bool:
    """Check whether two texts differ only in the image notation.

    Args:
        old: Earlier text.
        new: Current text.
        limits: Image limits.

    Returns:
        ``True`` if they differ but are canonically equal, and no image was unsafe.
    """
    a, b = canonical(old, limits), canonical(new, limits)
    return old != new and a == b and not any(d.startswith("unsafe:") for d in a[1])

# Main ************************************************************************
