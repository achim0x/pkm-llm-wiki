"""MCP-Server `pkm-mcp` (Spezifikation 7). Dünne Hülle über `Service`.

Transport stdio. Keine Netzwerkzugriffe, keine LLM-Aufrufe, keine Hintergrundprozesse.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .config import Config
from .errors import PkmError

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[no-redef]

INSTRUCTIONS = (
    "Zugriff auf das persönliche Wissensmanagement (PKM). Das Wiki ist nur lesbar. "
    "Dokumente werden nur nach gezeigtem und bestätigtem Entwurf angelegt oder geändert. "
    "Jede Änderung braucht `expected_hash` aus `read` und ergibt eine neue Version mit Git-Commit."
)

_service = None


def get_service():
    global _service
    if _service is None:
        from .service import Service

        _service = Service(Config.from_env())
    return _service


def reset_service() -> None:
    global _service
    _service = None


def _log(tool: str, args: dict[str, Any], result: dict[str, Any]) -> None:
    try:
        svc = _service
        if svc is None:
            return
        path = svc.cfg.log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(svc.cfg.tz).isoformat(timespec="seconds"),
            "tool": tool,
            "target": args.get("target") or args.get("title") or args.get("query"),
            "status": result.get("status"),
            "version": result.get("version"),
            "commit": result.get("commit"),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - Protokoll darf nie stören
        pass


def call(tool: str, fn: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Tool ausführen; fachliche Fehler werden als Status zurückgegeben."""
    try:
        result = fn(get_service(), **kwargs)
    except PkmError as exc:
        result = exc.to_dict()
    _log(tool, kwargs, result)
    return result


# ---------------------------------------------------------------- lesende Tools
def t_search(svc, query: str, scope: str = "wiki", max_results: int = 8):
    return svc.search(query, scope, max_results)


def t_read(svc, target: str, version: int | None = None):
    return svc.read(target, version)


def t_history(svc, target: str, diff_from: int | None = None, diff_to: int | None = None):
    return svc.history(target, diff_from, diff_to)


def t_read_index(svc):
    return svc.read_index()


def t_list_unprocessed(svc):
    return svc.list_unprocessed()


def build_server() -> _Server:
    server = _Server("pkm", instructions=INSTRUCTIONS)

    @server.tool()
    def search(query: str, scope: str = "wiki", max_results: int = 8) -> dict:
        """Volltextsuche (Präfixsuche, umlauttolerant). scope: wiki (Standard) | documents | all.
        max_results höchstens 25. Treffer mit id, version, path, title, type, summary, snippet,
        score, updated und bei Dokumenten processed (ob im Wiki eingearbeitet)."""
        return call("search", t_search, query=query, scope=scope, max_results=max_results)

    @server.tool()
    def read(target: str, version: int | None = None) -> dict:
        """Dokument oder Wiki-Seite lesen. target: Pfad, Wikilink oder id:d-…
        Mit version eine frühere Version aus Git (nur lesend). Liefert hash für expected_hash."""
        return call("read", t_read, target=target, version=version)

    @server.tool()
    def history(target: str, diff_from: int | None = None, diff_to: int | None = None) -> dict:
        """Versionsverlauf eines Dokuments (version, date, source, note, commit).
        Mit diff_from zusätzlich ein Unified Diff bis diff_to (Standard: aktuelle Version)."""
        return call("history", t_history, target=target, diff_from=diff_from, diff_to=diff_to)

    @server.tool()
    def read_index() -> dict:
        """Gibt wiki/index.md zurück (Katalog aller Wiki-Seiten mit Kurzfassung)."""
        return call("read_index", t_read_index)

    @server.tool()
    def list_unprocessed() -> dict:
        """Dokumente, deren aktueller Stand noch nicht im Wiki eingearbeitet ist."""
        return call("list_unprocessed", t_list_unprocessed)

    _register_write_tools(server)
    return server


def _register_write_tools(server: _Server) -> None:
    """Schreibende Tools (7.2). Neuanlage nur in documents/_inbox/, Änderungen nur an
    documents/**/*.md. Jede Änderung: neue Version + Git-Commit. Kein Löschen/Verschieben."""

    @server.tool()
    def create_document(
        title: str,
        content: str,
        topics: list[str] | None = None,
        context: str | None = None,
        related: list[str] | None = None,
        kind: str = "note",
        source: str = "claude-chat",
        note: str | None = None,
    ) -> dict:
        """Neues Dokument in documents/_inbox/ anlegen (Version 1, Commit). Nur nach gezeigtem
        und bestätigtem Entwurf. content ohne Frontmatter. kind: note | correction."""
        return call("create_document", lambda svc, **kw: svc.create_document(**kw), title=title,
                    content=content, topics=topics, context=context, related=related, kind=kind,
                    source=source, note=note)

    @server.tool()
    def rewrite_document(
        target: str, content: str, expected_hash: str, note: str | None = None,
        confirm_shortening: bool = False,
    ) -> dict:
        """Gesamten Inhalt unterhalb des Frontmatters ersetzen (Normalfall bei Fortsetzungen).
        Bei deutlicher Kürzung oder fehlenden Abschnitten Status large_shortening: Kürzung vom
        Nutzer bestätigen lassen und mit confirm_shortening=true erneut aufrufen."""
        return call("rewrite_document", lambda svc, **kw: svc.rewrite_document(**kw), target=target,
                    content=content, expected_hash=expected_hash, note=note,
                    confirm_shortening=confirm_shortening)

    @server.tool()
    def append_to_document(
        target: str, text: str, expected_hash: str, section: str | None = None, note: str | None = None,
    ) -> dict:
        """Text anhängen: am Ende des Abschnitts section (Schlüssel, z. B. "Offene Punkte",
        "Notizen#2" oder "_preamble"), neuer Abschnitt falls nicht vorhanden, ohne section am Dateiende."""
        return call("append_to_document", lambda svc, **kw: svc.append_to_document(**kw), target=target,
                    text=text, expected_hash=expected_hash, section=section, note=note)

    @server.tool()
    def edit_document(target: str, old: str, new: str, expected_hash: str, note: str | None = None) -> dict:
        """Textstelle old (muss genau einmal vorkommen) durch new ersetzen. new darf leer sein."""
        return call("edit_document", lambda svc, **kw: svc.edit_document(**kw), target=target, old=old,
                    new=new, expected_hash=expected_hash, note=note)

    @server.tool()
    def update_frontmatter(
        target: str,
        expected_hash: str,
        set: dict | None = None,  # noqa: A002 - Name aus der Spezifikation
        add: dict | None = None,
        remove: list[str] | None = None,
        note: str | None = None,
    ) -> dict:
        """Frontmatter ändern: set (setzen), add (an Listen anhängen), remove (Felder entfernen).
        Geschützt: id, version, created, updated. Kommentare im Frontmatter gehen dabei verloren."""
        return call("update_frontmatter", lambda svc, **kw: svc.update_frontmatter(**kw), target=target,
                    expected_hash=expected_hash, set=set, add=add, remove=remove, note=note)

    @server.tool()
    def restore_document(target: str, version: int, expected_hash: str) -> dict:
        """Inhalt einer früheren Version als neue Version zurückholen (Geschichte bleibt erhalten)."""
        return call("restore_document", lambda svc, **kw: svc.restore_document(**kw), target=target,
                    version=version, expected_hash=expected_hash)


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
