"""Search index in ``PKM_CACHE_DIR/index.db`` (specification 7.4). A pure throwaway cache.

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
import sqlite3
import unicodedata
from collections.abc import Callable, Iterable
from contextlib import closing
from typing import Any, TypeVar

from .config import Config
from .errors import PkmError
from .images import strip_images
from .paths import transliterate
from .schema import citation_key
from .vault import ALL_AREAS, Doc, Vault, extract_links, link_key, summary_of

# Variables *******************************************************************

SCHEMA = 2
WEIGHTS = (0.0, 5.0, 3.0, 2.0, 1.0)  # path, title, meta, summary, body
SNIPPET_WIDTH = 160
T = TypeVar("T")

DDL = """
CREATE TABLE IF NOT EXISTS info(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS files(
    path TEXT PRIMARY KEY, area TEXT, kind TEXT, mtime_ns INTEGER, size INTEGER,
    id TEXT, version INTEGER, title TEXT, type TEXT, summary TEXT, updated TEXT,
    file_hash TEXT, error TEXT, citation TEXT
);
CREATE INDEX IF NOT EXISTS files_id ON files(id);
CREATE INDEX IF NOT EXISTS files_citation ON files(citation);
CREATE TABLE IF NOT EXISTS links(src TEXT, target TEXT);
CREATE INDEX IF NOT EXISTS links_target ON links(target);
CREATE INDEX IF NOT EXISTS links_src ON links(src);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    path UNINDEXED, title, meta, summary, body, tokenize = 'unicode61 remove_diacritics 2'
);
"""

SEARCH_SQL = (
    "SELECT f.path, f.area, f.kind, f.id, f.version, f.title, f.type, f.summary, f.updated, f.citation, "
    f"bm25(fts, {', '.join(str(w) for w in WEIGHTS)}) AS rank "
    "FROM fts JOIN files f ON f.path = fts.path "
    "WHERE fts MATCH ? AND f.area IN ({marks}) ORDER BY rank LIMIT ?"
)

# Classes *********************************************************************


class SearchIndex:
    """FTS5 index over ``documents/``, ``wiki/`` and ``scratch/``, incremental and self-healing."""

    def __init__(self, cfg: Config, vault: Vault) -> None:
        """Create the index access.

        Args:
            cfg: Configuration.
            vault: Vault access.

        Raises:
            PkmError: ``index_unavailable`` if ``PKM_CACHE_DIR`` lies in the vault.
        """
        problem = cfg.cache_dir_problem()
        if problem:
            raise PkmError("index_unavailable", problem)
        self.cfg = cfg
        self.vault = vault
        self.path = cfg.index_path

    # Connection ***************************************************************

    def _connect(self) -> sqlite3.Connection:
        """Open the database and check or create the schema.

        Returns:
            Open connection.

        Raises:
            sqlite3.DatabaseError: For a damaged file or a different schema.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        try:
            con.execute("PRAGMA journal_mode=DELETE")
            con.executescript(DDL)
            row = con.execute("SELECT value FROM info WHERE key='schema'").fetchone()
            if row is None:
                con.execute("INSERT INTO info VALUES('schema', ?)", (str(SCHEMA),))
                con.commit()
            elif row[0] != str(SCHEMA):
                raise sqlite3.DatabaseError("schema mismatch")
        except sqlite3.Error:
            con.close()  # Otherwise the file could not be deleted and rebuilt on Windows.
            raise
        return con

    def _drop(self) -> None:
        """Delete the index file together with its companion files."""
        for suffix in ("", "-journal", "-wal", "-shm"):
            p = self.path.with_name(self.path.name + suffix)
            if p.exists():
                p.unlink()

    def _run_db(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Run a function with a connection and commit afterwards.

        Args:
            fn: Function that receives the connection.

        Returns:
            The result of ``fn``.
        """
        with closing(self._connect()) as con:
            result = fn(con)
            con.commit()
        return result

    def _with_db(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Like ``_run_db``, but rebuild a damaged index once and retry.

        Args:
            fn: Function that receives the connection.

        Returns:
            The result of ``fn``.
        """
        try:
            result = self._run_db(fn)
        except sqlite3.DatabaseError:
            self._drop()
            result = self._run_db(fn)
        return result

    # Updating *****************************************************************

    @staticmethod
    def _forget(con: sqlite3.Connection, rel: str) -> None:
        """Remove all entries of a file.

        Args:
            con: Connection.
            rel: Relative path.
        """
        con.execute("DELETE FROM files WHERE path=?", (rel,))
        con.execute("DELETE FROM fts WHERE path=?", (rel,))
        con.execute("DELETE FROM links WHERE src=?", (rel,))

    def _index_doc(self, con: sqlite3.Connection, doc: Doc) -> None:
        """Index a file (again).

        Args:
            con: Connection.
            doc: Loaded document.
        """
        self._forget(con, doc.rel)
        meta = doc.meta
        summary = strip_images(summary_of(doc)) if doc.kind == "md" else ""
        file_hash = doc.hashes.file_hash if doc.hashes else doc.bin_hash
        cit = doc.short_citation if doc.kind == "md" else None
        con.execute(
            "INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                doc.rel, doc.area, doc.kind, doc.mtime_ns, doc.size, doc.id, doc.version,
                doc.title, str(meta.get("type") or ""), summary, str(meta.get("date_updated") or ""),
                file_hash, doc.error, cit,
            ),
        )
        tags = " ".join(_as_list(meta.get("aliases")) + _as_list(meta.get("tags")) + _as_list(cit))
        body = doc.body if doc.kind == "md" else ""
        con.execute(
            "INSERT INTO fts(path, title, meta, summary, body) VALUES(?,?,?,?,?)",
            (doc.rel, fold(doc.title), fold(tags), fold(summary), fold(strip_images(body))),
        )
        if doc.kind == "md":
            con.executemany("INSERT INTO links VALUES(?,?)", [(doc.rel, link_key(t)) for t in extract_links(body)])

    def _changed_doc(self, rel: str, known: tuple[int, int] | None, force: bool) -> Doc | None:
        """Load a file if it has to be (re)indexed.

        Args:
            rel: Relative path.
            known: Stored (mtime_ns, size) or ``None``.
            force: Reindex regardless of mtime and size.

        Returns:
            The document or ``None`` if there is nothing to do or the file is not readable.
        """
        doc = None
        try:
            st = (self.vault.root / rel).stat()
            if force or known != (st.st_mtime_ns, st.st_size):
                doc = self.vault.load(rel)
        except (PkmError, OSError):
            doc = None
        return doc

    def _refresh(self, con: sqlite3.Connection, force: bool = False) -> dict[str, int]:
        """Reindex changed files (comparing mtime and size), remove deleted ones.

        Args:
            con: Connection.
            force: Reindex all files.

        Returns:
            Counters ``updated``, ``removed`` and ``total``.
        """
        known = {r[0]: (r[1], r[2]) for r in con.execute("SELECT path, mtime_ns, size FROM files")}
        seen: set[str] = set()
        updated = 0
        for rel in self.vault.iter_files(ALL_AREAS):
            seen.add(rel)
            doc = self._changed_doc(rel, known.get(rel), force)
            if doc is not None:
                self._index_doc(con, doc)
                updated += 1
        removed = [p for p in known if p not in seen]
        for rel in removed:
            self._forget(con, rel)
        return {"updated": updated, "removed": len(removed), "total": len(seen)}

    def refresh(self) -> dict[str, int]:
        """Update the index incrementally.

        Returns:
            Counters ``updated``, ``removed`` and ``total``.
        """
        return self._with_db(self._refresh)

    def rebuild(self) -> dict[str, int]:
        """Delete and rebuild the index.

        Returns:
            Counters ``updated``, ``removed`` and ``total``.
        """
        self._drop()
        return self._with_db(lambda con: self._refresh(con, force=True))

    # Queries ******************************************************************

    def find_id(self, doc_id: str) -> list[str]:
        """Paths for a document ID.

        Args:
            doc_id: Document ID.

        Returns:
            Sorted paths (several for duplicate IDs).
        """
        def query(con: sqlite3.Connection) -> list[str]:
            self._refresh(con)
            return [r[0] for r in con.execute("SELECT path FROM files WHERE id=? ORDER BY path", (doc_id,))]

        return self._with_db(query)

    def find_citation(self, value: str) -> list[str]:
        """Paths for a short citation (``short_citation``).

        Args:
            value: Short citation.

        Returns:
            Sorted paths in ``documents/``.
        """
        key = citation_key(value)

        def query(con: sqlite3.Connection) -> list[str]:
            self._refresh(con)
            rows = con.execute("SELECT path, citation FROM files WHERE citation IS NOT NULL AND area='documents'")
            return sorted(path for path, cit in rows if citation_key(cit) == key)

        return self._with_db(query)

    def ids(self) -> set[str]:
        """All assigned IDs.

        Returns:
            Set of the IDs in the vault.
        """
        def query(con: sqlite3.Connection) -> set[str]:
            self._refresh(con)
            return {r[0] for r in con.execute("SELECT id FROM files WHERE id IS NOT NULL")}

        return self._with_db(query)

    def backlinks(self, doc: Doc) -> list[str]:
        """Files that link to a document via wikilink.

        Args:
            doc: Target document.

        Returns:
            Sorted paths of the linking files (without the document itself).
        """
        keys = sorted(doc.link_keys())

        def query(con: sqlite3.Connection) -> list[str]:
            self._refresh(con)
            marks = ",".join("?" * len(keys))
            rows = con.execute(
                f"SELECT DISTINCT src FROM links WHERE target IN ({marks}) AND src != ? ORDER BY src",
                (*keys, doc.rel),
            )
            return [r[0] for r in rows]

        return self._with_db(query)

    def search(self, query: str, areas: Iterable[str], limit: int) -> list[dict[str, Any]]:
        """Full-text search with prefix search and weighting (title 5, aliases/tags/topics 3, summary 2).

        First all terms are required; without hits one of them is enough.

        Args:
            query: Search terms.
            areas: Areas (``documents``, ``wiki``, ``scratch``).
            limit: Maximum number of hits.

        Returns:
            Hits with path, area, kind, ID, version, title, type, summary, date, score and
            the terms used.
        """
        terms = query_terms(query)
        area_list = list(areas)
        results: list[dict[str, Any]] = []
        if terms:
            def run(con: sqlite3.Connection) -> list[tuple[Any, ...]]:
                self._refresh(con)
                rows = _search_rows(con, terms, area_list, limit, " ")
                if not rows and len(terms) > 1:
                    rows = _search_rows(con, terms, area_list, limit, " OR ")
                return rows

            results = [_hit(row, terms) for row in self._with_db(run)]
        return results

