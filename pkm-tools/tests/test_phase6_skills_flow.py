"""Skills (format) and a complete maintenance run per skill `pkm-wiki` (trial run 9.1).

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

import asyncio
import json
import re
from pathlib import Path

import pytest
import yaml

from pkm import mcp_server, pflege_server
from pkm.cli import build_parser, main
from pkm.config import Config
from pkm.service import Service

from .conftest import git, write

# Variables *******************************************************************

SORTED = "documents/haus/ueberlaufsensor.md"

TOPIC_PAGE = """---
type: topic
title: Zisterne
aliases: [Regenwassertank]
tags: [zisterne]
sources: []
date_updated: 2026-11-02T21:10:00
confidence: medium
---

> **Kurzfassung:** Dach, Tank und Überlaufsensor der Zisterne.

## Inhalt
Die Dachfläche beträgt 92 m².[^b1]
Der Überlauf wird per Ultraschallsensor erkannt.[^b2]
Der Tank fasst 6.500 L.[^b3]

## Siehe auch
- [[wiki/summaries/zisterne-ueberlaufsensor]]

## Belege
[^b1]: {b1}
[^b2]: {b2}
[^b3]: {b3}
"""

SUMMARY_PAGE = """---
type: summary
title: Zisterne – Überlaufsensor
sources: []
date_updated: 2026-11-02T21:10:00
confidence: high
---

> **Kurzfassung:** Ergebnis der Diskussion zum Überlaufsensor.

## Inhalt
Vorgesehen ist ein Ultraschallsensor am Deckel.[^b1]

## Siehe auch
- [[wiki/topics/zisterne]]

