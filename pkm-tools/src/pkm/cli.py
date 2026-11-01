"""Kommandozeile ``pkm`` (Spezifikation 8). Ausgabe als JSON.

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

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .citations import fix_citations, sync_citations
from .config import Config
from .doctor import doctor
from .errors import PkmError
from .lint import lint, write_report
from .maint import Maintenance
from .service import Service
from .vaultinit import init_vault
from .wikigen import build_index, build_status

# Variables *******************************************************************

OK_STATUSES = (None, "ok", "changed", "created", "unchanged")

# Classes *********************************************************************

# Functions *******************************************************************


def _print(data: Any) -> None:
    """Ergebnis als JSON auf die Standardausgabe schreiben.

    Args:
        data: Ergebnis.
    """
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def cmd_init(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm init``.

    Args:
        svc: Dienst.
        _args: Argumente (ungenutzt).

    Returns:
        Ergebnis von ``init_vault``.
    """
    return init_vault(svc.cfg)


def cmd_reindex(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm reindex``.

    Args:
        svc: Dienst.
        _args: Argumente (ungenutzt).

    Returns:
        Zähler des Neuaufbaus.
    """
    return svc.reindex()


def cmd_history(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm history <target> [--diff <von> [<bis>]]``.

    Args:
        svc: Dienst.
        args: ``target`` und ``diff``.

    Returns:
        Verlauf, ggf. mit Diff.
    """
    diff = args.diff or []
    return svc.history(args.target, diff[0] if diff else None, diff[1] if len(diff) > 1 else None)


def cmd_show(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm show <target> --version <n> [--section <key>]``.

    Args:
        svc: Dienst.
        args: ``target``, ``version``, ``section``.

    Returns:
        Inhalt der Version.
    """
    return svc.show(args.target, args.version, args.section)


def cmd_restore(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm restore <target> --version <n>`` (Quelle ``user``).

    Args:
        svc: Dienst.
        args: ``target``, ``version``.

    Returns:
        Rückgabe von ``restore_document``.
    """
    current = svc.read(args.target)
    return svc.restore_document(args.target, args.version, current["hash"], source="user")


def cmd_ids(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm ids``.

    Args:
        svc: Dienst.
        _args: Argumente (ungenutzt).

    Returns:
        Ergebnis von ``Maintenance.ids``.
    """
    return Maintenance(svc).ids()


def cmd_versions(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm versions``.

    Args:
        svc: Dienst.
        _args: Argumente (ungenutzt).

    Returns:
        Ergebnis von ``Maintenance.versions``.
    """
    return Maintenance(svc).versions()


def cmd_pending(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm pending``.

    Args:
        svc: Dienst.
        _args: Argumente (ungenutzt).

    Returns:
        Ergebnis von ``Maintenance.pending``.
    """
    return Maintenance(svc).pending()


def cmd_mark(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm mark <id>… [--pages <page>…] [--remove]``.

    Args:
        svc: Dienst.
        args: ``targets``, ``pages``, ``remove``.

    Returns:
        Ergebnis von ``Maintenance.mark``.
    """
    return Maintenance(svc).mark(args.targets, args.pages, args.remove)


def cmd_sha(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm sha <target> [--section <key>] [--full]``.

    Args:
        svc: Dienst.
        args: ``target``, ``section``, ``full``.

    Returns:
        Ergebnis von ``Maintenance.sha``.
    """
    return Maintenance(svc).sha(args.target, args.section, args.full)


def cmd_commit_wiki(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm commit-wiki -m <text>``.

    Args:
        svc: Dienst.
        args: ``message``.

    Returns:
        Ergebnis von ``Maintenance.commit_wiki``.
    """
    return Maintenance(svc).commit_wiki(args.message)


def cmd_index(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm index``.

    Args:
        svc: Dienst.
        _args: Argumente (ungenutzt).

    Returns:
        Ergebnis von ``build_index``.
    """
    return build_index(svc)


def cmd_status(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm status [--question <text>]…``.

    Args:
        svc: Dienst.
        args: ``question``.

    Returns:
        Ergebnis von ``build_status``.
    """
    return build_status(svc, args.question)


def cmd_fix_citations(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm fix-citations [<page>…]``.

    Args:
        svc: Dienst.
        args: ``pages``.

    Returns:
        Ergebnis von ``fix_citations``.
    """
    return fix_citations(svc, args.pages or None)


def cmd_sync_citations(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm sync-citations [<page>…]``.

    Args:
        svc: Dienst.
        args: ``pages``.

    Returns:
        Ergebnis von ``sync_citations``.
    """
    return sync_citations(svc, args.pages or None)


def cmd_lint(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm lint [--report]``.

    Args:
        svc: Dienst.
        args: ``report``.

    Returns:
        Prüfbericht, mit ``--report`` zusätzlich der Pfad des Berichts.
    """
    result = lint(svc)
    if args.report:
        result["report"] = write_report(svc, result)
    return result


def cmd_doctor(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm doctor [--short]``.

    Args:
        svc: Dienst.
        args: ``short``.

    Returns:
        Ergebnis von ``doctor``.
    """
    return doctor(svc, args.short)


def _add(sub: Any, name: str, help_text: str, func: Callable[[Service, argparse.Namespace], Any]) -> Any:
    """Unterbefehl anlegen.

    Args:
        sub: Subparser-Sammlung.
        name: Befehlsname.
        help_text: Hilfetext.
        func: Auszuführende Funktion.

    Returns:
        Der Parser des Unterbefehls.
    """
    parser = sub.add_parser(name, help=help_text)
    parser.set_defaults(func=func)
    return parser


def build_parser() -> argparse.ArgumentParser:
    """Argument-Parser mit allen Unterbefehlen.

    Returns:
        Der Parser.
    """
    p = argparse.ArgumentParser(prog="pkm", description="PKM-Werkzeuge (Pflege)")
    sub = p.add_subparsers(dest="command", required=True)
    _add(sub, "init", "Struktur und Git-Verzeichnis anlegen (idempotent)", cmd_init)
    _add(sub, "reindex", "Suchindex neu aufbauen", cmd_reindex)
    h = _add(sub, "history", "Versionen eines Dokuments", cmd_history)
    h.add_argument("target")
    h.add_argument("--diff", nargs="+", type=int, metavar="VERSION", help="<von> [<bis>]")
    for name, help_text, func in (("show", "Inhalt einer früheren Version", cmd_show),
                                  ("restore", "Frühere Version als neue Version zurückholen", cmd_restore)):
        s = _add(sub, name, help_text, func)
        s.add_argument("target")
        s.add_argument("--version", type=int, required=True)
        if name == "show":
            s.add_argument("--section")
    _add(sub, "ids", "Fehlende id/version eintragen, je Dokument ein Commit", cmd_ids)
    _add(sub, "versions", "Änderungen von Hand als Versionen committen", cmd_versions)
    _add(sub, "pending", "Zu verarbeitende Dokumente (JSON)", cmd_pending)
    m = _add(sub, "mark", "Dokumente als verarbeitet in state.json eintragen", cmd_mark)
    m.add_argument("targets", nargs="+", metavar="ID")
    m.add_argument("--pages", nargs="*", default=[], metavar="PAGE")
    m.add_argument("--remove", action="store_true", help="Einträge entfernen (z. B. gelöschte Dokumente)")
    sh = _add(sub, "sha", "Hashes nach 4.8 (Standard 6 Zeichen)", cmd_sha)
    sh.add_argument("target")
    sh.add_argument("--section")
    sh.add_argument("--full", action="store_true")
    _add(sub, "index", "wiki/index.md neu erzeugen", cmd_index)
    st = _add(sub, "status", "wiki/_status.md neu erzeugen", cmd_status)
    st.add_argument("--question", action="append", default=[], help="Rückfrage aufnehmen (mehrfach)")
    c = _add(sub, "commit-wiki", "Agenten-Commit: nur wiki/ und .pkm/state.json", cmd_commit_wiki)
    c.add_argument("--message", "-m", required=True)
    for name, help_text, func in (
        ("fix-citations", "Belege auf verschobene Originale/umbenannte Abschnitte korrigieren", cmd_fix_citations),
        ("sync-citations", "sources aus den Fußnoten erzeugen", cmd_sync_citations),
    ):
        _add(sub, name, help_text, func).add_argument("pages", nargs="*")
    li = _add(sub, "lint", "Prüfbericht (JSON)", cmd_lint)
    li.add_argument("--report", action="store_true", help="Bericht nach wiki/_lint/YYYY-MM-DD.md schreiben")
    do = _add(sub, "doctor", "Umgebung prüfen", cmd_doctor)
    do.add_argument("--short", action="store_true", help="nur Fehler")
    return p


def main(argv: list[str] | None = None) -> int:
    """Einstiegspunkt der CLI.

    Ohne ``PKM_ROOT`` wird der Vault (außer bei ``init``) vom aktuellen Ordner aufwärts gesucht.

    Args:
        argv: Argumente; ohne Angabe ``sys.argv``.

    Returns:
        Exit-Code: 0 bei Erfolg, 1 bei Fehlern oder einem Status ungleich ok.
    """
    args = build_parser().parse_args(argv)
    try:
        cfg = Config.from_env(search_from=None if args.command == "init" else Path.cwd())
        result = args.func(Service(cfg), args)
    except PkmError as exc:
        result = exc.to_dict()
    _print(result)
    failed = isinstance(result, dict) and result.get("status") not in OK_STATUSES
    return 1 if failed else 0

# Main ************************************************************************


if __name__ == "__main__":
    raise SystemExit(main())
