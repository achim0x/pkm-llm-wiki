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
