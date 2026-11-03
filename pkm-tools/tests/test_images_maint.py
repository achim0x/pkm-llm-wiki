"""Tests: Bilder in der Pflege (Spezifikation 4.9, 8) – zugehörige und eigenständige Bilder, Assets,
geänderte Bilddateien, verwaiste Anhänge, Lint, Doctor, Suche.

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
from urllib.parse import quote

import pytest

from pkm import images
from pkm.config import Config
from pkm.doctor import doctor
from pkm.lint import lint
from pkm.maint import Maintenance
from pkm.service import Service
from pkm.vaultinit import init_vault
from pkm.wikigen import build_status

from .conftest import git, write
from .test_images_core import make_png

# Variables *******************************************************************

PNG = make_png(text=False)
PNG_B64 = base64.b64encode(PNG).decode()

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="fsvc")
def fixture_fsvc(isolated_env, monkeypatch):
    """Dienst, bei dem jedes Bild als Datei abgelegt wird.

    Args:
        isolated_env: Isolierte Umgebung.
        monkeypatch: pytest-Fixture.

    Returns:
        Der Dienst.
    """
    del isolated_env
    monkeypatch.setenv("PKM_INLINE_MAX_KB", "0")
    cfg = Config.from_env()
    init_vault(cfg)
    return Service(cfg)


def _checks(svc, path=None):
    """Lint-Prüfnamen (optional nur für einen Pfad).

    Args:
        svc: Dienst.
        path: Pfad.

    Returns:
        Liste der Prüfnamen.
    """
    return [f["check"] for f in lint(svc)["findings"] if path is None or f.get("path") == path]


def test_referenced_image_is_not_a_document(fsvc):
    """Zugehörige Bilddateien sind kein eigenes Dokument; eigenständige schon."""
    res = fsvc.create_document(title="Foto", content="## Aufbau\n{{image:foto}}\n",
                               images=[{"name": "foto", "alt": "Foto", "png_base64": PNG_B64}])
    write(fsvc.cfg, "documents/_inbox/allein.png", "")
    (fsvc.cfg.root / "documents/_inbox/allein.png").write_bytes(make_png(3, 3, text=False))
    m = Maintenance(fsvc)
    m.versions()
    new = [d["path"] for d in m.pending()["new"]]
    assert res["path"] in new and "documents/_inbox/allein.png" in new
    assert res["images"][0]["path"] not in new


def test_changed_image_file_versions_document(fsvc, isolated_env):
    """Ändert sich eine verlinkte Bilddatei, bekommt das Dokument eine neue Version im selben Commit."""
    res = fsvc.create_document(title="Foto", content="## Aufbau\n{{image:foto}}\n",
                               images=[{"name": "foto", "alt": "Foto", "png_base64": PNG_B64}])
    image = res["images"][0]["path"]
    m = Maintenance(fsvc)
    m.mark([res["id"]])
    assert m.pending()["counts"]["changed"] == 0
    (fsvc.cfg.root / image).write_bytes(make_png(4, 4, text=False))
    pend = m.pending()
    assert len(pend["changed"]) == 1
    item = pend["changed"][0]
    assert item["assets_changed"] == [image] and item["sections"] == [{"key": "Aufbau", "change": "changed"}]
    out = m.versions()
    entry = next(c for c in out["committed"] if c.get("image") == image)
    assert entry["version"] == 2
    files = git(isolated_env, "show", "--name-only", "--format=", "HEAD").split()
    assert sorted(files) == sorted([res["path"], image])
    assert "PKM-Source: user" in git(isolated_env, "log", "-1", "--format=%B")


def test_orphaned_attachment_reported(fsvc):
    """Wird der letzte Verweis entfernt, ist die Bilddatei verwaist: Status und Lint melden sie."""
    res = fsvc.create_document(title="Foto", content="Text\n\n{{image:foto}}\n",
                               images=[{"name": "foto", "alt": "Foto", "png_base64": PNG_B64}])
    image = res["images"][0]["path"]
    m = Maintenance(fsvc)
    m.mark([res["id"]])
    line = next(ln for ln in fsvc.read(res["path"])["content"].splitlines() if ln.startswith("![Foto]"))
    fsvc.edit_document(target=res["path"], old=line, new="", expected_hash=fsvc.read(res["path"])["hash"],
                       confirm_shortening=True)
    pend = m.pending()
    assert pend["orphaned_attachments"] == [image] and image not in [d["path"] for d in pend["new"]]
    build_status(fsvc)
    assert "Verwaiste Anhänge (1)" in (fsvc.cfg.root / "wiki/_status.md").read_text(encoding="utf-8")
    assert "orphaned_attachment" in _checks(fsvc, image)


def test_lint_image_checks(svc):
    """Unsicheres SVG, fehlender Alternativtext, doppelte Namen; bestehende Base64-PNG ohne Hinweis."""
    bad_svg = quote('<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>', safe="")
    text = (f'![Plan](data:image/svg+xml,{bad_svg} "pkm:plan")\n\n'
            f'![](data:image/png;base64,{PNG_B64} "pkm:a")\n\n![x](data:image/png;base64,{PNG_B64} "pkm:a")\n\n'
            f'![](data:image/png;base64,{PNG_B64})\n')
    write(svc.cfg, "documents/bilder.md", text)
    checks = _checks(svc, "documents/bilder.md")
    assert "svg_unsafe" in checks and "image_duplicate_name" in checks
    assert checks.count("image_without_alt") == 1


def test_image_citation_checked(svc):
    """Ein Beleg [img:<name>] braucht das Bild im belegten Abschnitt."""
    doc = svc.create_document(title="Plan", content="## Aufbau\n{{image:plan}}\n",
                              images=[{"name": "plan", "alt": "Plan", "png_base64": PNG_B64}])
    sha = next(s["sha"] for s in svc.read(doc["path"])["sections"] if s["key"] == "Aufbau")
    base = f"[[{doc['path'][:-3]}#Aufbau]] · „[img:{{}}]“ · id:{doc['id']} · v:1 · sha:{sha}"
    page = "wiki/topics/plan.md"
    for name, expected in (("plan", False), ("fehlt", True)):
        text = f"---\ntype: topic\n---\n## Inhalt\nDer Plan zeigt X.[^b1]\n\n[^b1]: {base.format(name)}\n"
        write(svc.cfg, page, text)
        checks = _checks(svc, page)
        assert ("citation_image_missing" in checks) is expected and "quote_not_found" not in checks


def test_doctor_import_dir_and_search_alt_only(svc, cfg, monkeypatch):
    """doctor prüft PKM_IMPORT_DIR; die Suche kennt nur den Alternativtext."""
    svc.create_document(title="Notiz", content="{{image:plan}}",
                        images=[{"name": "plan", "alt": "Zisternenpumpe Schema", "png_base64": PNG_B64}])
    assert svc.search("Zisternenpumpe", scope="documents")["results"]
    assert not svc.search(PNG_B64[20:40], scope="documents")["results"]
    monkeypatch.setenv("PKM_IMPORT_DIR", str(cfg.root / "import"))
    bad = Service(Config.from_env())
    check = next(c for c in doctor(bad)["checks"] if c["check"] == "import_dir")
    assert not check["ok"] and check["severity"] == "error"
    assert images.strip_images("a ![Alt](x.png) b") == "a Alt b"

# Main ************************************************************************
