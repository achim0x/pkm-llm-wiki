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
    img = f"{INBOX}/projekt-uebergabe_2026-11-03_img"
    assert proposal["images_moved"] == [{"from": "documents/_attachments/logo.png", "to": f"{img}/logo.png"},
                                        {"from": f"{INBOX}/Meeting Notes_files/foto.png", "to": f"{img}/foto.png"},
                                        {"from": f"{INBOX}/Meeting Notes_files/skizze.png", "to": f"{img}/skizze.png"}]
    assert [c["to"] for c in proposal["links"]] == [f"./projekt-uebergabe_2026-11-03_img/{n}.png"
                                                    for n in ("skizze", "foto", "logo")]
    assert proposal["kept"] == []
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
    assert "![Skizze](./projekt-uebergabe_2026-11-03_img/skizze.png)" in text
    assert "![](./projekt-uebergabe_2026-11-03_img/foto.png)" in text  # embed becomes a relative Markdown image
    assert "![Logo](./projekt-uebergabe_2026-11-03_img/logo.png)" in text  # only this document used it
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
    assert entry["rename"]["images_moved"] == []
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
    assert {"from": f"{INBOX}/Meeting Notes_files/skizze.png",
            "to": f"{INBOX}/{prop['path'].rsplit('/', 1)[1][:-3]}_img/skizze.png"} in prop["images_moved"]
    assert {"path": f"{INBOX}/Meeting Notes_files/foto.png", "reason": "shared"} in prop["kept"]
    assert prop["linked_from"] == [f"{INBOX}/other_2026-11-01.md"]


def test_rename_rules_inside_and_outside_inbox(svc):
    """Outside the inbox only names against the rules get a proposal; wrong hash conflict; conforming stays."""
    write(svc.cfg, "documents/haus/Zisterne.md",
          "---\ntitle: Zisterne\ndate_markdown: 2026-11-01T08:00:00\n---\n\nA.\n")
    write(svc.cfg, "documents/haus/pumpe.md", "---\ntitle: Pumpe\n---\n\nP.\n")
    write(svc.cfg, f"{INBOX}/ok_2026-11-03.md", "---\ntitle: Ok\n---\n\nB.\n")
    write(svc.cfg, f"{INBOX}/Bad Name.md", "---\ntitle: Bad\n---\n\nC.\n")
    maintrun.begin_maintenance(svc)
    doc = svc.read("documents/haus/Zisterne.md")
    prop = maintrun.rename_document(svc, "documents/haus/Zisterne.md", doc["hash"])
    assert prop["status"] == "proposal" and prop["path"] == "documents/haus/zisterne_2026-11-01.md"
    pumpe = svc.read("documents/haus/pumpe.md")
    assert maintrun.rename_document(svc, "documents/haus/pumpe.md", pumpe["hash"])["status"] == "unchanged"
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

def _training(svc):
    """Inbox like in review B10: a document with spaces and capitals, images/IMG_0nn.png with alt texts.

    Args:
        svc: Service.
    """
    lines = [f"![Konzeptlandkarte Teil {n}](images/IMG_{n:03d}.png)" for n in range(1, 4)]
    write(svc.cfg, f"{INBOX}/Training from the Back of the Room.md",
          "---\ntitle: Training from the Back of the Room\ndate_markdown: 2026-11-04T09:00:00\n---\n\n## A\n"
          + "\n\n".join(lines) + "\n")
    for n in range(1, 4):
        _png(svc, f"{INBOX}/images/IMG_{n:03d}.png", 2 + n)