# Functions *******************************************************************


def fold(text: str) -> str:
    """Build the index text: original plus a version with umlauts spelled out.

    The tokenizer removes diacritics (ü → u). With the second version the search finds
    "Überlauf" also via "Ueberlauf" and "uberlauf".

    Args:
        text: Original text.

    Returns:
        Text for the index.
    """
    alt = transliterate(text)
    return text if alt == text else f"{text}\n{alt}"


def strip_marks(text: str) -> str:
    """Remove diacritical marks.

    Args:
        text: Arbitrary text.

    Returns:
        Text without accents and umlaut dots.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _as_list(value: Any) -> list[str]:
    """Frontmatter value as a list of strings.

    Args:
        value: List, single value or ``None``.

    Returns:
        List of strings (empty for ``None``).
    """
    if isinstance(value, list):
        items = [str(v) for v in value]
    elif value is None:
        items = []
    else:
        items = [str(value)]
    return items


def query_terms(query: str) -> list[str]:
    """Extract search terms from a query.

    Args:
        query: Free text.

    Returns:
        Words in lower case without diacritics.
    """
    return [t for t in re.findall(r"\w+", strip_marks(query).lower()) if t]


def _search_rows(
    con: sqlite3.Connection, terms: list[str], areas: list[str], limit: int, joiner: str
) -> list[tuple[Any, ...]]:
    """Run an FTS query.

    Args:
        con: Connection.
        terms: Search terms (searched as prefixes).
        areas: Areas.
        limit: Maximum number of hits.
        joiner: ``" "`` (all terms) or ``" OR "`` (one term is enough).

    Returns:
        Hit rows sorted by relevance.
    """
    match = joiner.join(f'"{t}"*' for t in terms)
    sql = SEARCH_SQL.format(marks=",".join("?" * len(areas)))
    return con.execute(sql, (match, *areas, limit)).fetchall()


def _hit(row: tuple[Any, ...], terms: list[str]) -> dict[str, Any]:
    """Convert a hit row into a result.

    Args:
        row: Row from ``SEARCH_SQL``.
        terms: Search terms used.

    Returns:
        Hit as a dictionary; the score is the negated BM25 rank.
    """
    path, area, kind, doc_id, version, title, typ, summary, updated, citation, rank = row
    return {
        "path": path, "area": area, "kind": kind, "id": doc_id, "version": version,
        "title": title, "type": typ or ("document" if area == "documents" else ""),
        "summary": summary, "date_updated": updated, "short_citation": citation, "score": round(-rank, 4),
        "terms": terms,
    }


def snippet(body: str, terms: list[str], width: int = SNIPPET_WIDTH) -> str:
    """Excerpt from the original text around the first hit.

    Args:
        body: Original text.
        terms: Search terms.
        width: Length of the excerpt.

    Returns:
        Excerpt, possibly with "…" at the edges; without a hit the beginning of the text.
    """
    flat = " ".join(body.split())
    pos = -1
    for variant in (strip_marks(flat).lower(), strip_marks(transliterate(flat)).lower()):
        ratio = len(flat) / max(len(variant), 1)
        hits = [int(variant.find(t) * ratio) for t in terms if variant.find(t) >= 0]
        if hits:
            pos = min(hits)
            break
    if pos < 0:
        result = flat[:width]
    else:
        start = max(0, pos - width // 3)
        end = min(len(flat), start + width)
        result = ("…" if start > 0 else "") + flat[start:end] + ("…" if end < len(flat) else "")
    return result

# Main ************************************************************************
