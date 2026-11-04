"""Citations: parser, resolution, show_citations, fix-/sync-citations (specification 4.2, 5.2, 7.3).

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
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import quote as urlquote

from . import hashes
from .errors import PkmError
from .frontmatter import set_fields_linewise
from .ids import is_valid_id
from .pagetext import DEF_RE, LIST_ITEM_RE, REF_RE, merge_table_refs, section_blocks
from .parse import PREAMBLE, Section, body_lines, normalize_key_input
from .vault import Doc, is_markdown, load_text_doc
from .wikigen import wiki_pages, write_if_changed

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

REF_GROUP_RE = re.compile(r"((?:\[\^[^\]\s]+\](?!:))+)")
LINK_RE = re.compile(r"^!?\[\[([^\]\|#]*)(?:#([^\]\|]*))?(?:\|[^\]]*)?\]\]")
SEP_RE = re.compile(r"\s+·\s+")
PAGE_ANCHOR_RE = re.compile(r"page=(\d+)")
SHA_VALUE_RE = re.compile(r"[0-9a-f]{6,64}")
QUOTE_PAIRS = (("„", "“"), ("“", "”"), ('"', '"'), ("»", "«"), ("«", "»"))
MAX_QUOTE = 200
MAX_EXCERPT = 1500
MAX_UNKNOWN_PART = 40
CONTENT_SECTIONS = ("Content", "Contradictions / open questions", "Inhalt", "Widersprüche / offene Fragen")

# Classes *********************************************************************


@dataclass
class Citation:  # pylint: disable=too-many-instance-attributes
    """A citation (footnote definition) per 4.2.

    Attributes:
        label: Footnote name, e.g. ``b1``.
        line: Line index of the definition in the body.
        raw: Text after ``[^label]:``.
        path: Link target as written (without anchor).
        anchor: Anchor (heading or ``page=n``).
        page: PDF page for ``#page=n``.
        explicit_key: Exact section key from ``§:``.
        quote: Literal quote.
        doc_id: ``id:``.
        version: ``v:``.
        sha: ``sha:`` (prefix of the section or file hash).
        problems: Format errors.
    """

    label: str
    line: int
    raw: str
    path: str | None = None
    anchor: str | None = None
    page: int | None = None
    explicit_key: str | None = None
    quote: str | None = None
    doc_id: str | None = None
    version: int | None = None
    sha: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def markdown(self) -> bool:
        """Whether the citation points to a Markdown document.

        Returns:
            ``True`` without extension or for ``.md``.
        """
        return not self.path or PurePosixPath(self.path).suffix.lower() in ("", ".md")

    @property
    def target_rel(self) -> str | None:
        """Path of the target file.

        Returns:
            Path with ``.md`` for Markdown, otherwise as written; ``None`` without a link.
        """
        result = self.path
        if self.path and self.markdown and not self.path.lower().endswith(".md"):
            result = f"{self.path}.md"
        return result

    @property
    def link_path(self) -> str | None:
        """Path as it appears in the wikilink.

        Returns:
            Path without ``.md``; ``None`` without a link.
        """
        return self.path[:-3] if self.path and self.path.lower().endswith(".md") else self.path

    @property
    def section_key(self) -> str | None:
        """Cited section.

        Returns:
            ``§:`` key, otherwise the anchor as key, otherwise ``_preamble``; ``None`` for attachments.
        """
        key = None
        if self.markdown:
            key = self.explicit_key or (normalize_key_input(self.anchor) if self.anchor else PREAMBLE)
        return key


@dataclass
class Statement:
    """Statement (paragraph or list item) with its footnotes.

    Attributes:
        text: Text without footnote marks.
        labels: Footnotes in the paragraph.
        section: Section key.
        line: Line index in the body.
        segments: Text pieces each up to the next footnote group, with its footnotes.
    """

    text: str
    labels: list[str]
    section: str
    line: int
    segments: list[tuple[str, list[str]]] = field(default_factory=list)

    def labels_for(self, needle: str) -> list[str]:
        """Citations for a piece of text.

        Args:
            needle: Normalized piece of text (see ``norm_ws``).

        Returns:
            The footnotes directly after the passage, otherwise those of the whole paragraph.
        """
        hit = next((labels for text, labels in self.segments if needle in norm_ws(text)), None)
        return hit or self.labels


@dataclass
class PageCitations:
    """All citations and statements of a wiki page.

    Attributes:
        doc: The page.
        definitions: Footnote definitions per name.
        references: Footnote references as (name, line index).
        statements: Statements in document order.
    """

    doc: Doc
    definitions: dict[str, Citation]
    references: list[tuple[str, int]]
    statements: list[Statement]

    def labels_in_order(self) -> list[str]:
        """Footnote names in order of use, then unused definitions.

        Returns:
            Names without duplicates.
        """
        return list(dict.fromkeys([label for label, _ in self.references] + list(self.definitions)))

    def statement_for(self, label: str) -> str | None:
        """First statement that uses a footnote.

        Args:
            label: Footnote name.

        Returns:
            Statement text or ``None``.
        """
        return next((st.text for st in self.statements if label in st.labels), None)


@dataclass
class Resolution:  # pylint: disable=too-many-instance-attributes
    """Result of resolving a citation per 5.2.

    Attributes:
        status: ``ok``, ``moved``, ``newer_version`` or ``missing``.
        current_path: Current path of the original.
        moved: Whether the original was found elsewhere via ID or hash.
        doc: Current original (Markdown only).
        current_version: Current version (Markdown only).
        cited_text: Cited section in the cited version.
        cited_sections: Section hashes of the cited version.
    """

    status: str
    current_path: str | None
    moved: bool
    doc: Doc | None
    current_version: int | None
    cited_text: str | None = None
    cited_sections: dict[str, str] | None = None


class Resolver:
    """Resolves citations; remembers loaded versions and attachment hashes."""

    def __init__(self, svc: Service) -> None:
        """Create the resolver.

        Args:
            svc: Service.
        """
        self.svc = svc
        self._versions: dict[tuple[str, int], Doc | None] = {}
        self._bin_index: dict[str, list[str]] | None = None

    def version_doc(self, doc_id: str, version: int) -> Doc | None:
        """Document in a version from Git.

        Args:
            doc_id: Document ID.
            version: Version number.

        Returns:
            The document or ``None`` if the version is not in the history.
        """
        key = (doc_id, version)
        if key not in self._versions:
            try:
                path, text = self.svc.text_at_version(doc_id, version)
                self._versions[key] = load_text_doc(path, text.encode("utf-8"))
            except PkmError:
                self._versions[key] = None
        return self._versions[key]

    def _bins(self) -> dict[str, list[str]]:
        """Hash → paths of all attachments below ``documents/`` (computed once).

        Returns:
            Mapping of SHA-256 to paths.
        """
        if self._bin_index is None:
            index: dict[str, list[str]] = {}
            for rel in self.svc.vault.iter_files(("documents",)):
                if not is_markdown(rel):
                    try:
                        index.setdefault(hashes.sha256_bytes(self.svc.vault.path(rel).read_bytes()), []).append(rel)
                    except OSError:
                        continue
            self._bin_index = index
        return self._bin_index

    def _load(self, rel: str | None) -> Doc | None:
        """Load a file below ``documents/`` if it exists.

        Args:
            rel: Relative path or ``None``.

        Returns:
            The document or ``None``.
        """
        doc = None
        try:
            if rel and rel.startswith("documents/") and self.svc.vault.exists(rel):
                doc = self.svc.vault.load(rel)
        except PkmError:
            doc = None
        return doc

    def _find_markdown(self, cit: Citation) -> tuple[Doc | None, bool]:
        """Find the original for a Markdown citation: first the path with a matching ID, then the ID.

        Args:
            cit: Citation.

        Returns:
            Tuple of (document or ``None``, moved).
        """
        doc, moved = None, False
        candidate = self._load(cit.target_rel)
        if candidate is not None and (cit.doc_id is None or candidate.id == cit.doc_id):
            doc = candidate
        elif cit.doc_id and is_valid_id(cit.doc_id):
            found = [p for p in self.svc.find_id(cit.doc_id) if p.startswith("documents/")]
            if found:
                doc, moved = self._load(found[0]), True
        return doc, moved

    def resolve(self, cit: Citation) -> Resolution:
        """Resolve a citation and determine its status (5.2).

        Args:
            cit: Citation.

        Returns:
            The resolution; for Markdown with the cited section from the cited version.
        """
        if not cit.markdown:
            result = self._resolve_bin(cit)
        else:
            doc, moved = self._find_markdown(cit)
            cited = self.version_doc(cit.doc_id, cit.version) if cit.doc_id and cit.version else None
            if cited is None and doc is not None and not self.svc.versioning:
                cited = _current_as_cited(doc, cit)
            cited_text = section_text(cited, cit.section_key) if cited else None
            cited_sections = cited.hashes.sections if cited and cited.hashes else None
            if doc is None:
                result = Resolution("missing", None, False, None, None, cited_text, cited_sections)
            else:
                status = "moved" if moved else "ok"
                if cit.version is not None and doc.version is not None and cit.version < doc.version:
                    current = doc.hashes.sections.get(cit.section_key or "") if doc.hashes else None
                    if not (current and cit.sha and hashes.matches(current, cit.sha)):
                        status = "newer_version"
                result = Resolution(status, doc.rel, moved, doc, doc.version, cited_text, cited_sections)
        return result

    def _resolve_bin(self, cit: Citation) -> Resolution:
        """Resolve a citation of an attachment (path and hash, otherwise hash in the inventory).

        Args:
            cit: Citation.

        Returns:
            The resolution.
        """
        result = Resolution("missing", None, False, None, None)
        rel = cit.target_rel
        if rel and rel.startswith("documents/") and self.svc.vault.exists(rel):
            h = hashes.sha256_bytes(self.svc.vault.path(rel).read_bytes())
            if not cit.sha or hashes.matches(h, cit.sha):
                result = Resolution("ok", rel, False, None, None)
        if result.status == "missing" and cit.sha:
            paths = next((p for h, p in self._bins().items() if hashes.matches(h, cit.sha)), None)
            if paths:
                result = Resolution("moved", sorted(paths)[0], True, None, None)
        return result

# Functions *******************************************************************


def _current_as_cited(doc: Doc, cit: Citation) -> Doc | None:
    """Without version control: the current document stands in for the cited version.

    This holds if the citation names the current version or the cited section is unchanged (``sha``).

    Args:
        doc: Current original.
        cit: Markdown citation.

    Returns:
        The current document or ``None`` if the cited state is unknown.
    """
    current = doc.hashes.sections.get(cit.section_key or "") if doc.hashes else None
    same = cit.version == doc.version or bool(current and cit.sha and hashes.matches(current, cit.sha))
    return doc if same else None


def _strip_quote(part: str) -> str | None:
    """Extract a quote from a citation part.

    Args:
        part: Part between `` · ``.

    Returns:
        Text without quotes or ``None`` if the part is not a quote.
    """
    return next(
        (part[len(left) : len(part) - len(right)] for left, right in QUOTE_PAIRS
         if part.startswith(left) and part.endswith(right) and len(part) >= 2),
        None,
    )


def _parse_part(cit: Citation, part: str) -> None:
    """Evaluate one part of the citation line.

    Args:
        cit: Citation (added to).
        part: Part between `` · ``.
    """
    quote = _strip_quote(part)
    if part.startswith("§:"):
        cit.explicit_key = part[2:].strip() or None
    elif part.startswith("id:"):
        cit.doc_id = part[3:].strip()
        if not is_valid_id(cit.doc_id):
            cit.problems.append("invalid ID")
    elif part.startswith("v:"):
        value = part[2:].strip()
        if value.isdigit():
            cit.version = int(value)
        else:
            cit.problems.append("invalid version")
    elif part.startswith("sha:"):
        value = part[4:].strip().lower()
        if SHA_VALUE_RE.fullmatch(value):
            cit.sha = value
        else:
            cit.problems.append("invalid sha")
    elif quote is not None:
        cit.quote = quote
    else:
        cit.problems.append(f"unknown part: {part[:MAX_UNKNOWN_PART]}")


def _check_required(cit: Citation) -> None:
    """Check the required parts of the citation and add problems.

    Args:
        cit: Citation (added to).
    """
    if cit.sha is None:
        cit.problems.append("sha missing")
    if cit.markdown:
        missing = [name for name, value in (("id", cit.doc_id), ("v", cit.version)) if value is None]
        cit.problems.extend(f"{name} missing" for name in missing)
        if cit.quote is None:
            cit.problems.append("quote missing")
    if cit.quote is not None and len(cit.quote) > MAX_QUOTE:
        cit.problems.append(f"quote longer than {MAX_QUOTE} characters")


def parse_citation(label: str, rest: str, line: int) -> Citation:
    """Read a citation line per 4.2.

    Args:
        label: Footnote name.
        rest: Text after ``[^label]:``.
        line: Line index in the body.

    Returns:
        The citation; format errors are in ``problems``.
    """
    cit = Citation(label, line, rest)
    parts = [p.strip() for p in SEP_RE.split(rest.strip()) if p.strip()]
    if not parts:
        cit.problems.append("empty")
    else:
        m = LINK_RE.match(parts[0])
        if m:
            cit.path = m.group(1).strip() or None
            cit.anchor = (m.group(2) or "").strip() or None
            page = PAGE_ANCHOR_RE.fullmatch(cit.anchor or "")
            cit.page = int(page.group(1)) if page else None
            tail = parts[0][m.end() :].strip()
            parts = ([tail] if tail else []) + parts[1:]
        else:
            cit.problems.append("link missing")
        for part in parts:
            _parse_part(cit, part)
        _check_required(cit)
    return cit


def _clean_statement(text: str) -> str:
    """Remove footnote marks and list markers, collapse whitespace.

    Args:
        text: Raw text.

    Returns:
        Cleaned text.
    """
    text = LIST_ITEM_RE.sub("", REF_RE.sub("", text), count=1)
    return " ".join(text.split())


def _segments(text: str) -> list[tuple[str, list[str]]]:
    """Split text at footnote groups.

    Args:
        text: Raw text with footnote marks.

    Returns:
        List of (piece of text up to the group, footnotes of the group).
    """
    parts = REF_GROUP_RE.split(text)
    out: list[tuple[str, list[str]]] = []
    for i in range(0, len(parts), 2):
        labels = [m.group(1) for m in REF_RE.finditer(parts[i + 1])] if i + 1 < len(parts) else []
        if parts[i].strip() or labels:
            out.append((_clean_statement(parts[i]), labels))
    return out


def _block_statements(block: list[tuple[int, str]], section: str) -> list[Statement]:
    """Turn a paragraph into statements; in lists every item is a statement of its own.

    Args:
        block: Lines of the paragraph as (index, text).
        section: Section key.

    Returns:
        Statements.
    """
    items = [block] if not any(LIST_ITEM_RE.match(t) for _, t in block) else [[b] for b in block]
    out = []
    for item in items:
        if item:
            text = " ".join(t for _, t in item)
            clean = _clean_statement(text)
            if clean:
                labels = [r.group(1) for r in REF_RE.finditer(text)]
                out.append(Statement(clean, labels, section, item[0][0], _segments(text)))
    return out


def parse_page(doc: Doc) -> PageCitations:
    """Split a wiki page into citations, references and statements.

    Args:
        doc: Wiki page.

    Returns:
        The citations of the page.

    Raises:
        PkmError: If the page is not readable.
    """
    if doc.parsed is None:
        raise PkmError(doc.error or "invalid_encoding", doc.error_message or "Page not readable.", path=doc.rel)
    lines = body_lines(doc.parsed.body)
    definitions: dict[str, Citation] = {}
    references: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        m = DEF_RE.match(line)
        if m:
            definitions.setdefault(m.group(1), parse_citation(m.group(1), m.group(2), i))
        else:
            references.extend((ref.group(1), i) for ref in REF_RE.finditer(line))
    def_lines = {i for i, ln in enumerate(lines) if DEF_RE.match(ln)}
    statements: list[Statement] = []
    for sec in doc.parsed.sections:
        start = sec.start + (1 if sec.heading is not None else 0)
        blocks = merge_table_refs(section_blocks(lines, range(start, sec.end), def_lines))
        statements += [st for block in blocks if block for st in _block_statements(block, sec.key)]
    return PageCitations(doc, definitions, references, statements)


def render_section(sec: Section) -> str:
    """Section as text (heading and content, without trailing blank lines).

    Args:
        sec: Section.

    Returns:
        The text.
    """
    lines = ([sec.heading] if sec.heading else []) + list(sec.content_lines)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def section_text(doc: Doc, key: str | None) -> str | None:
    """Text of a section.

    Args:
        doc: Document.
        key: Section key.

    Returns:
        The text or ``None`` if the section does not exist.
    """
    sec = doc.parsed.section(key) if doc.parsed is not None and key is not None else None
    return render_section(sec) if sec is not None else None


def _excerpt(text: str | None) -> str | None:
    """Shorten text to ``MAX_EXCERPT`` characters.

    Args:
        text: Text or ``None``.

    Returns:
        Shortened text (with "…") or ``None``.
    """
    return text if text is None or len(text) <= MAX_EXCERPT else text[:MAX_EXCERPT] + "…"


def norm_ws(text: str) -> str:
    """Normalize text for comparisons (collapse whitespace, casefold).

    Args:
        text: Text.

    Returns:
        Normalized text.
    """
    return " ".join(text.split()).casefold()


def obsidian_link(vault_name: str | None, rel: str | None) -> str | None:
    """``obsidian://`` link to a file.

    Args:
        vault_name: Name of the Obsidian vault (``PKM_VAULT_NAME``).
        rel: Relative path.

    Returns:
        The link or ``None`` if the vault name or path is missing.
    """
    link = None
    if vault_name and rel:
        file = rel[:-3] if rel.lower().endswith(".md") else rel
        link = f"obsidian://open?vault={urlquote(vault_name, safe='')}&file={urlquote(file, safe='')}"
    return link


def citations_overview(pc: PageCitations) -> list[dict[str, Any]]:
    """Parsed citations without checking (for ``read`` of wiki pages).

    Args:
        pc: Citations of the page.

    Returns:
        Per citation path, anchor, section, quote, ID, version, sha, statement and problems.
    """
    return [
        {
            "id": c.label, "path": c.path, "anchor": c.anchor, "section": c.section_key, "quote": c.quote,
            "doc_id": c.doc_id, "version": c.version, "sha": c.sha, "statement": pc.statement_for(c.label),
            "problems": c.problems,
        }
        for c in pc.definitions.values()
    ]


def _citation_entry(
    svc: Service, pc: PageCitations, cit: Citation, res: Resolution, with_excerpt: bool
) -> dict[str, Any]:
    """Entry for ``show_citations``.

    Args:
        svc: Service.
        pc: Citations of the page.
        cit: Citation.
        res: Resolution of the citation.
        with_excerpt: Include the wording from the cited (and possibly the current) version.

    Returns:
        The entry.
    """
    entry: dict[str, Any] = {
        "id": cit.label,
        "statement": pc.statement_for(cit.label),
        "original": res.current_path,
        "anchor": cit.anchor,
        "section": cit.section_key,
        "quote": cit.quote,
        "doc_id": cit.doc_id,
        "cited_version": cit.version,
        "current_version": res.current_version,
        "status": res.status,
    }
    if cit.problems:
        entry["problems"] = cit.problems
    if with_excerpt and cit.markdown:
        entry["cited_excerpt"] = _excerpt(res.cited_text)
        current = section_text(res.doc, cit.section_key) if res.doc else None
        if current is not None and current != res.cited_text:
            entry["current_excerpt"] = _excerpt(current)
    link = obsidian_link(svc.cfg.vault_name, res.current_path)
    if link:
        entry["obsidian_link"] = link
    return entry


def show_citations(
    svc: Service, target: str, statement: str | None = None, with_excerpt: bool = False
) -> dict[str, Any]:
    """Tool ``show_citations``.

    Args:
        svc: Service.
        target: Wiki page.
        statement: Piece of text; narrows to the citations of this passage or paragraph.
        with_excerpt: Wording from the cited and possibly the current version (at most 1,500 characters each).

    Returns:
        Page and citations with original, section, quote, versions, status and possibly Obsidian link.

    Raises:
        PkmError: ``not_found`` if ``statement`` does not occur on the page.
    """
    rel = svc.resolve(target, ("wiki",))
    pc = parse_page(svc.vault.load(rel))
    labels = pc.labels_in_order()
    if statement:
        needle = norm_ws(statement)
        matching = [st for st in pc.statements if needle in norm_ws(st.text)]
        if not matching:
            raise PkmError("not_found", "No statement with this text found on the page.", page=rel)
        wanted = {lab for st in matching for lab in st.labels_for(needle)}
        labels = [lab for lab in labels if lab in wanted]
    resolver = Resolver(svc)
    out = []
    for label in labels:
        cit = pc.definitions.get(label)
        if cit is None:
            out.append({"id": label, "status": "missing_definition", "statement": pc.statement_for(label)})
        else:
            out.append(_citation_entry(svc, pc, cit, resolver.resolve(cit), with_excerpt))
    return {"status": "ok", "page": rel, "citations": out}


def wiki_targets(svc: Service, pages: list[str] | None) -> list[str]:
    """Wiki pages to process.

    Args:
        svc: Service.
        pages: Given pages or ``None`` for all.

    Returns:
        Relative paths.
    """
    return [svc.resolve(p, ("wiki",)) for p in pages] if pages else [d.rel for d in wiki_pages(svc)]


def _render_first(link_path: str, key: str | None, page: int | None) -> str:
    """Build the first part of a citation line (link with anchor, possibly ``§:``).

    Args:
        link_path: Path without ``.md``.
        key: Section key.
        page: PDF page.

    Returns:
        Z. B. ``[[documents/a#Notizen]] §:Notizen#2``.
    """
    anchor = None
    explicit = None
    if page is not None:
        anchor = f"page={page}"
    elif key and key != PREAMBLE:
        base, sep, num = key.rpartition("#")
        if sep and num.isdigit() and base:
            anchor, explicit = base, key
        else:
            anchor = key
    link = f"[[{link_path}{'#' + anchor if anchor else ''}]]"
    return link + (f" §:{explicit}" if explicit else "")


def rewrite_definition(cit: Citation, link_path: str, key: str | None) -> str:
    """Citation line with a new path or section; the other parts are kept.

    Args:
        cit: Citation.
        link_path: New path without ``.md``.
        key: New section key.

    Returns:
        The new line.
    """
    parts = [p.strip() for p in SEP_RE.split(cit.raw.strip()) if p.strip()]
    m = LINK_RE.match(parts[0]) if parts else None
    tail = parts[0][m.end():].strip() if m else ""
    rest = [p for p in ([tail] if tail else []) + parts[1:] if not p.startswith("§:")]
    return f"[^{cit.label}]: " + " · ".join([_render_first(link_path, key, cit.page), *rest])


def _fixed_target(cit: Citation, res: Resolution) -> tuple[str | None, str | None]:
    """Determine the new path and section of a citation (moved or renamed).

    Args:
        cit: Citation.
        res: Resolution.

    Returns:
        Tuple of (path without ``.md``, section key).
    """
    new_path = cit.link_path
    if res.moved and res.current_path:
        new_path = res.current_path[:-3] if res.current_path.lower().endswith(".md") else res.current_path
    new_key = cit.section_key
    sections = res.doc.hashes.sections if res.doc is not None and res.doc.hashes else {}
    if sections and new_key and new_key not in sections and cit.sha:
        match = [k for k, h in sections.items() if hashes.matches(h, cit.sha)]
        if len(match) == 1:
            new_key = match[0]
    return new_path, new_key


def _fix_page(svc: Service, rel: str, resolver: Resolver) -> list[dict[str, str]]:
    """Fix the citations of a page and write the page.

    Args:
        svc: Service.
        rel: Wiki page.
        resolver: Resolver.

    Returns:
        Changed lines as (id, old, new).
    """
    doc = svc.vault.load(rel)
    changes: list[dict[str, str]] = []
    if doc.parsed is not None and not doc.error:
        lines = body_lines(doc.parsed.body)
        moved: dict[str, str] = {}
        definitions = parse_page(doc).definitions.values()
        for cit in definitions:
            if cit.path:
                new_path, new_key = _fixed_target(cit, resolver.resolve(cit))
                new_line = rewrite_definition(cit, new_path or "", new_key)
                if new_path and cit.link_path and new_path != cit.link_path:
                    moved[cit.link_path] = new_path
                if (new_path, new_key) != (cit.link_path, cit.section_key) and new_line != lines[cit.line]:
                    changes.append({"id": cit.label, "old": lines[cit.line], "new": new_line})
                    lines[cit.line] = new_line
        def_lines = {c.line for c in definitions}
        changes += _relink_lines(lines, moved, def_lines)
        if changes:
            write_if_changed(svc, rel, doc.parsed.frontmatter_text + "\n".join(lines) + "\n")
            sync_citations(svc, [rel])
    return changes


def _relink_lines(lines: list[str], moved: dict[str, str], skip: set[int]) -> list[dict[str, str]]:
    """Rewrite wikilinks in the page text to moved originals.

    Args:
        lines: Lines of the body (changed).
        moved: Old path without ``.md`` → new path.
        skip: Lines that are not touched (footnote definitions).

    Returns:
        Changes as (id, old, new) with ``id: link``.
    """
    changes: list[dict[str, str]] = []
    if moved:
        rx = re.compile(r"(!?\[\[)(" + "|".join(re.escape(p) for p in sorted(moved, key=len, reverse=True))
                        + r")(\.md)?(?=[\]#|])")
        for i, line in enumerate(lines):
            if i not in skip:
                new = rx.sub(lambda m: m.group(1) + moved[m.group(2)], line)
                if new != line:
                    changes.append({"id": "link", "old": line, "new": new})
                    lines[i] = new
    return changes


def fix_citations(svc: Service, pages: list[str] | None = None) -> dict[str, Any]:
    """``pkm fix-citations``: fix citations of moved originals and renamed sections.

    Args:
        svc: Service.
        pages: Wiki pages or ``None`` for all.

    Returns:
        Number of changed pages and the changes.
    """
    resolver = Resolver(svc)
    changes = []
    for rel in wiki_targets(svc, pages):
        page_changes = _fix_page(svc, rel, resolver)
        if page_changes:
            changes.append({"page": rel, "changes": page_changes})
    return {"status": "ok", "pages_changed": len(changes), "changes": changes}


def expected_sources(pc: PageCitations) -> list[str]:
    """``sources`` from the footnotes.

    Args:
        pc: Citations of the page.

    Returns:
        Sorted, unique wikilinks to the originals.
    """
    return sorted({f"[[{c.link_path}]]" for c in pc.definitions.values() if c.link_path})


def sync_citations(svc: Service, pages: list[str] | None = None) -> dict[str, Any]:
    """``pkm sync-citations``: regenerate ``sources`` from the footnotes.

    Args:
        svc: Service.
        pages: Wiki pages or ``None`` for all.

    Returns:
        Number of changed pages and the new ``sources``.
    """
    changed = []
    for rel in wiki_targets(svc, pages):
        doc = svc.vault.load(rel)
        if doc.parsed is not None and not doc.error:
            sources = expected_sources(parse_page(doc))
            if doc.meta.get("sources") != sources:
                write_if_changed(svc, rel, set_fields_linewise(doc.text or "", {"sources": sources}, block_lists=True))
                changed.append({"page": rel, "sources": sources})
    return {"status": "ok", "pages_changed": len(changed), "changes": changed}


def page_citations_for_read(doc: Doc) -> list[dict[str, Any]]:
    """Citations of a wiki page for ``read`` (without checking).

    Args:
        doc: Wiki page.

    Returns:
        Overview of the citations; empty if the page is not readable.
    """
    try:
        overview = citations_overview(parse_page(doc))
    except PkmError:
        overview = []
    return overview

# Main ************************************************************************
