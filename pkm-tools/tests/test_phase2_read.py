"""Vault, Adressierung, Suchindex und lesende Tools (Spezifikation 7.1, 7.3, 7.4)."""

import sqlite3

import pytest

from pkm.errors import PkmError
from pkm.service import Service

from .conftest import commit_doc, write

ID1 = "d-20261031-2340-k7q2"
ID2 = "d-20261101-0700-q4rt"

DOC1 = f"""---
id: {ID1}
version: 1
title: Zisterne – Überlaufsensor
topics: [zisterne, sensor]
---

## Ergebnis
Der Überlauf wird per Schwimmerschalter erkannt.

## Offene Punkte
- Montageort klären
"""

WIKI = """---
type: topic
title: Regenwasser-Ertrag
aliases: [Regenertrag]
tags: [wasser]
---

> **Kurzfassung:** Ertrag des Daches in Litern pro Millimeter.

## Inhalt
Die Dachfläche beträgt 92 m².[^b1] Siehe [[documents/haus/zisterne]].

## Belege
[^b1]: [[documents/haus/zisterne#Dach]] · „Dachfläche 92 m²“ · id:d-20261012-0915-x7mp · v:2 · sha:3f9a1c
"""


@pytest.fixture
def filled(cfg, svc):
    commit_doc(cfg, "documents/haus/zisterne.md", DOC1, ID1, 1)
    write(cfg, "documents/notiz.md", "Lose Notiz ohne Frontmatter über Bewässerung.\n")
    write(cfg, "documents/haus/datenblatt.pdf", "%PDF-1.4 fake")
    write(cfg, "wiki/topics/regenwasser-ertrag.md", WIKI)
    return svc


# --- Adressierung ---
@pytest.mark.parametrize(
    "target",
    ["documents/haus/zisterne.md", "documents/haus/zisterne", "[[documents/haus/zisterne]]",
     "[[zisterne]]", "zisterne", "ZISTERNE", f"id:{ID1}", "[[zisterne#Ergebnis|Alias]]"],
)
def test_resolve(filled, target):
    assert filled.resolve(target) == "documents/haus/zisterne.md"


def test_resolve_ambiguous(filled, cfg):
    write(cfg, "documents/alt/zisterne.md", "alt\n")
    with pytest.raises(PkmError) as e:
        filled.resolve("[[zisterne]]")
    assert e.value.status == "ambiguous"
    assert e.value.data["candidates"] == ["documents/alt/zisterne.md", "documents/haus/zisterne.md"]


def test_resolve_not_found_and_outside(filled):
    with pytest.raises(PkmError) as e:
        filled.resolve("gibtsnicht")
    assert e.value.status == "not_found"
    with pytest.raises(PkmError):
        filled.resolve("../etc/passwd")
    with pytest.raises(PkmError) as e:
        filled.resolve("CLAUDE.md")
    assert e.value.status in ("not_found", "forbidden")
    with pytest.raises(PkmError) as e:
        filled.resolve(".pkm/state.json")
    assert e.value.status in ("not_found", "forbidden")


def test_resolve_id_after_move(filled, cfg):
    (cfg.root / "documents/haus/zisterne.md").rename(cfg.root / "documents/zisterne-neu.md")
    assert filled.resolve(f"id:{ID1}") == "documents/zisterne-neu.md"


def test_resolve_id_without_index(cfg, isolated_env, monkeypatch):
    commit_doc(cfg, "documents/a.md", DOC1, ID1, 1)
    monkeypatch.setenv("PKM_CACHE_DIR", str(isolated_env["root"] / ".pkm" / "cache"))
    from pkm.config import Config

    s = Service(Config.from_env())
    assert s.resolve(f"id:{ID1}") == "documents/a.md"
    with pytest.raises(PkmError) as e:
        s.search("Zisterne")
    assert e.value.status == "index_unavailable"
    assert not (isolated_env["root"] / ".pkm" / "cache" / "index.db").exists()


