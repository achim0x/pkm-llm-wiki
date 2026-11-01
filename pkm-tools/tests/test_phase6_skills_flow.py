"""Skills (Format) und ein vollständiger Pflegelauf nach Skill `pkm-wiki` (Probelauf 9.1)."""

import json
import re
from pathlib import Path

import pytest
import yaml

from pkm.cli import main
from pkm.service import Service

from .conftest import git, write

SKILLS = Path(__file__).resolve().parents[1] / "skills"


# ---------------------------------------------------------------- Skills
@pytest.mark.parametrize("name", ["pkm-access", "pkm-wiki"])
def test_skill_frontmatter(name):
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "Frontmatter fehlt"
    meta = yaml.safe_load(m.group(1))
    assert meta["name"] == name
    assert re.fullmatch(r"[a-z0-9-]{1,64}", meta["name"])
    assert 20 < len(meta["description"]) <= 1024


SPEC_TOOLS = {"create_document", "rewrite_document", "append_to_document", "edit_document",
              "update_frontmatter", "restore_document", "search", "read", "history", "show_citations",
              "read_index", "list_unprocessed"}


def test_skill_tool_and_cli_names_exist():
    """Der Server bietet genau die Tools aus 4.7; Skills nennen nur vorhandene Tools und Befehle."""
    import asyncio

    from pkm import mcp_server
    from pkm.cli import build_parser

    tools = {t.name for t in asyncio.run(mcp_server.build_server().list_tools())}
    assert tools == SPEC_TOOLS
    access = (SKILLS / "pkm-access" / "SKILL.md").read_text(encoding="utf-8")
    assert {t for t in SPEC_TOOLS if f"`{t}`" in access} == SPEC_TOOLS
    commands = set(build_parser()._subparsers._group_actions[0].choices)
    wiki = (SKILLS / "pkm-wiki" / "SKILL.md").read_text(encoding="utf-8")
    used = set(re.findall(r"\bpkm ([a-z][a-z-]+)", wiki))
    assert used and used <= commands, used - commands


# --------------------------------------------------------- Pflegelauf
def run(capsys, *argv):
    code = main(list(argv))
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    return out


def citation(sha_out, path, key, quote):
    link = path[:-3]
    return f"[[{link}#{key}]] · „{quote}“ · id:{sha_out['id']} · v:{sha_out['version']} · sha:{sha_out['sha']}"


