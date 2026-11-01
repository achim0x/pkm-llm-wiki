"""Belege, show_citations, fix-/sync-citations, lint, doctor (Spezifikation 4.2, 5.2, 7.3, 8).

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
import json

import pytest

from pkm import mcp_server
from pkm.citations import fix_citations, parse_citation, parse_page, show_citations, sync_citations
from pkm.cli import main
from pkm.config import Config
from pkm.doctor import doctor
from pkm.errors import PkmError
from pkm.lint import lint, write_report
from pkm.maint import Maintenance
from pkm.service import Service

from .conftest import write

# Variables *******************************************************************

OTHER_ID = "d-20261012-0915-x7mp"

BODY = """## Dach
Dachfläche laut Plan 92 m².

## Entscheidungen
- Schwimmerschalter statt Ultraschall

## Notizen
erste

## Notizen
zweite Notiz
"""

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="setup")
def fixture_setup(svc, cfg):
    """Dokument, PDF und zwei Wiki-Seiten mit gültigen Belegen.

    Args:
        svc: Dienst.
        cfg: Konfiguration.

    Returns:
        Dokument, Link-Pfad, Abschnitts-Hashes, PDF-Hash und Seitenpfad.
    """
    d = svc.create_document(title="Zisterne", content=BODY)
    write(cfg, "documents/haus/datenblatt.pdf", "%PDF Nutzvolumen 6500 l")
    m = Maintenance(svc)
    sha = m.sha(d["path"])["sections"]
    pdf = m.sha("documents/haus/datenblatt.pdf")["file_hash"]
    link = d["path"][:-3]
    sha_ent = sha["Entscheidungen"]
    page = f"""---
type: topic
title: Regenwasser-Ertrag
sources:
  - "[[{link}]]"
  - "[[documents/haus/datenblatt.pdf]]"
updated: 2026-11-02
confidence: high
---

> **Kurzfassung:** Dach und Tank.

## Inhalt
Die Dachfläche beträgt 92 m².[^b1] Der Überlauf wird per Schwimmerschalter erkannt.[^b2]
Der Tank fasst 6.500 L.[^b3]

Zweiter Absatz zur Notiz.[^b4]

