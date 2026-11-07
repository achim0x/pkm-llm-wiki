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

import base64
import hashlib
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
    """Service that stores image files next to the document (PKM_IMAGE_FOLDER=document) and every image as a file.

    Args:
        isolated_env: Isolated environment.
        monkeypatch: pytest fixture.

    Returns:
        The service.
    """
    del isolated_env
    monkeypatch.setenv("PKM_INLINE_MAX_KB", "0")
    monkeypatch.setenv("PKM_IMAGE_FOLDER", "document")
    cfg = Config.from_env()
    init_vault(cfg)
    return Service(cfg)


def test_image_folder_next_to_document(dsvc):
    """With PKM_IMAGE_FOLDER=document new image files go to <folder>/<document name>_img/."""
    png = base64.b64encode(make_png(4, 4, text=False)).decode()
    res = dsvc.create_document(title="Photo", content="## A\n{{image:photo}}\n",
                               images=[{"name": "photo", "alt": "Photo", "png_base64": png}])
    stem = res["path"].rsplit("/", 1)[1][:-3]
    assert res["images"][0]["path"].startswith(f"documents/_inbox/{stem}_img/photo")
    pend = Maintenance(dsvc).pending()
    assert [d["path"] for d in pend["new"]] == [res["path"]] and pend["new"][0]["images"] == [res["images"][0]["path"]]


def test_invalid_image_folder(isolated_env, monkeypatch):
    """Unknown values of PKM_IMAGE_FOLDER are a configuration error."""
    del isolated_env
    monkeypatch.setenv("PKM_IMAGE_FOLDER", "elsewhere")
    with pytest.raises(Exception) as err:
        Config.from_env()
    assert "PKM_IMAGE_FOLDER" in str(err.value)

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
    """fix_images with extract: proposal first, then files with unchanged bytes; follow-up is notation only."""
    rel = _article(svc)
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
    """The same image in two documents is stored once; the second link points to the same file."""
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
    assert first["images"][0]["path"] == second["images"][0]["path"]
    assert len(list((cfg.root / "documents/_attachments").iterdir())) == 1


def test_begin_maintenance_returns_wiki_language(svc, monkeypatch):
    """begin_maintenance names the wiki language (server instructions may not reach the model)."""
    assert maintrun.begin_maintenance(svc)["wiki_language"]["code"] == "en"
    monkeypatch.setenv("PKM_LANGUAGE", "de")
    info = maintrun.begin_maintenance(Service(Config.from_env()))["wiki_language"]
    assert info == {"code": "de", "name": "German", "summary_label": "Kurzfassung",
                    "sections": ["Inhalt", "Widersprüche / offene Fragen", "Siehe auch", "Belege"]}


# Main ************************************************************************
