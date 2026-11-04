"""Tests: JPEG import and import folder ``pkm_img_import/`` in the vault (specification 4.9).

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

import pytest

from pkm import images
from pkm.config import IMPORT_FOLDER
from pkm.doctor import doctor
from pkm.errors import PkmError
from pkm.lint import lint
from pkm.maint import Maintenance

from .conftest import git
from .test_images_core import make_png

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


def _segment(marker, payload):
    """Build a JPEG segment.

    Args:
        marker: Marker byte.
        payload: Inhalt.

    Returns:
        Bytes of the segment.
    """
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def make_jpeg(width=4, height=3, orientation=6):
    """Create a structurally valid JPEG with EXIF (orientation, GPS placeholder) and a comment.

    Args:
        width: Width.
        height: Height.
        orientation: EXIF orientation or ``None``.

    Returns:
        JPEG-Bytes.
    """
    entries = [(0x8825, 4, 1, 0)]  # GPS IFD pointer as an example of data to remove
    if orientation:
        entries.insert(0, (0x0112, 3, 1, orientation << 16))
    ifd = struct.pack(">H", len(entries)) + b"".join(struct.pack(">HHII", *e) for e in entries) + struct.pack(">I", 0)
    exif = b"Exif\x00\x00" + b"MM\x00\x2a" + struct.pack(">I", 8) + ifd + b"GPS-geheim"
    sof = struct.pack(">BHHB", 8, height, width, 1) + b"\x01\x11\x00"
    return (b"\xff\xd8" + _segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
            + _segment(0xE1, exif) + _segment(0xFE, b"Kommentar geheim") + _segment(0xC0, sof)
            + _segment(0xDA, b"\x01\x01\x00\x00\x3f\x00") + b"\x12\x34\x56" + b"\xff\xd9")


def test_clean_jpeg_strips_metadata_keeps_orientation():
    """EXIF, GPS and comments disappear; the orientation stays as a minimal EXIF block."""
    cleaned = images.clean_jpeg(make_jpeg())
    assert b"geheim" not in cleaned and cleaned.startswith(b"\xff\xd8\xff\xe0")
    start = cleaned.index(b"Exif\x00\x00") + 6
    assert images._exif_orientation(cleaned[start:]) == 6  # pylint: disable=protected-access
    assert b"Exif" not in images.clean_jpeg(make_jpeg(orientation=None))
    assert cleaned.endswith(b"\x12\x34\x56\xff\xd9")


def test_clean_jpeg_rejects_invalid():
    """Invalid structure and too large images are rejected."""
    for bad in (b"\x89PNG", make_jpeg()[:40], make_jpeg(9000, 10)):
        with pytest.raises(PkmError) as e:
            images.clean_jpeg(bad)
        assert e.value.status == "invalid_image"


def test_init_creates_ignored_import_folder(svc, cfg):
    """pkm init creates pkm_img_import/, adds it to .gitignore; doctor is satisfied."""
    assert cfg.images.import_dir == cfg.root / IMPORT_FOLDER and (cfg.root / IMPORT_FOLDER).is_dir()
    assert f"{IMPORT_FOLDER}/" in (cfg.root / ".gitignore").read_text(encoding="utf-8")
    checks = {c["check"]: c for c in doctor(svc)["checks"]}
    assert checks["import_dir"]["ok"] and checks["import_ignored"]["ok"]


def test_import_folder_is_ignored_by_maintenance(svc, cfg, isolated_env):
    """Files in the import folder are no documents, not in Git, not in lint and not in the search."""
    (cfg.root / IMPORT_FOLDER / "foto.png").write_bytes(make_png(text=False))
    (cfg.root / IMPORT_FOLDER / "notiz.md").write_text("# Notiz\nGeheimwort\n", encoding="utf-8", newline="\n")
    m = Maintenance(svc)
    m.versions()
    assert not any(IMPORT_FOLDER in d["path"] for d in m.pending()["new"])
    assert not [f for f in lint(svc)["findings"] if IMPORT_FOLDER in (f.get("path") or "")]
    assert not svc.search("Geheimwort", scope="all")["results"]
    assert IMPORT_FOLDER not in git(isolated_env, "status", "--porcelain")


def test_create_document_imports_jpeg_from_vault_folder(svc, cfg, isolated_env):
    """JPEG from pkm_img_import/ is imported (copied, cleaned), small ones embedded, large ones as a .jpg file."""
    (cfg.root / IMPORT_FOLDER / "foto.jpg").write_bytes(make_jpeg())
    res = svc.create_document(title="Foto", content="{{image:foto}}",
                              images=[{"name": "foto", "alt": "Foto", "import_path": "foto.jpg"}])
    raw = (cfg.root / res["path"]).read_text(encoding="utf-8")
    assert "data:image/jpeg;base64," in raw and res["images"][0]["format"] == "jpg"
    uri = raw[raw.index("data:image/jpeg;base64,") + len("data:image/jpeg;base64,"):].split(" ", 1)[0]
    assert b"geheim" not in base64.b64decode(uri)
    assert (cfg.root / IMPORT_FOLDER / "foto.jpg").exists()
    big = svc.create_document(title="Foto groß", content="{{image:foto}}",
                              images=[{"name": "foto", "alt": "Foto", "import_path": "foto.jpg", "mode": "file"}])
    path = big["images"][0]["path"]
    assert path.endswith(".jpg") and path in git(isolated_env, "show", "--name-only", "--format=", "HEAD")
    assert svc.read_image(big["path"], "foto")["format"] == "jpg"
    with pytest.raises(PkmError) as e:
        svc.create_document(title="X", content="{{image:x}}",
                            images=[{"name": "x", "alt": "X", "import_path": "../documents/x.png"}])
    assert e.value.status in ("forbidden", "not_found")

# Main ************************************************************************
