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
    """Schreibende Tools (Phase 3)."""


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
