"""Vault model: find, load and address files (specification 3, 7.1).

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

import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from . import hashes
from .config import Config
from .errors import PkmError
from .ids import is_valid_id
from .normalize import normalize_bytes
from .parse import PREAMBLE, Parsed, parse
from .paths import nfc, safe_resolve
from .schema import citation_key, short_citation

# Variables *******************************************************************

AREAS = ("documents", "wiki")
SCRATCH = "scratch"
READ_AREAS = ("documents", "wiki", SCRATCH)
ALL_AREAS = READ_AREAS
WIKILINK_RE = re.compile(r"!?\[\[([^\]\|#]*)(?:#([^\]\|]*))?(?:\|[^\]]*)?\]\]")
FULL_WIKILINK_RE = re.compile(r"!?\[\[([^\]\|#]*)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
SUMMARY_LABEL_RE = re.compile(r"^\*\*[^*]+:\*\*\s*")
MAX_SUMMARY_WIKI = 400
MAX_SUMMARY_DOC = 200
ID_SCAN_BYTES = 4096

__all__ = [
    "ALL_AREAS", "AREAS", "PREAMBLE", "READ_AREAS", "SCRATCH", "Doc", "Vault", "extract_links", "link_key",
    "load_text_doc", "summary_of",
]

# Classes *********************************************************************


@dataclass
class Doc:  # pylint: disable=too-many-instance-attributes
    """A file in the vault (Markdown or attachment).

    Attributes:
        rel: Relative path with ``/`` in NFC.
        kind: ``md`` or ``bin``.
        size: File size in bytes.
        mtime_ns: Modification time in nanoseconds.
        text: Normalized text (Markdown only, ``None`` for an invalid encoding).
        parsed: Parsed document (Markdown only).
        hashes: Hashes per 4.8 (Markdown only).
        bin_hash: SHA-256 of the raw bytes (attachments only).
        error: ``invalid_encoding`` or ``invalid_frontmatter``.
        error_message: Explanation of the error.
    """

    rel: str
    kind: str
    size: int
    mtime_ns: int
    text: str | None = None
    parsed: Parsed | None = None
    hashes: hashes.DocHashes | None = None
    bin_hash: str | None = None
    error: str | None = None
    error_message: str | None = None

    @property
    def area(self) -> str:
        """Area of the file.

        Returns:
            ``documents``, ``wiki`` or ``scratch``.
        """
        return self.rel.split("/", 1)[0]

    @property
    def meta(self) -> dict[str, Any]:
        """Frontmatter fields.

        Returns:
            The fields; empty for attachments or an invalid frontmatter.
        """
        return self.parsed.meta if self.parsed else {}

    @property
    def id(self) -> str | None:
        """Document ID from the frontmatter.

        Returns:
            The ID if it is valid, otherwise ``None``.
        """
        value = self.meta.get("id")
        return value if is_valid_id(value) else None

    @property
    def version(self) -> int | None:
        """Version number from the frontmatter.

        Returns:
            The version as an integer or ``None``.
        """
        value = self.meta.get("version")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def short_citation(self) -> str | None:
        """Short citation from ``short_citation`` (also the old notation ``short citation``).

        Returns:
            The short citation or ``None``.
        """
        return short_citation(self.meta)

    @property
    def stem(self) -> str:
        """File name without extension.

        Returns:
            The stem of the file name.
        """
        return PurePosixPath(self.rel).stem

    @property
    def title(self) -> str:
        """Title for display and commits.

        Returns:
            ``title`` from the frontmatter, otherwise the first level-1 heading, otherwise the
            file name (with extension for attachments).
        """
        t = self.meta.get("title")
        result = t.strip() if isinstance(t, str) and t.strip() else ""
        if not result and self.parsed:
            result = next((s.key for s in self.parsed.sections if s.level == 1), "")
        if not result:
            result = self.stem if self.kind == "md" else PurePosixPath(self.rel).name
        return result

    @property
    def editable(self) -> bool:
        """Whether the file may be changed via MCP.

        Returns:
            ``True`` for valid Markdown files below ``documents/`` and ``scratch/``.
        """
        return self.area in ("documents", SCRATCH) and self.kind == "md" and self.error is None

    @property
    def versioned(self) -> bool:
        """Whether the file is versioned (``scratch/`` never, specification 3).

        Returns:
            ``False`` for files in ``scratch/``.
        """
        return self.area != SCRATCH

    @property
    def link_path(self) -> str:
        """Path as it appears in wikilinks.

        Returns:
            Markdown without ``.md``, attachments with extension.
        """
        return self.rel[:-3] if self.kind == "md" else self.rel

    @property
    def wikilink(self) -> str:
        """Wikilink to the file.

        Returns:
            ``[[<link_path>]]``.
        """
        return f"[[{self.link_path}]]"

    @property
    def body(self) -> str:
        """Body without frontmatter.

        Returns:
            The body or an empty text if the file is not readable.
        """
        return self.parsed.body if self.parsed is not None else ""

    def link_keys(self) -> set[str]:
        """Keys under which wikilinks point to this file.

        Returns:
            Full link path and file name (without ``.md``), each casefolded.
        """
        name = self.stem if self.kind == "md" else PurePosixPath(self.rel).name
        return {self.link_path.casefold(), name.casefold()}


class Vault:
    """Access to the files below ``documents/`` and ``wiki/``."""

    def __init__(self, cfg: Config) -> None:
        """Create the vault access.

        Args:
            cfg: Configuration.
        """
        self.cfg = cfg
        self.root = cfg.root

    # Inventory ****************************************************************

    def iter_files(self, areas: tuple[str, ...] = AREAS) -> Iterator[str]:
        """Iterate over all files of the areas (hidden files and folders excluded).

        Args:
            areas: Areas, e.g. ``("documents",)``.

        Yields:
            Relative paths in NFC, sorted per folder.
        """
        for area in areas:
            base = self.root / area
            if base.is_dir():
                for dirpath, dirnames, filenames in os.walk(base):
                    dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
                    for name in sorted(filenames):
                        if not name.startswith("."):
                            yield nfc((Path(dirpath) / name).relative_to(self.root).as_posix())

    def path(self, rel: str) -> Path:
        """Resolve a relative path safely within the vault.

        Args:
            rel: Relative path.

        Returns:
            Path in the vault.

        Raises:
            PkmError: ``invalid_path`` for disallowed paths.
        """
        return safe_resolve(self.root, rel)

    def exists(self, rel: str) -> bool:
        """Check whether a file exists.

        Args:
            rel: Relative path.

        Returns:
            ``True`` if it is a file.
        """
        return self.path(rel).is_file()

    def load(self, rel: str) -> Doc:
        """Load a file and (for Markdown) parse and hash it.

        Args:
            rel: Relative path.

        Returns:
            The document.

        Raises:
            PkmError: ``not_found`` if the file is missing.
        """
        p = self.path(rel)
        if not p.is_file():
            raise PkmError("not_found", f"File not found: {rel}", target=rel)
        st = p.stat()
        if is_markdown(rel):
            doc = load_text_doc(rel, p.read_bytes(), st.st_size, st.st_mtime_ns)
        else:
            doc = Doc(rel, "bin", st.st_size, st.st_mtime_ns, bin_hash=hashes.sha256_bytes(p.read_bytes()))
        return doc

    # Addressing (7.1) *********************************************************

    def resolve(
        self,
        target: str,
        areas: tuple[str, ...] = AREAS,
        find_id: Callable[[str], list[str]] | None = None,
        find_citation: Callable[[str], list[str]] | None = None,
    ) -> str:
        """Resolve a target (path, wikilink, short name, ``id:`` or short citation) into a relative path.

        If no path and no short name matches, ``short_citation`` is compared (7.1).

        Args:
            target: Target, e.g. ``documents/house/cistern.md``, ``[[cistern]]``, ``id:d-…`` or
                ``EN 61000-4-6:2014``.
            areas: Allowed areas.
            find_id: Search by ID (e.g. via the index); ``scan_id`` if omitted.
            find_citation: Search by short citation; ``scan_citation`` if omitted.

        Returns:
            Relative path of the file found.

        Raises:
            PkmError: ``not_found``, ``ambiguous`` (with candidates), ``forbidden`` or ``invalid_path``.
        """
        if not isinstance(target, str) or not target.strip():
            raise PkmError("not_found", "Empty target.")
        t = nfc(target.strip())
        if t.startswith("id:"):
            rel = self._resolve_id(t[3:].strip(), target, areas, find_id)
        else:
            try:
                m = FULL_WIKILINK_RE.fullmatch(t)
                name = (m.group(1).strip() if m else t).replace("\\", "/").strip("/")
                resolver = self._resolve_path if "/" in name else self._resolve_short
                rel = resolver(name, target, areas)
            except PkmError as exc:
                if exc.status not in ("not_found", "invalid_path"):
                    raise
                found = [r for r in (find_citation or self.scan_citation)(t) if r.split("/", 1)[0] in areas]
                if not found:
                    raise
                rel = _one(found, target)
        return rel

    def _resolve_id(
        self, doc_id: str, target: str, areas: tuple[str, ...], find_id: Callable[[str], list[str]] | None
    ) -> str:
        """Resolve a target via the document ID.

        Args:
            doc_id: Document ID.
            target: Original target (for error messages).
            areas: Allowed areas.
            find_id: Search by ID or ``None`` for ``scan_id``.

        Returns:
            Relative path.

        Raises:
            PkmError: ``not_found`` or ``ambiguous``.
        """
        if not is_valid_id(doc_id):
            raise PkmError("not_found", f"Invalid ID: {doc_id}", target=target)
        found = [r for r in (find_id or self.scan_id)(doc_id) if r.split("/", 1)[0] in areas]
        return _one(found, target)

    def _resolve_path(self, t: str, target: str, areas: tuple[str, ...]) -> str:
        """Resolve a target containing ``/`` as a path (with or without ``.md``).

        Args:
            t: Cleaned path.
            target: Original target (for error messages).
            areas: Allowed areas.

        Returns:
            Relative path.

        Raises:
            PkmError: ``not_found``, ``forbidden`` or ``invalid_path``.
        """
        found = next((p for p in (self.path(t), self.path(f"{t}.md")) if p.is_file()), None)
        if found is None:
            raise PkmError("not_found", f"Not found: {target}", target=target)
        rel = nfc(found.relative_to(self.root).as_posix())
        if rel.split("/", 1)[0] not in areas:
            raise PkmError("forbidden", f"Only {', '.join(areas)} are allowed here.", target=target)
        return rel

    def _resolve_short(self, t: str, target: str, areas: tuple[str, ...]) -> str:
        """Resolve short names without folder (file name without extension, case-insensitive).

        Args:
            t: Short name.
            target: Original target (for error messages).
            areas: Allowed areas.

        Returns:
            Relative path.

        Raises:
            PkmError: ``not_found`` or ``ambiguous``.
        """
        key = link_key(t)
        found = []
        for rel in self.iter_files(areas):
            name = PurePosixPath(rel).name
            stem = name[:-3] if is_markdown(name) else name
            if key in (stem.casefold(), name.casefold()):
                found.append(rel)
        return _one(found, target)

    def scan_id(self, doc_id: str) -> list[str]:
        """Search an ID without the index (slow, fallback).

        Args:
            doc_id: Document ID.

        Returns:
            All Markdown files with this ID.
        """
        needle = doc_id.encode()
        found = []
        for rel in self.iter_files():
            if is_markdown(rel) and needle in self._head(rel) and self.load(rel).id == doc_id:
                found.append(rel)
        return found

    def scan_citation(self, value: str) -> list[str]:
        """Search a short citation without the index (slow, fallback).

        Args:
            value: Short citation, e.g. ``EN 61000-4-6:2014``.

        Returns:
            Markdown files in ``documents/`` whose ``short_citation`` matches.
        """
        key = citation_key(value)
        found = []
        for rel in self.iter_files(("documents",)):
            if is_markdown(rel) and b"citation" in self._head(rel):
                cit = self.load(rel).short_citation
                if cit and citation_key(cit) == key:
                    found.append(rel)
        return found

    def _head(self, rel: str) -> bytes:
        """Read the beginning of a file (for the fast ID search).

        Args:
            rel: Relative path.

        Returns:
            The first bytes or empty bytes if the file is not readable.
        """
        try:
            data = self.path(rel).read_bytes()[:ID_SCAN_BYTES]
        except OSError:
            data = b""
        return data

# Functions *******************************************************************


def _one(found: list[str], target: str) -> str:
    """Require exactly one hit.

    Args:
        found: Paths found.
        target: Original target (for error messages).

    Returns:
        The only hit.

    Raises:
        PkmError: ``not_found`` without a hit, ``ambiguous`` with candidates for several.
    """
    if not found:
        raise PkmError("not_found", f"Not found: {target}", target=target)
    if len(found) > 1:
        raise PkmError("ambiguous", f"Ambiguous: {target}", target=target, candidates=sorted(found))
    return found[0]


def is_markdown(rel: str) -> bool:
    """Check whether a path denotes a Markdown file.

    Args:
        rel: Path or file name.

    Returns:
        ``True`` for the extension ``.md`` (case-insensitive).
    """
    return rel.lower().endswith(".md")


def load_text_doc(rel: str, data: bytes, size: int = 0, mtime_ns: int = 0) -> Doc:
    """Load a Markdown document from bytes.

    Args:
        rel: Relative path.
        data: File content.
        size: File size; the length of ``data`` if omitted.
        mtime_ns: Modification time.

    Returns:
        The document; on errors ``error`` and ``error_message`` are set.
    """
    doc = Doc(rel, "md", size or len(data), mtime_ns)
    try:
        text = normalize_bytes(data)
    except PkmError as exc:
        doc.error, doc.error_message = exc.status, exc.message
        text = None
    if text is not None:
        doc.text = text
        doc.parsed = parse(text)
        if doc.parsed.fm_error:
            doc.error, doc.error_message = "invalid_frontmatter", doc.parsed.fm_error
        doc.hashes = hashes.compute(text, doc.parsed)
    return doc


def extract_links(body: str) -> list[str]:
    """Collect wikilink targets from a text.

    Args:
        body: Markdown text.

    Returns:
        Targets without anchor and alias, without duplicates, in order of appearance.
    """
    seen: list[str] = []
    for m in WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.append(target)
    return seen


def link_key(target: str) -> str:
    """Make a wikilink target comparable.

    Args:
        target: Link target.

    Returns:
        Target in NFC, with ``/``, without ``.md``, casefolded.
    """
    t = nfc(target.strip()).replace("\\", "/")
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.casefold()


def summary_of(doc: Doc) -> str:
    """Summary of a document.

    Args:
        doc: Document.

    Returns:
        For wiki pages the first quote after the frontmatter (without a bold label like
        "Summary:"), for documents the first quote or the first paragraph; otherwise empty.
    """
    summary = ""
    if doc.parsed is not None:
        lines = [ln.lstrip() for ln in doc.parsed.body_lines]
        i = next((n for n, ln in enumerate(lines) if ln.strip()), len(lines))
        if i < len(lines) and lines[i].startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            summary = SUMMARY_LABEL_RE.sub("", " ".join(q for q in quote if q))[:MAX_SUMMARY_WIKI]
        elif doc.area != "wiki":
            summary = _first_paragraph(doc.parsed)[:MAX_SUMMARY_DOC]
    return summary


def _first_paragraph(parsed: Parsed) -> str:
    """Find the first paragraph across all sections.

    Args:
        parsed: Parsed document.

    Returns:
        The first paragraph (lines joined with spaces) or an empty text.
    """
    para: list[str] = []
    for section in parsed.sections:
        for line in section.content_lines:
            if line.strip():
                para.append(line.strip())
            elif para:
                break
        if para:
            break
    return " ".join(para)


def section_summary(doc: Doc) -> list[dict[str, Any]]:
    """Section overview for ``read``.

    Args:
        doc: Document.

    Returns:
        Per section key, level and short hash (``empty: true`` for sections without text of their
        own); empty for unreadable files.
    """
    result: list[dict[str, Any]] = []
    if doc.parsed is not None and doc.hashes is not None:
        sections = doc.hashes.sections
        result = [
            {"key": s.key, "level": s.level, "sha": hashes.short(sections[s.key])}
            | ({"empty": True} if sections[s.key] == hashes.EMPTY_HASH else {})
            for s in doc.parsed.sections
        ]
    return result


# Main ************************************************************************
