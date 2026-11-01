"""Abnahme (Spezifikation 14) als Simulation: jeder Schritt mit den echten Tools und der CLI.

Die Aufrufe des Chats bzw. Pflege-Agenten werden hier direkt ausgeführt. Geprüft wird, dass die
Werkzeuge jeden Schritt tragen; das Verhalten des LLM prüft die manuelle Abnahme (docs/abnahme.md).
"""

import json

from pkm.cli import main
from pkm.service import Service

from .conftest import git, write

FIRST = ("## Ergebnis\nDer Überlauf wird per Ultraschallsensor erkannt.\n\n"
         "## Entscheidungen\n- Ultraschallsensor am Deckel\n\n"
         "## Offene Punkte\n- Kabelweg\n- Montageort\n\n"
         "## Kontext / Begründung\nDachfläche laut Plan 92 m².\n")
SECOND = ("## Ergebnis\nDer Überlauf wird per Schwimmerschalter erkannt.\n\n"
          "## Entscheidungen\n- Schwimmerschalter statt Ultraschall\n\n"
          "## Offene Punkte\n- Kabelweg\n\n"
          "## Kontext / Begründung\nDachfläche laut Plan 92 m². Der Deckel beschlägt oft.\n")


def cli(capsys, *argv):
    code = main(list(argv))
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    return out


def cite(sha, link, key, quote):
    return f"[[{link}#{key}]] · „{quote}“ · id:{sha['id']} · v:{sha['version']} · sha:{sha['sha']}"


def write_wiki(cfg, capsys, link, lines_extra=""):
    ent = cli(capsys, "sha", f"[[{link}]]", "--section", "Entscheidungen")
    ctx = cli(capsys, "sha", f"[[{link}]]", "--section", "Kontext / Begründung")
    quote_ent = "Schwimmerschalter statt Ultraschall" if ent["version"] > 1 else "Ultraschallsensor am Deckel"
    page = f"""---
type: topic
title: Zisterne
sources: []
updated: 2026-11-02
confidence: high
---

> **Kurzfassung:** Überlaufsensor und Dach der Zisterne.

## Inhalt
Die Dachfläche beträgt 92 m².[^b1]
Der Überlauf wird erkannt mit: {quote_ent}.[^b2]
{lines_extra}
## Siehe auch
- [[wiki/summaries/ueberlaufsensor]]

## Belege
[^b1]: {cite(ctx, link, 'Kontext / Begründung', 'Dachfläche laut Plan 92 m²')}
[^b2]: {cite(ent, link, 'Entscheidungen', quote_ent)}
"""
    write(cfg, "wiki/topics/zisterne.md", page)
    summary = f"""---
type: summary
title: Überlaufsensor
sources: []
updated: 2026-11-02
confidence: high
---

> **Kurzfassung:** Entscheidung zum Überlaufsensor.

## Inhalt
Entschieden: {quote_ent}.[^b1]

## Siehe auch
- [[wiki/topics/zisterne]]

## Belege
[^b1]: {cite(ent, link, 'Entscheidungen', quote_ent)}
"""
    write(cfg, "wiki/summaries/ueberlaufsensor.md", summary)
    return ent


def finish_run(capsys, doc_id, message):
    cli(capsys, "sync-citations")
    cli(capsys, "mark", doc_id, "--pages", "wiki/topics/zisterne", "wiki/summaries/ueberlaufsensor")
    cli(capsys, "index")
    cli(capsys, "status")
    lint = cli(capsys, "lint")
    assert lint["summary"]["error"] == 0, lint["findings"]
    assert cli(capsys, "commit-wiki", "-m", message)["status"] == "ok"