def test_full_ingest_flow(cfg, isolated_env, capsys, monkeypatch):
    svc = Service(cfg)
    # 1. Dokumente: aus dem Chat, von Hand ohne Frontmatter, PDF
    chat = svc.create_document(title="Zisterne – Überlaufsensor", topics=["zisterne"], content=(
        "## Ergebnis\nDer Überlauf wird per Ultraschallsensor erkannt.\n\n"
        "## Entscheidungen\n- Ultraschallsensor am Deckel\n\n## Offene Punkte\n- Kabelweg\n"))
    write(cfg, "documents/haus/zisterne.md", "# Zisterne\n\n## Dach\nDachfläche laut Plan 92 m².\n")
    write(cfg, "documents/haus/datenblatt.pdf", "%PDF Nutzvolumen 6500 l")
    monkeypatch.delenv("PKM_ROOT")
    monkeypatch.chdir(cfg.root)

    # 2. Ingest nach Skill
    assert run(capsys, "doctor", "--short")["status"] == "ok"
    run(capsys, "versions")
    assert len(run(capsys, "ids")["assigned"]) == 1
    pend = run(capsys, "pending")
    assert pend["counts"]["new"] == 3
    hand = svc.read("documents/haus/zisterne.md")

    s_dach = run(capsys, "sha", "documents/haus/zisterne.md", "--section", "Dach")
    s_ent = run(capsys, "sha", f"id:{chat['id']}", "--section", "Entscheidungen")
    s_pdf = run(capsys, "sha", "documents/haus/datenblatt.pdf")
    page = f"""---
type: topic
title: Zisterne
aliases: [Regenwassertank]
tags: [zisterne]
sources: []
updated: 2026-11-02
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
[^b1]: {citation(s_dach, hand['path'], 'Dach', 'Dachfläche laut Plan 92 m²')}
[^b2]: {citation(s_ent, chat['path'], 'Entscheidungen', 'Ultraschallsensor am Deckel')}
[^b3]: [[documents/haus/datenblatt.pdf]] · „Nutzvolumen 6500 l“ · sha:{s_pdf['file_hash']}
"""
    summary = f"""---
type: summary
title: Zisterne – Überlaufsensor
sources: []
updated: 2026-11-02
confidence: high
---

> **Kurzfassung:** Ergebnis der Diskussion zum Überlaufsensor.

## Inhalt
Vorgesehen ist ein Ultraschallsensor am Deckel.[^b1]

## Siehe auch
- [[wiki/topics/zisterne]]

## Belege
[^b1]: {citation(s_ent, chat['path'], 'Entscheidungen', 'Ultraschallsensor am Deckel')}
"""
    write(cfg, "wiki/topics/zisterne.md", page)
    write(cfg, "wiki/summaries/zisterne-ueberlaufsensor.md", summary)
    run(capsys, "sync-citations")
    run(capsys, "mark", chat["id"], "--pages", "wiki/summaries/zisterne-ueberlaufsensor", "wiki/topics/zisterne")
    run(capsys, "mark", hand["id"], "documents/haus/datenblatt.pdf", "--pages", "wiki/topics/zisterne")
    run(capsys, "index")
    run(capsys, "status")
    with (cfg.root / "wiki/log.md").open("a", encoding="utf-8") as fh:
        fh.write("\n## [2026-11-02 21:10] ingest | 3 neu\n- neu: wiki/topics/zisterne\n")
    lint = run(capsys, "lint")
    assert lint["summary"]["error"] == 0 and lint["summary"]["warning"] == 0, lint["findings"]
    assert run(capsys, "commit-wiki", "-m", "pkm: ingest 3 documents")["status"] == "ok"
    assert run(capsys, "pending")["counts"]["new"] == 0
    assert "## Noch nicht verarbeitet (0)" in (cfg.root / "wiki/_status.md").read_text()
    assert "Vorschlag: documents/haus/" not in (cfg.root / "wiki/_status.md").read_text()  # topics passen nicht

    # 3. Einsortieren in Obsidian, Fortsetzung aus dem Chat
    (cfg.root / chat["path"]).rename(cfg.root / "documents/haus/ueberlaufsensor.md")
    cur = svc.read(f"id:{chat['id']}")
    svc.rewrite_document(target=f"id:{chat['id']}", expected_hash=cur["hash"],
                         note="Sensor: Schwimmerschalter statt Ultraschall", content=(
                             "## Ergebnis\nDer Überlauf wird per Schwimmerschalter erkannt.\n\n"
                             "## Entscheidungen\n- Schwimmerschalter statt Ultraschall\n\n"
                             "## Offene Punkte\n- Kabelweg\n"))
    git_status = git(isolated_env, "status", "--porcelain", "--", "documents")
    assert git_status.strip() == ""

    # 4. Nächster Lauf: nur geänderte Abschnitte, Belege korrigieren
    run(capsys, "versions")
    pend = run(capsys, "pending")
    assert pend["moved"][0]["to"] == "documents/haus/ueberlaufsensor.md"
    changed = pend["changed"][0]
    # Verschieben ohne Inhaltsänderung erhöht die Version nicht (16 Nr. 17), die Neufassung ergibt v2
    assert changed["processed_version"] == 1 and changed["version"] == 2
    assert {c["key"] for c in changed["sections"]} == {"Ergebnis", "Entscheidungen"}
    hist = run(capsys, "history", f"id:{chat['id']}", "--diff", "1")
    assert "+- Schwimmerschalter statt Ultraschall" in hist["diff"]
    run(capsys, "fix-citations")
    lint = run(capsys, "lint")
    checks = {f["check"] for f in lint["findings"]}
    assert "citation_newer_version" in checks and "citation_moved" not in checks
    by = {c["id"]: c for c in svc.show_citations("wiki/topics/zisterne")["citations"]}
    assert by["b2"]["status"] == "newer_version" and by["b2"]["original"] == "documents/haus/ueberlaufsensor.md"
