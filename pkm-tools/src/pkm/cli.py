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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pkm", description="PKM-Werkzeuge (Pflege)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Struktur und Git-Verzeichnis anlegen (idempotent)").set_defaults(func=cmd_init)
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
