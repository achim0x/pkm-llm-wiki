"""Command line ``pkm`` (specification 8). Output as JSON.

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

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import docimages, imagefix
from .citations import fix_citations, sync_citations
from .config import Config
from .doctor import doctor
from .errors import PkmError
from .lint import lint, write_report
from .maint import Maintenance
from .service import Service
from .setupwiz import Setup, SetupOptions
from .vaultinit import init_vault
from .wikigen import build_index, build_status

# Variables *******************************************************************

OK_STATUSES = (None, "ok", "changed", "created", "unchanged", "proposal")

# Classes *********************************************************************

# Functions *******************************************************************


def _print(data: Any) -> None:
    """Write the result as JSON to standard output.

    Args:
        data: Result.
    """
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _utf8_output() -> None:
    """Write standard output and errors as UTF-8 (Windows uses cp1252 for pipes, e.g. in Claude Desktop or CI)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def cmd_init(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm init``.

    Args:
        svc: Service.
        _args: Arguments (unused).

    Returns:
        Result of ``init_vault``.
    """
    return init_vault(svc.cfg)


def cmd_reindex(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm reindex``.

    Args:
        svc: Service.
        _args: Arguments (unused).

    Returns:
        Counters of the rebuild.
    """
    return svc.reindex()


def cmd_history(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm history <target> [--diff <from> [<to>]]``.

    Args:
        svc: Service.
        args: ``target`` and ``diff``.

    Returns:
        History, possibly with a diff.
    """
    diff = args.diff or []
    return svc.history(args.target, diff[0] if diff else None, diff[1] if len(diff) > 1 else None)


def cmd_show(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm show <target> --version <n> [--section <key>]``.

    Args:
        svc: Service.
        args: ``target``, ``version``, ``section``.

    Returns:
        Content of the version.
    """
    return svc.show(args.target, args.version, args.section)


def cmd_restore(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm restore <target> --version <n>`` (source ``user``).

    Args:
        svc: Service.
        args: ``target``, ``version``.

    Returns:
        Return value of ``restore_document``.
    """
    current = svc.read(args.target)
    return svc.restore_document(args.target, args.version, current["hash"], source="user")


def cmd_ids(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm ids``.

    Args:
        svc: Service.
        _args: Arguments (unused).

    Returns:
        Result of ``Maintenance.ids``.
    """
    return Maintenance(svc).ids()


def cmd_versions(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm versions``.

    Args:
        svc: Service.
        _args: Arguments (unused).

    Returns:
        Result of ``Maintenance.versions``.
    """
    return Maintenance(svc).versions()


def cmd_pending(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm pending``.

    Args:
        svc: Service.
        _args: Arguments (unused).

    Returns:
        Result of ``Maintenance.pending``.
    """
    return Maintenance(svc).pending()


def cmd_mark(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm mark <id>… [--pages <page>…] [--remove]``.

    Args:
        svc: Service.
        args: ``targets``, ``pages``, ``remove``.

    Returns:
        Result of ``Maintenance.mark``.
    """
    return Maintenance(svc).mark(args.targets, args.pages, args.remove)


def cmd_sha(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm sha <target> [--section <key>] [--full]``.

    Args:
        svc: Service.
        args: ``target``, ``section``, ``full``.

    Returns:
        Result of ``Maintenance.sha``.
    """
    return Maintenance(svc).sha(args.target, args.section, args.full)


def cmd_commit_wiki(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm commit-wiki -m <text>``.

    Args:
        svc: Service.
        args: ``message``.

    Returns:
        Result of ``Maintenance.commit_wiki``.
    """
    return Maintenance(svc).commit_wiki(args.message)


def cmd_fix_frontmatter(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm fix-frontmatter <target>… [--all]`` (only on explicit instruction by the user).

    Args:
        svc: Service.
        args: ``targets`` and ``all``.

    Returns:
        Result of ``Maintenance.fix_frontmatter``.
    """
    return Maintenance(svc).fix_frontmatter(args.targets, args.all)


def cmd_fix_images(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm fix-images <target>… [--all] [--apply] [--alt <name>=<text>]`` (only on instruction, 4.9).

    Without a target and without ``--all`` the command only lists the affected files. Without ``--apply`` it
    shows findings, proposals and diff; with ``--apply`` every changed file is committed as a new version
    (``PKM-Source: user``, ``PKM-Fix: images``).

    Args:
        svc: Service.
        args: ``targets``, ``all``, ``apply``, ``alt``.

    Returns:
        List of the affected files or results per file.

    Raises:
        PkmError: ``invalid_argument`` for ``--alt`` without ``=``.
    """
    if any("=" not in a for a in args.alt):
        raise PkmError("invalid_argument", "--alt expects <name>=<text>.")
    alt = dict(a.split("=", 1) for a in args.alt)
    docs = [d for d in Maintenance(svc).documents()[0] if d.kind == "md" and d.parsed is not None and not d.error]
    affected = [d.rel for d in docs if imagefix.image_issues(d.body or "", svc.cfg.images)]
    targets = list(args.targets) or (affected if args.all else [])
    result: dict[str, Any] = {"status": "ok", "affected": affected}
    if targets:
        result["results"] = [
            docimages.fix_document(svc.writer, t, svc.read(t, content=False)["hash"], image_alt=alt, apply=args.apply,
                                   source="user", areas=("documents/",))
            for t in targets
        ]
    return result


def cmd_index(svc: Service, _args: argparse.Namespace) -> Any:
    """``pkm index``.

    Args:
        svc: Service.
        _args: Arguments (unused).

    Returns:
        Result of ``build_index``.
    """
    return build_index(svc)


def cmd_status(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm status [--question <text>]…``.

    Args:
        svc: Service.
        args: ``question``.

    Returns:
        Result of ``build_status``.
    """
    return build_status(svc, args.question)


def cmd_fix_citations(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm fix-citations [<page>…]``.

    Args:
        svc: Service.
        args: ``pages``.

    Returns:
        Result of ``fix_citations``.
    """
    return fix_citations(svc, args.pages or None)


def cmd_sync_citations(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm sync-citations [<page>…]``.

    Args:
        svc: Service.
        args: ``pages``.

    Returns:
        Result of ``sync_citations``.
    """
    return sync_citations(svc, args.pages or None)


def cmd_lint(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm lint [--report]``.

    Args:
        svc: Service.
        args: ``report``.

    Returns:
        Lint report, with ``--report`` additionally the path of the report.
    """
    result = lint(svc)
    if args.report:
        result["report"] = write_report(svc, result)
    return result


def cmd_doctor(svc: Service, args: argparse.Namespace) -> Any:
    """``pkm doctor [--short]``.

    Args:
        svc: Service.
        args: ``short``.

    Returns:
        Result of ``doctor``.
    """
    return doctor(svc, args.short)


def _add(sub: Any, name: str, help_text: str, func: Callable[[Service, argparse.Namespace], Any]) -> Any:
    """Add a subcommand.

    Args:
        sub: Subparser collection.
        name: Command name.
        help_text: Help text.
        func: Function to run.

    Returns:
        The parser of the subcommand.
    """
    parser = sub.add_parser(name, help=help_text)
    parser.set_defaults(func=func)
    return parser


def cmd_setup(args: argparse.Namespace) -> dict[str, Any]:
    """``pkm setup``: guided installation (15.1); without Git the PKM runs without version control.

    Args:
        args: Answers given in advance (``vault``, ``vault_name``, ``git_name``, ``git_email``, ``yes``,
            ``claude_config``, ``no_claude``, ``skills_dir``).

    Returns:
        Result of ``Setup.run``.
    """
    opts = SetupOptions(vault=args.vault, vault_name=args.vault_name, git_name=args.git_name,
                        git_email=args.git_email, yes=args.yes, claude_config=args.claude_config,
                        no_claude=args.no_claude, skills_dir=args.skills_dir)
    say = (lambda text: print(text, file=sys.stderr)) if args.json else print
    return Setup(opts, say=say).run()


def _add_setup(sub: Any) -> None:
    """Add the subcommand ``setup``.

    Args:
        sub: Subparser collection.
    """
    se = _add(sub, "setup", "Guided installation: vault, Git check, Claude Desktop, skills (repeatable)", cmd_init)
    se.add_argument("--vault", help="vault folder (absolute path)")
    se.add_argument("--vault-name", help="name of the Obsidian vault (default: folder name)")
    se.add_argument("--git-name", help="Git user name for the PKM repo if none is set")
    se.add_argument("--git-email", help="Git e-mail address for the PKM repo if none is set")
    se.add_argument("--yes", action="store_true", help="accept defaults and confirmations without asking")
    se.add_argument("--claude-config", help="path of claude_desktop_config.json")
    se.add_argument("--no-claude", action="store_true", help="do not change the Claude Desktop configuration")
    se.add_argument("--skills-dir", help="target folder for the skill ZIP files")
    se.add_argument("--json", action="store_true", help="print the result as JSON")


def build_parser() -> argparse.ArgumentParser:
    """Argument parser with all subcommands.

    Returns:
        The parser.
    """
    p = argparse.ArgumentParser(prog="pkm", description="PKM tools (maintenance)")
    sub = p.add_subparsers(dest="command", required=True)
    _add_setup(sub)
    _add(sub, "init", "Create structure and Git directory (idempotent)", cmd_init)
    _add(sub, "reindex", "Rebuild the search index", cmd_reindex)
    h = _add(sub, "history", "Versions of a document", cmd_history)
    h.add_argument("target")
    h.add_argument("--diff", nargs="+", type=int, metavar="VERSION", help="<from> [<to>]")
    for name, help_text, func in (("show", "Content of an earlier version", cmd_show),
                                  ("restore", "Restore an earlier version as a new version", cmd_restore)):
        s = _add(sub, name, help_text, func)
        s.add_argument("target")
        s.add_argument("--version", type=int, required=True)
        if name == "show":
            s.add_argument("--section")
    _add(sub, "ids", "Enter missing id/version, one commit per document", cmd_ids)
    _add(sub, "versions", "Commit manual changes as versions", cmd_versions)
    _add(sub, "pending", "Documents to process (JSON)", cmd_pending)
    m = _add(sub, "mark", "Record documents as processed in state.json", cmd_mark)
    m.add_argument("targets", nargs="+", metavar="ID")
    m.add_argument("--pages", nargs="*", default=[], metavar="PAGE")
    m.add_argument("--remove", action="store_true", help="remove entries (e.g. deleted documents)")
    sh = _add(sub, "sha", "Hashes per 4.8 (default 6 characters)", cmd_sha)
    sh.add_argument("target")
    sh.add_argument("--section")
    sh.add_argument("--full", action="store_true")
    ff = _add(sub, "fix-frontmatter", "Repair frontmatter (only on instruction; without a target only list)",
              cmd_fix_frontmatter)
    ff.add_argument("targets", nargs="*")
    ff.add_argument("--all", action="store_true", help="repair all affected documents")
    fi = _add(sub, "fix-images", "Fix image data URIs per 4.9 (only on instruction; without --apply only propose)",
              cmd_fix_images)
    fi.add_argument("targets", nargs="*")
    fi.add_argument("--all", action="store_true", help="all affected documents")
    fi.add_argument("--apply", action="store_true", help="write the fix (new version)")
    fi.add_argument("--alt", action="append", default=[], metavar="NAME=TEXT", help="alt text per image")
    _add(sub, "index", "Regenerate wiki/index.md", cmd_index)
    st = _add(sub, "status", "Regenerate wiki/_status.md", cmd_status)
    st.add_argument("--question", action="append", default=[], help="add a question (repeatable)")
    c = _add(sub, "commit-wiki", "Agent commit: only wiki/ and .pkm/state.json", cmd_commit_wiki)
    c.add_argument("--message", "-m", required=True)
    for name, help_text, func in (
        ("fix-citations", "Fix citations of moved originals/renamed sections", cmd_fix_citations),
        ("sync-citations", "Generate sources from the footnotes", cmd_sync_citations),
    ):
        _add(sub, name, help_text, func).add_argument("pages", nargs="*")
    li = _add(sub, "lint", "Lint report (JSON)", cmd_lint)
    li.add_argument("--report", action="store_true", help="write the report to wiki/_lint/YYYY-MM-DD.md")
    do = _add(sub, "doctor", "Check the environment", cmd_doctor)
    do.add_argument("--short", action="store_true", help="errors only")
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point of the CLI.

    Without ``PKM_ROOT`` the vault is searched upwards from the current folder (except for ``init``).

    Args:
        argv: Arguments; ``sys.argv`` if omitted.

    Returns:
        Exit code: 0 on success, 1 on errors or a status other than ok.
    """
    _utf8_output()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "setup":
            result = cmd_setup(args)
        else:
            cfg = Config.from_env(search_from=None if args.command == "init" else Path.cwd())
            result = args.func(Service(cfg), args)
    except PkmError as exc:
        result = exc.to_dict()
    if args.command != "setup" or args.json:
        _print(result)
    elif result.get("status") not in OK_STATUSES and "message" in result:
        print(f"Error: {result['message']}")
    failed = isinstance(result, dict) and result.get("status") not in OK_STATUSES
    return 1 if failed else 0

# Main ************************************************************************


if __name__ == "__main__":
    raise SystemExit(main())