def test_lint_naming_groups(svc):
    """Lint reports three naming groups for the inbox: document, folder, generic image names."""
    _training(svc)
    from pkm.lint import lint  # pylint: disable=import-outside-toplevel
    naming = [f for f in lint(svc)["findings"] if f["check"] == "naming"]
    kinds = sorted(f["detail"]["kind"] for f in naming)
    assert kinds == ["document", "folder", "images"], naming
    doc = next(f for f in naming if f["detail"]["kind"] == "document")
    assert doc["detail"]["suggested_name"] == "training-from-the-back-of-the-room_2026-11-04.md"
    folder = next(f for f in naming if f["detail"]["kind"] == "folder")
    assert folder["path"] == f"{INBOX}/images" and folder["detail"]["suggested_name"] == \
        "training-from-the-back-of-the-room_2026-11-04_img"
    imgs = next(f for f in naming if f["detail"]["kind"] == "images")
    assert [f["suggested_name"] for f in imgs["detail"]["files"]] == [
        f"konzeptlandkarte-teil-{n}_2026-11-04.png" for n in range(1, 4)]
    assert all(f["severity"] == "info" for f in naming)


def test_rename_with_generic_images_then_notation_only(svc, cfg):
    """rename_document moves and names the images; the folder images/ disappears; next run notation only."""
    _training(svc)
    maintrun.begin_maintenance(svc)
    rel = f"{INBOX}/Training from the Back of the Room.md"
    doc = svc.read(rel)
    maintrun.finish_maintenance(svc, "- processed", processed=[doc["id"]])
    res = maintrun.rename_document(svc, rel, doc["hash"], apply=True)
    stem = "training-from-the-back-of-the-room_2026-11-04"
    assert res["path"] == f"{INBOX}/{stem}.md"
    assert not (cfg.root / INBOX / "images").exists()
    text = (cfg.root / res["path"]).read_text(encoding="utf-8")
    assert f"![Konzeptlandkarte Teil 1](./{stem}_img/konzeptlandkarte-teil-1_2026-11-04.png)" in text
    item = next(i for i in Maintenance(svc).pending()["changed"] if i["path"] == res["path"])
    assert item["image_notation_only"] is True and len(item["images_moved"]) == 3


def test_move_images_from_attachments(svc, cfg):
    """Lint image_location for old files in _attachments; move_images moves them next to the document."""
    _png(svc, "documents/_attachments/schema.png", 3)
    _png(svc, "documents/_attachments/shared.png", 4)
    write(cfg, "documents/KI/sandbox.md", "---\ntitle: Sandbox\n---\n\n## A\n![Schema](../_attachments/schema.png)\n"
          "![Gemeinsam](../_attachments/shared.png)\n")
    write(cfg, "documents/KI/other.md", "---\ntitle: Other\n---\n\n![x](../_attachments/shared.png)\n")
    maintrun.begin_maintenance(svc)
    from pkm.lint import lint  # pylint: disable=import-outside-toplevel
    loc = [f for f in lint(svc)["findings"] if f["check"] == "image_location"]
    assert [f["path"] for f in loc] == ["documents/KI/sandbox.md"]
    doc = svc.read("documents/KI/sandbox.md")
    prop = maintrun.move_images(svc, "documents/KI/sandbox.md", doc["hash"])
    assert prop["status"] == "proposal" and (cfg.root / "documents/_attachments/schema.png").exists()
    res = maintrun.move_images(svc, "documents/KI/sandbox.md", doc["hash"], apply=True)
    assert res["status"] == "moved"
    assert res["images_moved"] == [{"from": "documents/_attachments/schema.png",
                                    "to": "documents/KI/sandbox_img/schema.png"}]
    assert res["kept"] == [{"path": "documents/_attachments/shared.png", "reason": "shared"}]
    text = (cfg.root / "documents/KI/sandbox.md").read_text(encoding="utf-8")
    assert "![Schema](./sandbox_img/schema.png)" in text and "../_attachments/shared.png" in text
    assert (cfg.root / "documents/_attachments").is_dir()  # the old folder itself stays


def test_default_name_without_subtitle(svc):
    """R1: the proposal without name drops the subtitle and stays short."""
    write(svc.cfg, f"{INBOX}/Training.md", "---\ntitle: Training from the Back of the Room – 65 Wege, in Trainings "
          "Raum fürs Lernen zu schaffen\ndate_markdown: 2026-11-07T10:00:00\n---\n\nText.\n")
    begin = maintrun.begin_maintenance(svc)
    entry = next(e for e in begin["pending"]["new"] if e["path"] == f"{INBOX}/Training.md")
    assert entry["rename"]["to"] == f"{INBOX}/training-from-the-back-of-the-room_2026-11-07.md"


