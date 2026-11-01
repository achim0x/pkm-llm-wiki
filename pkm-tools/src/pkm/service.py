"""Fachliche Fassade für MCP-Server und CLI. Lesende Funktionen (Spezifikation 7.3)."""

from __future__ import annotations

import difflib
import json
from datetime import datetime
from typing import Any

from . import hashes
from .config import Config
from .errors import PkmError
from .gitlayer import Commit, Git
from .ids import is_valid_id
from .index import SearchIndex, query_terms, snippet
from .state import classify, load_state, state_key
from .vault import AREAS, Doc, Vault, extract_links, load_text_doc, section_summary

MAX_RESULTS = 25
HISTORY_DIFF_LINES = 400


def unified_diff(old: str, new: str, a: str, b: str, max_lines: int | None = None) -> str:
    lines = list(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), a, b))
    if max_lines is not None and len(lines) > max_lines:
        rest = len(lines) - max_lines
        lines = lines[:max_lines] + [f"… ({rest} weitere Zeilen gekürzt)\n"]
    return "".join(lines)


class Service:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.vault = Vault(cfg)
        self.git = Git(cfg.git_dir, cfg.root, cfg.git_author)
        self._index: SearchIndex | None = None

    # --- Hilfen ---
    def now(self) -> datetime:
        return datetime.now(self.cfg.tz).replace(microsecond=0)

    @property
    def index(self) -> SearchIndex:
        if self._index is None:
            self._index = SearchIndex(self.cfg, self.vault)
        return self._index

    def index_available(self) -> bool:
        return self.cfg.cache_dir_problem() is None

    def find_id(self, doc_id: str) -> list[str]:
        if self.index_available():
            try:
                paths = self.index.find_id(doc_id)
                return [p for p in paths if self.vault.exists(p)]
            except Exception:  # noqa: BLE001 - Index ist nur ein Cache
                pass
        return self.vault.scan_id(doc_id)

    def known_ids(self) -> set[str]:
        if self.index_available():
            try:
                return self.index.ids()
            except Exception:  # noqa: BLE001
                pass
        return {d.id for rel in self.vault.iter_files() if rel.endswith(".md") for d in [self.vault.load(rel)] if d.id}

    def resolve(self, target: str, areas: tuple[str, ...] = AREAS) -> str:
        return self.vault.resolve(target, areas, self.find_id)

    def load(self, target: str, areas: tuple[str, ...] = AREAS) -> Doc:
        return self.vault.load(self.resolve(target, areas))

    def state(self) -> dict[str, Any]:
        return load_state(self.cfg)

    def processed(self, doc: Doc, state: dict[str, Any] | None = None) -> bool:
        state = state if state is not None else self.state()
        key = state_key(doc)
        entry = state["documents"].get(key) if key else None
        return classify(doc, entry) is None

    # --- Versionen aus Git ---
    def versions(self, doc_id: str) -> list[Commit]:
        return [c for c in self.git.log_for_id(doc_id) if c.version is not None]

    def commit_for_version(self, doc_id: str, version: int) -> Commit:
        matching = [c for c in self.versions(doc_id) if c.version == version and c.path]
        if not matching:
            raise PkmError("not_found", f"Version {version} von {doc_id} nicht im Verlauf.", version=version)
        return matching[-1]

    def text_at_version(self, doc_id: str, version: int) -> tuple[str, str]:
        c = self.commit_for_version(doc_id, version)
        return c.path or "", self.git.show_file(c.sha, c.path or "").decode("utf-8", "replace")

    def _target_id(self, target: str) -> tuple[str, str | None]:
        """ID und aktueller Pfad; bei `id:` auch für gelöschte Dokumente (nur Git)."""
        t = target.strip()
        try:
            doc = self.load(t)
        except PkmError as exc:
            if exc.status == "not_found" and t.startswith("id:") and is_valid_id(t[3:].strip()):
                return t[3:].strip(), None
            raise
        if not doc.id:
            raise PkmError("not_found", f"{doc.rel} hat keine ID (noch nicht versioniert).", path=doc.rel)
        return doc.id, doc.rel

    # --- Tools ---
    def search(self, query: str, scope: str = "wiki", max_results: int = 8) -> dict[str, Any]:
        areas = {"wiki": ("wiki",), "documents": ("documents",), "all": AREAS}.get(scope)
        if areas is None:
            raise PkmError("invalid_argument", "scope muss wiki, documents oder all sein.")
        max_results = max(1, min(int(max_results), MAX_RESULTS))
        hits = self.index.search(query, areas, max_results)
        state = self.state()
        results = []
        for h in hits:
            item = {k: h[k] for k in ("id", "path", "title", "type", "summary", "score", "updated")}
            try:
                doc = self.vault.load(h["path"])
            except PkmError:
                continue
            item["snippet"] = snippet(doc.body, h["terms"]) if doc.kind == "md" else ""
            if h["area"] == "documents":
                item["version"] = doc.version
                item["processed"] = self.processed(doc, state)
            results.append(item)
        return {"status": "ok", "query": query, "scope": scope, "results": results, "terms": query_terms(query)}

    def read(self, target: str, version: int | None = None) -> dict[str, Any]:
        if version is not None:
            doc_id, rel = self._target_id(target)
            path, text = self.text_at_version(doc_id, int(version))
            doc = load_text_doc(path, text.encode("utf-8"))
            result = self._doc_result(doc, with_links=False)
            result.update({"editable": False, "current_path": rel, "version": version})
            return result
        doc = self.load(target)
        return self._doc_result(doc, with_links=True)

    def _doc_result(self, doc: Doc, with_links: bool) -> dict[str, Any]:
        if doc.kind == "bin":
            return {
                "status": "ok", "kind": "binary", "id": None, "version": None, "path": doc.rel,
                "size": doc.size, "hash": doc.bin_hash, "editable": False,
            }
        result: dict[str, Any] = {
            "status": "ok" if not doc.error else doc.error,
            "id": doc.id,
            "version": doc.version,
            "path": doc.rel,
            "title": doc.title,
            "frontmatter": doc.meta,
            "content": doc.body if not doc.error or doc.error == "invalid_frontmatter" else "",
            "hash": doc.hashes.file_hash if doc.hashes else None,
            "editable": doc.editable,
            "sections": section_summary(doc),
        }
        if doc.error:
            result["message"] = doc.error_message
        if with_links:
            result["links"] = extract_links(doc.body)
            try:
                result["backlinks"] = self.index.backlinks(doc) if self.index_available() else []
            except Exception:  # noqa: BLE001
                result["backlinks"] = []
        if doc.area == "wiki":
            from .citations import page_citations_for_read

            result["citations"] = page_citations_for_read(doc)
        return result

    def history(self, target: str, diff_from: int | None = None, diff_to: int | None = None) -> dict[str, Any]:
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
                raise PkmError("not_found", "Keine Versionen im Verlauf.")
            to = int(diff_to) if diff_to is not None else max(versions)
            _, old = self.text_at_version(doc_id, int(diff_from))
            _, new = self.text_at_version(doc_id, to)
            result["diff_from"], result["diff_to"] = int(diff_from), to
            result["diff"] = unified_diff(old, new, f"v{diff_from}", f"v{to}", HISTORY_DIFF_LINES)
        return result

    def show(self, target: str, version: int, section: str | None = None) -> dict[str, Any]:
        from .parse import normalize_key_input

        res = self.read(target, version)
        if section is not None:
            key = normalize_key_input(section)
            doc = load_text_doc(res["path"], (self._raw_version(target, version)).encode("utf-8"))
            sec = doc.parsed.section(key) if doc.parsed else None
            if sec is None:
                raise PkmError("not_found", f"Abschnitt nicht gefunden: {section}", section=section)
            res["section"] = key
            res["content"] = "\n".join(([sec.heading] if sec.heading else []) + sec.content_lines)
            res["section_hash"] = doc.hashes.sections[key] if doc.hashes else None
        return res

    def _raw_version(self, target: str, version: int) -> str:
        doc_id, _ = self._target_id(target)
        return self.text_at_version(doc_id, version)[1]

    def read_index(self) -> dict[str, Any]:
        p = self.cfg.root / "wiki" / "index.md"
        content = p.read_text(encoding="utf-8") if p.is_file() else ""
        return {"status": "ok", "path": "wiki/index.md", "content": content}

    def list_unprocessed(self) -> dict[str, Any]:
        """Wie `pkm pending`, als flache Liste mit Kategorie (live berechnet)."""
        from .maint import Maintenance

        pend = Maintenance(self).pending()
        docs = [
            {"category": category, **item}
            for category in ("new", "changed", "meta_changed", "moved", "deleted")
            for item in pend[category]
        ]
        return {"status": "ok", "count": len(docs), "documents": docs, "problems": pend["problems"]}

    def reindex(self) -> dict[str, Any]:
        return {"status": "ok", **self.index.rebuild()}

    def show_citations(self, target: str, statement: str | None = None,
                       with_excerpt: bool = False) -> dict[str, Any]:
        from .citations import show_citations

        return show_citations(self, target, statement, with_excerpt)

    # --- schreibende Tools (7.2) ---
    @property
    def writer(self):
        from .writer import Writer

        return Writer(self)

    def create_document(self, **kwargs: Any) -> dict[str, Any]:
        return self.writer.create_document(**kwargs)

    def rewrite_document(self, **kwargs: Any) -> dict[str, Any]:
        return self.writer.rewrite_document(**kwargs)

    def append_to_document(self, **kwargs: Any) -> dict[str, Any]:
        return self.writer.append_to_document(**kwargs)

    def edit_document(self, **kwargs: Any) -> dict[str, Any]:
        return self.writer.edit_document(**kwargs)

    def update_frontmatter(self, **kwargs: Any) -> dict[str, Any]:
        return self.writer.update_frontmatter(**kwargs)

    def restore_document(self, target: str, version: int, expected_hash: str | None,
                         source: str = "chat") -> dict[str, Any]:
        return self.writer.restore_document(target, version, expected_hash, source)


def dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


__all__ = ["Service", "hashes", "unified_diff"]