## Belege
[^b1]: [[{link}#Dach]] · „Dachfläche laut Plan 92 m²“ · id:{d['id']} · v:1 · sha:{sha['Dach']}
[^b2]: [[{link}#Entscheidungen]] · „Schwimmerschalter statt Ultraschall“ · id:{d['id']} · v:1 · sha:{sha_ent}
[^b3]: [[documents/haus/datenblatt.pdf#page=2]] · „Nutzvolumen 6500 l“ · sha:{pdf}
[^b4]: [[{link}#Notizen]] §:Notizen#2 · „zweite Notiz“ · id:{d['id']} · v:1 · sha:{sha['Notizen#2']}
"""
    write(cfg, "wiki/topics/regenwasser-ertrag.md", page)
    write(cfg, "wiki/entities/tank-1.md", "---\ntype: entity\ntitle: Tank 1\nsources: []\n---\n\n> Der Tank.\n\n"
          "## Siehe auch\n- [[wiki/topics/regenwasser-ertrag]]\n")
    see_also = "\n## Siehe auch\n- [[wiki/entities/tank-1]]\n"
    page2 = (cfg.root / "wiki/topics/regenwasser-ertrag.md").read_text() + see_also
    write(cfg, "wiki/topics/regenwasser-ertrag.md", page2)
    return {"doc": d, "link": link, "sha": sha, "pdf": pdf, "page": "wiki/topics/regenwasser-ertrag.md"}


# Parser **********************************************************************
def test_parse_citation_full():
    """Eine vollständige Beleg-Zeile wird gelesen."""
    c = parse_citation("b1", f"[[documents/haus/z#Dach]] · „Dachfläche 92 m²“ · id:{OTHER_ID} · v:2 · sha:3f9a1c", 0)
    assert (c.path, c.anchor, c.quote, c.doc_id, c.version, c.sha) == (
        "documents/haus/z", "Dach", "Dachfläche 92 m²", OTHER_ID, 2, "3f9a1c")
    assert not c.problems and c.section_key == "Dach" and c.target_rel == "documents/haus/z.md"


def test_parse_citation_pdf_and_dup_key():
    """PDF-Seiten und §:-Schlüssel (auch als eigener Teil)."""
    c = parse_citation("b4", "[[documents/a.pdf#page=2]] · „x“ · sha:c07d44", 0)
    assert c.page == 2 and not c.markdown and not c.problems and c.section_key is None
    d = parse_citation("b5", f"[[documents/a#Notizen]] §:Notizen#2 · „x“ · id:{OTHER_ID} · v:1 · sha:abcdef", 0)
    assert d.section_key == "Notizen#2"
    e = parse_citation("b6", f"[[documents/a#Notizen]] · §:Notizen#2 · „x“ · id:{OTHER_ID} · v:1 · sha:abcdef", 0)
    assert e.section_key == "Notizen#2"


def test_parse_citation_preamble_and_problems():
    """Ohne Anker gilt der Vorspann; Formatfehler werden gemeldet."""
    c = parse_citation("b1", "[[documents/a]] · „x“ · id:d-20261012-0915-x7mp · v:1 · sha:abcdef", 0)
    assert c.section_key == "_preamble"
    bad = parse_citation("b2", "ohne Link · v:x", 0)
    assert {"Link fehlt", "ungültige Version", "sha fehlt", "id fehlt", "Zitat fehlt"} <= set(bad.problems)
    long = parse_citation("b3", f"[[documents/a]] · „{'x' * 201}“ · id:{OTHER_ID} · v:1 · sha:abcdef", 0)
    assert any("200" in p for p in long.problems)


def test_parse_page_statements(svc, setup):
    """Aussagen ohne Fußnotenmarken mit ihren Belegen."""
    pc = parse_page(svc.vault.load(setup["page"]))
    assert set(pc.definitions) == {"b1", "b2", "b3", "b4"}
    st = {s.text: s.labels for s in pc.statements if s.section == "Inhalt"}
    first = next(k for k in st if k.startswith("Die Dachfläche"))
    assert st[first] == ["b1", "b2", "b3"]
    assert "[^" not in first


# show_citations **************************************************************
@pytest.mark.usefixtures("cfg")
def test_show_citations_ok(svc, setup):
    """Alle Belege der Beispielseite sind ok."""
    res = show_citations(svc, "[[regenwasser-ertrag]]")
    by = {c["id"]: c for c in res["citations"]}
    assert [c["status"] for c in res["citations"]] == ["ok"] * 4
    assert by["b1"]["original"] == setup["doc"]["path"] and by["b1"]["cited_version"] == 1
    assert by["b3"]["original"] == "documents/haus/datenblatt.pdf"
    assert by["b4"]["section"] == "Notizen#2"
    assert "obsidian_link" not in by["b1"]


def test_show_citations_statement_and_excerpt(svc, setup):
    """statement grenzt ein, with_excerpt liefert den Wortlaut."""
    res = show_citations(svc, setup["page"], statement="Dachfläche beträgt", with_excerpt=True)
    assert [c["id"] for c in res["citations"]] == ["b1"]
    whole = show_citations(svc, setup["page"], statement="92 m². Der Überlauf")
    assert [c["id"] for c in whole["citations"]] == ["b1", "b2", "b3"]  # über Grenzen: ganzer Absatz
    b1 = res["citations"][0]
    assert b1["cited_excerpt"] == "## Dach\nDachfläche laut Plan 92 m²."
    assert "current_excerpt" not in b1
    with pytest.raises(PkmError):
        show_citations(svc, setup["page"], statement="gibt es nicht")


def test_show_citations_newer_version(svc, setup):
    """Geänderte Abschnitte ergeben newer_version mit beiden Wortlauten."""
    d = setup["doc"]
    r = svc.edit_document(target=d["path"], old="92 m²", new="95 m²", expected_hash=d["new_hash"])
    svc.edit_document(target=d["path"], old="erste", new="erste!", expected_hash=r["new_hash"])
    res = show_citations(svc, setup["page"], with_excerpt=True)
    by = {c["id"]: c for c in res["citations"]}
    assert by["b1"]["status"] == "newer_version" and by["b1"]["current_version"] == 3
    assert "92 m²" in by["b1"]["cited_excerpt"] and "95 m²" in by["b1"]["current_excerpt"]
    assert by["b2"]["status"] == "ok"  # Abschnitt unverändert
    assert by["b4"]["status"] == "ok"


def test_show_citations_moved_and_missing(svc, setup, cfg):
    """Verschobene und fehlende Originale (Markdown und PDF)."""
    (cfg.root / "documents/neu").mkdir()
    (cfg.root / setup["doc"]["path"]).rename(cfg.root / "documents/neu/zisterne.md")
    (cfg.root / "documents/haus/datenblatt.pdf").rename(cfg.root / "documents/neu/blatt.pdf")
    by = {c["id"]: c for c in show_citations(svc, setup["page"])["citations"]}
    assert by["b1"]["status"] == "moved" and by["b1"]["original"] == "documents/neu/zisterne.md"
    assert by["b3"]["status"] == "moved" and by["b3"]["original"] == "documents/neu/blatt.pdf"
    (cfg.root / "documents/neu/zisterne.md").unlink()
    (cfg.root / "documents/neu/blatt.pdf").unlink()
    by = {c["id"]: c for c in show_citations(svc, setup["page"], with_excerpt=True)["citations"]}
    assert by["b1"]["status"] == "missing" and by["b3"]["status"] == "missing"
    assert "92 m²" in by["b1"]["cited_excerpt"]  # Wortlaut weiter aus Git


@pytest.mark.usefixtures("isolated_env")
def test_show_citations_obsidian_link(monkeypatch, setup):
    """Mit PKM_VAULT_NAME gibt es obsidian://-Links."""
    monkeypatch.setenv("PKM_VAULT_NAME", "Mein Vault")
    res = show_citations(Service(Config.from_env()), setup["page"])
    assert res["citations"][0]["obsidian_link"].startswith("obsidian://open?vault=Mein%20Vault&file=documents%2F")


def test_show_citations_only_wiki(svc, setup):
    """show_citations gilt nur für Wiki-Seiten."""
    with pytest.raises(PkmError):
        show_citations(svc, setup["doc"]["path"])


# fix/sync-citations **********************************************************
def test_fix_citations_moved(svc, setup, cfg):
    """fix-citations korrigiert Pfade samt §: und sources."""
    (cfg.root / "documents/neu").mkdir()
    (cfg.root / setup["doc"]["path"]).rename(cfg.root / "documents/neu/zisterne.md")
    res = fix_citations(svc)
    assert res["pages_changed"] == 1
    text = (cfg.root / setup["page"]).read_text()
    assert "[^b1]: [[documents/neu/zisterne#Dach]] · „Dachfläche laut Plan 92 m²“" in text
    assert "[^b4]: [[documents/neu/zisterne#Notizen]] §:Notizen#2 · „zweite Notiz“" in text
    assert '  - "[[documents/neu/zisterne]]"' in text
    assert all(c["status"] == "ok" for c in show_citations(svc, setup["page"])["citations"])
    assert fix_citations(svc)["pages_changed"] == 0


def test_fix_citations_renamed_section(svc, setup, cfg):
    """fix-citations passt umbenannte Abschnitte an."""
    d = setup["doc"]
    svc.edit_document(target=d["path"], old="## Dach\n", new="## Dachfläche\n", expected_hash=d["new_hash"])
    fix_citations(svc, [setup["page"]])
    assert f"[^b1]: [[{setup['link']}#Dachfläche]]" in (cfg.root / setup["page"]).read_text()


def test_sync_citations(svc, setup, cfg):
    """sync-citations erzeugt sources aus den Fußnoten."""
    p = cfg.root / setup["page"]
    p.write_text(p.read_text().replace('  - "[[documents/haus/datenblatt.pdf]]"\n', ""))
    res = sync_citations(svc)
    assert res["pages_changed"] == 1
    meta = svc.read(setup["page"])["frontmatter"]
    assert meta["sources"] == sorted([f"[[{setup['link']}]]", "[[documents/haus/datenblatt.pdf]]"])
    assert sync_citations(svc)["pages_changed"] == 0


# lint ************************************************************************
def checks(result):
    """Befunde als Menge.

    Args:
        result: Ergebnis von ``lint``.

    Returns:
        Menge von (Prüfung, Pfad).
    """
    return {(f["check"], f.get("path")) for f in result["findings"]}


@pytest.mark.usefixtures("setup")
def test_lint_clean(svc):
    """Die Beispielseite ist bis auf die gewollten Duplikat-Überschriften sauber."""
    res = lint(svc)
    errors = [f for f in res["findings"] if f["severity"] in ("error", "warning")]
    # Das Testdokument hat absichtlich doppelte Überschriften (Notizen, Notizen#2)
    assert [f["check"] for f in errors] == ["duplicate_heading"], errors


def test_lint_citation_problems(svc, setup, cfg):
    """Falsches Zitat, falscher sha, fehlende Fußnoten und Belege auf Wiki-Seiten."""
    p = cfg.root / setup["page"]
    t = p.read_text()
    t = t.replace("„Dachfläche laut Plan 92 m²“", "„Dachfläche 100 m²“")  # Zitat falsch
    t = t.replace(f"sha:{setup['sha']['Entscheidungen']}", "sha:000000")  # sha falsch
    t = t.replace("Der Tank fasst 6.500 L.[^b3]", "Der Tank fasst 6.500 L.[^b3] Ohne Beleg hier.\n\nNeue Aussage.[^b9]")
    t += "[^b5]: [[wiki/entities/tank-1]] · „x“ · sha:abcdef\n"
    t = t.replace("## Inhalt\n", "## Inhalt\nAussage ganz ohne Fußnote.\n\n")
    p.write_text(t)
    c = checks(lint(svc))
    page = setup["page"]
    for expected in ("quote_not_found", "sha_mismatch", "footnote_undefined", "footnote_unused",
                     "citation_to_wiki", "statement_without_citation"):
        assert (expected, page) in c, expected


def test_lint_moved_newer_missing(svc, setup, cfg):
    """Verschoben, neuere Version und fehlendes Original."""
    d = setup["doc"]
    svc.edit_document(target=d["path"], old="92 m²", new="95 m²", expected_hash=d["new_hash"])
    (cfg.root / "documents/neu").mkdir()
    (cfg.root / d["path"]).rename(cfg.root / "documents/neu/z.md")
    (cfg.root / "documents/haus/datenblatt.pdf").unlink()
    c = checks(lint(svc))
    page = setup["page"]
    assert ("citation_moved", page) in c and ("citation_newer_version", page) in c
    assert ("citation_missing", page) in c


def test_lint_anchor_missing_and_sources(svc, setup, cfg):
    """Fehlender Anker, ungültige confidence und veraltete sources."""
    p = cfg.root / setup["page"]
    text = p.read_text().replace("#Entscheidungen]]", "#Gibtsnicht]]")
    p.write_text(text.replace("confidence: high", "confidence: sicher"))
    c = checks(lint(svc))
    assert ("anchor_missing", setup["page"]) in c and ("invalid_confidence", setup["page"]) in c
    p.write_text(p.read_text().replace('  - "[[documents/haus/datenblatt.pdf]]"\n', ""))
    assert ("sources_out_of_sync", setup["page"]) in checks(lint(svc))


@pytest.mark.usefixtures("setup")
def test_lint_structure(svc, cfg):
    """Fehlende Kurzfassung, kaputte Links, verwaiste Seiten, fehlender Typ."""
    write(cfg, "wiki/topics/waise.md",
          "---\ntype: topic\ntitle: Waise\n---\nOhne Kurzfassung [[gibtsnicht]] [[gibtsnicht]]\n")
    write(cfg, "wiki/topics/ohne-typ.md", "---\ntitle: X\n---\n> K\n[[wiki/topics/waise]] [[gibtsnicht]]\n")
    c = checks(lint(svc))
    assert ("missing_summary", "wiki/topics/waise.md") in c
    assert ("broken_link", "wiki/topics/waise.md") in c
    assert ("orphan_page", "wiki/topics/ohne-typ.md") in c
    assert ("invalid_type", "wiki/topics/ohne-typ.md") in c
    assert ("missing_page", None) in c


def test_lint_documents_and_platform(svc, setup, cfg):
    """Prüfungen für Dokumente, Überschriften und Plattform."""
    write(cfg, "documents/ohne.md", "# Ohne\n\nTitel\n=====\n\n## A\n## A\n## B [x]\n")
    write(cfg, "documents/kaputt.md", "---\ntitle: [x\n---\n")
    (cfg.root / "documents/bin.md").write_bytes(b"\xff")
    write(cfg, "documents/kopie (conflicted copy).md", (cfg.root / setup["doc"]["path"]).read_text())
    write(cfg, "documents/Gross.md", "x\n")
    write(cfg, "documents/gross.md", "y\n")
    # macOS (APFS) und Windows unterscheiden Groß-/Kleinschreibung nicht: dort entsteht nur eine Datei
    case_sensitive = len({p.name for p in (cfg.root / "documents").glob("[Gg]ross.md")}) == 2
    p = cfg.root / setup["doc"]["path"]
    c = checks(lint(svc))
    expected_checks = [("missing_id", "documents/ohne.md"), ("setext_heading", "documents/ohne.md"),
                           ("duplicate_heading", "documents/ohne.md"), ("heading_bad_chars", "documents/ohne.md"),
                           ("invalid_frontmatter", "documents/kaputt.md"), ("invalid_encoding", "documents/bin.md"),
                           ("conflict_copy", "documents/kopie (conflicted copy).md")]
    if case_sensitive:
        expected_checks.append(("case_collision", "documents/Gross.md"))
    for expected, path in expected_checks:
        assert (expected, path) in c, expected
    assert p.exists()


def test_lint_version_mismatch_and_duplicates(svc, setup, cfg):
    """Version passt nicht zum Verlauf; doppelte IDs."""
    d = setup["doc"]
    p = cfg.root / d["path"]
    p.write_text(p.read_text().replace("version: 1", "version: 7"))
    svc.git.commit_paths([d["path"]], "manuell\n", as_user=True)
    write(cfg, "documents/kopie.md", p.read_text())
    c = checks(lint(svc))
    assert ("version_mismatch", d["path"]) in c
    assert ("duplicate_id", sorted([d["path"], "documents/kopie.md"])[0]) in c


@pytest.mark.usefixtures("setup")
def test_lint_report(svc, cfg):
    """lint --report schreibt den Bericht nach wiki/_lint/."""
    res = lint(svc)
    rel = write_report(svc, res)
    assert rel.startswith("wiki/_lint/") and (cfg.root / rel).read_text().startswith("# Lint-Bericht")


# doctor **********************************************************************
@pytest.mark.usefixtures("cfg")
def test_doctor_ok(svc):
    """doctor meldet in der Testumgebung keine Fehler."""
    res = doctor(svc)
    assert res["status"] == "ok", [c for c in res["checks"] if not c["ok"]]
    assert doctor(svc, short=True)["checks"] == []


def test_doctor_problems(svc, cfg, isolated_env):
    """doctor erkennt .git im Vault, Konfliktkopien und Commit-Signierung."""
    (cfg.root / ".git").mkdir()
    write(cfg, "documents/a (conflicted copy).md", "x")
    isolated_env["gitconfig"].write_text("[user]\n name=A\n email=a@b\n[commit]\n gpgsign = true\n")
    res = doctor(svc)
    bad = {c["check"]: c["severity"] for c in res["checks"] if not c["ok"]}
    assert bad["no_dotgit_in_vault"] == "error" and bad["conflict_copies"] == "error"
    assert bad["git_signing"] == "warning" and res["status"] == "error"


@pytest.mark.usefixtures("cfg")
def test_doctor_cache_in_nextcloud(isolated_env, monkeypatch):
    """doctor erkennt PKM_CACHE_DIR in einem Nextcloud-Ordner."""
    monkeypatch.setenv("PKM_CACHE_DIR", str(isolated_env["root"].parent / "cache"))
    res = doctor(Service(Config.from_env()))
    assert any(c["check"] == "cache_dir_nextcloud" and not c["ok"] for c in res["checks"])


def test_doctor_obsidian(svc, cfg):
    """doctor prüft die Obsidian-Einstellungen."""
    write(cfg, ".obsidian/app.json", json.dumps({
        "alwaysUpdateLinks": True, "newLinkFormat": "shortest", "useMarkdownLinks": False,
        "attachmentFolderPath": "documents/_attachments", "userIgnoreFilters": [".pkm/"]}))
    res = doctor(svc)
    bad = [c["check"] for c in res["checks"] if not c["ok"]]
    assert bad == ["obsidian_newLinkFormat"] and res["status"] == "ok"


# CLI und MCP *****************************************************************
@pytest.mark.usefixtures("setup")
def test_cli_phase5(capsys):
    """Die Beleg-Befehle laufen über die CLI."""
    for argv in (["fix-citations"], ["sync-citations"], ["lint", "--report"], ["doctor", "--short"]):
        assert main(argv) == 0, argv
        assert json.loads(capsys.readouterr().out)["status"] == "ok"


@pytest.mark.usefixtures("cfg")
def test_mcp_show_citations(setup):

    """show_citations über den MCP-Server."""
    mcp_server.reset_service()
    names = {t.name for t in asyncio.run(mcp_server.build_server().list_tools())}
    assert len(names) == 12 and "show_citations" in names
    res = mcp_server.call("show_citations", lambda s, **k: s.show_citations(**k), target=setup["page"],
                          statement="Tank fasst")
    assert [c["id"] for c in res["citations"]] == ["b3"]
    mcp_server.reset_service()

# Main ************************************************************************