def test_title_slug_limits():
    """Subtitles after ' – ', ' - ' or ': ' are dropped; long titles are cut at a word boundary."""
    from pkm.paths import title_slug  # pylint: disable=import-outside-toplevel
    assert title_slug("Zisterne: Überlaufsensor") == "zisterne"
    assert title_slug("Teil A - Teil B") == "teil-a"
    assert title_slug("KI-Agenten im Alltag") == "ki-agenten-im-alltag"
    slug = title_slug("eins zwei drei vier fuenf sechs sieben acht neun zehn elf zwoelf dreizehn", 30)
    assert len(slug) <= 30 and not slug.endswith("-") and slug == "eins-zwei-drei-vier-fuenf"


def test_move_images_always_relative_links(svc, cfg):
    """R2: move_images writes ./<document name>_img/… for Obsidian embeds and vault paths alike."""
    for n in (1, 2, 3):
        _png(svc, f"documents/Softskills/images_x/IMG_00{n}.png", 2 + n)
    write(cfg, "documents/Softskills/Encyclopedia.md", "---\ntitle: Encyclopedia\ndate_markdown: 2026-11-04T09:00:00\n"
          "---\n\n## A\n![[images_x/IMG_001.png]]\n\n![The four workshop phases](documents/Softskills/images_x/"
          "IMG_002.png)\n\n![[images_x/IMG_003.png|300]]\n")
    maintrun.begin_maintenance(svc)
    doc = svc.read("documents/Softskills/Encyclopedia.md")
    prop = maintrun.move_images(svc, "documents/Softskills/Encyclopedia.md", doc["hash"])
    assert all(c["to"].startswith("./Encyclopedia_img/") for c in prop["links"]), prop["links"]
    assert "./Encyclopedia_img/the-four-workshop-phases_2026-11-04.png" in [c["to"] for c in prop["links"]]
    res = maintrun.move_images(svc, "documents/Softskills/Encyclopedia.md", doc["hash"], apply=True)
    text = (cfg.root / "documents/Softskills/Encyclopedia.md").read_text(encoding="utf-8")
    assert "![|300](./Encyclopedia_img/IMG_003.png)" in text and "![[" not in text
    assert res["status"] == "moved"


def test_extract_images_tool_in_both_servers():
    """R3: extract_images is offered by both servers with min_kb and apply."""
    from pkm import mcp_server  # pylint: disable=import-outside-toplevel
    for mod in (mcp_server, maintenance_server):
        tool = next(t for t in asyncio.run(mod.build_server("en").list_tools()) if t.name == "extract_images")
        schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", {})
        assert {"target", "expected_hash", "min_kb", "apply"} <= set(schema["properties"])


def test_rename_names_citing_wiki_pages(svc, cfg):
    """R5: the proposal names the wiki pages that cite the document and the number of citations."""
    rel = f"{INBOX}/Verhandlung Regeln.md"
    write(cfg, rel, "---\ntitle: Verhandlung\n---\n\n## Regeln\nNie den ersten Preis.\n")
    begin = maintrun.begin_maintenance(svc)
    doc_id = begin["ids"]["assigned"][0]["id"]
    doc = svc.read(f"id:{doc_id}")
    sha = next(s["sha"] for s in doc["sections"] if s["key"] == "Regeln")
    cit = f'[[{rel[:-3]}#Regeln]] · "Nie den ersten Preis." · id:{doc_id} · v:{doc["version"]} · sha:{sha}'
    write(cfg, "wiki/summaries/verhandlung.md", "---\ntype: summary\ntitle: V\n---\n\n> **Summary:** S\n\n"
          f"## Content\nA.[^b1] B.[^b2]\n\n## Citations\n[^b1]: {cit}\n[^b2]: {cit}\n")
    write(cfg, "wiki/topics/verhandeln.md", "---\ntype: topic\ntitle: Verhandeln\n---\n\n> **Summary:** S\n\n"
          f"## See also\n- [[{rel[:-3]}]]\n")
    prop = maintrun.rename_document(svc, rel, doc["hash"])
    assert prop["cited_by"] == [{"page": "wiki/summaries/verhandlung", "citations": 2},
                                {"page": "wiki/topics/verhandeln", "citations": 0}]
    assert prop["citations"] == 2
    from pkm.lint import lint  # pylint: disable=import-outside-toplevel
    naming = next(f for f in lint(svc)["findings"] if f["check"] == "naming" and f["detail"]["kind"] == "document")
    assert naming["detail"]["citations"] == 2


