"""Write and read images in documents (specification 4.9, 7.2, 7.3): inserting new images,
storing them as files, placeholders in ``read`` and ``read_image``.

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

from . import imagefix, images
from .appendtext import count_overlapping
from .diffs import unified_diff
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


# Writing *********************************************************************
def has_image_markers(text: str) -> bool:
    """Check whether a text contains placeholders for new images.

    Args:
        text: New text.

    Returns:
        ``True`` for ``{{image:…}}``.
    """
    return bool(images.NEW_IMAGE_RE.search(text))


def check_text_images(
    writer: Writer, doc: Doc, text: str, fix: dict[str, Any] | None
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Check data URIs in the new text (4.9, check on import; 7.2).

    New data URIs (not already in the document) must conform to the form of 4.9, otherwise the result is
    ``nonconforming_image``. With ``fix_images`` they are fixed. Nonconforming images that are already in the
    document do not block and are returned as warnings.

    Args:
        writer: Writer.
        doc: Document (before).
        text: New full text.
        fix: ``fix_images`` and ``image_alt`` from the call.

    Returns:
        Tuple of (possibly fixed text, new image files, ``image_warnings``).

    Raises:
        PkmError: ``nonconforming_image`` with ``image_issues``.
    """
    fix = fix or {}
    limits, scratch = writer.cfg.images, not doc.versioned
    old_links = {r.link for r in images.find_images(doc.body or "") if r.inline}
    new_links = {r.link for r in images.find_images(text) if r.inline} - old_links
    issues = imagefix.image_issues(text, limits, legacy=False, scratch=scratch, only_links=new_links) if new_links \
        else []
    files: list[str] = []
    if issues and (not fix.get("fix_images") or not all(i["fixable"] for i in issues)):
        raise PkmError("nonconforming_image", "The text contains image data URIs that do not conform to the form "
                       "of 4.9. Show the findings and the proposal to the user; after confirmation repeat with "
                       "fix_images=true (and image_alt) or pass the images via images.", image_issues=issues)
    if issues:
        text, files = imagefix.fix_text(text, limits, writer=writer, doc_rel=doc.rel, image_alt=fix.get("image_alt"),
                                        legacy=False, scratch=scratch, only_links=new_links)
    current = {r.link for r in images.find_images(text) if r.inline}
    warnings = imagefix.image_issues(text, limits, scratch=scratch, only_links=old_links & current) \
        if old_links & current else []
    return text, files, warnings


