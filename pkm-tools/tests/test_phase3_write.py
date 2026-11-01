"""Schreibende Tools (Spezifikation 5.4, 6, 7.2, Tests aus 14).

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
import shutil

import pytest

from pkm import mcp_server
from pkm.cli import main
from pkm.config import Config
from pkm.errors import PkmError
from pkm.gitlayer import parse_message
from pkm.service import Service

from .conftest import git, write

# Variables *******************************************************************

BODY = """## Ergebnis
Sensor wird ein Ultraschallsensor.

## Entscheidungen
- Ultraschallsensor am Deckel

## Offene Punkte
- Montageort klären
- Kabelweg

## Kontext / Begründung
Diskussion im Chat.
"""

# Classes *********************************************************************

# Functions *******************************************************************


def commits(env) -> list[str]:
    """Alle Commit-Hashes.

    Args:
        env: Isolierte Umgebung.

    Returns:
        Hashes, neueste zuerst.
    """
    return git(env, "log", "--format=%H").split()


def last_commit(env) -> tuple[str, list[str], dict]:
    """Nachricht, Dateien und PKM-Zeilen des letzten Commits.

    Args:
        env: Isolierte Umgebung.

    Returns:
        Tupel aus (Nachricht, Dateien, PKM-Zeilen).
    """
    body = git(env, "log", "-1", "--format=%B")
    files = git(env, "show", "--name-only", "--format=", "HEAD").split()
    _subject, _note, trailers = parse_message(body)
    return body, files, trailers


@pytest.fixture(name="doc")
def fixture_doc(svc):
    """Per Chat angelegtes Dokument mit den vier Standardabschnitten.

    Args:
        svc: Dienst.

    Returns:
        Rückgabe von ``create_document``.
    """
    res = svc.create_document(title="Zisterne – Überlaufsensor", content=BODY, tags=["zisterne"],
                              context="Chat: Füllstand", note=None)
    return res


# create_document *************************************************************
def test_create(doc, svc, isolated_env, cfg):
    """create_document legt v1 im Eingang an und committet nur diese Datei."""
    assert doc["status"] == "created" and doc["version"] == 1
    assert re.fullmatch(r"documents/_inbox/\d{4}-\d{2}-\d{2}_zisterne-ueberlaufsensor\.md", doc["path"])
    r = svc.read(doc["path"])
    assert r["id"] == doc["id"] and r["version"] == 1 and r["hash"] == doc["new_hash"]
    fm = r["frontmatter"]
    assert fm["title"] == "Zisterne – Überlaufsensor" and "source" not in fm
    assert fm["kind"] == "note" and fm["tags"] == ["zisterne"] and fm["context"] == "Chat: Füllstand"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", fm["date_markdown"])
    assert fm["toolchain_markdown"] == "pkm-mcp" and "date_updated" not in fm
    body, files, tr = last_commit(isolated_env)
    assert body.startswith("doc: Zisterne – Überlaufsensor v1")
    assert files == [doc["path"]]
    assert tr == {"PKM-Id": doc["id"], "PKM-Version": "1", "PKM-Source": "chat"}
    assert git(isolated_env, "log", "-1", "--format=%an").strip() == "pkm-mcp"
    assert not (cfg.root / ".git").exists()


def test_create_strips_frontmatter_and_suffixes(svc):
    """Mitgeliefertes Frontmatter wird entfernt, gleiche Namen bekommen ein Suffix."""
    a = svc.create_document(title="Gleich", content="---\nid: fremd\n---\nText\n")
    b = svc.create_document(title="Gleich", content="Text 2")
    assert a["path"] != b["path"] and b["path"].endswith("_gleich-2.md")
    assert svc.read(a["path"])["frontmatter"]["id"] == a["id"] != "fremd"


def test_create_related_and_correction(svc, cfg, doc):
    """related wird als Wikilink gespeichert, kind correction ist möglich."""
    write(cfg, "wiki/topics/regen.md", "---\ntype: topic\n---\n> Kurz\n")
    res = svc.create_document(title="Korrektur Regen", content="Falsch: x. Richtig: y.", kind="correction",
                              related=["[[wiki/topics/regen]]", f"id:{doc['id']}"])
    fm = svc.read(res["path"])["frontmatter"]
    assert fm["kind"] == "correction"
    assert fm["related"] == ["[[wiki/topics/regen]]", f"[[{doc['path'][:-3]}]]"]
    with pytest.raises(PkmError):
        svc.create_document(title="x", content="y", kind="falsch")
    with pytest.raises(PkmError) as e:
        svc.create_document(title="x", content="y", related=["gibtsnicht"])
    assert e.value.status == "not_found"


@pytest.mark.usefixtures("svc", "isolated_env")
def test_create_too_large(monkeypatch):
    """Zu große Inhalte werden abgelehnt."""
    monkeypatch.setenv("PKM_MAX_KB", "1")
    with pytest.raises(PkmError) as e:
        Service(Config.from_env()).create_document(title="Groß", content="x" * 2000)
    assert e.value.status == "too_large"


def test_create_platform_safe_name(svc):
    """Dateinamen aus Titeln sind plattformfest."""
    res = svc.create_document(title='CON: a/b*c?"d"<e>|', content="x")
    name = res["path"].rsplit("/", 1)[1]
    assert not re.search(r'[\\:*?"<>|]', name) and len(name) <= 120


def test_slug_windows_reserved(svc):
    """Reservierte Windows-Namen werden umgangen."""
    assert svc.create_document(title="NUL", content="x")["path"].endswith("_nul-doc.md")


# Grundregeln *****************************************************************
def test_every_change_one_version_one_commit(doc, svc, isolated_env):
    """Jede Änderung erhöht die Version um 1 und erzeugt genau einen Commit."""
    n = len(commits(isolated_env))
    r = svc.edit_document(target=f"id:{doc['id']}", old="Kabelweg", new="Kabelweg prüfen",
                          expected_hash=doc["new_hash"], note=None)
    assert r["status"] == "changed" and r["version"] == 2
    assert len(commits(isolated_env)) == n + 1
    body, files, tr = last_commit(isolated_env)
    assert files == [doc["path"]] and tr["PKM-Version"] == "2" and tr["PKM-Source"] == "chat"
    assert "Textstelle geändert" in body
    cur = svc.read(doc["path"])
    assert cur["version"] == 2 and cur["hash"] == r["new_hash"]
    assert cur["frontmatter"]["date_updated"] >= cur["frontmatter"]["date_markdown"]
    assert "+- Kabelweg prüfen" in r["diff"]


def test_hash_conflict(doc, svc):
    """Ein falscher oder fehlender expected_hash ergibt conflict."""
    with pytest.raises(PkmError) as e:
        svc.edit_document(target=doc["path"], old="Kabelweg", new="x", expected_hash="0" * 64)
    assert e.value.status == "conflict" and e.value.data["current_hash"] == doc["new_hash"]
    with pytest.raises(PkmError) as e:
        svc.edit_document(target=doc["path"], old="Kabelweg", new="x", expected_hash="")
    assert e.value.status == "conflict"


def test_other_open_changes_untouched(doc, svc, cfg, isolated_env):
    """Offene Änderungen anderer Dateien bleiben unberührt."""
    write(cfg, "documents/andere.md", "offen\n")
    (cfg.root / "CLAUDE.md").write_text("geändert\n")
    svc.edit_document(target=doc["path"], old="Kabelweg", new="Kabel", expected_hash=doc["new_hash"])
    status = git(isolated_env, "status", "--porcelain")
    assert "documents/andere.md" in status and "CLAUDE.md" in status


@pytest.mark.parametrize("target", ["wiki/index.md", "CLAUDE.md", "../x.md", "/etc/passwd"])
def test_forbidden_targets(svc, target):
    """Ziele außerhalb von documents/ werden abgelehnt."""
    with pytest.raises(PkmError) as e:
        svc.edit_document(target=target, old="a", new="b", expected_hash="x")
    assert e.value.status in ("forbidden", "not_found", "invalid_path")


def test_wiki_forbidden(svc, cfg):
    """Wiki-Seiten sind aus Chats nicht änderbar."""
    write(cfg, "wiki/topics/t.md", "---\ntype: topic\n---\nText\n")
    h = svc.read("wiki/topics/t")["hash"]
    for call in (
        lambda: svc.edit_document(target="wiki/topics/t", old="Text", new="x", expected_hash=h),
        lambda: svc.append_to_document(target="[[t]]", text="x", expected_hash=h),
        lambda: svc.rewrite_document(target="wiki/topics/t.md", content="x", expected_hash=h),
    ):
        with pytest.raises(PkmError) as e:
            call()
        assert e.value.status == "forbidden"


def test_pdf_forbidden(svc, cfg):
    """Nicht-Markdown-Dateien sind nicht änderbar."""
    write(cfg, "documents/a.pdf", "%PDF")
    with pytest.raises(PkmError) as e:
        svc.edit_document(target="documents/a.pdf", old="a", new="b", expected_hash="x")
    assert e.value.status == "forbidden"


def test_invalid_frontmatter_refused(svc, cfg):
    """Dateien mit ungültigem Frontmatter werden nicht geändert."""
    write(cfg, "documents/k.md", "---\ntitle: [x\n---\nText\n")
    h = svc.read("documents/k.md")["hash"]
    with pytest.raises(PkmError) as e:
        svc.edit_document(target="documents/k.md", old="Text", new="x", expected_hash=h)
    assert e.value.status == "invalid_frontmatter"


@pytest.mark.usefixtures("isolated_env")
def test_without_git_writes_refused_reads_work(cfg, svc, doc):
    """Ohne Git sind Schreibtools gesperrt, Lesen und Suche gehen weiter."""
    shutil.rmtree(cfg.git_dir)
    with pytest.raises(PkmError) as e:
        svc.create_document(title="x", content="y")
    assert e.value.status == "git_unavailable"
    assert svc.read(doc["path"])["version"] == 1
    assert svc.search("Ultraschall", scope="documents")["results"]


def test_commit_failure_restores_file(doc, svc, cfg):
    """Schlägt der Commit fehl, wird die Datei zurückgesetzt."""
    before = (cfg.root / doc["path"]).read_bytes()
    hook = cfg.git_dir / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(PkmError) as e:
        svc.edit_document(target=doc["path"], old="Kabelweg", new="x", expected_hash=doc["new_hash"])
    assert e.value.status == "commit_failed"
    assert (cfg.root / doc["path"]).read_bytes() == before
    with pytest.raises(PkmError):
        svc.create_document(title="Neu", content="x")
    assert not any("_neu" in p for p in svc.vault.iter_files())


def test_unchanged_no_commit(doc, svc, isolated_env):
    """Eine Änderung ohne Wirkung ergibt unchanged ohne Commit."""
    n = len(commits(isolated_env))
    r = svc.edit_document(target=doc["path"], old="Kabelweg", new="Kabelweg", expected_hash=doc["new_hash"])
    assert r["status"] == "unchanged" and r["version"] == 1 and len(commits(isolated_env)) == n


# Änderungen von Hand (5.4) ***************************************************
def test_hand_edit_committed_first(doc, svc, cfg, isolated_env):
    """Eine Änderung von Hand wird vorher als eigene Version committet."""
    p = cfg.root / doc["path"]
    p.write_text(p.read_text(encoding="utf-8").replace("Kabelweg", "Kabelweg (von Hand)"), encoding="utf-8")
    h = svc.read(doc["path"])["hash"]
    n = len(commits(isolated_env))
    r = svc.append_to_document(target=doc["path"], text="- Neuer Punkt", expected_hash=h, section="Offene Punkte")
    assert r["version"] == 3
    assert len(commits(isolated_env)) == n + 2
    hist = svc.history(doc["path"])["versions"]
    assert [(v["version"], v["source"]) for v in hist] == [(1, "chat"), (2, "user"), (3, "chat")]
    assert git(isolated_env, "log", "-2", "--format=%an").split("\n")[1] == "Test User"
    assert "Kabelweg (von Hand)" in svc.read(f"id:{doc['id']}", version=2)["content"]


@pytest.mark.usefixtures("isolated_env")
def test_hand_document_without_id_gets_id(svc, cfg):
    """Ein Dokument ohne ID bekommt vor der Änderung ID und Version 1."""
    write(cfg, "documents/haus/eigen.md", "# Eigen\n\nText\n")
    h = svc.read("documents/haus/eigen.md")["hash"]
    r = svc.append_to_document(target="[[eigen]]", text="Mehr", expected_hash=h)
    assert r["version"] == 2 and r["id"]
    hist = svc.history("[[eigen]]")["versions"]
    assert [(v["version"], v["source"]) for v in hist] == [(1, "user"), (2, "chat")]
    text = (cfg.root / "documents/haus/eigen.md").read_text(encoding="utf-8")
    assert text.startswith(f"---\nid: {r['id']}\nversion: 2\n")


def test_hand_move_then_edit(doc, svc, cfg, isolated_env):
    """Ein von Hand verschobenes Dokument wird ohne Versionssprung als moved committet."""
    (cfg.root / "documents/haus").mkdir()
    (cfg.root / doc["path"]).rename(cfg.root / "documents/haus/sensor.md")
    h = svc.read(f"id:{doc['id']}")["hash"]
    r = svc.edit_document(target=f"id:{doc['id']}", old="Kabelweg", new="Kabel", expected_hash=h)
    assert r["path"] == "documents/haus/sensor.md" and r["version"] == 2
    hist = svc.history(f"id:{doc['id']}")["versions"]
    assert hist[1]["subject"].endswith(" moved") and hist[1]["version"] == 1
    assert git(isolated_env, "status", "--porcelain").strip() == ""


# rewrite_document ************************************************************
def test_rewrite(doc, svc):
    """rewrite_document ersetzt den Inhalt und behält das Frontmatter."""
    new = BODY.replace("Ultraschallsensor", "Schwimmerschalter").replace("- Kabelweg\n", "")
    r = svc.rewrite_document(target=doc["path"], content=new, expected_hash=doc["new_hash"],
                             note="Sensor: Schwimmerschalter statt Ultraschall")
    assert r["version"] == 2
    cur = svc.read(doc["path"])
    assert "Schwimmerschalter" in cur["content"] and cur["frontmatter"]["context"] == "Chat: Füllstand"
    assert svc.history(doc["path"])["versions"][1]["note"] == "Sensor: Schwimmerschalter statt Ultraschall"


def test_rewrite_large_shortening(doc, svc):
    """Starke Kürzung erfordert confirm_shortening."""
    with pytest.raises(PkmError) as e:
        svc.rewrite_document(target=doc["path"], content="## Ergebnis\nKurz.\n", expected_hash=doc["new_hash"])
    assert e.value.status == "large_shortening"
    assert e.value.data["missing_sections"] == ["Entscheidungen", "Offene Punkte", "Kontext / Begründung"]
    r = svc.rewrite_document(target=doc["path"], content="## Ergebnis\nKurz.\n",
                             expected_hash=doc["new_hash"], confirm_shortening=True)
    assert r["version"] == 2


def test_rewrite_missing_section_only(doc, svc):
    """Auch ein einzelner fehlender Abschnitt löst large_shortening aus."""
    new = BODY.replace("## Kontext / Begründung", "## Hintergrund")
    with pytest.raises(PkmError) as e:
        svc.rewrite_document(target=doc["path"], content=new, expected_hash=doc["new_hash"])
    assert e.value.data["missing_sections"] == ["Kontext / Begründung"]


# append_to_document **********************************************************
@pytest.mark.usefixtures("cfg")
def test_append_existing_section(doc, svc):
    """append_to_document fügt am Ende eines Abschnitts ein."""
    svc.append_to_document(target=doc["path"], text="- Neu", expected_hash=doc["new_hash"], section="Offene Punkte")
    body = svc.read(doc["path"])["content"]
    assert "- Kabelweg\n\n- Neu\n\n## Kontext / Begründung" in body


def test_append_new_section_and_end(doc, svc):
    """Neuer Abschnitt bzw. Dateiende."""
    r = svc.append_to_document(target=doc["path"], text="Text A", expected_hash=doc["new_hash"], section="Quellen")
    assert svc.read(doc["path"])["content"].endswith("Diskussion im Chat.\n\n## Quellen\n\nText A\n")
    svc.append_to_document(target=doc["path"], text="Ende", expected_hash=r["new_hash"])
    assert svc.read(doc["path"])["content"].endswith("Text A\n\nEnde\n")


def test_append_preamble(svc):
    """Einfügen in den Vorspann, auch wenn es keinen gibt."""
    d = svc.create_document(title="Vorspann", content="Einleitung\n\n## A\nx\n")
    svc.append_to_document(target=d["path"], text="Zusatz", expected_hash=d["new_hash"], section="_preamble")
    assert svc.read(d["path"])["content"] == "\nEinleitung\n\nZusatz\n\n## A\nx\n"
    e = svc.create_document(title="Ohne Vorspann", content="## A\nx\n")
    svc.append_to_document(target=e["path"], text="Neu oben", expected_hash=e["new_hash"], section="_preamble")
    assert svc.read(e["path"])["content"] == "\nNeu oben\n\n## A\nx\n"


def test_append_duplicates(svc):
    """Doppelte Abschnitte verlangen den Schlüssel mit Suffix."""
    d = svc.create_document(title="Dup", content="## Notizen\na\n## Notizen\nb\n")
    with pytest.raises(PkmError) as e:
        svc.append_to_document(target=d["path"], text="c", expected_hash=d["new_hash"], section="Notizen")
    assert e.value.status == "ambiguous" and e.value.data["candidates"] == ["Notizen", "Notizen#2"]
    svc.append_to_document(target=d["path"], text="c", expected_hash=d["new_hash"], section="Notizen#2")
    assert svc.read(d["path"])["content"] == "\n## Notizen\na\n## Notizen\nb\n\nc\n"


# edit_document ***************************************************************
def test_edit_not_found_and_ambiguous(svc):
    """Fehlende oder mehrfache Textstellen werden gemeldet."""
    d = svc.create_document(title="E", content="a a\n")
    with pytest.raises(PkmError) as e:
        svc.edit_document(target=d["path"], old="b", new="c", expected_hash=d["new_hash"])
    assert e.value.status == "not_found"
    with pytest.raises(PkmError) as e:
        svc.edit_document(target=d["path"], old="a", new="c", expected_hash=d["new_hash"])
    assert e.value.status == "ambiguous" and e.value.data["count"] == 2


def test_edit_outside_frontmatter_only(svc):
    """edit_document ändert nichts im Frontmatter."""
    d = svc.create_document(title="Titelwort", content="Text\n")
    with pytest.raises(PkmError) as e:
        svc.edit_document(target=d["path"], old="Titelwort", new="x", expected_hash=d["new_hash"])
    assert e.value.status == "not_found"


def test_edit_crlf_and_nfd_input(svc):
    """CRLF- und NFD-Eingaben werden normalisiert."""
    d = svc.create_document(title="Norm", content="Zeile eins\nÜber zwei\n")
    r = svc.edit_document(target=d["path"], old="Zeile eins\r\nÜber", new="Neu\r\nÜber",
                          expected_hash=d["new_hash"])
    assert r["status"] == "changed"
    assert "Neu\nÜber zwei" in svc.read(d["path"])["content"]


def test_edit_empty_new_deletes(doc, svc):
    """Ein leeres new löscht die Textstelle."""
    svc.edit_document(target=doc["path"], old="- Kabelweg\n", new="", expected_hash=doc["new_hash"])
    assert "Kabelweg" not in svc.read(doc["path"])["content"]


# update_frontmatter **********************************************************
def test_update_frontmatter(doc, svc):
    """set, add und remove ändern das Frontmatter."""
    r = svc.update_frontmatter(target=doc["path"], expected_hash=doc["new_hash"],
                               set={"title": "Neuer Titel"}, add={"tags": ["sensor", "zisterne"]},
                               remove=["context"])
    fm = svc.read(doc["path"])["frontmatter"]
    assert fm["title"] == "Neuer Titel" and fm["tags"] == ["zisterne", "sensor"]
    assert "context" not in fm and fm["version"] == 2 and fm["id"] == doc["id"]
    assert r["version"] == 2


@pytest.mark.parametrize("field", ["id", "version", "date_markdown", "date_updated", "status_markdown"])
def test_update_frontmatter_protected(doc, svc, field):
    """Geschützte Felder lassen sich nicht ändern."""
    with pytest.raises(PkmError) as e:
        svc.update_frontmatter(target=doc["path"], expected_hash=doc["new_hash"], set={field: "x"})
    assert e.value.status == "protected_field"


def test_update_frontmatter_add_to_scalar(doc, svc):
    """An Felder, die keine Liste sind, kann nichts angehängt werden."""
    with pytest.raises(PkmError):
        svc.update_frontmatter(target=doc["path"], expected_hash=doc["new_hash"], add={"title": ["x"]})


def test_server_fields_linewise_keep_comments(svc, cfg):
    """Kommentare im Frontmatter überstehen eine Änderung."""
    write(cfg, "documents/k.md", "---\ntitle: K  # mein Kommentar\n---\nText\n")
    h = svc.read("documents/k.md")["hash"]
    svc.edit_document(target="documents/k.md", old="Text", new="Neu", expected_hash=h)
    text = (cfg.root / "documents/k.md").read_text(encoding="utf-8")
    assert "title: K  # mein Kommentar" in text and "version: 2" in text


# restore_document ************************************************************
@pytest.mark.usefixtures("isolated_env")
def test_restore(doc, svc):
    """restore_document holt eine alte Version als neue Version zurück."""
    r2 = svc.edit_document(target=doc["path"], old="Kabelweg", new="Kabel", expected_hash=doc["new_hash"])
    r3 = svc.restore_document(target=doc["path"], version=1, expected_hash=r2["new_hash"])
    assert r3["version"] == 3 and "Kabelweg" in svc.read(doc["path"])["content"]
    hist = svc.history(doc["path"])["versions"]
    assert hist[-1]["note"] == "wiederhergestellt aus v1"
    with pytest.raises(PkmError):
        svc.restore_document(target=doc["path"], version=9, expected_hash=r3["new_hash"])


def test_cli_restore(doc, svc, capsys):

    """pkm restore committet mit Quelle user."""
    svc.edit_document(target=doc["path"], old="Kabelweg", new="Kabel", expected_hash=doc["new_hash"])
    assert main(["restore", doc["path"], "--version", "1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["version"] == 3
    assert svc.history(doc["path"])["versions"][-1]["source"] == "user"


# MCP-Tools *******************************************************************
@pytest.mark.usefixtures("cfg")
def test_mcp_write_tools_registered():

    """Alle schreibenden Tools sind registriert."""
    names = {t.name for t in asyncio.run(mcp_server.build_server().list_tools())}
    assert {"create_document", "rewrite_document", "append_to_document", "edit_document",
            "update_frontmatter", "restore_document"} <= names


def test_mcp_call_create_and_conflict(cfg):

    """Aufruf über den Server: Anlegen klappt, falscher Hash ergibt conflict."""
    mcp_server.reset_service()
    server = mcp_server.build_server()
    out = asyncio.run(server.call_tool("create_document", {"title": "Per MCP", "content": "Hallo"}))
    assert "created" in str(out)
    path = next(p for p in mcp_server.get_service().vault.iter_files() if p.endswith("_per-mcp.md"))
    res = mcp_server.call("edit_document", lambda s, **k: s.edit_document(**k), target=path, old="Hallo",
                          new="Servus", expected_hash="falsch")
    assert res["status"] == "conflict" and len(res["current_hash"]) == 64
    log = cfg.log_path.read_text(encoding="utf-8")
    assert '"tool": "create_document"' in log and '"status": "conflict"' in log
    mcp_server.reset_service()

# Main ************************************************************************
