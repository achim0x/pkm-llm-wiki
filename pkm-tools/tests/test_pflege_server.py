"""Tests: MCP-Server ``pkm-pflege`` mit begin_maintenance, write_wiki_page und finish_maintenance.

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

import asyncio
import json

import pytest

from pkm import maintrun, pflege_server
from pkm.errors import PkmError
from pkm.state import load_state

from .conftest import git, write

# Variables *******************************************************************

DOC = "documents/softskills/verhandlung.md"

DOC_TEXT = "# Verhandlung\n\n## Regeln\nNie den ersten Preis akzeptieren.\n"

PAGE = """---
type: summary
title: Verhandlungsregeln
sources: []
date_updated: 2026-11-02T21:10:00
confidence: high
---

> **Kurzfassung:** Regeln für Verhandlungen.

## Inhalt
Den ersten Preis nie annehmen.[^b1]

## Belege
[^b1]: [[documents/softskills/verhandlung#Regeln]] · „Nie den ersten Preis akzeptieren.“ · id:{id} · v:{v} · sha:{sha}
"""

# Classes *********************************************************************

# Functions *******************************************************************


def _page(svc, doc_id):
    """Zusammenfassung mit gültigem Beleg auf das Testdokument erzeugen.

    Args:
        svc: Dienst.
        doc_id: ID des Dokuments.

    Returns:
        Seiteninhalt.
    """
    doc = svc.read(f"id:{doc_id}")
    sha = next(s["sha"] for s in doc["sections"] if s["key"] == "Regeln")
    return PAGE.format(id=doc_id, v=doc["version"], sha=sha)


def test_server_tools():
    """Der Pflege-Server bietet die lesenden Tools und die drei Pflege-Tools, aber keine Dokument-Schreibtools."""
    tools = {t.name for t in asyncio.run(pflege_server.build_server().list_tools())}
    assert {"begin_maintenance", "write_wiki_page", "finish_maintenance", "read", "search", "history"} <= tools
    assert not tools & {"create_document", "rewrite_document", "edit_document", "append_to_document"}


def test_full_run(svc, cfg, isolated_env):
    """Ein Lauf: ID vergeben, Seite schreiben, abschließen; danach ist nichts mehr offen."""
    write(cfg, DOC, DOC_TEXT)
    begin = maintrun.begin_maintenance(svc)
    assert begin["status"] == "ok"
    assert begin["ids"]["assigned"][0]["path"] == DOC
    doc_id = begin["ids"]["assigned"][0]["id"]
    assert [d["path"] for d in begin["pending"]["new"]] == [DOC]

    res = maintrun.write_wiki_page(svc, "wiki/summaries/verhandlung", _page(svc, doc_id))
    assert res["status"] == "created" and res["path"] == "wiki/summaries/verhandlung.md"

    fin = maintrun.finish_maintenance(svc, "- neu: wiki/summaries/verhandlung", log_title="1 neu",
                                      processed=[doc_id])
    assert fin["marked"][0]["pages"] == ["wiki/summaries/verhandlung"]
    assert fin["synced_sources"] == 1
    assert not fin["warnings"]
    assert fin["lint"]["summary"]["error"] == 0, fin["lint"]["findings"]
    assert fin["commit"]["status"] == "ok"
    log = (cfg.root / "wiki/log.md").read_text(encoding="utf-8")
    assert "] ingest | 1 neu\n- neu: wiki/summaries/verhandlung" in log
    assert "wiki/summaries/verhandlung" in (cfg.root / "wiki/index.md").read_text(encoding="utf-8")
    state = load_state(cfg)["documents"]
    assert state[doc_id]["wiki_pages"] == ["wiki/summaries/verhandlung"]
    assert git(isolated_env, "log", "-1", "--format=%s").strip() == "pkm: ingest 1 document"
    assert git(isolated_env, "status", "--porcelain").strip() == ""
    assert maintrun.begin_maintenance(svc)["pending"]["counts"]["new"] == 0


@pytest.mark.parametrize("path", ["wiki/index.md", "wiki/log.md", "wiki/_status.md", "documents/x.md",
                                  "wiki/x.md", "scratch/x.md", "wiki/_lint/x.md"])
def test_write_forbidden(svc, path):
    """Generierte Dateien und Bereiche außerhalb der Seitenordner sind gesperrt."""
    with pytest.raises(PkmError) as e:
        maintrun.write_wiki_page(svc, path, "x")
    assert e.value.status == "forbidden"


def test_write_rejects_escape(svc):
    """Pfade mit .. werden abgelehnt."""
    with pytest.raises(PkmError) as e:
        maintrun.write_wiki_page(svc, "wiki/topics/../../documents/x", "x")
    assert e.value.status in ("invalid_path", "forbidden")


def test_write_conflicts(svc):
    """Bestehende Seiten nur mit passendem expected_hash; neue ohne."""
    first = maintrun.write_wiki_page(svc, "wiki/topics/thema", "---\ntype: topic\n---\nA\n")
    for expected in (None, "falsch"):
        with pytest.raises(PkmError) as e:
            maintrun.write_wiki_page(svc, "wiki/topics/thema", "B\n", expected)
        assert e.value.status == "conflict"
    with pytest.raises(PkmError) as e:
        maintrun.write_wiki_page(svc, "wiki/topics/neu", "B\n", "abc")
    assert e.value.status == "conflict"
    same = maintrun.write_wiki_page(svc, "wiki/topics/thema", "---\ntype: topic\n---\nA\n", first["hash"])
    assert same["status"] == "unchanged"
    changed = maintrun.write_wiki_page(svc, "wiki/topics/thema", "---\ntype: topic\n---\nB\n", first["hash"])
    assert changed["status"] == "changed" and changed["hash"] != first["hash"]
    assert svc.read("wiki/topics/thema")["hash"] == changed["hash"]


def test_begin_blocked_by_doctor(svc, cfg):
    """Fehler der Umgebung (hier ein .git im Vault) stoppen den Lauf vor jeder Änderung."""
    (cfg.root / ".git").mkdir()
    res = maintrun.begin_maintenance(svc)
    assert res["status"] == "blocked" and res["doctor"]
    assert "pending" not in res


def test_begin_with_lint(svc):
    """with_lint liefert den Prüfbericht mit."""
    assert "lint" in maintrun.begin_maintenance(svc, with_lint=True)


def test_finish_warns_without_citation_and_validates(svc, cfg):
    """Ein verarbeitetes Dokument ohne Beleg wird trotzdem vermerkt, aber gemeldet."""
    write(cfg, DOC, DOC_TEXT)
    doc_id = maintrun.begin_maintenance(svc)["ids"]["assigned"][0]["id"]
    fin = maintrun.finish_maintenance(svc, "- nur vermerkt", processed=[doc_id])
    assert fin["warnings"] and fin["marked"][0]["pages"] == []
    for kwargs in ({"log_entry": " "}, {"log_entry": "x", "operation": "delete"}):
        with pytest.raises(PkmError) as e:
            maintrun.finish_maintenance(svc, **kwargs)
        assert e.value.status == "invalid_argument"


def test_finish_removes_deleted(svc, cfg):
    """removed trägt gelöschte Dokumente aus state.json aus."""
    write(cfg, DOC, DOC_TEXT)
    doc_id = maintrun.begin_maintenance(svc)["ids"]["assigned"][0]["id"]
    maintrun.finish_maintenance(svc, "- vermerkt", processed=[doc_id])
    (cfg.root / DOC).unlink()
    begin = maintrun.begin_maintenance(svc)
    assert [d["key"] for d in begin["pending"]["deleted"]] == [doc_id]
    maintrun.finish_maintenance(svc, "- gelöscht", operation="ingest", removed=[doc_id])
    assert doc_id not in load_state(cfg)["documents"]


@pytest.mark.usefixtures("cfg")
def test_tool_call_returns_status():
    """Über die MCP-Hülle kommen fachliche Fehler als Status zurück."""
    server = pflege_server.build_server()
    result = asyncio.run(server.call_tool("write_wiki_page", {"path": "wiki/index.md", "content": "x"}))
    text = json.dumps(result, default=str)
    assert "forbidden" in text

# Main ************************************************************************
