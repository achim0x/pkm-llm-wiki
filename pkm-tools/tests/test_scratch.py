"""Bereich ``scratch/`` für kurzlebige Notizen und Todo-Listen (Spezifikation 0.14).

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

import pytest

from pkm import mcp_server
from pkm.config import Config
from pkm.doctor import doctor
from pkm.errors import PkmError
from pkm.lint import lint
from pkm.maint import Maintenance
from pkm.service import Service
from pkm.vaultinit import init_vault

from .conftest import git, write

# Variables *******************************************************************

TODO = "- [ ] Filter der Zisternenpumpe reinigen\n- [ ] Regenrinne prüfen\n"

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="todo")
def fixture_todo(svc: Service) -> dict:
    """Todo-Liste in ``scratch/todo/`` (per Chat angelegt).

    Args:
        svc: Dienst.

    Returns:
        Rückgabe von ``create_document``.
    """
    return svc.create_document(title="Todo Haus", content=TODO, area="scratch", folder="todo")


def commit_count(env: dict) -> int:
    """Anzahl der Commits im Testvault.

    Args:
        env: Isolierte Umgebung.

    Returns:
        Anzahl der Commits.
    """
    return len(git(env, "log", "--format=%H").split())


def test_create_in_scratch_without_version_and_commit(svc, cfg, isolated_env):
    """Notizen in scratch/ haben ein kleines Frontmatter, keine ID, keine Version, keinen Commit."""
    before = commit_count(isolated_env)
    res = svc.create_document(title="Todo Haus", content=TODO, area="scratch", folder="todo", tags=["haus"])
    assert res["status"] == "created" and res["path"] == "scratch/todo/todo-haus.md"
    assert "id" not in res and "version" not in res and "commit" not in res
    meta = svc.read(res["path"])["frontmatter"]
    assert list(meta) == ["title", "date_markdown", "tags"]
    assert commit_count(isolated_env) == before
    assert git(isolated_env, "status", "--porcelain").strip() == ""
    assert (cfg.root / ".gitignore").read_text(encoding="utf-8").splitlines()[1] == "scratch/"


def test_create_in_scratch_name_suffix_and_kind(svc):
    """Gleiche Namen bekommen ein Suffix; kind wird nur übernommen, wenn angegeben."""
    first = svc.create_document(title="Notiz", content="a", area="scratch")
    second = svc.create_document(title="Notiz", content="b", area="scratch", kind="correction")
    assert (first["path"], second["path"]) == ("scratch/notiz.md", "scratch/notiz-2.md")
    assert "kind" not in svc.read(first["path"])["frontmatter"]
    assert svc.read(second["path"])["frontmatter"]["kind"] == "correction"


@pytest.mark.parametrize(
    "kwargs, status",
    [({"area": "wiki"}, "invalid_argument"), ({"folder": "x"}, "invalid_argument"),
     ({"area": "scratch", "folder": "../x"}, "invalid_path"), ({"area": "scratch", "folder": "a/CON"}, "invalid_path")],
)
def test_create_invalid_area_and_folder(svc, kwargs, status):
    """Ungültige Bereiche und Ordner werden abgelehnt."""
    with pytest.raises(PkmError) as e:
        svc.create_document(title="X", content="y", **kwargs)
    assert e.value.status == status


def test_read_scratch(svc, todo):
    """read liefert für scratch/ weder id noch version, editable ist true."""
    r = svc.read("[[todo-haus]]")
    assert r["path"] == todo["path"] and r["editable"] is True
    assert "id" not in r and "version" not in r and r["hash"] == todo["new_hash"]


def test_check_off_item_without_version(svc, cfg, isolated_env, todo):
    """Abhaken ändert die Datei ohne Version und Commit; updated wird gesetzt."""
    before = commit_count(isolated_env)
    old_updated = svc.read(todo["path"])["frontmatter"].get("date_updated", "")
    r = svc.edit_document(target=todo["path"], old="- [ ] Filter", new="- [x] Filter",
                          expected_hash=todo["new_hash"], note="wird ignoriert")
    assert r["status"] == "changed" and "version" not in r and "commit" not in r
    assert "+- [x] Filter der Zisternenpumpe reinigen" in r["diff"]
    text = (cfg.root / todo["path"]).read_text(encoding="utf-8")
    assert "- [x] Filter" in text and "version:" not in text and "id:" not in text
    assert svc.read(todo["path"])["frontmatter"].get("date_updated", "") >= old_updated
    assert commit_count(isolated_env) == before


def test_append_to_scratch_file_without_frontmatter(svc, cfg):
    """Eine Notiz ohne Frontmatter bekommt beim Ändern keines."""
    write(cfg, "scratch/einkauf.md", "- Milch\n")
    h = svc.read("scratch/einkauf.md")["hash"]
    r = svc.append_to_document(target="[[einkauf]]", text="- Brot", expected_hash=h)
    assert r["status"] == "changed"
    assert (cfg.root / "scratch/einkauf.md").read_text(encoding="utf-8") == "- Milch\n\n- Brot\n"


def test_scratch_hash_conflict_and_shortening(svc, todo):
    """Hash-Schutz und Kürzungsschutz gelten auch in scratch/."""
    with pytest.raises(PkmError) as e:
        svc.edit_document(target=todo["path"], old="Regenrinne", new="Dach", expected_hash="0" * 64)
    assert e.value.status == "conflict"
    with pytest.raises(PkmError) as e:
        svc.rewrite_document(target=todo["path"], content="x", expected_hash=todo["new_hash"])
    assert e.value.status == "large_shortening"
    r = svc.rewrite_document(target=todo["path"], content="x", expected_hash=todo["new_hash"],
                             confirm_shortening=True)
    assert svc.read(todo["path"])["content"] == "\nx\n" and r["status"] == "changed"


def test_scratch_not_versioned(svc, todo):
    """history, read mit version und restore_document liefern not_versioned."""
    for call in (lambda: svc.history(todo["path"]), lambda: svc.read(todo["path"], version=1),
                 lambda: svc.restore_document(todo["path"], 1, todo["new_hash"])):
        with pytest.raises(PkmError) as e:
            call()
        assert e.value.status == "not_versioned"


def test_search_scratch_only_with_scope(svc, todo):
    """scratch/ wird nur mit scope scratch durchsucht."""
    assert [r["path"] for r in svc.search("Zisternenpumpe", scope="scratch")["results"]] == [todo["path"]]
    for scope in ("wiki", "documents", "all"):
        assert not svc.search("Zisternenpumpe", scope=scope)["results"]
    hit = svc.search("Regenrinne", scope="scratch")["results"][0]
    assert "version" not in hit and "processed" not in hit


@pytest.mark.usefixtures("todo")
def test_maintenance_ignores_scratch(svc, cfg, isolated_env):
    """pending, ids, versions, lint und status ignorieren scratch/."""
    write(cfg, "scratch/ohne-frontmatter.md", "## A\n## A\nText ohne ID\n")
    m = Maintenance(svc)
    assert not m.ids()["assigned"] and not m.versions()["committed"]
    assert all(n == 0 for n in m.pending()["counts"].values())
    assert not [f for f in lint(svc)["findings"] if (f.get("path") or "").startswith("scratch/")]
    assert svc.list_unprocessed()["count"] == 0
    assert git(isolated_env, "status", "--porcelain").strip() == ""


def test_lint_reports_citation_to_scratch(svc, cfg, todo):
    """Ein Beleg im Wiki, der auf scratch/ zeigt, ist ein Fehler."""
    write(cfg, "wiki/topics/t.md", "---\ntype: topic\nsources: []\n---\n\n> K\n\n## Inhalt\nAussage.[^b1]\n\n"
          f"## Belege\n[^b1]: [[{todo['path'][:-3]}]] · „Filter“ · sha:abcdef\n")
    checks = {(f["check"], f["path"]) for f in lint(svc)["findings"]}
    assert ("citation_to_scratch", "wiki/topics/t.md") in checks


def test_move_scratch_to_documents_becomes_document(svc, cfg, isolated_env, todo):
    """Aus scratch/ nach documents/ verschoben: beim nächsten Lauf version 1 und ein Commit."""
    (cfg.root / "documents/haus").mkdir()
    (cfg.root / todo["path"]).rename(cfg.root / "documents/haus/todo.md")
    m = Maintenance(svc)
    assigned = m.ids()["assigned"]
    assert [a["path"] for a in assigned] == ["documents/haus/todo.md"]
    doc = svc.read("documents/haus/todo.md")
    assert doc["version"] == 1 and doc["id"] == assigned[0]["id"]
    assert m.pending()["new"][0]["path"] == "documents/haus/todo.md"
    assert git(isolated_env, "status", "--porcelain").strip() == ""


def test_move_documents_to_scratch_acts_like_delete(svc, cfg, isolated_env):
    """Aus documents/ nach scratch/ verschoben wirkt wie Löschen."""
    doc = svc.create_document(title="Alt", content="## A\nx\n")
    m = Maintenance(svc)
    m.mark([doc["id"]], pages=["wiki/index"])
    (cfg.root / doc["path"]).rename(cfg.root / "scratch/alt.md")
    committed = m.versions()["committed"]
    assert committed and committed[0]["deleted"] is True
    assert [d["id"] for d in m.pending()["deleted"]] == [doc["id"]]
    with pytest.raises(PkmError):
        svc.resolve(f"id:{doc['id']}")
    assert git(isolated_env, "status", "--porcelain", "--", "documents", "scratch").strip() == ""


def test_wiki_still_read_only(svc, cfg):
    """wiki/ bleibt aus Chats unveränderbar."""
    write(cfg, "wiki/topics/t.md", "---\ntype: topic\n---\nText\n")
    h = svc.read("wiki/topics/t")["hash"]
    with pytest.raises(PkmError) as e:
        svc.edit_document(target="wiki/topics/t", old="Text", new="x", expected_hash=h)
    assert e.value.status == "forbidden"


def test_doctor_and_init_scratch_ignore(svc, cfg):
    """doctor meldet fehlendes scratch/ in .gitignore; pkm init ergänzt es in älteren Vaults."""
    assert next(c for c in doctor(svc)["checks"] if c["check"] == "scratch_ignored")["ok"]
    gitignore = cfg.root / ".gitignore"
    gitignore.write_text(gitignore.read_text(encoding="utf-8").replace("scratch/\n", ""),
                 encoding="utf-8", newline="\n")
    assert doctor(svc)["status"] == "error"
    assert init_vault(Config.from_env())["updated_files"] == [".gitignore"]
    assert doctor(svc)["status"] == "ok"
    assert not init_vault(Config.from_env())["updated_files"]


@pytest.mark.usefixtures("cfg")
def test_mcp_create_document_has_area_and_folder():
    """Das MCP-Tool create_document kennt area und folder."""
    tools = {t.name: t for t in asyncio.run(mcp_server.build_server().list_tools())}
    params = tools["create_document"].input_schema["properties"]
    assert {"area", "folder"} <= set(params)

# Main ************************************************************************
