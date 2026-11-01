"""Pflege-CLI (Spezifikation 4.3, 4.4, 4.6, 4.8 „Was daraus folgt“, 5.3, 5.4, 8)."""

import json

import pytest

from pkm.cli import main
from pkm.errors import PkmError
from pkm.maint import Maintenance

from .conftest import git, write

DOC = """---
title: Bewässerung
topics: [garten]
---

## Ergebnis
Täglich 10 Minuten.

## Offene Punkte
- Zeitplan
"""


@pytest.fixture
def m(svc):
    return Maintenance(svc)


def subjects(env, n=None):
    args = ["log", "--format=%s"] + ([f"-{n}"] if n else [])
    return git(env, *args).strip().splitlines()


# ---------------------------------------------------------------- ids
def test_ids_assigns_and_commits_each(m, cfg, isolated_env):
    write(cfg, "documents/a.md", "# A\n\nText a\n")
    write(cfg, "documents/haus/b.md", DOC)
    write(cfg, "documents/c.md", "---\nid: d-20261031-2340-k7q2\ntitle: C\n---\nText\n")
    res = m.ids()
    assert len(res["assigned"]) == 3
    assert set(subjects(isolated_env, 3)) == {"doc: C v1", "doc: Bewässerung v1", "doc: A v1"}
    for rel in ("documents/a.md", "documents/haus/b.md", "documents/c.md"):
        assert git(isolated_env, "status", "--porcelain", "--", rel) == ""
    a = (cfg.root / "documents/a.md").read_text(encoding="utf-8")
    assert a.endswith("---\n# A\n\nText a\n") and "version: 1" in a
    assert "id: d-20261031-2340-k7q2" in (cfg.root / "documents/c.md").read_text()
    body = git(isolated_env, "log", "-1", "--format=%B")
    assert "PKM-Source: agent" in body and "PKM-Version: 1" in body
    for sha in git(isolated_env, "log", "-3", "--format=%H").split():
        assert len(git(isolated_env, "show", "--name-only", "--format=", sha).split()) == 1
    assert m.ids()["assigned"] == []


def test_ids_keeps_rest_bytes_and_comments(m, cfg):
    text = "---\ntitle: X  # Kommentar\ntopics: [a]\n---\n\nInhalt  mit  Leerzeichen\n"
    write(cfg, "documents/x.md", text)
    m.ids()
    out = (cfg.root / "documents/x.md").read_text(encoding="utf-8")
    assert out.startswith("---\ntitle: X  # Kommentar\ntopics: [a]\nid: d-")
    assert out.endswith("version: 1\n---\n\nInhalt  mit  Leerzeichen\n")


def test_ids_reports_duplicates_and_skips_invalid(m, cfg):
    write(cfg, "documents/a.md", "---\nid: d-20261031-2340-k7q2\nversion: 1\n---\nA\n")
    write(cfg, "documents/kopie.md", "---\nid: d-20261031-2340-k7q2\nversion: 1\n---\nA\n")
    write(cfg, "documents/kaputt.md", "---\ntitle: [x\n---\n")
    res = m.ids()
    assert res["duplicates"] == [{"id": "d-20261031-2340-k7q2", "paths": ["documents/a.md", "documents/kopie.md"]}]
    assert {"path": "documents/kaputt.md", "reason": "invalid_frontmatter"} in res["skipped"]


def test_ids_skips_conflict_copies(m, cfg):
    write(cfg, "documents/n (conflicted copy 2026-11-01).md", "Text\n")
    res = m.ids()
    assert res["assigned"] == []
    assert res["problems"][0]["problem"] == "conflict_copy"


# ----------------------------------------------------------- versions
@pytest.fixture
def created(svc):
    return svc.create_document(title="Sensor", content="## Ergebnis\nA\n\n## Offene Punkte\n- x\n", topics=["zisterne"])


def test_versions_combines_hand_edits(m, svc, cfg, created, isolated_env):
    p = cfg.root / created["path"]
    p.write_text(p.read_text().replace("A\n", "B\n"))
    p.write_text(p.read_text().replace("B\n", "C\n"))
    res = m.versions()
    assert [c["version"] for c in res["committed"]] == [2]
    hist = svc.history(created["path"])["versions"]
    assert [(v["version"], v["source"]) for v in hist] == [(1, "chat"), (2, "user")]
    assert git(isolated_env, "status", "--porcelain").strip() == ""
    assert m.versions()["committed"] == []


