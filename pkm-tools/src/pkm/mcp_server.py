"""MCP-Server ``pkm-mcp`` (Spezifikation 7). Dünne Hülle über ``Service``.

Transport stdio. Keine Netzwerkzugriffe, keine LLM-Aufrufe, keine Hintergrundprozesse.

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

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .config import Config
from .errors import PkmError
from .service import Service

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[no-redef]

# Variables *******************************************************************

INSTRUCTIONS = (
    "Zugriff auf das persönliche Wissensmanagement (PKM). Das Wiki ist nur lesbar. "
    "Dokumente werden nur nach gezeigtem und bestätigtem Entwurf angelegt oder geändert. "
    "Jede Änderung braucht `expected_hash` aus `read` und ergibt eine neue Version mit Git-Commit."
)

_SERVICE: dict[str, Service] = {}

# Classes *********************************************************************

# Functions *******************************************************************


def get_service() -> Service:
    """Dienst beim ersten Aufruf aus der Umgebung anlegen.

    Returns:
        Den Dienst.

    Raises:
        PkmError: ``config_error`` bei fehlender oder ungültiger Konfiguration.
    """
    if "svc" not in _SERVICE:
        _SERVICE["svc"] = Service(Config.from_env())
    return _SERVICE["svc"]


def reset_service() -> None:
    """Dienst verwerfen (z. B. in Tests nach geänderter Umgebung)."""
    _SERVICE.clear()


def _log(tool: str, args: dict[str, Any], result: dict[str, Any]) -> None:
    """Aufruf in ``.pkm/mcp.log`` protokollieren; Fehler beim Protokollieren werden ignoriert.

    Args:
        tool: Toolname.
        args: Aufrufparameter.
        result: Rückgabe des Tools.
    """
    svc = _SERVICE.get("svc")
    if svc is not None:
        entry = {
            "ts": datetime.now(svc.cfg.tz).isoformat(timespec="seconds"),
            "tool": tool,
            "target": args.get("target") or args.get("title") or args.get("query"),
            "status": result.get("status"),
            "version": result.get("version"),
            "commit": result.get("commit"),
        }
        try:
            svc.cfg.log_path.parent.mkdir(parents=True, exist_ok=True)
            with svc.cfg.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # Das Protokoll darf nie stören.


def call(tool: str, fn: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Tool ausführen; fachliche Fehler werden als Status zurückgegeben.

    Args:
        tool: Toolname (für das Protokoll).
        fn: Funktion, die den Dienst als erstes Argument erhält (z. B. ``Service.read``).
        **kwargs: Parameter des Tools.

    Returns:
        Rückgabe des Tools bzw. ``{status, message, …}`` bei fachlichen Fehlern.
    """
    try:
        result = fn(get_service(), **kwargs)
    except PkmError as exc:
        result = exc.to_dict()
    _log(tool, kwargs, result)
    return result


def _register_read_tools(server: _Server) -> None:
    """Lesende Tools (7.3) registrieren.

    Args:
        server: MCP-Server.
    """

    @server.tool()
    def search(query: str, scope: str = "wiki", max_results: int = 8) -> dict:
        """Volltextsuche (Präfixsuche, umlauttolerant). scope: wiki (Standard) | documents | scratch | all
        (all = wiki + documents; scratch nur auf ausdrückliche Angabe).
        max_results höchstens 25. Treffer mit id, version, path, title, type, summary, snippet,
        score, updated und bei Dokumenten processed (ob im Wiki eingearbeitet)."""
        return call("search", Service.search, query=query, scope=scope, max_results=max_results)

    @server.tool()
    def read(target: str, version: int | None = None) -> dict:
        """Dokument oder Wiki-Seite lesen. target: Pfad, Wikilink, id:d-… oder Kurzbezeichnung (short_citation).
        Mit version eine frühere Version aus Git (nur lesend). Liefert hash für expected_hash."""
        return call("read", Service.read, target=target, version=version)

    @server.tool()
    def history(target: str, diff_from: int | None = None, diff_to: int | None = None) -> dict:
        """Versionsverlauf eines Dokuments (version, date, source, note, commit).
        Mit diff_from zusätzlich ein Unified Diff bis diff_to (Standard: aktuelle Version)."""
        return call("history", Service.history, target=target, diff_from=diff_from, diff_to=diff_to)

    @server.tool()
    def show_citations(target: str, statement: str | None = None, with_excerpt: bool = False) -> dict:
        """Belege einer Wiki-Seite: Original (aktueller Pfad), Abschnitt/Seite, Zitat, belegte und
        aktuelle Version, Status (ok | moved | newer_version | missing) und Obsidian-Link.
        statement grenzt auf Absätze mit diesem Text ein. with_excerpt lädt den Abschnitt aus der
        belegten und, falls abweichend, der aktuellen Version."""
        return call("show_citations", Service.show_citations, target=target, statement=statement,
                    with_excerpt=with_excerpt)

    @server.tool()
    def read_index() -> dict:
        """Gibt wiki/index.md zurück (Katalog aller Wiki-Seiten mit Kurzfassung)."""
        return call("read_index", Service.read_index)

    @server.tool()
    def list_unprocessed() -> dict:
        """Dokumente, deren aktueller Stand noch nicht im Wiki eingearbeitet ist."""
        return call("list_unprocessed", Service.list_unprocessed)


