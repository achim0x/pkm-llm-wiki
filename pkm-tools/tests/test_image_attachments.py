"""Attachments regardless of folder, storage location, duplicates and size limit (version 0.3.0).

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
# Imports *********************************************************************

import asyncio
import base64
import hashlib
import json
import random
import struct
import zlib

import pytest

from pkm import imagefix, imagelint, images, maintrun
from pkm.config import Config, ImageConfig
from pkm.errors import PkmError
from pkm.lint import lint
from pkm.maint import Maintenance
from pkm.service import Service
from pkm.vaultinit import init_vault

from .conftest import git, write
from .test_images_core import make_png

# Variables *******************************************************************

DOC_ID = "d-20261106-1200-abcd"

# Classes *********************************************************************

# Functions *******************************************************************


def _doc(svc, rel, body, doc_id=DOC_ID, title="Encyclopedia"):
    """Write a Markdown document with ID and version.

    Args:
        svc: Service.
        rel: Path in the vault.
        body: Body.
        doc_id: ID.
        title: Title.
    """
    write(svc.cfg, rel, f"---\ntitle: {title}\nid: {doc_id}\nversion: 1\n---\n\n{body}")


def _png(svc, rel, size=3):
    """Write a PNG file.

    Args:
        svc: Service.
        rel: Path in the vault.
        size: Width and height (different sizes give different bytes).

    Returns:
        The bytes.
    """
    data = make_png(size, size, text=False)
    path = svc.cfg.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def test_linked_images_in_subfolder_are_attachments(svc):
    """A document with many images in a subfolder gives one new entry with images and no warnings."""
    folder = "documents/Softskills/images_ultimate_workshop_exercises"
    lines = ["## Exercises"]
    for n in range(1, 101):
        _png(svc, f"{folder}/IMG_{n:03d}.png", 2 + n)
        if n % 4 == 0:
            lines.append(f"![[images_ultimate_workshop_exercises/IMG_{n:03d}.png]]")  # Obsidian shortest path
        elif n % 4 == 1:
            lines.append(f"![Exercise {n}](images_ultimate_workshop_exercises/IMG_{n:03d}.png)")
        elif n % 4 == 2:
            lines.append(f"![Exercise {n}](images_ultimate_workshop_exercises/img_{n:03d}.PNG)")  # other case
        else:
            lines.append(f"![[IMG_{n:03d}.png]]")  # bare name
    _doc(svc, "documents/Softskills/Ultimate_Workshop_Exercise_Encyclopedia.md", "\n".join(lines) + "\n")
    m = Maintenance(svc)
    m.versions()
    pend = m.pending()
    assert [d["path"] for d in pend["new"]] == ["documents/Softskills/Ultimate_Workshop_Exercise_Encyclopedia.md"]
    assert len(pend["new"][0]["images"]) == 100 and not pend["orphaned_attachments"]
    res = maintrun.finish_maintenance(svc, "- processed the encyclopedia", "ingest", "Ingest",
                                      processed=[DOC_ID, f"{folder}/IMG_001.png"])
    assert not [w for w in res["warnings"] if "IMG_" in w]
    skipped = [e for e in res["marked"] if e.get("skipped") == "attachment"]
    assert skipped and skipped[0]["attachment_of"] == [
        "documents/Softskills/Ultimate_Workshop_Exercise_Encyclopedia.md"]
    assert Maintenance(svc).pending()["counts"]["new"] == 0


def test_angle_bracket_link_with_spaces(svc):
    """A link in angle brackets with spaces counts as an attachment."""
    _png(svc, "documents/notes/my pictures/a b.png")
    _doc(svc, "documents/notes/note.md", "## A\n![Photo](<my pictures/a b.png>)\n")
    m = Maintenance(svc)
    m.versions()
    pend = m.pending()
    assert [d["path"] for d in pend["new"]] == ["documents/notes/note.md"]
    assert pend["new"][0]["images"] == ["documents/notes/my pictures/a b.png"]


def test_orphan_in_any_folder_and_image_folder(svc):
    """An image that was an attachment is orphaned wherever it lies; so is an unlinked file in a _img folder."""
    _png(svc, "documents/notes/pics/a.png")
    _png(svc, "documents/notes/note_img/loose.png", 5)
    _doc(svc, "documents/notes/note.md", "## A\n![Photo](pics/a.png)\n")
    m = Maintenance(svc)
    m.versions()
    m.mark([DOC_ID])
    _doc(svc, "documents/notes/note.md", "## A\nno image any more\n")
    pend = m.pending()
    assert pend["orphaned_attachments"] == ["documents/notes/note_img/loose.png", "documents/notes/pics/a.png"]
    assert not [d for d in pend["new"] if d["path"].endswith(".png")]


@pytest.fixture(name="dsvc")
def fixture_dsvc(isolated_env, monkeypatch):
    """Service that stores every image as a file (always next to the document, 4.9).

    Args:
        isolated_env: Isolated environment.
        monkeypatch: pytest fixture.

    Returns:
        The service.
    """
    del isolated_env
    monkeypatch.setenv("PKM_INLINE_MAX_KB", "0")
    cfg = Config.from_env()
    init_vault(cfg)
    return Service(cfg)


def test_image_folder_next_to_document(dsvc):
    """New image files go to <folder>/<document name>_img/."""
    png = base64.b64encode(make_png(4, 4, text=False)).decode()
    res = dsvc.create_document(title="Photo", content="## A\n{{image:photo}}\n",
                               images=[{"name": "photo", "alt": "Photo", "png_base64": png}])
    stem = res["path"].rsplit("/", 1)[1][:-3]
    assert res["images"][0]["path"].startswith(f"documents/_inbox/{stem}_img/photo")
    pend = Maintenance(dsvc).pending()
    assert [d["path"] for d in pend["new"]] == [res["path"]] and pend["new"][0]["images"] == [res["images"][0]["path"]]


def test_old_image_folder_setting_is_ignored(isolated_env, monkeypatch):
    """PKM_IMAGE_FOLDER is no longer used: images always go to <document name>_img/."""
    del isolated_env
    monkeypatch.setenv("PKM_IMAGE_FOLDER", "attachments")
    assert Config.from_env().images.folder_for("documents/haus/zisterne.md") == "documents/haus/zisterne_img"

def test_identical_standalone_images_are_duplicates_not_moved(svc):
    """Two byte-identical standalone images: processed once, then pending is empty on every run."""
    data = _png(svc, "documents/_inbox/IMG_020.png", 6)
    (svc.cfg.root / "documents/_inbox/IMG_068.png").write_bytes(data)
    m = Maintenance(svc)
    m.versions()
    pend = m.pending()
    assert [d["path"] for d in pend["new"]] == ["documents/_inbox/IMG_020.png"]
    m.mark(["documents/_inbox/IMG_020.png"])
    for _ in range(2):
        pend = m.pending()
        assert not any(pend[c] for c in ("new", "changed", "moved", "deleted")), pend
    findings = [f for f in lint(svc)["findings"] if f["check"] == "duplicate_image"]
    assert len(findings) == 1 and findings[0]["severity"] == "info"
    assert findings[0]["detail"]["paths"] == ["documents/_inbox/IMG_020.png", "documents/_inbox/IMG_068.png"]


def test_standalone_image_moved_and_changed(svc):
    """moved only if the old path is gone; same path with new content is changed and replaces the entry."""
    _png(svc, "documents/_inbox/photo.png", 6)
    m = Maintenance(svc)
    m.versions()
    m.mark(["documents/_inbox/photo.png"])
    (svc.cfg.root / "documents/_inbox/photo.png").rename(svc.cfg.root / "documents/photo.png")
    pend = m.pending()
    assert [(d["from"], d["to"]) for d in pend["moved"]] == [("documents/_inbox/photo.png", "documents/photo.png")]
    m.mark(["documents/photo.png"])
    _png(svc, "documents/photo.png", 7)
    pend = m.pending()
    assert [d["path"] for d in pend["changed"]] == ["documents/photo.png"] and not pend["new"] and not pend["deleted"]
    m.mark(["documents/photo.png"])
    pend = m.pending()
    assert not any(pend[c] for c in ("new", "changed", "moved", "deleted"))

def big_png(width, height, seed=1):
    """PNG with noise (does not compress), for size tests.

    Args:
        width: Width.
        height: Height.
        seed: Seed of the noise.

    Returns:
        PNG bytes (about 3 bytes per pixel).
    """
    rng = random.Random(seed)

    def chunk(kind, data):
        """Build a PNG chunk.

        Args:
            kind: Chunk type.
            data: Content.

        Returns:
            Bytes of the chunk.
        """
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(rng.getrandbits(8) for _ in range(3 * width)) for _ in range(height))
    return b"".join([images.PNG_SIGNATURE, chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
                     chunk(b"IDAT", zlib.compress(raw, 0)), chunk(b"IEND", b"")])


def _article(svc, n_images=3, side=40):
    """Document with a little text and large embedded Base64 PNGs (like the c't article).

    Args:
        svc: Service.
        n_images: Number of images.
        side: Width and height of each image.

    Returns:
        Path of the document.
    """
    parts = ["## Article", "Some text about sandboxes. " * 20]
    for n in range(n_images):
        b64 = base64.b64encode(big_png(side, side, seed=n)).decode()
        parts.append(f"![Figure {n + 1}](data:image/png;base64,{b64})")
    rel = "documents/KI/sandbox_harness-heise.md"
    _doc(svc, rel, "\n\n".join(parts) + "\n", title="Sandbox harness")
    Maintenance(svc).versions()
    return rel


def test_size_limit_counts_text_without_data_uris(svc, monkeypatch):
    """The limit applies to the text without data URIs; frontmatter changes are exempt."""
    monkeypatch.setenv("PKM_MAX_KB", "2")
    svc = Service(Config.from_env())
    rel = _article(svc)
    assert (svc.cfg.root / rel).stat().st_size > 10 * 1024
    doc = svc.read(rel)
    res = maintrun.set_document_metadata(svc, rel, doc["hash"], set={"context": "Article"})
    assert res["status"] == "changed"
    res = svc.writer.update_frontmatter(rel, res["new_hash"], set={"tags": ["ki"]})
    assert res["status"] == "changed"
    long_text = "word " * 350  # below the limit itself, but the document text gets larger than 2 KB
    with pytest.raises(Exception) as err:
        svc.writer.append_to_document(rel, long_text, res["new_hash"])
    message = str(err.value)
    assert "KB of text without embedded images" in message and "extract" in message
    assert "confirm_large=true" in message
    res = svc.writer.append_to_document(rel, long_text, res["new_hash"], confirm_large=True)
    assert res["status"] == "changed"


def test_confirm_large_overrides_limit(svc, monkeypatch):
    """confirm_large lets the user override PKM_MAX_KB for a single call; without it the call is refused."""
    monkeypatch.setenv("PKM_MAX_KB", "1")
    svc = Service(Config.from_env())
    text = "## Long\n" + "line of text\n" * 200  # about 2.6 KB
    with pytest.raises(Exception) as err:
        svc.writer.create_document(title="Long", content=text)
    assert getattr(err.value, "status", "") == "too_large"
    res = svc.writer.create_document(title="Long", content=text, confirm_large=True)
    assert res["status"] == "created"
    with pytest.raises(PkmError, match="confirm_large"):
        svc.writer.rewrite_document(res["path"], text + "more\n", res["new_hash"])
    res = svc.writer.rewrite_document(res["path"], text + "more\n", res["new_hash"], confirm_large=True)
    assert res["status"] == "changed"
    res = svc.writer.edit_document(res["path"], "more", "more text", res["new_hash"], confirm_large=True)
    assert res["status"] == "changed"


def test_extract_embedded_images(svc, isolated_env):
    """fix_images with extract: proposal first, then files with unchanged bytes; follow-up is notation only.

    The answers carry no Base64 (diff with placeholders): each stays below 10 KB although the images
    have about 270 KB.
    """
    rel = _article(svc, side=150)
    m = Maintenance(svc)
    doc_id = svc.read(rel, content=False)["id"]
    m.mark([doc_id])
    before = {r.name: r.data() for r in images.find_images(svc.vault.load(rel).body or "")}
    proposal = svc.fix_images(target=rel, expected_hash=svc.read(rel)["hash"], extract=True, min_kb=4)
    assert proposal["status"] == "proposal" and len(proposal["files"]) == 3
    assert not (svc.cfg.root / "documents/_attachments").exists() or not any(
        (svc.cfg.root / "documents/_attachments").iterdir())
    res = svc.fix_images(target=rel, expected_hash=svc.read(rel)["hash"], extract=True, min_kb=4, apply=True)
    assert res["status"] == "changed" and len(res["extracted"]) == 3
    assert len(json.dumps(proposal)) < 10 * 1024 and len(json.dumps(res)) < 10 * 1024
    assert "base64" not in res["diff"] and "pkm-image:" in res["diff"]
    assert "PKM-Fix: images-extract" in git(isolated_env, "log", "-1", "--format=%B")
    body = svc.vault.load(rel).body or ""
    assert "data:image" not in body and (svc.cfg.root / rel).stat().st_size < 3 * 1024
    for info in res["extracted"]:
        assert (svc.cfg.root / info["path"]).read_bytes() == before[info["name"]]
    assert sorted(r.name for r in images.find_images(body)) == sorted(before)  # names stay for [img:<name>]
    item = next(c for c in m.pending()["changed"] if c["path"] == rel)
    assert item["image_notation_only"] is True and len(item["images_changed"]) == 3


def test_notation_only_with_linked_file():
    """A data URI replaced by a link to a file with the same bytes is a change of notation only."""
    data = big_png(8, 8)
    old = "## A\n![Fig](data:image/png;base64," + base64.b64encode(data).decode() + ")\n"
    new = "## A\n![Fig](fig.png)\n"
    limits = ImageConfig()
    same = imagefix.notation_only(old, new, limits, None, lambda ref: hashlib.sha256(data).hexdigest())
    other = imagefix.notation_only(old, new, limits, None, lambda ref: "0" * 64)
    assert same is True and other is False


def test_lint_image_hints(svc):
    """generic_alt_text and large_embedded_image are info findings; good alt texts are not reported."""
    big = base64.b64encode(big_png(110, 110)).decode()  # about 36 KB
    _png(svc, "documents/notes/pics/IMG_068.png")
    _png(svc, "documents/notes/pics/b.png", 5)
    _doc(svc, "documents/notes/note.md", "## A\n![Image](pics/IMG_068.png)\n\n![IMG_068.png](pics/b.png)\n\n"
         f"![Cistern with overflow pipe](data:image/png;base64,{big})\n")
    findings = [f for f in lint(svc)["findings"] if f.get("path") == "documents/notes/note.md"]
    generic = [f for f in findings if f["check"] == "generic_alt_text"]
    large = [f for f in findings if f["check"] == "large_embedded_image"]
    assert len(generic) == 2 and all(f["severity"] == "info" for f in generic)
    assert len(large) == 1 and large[0]["severity"] == "info" and "extract" in large[0]["message"]
    assert imagelint.is_generic_alt("Bild") and imagelint.is_generic_alt("IMG_020")
    assert not imagelint.is_generic_alt("Schaltplan Überlaufsensor")


def test_identical_image_stored_once(isolated_env, monkeypatch):
    """The same image twice in one document is stored once; another document gets its own copy (own folder)."""
    del isolated_env
    monkeypatch.setenv("PKM_INLINE_MAX_KB", "0")
    cfg = Config.from_env()
    init_vault(cfg)
    fsvc = Service(cfg)
    png = base64.b64encode(make_png(4, 4, text=False)).decode()
    first = fsvc.create_document(title="One", content="## A\n{{image:logo}}\n",
                                 images=[{"name": "logo", "alt": "Logo", "png_base64": png}])
    second = fsvc.create_document(title="Two", content="## A\n{{image:company-logo}}\n",
                                  images=[{"name": "company-logo", "alt": "Company logo", "png_base64": png}])
    assert first["images"][0]["path"].startswith(first["path"][:-3] + "_img/")
    assert second["images"][0]["path"].startswith(second["path"][:-3] + "_img/")
    raw = (cfg.root / first["path"]).read_text(encoding="utf-8")
    edit = fsvc.append_to_document(target=first["path"], text="{{image:logo-2}}",
                                   expected_hash=hashlib.sha256(raw.encode()).hexdigest(),
                                   images=[{"name": "logo-2", "alt": "Logo again", "png_base64": png}])
    assert edit["images"][0]["path"] == first["images"][0]["path"]
    assert len(list((cfg.root / (first["path"][:-3] + "_img")).iterdir())) == 1


def test_begin_maintenance_returns_wiki_language(svc, monkeypatch):
    """begin_maintenance names the wiki language (server instructions may not reach the model)."""
    assert maintrun.begin_maintenance(svc)["wiki_language"]["code"] == "en"
    monkeypatch.setenv("PKM_LANGUAGE", "de")
    info = maintrun.begin_maintenance(Service(Config.from_env()))["wiki_language"]
    assert info == {"code": "de", "name": "German", "summary_label": "Kurzfassung",
                    "sections": ["Inhalt", "Widersprüche / offene Fragen", "Siehe auch", "Belege"]}


def test_generated_wiki_files_in_wiki_language(svc, monkeypatch):
    """With PKM_LANGUAGE=de, _status.md, index.md and a new log.md have German headings."""
    from pkm.wikigen import build_index, build_status  # pylint: disable=import-outside-toplevel
    monkeypatch.setenv("PKM_LANGUAGE", "de")
    svc = Service(Config.from_env())
    _doc(svc, "documents/_inbox/neu.md", "## A\nText\n")
    build_status(svc, ["Soll das so bleiben?"])
    build_index(svc)
    status = (svc.cfg.root / "wiki/_status.md").read_text(encoding="utf-8")
    assert "## Noch nicht verarbeitet (1)" in status and "## Probleme (0)" in status and "## Fragen (1)" in status
    assert "– neu" in status and "Noch im Eingang, bereits verarbeitet" in status
    assert (svc.cfg.root / "wiki/index.md").read_text(encoding="utf-8").startswith("# Wiki-Index")
    (svc.cfg.root / "wiki/log.md").unlink()
    maintrun.append_log(svc, "ingest", "Test", "- nichts")
    assert (svc.cfg.root / "wiki/log.md").read_text(encoding="utf-8").startswith("# Pflegeprotokoll")


def test_tool_schemas_contain_new_parameters():
    """The schemas delivered to the client contain extract/min_kb and confirm_large (both servers)."""
    from pkm import maintenance_server, mcp_server  # pylint: disable=import-outside-toplevel
    expected = {"fix_images": {"extract", "min_kb"}, "create_document": {"confirm_large"},
                "rewrite_document": {"confirm_large"}, "append_to_document": {"confirm_large"},
                "edit_document": {"confirm_large"}}
    for mod in (mcp_server, maintenance_server):
        for tool in asyncio.run(mod.build_server("en").list_tools()):
            if tool.name in expected:
                schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", {})
                assert expected[tool.name] <= set(schema.get("properties", {})), (mod.__name__, tool.name)
                if tool.name == "fix_images":
                    assert "extract=true" in (tool.description or "")


def test_topic_with_page_by_tags_is_not_reported(svc):
    """A tag is covered by a topic page that carries it as its first tag; further tags do not count."""
    for n in range(3):
        _doc(svc, f"documents/ki/d{n}.md", "## A\nText\n", doc_id=f"d-20261106-1200-abc{'defg'[n]}")
        text = (svc.cfg.root / f"documents/ki/d{n}.md").read_text(encoding="utf-8")
        (svc.cfg.root / f"documents/ki/d{n}.md").write_text(
            text.replace("version: 1\n", "version: 1\ntags: [ki-agenten, sandboxing, harness, docker]\n"),
            encoding="utf-8")
    write(svc.cfg, "wiki/topics/ki-agenten-und-harnesse.md",
          "---\ntype: topic\ntitle: KI-Agenten und Harnesse\ntags: [ki-agenten, docker]\n---\n\n> **Summary:** S\n")
    write(svc.cfg, "wiki/topics/sandboxing-von-ki-agenten.md",
          "---\ntype: topic\ntitle: Sandboxing von KI-Agenten\naliases: [Sandboxing]\n---\n\n> **Summary:** S\n")
    topics = [f["message"] for f in lint(svc)["findings"] if f["check"] == "topic_without_page"]
    assert not any("ki-agenten" in t or "sandboxing" in t for t in topics), topics
    assert any("harness" in t for t in topics)
    assert any("'docker'" in t for t in topics)  # only a further tag of a page about another topic


def test_switch_to_attachments_is_reported_as_migration(svc):
    """State from before 0.3.0 (images as standalone entries, empty assets): one assets_migrated, then clean."""
    from pkm.state import load_state  # pylint: disable=import-outside-toplevel
    data = _png(svc, "documents/enc/images_x/IMG_001.png")
    _doc(svc, "documents/enc/encyclopedia.md", "## A\n![[images_x/IMG_001.png]]\n")
    m = Maintenance(svc)
    m.versions()
    m.mark([DOC_ID])
    state = load_state(svc.cfg)
    state["documents"][DOC_ID]["assets"] = {}
    digest = hashlib.sha256(data).hexdigest()
    state["documents"][f"sha:{digest}"] = {"path": "documents/enc/images_x/IMG_001.png", "wiki_pages": []}
    m.save_state(state)
    item = m.pending()["changed"][0]
    assert item["assets_migrated"] is True and item["image_notation_only"] is True and item["sections"] == []
    m.mark([DOC_ID])
    assert f"sha:{digest}" not in load_state(svc.cfg)["documents"]
    pend = m.pending()
    assert not any(pend[c] for c in ("new", "changed", "moved", "deleted"))


def test_extract_file_names(svc):
    """File names come from the alt text cut at a word boundary, with the document date; the proposal names them."""
    b64 = base64.b64encode(big_png(40, 40)).decode()
    alt = "GitHub Einstellungen Personal Access Token anlegen und Berechtigungen auswählen"
    rel = "documents/KI/artikel.md"
    write(svc.cfg, rel, f"---\ntitle: Artikel\ndate_markdown: 2026-11-04T10:00:00\nid: {DOC_ID}\nversion: 1\n---\n\n"
          f"## A\n![{alt}](data:image/png;base64,{b64})\n")
    Maintenance(svc).versions()
    proposal = svc.fix_images(target=rel, expected_hash=svc.read(rel)["hash"], extract=True, min_kb=4)
    res = svc.fix_images(target=rel, expected_hash=svc.read(rel)["hash"], extract=True, min_kb=4, apply=True)
    path = res["extracted"][0]["path"]
    assert proposal["files"] == [path]
    name = path.rsplit("/", 1)[1]
    assert name.endswith("_2026-11-04.png") and "YYYY" not in name
    stem = name[:-len("_2026-11-04.png")]
    assert len(stem) <= 60 and stem.startswith("github-einstellungen-personal-access-token-")
    assert stem.split("-")[-1] in alt.lower().split()  # ends with a whole word


def test_link_style(isolated_env, monkeypatch):
    """Image links are relative to the document by default; PKM_LINK_STYLE=absolute writes vault paths.

    read_image finds images linked either way.
    """
    del isolated_env
    monkeypatch.setenv("PKM_INLINE_MAX_KB", "0")
    cfg = Config.from_env()
    init_vault(cfg)
    assert cfg.images.link_style == "relative"
    png = base64.b64encode(make_png(4, 4, text=False)).decode()
    svc = Service(cfg)
    res = svc.create_document(title="A", content="{{image:pic}}",
                              images=[{"name": "pic", "alt": "Pic", "png_base64": png}])
    assert "](./a_" in (cfg.root / res["path"]).read_text(encoding="utf-8")
    monkeypatch.setenv("PKM_LINK_STYLE", "absolute")
    svc = Service(Config.from_env())
    png2 = base64.b64encode(make_png(5, 5, text=False)).decode()
    res = svc.create_document(title="B", content="{{image:pic}}",
                              images=[{"name": "pic", "alt": "Pic", "png_base64": png2}])
    assert f"]({res['images'][0]['path']} " in (cfg.root / res["path"]).read_text(encoding="utf-8")
    assert svc.read_image(res["path"], "pic")["data"] == base64.b64decode(png2)
    monkeypatch.setenv("PKM_LINK_STYLE", "elsewhere")
    with pytest.raises(PkmError):
        Config.from_env()


def test_moved_image_files_are_notation_only(svc):
    """Image files moved by hand into <doc>_img/ with only the links changed: image_notation_only, images_moved."""
    for n in range(3):
        _png(svc, f"documents/_attachments/bild-{n}.png", 3 + n)
    body = "## A\n" + "".join(f"![Bild {n}](../_attachments/bild-{n}.png)\n\n" for n in range(3))
    _doc(svc, "documents/KI/sandbox.md", body)
    m = Maintenance(svc)
    m.versions()
    m.mark([DOC_ID])
    for n in range(3):
        (svc.cfg.root / "documents/KI/sandbox_img").mkdir(exist_ok=True)
        (svc.cfg.root / f"documents/_attachments/bild-{n}.png").rename(
            svc.cfg.root / f"documents/KI/sandbox_img/bild-{n}.png")
    path = svc.cfg.root / "documents/KI/sandbox.md"
    path.write_text(path.read_text(encoding="utf-8").replace("../_attachments/", "./sandbox_img/"), encoding="utf-8")
    m.versions()
    item = next(i for i in m.pending()["changed"] if i["path"] == "documents/KI/sandbox.md")
    assert item["image_notation_only"] is True
    assert item["images_changed"] == []
    assert item["images_moved"] == [{"from": f"documents/_attachments/bild-{n}.png",
                                     "to": f"documents/KI/sandbox_img/bild-{n}.png"} for n in range(3)]


# Main ************************************************************************