def test_versions_pure_move_no_version_bump(m, svc, cfg, created, isolated_env):
    (cfg.root / "documents/haus").mkdir()
    (cfg.root / created["path"]).rename(cfg.root / "documents/haus/sensor.md")
    res = m.versions()
    assert res["committed"][0]["subject"] == "doc: Sensor moved" and res["committed"][0]["version"] == 1
    files = git(isolated_env, "show", "--name-status", "--no-renames", "--format=", "HEAD").split()
    assert set(files) == {"A", "documents/haus/sensor.md", "D", created["path"]}
    assert git(isolated_env, "status", "--porcelain").strip() == ""


def test_versions_move_and_change(m, svc, cfg, created, isolated_env):
    (cfg.root / "documents/haus").mkdir()
    (cfg.root / created["path"]).rename(cfg.root / "documents/haus/sensor.md")
    p = cfg.root / "documents/haus/sensor.md"
    p.write_text(p.read_text().replace("A\n", "Neu\n"))
    res = m.versions()
    assert res["committed"][0]["version"] == 2
    assert git(isolated_env, "status", "--porcelain").strip() == ""
    assert [v["path"] for v in svc.history(f"id:{created['id']}")["versions"]] == [created["path"], "documents/haus/sensor.md"]


def test_versions_crlf_from_windows_counts_as_change_only_if_content(m, svc, cfg, created):
    p = cfg.root / created["path"]
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    # Datei weicht byteweise ab, Inhalt (normalisiert) gleich → trotzdem Version, Datei wird LF
    res = m.versions()
    assert len(res["committed"]) == 1
    assert b"\r\n" not in p.read_bytes()


def test_versions_binaries_and_deletions(m, cfg, isolated_env, created):
    write(cfg, "documents/blatt.pdf", "%PDF-1")
    res = m.versions()
    assert res["committed"][0]["path"] == "documents/blatt.pdf"
    (cfg.root / "documents/haus").mkdir()
    (cfg.root / "documents/blatt.pdf").rename(cfg.root / "documents/haus/blatt.pdf")
    res = m.versions()
    assert res["committed"][0]["moved_from"] == "documents/blatt.pdf"
    (cfg.root / created["path"]).unlink()
    res = m.versions()
    assert res["committed"][0]["deleted"] is True
    assert subjects(isolated_env, 1) == ["doc: Sensor deleted"]
    assert git(isolated_env, "status", "--porcelain").strip() == ""


def test_versions_skips_conflict_copy_and_missing_id(m, cfg):
    write(cfg, "documents/x (Konflikt).md", "x\n")
    write(cfg, "documents/ohne.md", "ohne id\n")
    res = m.versions()
    reasons = {s["path"]: s["reason"] for s in res["skipped"]}
    assert reasons == {"documents/x (Konflikt).md": "conflict_copy", "documents/ohne.md": "missing_id"}


# ------------------------------------------------------- pending / mark
def test_pending_lifecycle(m, svc, cfg, created):
    pend = m.pending()
    assert [i["id"] for i in pend["new"]] == [created["id"]]
    m.mark([created["id"]], pages=["wiki/index.md"])
    state = json.loads(cfg.state_path.read_text())
    entry = state["documents"][created["id"]]
    assert entry["processed_version"] == 1 and entry["wiki_pages"] == ["wiki/index"]
    assert set(entry["sections"]) == {"Ergebnis", "Offene Punkte"} and len(entry["body_hash"]) == 64
    assert m.pending()["counts"] == {"new": 0, "changed": 0, "meta_changed": 0, "moved": 0, "deleted": 0}

    # nur updated/version geändert → nichts zu tun
    r = svc.update_frontmatter(target=created["path"], expected_hash=created["new_hash"], set={"context": "x"})
    assert m.pending()["counts"]["meta_changed"] == 0  # context zählt nicht zu meta_hash
    # Abschnitt umbenannt + geändert + neu
    svc.rewrite_document(target=created["path"], expected_hash=r["new_hash"], confirm_shortening=True,
                         content="## Resultat\nA\n\n## Offene Punkte\n- y\n\n## Neu\nz\n")
    item = m.pending()["changed"][0]
    assert item["processed_version"] == 1 and item["version"] == 3
    assert {(c["key"], c["change"]) for c in item["sections"]} == {
        ("Resultat", "renamed"), ("Offene Punkte", "changed"), ("Neu", "added")}
    assert next(c for c in item["sections"] if c["change"] == "renamed")["from"] == "Ergebnis"