# --- Suche ---
def test_search_wiki_default(filled):
    res = filled.search("Regenertrag")
    assert [r["path"] for r in res["results"]] == ["wiki/topics/regenwasser-ertrag.md"]
    r = res["results"][0]
    assert r["summary"] == "Ertrag des Daches in Litern pro Millimeter."
    assert r["type"] == "topic"
    assert "version" not in r


def test_search_documents_with_processed(filled):
    res = filled.search("schwimmer", scope="documents")
    r = res["results"][0]
    assert r["path"] == "documents/haus/zisterne.md"
    assert r["id"] == ID1 and r["version"] == 1 and r["processed"] is False
    assert "Schwimmerschalter" in r["snippet"]


@pytest.mark.parametrize("q", ["Überlauf", "uberlauf", "Ueberlauf", "überl", "ÜBERLAUF"])
def test_search_umlaut_tolerance(filled, q):
    paths = [r["path"] for r in filled.search(q, scope="documents")["results"]]
    assert "documents/haus/zisterne.md" in paths


def test_search_weighting(filled, cfg):
    write(cfg, "documents/text.md", "# Andere\n\nHier steht nebenbei das Wort Zisterne im Text.\n")
    res = filled.search("zisterne", scope="documents")["results"]
    assert res[0]["path"] == "documents/haus/zisterne.md"


def test_search_limits_and_scope(filled):
    assert filled.search("a", max_results=999)  # wird auf 25 begrenzt, kein Fehler
    with pytest.raises(PkmError):
        filled.search("x", scope="falsch")
    assert filled.search("   ")["results"] == []


def test_search_incremental_and_rebuild(filled, cfg):
    assert filled.search("Kolibri", scope="all")["results"] == []
    write(cfg, "documents/vogel.md", "Ein Kolibri.\n")
    assert [r["path"] for r in filled.search("kolibri", scope="all")["results"]] == ["documents/vogel.md"]
    (cfg.root / "documents/vogel.md").unlink()
    assert filled.search("kolibri", scope="all")["results"] == []
    cfg.index_path.write_bytes(b"kaputt" * 100)
    assert filled.search("Regenertrag")["results"]
    cfg.index_path.unlink()
    assert filled.search("Regenertrag")["results"]


def test_index_schema_mismatch_rebuilds(filled, cfg):
    filled.search("x")
    con = sqlite3.connect(cfg.index_path)
    con.execute("UPDATE info SET value='0' WHERE key='schema'")
    con.commit()
    con.close()
    assert filled.search("Regenertrag")["results"]


def test_reindex(filled):
    res = filled.reindex()
    assert res["total"] == 7  # 3 Dokumente, 1 Wiki-Seite, index/log/_status


# --- read ---
def test_read_document(filled):
    r = filled.read("[[zisterne]]")
    assert r["id"] == ID1 and r["version"] == 1 and r["editable"] is True
    assert r["frontmatter"]["title"] == "Zisterne – Überlaufsensor"
    assert r["content"].startswith("\n## Ergebnis")
    assert [s["key"] for s in r["sections"]] == ["Ergebnis", "Offene Punkte"]
    assert len(r["hash"]) == 64
    assert r["backlinks"] == ["wiki/topics/regenwasser-ertrag.md"]


def test_read_wiki_not_editable(filled):
    r = filled.read("wiki/topics/regenwasser-ertrag")
    assert r["editable"] is False
    assert [(c["id"], c["path"], c["version"], c["sha"]) for c in r["citations"]] == [
        ("b1", "documents/haus/zisterne", 2, "3f9a1c")]
    assert r["links"] == ["documents/haus/zisterne"]


def test_read_pdf(filled):
    r = filled.read("documents/haus/datenblatt.pdf")
    assert r["kind"] == "binary" and len(r["hash"]) == 64 and r["editable"] is False


def test_read_invalid_frontmatter(filled, cfg):
    write(cfg, "documents/kaputt.md", "---\ntitle: [x\n---\nText\n")
    r = filled.read("kaputt")
    assert r["status"] == "invalid_frontmatter" and r["editable"] is False and "Text" in r["content"]