def place_images(
    writer: Writer, doc: Doc, text: str, specs: list[dict[str, Any]] | None
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Check new images and insert them at the placeholders ``{{image:<name>}}``.

    Embedded images become data URIs, large ones or ``mode: file`` become files in
    ``documents/_attachments/`` (always embedded in ``scratch/``).

    Args:
        writer: Writer (for configuration, vault and free file names).
        doc: Document (before), determines location and area.
        text: New full text with placeholders.
        specs: Image specifications from the tool call.

    Returns:
        Tuple of (text with images, newly written image files, info per image).

    Raises:
        PkmError: Errors from ``images.prepare_image`` and ``images.check_new_names``.
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
    """Remove newly written image files again (after an error).

    Args:
        writer: Writer.
        files: Relative paths.
    """
    for rel in files:
        writer.vault.path(rel).unlink(missing_ok=True)


def restore_body(old_body: str, new_body: str) -> str:
    """Replace placeholders of embedded images in the new body by the originals.

    Args:
        old_body: Previous body.
        new_body: New body with placeholders.

    Returns:
        Body with the original images.
    """
    return images.restore_placeholders(new_body, images.find_images(old_body))


def removed_images(old_body: str, new_body: str) -> list[str]:
    """Images that are missing in the new body.

    Args:
        old_body: Previous body.
        new_body: New body (originals already inserted).

    Returns:
        Names of the removed images.
    """
    new_keys = {r.link if r.inline else r.raw for r in images.find_images(new_body)}
    return [r.name for r in images.find_images(old_body) if (r.link if r.inline else r.raw) not in new_keys]


def edit_view(body: str, old: str, new: str) -> str:
    """Run ``edit_document`` on the text with placeholders and insert the images again.

    Args:
        body: Previous body.
        old: Passage (exactly once in the placeholder view).
        new: Replacement.

    Returns:
        New body with the original images.

    Raises:
        PkmError: ``not_found`` or ``ambiguous``.
    """
    view = images.to_placeholders(body)
    n = count_overlapping(view, old)
    if n == 0:
        raise PkmError("not_found", "The passage `old` does not occur in the document.")
    if n > 1:
        raise PkmError("ambiguous", f"The passage `old` occurs {n} times.", count=n)
    return restore_body(body, view.replace(old, new, 1))


# Fixing **********************************************************************
def fix_document(  # pylint: disable=too-many-arguments,too-many-locals
    writer: Writer, target: str, expected_hash: str | None, *, images_only: list[str] | None = None,
    image_alt: dict[str, str] | None = None, apply: bool = False, confirm_shortening: bool = False,
    note: str | None = None, source: str = "chat", areas: tuple[str, ...] = ("documents/", "scratch/"),
) -> dict[str, Any]:
    """Tool ``fix_images``: fix the notation of nonconforming image data URIs of a document (4.9, 7.2).

    Without ``apply`` only a proposal (``proposal``) with findings and a diff in placeholder notation. With
    ``apply`` a new version in which only the image notation changes (commit with ``PKM-Fix: images``).

    Args:
        writer: Writer.
        target: Document.
        expected_hash: Hash from ``read``.
        images_only: Only these images (names from ``image_issues``).
        image_alt: Alt texts per name.
        apply: Write instead of only proposing.
        confirm_shortening: Removal of unused definitions confirmed.
        note: Change note.
        source: ``chat``, ``agent`` or ``user``.
        areas: Allowed areas.

    Returns:
        ``proposal``/``unchanged``/return value of ``finish`` with ``image_issues`` (remaining findings).

    Raises:
        PkmError: ``forbidden`` outside the areas, ``conflict``, ``ambiguous``, ``large_shortening``.
    """
    with writer.lock():
        doc = writer.editable_doc(target)
        if not doc.rel.startswith(areas):
            raise PkmError("forbidden", "fix_images is only allowed here for " + ", ".join(areas) + ".", path=doc.rel)
        if doc.versioned and apply:
            writer.require_git()
        writer.check_hash(doc, expected_hash)
        if doc.versioned and apply:
            doc = writer.commit_user_state(doc)
        assert doc.parsed is not None
        body, scratch = doc.parsed.body, not doc.versioned
        limits = writer.cfg.images
        issues = imagefix.image_issues(body, limits, scratch=scratch, section_of=section_of(doc, body))
        opts = {"names": images_only, "image_alt": image_alt, "confirm_shortening": confirm_shortening,
                "scratch": scratch, "doc_rel": doc.rel}
        if not apply:
            new_body, _ = imagefix.fix_text(body, limits, **opts)
            result: dict[str, Any] = {
                "status": "proposal" if new_body != body else "unchanged", "path": doc.rel, "image_issues": issues,
                "diff": unified_diff(images.to_placeholders(body), images.to_placeholders(new_body), "before",
                                     "after", 200),
            }
        else:
            new_body, files = imagefix.fix_text(body, limits, writer=writer, **opts)
            try:
                text = doc.parsed.frontmatter_text + new_body
                result = (writer.finish(doc, text, note or "images fixed per 4.9", source, files,
                                        "PKM-Fix: images") if doc.versioned else writer.finish_scratch(doc, text))
            except PkmError:
                remove_files(writer, files)
                raise
            result["image_issues"] = imagefix.image_issues(new_body, limits, scratch=scratch)
    return result


# Reading *********************************************************************
def section_of(doc: Doc, text: str) -> Any:
    """Function text position → section key for the body of a document.

    Args:
        doc: Document.
        text: Body.

    Returns:
        Function that returns the key for a position (``None`` without sections).
    """
    sections = list(doc.parsed.sections) if doc.parsed is not None else []

    def lookup(pos: int) -> str | None:
        """Section at a position.

        Args:
            pos: Character position in the body.

        Returns:
            Section key or ``None``.
        """
        line = text.count("\n", 0, pos)
        return next((s.key for s in sections if s.start <= line < s.end), None)

    return lookup


def read_view(
    doc: Doc, text: str, section: str | None = None, limits: Any = None
) -> tuple[str, list[dict[str, Any]]]:
    """Text for ``read``: embedded images as placeholders, plus the image list.

    Args:
        doc: Document.
        text: Read text (body or one section).
        section: Key if only one section is read.
        limits: Image limits (``ImageConfig``) for ``conforming`` and ``problems``.

    Returns:
        Tuple of (text with placeholders, image list of the body or the section).
    """
    body = doc.body or ""
    listed = images.image_summary(body, section_of(doc, body))
    if limits is not None:
        found = {i["ref"]: i["problems"] for i in imagefix.image_issues(
            body, limits, scratch=not doc.versioned, wiki=doc.area == "wiki")}
        for entry in listed:
            if entry["mode"] == "inline":
                entry["conforming"] = entry["name"] not in found
                if entry["name"] in found:
                    entry["problems"] = found[entry["name"]]
    return images.to_placeholders(text), [i for i in listed if section is None or i.get("section") == section]


def _resolve_file(svc: Any, doc_rel: str, ref: images.ImageRef) -> str:
    """Find the image file of a linked image in the vault.

    Args:
        svc: Service.
        doc_rel: Path of the document.
        ref: Image.

    Returns:
        Relative path of the file.

    Raises:
        PkmError: ``not_found``.
    """
    target = images.link_target(ref, doc_rel) or ""
    if not svc.vault.exists(target) and "/" not in target:
        matches = [r for r in svc.vault.iter_files(("documents",)) if PurePosixPath(r).name == target]
        target = matches[0] if len(matches) == 1 else target
    if not svc.vault.exists(target):
        raise PkmError("not_found", f"Image file not found: {ref.link}", image=ref.name)
    return target


def image_payload(svc: Any, target: str, image: str | None = None, as_: str = "auto") -> dict[str, Any]:
    """Tool ``read_image``: image of a document or a standalone image file.

    Args:
        svc: Service.
        target: Document or image file.
        image: Image name (omit for standalone images).
        as_: ``auto`` (PNG as image, SVG as text), ``image`` or ``svg_text``.

    Returns:
        Name, alt text, format, size, hash and depending on the format ``svg`` (text) or ``data``
        (bytes, returned by the MCP server as image content).

    Raises:
        PkmError: ``not_found``, ``invalid_argument`` (e.g. rasterizing SVG without ``PKM_SVG_RASTER``).
    """
    if as_ not in AS_VALUES:
        raise PkmError("invalid_argument", f"as must be one of {', '.join(AS_VALUES)}.")
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
            raise PkmError("unknown_image", f"Image not found: {image}",
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
    """Rasterize SVG (only with ``PKM_SVG_RASTER`` and the library installed).

    Args:
        data: SVG bytes.
        enabled: ``PKM_SVG_RASTER``.

    Returns:
        PNG bytes.

    Raises:
        PkmError: ``invalid_argument`` if rasterizing is not enabled or not available.
    """
    if not enabled:
        raise PkmError("invalid_argument", "SVG rasterizing is not enabled (PKM_SVG_RASTER); use "
                       "as=svg_text.")
    try:
        import cairosvg  # type: ignore[import-not-found]  # pylint: disable=import-outside-toplevel,import-error
    except ImportError as exc:
        raise PkmError("invalid_argument", "PKM_SVG_RASTER requires the library cairosvg.") from exc
    return cairosvg.svg2png(bytestring=data)

# Main ************************************************************************
