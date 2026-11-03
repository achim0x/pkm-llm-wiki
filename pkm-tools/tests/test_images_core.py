"""Tests: Bildmodul (Spezifikation 4.9) – Erkennen, Platzhalter, SVG-Bereinigung, PNG-Prüfung.

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

import base64
import struct
import zlib
from pathlib import Path

import pytest

from pkm import images
from pkm.config import ImageConfig
from pkm.errors import PkmError

# Variables *******************************************************************

SVG = ('<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
       '<!-- Kommentar --><metadata>x</metadata><rect width="10" height="10" fill="#f00"/></svg>')

# Classes *********************************************************************

# Functions *******************************************************************


def make_png(width=2, height=2, text=True):
    """Kleines gültiges PNG erzeugen.

    Args:
        width: Breite.
        height: Höhe.
        text: Mit tEXt-Block.

    Returns:
        PNG-Bytes.
    """
    def chunk(kind, data):
        """PNG-Block bilden.

        Args:
            kind: Blocktyp.
            data: Inhalt.

        Returns:
            Bytes des Blocks.
        """
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\x00\x00\x00" * width for _ in range(height))
    parts = [images.PNG_SIGNATURE, chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))]
    if text:
        parts.append(chunk(b"tEXt", b"Comment\x00geheim"))
    parts += [chunk(b"IDAT", zlib.compress(raw)), chunk(b"IEND", b"")]
    return b"".join(parts)


def limits(tmp_path=None, **kw):
    """Bildgrenzen für Tests.

    Args:
        tmp_path: Importordner.
        **kw: Abweichende Werte.

    Returns:
        ``ImageConfig``.
    """
    return ImageConfig(import_dir=tmp_path, **kw)


def test_sanitize_svg_minifies_and_keeps_shapes():
    """Kommentare, Metadaten und XML-Kopf verschwinden, Formen bleiben."""
    out = images.sanitize_svg(SVG, 200)
    assert out.startswith("<svg") and "<rect" in out and "Kommentar" not in out and "metadata" not in out


@pytest.mark.parametrize("bad", [
    '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><rect/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect onclick="x()"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><b>x</b></foreignObject></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
    '<use xlink:href="http://evil/x.svg#a"/><a href="https://x">t</a></svg>',
])
def test_sanitize_svg_removes_unsafe_parts(bad):
    """Script, Ereignis-Attribute, foreignObject und externe Verweise werden entfernt."""
    out = images.sanitize_svg(bad, 200)
    assert not images.svg_problems(out) and "alert" not in out and "evil" not in out


def test_sanitize_svg_rejects_xxe_raster_and_size():
    """DOCTYPE/Entities, eingebettete Rastergrafiken und zu große SVG werden abgelehnt."""
    xxe = '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg">&x;</svg>'
    raster = '<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,AAAA"/></svg>'
    big = '<svg xmlns="http://www.w3.org/2000/svg">' + "<rect/>" * 400 + "</svg>"
    for svg, status in ((xxe, "invalid_image"), (raster, "svg_too_complex"), (big, "svg_too_complex"),
                        ("kein xml", "invalid_image")):
        with pytest.raises(PkmError) as e:
            images.sanitize_svg(svg, 1)
        assert e.value.status == status


def test_svg_data_uri_is_markdown_safe():
    """Die URL-Kodierung bricht keine Markdown-Syntax und lässt sich zurücklesen."""
    svg = images.sanitize_svg('<svg xmlns="http://www.w3.org/2000/svg"><text x="1">a (b) [c] "d"</text></svg>', 200)
    uri = images.svg_data_uri(svg)
    assert not any(ch in uri for ch in ' ()[]"#<>')
    line = f'![Diagramm]({uri} "pkm:diagramm")'
    refs = images.find_images(line)
    assert len(refs) == 1
    ref = refs[0]
    assert ref.name == "diagramm" and ref.inline and ref.fmt == "svg"
    assert b"a (b) [c]" in ref.data()


def test_clean_png_strips_text_and_checks_size():
    """PNG: Textblöcke entfernt, Signatur und Größe geprüft."""
    png = make_png()
    cleaned = images.clean_png(png)
    assert b"geheim" not in cleaned and cleaned.startswith(images.PNG_SIGNATURE)
    for bad in (b"GIF89a", png[:30], make_png(9000, 1, text=False)):
        with pytest.raises(PkmError) as e:
            images.clean_png(bad)
        assert e.value.status == "invalid_image"


def test_find_images_names_and_kinds():
    """Namen aus pkm:, sonst aus Alternativtext oder bild-<n>; Dateien und Obsidian-Einbettungen."""
    b64 = base64.b64encode(make_png()).decode()
    text = (f'![Display](data:image/png;base64,{b64})\n'
            f'![Foto Einstieg](../_attachments/foto.png "pkm:foto-einstieg")\n'
            '![[Pasted image 2026.png]]\n'
            '![extern](https://example.org/x.png)\n')
    refs = images.find_images(text)
    assert [(r.name, r.inline, r.named) for r in refs] == [
        ("display", True, False), ("foto-einstieg", False, True), ("bild-3", False, False)]
    assert images.link_target(refs[1], "documents/_inbox/notiz.md") == "documents/_attachments/foto.png"


def test_placeholders_roundtrip_byte_exact():
    """Platzhalter ersetzen Base64; die Rückübersetzung ist byte-genau, Unbekanntes wird abgelehnt."""
    b64 = base64.b64encode(make_png()).decode()
    text = f"Text\n![Display|300](data:image/png;base64,{b64})\nmehr\n"
    shown = images.to_placeholders(text)
    assert b64 not in shown and "pkm-image:display" in shown and "|300" in shown
    refs = images.find_images(text)
    assert images.restore_placeholders(shown, refs) == text
    with pytest.raises(PkmError) as e:
        images.restore_placeholders(shown.replace("pkm-image:display", "pkm-image:fremd"), refs)
    assert e.value.status == "unknown_image"


def test_prepare_image_modes_and_sources(tmp_path):
    """auto bettet kleine Bilder ein, große werden Datei; inline zu groß wird abgelehnt; scratch immer inline."""
    small = images.prepare_image({"name": "a", "alt": "A", "svg": SVG}, limits())
    assert small.mode == "inline" and small.fmt == "svg"
    png = make_png(200, 200, text=False)
    b64 = base64.b64encode(png).decode()
    tiny = limits(inline_max_kb=0)
    assert images.prepare_image({"name": "b", "alt": "B", "png_base64": b64}, tiny).mode == "file"
    assert images.prepare_image({"name": "b", "alt": "B", "png_base64": b64}, tiny, scratch=True).mode == "inline"
    with pytest.raises(PkmError) as e:
        images.prepare_image({"name": "b", "alt": "B", "png_base64": b64, "mode": "inline"}, tiny)
    assert e.value.status == "too_large_for_inline"
    (tmp_path / "foto.png").write_bytes(png)
    imported = images.prepare_image({"name": "c", "alt": "C", "import_path": "foto.png"}, limits(tmp_path))
    assert imported.fmt == "png" and imported.data == png
    outside = Path(tmp_path).parent / "x.png"
    outside.write_bytes(png)
    cases = [({"name": "c", "alt": "C", "import_path": str(outside)}, "forbidden"),
             ({"name": "C!", "alt": "C", "svg": SVG}, "invalid_argument"),
             ({"name": "c", "alt": "", "svg": SVG}, "invalid_argument"),
             ({"name": "c", "alt": "C", "svg": SVG, "png_base64": b64}, "invalid_argument"),
             ({"name": "c", "alt": "C", "png_base64": "x" * 2000}, "too_large")]
    for spec, status in cases:
        with pytest.raises(PkmError) as e:
            images.prepare_image(spec, limits(tmp_path, param_max_kb=1))
        assert e.value.status == status, spec


def test_new_image_placeholders():
    """{{image:<name>}} muss zu den Bildern passen."""
    img = images.prepare_image({"name": "a", "alt": "A", "svg": SVG}, limits())
    images.check_new_names("x {{image:a}}", [img], [])
    for text, status in (("x", "invalid_argument"), ("{{image:a}} {{image:b}}", "unknown_image")):
        with pytest.raises(PkmError) as e:
            images.check_new_names(text, [img], [])
        assert e.value.status == status
    assert images.insert_new_images("x {{image:a}}", {"a": "BILD"}) == "x BILD"

# Main ************************************************************************
