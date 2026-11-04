"""Tests: Prüfung und Korrektur von Bild-Data-URIs bei der Übernahme (Spezifikation 0.24, 4.9).

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
import json
from urllib.parse import quote

import pytest

from pkm import images, maintrun
from pkm.cli import main
from pkm.config import ImageConfig
from pkm.errors import PkmError
from pkm.imagefix import fix_text, image_issues, notation_only
from pkm.lint import lint
from pkm.maint import Maintenance

from .conftest import git, write
from .test_images_core import make_png
from .test_images_import import make_jpeg

# Variables *******************************************************************

LIMITS = ImageConfig()
SVG_RAW = ("<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'>"
           "<rect fill='#f00' width='10' height='10'/></svg>")
PRACTICE = ("# Notiz\n\n## Aufbau\nDer Aufbau: ![Plan][plan] siehe oben.\n\n"
            f"[plan]: <data:image/svg+xml;utf8,{SVG_RAW}>\n")
PNG_B64 = base64.b64encode(make_png(text=False)).decode()
GOOD_SVG = images.svg_data_uri(images.sanitize_svg(SVG_RAW, 200))

# Classes *********************************************************************

# Functions *******************************************************************


def _problems(text, **kw):
    """Befundcodes je Bild.

    Args:
        text: Markdown.
        **kw: Optionen für ``image_issues``.

    Returns:
        Bildname → Befunde.
    """
    return {i["ref"]: i["problems"] for i in image_issues(text, LIMITS, **kw)}


# Befunde *********************************************************************
def test_practice_vector():
    """Referenzstil mit ;utf8 und nicht kodierten Zeichen (Fall aus der Praxis)."""
    probs = _problems(PRACTICE)["plan"]
    assert {"reference_style", "svg_parameters", "unencoded_chars", "not_own_line", "missing_name"} <= set(probs)


@pytest.mark.parametrize("text, code", [
    (f'<img src="data:image/png;base64,{PNG_B64}" alt="X">\n', "html_img"),
    (f'![X](<data:image/png;base64,{PNG_B64}> "pkm:x")\n', "angle_brackets"),
    (f'![X]({GOOD_SVG} "pkm:x") Text\n', "not_own_line"),
    (f'![X](data:image/svg+xml;base64,{base64.b64encode(SVG_RAW.encode()).decode()} "pkm:x")\n', "svg_base64"),
    (f'![X](data:image/png;base64,{PNG_B64[:10]}\n{PNG_B64[10:]})\n', "base64_whitespace"),
    (f'![X](data:image/png;base64,{base64.b64encode(make_jpeg()).decode()})\n', "media_type_mismatch"),
    (f'![X]({GOOD_SVG})\n', "missing_name"),
    (f'![X]({GOOD_SVG} "pkm:Ungültig!")\n', "invalid_name"),
    (f'![X]({GOOD_SVG} "pkm:x")\n\n![Y]({GOOD_SVG} "pkm:x")\n', "duplicate_name"),
    (f'![]({GOOD_SVG} "pkm:x")\n', "missing_alt"),
    ('![X](data:image/svg+xml,' + quote("<svg xmlns='http://www.w3.org/2000/svg'><script>a</script></svg>", safe="")
     + ' "pkm:x")\n', "svg_unsafe"),
    (f'![X](data:image/gif;base64,{base64.b64encode(b"GIF89a" + bytes(20)).decode()} "pkm:x")\n', "unsupported_type"),
    ('![X](data:image/png;base64,AAAA "pkm:x")\n', "invalid_data"),
    (f'Text\n\n[unbenutzt]: <data:image/svg+xml,{GOOD_SVG[19:]}>\n', "unused_definition"),
])
def test_problem_codes(text, code):
    """Jeder Befundcode wird erkannt."""
    assert any(code in p for p in _problems(text, legacy=False).values()), _problems(text, legacy=False)


def test_conforming_and_code_are_clean():
    """Konforme Bilder und Data-URIs in Code ergeben keine Befunde; zu groß nur über der Grenze."""
    good = f'![Plan]({GOOD_SVG} "pkm:plan")\n\n```\n![x](data:image/png;base64, kaputt)\n```\n\n`![y](data:a b)`\n'
    assert not image_issues(good, LIMITS, legacy=False)
    assert "too_large_for_inline" in image_issues(good, ImageConfig(inline_max_kb=0), legacy=False)[0]["problems"]


def test_legacy_png_only_notation():
    """Bestehende Base64-PNG: nur Schreibweise; Name und Alternativtext werden nicht verlangt."""
    text = f'Text <img src="data:image/png;base64,{PNG_B64[:8]}\n{PNG_B64[8:]}">\n'
    assert _problems(text)["image-1"] == ["html_img", "base64_whitespace"]
    new, _ = fix_text(text, LIMITS)
    refs = images.find_images(new)
    assert refs[0].data() == make_png(text=False) and not refs[0].named and "pkm:" not in new
    assert not image_issues(new, LIMITS)


def test_fix_practice_vector_keeps_text_and_name():
    """Korrektur: Bild in eigene Zeile, Definition entfernt, Name bleibt, übriger Text unverändert."""
    new, _ = fix_text(PRACTICE, LIMITS, image_alt={"plan": "Aufbauplan"})
    assert "Der Aufbau:\n![Aufbauplan](data:image/svg+xml," in new and '"pkm:plan")\nsiehe oben.' in new
    assert "[plan]:" not in new and new.startswith("# Notiz\n\n## Aufbau\n")
    assert not image_issues(new, LIMITS)
    assert not notation_only(PRACTICE, new, LIMITS)  # Alternativtext geändert
    same_alt, _ = fix_text(PRACTICE, LIMITS)
    assert notation_only(PRACTICE, same_alt, LIMITS)


def test_reference_used_twice_and_unused_definition():
    """Mehrfach verwendete Referenz ergibt ambiguous; unbenutzte Definition nur mit Bestätigung."""
    twice = PRACTICE + "\nNochmal ![Plan][plan]\n"
    issue = image_issues(twice, LIMITS)[0]
    assert "more than once" in issue["note"]
    with pytest.raises(PkmError) as e:
        fix_text(twice, LIMITS)
    assert e.value.status == "ambiguous" and e.value.data["lines"] == [4, 8]
    unused = f"Text\n\n[weg]: <{GOOD_SVG}>\n"
    with pytest.raises(PkmError) as e:
        fix_text(unused, LIMITS)
    assert e.value.status == "large_shortening"
    assert fix_text(unused, LIMITS, confirm_shortening=True)[0] == "Text\n\n"


# Werkzeuge *******************************************************************
def test_read_placeholders_any_notation(svc):
    """read zeigt für jede Schreibweise Platzhalter; rewrite stellt sie byte-genau wieder her."""
    doc = svc.create_document(title="Alt", content="Text")
    write(svc.cfg, doc["path"], (svc.cfg.root / doc["path"]).read_text(encoding="utf-8") + "\n" + PRACTICE)
    data = svc.read(doc["path"])
    assert "data:image" not in data["content"] and "[plan]: <pkm-image:plan>" in data["content"]
    assert data["images"][0]["conforming"] is False and "reference_style" in data["images"][0]["problems"]
    before = (svc.cfg.root / doc["path"]).read_text(encoding="utf-8")
    svc.rewrite_document(target=doc["path"], content=data["content"].replace("siehe oben", "siehe unten"),
                         expected_hash=data["hash"])
    after = (svc.cfg.root / doc["path"]).read_text(encoding="utf-8")
    assert f"<data:image/svg+xml;utf8,{SVG_RAW}>" in after and "siehe unten" in after
    assert before.split("[plan]:")[1] == after.split("[plan]:")[1]


def test_write_tools_reject_then_fix(svc):
    """Abweichende Data-URI im Text: nonconforming_image ohne Schreiben; mit fix_images korrekt."""
    with pytest.raises(PkmError) as e:
        svc.create_document(title="Neu", content=PRACTICE)
    assert e.value.status == "nonconforming_image" and e.value.data["image_issues"][0]["ref"] == "plan"
    assert not list((svc.cfg.root / "documents/_inbox").glob("neu_*"))
    res = svc.create_document(title="Neu", content=PRACTICE, fix_images=True, image_alt={"plan": "Plan"})
    raw = (svc.cfg.root / res["path"]).read_text(encoding="utf-8")
    assert '"pkm:plan")' in raw and "[plan]:" not in raw and not image_issues(raw, LIMITS)


def test_image_warnings_do_not_block(svc):
    """Abweichende Bilder im Bestand blockieren nicht, sondern kommen als image_warnings."""
    doc = svc.create_document(title="Alt", content="Text")
    write(svc.cfg, doc["path"], (svc.cfg.root / doc["path"]).read_text(encoding="utf-8") + "\n" + PRACTICE)
    out = svc.append_to_document(target=doc["path"], text="Neue Zeile", expected_hash=svc.read(doc["path"])["hash"])
    assert out["status"] == "changed" and out["image_warnings"][0]["ref"] == "plan"


def test_fix_images_tool_proposal_and_apply(svc, isolated_env):
    """fix_images: ohne apply nur Vorschlag; mit apply eine Version mit PKM-Fix: images."""
    doc = svc.create_document(title="Alt", content="Text")
    write(svc.cfg, doc["path"], (svc.cfg.root / doc["path"]).read_text(encoding="utf-8") + "\n" + PRACTICE)
    h = svc.read(doc["path"])["hash"]
    prop = svc.fix_images(target=doc["path"], expected_hash=h)
    assert prop["status"] == "proposal" and "pkm-image:plan" in prop["diff"] and prop["image_issues"]
    assert svc.read(doc["path"])["hash"] == h
    out = svc.fix_images(target=doc["path"], expected_hash=h, apply=True, image_alt={"plan": "Plan"})
    assert out["status"] == "changed" and not out["image_issues"]
    body = git(isolated_env, "log", "-1", "--format=%B")
    assert "PKM-Fix: images" in body and "images fixed per 4.9" in body
    with pytest.raises(PkmError) as e:
        svc.fix_images(target="wiki/index", expected_hash="x")
    assert e.value.status == "forbidden"


# Pflege **********************************************************************
def test_pending_issues_notation_only_and_raised_citation(svc, cfg):
    """begin_maintenance meldet Befunde; nach der Korrektur image_notation_only, Belege werden angehoben."""
    write(cfg, "documents/notiz.md", PRACTICE)
    begin = maintrun.begin_maintenance(svc)
    doc_id = begin["ids"]["assigned"][0]["id"]
    assert begin["pending"]["new"][0]["image_issues"][0]["ref"] == "plan"
    sha = next(s["sha"] for s in svc.read(f"id:{doc_id}")["sections"] if s["key"] == "Aufbau")
    page = "wiki/topics/plan.md"
    write(cfg, page, f"---\ntype: topic\n---\n## Inhalt\nDer Plan zeigt X.[^b1]\n\n"
                     f"[^b1]: [[documents/notiz#Aufbau]] · „[img:plan]“ · id:{doc_id} · v:1 · sha:{sha}\n")
    maintrun.finish_maintenance(svc, "- vermerkt", processed=[doc_id])
    h = svc.read(f"id:{doc_id}")["hash"]
    maintrun.fix_document_images(svc, f"id:{doc_id}", h, apply=True)
    changed = maintrun.begin_maintenance(svc)["pending"]["changed"]
    assert changed[0]["image_notation_only"] is True and "image_issues" not in changed[0]
    fin = maintrun.finish_maintenance(svc, "- Bildschreibweise", processed=[doc_id])
    assert fin["raised_citations"]["pages_changed"] == 1
    line = (cfg.root / page).read_text(encoding="utf-8").splitlines()[-1]
    assert " · v:2 · " in line and f"sha:{sha}" not in line
    assert not [f for f in fin["lint"]["findings"] if f.get("path") == page and f["severity"] == "error"]


def test_write_wiki_page_checks_and_restores(svc):
    """write_wiki_page lehnt abweichende Data-URIs ab, korrigiert mit fix_images und erhält Platzhalter."""
    page = "wiki/syntheses/plan"
    content = f"---\ntype: synthesis\n---\n## Inhalt\nPlan: ![Plan][p]\n\n[p]: <data:image/svg+xml;utf8,{SVG_RAW}>\n"
    with pytest.raises(PkmError) as e:
        maintrun.write_wiki_page(svc, page, content)
    assert e.value.status == "nonconforming_image"
    res = maintrun.write_wiki_page(svc, page, content, fix_images=True)
    data = svc.read(res["path"])
    assert "pkm-image:p" in data["content"] and "data:image" not in data["content"]
    again = maintrun.write_wiki_page(svc, page, data["content"].replace("Plan:", "Der Plan:"), res["hash"])
    assert again["status"] == "changed" and "data:image/svg+xml," in (svc.cfg.root / res["path"]).read_text(
        encoding="utf-8")


def test_lint_and_cli(svc, cfg, capsys):
    """Lint meldet nonconforming_image und unsupported_type; pkm fix-images ohne --apply ändert nichts."""
    write(cfg, "documents/notiz.md", PRACTICE + "\n[Seite](data:text/html,<b>x</b>)\n")
    checks = [f["check"] for f in lint(svc)["findings"] if f.get("path") == "documents/notiz.md"]
    assert "nonconforming_image" in checks and "unsupported_type" in checks
    Maintenance(svc).ids()
    before = (cfg.root / "documents/notiz.md").read_bytes()
    assert main(["fix-images"]) == 0
    assert json.loads(capsys.readouterr().out)["affected"] == ["documents/notiz.md"]
    assert main(["fix-images", "documents/notiz.md"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["results"][0]["status"] == "proposal" and (cfg.root / "documents/notiz.md").read_bytes() == before
    assert main(["fix-images", "documents/notiz.md", "--apply", "--alt", "plan=Plan"]) == 0
    assert '"pkm:plan")' in (cfg.root / "documents/notiz.md").read_text(encoding="utf-8")

# Main ************************************************************************
