"""Skills (Format) und ein vollständiger Pflegelauf nach Skill `pkm-wiki` (Probelauf 9.1).

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
              "read_index", "list_unprocessed", "add_image", "read_image"}

# Classes *********************************************************************

# Functions *******************************************************************


# Skills **********************************************************************
@pytest.mark.parametrize("name", ["pkm-access", "pkm-wiki"])
def test_skill_frontmatter(name):
    """Die Skills haben gültiges Frontmatter."""
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "Frontmatter fehlt"
    meta = yaml.safe_load(m.group(1))
    assert meta["name"] == name
    assert re.fullmatch(r"[a-z0-9-]{1,64}", meta["name"])
    assert 20 < len(meta["description"]) <= 1024


def test_skill_tool_and_cli_names_exist():
    """Der Server bietet genau die Tools aus 4.7; Skills nennen nur vorhandene Tools und Befehle."""
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


# Pflegelauf ******************************************************************
def run(capsys, *argv):
    """CLI-Befehl ausführen und das JSON-Ergebnis zurückgeben.

    Args:
        capsys: pytest-Fixture zum Lesen der Ausgabe.
        *argv: Argumente für ``pkm``.

    Returns:
        Das ausgegebene JSON-Objekt.
    """
    code = main(list(argv))
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    return out


def citation(sha_out, path, key, quote):
    """Beleg-Zeile (ohne Fußnotennamen) bilden.

    Args:
        sha_out: Ergebnis von ``pkm sha``.
        path: Dokumentpfad mit ``.md``.
        key: Abschnittsschlüssel.
        quote: Wörtliches Zitat.

    Returns:
        Der Belegtext.
    """
    link = path[:-3]
    return f"[[{link}#{key}]] · „{quote}“ · id:{sha_out['id']} · v:{sha_out['version']} · sha:{sha_out['sha']}"


def _create_documents(svc: Service, cfg: Config) -> dict:
    """Drei Quellen anlegen: aus dem Chat, von Hand ohne Frontmatter und ein PDF.

    Args:
        svc: Dienst.
        cfg: Konfiguration.

    Returns:
        Rückgabe von ``create_document`` für das Chat-Dokument.
    """
    chat = svc.create_document(title="Zisterne – Überlaufsensor", tags=["zisterne"], content=(
        "## Ergebnis\nDer Überlauf wird per Ultraschallsensor erkannt.\n\n"
        "## Entscheidungen\n- Ultraschallsensor am Deckel\n\n## Offene Punkte\n- Kabelweg\n"))
    write(cfg, "documents/haus/zisterne.md", "# Zisterne\n\n## Dach\nDachfläche laut Plan 92 m².\n")
    write(cfg, "documents/haus/datenblatt.pdf", "%PDF Nutzvolumen 6500 l")
    return chat


def _write_pages(cfg: Config, capsys: pytest.CaptureFixture[str], chat: dict, hand_path: str) -> None:
    """Themen- und Zusammenfassungsseite mit Belegen schreiben (wie der Pflege-Agent).

    Args:
        cfg: Konfiguration.
        capsys: pytest-Fixture für die CLI-Aufrufe.
        chat: Chat-Dokument.
        hand_path: Pfad der Notiz von Hand.
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
    """Ersten Pflegelauf abschließen und prüfen (Lint sauber, nichts mehr offen).

    Args:
        cfg: Konfiguration.
        capsys: pytest-Fixture für die CLI-Aufrufe.
        chat_id: ID des Chat-Dokuments.
        hand_id: ID der Notiz von Hand.
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
    assert "## Noch nicht verarbeitet (0)" in status
    assert "Vorschlag: documents/haus/" not in status  # tags passen nicht


def _continue_in_chat(svc: Service, cfg: Config, env: dict, chat: dict) -> None:
    """In Obsidian einsortieren und die Diskussion im Chat fortsetzen.

    Args:
        svc: Dienst.
        cfg: Konfiguration.
        env: Isolierte Umgebung.
        chat: Chat-Dokument.
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
    """Nächster Lauf: nur geänderte Abschnitte, verschobene Belege korrigieren.

    Args:
        svc: Dienst.
        capsys: pytest-Fixture für die CLI-Aufrufe.
        chat_id: ID des Chat-Dokuments.
    """
    run(capsys, "versions")
    pend = run(capsys, "pending")
    assert pend["moved"][0]["to"] == SORTED
    changed = pend["changed"][0]
    # Verschieben ohne Inhaltsänderung erhöht die Version nicht (16 Nr. 17), die Neufassung ergibt v2
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
    """Vollständiger Pflegelauf nach Skill pkm-wiki und Folgelauf nach einer Fortsetzung."""
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
