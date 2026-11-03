"""Tests zum Änderungsauftrag 2026-11-02: Metadaten nach Bestätigung, Feldreihenfolge, read in Teilen,
Lint ohne Fehlalarme, Verschieben außerhalb von Obsidian, leere Abschnitte, Anheben von Belegen.

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

import pytest

from pkm import maintrun, service
from pkm.citations import fix_citations, parse_page
from pkm.citeraise import raise_versions
from pkm.errors import PkmError
from pkm.lint import lint

from .conftest import git, write

# Variables *******************************************************************

DOC = "documents/softskills/verhandlung.md"
DOC_TEXT = "# Verhandlung\n\n## Regeln\nNie den ersten Preis akzeptieren.\n\n## Rollen\nZwei Rollen.\n"

# Classes *********************************************************************

# Functions *******************************************************************


def _new_doc(svc, cfg, text=DOC_TEXT, rel=DOC):
    """Dokument von Hand anlegen und per begin_maintenance mit ID versehen.

    Args:
        svc: Dienst.
        cfg: Konfiguration.
        text: Inhalt.
        rel: Pfad.

    Returns:
        Die vergebene ID.
    """
    write(cfg, rel, text)
    return maintrun.begin_maintenance(svc)["ids"]["assigned"][0]["id"]


def _cite(svc, doc_id, key):
    """Beleg-Zeile auf einen Abschnitt erzeugen.

    Args:
        svc: Dienst.
        doc_id: ID.
        key: Abschnittsschlüssel.

    Returns:
        Zeile ohne Fußnotennamen.
    """
    doc = svc.read(f"id:{doc_id}")
    sha = next(s["sha"] for s in doc["sections"] if s["key"] == key)
    path = doc["path"][:-3]
    return f"[[{path}#{key}]] · „x“ · id:{doc_id} · v:{doc['version']} · sha:{sha}"


def _lint_checks(svc, page):
    """Lint-Befunde einer Seite.

    Args:
        svc: Dienst.
        page: Pfad der Seite.

    Returns:
        Liste der Prüfnamen.
    """
    return [f["check"] for f in lint(svc)["findings"] if f.get("path") == page]


# Metadaten *******************************************************************
def test_set_metadata_in_schema_order(svc, cfg, isolated_env):
    """Felder kommen an die Stelle aus dem Schema; neue Version mit PKM-Source agent; Tags vereinheitlicht."""
    doc_id = _new_doc(svc, cfg)
    h = svc.read(f"id:{doc_id}")["hash"]
    res = maintrun.set_document_metadata(svc, f"id:{doc_id}", h, set={
        "title": "Verhandlungsregeln", "context": "Buch: Schranner", "tags": ["Verhandlung", "Führung", "führung"],
        "kind": "note"})
    assert res["status"] == "changed" and res["version"] == 2
    text = (cfg.root / DOC).read_text(encoding="utf-8")
    keys = [ln.split(":")[0] for ln in text.split("---")[1].strip().splitlines()]
    assert keys == ["title", "id", "version", "date_updated", "context", "tags", "kind"]
    assert "tags: [verhandlung, fuehrung]" in text
    assert 'context: "Buch: Schranner"' in text
    assert "PKM-Source: agent" in git(isolated_env, "log", "-1", "--format=%B")


def test_set_metadata_rules(svc, cfg):
    """Whitelist, kind-Prüfung, kein Überschreiben ohne overwrite, add für tags."""
    doc_id = _new_doc(svc, cfg, "---\ntitle: Alt\ntags: [a]\n---\nText\n")
    target = f"id:{doc_id}"
    cases = [({"related": ["x"]}, None, "protected_field"), ({"id": "x"}, None, "protected_field"),
             ({"kind": "memo"}, None, "invalid_argument"), ({"title": "Neu"}, None, "field_exists"),
             (None, {"title": "x"}, "protected_field"), ({"context": " "}, None, "invalid_argument")]
    for set_fields, add_fields, status in cases:
        with pytest.raises(PkmError) as e:
            maintrun.set_document_metadata(svc, target, svc.read(target)["hash"], set=set_fields, add=add_fields)
        assert e.value.status == status, (set_fields, add_fields)
    res = maintrun.set_document_metadata(svc, target, svc.read(target)["hash"], set={"title": "Neu"}, overwrite=True,
                                         add={"tags": ["B", "a"]})
    assert res["status"] == "changed"
    meta = svc.read(target)["frontmatter"]
    assert meta["title"] == "Neu" and meta["tags"] == ["a", "b"]
    same = maintrun.set_document_metadata(svc, target, svc.read(target)["hash"], set={"title": "Neu"})
    assert same["status"] == "unchanged"
    with pytest.raises(PkmError) as e:
        maintrun.set_document_metadata(svc, target, "falsch", set={"kind": "note"})
    assert e.value.status == "conflict"
    with pytest.raises(PkmError):
        maintrun.set_document_metadata(svc, "wiki/index", "x", set={"kind": "note"})


def test_begin_reports_missing_fields_and_known_tags(svc, cfg):
    """begin_maintenance nennt fehlende Felder neuer Dokumente und vorhandene Tags."""
    write(cfg, "documents/a.md", "---\ntitle: A\ntags: [garten, wasser]\n---\nA\n")
    write(cfg, "documents/b.md", "---\ntags: [Garten]\nkind: note\n---\nB\n")
    res = maintrun.begin_maintenance(svc)
    missing = {d["path"]: d["missing_fields"] for d in res["pending"]["new"]}
    assert missing == {"documents/a.md": ["context", "kind"], "documents/b.md": ["title", "context"]}
    assert res["known_tags"] == {"garten": 2, "wasser": 1}


def test_update_frontmatter_keeps_schema_order(svc, cfg):
    """update_frontmatter (Server pkm) schreibt neue Felder in der Schema-Reihenfolge."""
    doc_id = _new_doc(svc, cfg, "Text\n")
    target = f"id:{doc_id}"
    svc.update_frontmatter(target=target, expected_hash=svc.read(target)["hash"],
                           set={"kind": "note", "title": "T", "custom": "x", "tags": ["a"]})
    keys = list(svc.read(target)["frontmatter"])
    assert keys[:2] == ["title", "id"] and keys.index("tags") < keys.index("kind") < keys.index("custom")


def test_versions_commits_claude_md(svc, cfg, isolated_env):
    """Eine von Hand geänderte CLAUDE.md wird als Nutzer-Commit erfasst."""
    p = cfg.root / "CLAUDE.md"
    p.write_text(p.read_text(encoding="utf-8") + "\nNeue Regel.\n", encoding="utf-8", newline="\n")
    res = maintrun.begin_maintenance(svc)
    assert [c["path"] for c in res["versions"]["committed"]] == ["CLAUDE.md"]
    assert "PKM-Source: user" in git(isolated_env, "log", "-1", "--format=%B")
    assert git(isolated_env, "status", "--porcelain", "CLAUDE.md").strip() == ""


# read ************************************************************************
def test_read_section_paging_and_metadata_only(svc, cfg, monkeypatch):
    """read liefert einzelne Abschnitte, Seiten oder nur Metadaten; zu große Inhalte werden ausgelassen."""
    doc_id = _new_doc(svc, cfg)
    target = f"id:{doc_id}"
    sec = svc.read(target, section="Regeln")
    assert sec["content"] == "## Regeln\nNie den ersten Preis akzeptieren." and sec["section"] == "Regeln"
    meta = svc.read(target, content=False)
    assert "content" not in meta and meta["content_length"] > 0 and meta["hash"] and meta["sections"]
    full = svc.read(target)["content"]
    first = svc.read(target, max_chars=10)
    assert first["content"] == full[:10] and first["truncated"] and first["next_offset"] == 10
    rest = svc.read(target, offset=10)
    assert first["content"] + rest["content"] == full and not rest["truncated"]
    monkeypatch.setattr(service, "READ_LIMIT", 20)
    big = svc.read(target)
    assert big["content_omitted"] and "content" not in big
    with pytest.raises(PkmError) as e:
        svc.read(target, section="Gibt es nicht")
    assert e.value.status == "not_found" and "Regeln" in e.value.data["sections"]


def test_empty_section_is_marked_and_linted(svc, cfg):
    """Abschnitte ohne eigenen Text sind in read markiert; ein Beleg darauf gibt eine Warnung."""
    doc_id = _new_doc(svc, cfg)
    sections = {s["key"]: s for s in svc.read(f"id:{doc_id}")["sections"]}
    assert sections["Verhandlung"].get("empty") and not sections["Regeln"].get("empty")
    page = "wiki/topics/t.md"
    write(cfg, page, f"---\ntype: topic\n---\n## Inhalt\nAussage.[^b1]\n\n[^b1]: {_cite(svc, doc_id, 'Verhandlung')}\n")
    assert "citation_empty_section" in _lint_checks(svc, page)


# Lint ************************************************************************
def test_lint_ignores_structure_lines(svc, cfg):
    """Zwischenüberschriften, Fett-Zeilen, Link-Zeilen und belegte Tabellen erzeugen keine Warnung."""
    doc_id = _new_doc(svc, cfg)
    cite = _cite(svc, doc_id, "Regeln")
    page = "wiki/topics/t.md"
    write(cfg, page, f"""---
