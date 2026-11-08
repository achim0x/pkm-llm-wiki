"""Domain facade for the MCP server and the CLI (specification 7.2, 7.3).

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

import sqlite3
from datetime import datetime
from typing import Any

from . import citations, docimages
from .config import Config
from .diffs import unified_diff
from .errors import NO_VERSIONING, PkmError
from .gitlayer import Commit, Git
from .ids import is_valid_id
from .images import to_placeholders
from .index import SearchIndex, query_terms, snippet
from .maint import Maintenance
from .parse import normalize_key_input
from .state import classify, load_state, state_key
from .vault import AREAS, READ_AREAS, SCRATCH, Doc, Vault, extract_links, load_text_doc, section_summary
from .writer import Writer

# Variables *******************************************************************

MAX_RESULTS = 25
HISTORY_DIFF_LINES = 400
SCOPES = {"wiki": ("wiki",), "documents": ("documents",), "scratch": (SCRATCH,), "all": AREAS}
UNPROCESSED_CATEGORIES = ("new", "changed", "meta_changed", "moved", "deleted")
INDEX_ERRORS = (sqlite3.Error, PkmError, OSError)
READ_LIMIT = 40_000

# Classes *********************************************************************


class Service:  # pylint: disable=too-many-public-methods
    """Facade over vault, Git, search index and write logic; one method per tool or command."""

    def __init__(self, cfg: Config) -> None:
        """Create the service.

        Args:
            cfg: Configuration.
        """
        self.cfg = cfg
        self.vault = Vault(cfg)
        self.git = Git(cfg.git_dir, cfg.root, cfg.git_author, cfg.git_exe)
        self.versioning = cfg.versioning
        self._index: SearchIndex | None = None

    # Helpers ******************************************************************

    def now(self) -> datetime:
        """Current time in ``PKM_TZ`` without microseconds.

        Returns:
            Point in time with time zone.
        """
        return datetime.now(self.cfg.tz).replace(microsecond=0)

    @property
    def index(self) -> SearchIndex:
        """Search index (created on first access).

        Returns:
            The index.

        Raises:
            PkmError: ``index_unavailable`` if ``PKM_CACHE_DIR`` lies in the vault.
        """
        if self._index is None:
            self._index = SearchIndex(self.cfg, self.vault)
        return self._index

    @property
    def writer(self) -> Writer:
        """Write logic for this service.

        Returns:
            A ``Writer``.
        """
        return Writer(self)

    def index_available(self) -> bool:
        """Check whether the search index may be used.

        Returns:
            ``True`` if ``PKM_CACHE_DIR`` lies outside the vault.
        """
        return self.cfg.cache_dir_problem() is None

    def find_id(self, doc_id: str) -> list[str]:
        """Find the paths for an ID, preferably via the index.

        Args:
            doc_id: Document ID.

        Returns:
            Existing paths with this ID.
        """
        paths = None
        if self.index_available():
            try:
                paths = [p for p in self.index.find_id(doc_id) if self.vault.exists(p)] or None
            except INDEX_ERRORS:  # The index is only a cache.
                paths = None
        # Empty hit: the index can be outdated (e.g. after a move) – then scan.
        paths = paths if paths is not None else self.vault.scan_id(doc_id)
        return [p for p in paths if not p.startswith(f"{SCRATCH}/")]

    def find_citation(self, value: str) -> list[str]:
        """Find the paths for a short citation, preferably via the index.

        Args:
            value: Short citation (``short_citation``).

        Returns:
            Existing paths in ``documents/``.
        """
        paths = None
        if self.index_available():
            try:
                paths = [p for p in self.index.find_citation(value) if self.vault.exists(p)] or None
            except INDEX_ERRORS:
                paths = None
        return paths if paths is not None else self.vault.scan_citation(value)

    def known_ids(self) -> set[str]:
        """All assigned IDs, preferably via the index.

        Returns:
            Set of the IDs.
        """
        ids = None
        if self.index_available():
            try:
                ids = self.index.ids()
            except INDEX_ERRORS:
                ids = None
        if ids is None:
            docs = (self.vault.load(rel) for rel in self.vault.iter_files() if rel.endswith(".md"))
            ids = {d.id for d in docs if d.id}
        return ids

    def resolve(self, target: str, areas: tuple[str, ...] = READ_AREAS) -> str:
        """Resolve a target (path, wikilink, short name or ``id:``).

        Args:
            target: Target.
            areas: Allowed areas.

        Returns:
            Relative path.
        """
        return self.vault.resolve(target, areas, self.find_id, self.find_citation)

    def load(self, target: str, areas: tuple[str, ...] = READ_AREAS) -> Doc:
        """Resolve and load a target.

        Args:
            target: Target.
            areas: Allowed areas.

        Returns:
            The document.
        """
        return self.vault.load(self.resolve(target, areas))

    def state(self) -> dict[str, Any]:
        """Read the processing state.

        Returns:
            Content of ``state.json``.
        """
        return load_state(self.cfg)

    def processed(self, doc: Doc, state: dict[str, Any] | None = None) -> bool:
        """Check whether the current state of a document is incorporated into the wiki.

        Args:
            doc: Document.
            state: Already loaded state; read if omitted.

        Returns:
            ``True`` if ``classify`` reports nothing to do.
        """
        state = state if state is not None else self.state()
        key = state_key(doc)
        entry = state["documents"].get(key) if key else None
        return classify(doc, entry) is None

    # Versions from Git ********************************************************

    def versions(self, doc_id: str) -> list[Commit]:
        """Commits of a document with a version number.

        Args:
            doc_id: Document ID.

        Returns:
            Commits, oldest first; empty without version control.
        """
        return [c for c in self.git.log_for_id(doc_id) if c.version is not None] if self.versioning else []

    def commit_for_version(self, doc_id: str, version: int) -> Commit:
        """Commit for a version (the last one if there are several, e.g. after a pure move).

        Args:
            doc_id: Document ID.
            version: Version number.

        Returns:
            The commit.

        Raises:
            PkmError: ``not_found`` if the version is not in the history.
        """
        matching = [c for c in self.versions(doc_id) if c.version == version and c.path]
        if not matching:
            raise PkmError("not_found", f"Version {version} of {doc_id} not in the history.", version=version)
        return matching[-1]

    def text_at_version(self, doc_id: str, version: int) -> tuple[str, str]:
        """Path and text of a document in a version.

        Args:
            doc_id: Document ID.
            version: Version number.

        Returns:
            Tuple of (path at that time, text).

        Raises:
            PkmError: ``not_versioned`` without version control, ``not_found`` for an unknown version.
        """
        if not self.versioning:
            raise PkmError("not_versioned", NO_VERSIONING, version=version)
        c = self.commit_for_version(doc_id, version)
        return c.path or "", self.git.show_file(c.sha, c.path or "").decode("utf-8", "replace")

    def _target_id(self, target: str) -> tuple[str, str | None]:
        """Determine the ID and current path; for ``id:`` also for deleted documents.

        Args:
            target: Target.

        Returns:
            Tuple of (ID, current path or ``None`` if the document is deleted).

        Raises:
            PkmError: ``not_found`` if the target is missing or has no ID; ``not_versioned``
                for files in ``scratch/`` and without version control.
        """
        if not self.versioning:
            raise PkmError("not_versioned", NO_VERSIONING, target=target)
        t = target.strip()
        try:
            doc = self.load(t)
        except PkmError as exc:
            if not (exc.status == "not_found" and t.startswith("id:") and is_valid_id(t[3:].strip())):
                raise
            doc = None
        if doc is not None and not doc.versioned:
            raise PkmError("not_versioned", f"{doc.rel} lies in scratch/ and has no history.", path=doc.rel)
        if doc is None:
            result: tuple[str, str | None] = (t[3:].strip(), None)
        elif not doc.id:
            raise PkmError("not_found", f"{doc.rel} has no ID (not versioned yet).", path=doc.rel)
        else:
            result = (doc.id, doc.rel)
        return result

    # Reading tools ************************************************************

    def search(self, query: str, scope: str = "wiki", max_results: int = 8) -> dict[str, Any]:
        """Tool ``search``.

        Args:
            query: Search terms.
            scope: ``wiki``, ``documents``, ``scratch`` or ``all`` (= ``wiki`` and ``documents``).
            max_results: Maximum number of hits (1–25).

        Returns:
            Hits with ``id``, ``path``, ``title``, ``type``, ``summary``, ``snippet``, ``score``,
            ``date_updated``, ``short_citation`` and for documents ``version`` and ``processed``.

        Raises:
            PkmError: ``invalid_argument`` for an unknown ``scope``.
        """
        areas = SCOPES.get(scope)
        if areas is None:
            raise PkmError("invalid_argument", "scope must be wiki, documents, scratch or all.")
        hits = self.index.search(query, areas, max(1, min(int(max_results), MAX_RESULTS)))
        state = self.state()
        results = []
        for hit in hits:
            item = self._search_item(hit, state)
            if item is not None:
                results.append(item)
        return {"status": "ok", "query": query, "scope": scope, "results": results, "terms": query_terms(query)}

    def _search_item(self, hit: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
        """Add excerpt, version and processing state to a search hit.

        Args:
            hit: Hit from the index.
            state: Processing state.

        Returns:
            Result entry or ``None`` if the file is missing in the meantime.
        """
        item: dict[str, Any] | None = None
        try:
            doc = self.vault.load(hit["path"])
        except PkmError:
            doc = None
        if doc is not None:
            item = {k: hit[k] for k in ("id", "path", "title", "type", "summary", "score", "date_updated",
                                        "short_citation")}
            item["snippet"] = snippet(doc.body, hit["terms"]) if doc.kind == "md" else ""
            if hit["area"] == "documents":
                item["version"] = doc.version
                item["processed"] = self.processed(doc, state)
        return item

    def read(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        target: str,
        version: int | None = None,
        section: str | None = None,
        offset: int = 0,
        max_chars: int | None = None,
        content: bool = True,
    ) -> dict[str, Any]:
        """Tool ``read``.

        Args:
            target: Path, wikilink or ``id:``.
            version: Earlier version from Git (read-only).
            section: Return only this section (key as in ``sections``).
            offset: Start character for reading page by page.
            max_chars: Return at most this many characters.
            content: ``False`` returns only frontmatter, ``sections``, ``hash`` and ``content_length``.

        Returns:
            Content, frontmatter, ``hash``, ``editable``, sections, links and backlinks;
            for wiki pages additionally the parsed citations; in ``scratch/`` without ``id`` and ``version``.
            If the content is larger than ``READ_LIMIT`` and neither ``section`` nor ``max_chars``
            is given, ``content`` is left out (``content_omitted``).

        Raises:
            PkmError: ``not_versioned`` for ``version`` with files in ``scratch/``.
        """
        if version is not None:
            doc_id, rel = self._target_id(target)
            path, text = self.text_at_version(doc_id, int(version))
            doc = load_text_doc(path, text.encode("utf-8"))
            result = self._doc_result(doc, with_links=False)
            result.update({"editable": False, "current_path": rel, "version": version})
        else:
            doc = self.load(target)
            result = self._doc_result(doc, with_links=True)
        if "content" in result:
            text = _section_content(doc, section, result) if section is not None else result["content"]
            text, result["images"] = docimages.read_view(doc, text, result.get("section"), self.cfg.images)
            result.update(_page_of(text, offset, max_chars, content))
            if "content" not in result or result["content"] is None:
                result.pop("content", None)
        return result

    def _doc_result(self, doc: Doc, with_links: bool) -> dict[str, Any]:
        """Build the return value of ``read`` for a loaded document.

        Args:
            doc: Document.
            with_links: Determine links and backlinks.

        Returns:
            The result dictionary.
        """
        if doc.kind == "bin":
            result: dict[str, Any] = {
                "status": "ok", "kind": "binary", "id": None, "version": None, "path": doc.rel,
                "size": doc.size, "hash": doc.bin_hash, "editable": False,
            }
        else:
            result = {
                "status": doc.error or "ok",
                "id": doc.id,
                "version": doc.version,
                "path": doc.rel,
                "title": doc.title,
                "frontmatter": doc.meta,
                "content": doc.body if doc.error in (None, "invalid_frontmatter") else "",
                "images": [],
                "hash": doc.hashes.file_hash if doc.hashes else None,
                "editable": doc.editable,
                "sections": section_summary(doc),
            }
            if doc.error:
                result["message"] = doc.error_message
            if with_links:
                result["links"] = extract_links(doc.body)
                result["backlinks"] = self._backlinks(doc)
            if doc.area == "wiki":
                result["citations"] = citations.page_citations_for_read(doc)
            if not doc.versioned:
                result.pop("id")
                result.pop("version")
        return result

    def _backlinks(self, doc: Doc) -> list[str]:
        """Backlinks via the index (empty if the index is not available).

        Args:
            doc: Document.

        Returns:
            Paths of the linking files.
        """
        links: list[str] = []
        if self.index_available():
            try:
                links = self.index.backlinks(doc)
            except INDEX_ERRORS:
                links = []
        return links

    def history(self, target: str, diff_from: int | None = None, diff_to: int | None = None) -> dict[str, Any]:
        """Tool ``history``.

        Args:
            target: Document (also ``id:`` of a deleted document).
            diff_from: Version to compare from.
            diff_to: Version to compare to; default is the newest.

        Returns:
            Versions with date, source, note and commit; with ``diff_from`` additionally ``diff``.

        Raises:
            PkmError: ``not_found`` if there are no versions; ``not_versioned`` in ``scratch/``.
        """
        doc_id, rel = self._target_id(target)
        commits = self.git.log_for_id(doc_id)
        entries = [
            {
                "version": c.version, "date": c.date, "source": c.source, "note": c.note,
                "subject": c.subject, "commit": c.sha[:10], "path": c.path,
            }
            for c in commits
        ]
        result: dict[str, Any] = {"status": "ok", "id": doc_id, "path": rel, "versions": entries}
        if diff_from is not None:
            versions = [c.version for c in commits if c.version is not None]
            if not versions:
                raise PkmError("not_found", "No versions in the history.")
            to = int(diff_to) if diff_to is not None else max(versions)
            _, old = self.text_at_version(doc_id, int(diff_from))
            _, new = self.text_at_version(doc_id, to)
            result["diff_from"], result["diff_to"] = int(diff_from), to
            result["diff"] = unified_diff(old, new, f"v{diff_from}", f"v{to}", HISTORY_DIFF_LINES)
        return result

    def show(self, target: str, version: int, section: str | None = None) -> dict[str, Any]:
        """CLI ``pkm show``: earlier version, optionally only one section.

        Args:
            target: Document.
            version: Version number.
            section: Section key.

        Returns:
            Like ``read`` with ``version``; with ``section`` additionally ``section`` and ``section_hash``
            and ``content`` with this section only.

        Raises:
            PkmError: ``not_found`` if the section is missing.
        """
        res = self.read(target, version)
        if section is not None:
            key = normalize_key_input(section)
            doc_id, _ = self._target_id(target)
            doc = load_text_doc(res["path"], self.text_at_version(doc_id, version)[1].encode("utf-8"))
            sec = doc.parsed.section(key) if doc.parsed else None
            if sec is None:
                raise PkmError("not_found", f"Section not found: {section}", section=section)
            res["section"] = key
            res["content"] = to_placeholders("\n".join(([sec.heading] if sec.heading else []) + sec.content_lines))
            res["section_hash"] = doc.hashes.sections[key] if doc.hashes else None
        return res

    def read_index(self) -> dict[str, Any]:
        """Tool ``read_index``.

        Returns:
            Content of ``wiki/index.md`` (empty if the file is missing).
        """
        p = self.cfg.root / "wiki" / "index.md"
        content = p.read_text(encoding="utf-8") if p.is_file() else ""
        return {"status": "ok", "path": "wiki/index.md", "content": content}

    def list_unprocessed(self) -> dict[str, Any]:
        """Tool ``list_unprocessed``: like ``pkm pending`` as a flat list (computed live).

        Returns:
            Count, documents with ``category`` and problems found.
        """
        pend = Maintenance(self).pending()
        docs = [{"category": category, **item} for category in UNPROCESSED_CATEGORIES for item in pend[category]]
        return {"status": "ok", "count": len(docs), "documents": docs, "problems": pend["problems"]}

    def reindex(self) -> dict[str, Any]:
        """CLI ``pkm reindex``.

        Returns:
            Counters of the rebuild.
        """
        return {"status": "ok", **self.index.rebuild()}

    def show_citations(self, target: str, statement: str | None = None, with_excerpt: bool = False) -> dict[str, Any]:
        """Tool ``show_citations``.

        Args:
            target: Wiki page.
            statement: Text fragment to narrow down.
            with_excerpt: Load the wording from the original.

        Returns:
            See ``citations.show_citations``.
        """
        return citations.show_citations(self, target, statement, with_excerpt)

    # Writing tools (7.2) ******************************************************

    def create_document(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``create_document``.

        Args:
            **kwargs: Parameters like ``Writer.create_document``.

        Returns:
            Return value of the writer.
        """
        return self.writer.create_document(**kwargs)

    def rewrite_document(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``rewrite_document``.

        Args:
            **kwargs: Parameters like ``Writer.rewrite_document``.

        Returns:
            Return value of the writer.
        """
        return self.writer.rewrite_document(**kwargs)

    def append_to_document(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``append_to_document``.

        Args:
            **kwargs: Parameters like ``Writer.append_to_document``.

        Returns:
            Return value of the writer.
        """
        return self.writer.append_to_document(**kwargs)

    def edit_document(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``edit_document``.

        Args:
            **kwargs: Parameters like ``Writer.edit_document``.

        Returns:
            Return value of the writer.
        """
        return self.writer.edit_document(**kwargs)

    def add_image(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``add_image`` (4.9).

        Args:
            **kwargs: Parameters of ``Writer.add_image``.

        Returns:
            Return value of the writer.
        """
        return self.writer.add_image(**kwargs)

    def read_image(self, target: str, image: str | None = None, as_: str = "auto") -> dict[str, Any]:
        """Tool ``read_image`` (4.9).

        Args:
            target: Document or standalone image file.
            image: Image name.
            as_: ``auto``, ``image`` or ``svg_text``.

        Returns:
            Metadata and image (``svg`` as text or ``data`` as bytes).
        """
        return docimages.image_payload(self, target, image, as_)

    def fix_images(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``fix_images`` (4.9, 7.2).

        Args:
            **kwargs: Parameters of ``docimages.fix_document``.

        Returns:
            Proposal or new version.
        """
        return docimages.fix_document(self.writer, **kwargs)

    def update_frontmatter(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``update_frontmatter``.

        Args:
            **kwargs: Parameters like ``Writer.update_frontmatter``.

        Returns:
            Return value of the writer.
        """
        return self.writer.update_frontmatter(**kwargs)

    def restore_document(
        self, target: str, version: int, expected_hash: str | None, source: str = "chat"
    ) -> dict[str, Any]:
        """Tool ``restore_document`` or CLI ``pkm restore``.

        Args:
            target: Document.
            version: Version to restore.
            expected_hash: Hash from ``read``.
            source: ``chat`` (MCP) or ``user`` (CLI).

        Returns:
            Return value of the writer.
        """
        return self.writer.restore_document(target, version, expected_hash, source)

# Functions *******************************************************************

def _section_content(doc: Doc, section: str, result: dict[str, Any]) -> str:
    """Text of a section for ``read``.

    Args:
        doc: Document.
        section: Section key.
        result: Result of ``read`` (receives ``section``).

    Returns:
        Heading and content of the section.

    Raises:
        PkmError: ``not_found`` with the list of sections.
    """
    key = normalize_key_input(section)
    text = citations.section_text(doc, key)
    if text is None:
        raise PkmError("not_found", f"Section not found: {section}",
                       sections=[s["key"] for s in result.get("sections", [])])
    result["section"] = key
    return text


def _page_of(text: str, offset: int, max_chars: int | None, content: bool) -> dict[str, Any]:
    """Trim the content for ``read``.

    Args:
        text: Complete text (document or section).
        offset: Start character.
        max_chars: Maximum number of characters or ``None``.
        content: Return content at all.

    Returns:
        ``content`` (or ``None``), ``content_length`` and if needed ``offset``, ``truncated``,
        ``next_offset`` or ``content_omitted`` with a hint.

    Raises:
        PkmError: ``invalid_argument`` for negative values.
    """
    if offset < 0 or (max_chars is not None and max_chars <= 0):
        raise PkmError("invalid_argument", "offset must be ≥ 0 and max_chars > 0.")
    out: dict[str, Any] = {"content": None, "content_length": len(text)}
    if content and (max_chars is not None or offset):
        end = len(text) if max_chars is None else min(len(text), offset + max_chars)
        out.update(content=text[offset:end], offset=offset, truncated=end < len(text))
        if end < len(text):
            out["next_offset"] = end
    elif content and len(text) > READ_LIMIT:
        out.update(content_omitted=True, hint=f"Content larger than {READ_LIMIT} characters: read it with section or "
                   "offset/max_chars.")
    elif content:
        out["content"] = text
    return out

# Main ************************************************************************
