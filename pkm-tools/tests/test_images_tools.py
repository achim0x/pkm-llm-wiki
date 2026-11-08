"""Tests: images in the tools (specification 4.9, 7.2, 7.3) – creating, changing, reading, read_image.

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
import base64

import pytest

from pkm import mcp_server
from pkm.config import Config
from pkm.errors import PkmError
from pkm.service import Service

from .conftest import git
from .test_images_core import SVG, make_png

# Variables *******************************************************************

PNG_B64 = base64.b64encode(make_png(text=False)).decode()

# Classes *********************************************************************

# Functions *******************************************************************


def _svg_doc(svc):
    """Create a document with an embedded SVG.

    Args:
        svc: Service.

    Returns:
        Return value of ``create_document``.
    """
    return svc.create_document(title="Schaltplan", content="## Aufbau\nText\n{{image:plan}}\n\n## Rest\nmehr\n",
                               images=[{"name": "plan", "alt": "Schaltplan Überlauf", "svg": SVG}])


def test_create_inline_svg_and_read_placeholders(svc, isolated_env):
    """A small SVG is embedded; read shows a placeholder and the image list."""
    res = _svg_doc(svc)
    assert res["images"][0]["mode"] == "inline"
    raw = (svc.cfg.root / res["path"]).read_text(encoding="utf-8")
    assert 'data:image/svg+xml,' in raw and '"pkm:plan")' in raw
    doc = svc.read(res["path"])
    assert "data:image" not in doc["content"] and "pkm-image:plan" in doc["content"]
    assert doc["images"][0]["name"] == "plan" and doc["images"][0]["section"] == "Aufbau"
    assert svc.read(res["path"], section="Rest")["images"] == []
    assert git(isolated_env, "show", "--name-only", "--format=", "HEAD").split() == [res["path"]]


def test_large_png_becomes_file_in_same_commit(isolated_env, monkeypatch):
    """Above the limit the PNG becomes a file in _attachments, in the same commit as the document."""
    monkeypatch.setenv("PKM_INLINE_MAX_KB", "0")
    from pkm.vaultinit import init_vault  # pylint: disable=import-outside-toplevel
    cfg = Config.from_env()
    init_vault(cfg)
    svc = Service(cfg)
    res = svc.create_document(title="Foto", content="{{image:foto}}",
                              images=[{"name": "foto", "alt": "Foto Einstieg", "png_base64": PNG_B64}])
    path = res["images"][0]["path"]
    assert path.startswith("documents/_attachments/foto_") and path.endswith(".png")
    assert (cfg.root / path).read_bytes() == base64.b64decode(PNG_B64)
    raw = (cfg.root / res["path"]).read_text(encoding="utf-8")
    assert "](documents/_attachments/foto_" in raw  # link style absolute (like Obsidian, PKM_LINK_STYLE)
    assert sorted(git(isolated_env, "show", "--name-only", "--format=", "HEAD").split()) == sorted([res["path"], path])
    data = svc.read_image(res["path"], "foto")
    assert data["mode"] == "file" and data["data"] == base64.b64decode(PNG_B64)
    assert svc.read_image(path)["format"] == "png"
    note = svc.create_document(title="Notiz", content="{{image:foto}}", area="scratch",
                               images=[{"name": "foto", "alt": "Foto", "png_base64": PNG_B64, "mode": "file"}])
    assert note["images"][0]["mode"] == "inline"


def test_rewrite_keeps_images_byte_exact_and_guards_removal(svc):
    """rewrite_document with placeholders keeps the image; removing needs confirmation."""
    res = _svg_doc(svc)
    before = (svc.cfg.root / res["path"]).read_text(encoding="utf-8")
    image_line = next(ln for ln in before.splitlines() if ln.startswith("![Schaltplan"))
    doc = svc.read(res["path"])
    new = doc["content"].replace("Text", "Neuer Text")
    out = svc.rewrite_document(target=res["path"], content=new, expected_hash=doc["hash"])
    after = (svc.cfg.root / res["path"]).read_text(encoding="utf-8")
    assert image_line in after and "Neuer Text" in after
    without = "\n".join(ln for ln in svc.read(res["path"])["content"].splitlines() if "pkm-image" not in ln)
    with pytest.raises(PkmError) as e:
        svc.rewrite_document(target=res["path"], content=without, expected_hash=out["new_hash"])
    assert e.value.status == "large_shortening" and e.value.data["removed_images"] == ["plan"]
    with pytest.raises(PkmError) as e:
        svc.rewrite_document(target=res["path"], content=doc["content"].replace("pkm-image:plan", "pkm-image:x"),
                             expected_hash=out["new_hash"], confirm_shortening=True)
    assert e.value.status == "unknown_image"


def test_edit_and_add_image(svc):
    """edit_document works on the text with placeholders; add_image inserts at the end of the section."""
    res = _svg_doc(svc)
    h = svc.read(res["path"])["hash"]
    out = svc.edit_document(target=res["path"], old="Text", new="Text geändert", expected_hash=h)
    assert out["status"] == "changed"
    line = next(ln for ln in svc.read(res["path"])["content"].splitlines() if "pkm-image:plan" in ln)
    with pytest.raises(PkmError) as e:
        svc.edit_document(target=res["path"], old=line, new="", expected_hash=out["new_hash"])
    assert e.value.status == "large_shortening"
    added = svc.add_image(target=res["path"], expected_hash=out["new_hash"], section="Rest", caption="Abb. 2",
                          image={"name": "display", "alt": "Display", "png_base64": PNG_B64})
    content = svc.read(res["path"])["content"]
    assert added["version"] == 3 and content.index("pkm-image:display") > content.index("## Rest")
    assert "Abb. 2" in content
    with pytest.raises(PkmError) as e:
        svc.add_image(target=res["path"], expected_hash=added["new_hash"],
                      image={"name": "plan", "alt": "Doppelt", "svg": SVG})
    assert e.value.status == "invalid_argument"


def test_read_image_svg_text_and_raster_flag(svc):
    """read_image returns SVG as text; rasterizing only with PKM_SVG_RASTER."""
    res = _svg_doc(svc)
    img = svc.read_image(res["path"], "plan")
    assert img["svg"].startswith("<svg") and img["format"] == "svg" and "data" not in img
    with pytest.raises(PkmError) as e:
        svc.read_image(res["path"], "plan", as_="image")
    assert e.value.status == "invalid_argument"
    with pytest.raises(PkmError) as e:
        svc.read_image(res["path"], "fehlt")
    assert e.value.status == "unknown_image"


@pytest.mark.usefixtures("cfg")
def test_mcp_read_image_returns_image_content():
    """Via MCP a PNG comes as image content."""
    mcp_server.reset_service()
    svc = mcp_server.get_service()
    res = svc.create_document(title="Display", content="{{image:display}}",
                              images=[{"name": "display", "alt": "Display", "png_base64": PNG_B64}])
    server = mcp_server.build_server()
    out = asyncio.run(server.call_tool("read_image", {"target": res["path"], "image": "display"}))
    blocks = out[0] if isinstance(out, tuple) else getattr(out, "content", out)
    kinds = [getattr(b, "type", None) for b in blocks]
    assert kinds == ["text", "image"]
    mcp_server.reset_service()

# Main ************************************************************************
