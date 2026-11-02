"""MCP-Server ``pkm-pflege-mcp`` für die Wiki-Pflege aus Claude Desktop bzw. Cowork.

Läuft wie ``pkm-mcp`` lokal auf dem PKM-Rechner. Neben den lesenden Tools bietet er die Pflege-Tools
``begin_maintenance``, ``write_wiki_page``, ``set_document_metadata`` und ``finish_maintenance``. Er schreibt
in ``wiki/`` und ``.pkm/state.json``; an Dokumenten setzt er nur ``id``/``version`` (wie ``pkm ids``/
``pkm versions``) und nach Bestätigung des Nutzers ``title``, ``context``, ``tags``, ``kind``, ``short_citation``.
Nur in Pflege-Unterhaltungen einschalten.

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

from . import maintrun
from .mcp_server import Server, call, register_read_tools

# Variables *******************************************************************

INSTRUCTIONS = (
    "Pflege des PKM-Wikis (Skill pkm-wiki). Ablauf: begin_maintenance, Dokumente mit read/history lesen, "
    "Wiki-Seiten mit write_wiki_page schreiben, zum Schluss finish_maintenance. Dokumente in documents/ werden "
    "nie geändert; index.md, _status.md, log.md und sources sind generiert."
)

# Classes *********************************************************************

# Functions *******************************************************************


def _register_maintenance_tools(server: Server) -> None:
    """Pflege-Tools registrieren.

    Args:
        server: MCP-Server.
    """

    @server.tool()
    def begin_maintenance(with_lint: bool = False) -> dict:
        """Pflegelauf beginnen: prüft die Umgebung (doctor), committet Handänderungen als Versionen,
        vergibt fehlende IDs, liefert pending (new, changed, meta_changed, moved, deleted, problems) und
        korrigiert Belege auf verschobene Dokumente. Neue Dokumente enthalten missing_fields (fehlende title,
        context, tags, kind); known_tags nennt vorhandene Schlagwörter mit Häufigkeit.
        status blocked: Fehler melden und abbrechen. status needs_decision: doppelte IDs, Nutzer fragen.
        with_lint liefert zusätzlich den Prüfbericht."""
        return call("begin_maintenance", maintrun.begin_maintenance, with_lint=with_lint)

    @server.tool()
    def write_wiki_page(path: str, content: str, expected_hash: str | None = None) -> dict:
        """Wiki-Seite unter wiki/topics|entities|summaries|syntheses/ anlegen oder vollständig ersetzen
        (content mit Frontmatter). Bestehende Seiten erst mit read lesen und deren hash als expected_hash
        angeben; neue Seiten ohne expected_hash. Kein Commit, den macht finish_maintenance."""
        return call("write_wiki_page", maintrun.write_wiki_page, path=path, content=content,
                    expected_hash=expected_hash)

    @server.tool()
    def set_document_metadata(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str,
        expected_hash: str,
        set: dict | None = None,  # pylint: disable=redefined-builtin
        add: dict | None = None,
        overwrite: bool = False,
        note: str | None = None,
    ) -> dict:
        """Nur nach ausdrücklicher Bestätigung des Nutzers: title, context, tags, kind, short_citation eines
        Dokuments in documents/ eintragen (neue Version, Commit mit PKM-Source agent). set setzt Felder, add
        hängt an tags an. Vorhandene Werte nur mit overwrite=true ändern (sonst field_exists). kind: note |
        standard | regulation | correction. Tags werden vereinheitlicht (klein, Umlaute ausgeschrieben,
        Bindestriche). expected_hash aus read; bei conflict neu lesen."""
        return call("set_document_metadata", maintrun.set_document_metadata, target=target,
                    expected_hash=expected_hash, set=set, add=add, overwrite=overwrite, note=note)

    @server.tool()
    def finish_maintenance(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        log_entry: str,
        operation: str = "ingest",
        log_title: str | None = None,
        processed: list[str] | None = None,
        removed: list[str] | None = None,
        questions: list[str] | None = None,
        lint_report: bool = False,
    ) -> dict:
        """Pflegelauf abschließen: Belege korrigieren, sources erzeugen, verarbeitete Dokumente (processed:
        IDs oder Pfade) mit den belegenden Seiten vermerken, removed (Schlüssel gelöschter Dokumente)
        austragen, log_entry (Markdown-Liste) mit Zeitstempel an wiki/log.md anhängen, index.md und
        _status.md (mit questions) erzeugen, lint ausführen und den Agenten-Commit anlegen.
        operation: ingest | lint | fix. Meldet lint Fehler in eigenen Seiten: beheben und erneut mit
        operation=fix aufrufen."""
        return call("finish_maintenance", maintrun.finish_maintenance, log_entry=log_entry, operation=operation,
                    log_title=log_title, processed=processed, removed=removed, questions=questions,
                    lint_report=lint_report)


def build_server() -> Server:
    """Pflege-Server mit lesenden Tools und den Pflege-Tools aufbauen.

    Returns:
        Der Server.
    """
    server = Server("pkm-pflege", instructions=INSTRUCTIONS)
    register_read_tools(server)
    _register_maintenance_tools(server)
    return server


def main() -> None:
    """Einstiegspunkt ``pkm-pflege-mcp``: Server über stdio starten."""
    build_server().run()

# Main ************************************************************************


if __name__ == "__main__":
    main()