def test_pending_order_only_and_meta(m, svc, cfg, created):
    m.mark([created["id"]])
    r = svc.rewrite_document(target=created["path"], expected_hash=created["new_hash"],
                             content="## Offene Punkte\n- x\n\n## Ergebnis\nA\n")
    item = m.pending()["changed"][0]
    assert item["sections"] == []
    m.mark([created["id"]])
    svc.update_frontmatter(target=created["path"], expected_hash=r["new_hash"], add={"topics": ["neu"]})
    assert m.pending()["meta_changed"][0]["id"] == created["id"]


def test_pending_removed_section_and_dup_rename(m, svc, created):
    m.mark([created["id"]])
    svc.rewrite_document(target=created["path"], expected_hash=created["new_hash"], confirm_shortening=True,
                         content="## Ergebnis\nA\n")
    assert m.pending()["changed"][0]["sections"] == [{"key": "Offene Punkte", "change": "removed"}]


def test_pending_dup_numbering_shift_is_rename(m, svc):
    d = svc.create_document(title="Dup", content="## Notizen\na\n## Notizen\nb\n")
    m.mark([d["id"]])
    svc.edit_document(target=d["path"], old="## Notizen\na\n", new="", expected_hash=d["new_hash"])
    secs = m.pending()["changed"][0]["sections"]
    assert {"key": "Notizen", "change": "renamed", "from": "Notizen#2"} in secs
    assert {"key": "Notizen", "change": "removed"} in secs


def test_pending_moved_deleted_and_binaries(m, svc, cfg, created):
    write(cfg, "documents/blatt.pdf", "%PDF-1")
    m.mark([created["id"], "documents/blatt.pdf"], pages=["wiki/index"])
    (cfg.root / "documents/haus").mkdir()
    (cfg.root / created["path"]).rename(cfg.root / "documents/haus/s.md")
    (cfg.root / "documents/blatt.pdf").rename(cfg.root / "documents/haus/blatt.pdf")
    pend = m.pending()
    moved = {(i["from"], i["to"]) for i in pend["moved"]}
    assert (created["path"], "documents/haus/s.md") in moved
    assert ("documents/blatt.pdf", "documents/haus/blatt.pdf") in moved
    assert pend["counts"]["changed"] == 0
    (cfg.root / "documents/haus/blatt.pdf").write_bytes(b"%PDF-2")  # neue Fassung = neues Dokument
    pend = m.pending()
    assert pend["counts"]["new"] == 1 and pend["deleted"][0]["key"].startswith("sha:")
    assert pend["deleted"][0]["wiki_pages"] == ["wiki/index"]
    res = m.mark([pend["deleted"][0]["key"]], remove=True)
    assert res["marked"][0]["removed"]


def test_pending_moved_and_changed(m, svc, cfg, created):
    m.mark([created["id"]])
    (cfg.root / "documents/neu.md").write_text((cfg.root / created["path"]).read_text().replace("A\n", "B\n"))
    (cfg.root / created["path"]).unlink()
    pend = m.pending()
    assert pend["moved"][0]["to"] == "documents/neu.md"
    assert pend["changed"][0]["sections"] == [{"key": "Ergebnis", "change": "changed"}]


def test_pending_duplicates_problem(m, svc, cfg, created):
    m.mark([created["id"]])
    (cfg.root / "documents/kopie.md").write_text((cfg.root / created["path"]).read_text())
    pend = m.pending()
    assert any(p["problem"] == "duplicate_id" for p in pend["problems"])
    assert pend["counts"]["new"] == 0 and pend["counts"]["moved"] == 0


def test_mark_rejects_unknown(m):
    with pytest.raises(PkmError):
        m.mark(["d-20261031-2340-k7q2"])


# ---------------------------------------------------------------- sha
def test_sha(m, created):
    res = m.sha(created["path"])
    assert set(res["sections"]) == {"Ergebnis", "Offene Punkte"} and len(res["file_hash"]) == 6
    one = m.sha(f"id:{created['id']}", section="## Ergebnis", full=True)
    assert len(one["sha"]) == 64 and one["sha"].startswith(res["sections"]["Ergebnis"])
    with pytest.raises(PkmError):
        m.sha(created["path"], section="Fehlt")