def _register_write_tools(server: _Server) -> None:
    """Schreibende Tools (7.2) registrieren.

    Neuanlage nur in ``documents/_inbox/`` bzw. ``scratch/``, Änderungen nur an ``documents/**/*.md``
    und ``scratch/**/*.md``. Jede Änderung in ``documents/`` ergibt eine neue Version mit Git-Commit,
    in ``scratch/`` ohne Version und Commit. Löschen und Verschieben gibt es nicht.

    Args:
        server: MCP-Server.
    """

    @server.tool()
    def create_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        title: str,
        content: str,
        tags: list[str] | None = None,
        short_citation: str | None = None,
        date_document: str | None = None,
        context: str | None = None,
        related: list[str] | None = None,
        kind: str | None = None,
        toolchain: str | None = None,
        note: str | None = None,
        area: str = "documents",
        folder: str | None = None,
    ) -> dict:
        """Neues Dokument in documents/_inbox/ anlegen (Version 1, Commit) oder mit area="scratch"
        eine kurzlebige Notiz/Todo-Liste in scratch/[folder/] (ohne Version und Commit, nie im Wiki).
        Nur nach gezeigtem und bestätigtem Entwurf. content ohne Frontmatter. tags: Kleinbuchstaben mit
        Bindestrich. kind: note | standard | regulation | correction. toolchain: eigener Modellname plus
        "(pkm-mcp)", wird zu toolchain_markdown."""
        return call("create_document", Service.create_document, title=title, content=content, tags=tags,
                    short_citation=short_citation, date_document=date_document, context=context, related=related,
                    kind=kind, toolchain=toolchain, note=note, area=area, folder=folder)

    @server.tool()
    def rewrite_document(
        target: str, content: str, expected_hash: str, note: str | None = None, confirm_shortening: bool = False
    ) -> dict:
        """Gesamten Inhalt unterhalb des Frontmatters ersetzen (Normalfall bei Fortsetzungen).
        Bei deutlicher Kürzung oder fehlenden Abschnitten Status large_shortening: Kürzung vom
        Nutzer bestätigen lassen und mit confirm_shortening=true erneut aufrufen."""
        return call("rewrite_document", Service.rewrite_document, target=target, content=content,
                    expected_hash=expected_hash, note=note, confirm_shortening=confirm_shortening)

    @server.tool()
    def append_to_document(
        target: str, text: str, expected_hash: str, section: str | None = None, note: str | None = None
    ) -> dict:
        """Text anhängen: am Ende des Abschnitts section (Schlüssel, z. B. "Offene Punkte",
        "Notizen#2" oder "_preamble"), neuer Abschnitt falls nicht vorhanden, ohne section am Dateiende."""
        return call("append_to_document", Service.append_to_document, target=target, text=text,
                    expected_hash=expected_hash, section=section, note=note)

    @server.tool()
    def edit_document(target: str, old: str, new: str, expected_hash: str, note: str | None = None) -> dict:
        """Textstelle old (muss genau einmal vorkommen) durch new ersetzen. new darf leer sein."""
        return call("edit_document", Service.edit_document, target=target, old=old, new=new,
                    expected_hash=expected_hash, note=note)

    @server.tool()
    def update_frontmatter(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str,
        expected_hash: str,
        set: dict | None = None,  # pylint: disable=redefined-builtin
        add: dict | None = None,
        remove: list[str] | None = None,
        note: str | None = None,
    ) -> dict:
        """Frontmatter ändern: set (setzen), add (an Listen anhängen), remove (Felder entfernen).
        Geschützt: id, version, date_markdown, date_updated, status_markdown. Kommentare im Frontmatter gehen
        dabei verloren."""
        return call("update_frontmatter", Service.update_frontmatter, target=target, expected_hash=expected_hash,
                    set=set, add=add, remove=remove, note=note)

    @server.tool()
    def restore_document(target: str, version: int, expected_hash: str) -> dict:
        """Inhalt einer früheren Version als neue Version zurückholen (Geschichte bleibt erhalten).
        Für Dateien in scratch/ kommt not_versioned."""
        return call("restore_document", Service.restore_document, target=target, version=version,
                    expected_hash=expected_hash)


def build_server() -> _Server:
    """MCP-Server mit allen zwölf Tools aufbauen.

    Returns:
        Der Server.
    """
    server = _Server("pkm", instructions=INSTRUCTIONS)
    _register_read_tools(server)
    _register_write_tools(server)
    return server


def main() -> None:
    """Einstiegspunkt ``pkm-mcp``: Server über stdio starten."""
    build_server().run()

# Main ************************************************************************


if __name__ == "__main__":
    main()