def test_read_invalid_encoding(filled, cfg):
    (cfg.root / "documents/bin.md").write_bytes(b"\xff\xfe")
    r = filled.read("documents/bin.md")
    assert r["status"] == "invalid_encoding" and r["editable"] is False


def test_read_old_version(filled, cfg):
    commit_doc(cfg, "documents/haus/zisterne.md", DOC1.replace("version: 1", "version: 2").replace(
        "Schwimmerschalter", "Ultraschall"), ID1, 2)
    old = filled.read(f"id:{ID1}", version=1)
    assert "Schwimmerschalter" in old["content"] and old["editable"] is False and old["version"] == 1
    with pytest.raises(PkmError):
        filled.read(f"id:{ID1}", version=9)


# --- history ---
def test_history_with_diff_after_move(filled, cfg):
    from pkm.gitlayer import Git, build_message

    (cfg.root / "documents/neu").mkdir()
    (cfg.root / "documents/haus/zisterne.md").rename(cfg.root / "documents/neu/z.md")
    write(cfg, "documents/neu/z.md", DOC1.replace("version: 1", "version: 2").replace("klären", "geklärt"))
    Git(cfg.git_dir, cfg.root).commit_paths(
        ["documents/haus/zisterne.md", "documents/neu/z.md"],
        build_message("Z", "v2", "Montageort geklärt", ID1, 2, "user"),
    )
    h = filled.history("[[z]]", diff_from=1)
    assert [v["version"] for v in h["versions"]] == [1, 2]
    assert h["versions"][1]["note"] == "Montageort geklärt" and h["versions"][1]["source"] == "user"
    assert h["versions"][0]["path"] == "documents/haus/zisterne.md"
    assert "-- Montageort klären" in h["diff"] and "+- Montageort geklärt" in h["diff"]
    assert h["diff_to"] == 2


def test_history_deleted_document_by_id(filled, cfg):
    (cfg.root / "documents/haus/zisterne.md").unlink()
    h = filled.history(f"id:{ID1}")
    assert h["path"] is None and h["versions"][0]["version"] == 1


def test_show_section(filled):
    r = filled.show(f"id:{ID1}", 1, "Offene Punkte")
    assert r["content"] == "## Offene Punkte\n- Montageort klären"


# --- read_index / list_unprocessed ---
def test_read_index(filled):
    assert filled.read_index()["content"].startswith("# Wiki-Index")


def test_list_unprocessed(filled, cfg):
    import json

    from pkm import hashes as H

    res = filled.list_unprocessed()
    cats = {d["path"]: d["category"] for d in res["documents"]}
    assert cats["documents/haus/zisterne.md"] == "new"
    assert cats["documents/haus/datenblatt.pdf"] == "new"
    doc = filled.vault.load("documents/haus/zisterne.md")
    state = {"version": 1, "documents": {ID1: {
        "path": doc.rel, "processed_version": 1, "file_hash": doc.hashes.file_hash,
        "body_hash": doc.hashes.body_hash, "meta_hash": doc.hashes.meta_hash,
        "sections": dict(doc.hashes.sections)}}}
    cfg.state_path.write_text(json.dumps(state))
    res = filled.list_unprocessed()
    assert "documents/haus/zisterne.md" not in {d["path"] for d in res["documents"]}
    write(cfg, "documents/haus/zisterne.md", DOC1.replace("klären", "prüfen").replace("## Ergebnis", "## Resultat"))
    entry = next(d for d in filled.list_unprocessed()["documents"] if d["id"] == ID1)
    assert entry["category"] == "changed" and entry["processed_version"] == 1
    assert {(c["key"], c["change"]) for c in entry["sections"]} == {("Offene Punkte", "changed"), ("Resultat", "renamed")}
    write(cfg, "documents/haus/zisterne.md", DOC1.replace("topics: [zisterne, sensor]", "topics: [zisterne]"))
    entry = next(d for d in filled.list_unprocessed()["documents"] if d["id"] == ID1)
    assert entry["category"] == "meta_changed"
    assert H.short("abcdef12") == "abcdef"