# ------------------------------------------------------- index/status
WIKI_TOPIC = """---
type: topic
title: Regenwasser-Ertrag
sources:
  - "[[documents/a]]"
  - "[[documents/b]]"
updated: 2026-11-02
---

> **Kurzfassung:** Ertrag in L/mm.

## Inhalt
"""


def test_index(svc, cfg):
    from pkm.wikigen import build_index

    write(cfg, "wiki/topics/regenwasser-ertrag.md", WIKI_TOPIC)
    write(cfg, "wiki/entities/tank-1.md", "---\ntype: entity\ntitle: Tank 1\n---\n\n> Der Tank.\n")
    write(cfg, "wiki/summaries/x.md", "---\ntitle: X\n---\nkeine Kurzfassung\n")
    res = build_index(svc)
    text = (cfg.root / "wiki/index.md").read_text()
    assert res["pages"] == 3 and res["changed"]
    assert "## Themen\n\n- [[wiki/topics/regenwasser-ertrag]] – Ertrag in L/mm. _(2 Quellen, 2026-11-02)_" in text
    assert "## Entitäten\n\n- [[wiki/entities/tank-1]] – Der Tank. _(0 Quellen)_" in text
    assert "## Zusammenfassungen\n\n- [[wiki/summaries/x]] – _(keine Kurzfassung)_" in text
    assert build_index(svc)["changed"] is False


def test_status(svc, m, cfg, created):
    from pkm.wikigen import build_status

    write(cfg, "documents/haus/alt.md", "---\nid: d-20261031-2340-abcd\nversion: 1\ntopics: [zisterne]\n---\nx\n")
    write(cfg, "documents/n (conflicted copy).md", "x\n")
    build_status(svc)
    text = (cfg.root / "wiki/_status.md").read_text()
    assert f"## Noch nicht verarbeitet (2)\n- [[{created['path'][:-3]}]] – neu (v1)" in text
    assert "Konfliktkopie: documents/n (conflicted copy).md" in text
    m.mark([created["id"], "d-20261031-2340-abcd"])
    build_status(svc, ["Wohin mit dem Sensor-Dokument?"])
    text = (cfg.root / "wiki/_status.md").read_text()
    assert "## Noch nicht verarbeitet (0)" in text
    assert f"- [[{created['path'][:-3]}]] → Vorschlag: documents/haus/" in text
    assert "## Rückfragen (1)\n- Wohin mit dem Sensor-Dokument?" in text


def test_status_changed_line(svc, m, cfg, created):
    from pkm.wikigen import build_status

    m.mark([created["id"]])
    svc.edit_document(target=created["path"], old="- x", new="- y", expected_hash=created["new_hash"])
    build_status(svc)
    assert "– v1 → v2, geändert: „Offene Punkte“" in (cfg.root / "wiki/_status.md").read_text()


# --------------------------------------------------------- commit-wiki
def test_commit_wiki_only_wiki_and_state(m, cfg, isolated_env, created):
    write(cfg, "documents/offen.md", "offen\n")
    write(cfg, "wiki/topics/t.md", "---\ntype: topic\n---\n> K\n")
    m.mark([created["id"]])
    res = m.commit_wiki("ingest 1 documents")
    assert res["status"] == "ok"
    files = git(isolated_env, "show", "--name-only", "--format=", "HEAD").split()
    assert set(files) == {"wiki/topics/t.md", ".pkm/state.json"}
    assert subjects(isolated_env, 1) == ["pkm: ingest 1 documents"]
    assert "PKM-Source: agent" in git(isolated_env, "log", "-1", "--format=%B")
    assert "documents/offen.md" in git(isolated_env, "status", "--porcelain")
    assert m.commit_wiki("lint")["status"] == "unchanged"


# ---------------------------------------------------------------- CLI
def test_cli_commands(cfg, capsys, created):
    for argv in (["ids"], ["versions"], ["pending"], ["sha", created["path"]], ["index"], ["status"],
                 ["mark", created["id"], "--pages", "wiki/index"], ["commit-wiki", "-m", "pkm: lint"]):
        assert main(argv) == 0, argv
        out = json.loads(capsys.readouterr().out)
        assert out["status"] in ("ok", "unchanged")