def test_acceptance_steps_1_to_10(cfg, isolated_env, capsys, monkeypatch):
    svc = Service(cfg)
    monkeypatch.chdir(cfg.root)

    # 1. Ablegen aus dem Chat (nach Suche und bestätigtem Entwurf)
    assert svc.search("Überlaufsensor", scope="documents")["results"] == []
    doc = svc.create_document(title="Zisterne – Überlaufsensor", content=FIRST, topics=["zisterne"],
                              context="Chat: Überlaufsensor")
    assert doc["path"].startswith("documents/_inbox/") and doc["version"] == 1
    assert git(isolated_env, "show", "--name-only", "--format=%s", "HEAD").split("\n")[0].endswith(" v1")
    doc_id = doc["id"]

    # 2. Erster Pflegelauf
    assert cli(capsys, "doctor", "--short")["status"] == "ok"
    cli(capsys, "versions")
    cli(capsys, "ids")
    assert [i["id"] for i in cli(capsys, "pending")["new"]] == [doc_id]
    write_wiki(cfg, capsys, doc["path"][:-3])
    finish_run(capsys, doc_id, "pkm: ingest 1 documents")
    files = git(isolated_env, "show", "--name-only", "--format=", "HEAD").split()
    assert all(f.startswith("wiki/") or f == ".pkm/state.json" for f in files)

    # 3. Einsortieren in Obsidian: Datei verschoben, Obsidian schreibt die Links um
    (cfg.root / "documents/haus").mkdir()
    (cfg.root / doc["path"]).rename(cfg.root / "documents/haus/ueberlaufsensor.md")
    for page in ("wiki/topics/zisterne.md", "wiki/summaries/ueberlaufsensor.md"):
        p = cfg.root / page
        p.write_text(p.read_text().replace(doc["path"][:-3], "documents/haus/ueberlaufsensor"))
    checks = {f["check"] for f in cli(capsys, "lint")["findings"]}
    assert "citation_moved" not in checks and "citation_missing" not in checks

    # 4. Fortsetzung in neuem Chat: finden, lesen, neu fassen
    hits = svc.search("Überlaufsensor", scope="documents")["results"]
    assert hits[0]["id"] == doc_id and hits[0]["path"] == "documents/haus/ueberlaufsensor.md"
    cur = svc.read(f"id:{doc_id}")
    r = svc.rewrite_document(target=f"id:{doc_id}", content=SECOND, expected_hash=cur["hash"],
                             note="Sensor: Schwimmerschalter statt Ultraschall")
    assert r["version"] == 2 and "Fortsetzung" not in svc.read(f"id:{doc_id}")["content"]

    # 5. Verlauf
    hist = svc.history(f"id:{doc_id}", diff_from=1)
    versions = [(v["version"], v["note"]) for v in hist["versions"] if not v["subject"].endswith(" moved")]
    assert versions[-1] == (2, "Sensor: Schwimmerschalter statt Ultraschall")
    assert "+- Schwimmerschalter statt Ultraschall" in hist["diff"]

    # 6. Zweiter Pflegelauf: nur geänderte Abschnitte, „Bis Version 1“ mit Beleg auf v1
    cli(capsys, "versions")
    changed = cli(capsys, "pending")["changed"][0]
    assert changed["processed_version"] == 1 and changed["version"] == 2
    assert {c["key"] for c in changed["sections"]} == {"Ergebnis", "Entscheidungen", "Offene Punkte",
                                                      "Kontext / Begründung"}
    old_ent = {"id": doc_id, "version": 1,
               "sha": cli(capsys, "show", f"id:{doc_id}", "--version", "1", "--section", "Entscheidungen")[
                   "section_hash"][:6]}
    extra = "Bis Version 1: Ultraschallsensor am Deckel.[^b3]\n"
    write_wiki(cfg, capsys, "documents/haus/ueberlaufsensor", extra)
    p = cfg.root / "wiki/topics/zisterne.md"
    p.write_text(p.read_text() + "[^b3]: " + cite(old_ent, "documents/haus/ueberlaufsensor", "Entscheidungen",
                                                  "Ultraschallsensor am Deckel") + "\n")
    finish_run(capsys, doc_id, "pkm: ingest 1 documents")

    # 7. Quellen
    res = svc.show_citations("wiki/topics/zisterne", statement="Dachfläche beträgt", with_excerpt=True)
    c = res["citations"][0]
    assert (c["original"], c["section"], c["status"]) == ("documents/haus/ueberlaufsensor.md", "Kontext / Begründung", "ok")
    old = {x["id"]: x for x in svc.show_citations("wiki/topics/zisterne")["citations"]}["b3"]
    assert old["cited_version"] == 1 and old["status"] == "newer_version"

    # 8. Fortsetzung als datierter Abschnitt (nur auf Anweisung)
    cur = svc.read(f"id:{doc_id}")
    r = svc.append_to_document(target=f"id:{doc_id}", expected_hash=cur["hash"], section="Fortsetzung 2026-11-03",
                               text="### Ergebnis\nSchwimmerschalter mit 5 m Kabel bestellen.")
    assert "## Fortsetzung 2026-11-03" in svc.read(f"id:{doc_id}")["content"] and r["version"] == 3

    # 9. Änderung auf Windows (CRLF, Obsidian) → Version mit PKM-Source: user
    path = cfg.root / "documents/haus/ueberlaufsensor.md"
    path.write_bytes(path.read_bytes().replace(b"- Kabelweg\n", b"- Kabelweg\n- Frostschutz\n").replace(b"\n", b"\r\n"))
    committed = cli(capsys, "versions")["committed"]
    assert committed[0]["version"] == 4
    assert "PKM-Source: user" in git(isolated_env, "log", "-1", "--format=%B")
    assert b"\r\n" not in path.read_bytes()
    pend = cli(capsys, "pending")["changed"][0]
    assert {c["key"] for c in pend["sections"]} == {"Offene Punkte", "Fortsetzung 2026-11-03"}

    # 10. Doctor und Lint ohne Fehler
    write_wiki(cfg, capsys, "documents/haus/ueberlaufsensor", extra)
    p.write_text(p.read_text() + "[^b3]: " + cite(old_ent, "documents/haus/ueberlaufsensor", "Entscheidungen",
                                                  "Ultraschallsensor am Deckel") + "\n")
    finish_run(capsys, doc_id, "pkm: ingest 1 documents")
    assert cli(capsys, "doctor")["errors"] == 0
    assert cli(capsys, "lint")["summary"]["error"] == 0
    assert git(isolated_env, "status", "--porcelain").strip() == ""
    assert not (cfg.root / ".git").exists()
