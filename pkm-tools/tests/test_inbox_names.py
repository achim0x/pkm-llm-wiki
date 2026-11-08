"""Tests: name proposals for new documents in the inbox and renaming with the image folder.

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

import pytest

from pkm import inboxnames, maintenance_server, maintrun
from pkm.errors import PkmError
from pkm.maint import Maintenance

from .conftest import git, write
from .test_images_core import make_png

# Variables *******************************************************************

INBOX = "documents/_inbox"
DOC = f"{INBOX}/Meeting Notes.md"
TEXT = ("---\ntitle: Projekt Übergabe\ndate_markdown: 2026-11-03T10:00:00\n---\n\n## Bilder\n"
        "![Skizze](Meeting%20Notes_files/skizze.png)\n\n![[Meeting Notes_files/foto.png]]\n\n"
        "![Logo](../_attachments/logo.png)\n")

# Classes *********************************************************************

# Functions *******************************************************************


def _png(svc, rel, size=3):
    """Write a PNG file.

    Args:
        svc: Service.
        rel: Path in the vault.
        size: Width and height (different sizes give different bytes).
    """
    path = svc.cfg.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(make_png(size, size, text=False))


def _setup(svc):
    """Inbox document with its own image folder and a shared attachment.

    Args:
        svc: Service.
    """
    write(svc.cfg, DOC, TEXT)
    _png(svc, f"{INBOX}/Meeting Notes_files/skizze.png", 3)
    _png(svc, f"{INBOX}/Meeting Notes_files/foto.png", 4)
    _png(svc, "documents/_attachments/logo.png", 5)


def test_conforming_names():
    """Names after the convention need no proposal; others do."""
    assert inboxnames.conforming(f"{INBOX}/projekt-uebergabe_2026-11-03.md")
    assert inboxnames.conforming(f"{INBOX}/projekt-uebergabe-2_2026-11-03.md")
    assert not inboxnames.conforming(DOC)
    assert not inboxnames.conforming(f"{INBOX}/Projekt_2026-11-03.md")
    assert not inboxnames.conforming(f"{INBOX}/projekt.md")


def test_begin_maintenance_proposes_name(svc, cfg):
    """begin_maintenance adds a rename proposal with the image folder; _status.md names it."""
    _setup(svc)
    begin = maintrun.begin_maintenance(svc)
    entry = next(e for e in begin["pending"]["new"] if e["path"] == DOC)
    proposal = entry["rename"]
    assert proposal["to"] == f"{INBOX}/projekt-uebergabe_2026-11-03.md"
    assert proposal["image_folders"] == [{"from": f"{INBOX}/Meeting Notes_files",
                                          "to": f"{INBOX}/projekt-uebergabe_2026-11-03_img"}]
    assert [c["to"] for c in proposal["links"]] == [
        "projekt-uebergabe_2026-11-03_img/skizze.png", f"{INBOX}/projekt-uebergabe_2026-11-03_img/foto.png"]
    assert "text" not in proposal
    maintrun.finish_maintenance(svc, "- nothing processed")
    status = (cfg.root / "wiki/_status.md").read_text(encoding="utf-8")
    assert "name proposal: projekt-uebergabe_2026-11-03.md" in status


def test_rename_proposal_and_apply(svc, cfg, isolated_env):
    """Without apply only the proposal; with apply file, folder and links move, in one agent commit."""
    _setup(svc)
    maintrun.begin_maintenance(svc)
    doc = svc.read(DOC)
    prop = maintrun.rename_document(svc, DOC, doc["hash"])
    assert prop["status"] == "proposal" and (cfg.root / DOC).exists()

    res = maintrun.rename_document(svc, DOC, doc["hash"], apply=True)
    new = f"{INBOX}/projekt-uebergabe_2026-11-03.md"
    assert res["status"] == "renamed" and res["path"] == new and res["version"] == doc["version"] + 1
    assert not (cfg.root / DOC).exists() and not (cfg.root / INBOX / "Meeting Notes_files").exists()
    text = (cfg.root / new).read_text(encoding="utf-8")
    assert "![Skizze](projekt-uebergabe_2026-11-03_img/skizze.png)" in text
    assert f"![[{INBOX}/projekt-uebergabe_2026-11-03_img/foto.png]]" in text
    assert "![Logo](../_attachments/logo.png)" in text  # shared folder untouched
    assert (cfg.root / INBOX / "projekt-uebergabe_2026-11-03_img/foto.png").exists()
    assert git(isolated_env, "status", "--porcelain", "--", "documents/_inbox").strip() == ""
    assert git(isolated_env, "log", "-1", "--format=%an").strip() != ""
    assert "PKM-Source: agent" in git(isolated_env, "log", "-1", "--format=%B")

    pend = Maintenance(svc).pending()
    assert [e["path"] for e in pend["new"] if e["path"].startswith(INBOX)] == [new]
    assert not [i for i in pend["new"] if i["path"].endswith(".png")]  # images still attachments


def test_rename_only_moves_without_images(svc):
    """A document without its own image folder is only moved (version stays)."""
    write(svc.cfg, f"{INBOX}/Notiz.md", "---\ntitle: Kurze Notiz\n---\n\nText.\n")
    begin = maintrun.begin_maintenance(svc)
    entry = begin["pending"]["new"][0]
    assert entry["rename"]["image_folders"] == []
    doc = svc.read(f"{INBOX}/Notiz.md")
    res = maintrun.rename_document(svc, f"id:{doc['id']}", doc["hash"], apply=True)
    date = doc["id"][2:6] + "-" + doc["id"][6:8] + "-" + doc["id"][8:10]
    assert res["path"] == f"{INBOX}/kurze-notiz_{date}.md" and res["version"] == doc["version"]


def test_rename_own_name_and_collision(svc):
    """name replaces the title; an existing name gets a suffix before the date."""
    write(svc.cfg, f"{INBOX}/zisterne_2026-11-03.md", "---\ntitle: Zisterne\n---\n\nA.\n")
    write(svc.cfg, f"{INBOX}/Neu.md", "---\ntitle: Etwas\ndate_markdown: 2026-11-03T08:00:00\n---\n\nB.\n")
    begin = maintrun.begin_maintenance(svc)
    assert [e["path"] for e in begin["pending"]["new"] if "rename" in e] == [f"{INBOX}/Neu.md"]
    doc = svc.read(f"{INBOX}/Neu.md")
    res = maintrun.rename_document(svc, f"{INBOX}/Neu.md", doc["hash"], name="Zisterne")
    assert res["path"] == f"{INBOX}/zisterne-2_2026-11-03.md"


def test_shared_folder_is_kept_and_links_reported(svc):
    """A folder other documents also use is not renamed; links from other documents are reported."""
    write(svc.cfg, DOC, TEXT)
    _png(svc, f"{INBOX}/Meeting Notes_files/skizze.png", 3)
    _png(svc, f"{INBOX}/Meeting Notes_files/foto.png", 4)
    write(svc.cfg, f"{INBOX}/other_2026-11-01.md",
          "---\ntitle: Other\n---\n\n![x](Meeting%20Notes_files/foto.png)\n\nSee [[Meeting Notes]].\n")
    maintrun.begin_maintenance(svc)
    doc = svc.read(DOC)
    prop = maintrun.rename_document(svc, DOC, doc["hash"])
    assert prop["image_folders"] == [] and prop["kept_folders"][0]["reason"] == "shared"
    assert prop["linked_from"] == [f"{INBOX}/other_2026-11-01.md"]


def test_rename_refused_outside_inbox_and_on_conflict(svc):
    """Only Markdown in the inbox; a wrong hash is a conflict; a conforming name stays."""
    write(svc.cfg, "documents/haus/Zisterne.md", "---\ntitle: Zisterne\n---\n\nA.\n")
    write(svc.cfg, f"{INBOX}/ok_2026-11-03.md", "---\ntitle: Ok\n---\n\nB.\n")
    write(svc.cfg, f"{INBOX}/Bad Name.md", "---\ntitle: Bad\n---\n\nC.\n")
    maintrun.begin_maintenance(svc)
    doc = svc.read("documents/haus/Zisterne.md")
    with pytest.raises(PkmError) as exc:
        maintrun.rename_document(svc, "documents/haus/Zisterne.md", doc["hash"])
    assert exc.value.status == "forbidden"
    with pytest.raises(PkmError) as exc:
        maintrun.rename_document(svc, f"{INBOX}/Bad Name.md", "0" * 64)
    assert exc.value.status == "conflict"
    ok = svc.read(f"{INBOX}/ok_2026-11-03.md")
    assert maintrun.rename_document(svc, f"{INBOX}/ok_2026-11-03.md", ok["hash"])["status"] == "unchanged"


def test_processed_document_renamed_citations_follow(svc, cfg):
    """A document renamed after processing appears as moved; its citations follow."""
    write(cfg, f"{INBOX}/Verhandlung.md", "---\ntitle: Verhandlung\n---\n\n## Regeln\nNie den ersten Preis.\n")
    begin = maintrun.begin_maintenance(svc)
    doc_id = begin["ids"]["assigned"][0]["id"]
    doc = svc.read(f"id:{doc_id}")
    sha = next(s["sha"] for s in doc["sections"] if s["key"] == "Regeln")
    page = ("---\ntype: summary\ntitle: Verhandlung\nsources: []\ndate_updated: 2026-11-02T21:10:00\n"
            "confidence: high\n---\n\n> **Summary:** Regeln.\n\n## Content\nNie.[^b1]\n\n## Citations\n"
            f"[^b1]: [[{INBOX}/Verhandlung#Regeln]] · \"Nie den ersten Preis.\" · id:{doc_id} · "
            f"v:{doc['version']} · sha:{sha}\n")
    maintrun.write_wiki_page(svc, "wiki/summaries/verhandlung", page)
    maintrun.finish_maintenance(svc, "- new", processed=[doc_id])
    res = maintrun.rename_document(svc, f"id:{doc_id}", doc["hash"], apply=True)
    fin = maintrun.finish_maintenance(svc, "- renamed", operation="fix", processed=[doc_id])
    assert fin["lint"]["summary"]["error"] == 0, fin["lint"]["findings"]
    assert f"[[{res['path'][:-3]}#Regeln]]" in (cfg.root / "wiki/summaries/verhandlung.md").read_text(
        encoding="utf-8")
    assert not Maintenance(svc).pending()["moved"]


def test_server_offers_rename_document():
    """The maintenance server offers rename_document."""
    tools = {t.name for t in asyncio.run(maintenance_server.build_server().list_tools())}
    assert "rename_document" in tools

# Main ************************************************************************
