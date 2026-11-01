"""Fachliche Fassade für MCP-Server und CLI (Spezifikation 7.2, 7.3).

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
# along with this program.  If not, see <https://gnu.org>.

# *****************************************************************************

# Imports *********************************************************************

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from . import citations
from .config import Config
from .diffs import unified_diff
from .errors import PkmError
from .gitlayer import Commit, Git
from .ids import is_valid_id
from .index import SearchIndex, query_terms, snippet
from .maint import Maintenance
from .parse import normalize_key_input
from .state import classify, load_state, state_key
from .vault import AREAS, Doc, Vault, extract_links, load_text_doc, section_summary
from .writer import Writer

# Variables *******************************************************************

MAX_RESULTS = 25
HISTORY_DIFF_LINES = 400
SCOPES = {"wiki": ("wiki",), "documents": ("documents",), "all": AREAS}
UNPROCESSED_CATEGORIES = ("new", "changed", "meta_changed", "moved", "deleted")
INDEX_ERRORS = (sqlite3.Error, PkmError, OSError)

# Classes *********************************************************************


class Service:  # pylint: disable=too-many-public-methods
    """Fassade über Vault, Git, Suchindex und Schreiblogik; eine Methode je Tool bzw. Befehl."""

    def __init__(self, cfg: Config) -> None:
        """Dienst anlegen.

        Args:
            cfg: Konfiguration.
        """
        self.cfg = cfg
        self.vault = Vault(cfg)
        self.git = Git(cfg.git_dir, cfg.root, cfg.git_author)
        self._index: SearchIndex | None = None

    # Hilfen *******************************************************************

    def now(self) -> datetime:
        """Aktuelle Zeit in ``PKM_TZ`` ohne Mikrosekunden.

        Returns:
            Zeitpunkt mit Zeitzone.
        """
        return datetime.now(self.cfg.tz).replace(microsecond=0)

    @property
    def index(self) -> SearchIndex:
        """Suchindex (beim ersten Zugriff angelegt).

        Returns:
            Den Index.

        Raises:
            PkmError: ``index_unavailable``, wenn ``PKM_CACHE_DIR`` im Vault liegt.
        """
        if self._index is None:
            self._index = SearchIndex(self.cfg, self.vault)
        return self._index

    @property
    def writer(self) -> Writer:
        """Schreiblogik für diesen Dienst.

        Returns:
            Ein ``Writer``.
        """
        return Writer(self)

    def index_available(self) -> bool:
        """Prüfen, ob der Suchindex genutzt werden darf.

        Returns:
            ``True``, wenn ``PKM_CACHE_DIR`` außerhalb des Vaults liegt.
        """
        return self.cfg.cache_dir_problem() is None

    def find_id(self, doc_id: str) -> list[str]:
        """Pfade zu einer ID suchen, bevorzugt über den Index.

        Args:
            doc_id: Dokument-ID.

        Returns:
            Existierende Pfade mit dieser ID.
        """
        paths = None
        if self.index_available():
            try:
                paths = [p for p in self.index.find_id(doc_id) if self.vault.exists(p)]
            except INDEX_ERRORS:  # Der Index ist nur ein Cache.
                paths = None
        return paths if paths is not None else self.vault.scan_id(doc_id)

    def known_ids(self) -> set[str]:
        """Alle vergebenen IDs, bevorzugt über den Index.

        Returns:
            Menge der IDs.
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

    def resolve(self, target: str, areas: tuple[str, ...] = AREAS) -> str:
        """Ziel auflösen (Pfad, Wikilink, Kurzname oder ``id:``).

        Args:
            target: Ziel.
            areas: Erlaubte Bereiche.

        Returns:
            Relativer Pfad.
        """
        return self.vault.resolve(target, areas, self.find_id)

    def load(self, target: str, areas: tuple[str, ...] = AREAS) -> Doc:
        """Ziel auflösen und laden.

        Args:
            target: Ziel.
            areas: Erlaubte Bereiche.

        Returns:
            Das Dokument.
        """
        return self.vault.load(self.resolve(target, areas))

    def state(self) -> dict[str, Any]:
        """Verarbeitungsstand lesen.

        Returns:
            Inhalt von ``state.json``.
        """
        return load_state(self.cfg)

    def processed(self, doc: Doc, state: dict[str, Any] | None = None) -> bool:
        """Prüfen, ob der aktuelle Stand eines Dokuments im Wiki eingearbeitet ist.

        Args:
            doc: Dokument.
            state: Bereits gelesener Stand; ohne Angabe wird er gelesen.

        Returns:
            ``True``, wenn ``classify`` nichts zu tun meldet.
        """
        state = state if state is not None else self.state()
        key = state_key(doc)
        entry = state["documents"].get(key) if key else None
        return classify(doc, entry) is None

    # Versionen aus Git ********************************************************

    def versions(self, doc_id: str) -> list[Commit]:
        """Commits eines Dokuments mit Versionsnummer.

        Args:
            doc_id: Dokument-ID.

        Returns:
            Commits, älteste zuerst.
        """
        return [c for c in self.git.log_for_id(doc_id) if c.version is not None]

    def commit_for_version(self, doc_id: str, version: int) -> Commit:
        """Commit zu einer Version (bei mehreren der letzte, z. B. nach reinem Verschieben).

        Args:
            doc_id: Dokument-ID.
            version: Versionsnummer.

        Returns:
            Den Commit.

        Raises:
            PkmError: ``not_found``, wenn die Version nicht im Verlauf ist.
        """
        matching = [c for c in self.versions(doc_id) if c.version == version and c.path]
        if not matching:
            raise PkmError("not_found", f"Version {version} von {doc_id} nicht im Verlauf.", version=version)
        return matching[-1]

    def text_at_version(self, doc_id: str, version: int) -> tuple[str, str]:
        """Pfad und Text eines Dokuments in einer Version.

        Args:
            doc_id: Dokument-ID.
            version: Versionsnummer.

        Returns:
            Tupel aus (damaliger Pfad, Text).
        """
        c = self.commit_for_version(doc_id, version)
        return c.path or "", self.git.show_file(c.sha, c.path or "").decode("utf-8", "replace")

    def _target_id(self, target: str) -> tuple[str, str | None]:
        """ID und aktuellen Pfad bestimmen; bei ``id:`` auch für gelöschte Dokumente.

        Args:
            target: Ziel.

        Returns:
            Tupel aus (ID, aktueller Pfad oder ``None``, wenn das Dokument gelöscht ist).

        Raises:
            PkmError: ``not_found``, wenn das Ziel fehlt oder keine ID hat.
        """
        t = target.strip()
        try:
            doc = self.load(t)
        except PkmError as exc:
            if not (exc.status == "not_found" and t.startswith("id:") and is_valid_id(t[3:].strip())):
                raise
            doc = None
        if doc is None:
            result: tuple[str, str | None] = (t[3:].strip(), None)
        elif not doc.id:
            raise PkmError("not_found", f"{doc.rel} hat keine ID (noch nicht versioniert).", path=doc.rel)
        else:
            result = (doc.id, doc.rel)
        return result

    # Lesende Tools ************************************************************

    def search(self, query: str, scope: str = "wiki", max_results: int = 8) -> dict[str, Any]:
        """Tool ``search``.

        Args:
            query: Suchbegriffe.
            scope: ``wiki``, ``documents`` oder ``all``.
            max_results: Höchstzahl der Treffer (1–25).

        Returns:
            Treffer mit ``id``, ``path``, ``title``, ``type``, ``summary``, ``snippet``, ``score``,
            ``updated`` und bei Dokumenten ``version`` und ``processed``.

        Raises:
            PkmError: ``invalid_argument`` bei unbekanntem ``scope``.
        """
        areas = SCOPES.get(scope)
        if areas is None:
            raise PkmError("invalid_argument", "scope muss wiki, documents oder all sein.")
        hits = self.index.search(query, areas, max(1, min(int(max_results), MAX_RESULTS)))
        state = self.state()
        results = []
        for hit in hits:
            item = self._search_item(hit, state)
            if item is not None:
                results.append(item)
        return {"status": "ok", "query": query, "scope": scope, "results": results, "terms": query_terms(query)}

    def _search_item(self, hit: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
        """Suchtreffer um Ausschnitt, Version und Verarbeitungsstand ergänzen.

        Args:
            hit: Treffer aus dem Index.
            state: Verarbeitungsstand.

        Returns:
            Ergebnis-Eintrag oder ``None``, wenn die Datei inzwischen fehlt.
        """
        item: dict[str, Any] | None = None
        try:
            doc = self.vault.load(hit["path"])
        except PkmError:
            doc = None
        if doc is not None:
            item = {k: hit[k] for k in ("id", "path", "title", "type", "summary", "score", "updated")}
            item["snippet"] = snippet(doc.body, hit["terms"]) if doc.kind == "md" else ""
            if hit["area"] == "documents":
                item["version"] = doc.version
                item["processed"] = self.processed(doc, state)
        return item

    def read(self, target: str, version: int | None = None) -> dict[str, Any]:
        """Tool ``read``.

        Args:
            target: Pfad, Wikilink oder ``id:``.
            version: Frühere Version aus Git (nur lesend).

        Returns:
            Inhalt, Frontmatter, ``hash``, ``editable``, Abschnitte, Links und Rückverweise;
            bei Wiki-Seiten zusätzlich die geparsten Belege.
        """
        if version is not None:
            doc_id, rel = self._target_id(target)
            path, text = self.text_at_version(doc_id, int(version))
            result = self._doc_result(load_text_doc(path, text.encode("utf-8")), with_links=False)
            result.update({"editable": False, "current_path": rel, "version": version})
        else:
            result = self._doc_result(self.load(target), with_links=True)
        return result

    def _doc_result(self, doc: Doc, with_links: bool) -> dict[str, Any]:
        """Rückgabe von ``read`` für ein geladenes Dokument bilden.

        Args:
            doc: Dokument.
            with_links: Links und Rückverweise ermitteln.

        Returns:
            Das Ergebnis-Wörterbuch.
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
        return result

    def _backlinks(self, doc: Doc) -> list[str]:
        """Rückverweise über den Index (leer, wenn der Index nicht verfügbar ist).

        Args:
            doc: Dokument.

        Returns:
            Pfade der verweisenden Dateien.
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
            target: Dokument (auch ``id:`` eines gelöschten Dokuments).
            diff_from: Version, ab der verglichen wird.
            diff_to: Version, bis zu der verglichen wird; Standard ist die neueste.

        Returns:
            Versionen mit Datum, Quelle, Notiz und Commit; mit ``diff_from`` zusätzlich ``diff``.

        Raises:
            PkmError: ``not_found``, wenn es keine Versionen gibt.
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
                raise PkmError("not_found", "Keine Versionen im Verlauf.")
            to = int(diff_to) if diff_to is not None else max(versions)
            _, old = self.text_at_version(doc_id, int(diff_from))
            _, new = self.text_at_version(doc_id, to)
            result["diff_from"], result["diff_to"] = int(diff_from), to
            result["diff"] = unified_diff(old, new, f"v{diff_from}", f"v{to}", HISTORY_DIFF_LINES)
        return result

    def show(self, target: str, version: int, section: str | None = None) -> dict[str, Any]:
        """CLI ``pkm show``: frühere Version, optional nur ein Abschnitt.

        Args:
            target: Dokument.
            version: Versionsnummer.
            section: Abschnittsschlüssel.

        Returns:
            Wie ``read`` mit ``version``; mit ``section`` zusätzlich ``section`` und ``section_hash``
            und ``content`` nur mit diesem Abschnitt.

        Raises:
            PkmError: ``not_found``, wenn der Abschnitt fehlt.
        """
        res = self.read(target, version)
        if section is not None:
            key = normalize_key_input(section)
            doc_id, _ = self._target_id(target)
            doc = load_text_doc(res["path"], self.text_at_version(doc_id, version)[1].encode("utf-8"))
            sec = doc.parsed.section(key) if doc.parsed else None
            if sec is None:
                raise PkmError("not_found", f"Abschnitt nicht gefunden: {section}", section=section)
            res["section"] = key
            res["content"] = "\n".join(([sec.heading] if sec.heading else []) + sec.content_lines)
            res["section_hash"] = doc.hashes.sections[key] if doc.hashes else None
        return res

    def read_index(self) -> dict[str, Any]:
        """Tool ``read_index``.

        Returns:
            Inhalt von ``wiki/index.md`` (leer, wenn die Datei fehlt).
        """
        p = self.cfg.root / "wiki" / "index.md"
        content = p.read_text(encoding="utf-8") if p.is_file() else ""
        return {"status": "ok", "path": "wiki/index.md", "content": content}

    def list_unprocessed(self) -> dict[str, Any]:
        """Tool ``list_unprocessed``: wie ``pkm pending`` als flache Liste (live berechnet).

        Returns:
            Anzahl, Dokumente mit ``category`` und gefundene Probleme.
        """
        pend = Maintenance(self).pending()
        docs = [{"category": category, **item} for category in UNPROCESSED_CATEGORIES for item in pend[category]]
        return {"status": "ok", "count": len(docs), "documents": docs, "problems": pend["problems"]}

    def reindex(self) -> dict[str, Any]:
        """CLI ``pkm reindex``.

        Returns:
            Zähler des Neuaufbaus.
        """
        return {"status": "ok", **self.index.rebuild()}

    def show_citations(self, target: str, statement: str | None = None, with_excerpt: bool = False) -> dict[str, Any]:
        """Tool ``show_citations``.

        Args:
            target: Wiki-Seite.
            statement: Textstück zum Eingrenzen.
            with_excerpt: Wortlaut aus dem Original laden.

        Returns:
            Siehe ``citations.show_citations``.
        """
        return citations.show_citations(self, target, statement, with_excerpt)

    # Schreibende Tools (7.2) **************************************************

    def create_document(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``create_document``.

        Args:
            **kwargs: Parameter wie ``Writer.create_document``.

        Returns:
            Rückgabe des Writers.
        """
        return self.writer.create_document(**kwargs)

    def rewrite_document(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``rewrite_document``.

        Args:
            **kwargs: Parameter wie ``Writer.rewrite_document``.

        Returns:
            Rückgabe des Writers.
        """
        return self.writer.rewrite_document(**kwargs)

    def append_to_document(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``append_to_document``.

        Args:
            **kwargs: Parameter wie ``Writer.append_to_document``.

        Returns:
            Rückgabe des Writers.
        """
        return self.writer.append_to_document(**kwargs)

    def edit_document(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``edit_document``.

        Args:
            **kwargs: Parameter wie ``Writer.edit_document``.

        Returns:
            Rückgabe des Writers.
        """
        return self.writer.edit_document(**kwargs)

    def update_frontmatter(self, **kwargs: Any) -> dict[str, Any]:
        """Tool ``update_frontmatter``.

        Args:
            **kwargs: Parameter wie ``Writer.update_frontmatter``.

        Returns:
            Rückgabe des Writers.
        """
        return self.writer.update_frontmatter(**kwargs)

    def restore_document(
        self, target: str, version: int, expected_hash: str | None, source: str = "chat"
    ) -> dict[str, Any]:
        """Tool ``restore_document`` bzw. CLI ``pkm restore``.

        Args:
            target: Dokument.
            version: Wiederherzustellende Version.
            expected_hash: Hash aus ``read``.
            source: ``chat`` (MCP) oder ``user`` (CLI).

        Returns:
            Rückgabe des Writers.
        """
        return self.writer.restore_document(target, version, expected_hash, source)

# Functions *******************************************************************

# Main ************************************************************************