## Belege
[^b1]: {b1}
"""

SKILLS = Path(__file__).resolve().parents[1] / "skills"

SPEC_TOOLS = {"create_document", "rewrite_document", "append_to_document", "edit_document",
              "update_frontmatter", "restore_document", "search", "read", "history", "show_citations",
              "read_index", "list_unprocessed", "add_image", "read_image", "fix_images"}

# Classes *********************************************************************

# Functions *******************************************************************


# Skills **********************************************************************
@pytest.mark.parametrize("name", ["pkm-access", "pkm-wiki"])
def test_skill_frontmatter(name):
    """The skills have a valid frontmatter."""
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "Frontmatter fehlt"
    meta = yaml.safe_load(m.group(1))
    assert meta["name"] == name
    assert re.fullmatch(r"[a-z0-9-]{1,64}", meta["name"])
    assert 20 < len(meta["description"]) <= 1024


def test_skill_tool_and_cli_names_exist():
    """The server offers exactly the tools of 4.7; the skills name only existing tools and commands."""
    tools = {t.name for t in asyncio.run(mcp_server.build_server().list_tools())}
    assert tools == SPEC_TOOLS
    access = (SKILLS / "pkm-access" / "SKILL.md").read_text(encoding="utf-8")
    assert {t for t in SPEC_TOOLS if f"`{t}`" in access} == SPEC_TOOLS
    usage = re.search(r"\{([a-z,-]+)\}", build_parser().format_usage())
    commands = set(usage.group(1).split(","))
    wiki = (SKILLS / "pkm-wiki" / "SKILL.md").read_text(encoding="utf-8")
    used = set(re.findall(r"\bpkm ([a-z][a-z-]+)", wiki))
    assert used <= commands, used - commands
    pflege = {t.name for t in asyncio.run(pflege_server.build_server().list_tools())}
    named = set(re.findall(r"`([a-z_]+)`", wiki)) & (pflege | SPEC_TOOLS)
    assert pflege <= named, pflege - named


# Maintenance run *************************************************************
def run(capsys, *argv):
    """Run a CLI command and return the JSON result.

    Args:
        capsys: pytest fixture for reading the output.
        *argv: Arguments for ``pkm``.

    Returns:
        The printed JSON object.
    """
    code = main(list(argv))
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    return out


def citation(sha_out, path, key, quote):
    """Build a citation line (without footnote name).

    Args:
        sha_out: Result of ``pkm sha``.
        path: Document path with ``.md``.
        key: Section key.
        quote: Literal quote.

    Returns:
        The citation text.
    """
    link = path[:-3]
    return f"[[{link}#{key}]] · „{quote}“ · id:{sha_out['id']} · v:{sha_out['version']} · sha:{sha_out['sha']}"


def _create_documents(svc: Service, cfg: Config) -> dict:
    """Create three sources: from the chat, by hand without frontmatter and a PDF.

    Args:
        svc: Service.
        cfg: Configuration.

    Returns:
        Return value of ``create_document`` for the chat document.
    """
    chat = svc.create_document(title="Zisterne – Überlaufsensor", tags=["zisterne"], content=(
        "## Ergebnis\nDer Überlauf wird per Ultraschallsensor erkannt.\n\n"
        "## Entscheidungen\n- Ultraschallsensor am Deckel\n\n## Offene Punkte\n- Kabelweg\n"))
    write(cfg, "documents/haus/zisterne.md", "# Zisterne\n\n## Dach\nDachfläche laut Plan 92 m².\n")
    write(cfg, "documents/haus/datenblatt.pdf", "%PDF Nutzvolumen 6500 l")
    return chat


def _write_pages(cfg: Config, capsys: pytest.CaptureFixture[str], chat: dict, hand_path: str) -> None:
    """Write the topic and summary page with citations (like the maintenance agent).

    Args:
        cfg: Configuration.
        capsys: pytest fixture for the CLI calls.
        chat: Chat document.
        hand_path: Path of the manual note.
    """
    s_dach = run(capsys, "sha", hand_path, "--section", "Dach")
    s_ent = run(capsys, "sha", f"id:{chat['id']}", "--section", "Entscheidungen")
    s_pdf = run(capsys, "sha", "documents/haus/datenblatt.pdf")
    ent = citation(s_ent, chat["path"], "Entscheidungen", "Ultraschallsensor am Deckel")
    write(cfg, "wiki/topics/zisterne.md", TOPIC_PAGE.format(
        b1=citation(s_dach, hand_path, "Dach", "Dachfläche laut Plan 92 m²"), b2=ent,
        b3=f"[[documents/haus/datenblatt.pdf]] · „Nutzvolumen 6500 l“ · sha:{s_pdf['file_hash']}"))
    write(cfg, "wiki/summaries/zisterne-ueberlaufsensor.md", SUMMARY_PAGE.format(b1=ent))


def _finish_first_run(cfg: Config, capsys: pytest.CaptureFixture[str], chat_id: str, hand_id: str) -> None:
    """Finish the first maintenance run and check it (lint clean, nothing open).

    Args:
        cfg: Configuration.
        capsys: pytest fixture for the CLI calls.
        chat_id: ID of the chat document.
        hand_id: ID of the manual note.
    """
    run(capsys, "sync-citations")
    run(capsys, "mark", chat_id, "--pages", "wiki/summaries/zisterne-ueberlaufsensor", "wiki/topics/zisterne")
    run(capsys, "mark", hand_id, "documents/haus/datenblatt.pdf", "--pages", "wiki/topics/zisterne")
    run(capsys, "index")
    run(capsys, "status")
    with (cfg.root / "wiki/log.md").open("a", encoding="utf-8") as fh:
        fh.write("\n## [2026-11-02 21:10] ingest | 3 neu\n- neu: wiki/topics/zisterne\n")
    lint = run(capsys, "lint")
    assert lint["summary"]["error"] == 0 and lint["summary"]["warning"] == 0, lint["findings"]
    assert run(capsys, "commit-wiki", "-m", "pkm: ingest 3 documents")["status"] == "ok"
    assert run(capsys, "pending")["counts"]["new"] == 0
    status = (cfg.root / "wiki/_status.md").read_text(encoding="utf-8")
    assert "## Not yet processed (0)" in status
    assert "proposal: documents/haus/" not in status  # tags do not match


def _continue_in_chat(svc: Service, cfg: Config, env: dict, chat: dict) -> None:
    """File in Obsidian and continue the discussion in the chat.

    Args:
        svc: Service.
        cfg: Configuration.
        env: Isolated environment.
        chat: Chat document.
    """
    (cfg.root / chat["path"]).rename(cfg.root / SORTED)
    cur = svc.read(f"id:{chat['id']}")
    svc.rewrite_document(target=f"id:{chat['id']}", expected_hash=cur["hash"],
                         note="Sensor: Schwimmerschalter statt Ultraschall", content=(
                             "## Ergebnis\nDer Überlauf wird per Schwimmerschalter erkannt.\n\n"
                             "## Entscheidungen\n- Schwimmerschalter statt Ultraschall\n\n"
                             "## Offene Punkte\n- Kabelweg\n"))
    assert git(env, "status", "--porcelain", "--", "documents").strip() == ""


def _second_run(svc: Service, capsys: pytest.CaptureFixture[str], chat_id: str) -> None:
    """Next run: only changed sections, fix moved citations.

    Args:
        svc: Service.
        capsys: pytest fixture for the CLI calls.
        chat_id: ID of the chat document.
    """
    run(capsys, "versions")
    pend = run(capsys, "pending")
    assert pend["moved"][0]["to"] == SORTED
    changed = pend["changed"][0]
    # A move without a change of content does not raise the version (16 no. 17), the rewrite gives v2
    assert changed["processed_version"] == 1 and changed["version"] == 2
    assert {c["key"] for c in changed["sections"]} == {"Ergebnis", "Entscheidungen"}
    hist = run(capsys, "history", f"id:{chat_id}", "--diff", "1")
    assert "+- Schwimmerschalter statt Ultraschall" in hist["diff"]
    run(capsys, "fix-citations")
    checks = {f["check"] for f in run(capsys, "lint")["findings"]}
    assert "citation_newer_version" in checks and "citation_moved" not in checks
    by = {c["id"]: c for c in svc.show_citations("wiki/topics/zisterne")["citations"]}
    assert by["b2"]["status"] == "newer_version" and by["b2"]["original"] == SORTED


def test_full_ingest_flow(cfg, isolated_env, capsys, monkeypatch):
    """Complete maintenance run per skill pkm-wiki and a follow-up run after a continuation."""
    svc = Service(cfg)
    chat = _create_documents(svc, cfg)
    monkeypatch.delenv("PKM_ROOT")
    monkeypatch.chdir(cfg.root)
    assert run(capsys, "doctor", "--short")["status"] == "ok"
    run(capsys, "versions")
    assert len(run(capsys, "ids")["assigned"]) == 1
    assert run(capsys, "pending")["counts"]["new"] == 3
    hand = svc.read("documents/haus/zisterne.md")
    _write_pages(cfg, capsys, chat, hand["path"])
    _finish_first_run(cfg, capsys, chat["id"], hand["id"])
    _continue_in_chat(svc, cfg, isolated_env, chat)
    _second_run(svc, capsys, chat["id"])

# Main ************************************************************************
