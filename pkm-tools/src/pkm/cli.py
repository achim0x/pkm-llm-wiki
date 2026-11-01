"""Kommandozeile `pkm` (Spezifikation 8). Ausgabe als JSON."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .config import Config
from .errors import PkmError


def _print(data: Any) -> None:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def cmd_init(cfg: Config, args: argparse.Namespace) -> Any:
    from .vaultinit import init_vault

    return init_vault(cfg)


def cmd_reindex(cfg: Config, args: argparse.Namespace) -> Any:
    from .service import Service

    return Service(cfg).reindex()


def cmd_history(cfg: Config, args: argparse.Namespace) -> Any:
    from .service import Service

    diff = args.diff or []
    return Service(cfg).history(args.target, diff[0] if diff else None, diff[1] if len(diff) > 1 else None)


def cmd_show(cfg: Config, args: argparse.Namespace) -> Any:
    from .service import Service

    return Service(cfg).show(args.target, args.version, args.section)


def cmd_restore(cfg: Config, args: argparse.Namespace) -> Any:
    from .service import Service

    svc = Service(cfg)
    current = svc.read(args.target)
    return svc.restore_document(args.target, args.version, current["hash"], source="user")


def _maint(cfg: Config):
    from .maint import Maintenance
    from .service import Service

    return Maintenance(Service(cfg))


def cmd_ids(cfg: Config, args: argparse.Namespace) -> Any:
    return _maint(cfg).ids()


def cmd_versions(cfg: Config, args: argparse.Namespace) -> Any:
    return _maint(cfg).versions()


def cmd_pending(cfg: Config, args: argparse.Namespace) -> Any:
    return _maint(cfg).pending()


def cmd_mark(cfg: Config, args: argparse.Namespace) -> Any:
    return _maint(cfg).mark(args.targets, args.pages, args.remove)


def cmd_sha(cfg: Config, args: argparse.Namespace) -> Any:
    return _maint(cfg).sha(args.target, args.section, args.full)


def cmd_commit_wiki(cfg: Config, args: argparse.Namespace) -> Any:
    return _maint(cfg).commit_wiki(args.message)


def cmd_index(cfg: Config, args: argparse.Namespace) -> Any:
    from .service import Service
    from .wikigen import build_index

    return build_index(Service(cfg))


def cmd_status(cfg: Config, args: argparse.Namespace) -> Any:
    from .service import Service
    from .wikigen import build_status

    return build_status(Service(cfg), args.question)


def cmd_fix_citations(cfg: Config, args: argparse.Namespace) -> Any:
    from .citations import fix_citations
    from .service import Service

    return fix_citations(Service(cfg), args.pages or None)


def cmd_sync_citations(cfg: Config, args: argparse.Namespace) -> Any:
    from .citations import sync_citations
    from .service import Service

    return sync_citations(Service(cfg), args.pages or None)


def cmd_lint(cfg: Config, args: argparse.Namespace) -> Any:
    from .lint import lint, write_report
    from .service import Service

    svc = Service(cfg)
    result = lint(svc)
    if args.report:
        result["report"] = write_report(svc, result)
    return result


def cmd_doctor(cfg: Config, args: argparse.Namespace) -> Any:
    from .doctor import doctor
    from .service import Service

    return doctor(Service(cfg), args.short)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pkm", description="PKM-Werkzeuge (Pflege)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Struktur und Git-Verzeichnis anlegen (idempotent)").set_defaults(func=cmd_init)
    sub.add_parser("reindex", help="Suchindex neu aufbauen").set_defaults(func=cmd_reindex)
    h = sub.add_parser("history", help="Versionen eines Dokuments")
    h.add_argument("target")
    h.add_argument("--diff", nargs="+", type=int, metavar="VERSION", help="<von> [<bis>]")
    h.set_defaults(func=cmd_history)
    s = sub.add_parser("show", help="Inhalt einer früheren Version")
    s.add_argument("target")
    s.add_argument("--version", type=int, required=True)
    s.add_argument("--section")
    s.set_defaults(func=cmd_show)
    r = sub.add_parser("restore", help="Frühere Version als neue Version zurückholen")
    r.add_argument("target")
    r.add_argument("--version", type=int, required=True)
    r.set_defaults(func=cmd_restore)
    sub.add_parser("ids", help="Fehlende id/version eintragen, je Dokument ein Commit").set_defaults(func=cmd_ids)
    sub.add_parser("versions", help="Änderungen von Hand als Versionen committen").set_defaults(func=cmd_versions)
    sub.add_parser("pending", help="Zu verarbeitende Dokumente (JSON)").set_defaults(func=cmd_pending)
    m = sub.add_parser("mark", help="Dokumente als verarbeitet in state.json eintragen")
    m.add_argument("targets", nargs="+", metavar="ID")
    m.add_argument("--pages", nargs="*", default=[], metavar="PAGE")
    m.add_argument("--remove", action="store_true", help="Einträge entfernen (z. B. gelöschte Dokumente)")
    m.set_defaults(func=cmd_mark)
    h = sub.add_parser("sha", help="Hashes nach 4.8 (Standard 6 Zeichen)")
    h.add_argument("target")
    h.add_argument("--section")
    h.add_argument("--full", action="store_true")
    h.set_defaults(func=cmd_sha)
    sub.add_parser("index", help="wiki/index.md neu erzeugen").set_defaults(func=cmd_index)
    st = sub.add_parser("status", help="wiki/_status.md neu erzeugen")
    st.add_argument("--question", action="append", default=[], help="Rückfrage aufnehmen (mehrfach)")
    st.set_defaults(func=cmd_status)
    c = sub.add_parser("commit-wiki", help="Agenten-Commit: nur wiki/ und .pkm/state.json")
    c.add_argument("--message", "-m", required=True)
    c.set_defaults(func=cmd_commit_wiki)
    fc = sub.add_parser("fix-citations", help="Belege auf verschobene Originale/umbenannte Abschnitte korrigieren")
    fc.add_argument("pages", nargs="*")
    fc.set_defaults(func=cmd_fix_citations)
    sc = sub.add_parser("sync-citations", help="sources aus den Fußnoten erzeugen")
    sc.add_argument("pages", nargs="*")
    sc.set_defaults(func=cmd_sync_citations)
    li = sub.add_parser("lint", help="Prüfbericht (JSON)")
    li.add_argument("--report", action="store_true", help="Bericht nach wiki/_lint/YYYY-MM-DD.md schreiben")
    li.set_defaults(func=cmd_lint)
    do = sub.add_parser("doctor", help="Umgebung prüfen")
    do.add_argument("--short", action="store_true", help="nur Fehler")
    do.set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = Config.from_env()
        result = args.func(cfg, args)
    except PkmError as exc:
        _print(exc.to_dict())
        return 1
    _print(result)
    if isinstance(result, dict) and result.get("status") not in (None, "ok", "changed", "created", "unchanged"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