type: topic
---
## Inhalt
### Die Regeln
**Die drei Rollen**
| Rolle | Aufgabe |
|---|---|
| A | B |

[^b1]

Details: [[wiki/topics/andere]]
- [[wiki/topics/andere]]
Belegte Aussage.[^b1]

[^b1]: {cite}
""")
    pc = parse_page(svc.vault.load(page))
    assert [st.labels for st in pc.statements if st.section == "Inhalt"] == [["b1"], ["b1"]]
    assert "statement_without_citation" not in _lint_checks(svc, page)


def test_lint_still_flags_unsupported_table(svc, cfg):
    """Eine Tabelle ohne Beleg und ein normaler Satz ohne Beleg bleiben Warnungen."""
    page = "wiki/topics/t.md"
    write(cfg, page, "---\ntype: topic\n---\n## Inhalt\n| A | B |\n|---|---|\n| 1 | 2 |\n\nOhne Beleg.\n")
    assert _lint_checks(svc, page).count("statement_without_citation") == 2


# Verschieben und Versionen ***************************************************
def test_move_outside_obsidian_rewrites_footnotes_and_links(svc, cfg):
    """Nach einem Verschieben ohne Obsidian (Index veraltet) werden Beleg und Wikilink umgeschrieben."""
    doc_id = _new_doc(svc, cfg)
    page = "wiki/summaries/v.md"
    write(cfg, page, f"---\ntype: summary\n---\nOriginal: [[{DOC[:-3]}]]\n\n## Inhalt\nA.[^b1]\n\n"
                     f"[^b1]: {_cite(svc, doc_id, 'Regeln')}\n")
    svc.search("Verhandlung", scope="all")  # Index aufbauen, dann veraltet lassen
    new = "documents/archiv/verhandlung.md"
    (cfg.root / "documents/archiv").mkdir(parents=True)
    (cfg.root / DOC).rename(cfg.root / new)
    res = fix_citations(svc)
    assert res["pages_changed"] == 1
    text = (cfg.root / page).read_text(encoding="utf-8")
    assert f"Original: [[{new[:-3]}]]" in text and f"[[{new[:-3]}#Regeln]]" in text
    assert DOC[:-3] not in text


def test_raise_versions_only_for_unchanged_sections(svc, cfg):
    """Belege auf unveränderte Abschnitte werden auf die neue Version angehoben, andere nicht."""
    doc_id = _new_doc(svc, cfg)
    page = "wiki/topics/t.md"
    write(cfg, page, f"---\ntype: topic\n---\n## Inhalt\nA.[^b1]\nB.[^b2]\n\n"
                     f"[^b1]: {_cite(svc, doc_id, 'Regeln')}\n[^b2]: {_cite(svc, doc_id, 'Rollen')}\n")
    target = f"id:{doc_id}"
    svc.edit_document(target=target, old="Zwei Rollen.", new="Drei Rollen.", expected_hash=svc.read(target)["hash"])
    res = raise_versions(svc)
    assert res["pages_changed"] == 1 and [c["id"] for c in res["changes"][0]["changes"]] == ["b1"]
    defs = parse_page(svc.vault.load(page)).definitions
    assert defs["b1"].version == 2 and defs["b2"].version == 1
    assert raise_versions(svc)["pages_changed"] == 0

# Main ************************************************************************
