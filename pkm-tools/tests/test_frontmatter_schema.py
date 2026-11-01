"""Frontmatter nach dem Schema der digitalisierten Normen (Spezifikation 0.15–0.18, 4.1).

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
import re

import pytest

from pkm import mcp_server
from pkm.errors import PkmError
from pkm.lint import lint
from pkm.maint import Maintenance
from pkm.service import Service

from .conftest import git, write

# Variables *******************************************************************

NORM_TITLE = ("EN 61000-4-6 – Elektromagnetische Verträglichkeit (EMV) – Teil 4-6: Prüf- und Messverfahren – "
              "Störfestigkeit gegen leitungsgeführte Störgrößen, induziert durch hochfrequente Felder")
NORM = f"""---
title: {NORM_TITLE}
short citation: EN 61000-4-6:2014
date_document: August 2014
status_markdown: draft
date_markdown: 2026-10-25T14:12:00
toolchain_markdown: Claude Opus 5.5, Docling V 2.96.1
---

## 1 Anwendungsbereich
Dieser Teil der IEC 61000 gilt für leitungsgeführte Störgrößen.
"""
NORM_PATH = "documents/normen/en-61000-4-6.md"
STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

# Classes *********************************************************************

# Functions *******************************************************************


def checks_for(svc: Service, path: str) -> set[tuple[str, str]]:
    """Lint-Befunde einer Datei.

    Args:
        svc: Dienst.
        path: Relativer Pfad.

    Returns:
        Menge von (Prüfung, Schweregrad).
    """
    return {(f["check"], f["severity"]) for f in lint(svc)["findings"] if f.get("path") == path}


def test_norm_with_unquoted_colon_is_invalid_and_linted(svc, cfg):
    """Ein unquotiertes „: “ im Titel ergibt invalid_frontmatter mit Hinweis auf fix-frontmatter."""
    write(cfg, NORM_PATH, NORM)
    assert svc.read(NORM_PATH)["status"] == "invalid_frontmatter"
    finding = next(f for f in lint(svc)["findings"] if f.get("path") == NORM_PATH)
    assert finding["check"] == "invalid_frontmatter" and "pkm fix-frontmatter" in finding["message"]


def test_fix_frontmatter_lists_then_fixes_only_affected_lines(svc, cfg, isolated_env):
    """fix-frontmatter ohne Ziel listet nur; mit Ziel ändert es nur die betroffenen Zeilen."""
    write(cfg, NORM_PATH, NORM)
    m = Maintenance(svc)
    dry = m.fix_frontmatter()
    assert dry["dry_run"] and [f["path"] for f in dry["files"]] == [NORM_PATH]
    assert (cfg.root / NORM_PATH).read_text(encoding="utf-8") == NORM
    res = m.fix_frontmatter([NORM_PATH])
    assert res["files"][0]["committed"] is False
    fixed = (cfg.root / NORM_PATH).read_text(encoding="utf-8")
    diff = [(a, b) for a, b in zip(NORM.splitlines(), fixed.splitlines(), strict=True) if a != b]
    assert diff == [(f"title: {NORM_TITLE}", f'title: "{NORM_TITLE}"'),
                    ("short citation: EN 61000-4-6:2014", "short_citation: EN 61000-4-6:2014")]
    doc = svc.read(NORM_PATH)
    assert doc["status"] == "ok" and doc["frontmatter"]["title"] == NORM_TITLE
    assert "PKM-Id" not in git(isolated_env, "log", "-1", "--format=%B")


def test_ids_appends_only_id_and_version(svc, cfg):
    """Ein Dokument mit den sechs Umwandlungsfeldern bekommt nur id und version am Ende."""
    write(cfg, NORM_PATH, NORM)
    m = Maintenance(svc)
    m.fix_frontmatter([NORM_PATH])
    before = (cfg.root / NORM_PATH).read_text(encoding="utf-8")
    assigned = m.ids()["assigned"]
    after = (cfg.root / NORM_PATH).read_text(encoding="utf-8")
    fm_before = before.split("---\n")[1]
    assert after == f"---\n{fm_before}id: {assigned[0]['id']}\nversion: 1\n---\n" + before.split("---\n", 2)[2]
    assert "status_markdown: draft" in after


def test_short_citation_as_target(svc, cfg):
    """short_citation (auch alte Schreibweise, andere Groß-/Kleinschreibung, Leerraum) ist ein Ziel."""
    write(cfg, NORM_PATH, NORM.replace(f"title: {NORM_TITLE}", f'title: "{NORM_TITLE}"'))
    for target in ("EN 61000-4-6:2014", "en 61000-4-6:2014", "EN  61000-4-6:2014"):
        assert svc.resolve(target) == NORM_PATH
    with pytest.raises(PkmError) as e:
        svc.resolve("EN 99999:2020")
    assert e.value.status == "not_found"
    write(cfg, "documents/normen/kopie.md", (cfg.root / NORM_PATH).read_text(encoding="utf-8"))
    with pytest.raises(PkmError) as e:
        svc.resolve("EN 61000-4-6:2014")
    assert e.value.status == "ambiguous"


def test_legacy_name_renamed_with_new_version(svc, cfg, isolated_env):
    """Mit ID wird die Umbenennung durch fix-frontmatter als neue Version (user) committet."""
    write(cfg, NORM_PATH, NORM.replace(f"title: {NORM_TITLE}", f'title: "{NORM_TITLE}"'))
    m = Maintenance(svc)
    doc_id = m.ids()["assigned"][0]["id"]
    res = m.fix_frontmatter(all_documents=True)
    entry = res["files"][0]
    assert entry["changes"] == ["short citation → short_citation"] and entry["version"] == 2
    assert "PKM-Source: user" in git(isolated_env, "log", "-1", "--format=%B")
    assert svc.read(f"id:{doc_id}")["frontmatter"]["short_citation"] == "EN 61000-4-6:2014"
    assert svc.resolve("EN 61000-4-6:2014") == NORM_PATH
    assert not Maintenance(svc).fix_frontmatter()["files"]


def test_create_document_frontmatter(svc):
    """create_document schreibt das Schema aus 4.1 in der vorgesehenen Reihenfolge."""
    res = svc.create_document(title="Norm-Notiz: EMV", content="## Ergebnis\nx\n", tags=["emv"],
                              short_citation="EN 61000-4-6:2014", date_document="August 2014", kind="standard",
                              toolchain="Claude Opus 5.5 (pkm-mcp)", context="Chat: EMV")
    fm = svc.read(res["path"])["frontmatter"]
    assert list(fm) == ["title", "short_citation", "date_document", "date_markdown", "toolchain_markdown", "id",
                        "version", "context", "tags", "kind"]
    assert fm["title"] == "Norm-Notiz: EMV" and STAMP_RE.match(fm["date_markdown"])
    assert fm["toolchain_markdown"] == "Claude Opus 5.5 (pkm-mcp)" and "status_markdown" not in fm
    hits = svc.search("Norm-Notiz", scope="documents")["results"]
    assert hits[0]["short_citation"] == "EN 61000-4-6:2014" and "date_updated" in hits[0]


@pytest.mark.parametrize("kind", ["note", "standard", "regulation", "correction"])
def test_kinds(svc, kind):
    """Alle vier Werte von kind sind erlaubt."""
    res = svc.create_document(title=f"K {kind}", content="x", kind=kind)
    assert svc.read(res["path"])["frontmatter"]["kind"] == kind


def test_invalid_kind(svc):
    """Unbekannte Werte von kind werden abgelehnt."""
    with pytest.raises(PkmError) as e:
        svc.create_document(title="X", content="y", kind="gesetz")
    assert e.value.status == "invalid_argument"


def test_date_updated_without_timezone(svc):
    """date_updated wird mit Uhrzeit in Ortszeit ohne Zeitzone geschrieben."""
    res = svc.create_document(title="Zeit", content="a b")
    r = svc.edit_document(target=res["path"], old="a", new="c", expected_hash=res["new_hash"])
    fm = svc.read(res["path"])["frontmatter"]
    assert r["version"] == 2 and STAMP_RE.match(fm["date_updated"]) and "+" not in fm["date_updated"]


def test_status_markdown_never_written(svc, cfg):
    """Kein Werkzeug setzt oder ändert status_markdown."""
    write(cfg, NORM_PATH, NORM.replace(f"title: {NORM_TITLE}", f'title: "{NORM_TITLE}"'))
    Maintenance(svc).ids()
    doc = svc.read(NORM_PATH)
    with pytest.raises(PkmError) as e:
        svc.update_frontmatter(target=NORM_PATH, expected_hash=doc["hash"], set={"status_markdown": "final"})
    assert e.value.status == "protected_field"
    svc.edit_document(target=NORM_PATH, old="leitungsgeführte", new="leitungsgebundene", expected_hash=doc["hash"])
    assert svc.read(NORM_PATH)["frontmatter"]["status_markdown"] == "draft"


def test_lint_frontmatter_hints(svc, cfg):
    """Hinweise und Fehler zu Herkunftsfeldern, alter Schreibweise, kind, Datum und tags."""
    write(cfg, NORM_PATH, NORM.replace(f"title: {NORM_TITLE}", f'title: "{NORM_TITLE}"'))
    write(cfg, "documents/b.md", "---\ntitle: B\nkind: gesetz\ndate_updated: 2026-11-01T10:00:00+01:00\n"
          "tags: [zwei worte]\n---\nx\n")
    norm = checks_for(svc, NORM_PATH)
    assert {("legacy_short_citation", "info"), ("missing_kind", "info")} <= norm
    assert ("missing_date_markdown", "info") not in norm
    other = checks_for(svc, "documents/b.md")
    assert {("invalid_kind", "error"), ("invalid_date", "warning"), ("invalid_tags", "warning"),
            ("missing_date_markdown", "info"), ("missing_toolchain_markdown", "info")} <= other


def test_lint_accepts_date_only_and_kind_standard(svc, cfg):
    """Datum ohne Uhrzeit ist gültig; mit kind gibt es keinen missing_kind-Hinweis."""
    text = NORM.replace(f"title: {NORM_TITLE}", f'title: "{NORM_TITLE}"').replace("2026-10-25T14:12:00", "2026-10-25")
    write(cfg, NORM_PATH, text.replace("short citation:", "kind: standard\nshort_citation:"))
    checks = {c for c, _ in checks_for(svc, NORM_PATH)}
    assert not checks & {"invalid_date", "missing_kind", "legacy_short_citation", "invalid_kind"}


@pytest.mark.usefixtures("cfg")
def test_mcp_create_document_parameters():
    """Das MCP-Tool create_document kennt tags, short_citation, date_document und toolchain."""
    tools = {t.name: t for t in asyncio.run(mcp_server.build_server().list_tools())}
    params = set(tools["create_document"].input_schema["properties"])
    assert {"tags", "short_citation", "date_document", "toolchain"} <= params
    assert not params & {"topics", "source"}

# Main ************************************************************************
