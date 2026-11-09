"""``pkm lint`` (specification 8, 4.8): structure, citations, documents, platform. JSON report.

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
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from . import hashes
from .citations import CONTENT_SECTIONS, Citation, Resolution, Resolver, expected_sources, norm_ws, parse_page
from .cloudsync import conflict_copies
from .errors import PkmError
from .frontmatter import fix_frontmatter_text
from .imagelint import check_images, has_image, image_quote
from .namelint import check_names
from .parse import Section, body_lines, find_setext
from .parse import parse as parse_text
from .paths import case_collisions, is_platform_safe_name, slugify
from .schema import (
    DATE_FIELDS,
    KINDS,
    LEGACY_SHORT_CITATION,
    is_valid_date_value,
    looks_converted,
)
from .sourcelint import check_sources
from .vault import Doc, extract_links, is_markdown, link_key, summary_of
from .wikigen import FOLDER_TYPES, page_type, wiki_pages, write_if_changed

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

WIKI_TYPES = ("topic", "entity", "summary", "synthesis")
CONFIDENCE = ("high", "medium", "low")
BAD_ANCHOR_CHARS = set("#^[]|")
SUFFIX_LIKE_RE = re.compile(r"#([0-9]+)$")
SEVERITIES = ("error", "warning", "info")
SEVERITY_LABELS = {"error": "Errors", "warning": "Warnings", "info": "Notes"}
MIN_MISSING_PAGE_LINKS = 2
MIN_TOPIC_DOCUMENTS = 3
COVERING_TYPES = ("topic", "entity", "synthesis")  # pages whose tags cover a topic
STATEMENT_PREVIEW = 80

# Classes *********************************************************************


class Report:
    """Collects findings."""

    def __init__(self) -> None:
        """Create an empty report."""
        self.findings: list[dict[str, Any]] = []

    def add(self, check: str, severity: str, path: str | None, message: str, **detail: Any) -> None:
        """Add a finding.

        Args:
            check: Name of the check, e.g. ``broken_link``.
            severity: ``error``, ``warning`` or ``info``.
            path: Affected file or ``None``.
            message: Description.
            **detail: Additional details.
        """
        item: dict[str, Any] = {"check": check, "severity": severity, "path": path, "message": message}
        if detail:
            item["detail"] = detail
        self.findings.append(item)

    def result(self) -> dict[str, Any]:
        """Report as a JSON object.

        Returns:
            ``status``, ``summary`` (count per severity) and ``findings``.
        """
        counts = Counter(f["severity"] for f in self.findings)
        return {"status": "ok", "summary": {s: counts.get(s, 0) for s in SEVERITIES}, "findings": self.findings}


class Linter:  # pylint: disable=too-many-instance-attributes
    """Runs all checks from specification 8 and 4.8."""

    def __init__(self, svc: Service) -> None:
        """Load the vault contents.

        Args:
            svc: Service.
        """
        self.svc = svc
        self.vault = svc.vault
        self.r = Report()
        self.all_files = list(self.vault.iter_files())
        self.keys: dict[str, set[str]] = defaultdict(set)
        for rel in self.all_files:
            name = PurePosixPath(rel).name
            stem = name[:-3] if is_markdown(name) else name
            self.keys[link_key(rel)].add(rel)
            self.keys[stem.casefold()].add(rel)
            self.keys[name.casefold()].add(rel)
        self.pages = wiki_pages(svc)
        self.docs: list[Doc] = []
        for rel in self.all_files:
            if rel.startswith("documents/"):
                try:
                    self.docs.append(self.vault.load(rel))
                except PkmError:
                    continue
        self.conflicts = conflict_copies(self.all_files, {d.rel: d.id for d in self.docs if d.kind == "md"})

    def run(self) -> dict[str, Any]:
        """Run all checks.

        Returns:
            The report.
        """
        self.platform()
        self.documents()
        check_images(self.r.add, self.svc, self.docs, self.pages)
        check_names(self.r.add, self.svc, self.docs)
        self.structure()
        self.citations()
        check_sources(self.r.add, self.pages, self.docs, self.svc.cfg.ip_well_known)
        return self.r.result()

    # Platform *****************************************************************

    def platform(self) -> None:
        """Conflict copies, names that are not platform-safe and upper/lower case collisions."""
        for rel in self.all_files:
            if rel in self.conflicts:
                self.r.add("conflict_copy", "error", rel,
                           "Cloud storage conflict copy; merge the versions in Obsidian.")
            bad = next((part for part in PurePosixPath(rel).parts if not is_platform_safe_name(part)), None)
            if bad is not None:
                self.r.add("unsafe_filename", "warning", rel, f"Name '{bad}' is not valid on all systems.")
        for group in case_collisions(self.all_files):
            self.r.add("case_collision", "error", group[0], "Names differ only in upper/lower case.",
                       paths=group)

    # Documents ****************************************************************

    def documents(self) -> None:
        """ID, version, comparison with the history, duplicate IDs, encoding, frontmatter, headings."""
        by_id: dict[str, list[str]] = defaultdict(list)
        git_ok = self.svc.versioning and self.svc.git.problem() is None
        for doc in self.docs:
            if doc.kind == "md" and doc.error:
                self.r.add(doc.error, "error", doc.rel, _error_message(doc))
            elif doc.kind == "md" and doc.rel not in self.conflicts:
                self._document(doc, git_ok)
                if doc.id:
                    by_id[doc.id].append(doc.rel)
        for doc_id, paths in by_id.items():
            if len(paths) > 1:
                self.r.add("duplicate_id", "error", sorted(paths)[0], f"ID {doc_id} assigned more than once.",
                           paths=sorted(paths))

    def _document(self, doc: Doc, git_ok: bool) -> None:
        """Checks for a valid Markdown document.

        Args:
            doc: Document.
            git_ok: Whether Git is available (for the comparison with the history).
        """
        self._frontmatter(doc)
        if not doc.id:
            self.r.add("missing_id", "warning", doc.rel, "Document without a valid ID (pkm ids).")
        if doc.version is None:
            self.r.add("missing_version", "warning", doc.rel, "Document without version (pkm ids).")
        if git_ok and doc.id and doc.version is not None and not self.svc.git.is_dirty(doc.rel):
            versions = [c.version for c in self.svc.versions(doc.id) if c.path]
            if versions and versions[-1] != doc.version:
                self.r.add("version_mismatch", "error", doc.rel,
                           f"version {doc.version} does not match the history (last v{versions[-1]}).")
        self.headings(doc)

    def _frontmatter(self, doc: Doc) -> None:
        """Check the frontmatter per 4.1: provenance fields, old field names, ``kind``, date fields, ``tags``.

        Args:
            doc: Document with a valid frontmatter.
        """
        meta = doc.meta
        for field, label in (("date_markdown", "date_markdown"), ("toolchain_markdown", "toolchain_markdown")):
            if field not in meta:
                self.r.add(f"missing_{field}", "info", doc.rel, f"Field {label} is missing (not added).")
        if LEGACY_SHORT_CITATION in meta:
            self.r.add("legacy_short_citation", "info", doc.rel,
                       "Field 'short citation' with a space; pkm fix-frontmatter renames it (only on instruction).")
        if "kind" not in meta and looks_converted(meta):
            self.r.add("missing_kind", "info", doc.rel,
                       "Converted document without kind (add standard or regulation by hand).")
        elif "kind" in meta and meta["kind"] not in KINDS:
            self.r.add("invalid_kind", "error", doc.rel, f"Unknown value in kind: {meta['kind']!r}.")
        self._dates_and_tags(doc)

    def _dates_and_tags(self, doc: Doc) -> None:
        """Check the format of the date fields and the tags (documents and wiki pages).

        Args:
            doc: File with a valid frontmatter.
        """
        for field in DATE_FIELDS:
            if field in doc.meta and not is_valid_date_value(doc.meta[field]):
                self.r.add("invalid_date", "warning", doc.rel,
                           f"{field} does not have the format YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD (without time zone): "
                           f"{doc.meta[field]!r}.")
        tags = doc.meta.get("tags")
        if tags is not None and (not isinstance(tags, list) or any(" " in str(t).strip() for t in tags)):
            self.r.add("invalid_tags", "warning", doc.rel,
                       "tags must be a list without spaces in the entries.")

    def headings(self, doc: Doc) -> None:
        """Headings per 4.8: setext, duplicates, anchor characters, text ending in ``#`` plus digits.

        Args:
            doc: Document with valid content.
        """
        assert doc.parsed is not None
        for i in find_setext(body_lines(doc.parsed.body)):
            self.r.add("setext_heading", "info", doc.rel,
                       f"Setext heading (line {i + 1} of the content) is not a section boundary; please use #.")
        headings = [s for s in doc.parsed.sections if s.level]
        bases = {s.base for s in headings}
        reported: set[str] = set()
        for sec in headings:
            if sec.key != sec.base and sec.base not in reported:
                reported.add(sec.base)
                self.r.add("duplicate_heading", "warning", doc.rel, f"Heading '{sec.base}' occurs more than once.")
            self._heading_text(doc, sec, bases)

    def _heading_text(self, doc: Doc, sec: Section, bases: set[str]) -> None:
        """Check the heading text (suffix confusion and characters that break anchors).

        Args:
            doc: Document.
            sec: Section with heading.
            bases: All heading texts of the document.
        """
        m = SUFFIX_LIKE_RE.search(sec.base)
        if m and sec.key == sec.base:
            stem = sec.base[: m.start()]
            hint = f"please rephrase (e.g. '{stem} {m.group(1)}')"
            if stem in bases:
                self.r.add("heading_suffix_collision", "error", doc.rel,
                           f"Heading '{sec.base}' collides with the duplicate suffix of '{stem}'; {hint}.")
            else:
                self.r.add("heading_suffix_like", "warning", doc.rel,
                           f"Heading '{sec.base}' ends in # plus digits and can be confused with a "
                           f"duplicate suffix; {hint}.")
        text = sec.base[: m.start()] if m else sec.base
        if BAD_ANCHOR_CHARS & set(text):
            self.r.add("heading_bad_chars", "warning", doc.rel,
                       f"Heading '{sec.base}' contains characters that break Obsidian anchors (# ^ [ ] |).")

    # Structure ****************************************************************

    def resolve_link(self, target: str) -> set[str]:
        """Find a wikilink target in the vault.

        Args:
            target: Link target.

        Returns:
            Matching paths (none, one or several).
        """
        return self.keys.get(link_key(target), set())

    def structure(self) -> None:
        """Type, confidence, summary, links, orphaned and missing pages, topics without a page."""
        incoming: Counter[str] = Counter()
        unresolved: Counter[str] = Counter()
        for page in self.pages:
            if page.error:
                self.r.add(page.error, "error", page.rel, page.error_message or page.error)
            else:
                self._page_meta(page)
                self._page_links(page, incoming, unresolved)
        for page in self.pages:
            if page.rel.split("/")[1] in FOLDER_TYPES and not incoming.get(page.rel):
                self.r.add("orphan_page", "warning", page.rel, "No other wiki page links to this page.")
        for target, n in unresolved.items():
            if n >= MIN_MISSING_PAGE_LINKS:
                self.r.add("missing_page", "info", None, f"[[{target}]] is linked {n} times, the page is missing.")
        self._topics_without_page()

    def _page_meta(self, page: Doc) -> None:
        """Check the frontmatter and summary of a wiki page.

        Args:
            page: Wiki page.
        """
        folder = page.rel.split("/")[1] if page.rel.count("/") >= 2 else ""
        typ = page.meta.get("type")
        if typ not in WIKI_TYPES:
            self.r.add("invalid_type", "warning", page.rel, f"type missing or invalid: {typ!r}.")
        elif folder in FOLDER_TYPES and FOLDER_TYPES[folder] != typ:
            self.r.add("type_folder_mismatch", "info", page.rel, f"type {typ} does not match the folder {folder}/.")
        self._dates_and_tags(page)
        conf = page.meta.get("confidence")
        if conf is not None and conf not in CONFIDENCE:
            self.r.add("invalid_confidence", "warning", page.rel, f"confidence invalid: {conf!r}.")
        if not summary_of(page):
            self.r.add("missing_summary", "warning", page.rel, "Summary (first quote >) is missing.")

    def _page_links(self, page: Doc, incoming: Counter[str], unresolved: Counter[str]) -> None:
        """Check and count the links of a wiki page.

        Args:
            page: Wiki page.
            incoming: Incoming links per page (added to).
            unresolved: Targets not found (added to).
        """
        for target in extract_links(page.body):
            found = self.resolve_link(target)
            if not found:
                unresolved[target] += 1
                self.r.add("broken_link", "error", page.rel, f"Link target not found: [[{target}]].")
            elif len(found) > 1:
                self.r.add("ambiguous_link", "warning", page.rel, f"Link [[{target}]] is ambiguous.",
                           candidates=sorted(found))
            else:
                (dest,) = found
                if dest != page.rel:
                    incoming[dest] += 1

    def _topics_without_page(self) -> None:
        """Topics that occur in several documents but have no wiki page.

        A tag counts as covered if the file name, title or an alias of any wiki page equals it, if a topic,
        entity or synthesis page carries it as its **first** tag, or if it occurs as whole words in the file
        name or title of such a page (``sandboxing`` in ``sandboxing-von-ki-agenten``); ignoring case, umlauts
        spelled out, hyphens and spaces alike. Further tags of a page about another topic do not count.
        """
        names: set[str] = set()
        word_names: list[str] = []
        for page in self.pages:
            names.update({_topic_key(page.stem), _topic_key(page.title)})
            aliases, tags = page.meta.get("aliases"), page.meta.get("tags")
            if isinstance(aliases, list):
                names.update(_topic_key(str(v)) for v in aliases)
            if page_type(page) in COVERING_TYPES:
                word_names += [f"-{slugify(page.stem)}-", f"-{slugify(page.title)}-"]
                if isinstance(tags, list) and tags:
                    names.add(_topic_key(str(tags[0])))
        topics: Counter[str] = Counter()
        for doc in self.docs:
            t = doc.meta.get("tags")
            if isinstance(t, list):
                topics.update({str(x).casefold() for x in t})
        for topic, n in sorted(topics.items()):
            covered = _topic_key(topic) in names or any(f"-{slugify(topic)}-" in w for w in word_names)
            if n >= MIN_TOPIC_DOCUMENTS and not covered:
                self.r.add("topic_without_page", "info", None,
                           f"Topic '{topic}' in {n} documents, but without a wiki page.")

    # Citations ****************************************************************

    def citations(self) -> None:
        """Check footnotes, statements without citation, ``sources`` and every single citation."""
        resolver = Resolver(self.svc)
        for page in self.pages:
            if not page.error:
                pc = parse_page(page)
                labels_ref = {lab for lab, _ in pc.references}
                for label in sorted(labels_ref - set(pc.definitions)):
                    self.r.add("footnote_undefined", "error", page.rel, f"Footnote [^{label}] without definition.")
                for label in sorted(set(pc.definitions) - labels_ref):
                    self.r.add("footnote_unused", "info", page.rel, f"Footnote [^{label}] is not used.")
                for st in pc.statements:
                    if st.section in CONTENT_SECTIONS and not st.labels:
                        self.r.add("statement_without_citation", "warning", page.rel,
                                   f"Statement without citation: '{st.text[:STATEMENT_PREVIEW]}'", section=st.section)
                if page.meta.get("sources") != expected_sources(pc):
                    self.r.add("sources_out_of_sync", "warning", page.rel,
                               "sources does not match the footnotes (pkm sync-citations).")
                for cit in pc.definitions.values():
                    self.citation(page, cit, resolver)

    def citation(self, page: Doc, cit: Citation, resolver: Resolver) -> None:
        """Check a citation: format, target, resolution and content.

        Args:
            page: Wiki page.
            cit: Citation.
            resolver: Resolver.
        """
        for problem in cit.problems:
            self.r.add("citation_format", "error", page.rel, f"[^{cit.label}]: {problem}.", footnote=cit.label)
        target = cit.target_rel or ""
        if cit.path and not target.startswith("documents/"):
            check = {"wiki": "citation_to_wiki", "scratch": "citation_to_scratch"}.get(
                target.split("/", 1)[0], "citation_outside_documents")
            self.r.add(check, "error", page.rel, f"[^{cit.label}] does not point to documents/: {cit.path}.",
                       footnote=cit.label)
        elif cit.path:
            res = resolver.resolve(cit)
            self._citation_status(page, cit, res)
            if cit.markdown:
                self._citation_content(page, cit, res)
                sections = res.doc.hashes.sections if res.doc is not None and res.doc.hashes else {}
                if sections.get(cit.section_key or "") == hashes.EMPTY_HASH:
                    self.r.add("citation_empty_section", "warning", page.rel,
                               f"[^{cit.label}] cites the section '{cit.section_key}' that has no text of its own; "
                               "cite the subsection containing the quote.", footnote=cit.label)

    def _citation_status(self, page: Doc, cit: Citation, res: Resolution) -> None:
        """Findings from the resolution (missing, moved, newer version).

        Args:
            page: Wiki page.
            cit: Citation.
            res: Resolution.
        """
        if res.status == "missing":
            self.r.add("citation_missing", "error", page.rel, f"[^{cit.label}] original not found: {cit.path}.",
                       footnote=cit.label)
        if res.moved:
            self.r.add("citation_moved", "warning", page.rel,
                       f"[^{cit.label}] original moved to {res.current_path} (pkm fix-citations).",
                       footnote=cit.label)
        if res.status == "newer_version":
            self.r.add("citation_newer_version", "warning", page.rel,
                       f"[^{cit.label}] section has changed since v{cit.version} "
                       f"(currently v{res.current_version}).", footnote=cit.label)

    def _citation_content(self, page: Doc, cit: Citation, res: Resolution) -> None:
        """Check anchor, sha and quote against the cited version.

        Args:
            page: Wiki page.
            cit: Markdown citation.
            res: Resolution.
        """
        key = cit.section_key
        if res.cited_sections is None:
            if cit.doc_id and cit.version and res.status != "missing" and self.svc.versioning:
                self.r.add("cited_version_missing", "error", page.rel,
                           f"[^{cit.label}] v{cit.version} of {cit.doc_id} not in the history.", footnote=cit.label)
        elif key not in res.cited_sections:
            self.r.add("anchor_missing", "warning", page.rel,
                       f"[^{cit.label}] section '{key}' does not exist in v{cit.version}.", footnote=cit.label)
        elif cit.sha and not hashes.matches(res.cited_sections[key], cit.sha):
            self.r.add("sha_mismatch", "error", page.rel,
                       f"[^{cit.label}] sha does not match the section in v{cit.version}.", footnote=cit.label)
        image = image_quote(cit.quote)
        if image and res.cited_sections is not None and not has_image(res.cited_text, image):
            self.r.add("citation_image_missing", "error", page.rel,
                       f"[^{cit.label}] image '{image}' is not in v{cit.version}, section '{key}'.",
                       footnote=cit.label)
        if (not image and res.cited_sections is not None and cit.quote and res.cited_text is not None
                and norm_ws(cit.quote) not in norm_ws(res.cited_text)):
            self.r.add("quote_not_found", "error", page.rel,
                       f"[^{cit.label}] quote is not in v{cit.version}, section '{key}'.", footnote=cit.label)

# Functions *******************************************************************


def _topic_key(name: str) -> str:
    """Comparable form of a tag, title or file name.

    Args:
        name: Name.

    Returns:
        Lower case with hyphens and underscores as spaces, whitespace collapsed.
    """
    return " ".join(name.replace("-", " ").replace("_", " ").casefold().split())


def _error_message(doc: Doc) -> str:
    """Error text for unreadable documents, with a hint to ``pkm fix-frontmatter`` if that helps.

    Args:
        doc: Document with ``error``.

    Returns:
        Error text.
    """
    message = doc.error_message or doc.error or ""
    if doc.error == "invalid_frontmatter" and doc.text is not None:
        fixed, changes = fix_frontmatter_text(doc.text)
        if changes and parse_text(fixed).fm_error is None:
            message += " Missing quotes: pkm fix-frontmatter fixes that (only on instruction)."
    return message


def lint(svc: Service) -> dict[str, Any]:
    """``pkm lint``.

    Args:
        svc: Service.

    Returns:
        The lint report.
    """
    return Linter(svc).run()


def write_report(svc: Service, result: dict[str, Any]) -> str:
    """Write the report to ``wiki/_lint/YYYY-MM-DD.md``.

    Args:
        svc: Service.
        result: Result of ``lint``.

    Returns:
        Relative path of the report.
    """
    date = svc.now().date().isoformat()
    rel = f"wiki/_lint/{date}.md"
    s = result["summary"]
    lines = [f"# Lint report {date}", "", f"{s['error']} errors, {s['warning']} warnings, {s['info']} notes.", ""]
    for sev in SEVERITIES:
        items = [f for f in result["findings"] if f["severity"] == sev]
        if items:
            lines += [f"## {SEVERITY_LABELS[sev]} ({len(items)})", ""]
            for f in items:
                where = f" – {f['path']}" if f.get("path") else ""
                lines.append(f"- `{f['check']}`{where}: {f['message']}")
            lines.append("")
    write_if_changed(svc, rel, "\n".join(lines))
    return rel

# Main ************************************************************************
