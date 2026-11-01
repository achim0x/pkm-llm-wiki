"""Suchindex in `PKM_CACHE_DIR/index.db` (Spezifikation 7.4). Reiner Wegwerf-Cache."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections.abc import Iterable
from contextlib import closing
from typing import Any

from .config import Config
from .errors import PkmError
from .paths import transliterate
from .vault import Doc, Vault, extract_links, link_key, summary_of

SCHEMA = 1
WEIGHTS = (0.0, 5.0, 3.0, 2.0, 1.0)  # path, title, meta, summary, body

DDL = """
CREATE TABLE IF NOT EXISTS info(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS files(
    path TEXT PRIMARY KEY, area TEXT, kind TEXT, mtime_ns INTEGER, size INTEGER,
    id TEXT, version INTEGER, title TEXT, type TEXT, summary TEXT, updated TEXT,
    file_hash TEXT, error TEXT
);
CREATE INDEX IF NOT EXISTS files_id ON files(id);
CREATE TABLE IF NOT EXISTS links(src TEXT, target TEXT);
CREATE INDEX IF NOT EXISTS links_target ON links(target);
CREATE INDEX IF NOT EXISTS links_src ON links(src);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    path UNINDEXED, title, meta, summary, body, tokenize = 'unicode61 remove_diacritics 2'
);
"""


def fold(text: str) -> str:
    """Indextext: Original plus Fassung mit ausgeschriebenen Umlauten.

    Der Tokenizer entfernt Diakritika (ü → u). Mit der zweiten Fassung findet die Suche
    „Überlauf“ auch über „Ueberlauf“ und „uberlauf“.
    """
    alt = transliterate(text)
    return text if alt == text else f"{text}\n{alt}"


def strip_marks(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if value is None:
        return []
    return [str(value)]


def query_terms(query: str) -> list[str]:
    return [t for t in re.findall(r"\w+", strip_marks(query).lower()) if t]


def snippet(body: str, terms: list[str], width: int = 160) -> str:
    """Ausschnitt aus dem Originaltext um den ersten Treffer."""
    flat = " ".join(body.split())
    pos = -1
    for variant in (strip_marks(flat).lower(), strip_marks(transliterate(flat)).lower()):
        ratio = len(flat) / max(len(variant), 1)
        for t in terms:
            p = variant.find(t)
            if p >= 0 and (pos < 0 or int(p * ratio) < pos):
                pos = int(p * ratio)
        if pos >= 0:
            break
    if pos < 0:
        return flat[:width]
    start = max(0, pos - width // 3)
    end = min(len(flat), start + width)
    out = flat[start:end]
    return ("…" if start > 0 else "") + out + ("…" if end < len(flat) else "")


class SearchIndex:
    def __init__(self, cfg: Config, vault: Vault) -> None:
        problem = cfg.cache_dir_problem()
        if problem:
            raise PkmError("index_unavailable", problem)
        self.cfg = cfg
        self.vault = vault
        self.path = cfg.index_path

    # --- Verbindung ---
    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        con.execute("PRAGMA journal_mode=DELETE")
        con.executescript(DDL)
        row = con.execute("SELECT value FROM info WHERE key='schema'").fetchone()
        if row is None:
            con.execute("INSERT INTO info VALUES('schema', ?)", (str(SCHEMA),))
            con.commit()
        elif row[0] != str(SCHEMA):
            con.close()
            raise sqlite3.DatabaseError("schema mismatch")
        return con

    def _drop(self) -> None:
        for suffix in ("", "-journal", "-wal", "-shm"):
            p = self.path.with_name(self.path.name + suffix)
            if p.exists():
                p.unlink()

    def _with_db(self, fn):
        """Funktion mit Verbindung ausführen; bei beschädigtem Index neu aufbauen."""
        for attempt in (1, 2):
            try:
                with closing(self._connect()) as con:
                    result = fn(con)
                    con.commit()
                    return result
            except sqlite3.DatabaseError:
                if attempt == 2:
                    raise
                self._drop()
        return None

    # --- Aktualisierung ---
    def _index_doc(self, con: sqlite3.Connection, doc: Doc) -> None:
        con.execute("DELETE FROM files WHERE path=?", (doc.rel,))
        con.execute("DELETE FROM fts WHERE path=?", (doc.rel,))
        con.execute("DELETE FROM links WHERE src=?", (doc.rel,))
        meta = doc.meta
        summary = summary_of(doc) if doc.kind == "md" else ""
        file_hash = doc.hashes.file_hash if doc.hashes else doc.bin_hash
        con.execute(
            "INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                doc.rel, doc.area, doc.kind, doc.mtime_ns, doc.size, doc.id, doc.version,
                doc.title, str(meta.get("type") or ""), summary, str(meta.get("updated") or ""),
                file_hash, doc.error,
            ),
        )
        tags = " ".join(_as_list(meta.get("aliases")) + _as_list(meta.get("tags")) + _as_list(meta.get("topics")))
        body = doc.body if doc.kind == "md" else ""
        con.execute(
            "INSERT INTO fts(path, title, meta, summary, body) VALUES(?,?,?,?,?)",
            (doc.rel, fold(doc.title), fold(tags), fold(summary), fold(body)),
        )
        if doc.kind == "md":
            con.executemany(
                "INSERT INTO links VALUES(?,?)", [(doc.rel, link_key(t)) for t in extract_links(body)]
            )

    def _refresh(self, con: sqlite3.Connection, force: bool = False) -> dict[str, int]:
        known = {r[0]: (r[1], r[2]) for r in con.execute("SELECT path, mtime_ns, size FROM files")}
        seen: set[str] = set()
        updated = 0
        for rel in self.vault.iter_files():
            seen.add(rel)
            p = self.vault.root / rel
            try:
                st = p.stat()
            except OSError:
                continue
            if not force and known.get(rel) == (st.st_mtime_ns, st.st_size):
                continue
            try:
                doc = self.vault.load(rel)
            except (PkmError, OSError):
                continue
            self._index_doc(con, doc)
            updated += 1
        removed = [p for p in known if p not in seen]
        for rel in removed:
            con.execute("DELETE FROM files WHERE path=?", (rel,))
            con.execute("DELETE FROM fts WHERE path=?", (rel,))
            con.execute("DELETE FROM links WHERE src=?", (rel,))
        return {"updated": updated, "removed": len(removed), "total": len(seen)}

    def refresh(self) -> dict[str, int]:
        return self._with_db(self._refresh)

    def rebuild(self) -> dict[str, int]:
        self._drop()
        return self._with_db(lambda con: self._refresh(con, force=True))

    # --- Abfragen ---
    def find_id(self, doc_id: str) -> list[str]:
        def q(con):
            self._refresh(con)
            return [r[0] for r in con.execute("SELECT path FROM files WHERE id=? ORDER BY path", (doc_id,))]

        return self._with_db(q)

    def ids(self) -> set[str]:
        def q(con):
            self._refresh(con)
            return {r[0] for r in con.execute("SELECT id FROM files WHERE id IS NOT NULL")}

        return self._with_db(q)

    def backlinks(self, doc: Doc) -> list[str]:
        keys = sorted(doc.link_keys())

        def q(con):
            self._refresh(con)
            marks = ",".join("?" * len(keys))
            rows = con.execute(
                f"SELECT DISTINCT src FROM links WHERE target IN ({marks}) AND src != ? ORDER BY src",
                (*keys, doc.rel),
            )
            return [r[0] for r in rows]

        return self._with_db(q)

    def search(self, query: str, areas: Iterable[str], limit: int) -> list[dict[str, Any]]:
        terms = query_terms(query)
        if not terms:
            return []
        areas = list(areas)

        def run(con, joiner: str):
            match = joiner.join(f'"{t}"*' for t in terms)
            marks = ",".join("?" * len(areas))
            sql = (
                "SELECT f.path, f.area, f.kind, f.id, f.version, f.title, f.type, f.summary, f.updated, "
                f"bm25(fts, {', '.join(str(w) for w in WEIGHTS)}) AS rank "
                "FROM fts JOIN files f ON f.path = fts.path "
                f"WHERE fts MATCH ? AND f.area IN ({marks}) ORDER BY rank LIMIT ?"
            )
            return con.execute(sql, (match, *areas, limit)).fetchall()

        def q(con):
            self._refresh(con)
            rows = run(con, " ")
            if not rows and len(terms) > 1:
                rows = run(con, " OR ")
            return rows

        rows = self._with_db(q)
        out = []
        for path, area, kind, doc_id, version, title, typ, summary, updated, rank in rows:
            out.append(
                {
                    "path": path, "area": area, "kind": kind, "id": doc_id, "version": version,
                    "title": title, "type": typ or ("document" if area == "documents" else ""),
                    "summary": summary, "updated": updated, "score": round(-rank, 4), "terms": terms,
                }
            )
        return out