def test_image_location_proposes_lowercase_rename(svc, cfg):
    """R6/R8: a name with capitals: lint proposes rename_document; generic names with generic alt text are named."""
    _png(svc, "documents/Softskills/images_x/IMG_001.png", 3)
    _png(svc, "documents/Softskills/images_x/IMG_066.png", 4)
    write(cfg, "documents/Softskills/Ultimate_Workshop_Encyclopedia.md",
          "---\ntitle: Ultimate Workshop Encyclopedia\ndate_markdown: 2026-11-04T09:00:00\n---\n\n## A\n"
          "![The four phases](images_x/IMG_001.png)\n\n![Image](images_x/IMG_066.png)\n")
    maintrun.begin_maintenance(svc)
    from pkm.lint import lint  # pylint: disable=import-outside-toplevel
    loc = next(f for f in lint(svc)["findings"] if f["check"] == "image_location")
    assert loc["detail"]["tool"] == "rename_document"
    assert loc["detail"]["suggested_name"] == "ultimate-workshop-encyclopedia_2026-11-04.md"
    assert loc["detail"]["target"] == "documents/Softskills/ultimate-workshop-encyclopedia_2026-11-04_img"
    assert loc["detail"]["generic_names_kept"] == ["documents/Softskills/images_x/IMG_066.png"]
    rel = "documents/Softskills/Ultimate_Workshop_Encyclopedia.md"
    doc = svc.read(rel)
    prop = maintrun.rename_document(svc, rel, doc["hash"])
    assert prop["generic_names_kept"] == ["documents/Softskills/images_x/IMG_066.png"] and "hint" in prop
    res = maintrun.rename_document(svc, rel, doc["hash"], apply=True, alt_texts={"IMG_066.png": "Ablauf Kreis"})
    img = "ultimate-workshop-encyclopedia_2026-11-04_img"
    assert res["path"] == "documents/Softskills/ultimate-workshop-encyclopedia_2026-11-04.md"
    text = (cfg.root / res["path"]).read_text(encoding="utf-8")
    assert f"![Ablauf Kreis](./{img}/ablauf-kreis_2026-11-04.png)" in text
    assert f"![The four phases](./{img}/the-four-phases_2026-11-04.png)" in text
    assert not (cfg.root / "documents/Softskills/images_x").exists()


def test_alt_texts_unknown_file_is_rejected(svc, cfg):
    """alt_texts with an unknown file is invalid_argument."""
    _png(svc, "documents/KI/doc_img/IMG_001.png", 3)
    write(cfg, "documents/KI/doc.md", "---\ntitle: Doc\n---\n\n![Image](./doc_img/IMG_001.png)\n")
    maintrun.begin_maintenance(svc)
    doc = svc.read("documents/KI/doc.md")
    with pytest.raises(PkmError) as exc:
        maintrun.move_images(svc, "documents/KI/doc.md", doc["hash"], alt_texts={"nope.png": "x"})
    assert exc.value.status == "invalid_argument"
    prop = maintrun.move_images(svc, "documents/KI/doc.md", doc["hash"], alt_texts={"IMG_001.png": "Schaltplan"})
    (move,) = prop["images_moved"]
    assert move["from"] == "documents/KI/doc_img/IMG_001.png"
    assert move["to"].startswith("documents/KI/doc_img/schaltplan_")
    assert prop["alt_texts"] == {"documents/KI/doc_img/IMG_001.png": "Schaltplan"}


# Main ************************************************************************
