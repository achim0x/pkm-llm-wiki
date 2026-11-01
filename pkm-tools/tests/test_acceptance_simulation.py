"""Abnahme (Spezifikation 14) als Simulation: jeder Schritt mit den echten Tools und der CLI.

Die Aufrufe des Chats bzw. Pflege-Agenten werden hier direkt ausgeführt. Geprüft wird, dass die
Werkzeuge jeden Schritt tragen; das Verhalten des LLM prüft die manuelle Abnahme (docs/abnahme.md).

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

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from pkm.cli import main
from pkm.config import Config
from pkm.service import Service

from .conftest import git, write

# Variables *******************************************************************

SORTED = "documents/haus/ueberlaufsensor.md"

FIRST = ("## Ergebnis\nDer Überlauf wird per Ultraschallsensor erkannt.\n\n"
         "## Entscheidungen\n- Ultraschallsensor am Deckel\n\n"
         "## Offene Punkte\n- Kabelweg\n- Montageort\n\n"
         "## Kontext / Begründung\nDachfläche laut Plan 92 m².\n")

SECOND = ("## Ergebnis\nDer Überlauf wird per Schwimmerschalter erkannt.\n\n"
          "## Entscheidungen\n- Schwimmerschalter statt Ultraschall\n\n"
          "## Offene Punkte\n- Kabelweg\n\n"
          "## Kontext / Begründung\nDachfläche laut Plan 92 m². Der Deckel beschlägt oft.\n")

# Classes *********************************************************************


@dataclass
class _Run:
    """Kontext des Abnahme-Ablaufs.

    Attributes:
        cfg: Konfiguration.
        env: Isolierte Umgebung.
        capsys: pytest-Fixture für CLI-Ausgaben.
        svc: Dienst (Aufrufe des Chats).
        path: Aktueller Pfad des Dokuments.
    """

    cfg: Config
    env: dict[str, Path]
    capsys: pytest.CaptureFixture[str]
    svc: Service
    path: str = ""

# Functions *******************************************************************


def cli(capsys, *argv):
    """CLI-Befehl ausführen und das JSON-Ergebnis zurückgeben.

    Args:
        capsys: pytest-Fixture zum Lesen der Ausgabe.
        *argv: Argumente für ``pkm``.

    Returns:
        Das ausgegebene JSON-Objekt.
    """
    code = main(list(argv))
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    return out


def cite(sha, link, key, quote):
    """Beleg-Zeile (ohne Fußnotennamen) bilden.

    Args:
        sha: Ergebnis von ``pkm sha`` mit ``id``, ``version`` und ``sha``.
        link: Dokumentpfad ohne ``.md``.
        key: Abschnittsschlüssel.
        quote: Wörtliches Zitat.

    Returns:
        Der Belegtext nach Spezifikation 4.2.
    """
    return f"[[{link}#{key}]] · „{quote}“ · id:{sha['id']} · v:{sha['version']} · sha:{sha['sha']}"


def write_wiki(cfg, capsys, link, lines_extra=""):
    """Themen- und Zusammenfassungsseite so schreiben, wie es der Pflege-Agent tun würde.

    Args:
        cfg: Konfiguration.
        capsys: pytest-Fixture für die CLI-Aufrufe.
        link: Aktueller Dokumentpfad ohne ``.md``.
        lines_extra: Zusätzliche Zeilen im Abschnitt „Inhalt“.

    Returns:
        Ergebnis von ``pkm sha`` für den Abschnitt „Entscheidungen“.
    """
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
    """Pflegelauf abschließen: sync-citations, mark, index, status, lint, commit-wiki.

    Args:
        capsys: pytest-Fixture für die CLI-Aufrufe.
        doc_id: Verarbeitetes Dokument.
        message: Commit-Betreff.
    """
    cli(capsys, "sync-citations")
    cli(capsys, "mark", doc_id, "--pages", "wiki/topics/zisterne", "wiki/summaries/ueberlaufsensor")
    cli(capsys, "index")
    cli(capsys, "status")
    lint = cli(capsys, "lint")
    assert lint["summary"]["error"] == 0, lint["findings"]
    assert cli(capsys, "commit-wiki", "-m", message)["status"] == "ok"


def _step_1_create(run: _Run) -> str:
    """Schritt 1: Ablegen aus dem Chat (nach Suche und bestätigtem Entwurf).

    Args:
        run: Ablaufkontext.

    Returns:
        Die neue Dokument-ID.
    """
    assert not run.svc.search("Überlaufsensor", scope="documents")["results"]
    doc = run.svc.create_document(title="Zisterne – Überlaufsensor", content=FIRST, topics=["zisterne"],
                                  context="Chat: Überlaufsensor")
    assert doc["path"].startswith("documents/_inbox/") and doc["version"] == 1
    assert git(run.env, "show", "--name-only", "--format=%s", "HEAD").split("\n")[0].endswith(" v1")
    run.path = doc["path"]
    return doc["id"]


def _step_2_first_run(run: _Run, doc_id: str) -> None:
    """Schritt 2: erster Pflegelauf; der Agenten-Commit enthält nur wiki/ und state.json.

    Args:
        run: Ablaufkontext.
        doc_id: Dokument-ID.
    """
    assert cli(run.capsys, "doctor", "--short")["status"] == "ok"
    cli(run.capsys, "versions")
    cli(run.capsys, "ids")
    assert [i["id"] for i in cli(run.capsys, "pending")["new"]] == [doc_id]
    write_wiki(run.cfg, run.capsys, run.path[:-3])
    finish_run(run.capsys, doc_id, "pkm: ingest 1 documents")
    files = git(run.env, "show", "--name-only", "--format=", "HEAD").split()
    assert all(f.startswith("wiki/") or f == ".pkm/state.json" for f in files)


def _step_3_sort_in(run: _Run) -> None:
    """Schritt 3: in Obsidian einsortieren; Obsidian schreibt die Links um.

    Args:
        run: Ablaufkontext.
    """
    root = run.cfg.root
    (root / "documents/haus").mkdir()
    (root / run.path).rename(root / SORTED)
    for page in ("wiki/topics/zisterne.md", "wiki/summaries/ueberlaufsensor.md"):
        p = root / page
        p.write_text(p.read_text().replace(run.path[:-3], SORTED[:-3]))
    checks = {f["check"] for f in cli(run.capsys, "lint")["findings"]}
    assert "citation_moved" not in checks and "citation_missing" not in checks


def _step_4_5_continue(run: _Run, doc_id: str) -> None:
    """Schritte 4 und 5: Fortsetzung in neuem Chat (finden, lesen, neu fassen) und Verlauf.

    Args:
        run: Ablaufkontext.
        doc_id: Dokument-ID.
    """
    hits = run.svc.search("Überlaufsensor", scope="documents")["results"]
    assert hits[0]["id"] == doc_id and hits[0]["path"] == SORTED
    cur = run.svc.read(f"id:{doc_id}")
    r = run.svc.rewrite_document(target=f"id:{doc_id}", content=SECOND, expected_hash=cur["hash"],
                                 note="Sensor: Schwimmerschalter statt Ultraschall")
    assert r["version"] == 2 and "Fortsetzung" not in run.svc.read(f"id:{doc_id}")["content"]
    hist = run.svc.history(f"id:{doc_id}", diff_from=1)
    versions = [(v["version"], v["note"]) for v in hist["versions"] if not v["subject"].endswith(" moved")]
    assert versions[-1] == (2, "Sensor: Schwimmerschalter statt Ultraschall")
    assert "+- Schwimmerschalter statt Ultraschall" in hist["diff"]


def _write_wiki_with_old_version(run: _Run, doc_id: str) -> None:
    """Wiki mit „Bis Version 1: …“ und Beleg auf v1 schreiben und den Lauf abschließen.

    Args:
        run: Ablaufkontext.
        doc_id: Dokument-ID.
    """
    shown = cli(run.capsys, "show", f"id:{doc_id}", "--version", "1", "--section", "Entscheidungen")
    old_ent = {"id": doc_id, "version": 1, "sha": shown["section_hash"][:6]}
    write_wiki(run.cfg, run.capsys, SORTED[:-3], "Bis Version 1: Ultraschallsensor am Deckel.[^b3]\n")
    p = run.cfg.root / "wiki/topics/zisterne.md"
    footnote = cite(old_ent, SORTED[:-3], "Entscheidungen", "Ultraschallsensor am Deckel")
    p.write_text(p.read_text() + f"[^b3]: {footnote}\n")
    finish_run(run.capsys, doc_id, "pkm: ingest 1 documents")


def _step_6_second_run(run: _Run, doc_id: str) -> None:
    """Schritt 6: zweiter Pflegelauf; nur geänderte Abschnitte, „Bis Version 1“ mit Beleg auf v1.

    Args:
        run: Ablaufkontext.
        doc_id: Dokument-ID.
    """
    cli(run.capsys, "versions")
    changed = cli(run.capsys, "pending")["changed"][0]
    assert changed["processed_version"] == 1 and changed["version"] == 2
    assert {c["key"] for c in changed["sections"]} == {"Ergebnis", "Entscheidungen", "Offene Punkte",
                                                      "Kontext / Begründung"}
    _write_wiki_with_old_version(run, doc_id)


def _step_7_8_sources_and_dated(run: _Run, doc_id: str) -> None:
    """Schritte 7 und 8: Quellen nennen; datierter Abschnitt nur auf Anweisung.

    Args:
        run: Ablaufkontext.
        doc_id: Dokument-ID.
    """
    res = run.svc.show_citations("wiki/topics/zisterne", statement="Dachfläche beträgt", with_excerpt=True)
    c = res["citations"][0]
    assert (c["original"], c["section"], c["status"]) == (SORTED, "Kontext / Begründung", "ok")
    old = {x["id"]: x for x in run.svc.show_citations("wiki/topics/zisterne")["citations"]}["b3"]
    assert old["cited_version"] == 1 and old["status"] == "newer_version"
    cur = run.svc.read(f"id:{doc_id}")
    r = run.svc.append_to_document(target=f"id:{doc_id}", expected_hash=cur["hash"],
                                   section="Fortsetzung 2026-11-03",
                                   text="### Ergebnis\nSchwimmerschalter mit 5 m Kabel bestellen.")
    assert "## Fortsetzung 2026-11-03" in run.svc.read(f"id:{doc_id}")["content"] and r["version"] == 3


def _step_9_windows(run: _Run) -> None:
    """Schritt 9: Änderung auf Windows (CRLF, Obsidian) ergibt eine Version mit PKM-Source: user.

    Args:
        run: Ablaufkontext.
    """
    path = run.cfg.root / SORTED
    data = path.read_bytes().replace(b"- Kabelweg\n", b"- Kabelweg\n- Frostschutz\n")
    path.write_bytes(data.replace(b"\n", b"\r\n"))
    assert cli(run.capsys, "versions")["committed"][0]["version"] == 4
    assert "PKM-Source: user" in git(run.env, "log", "-1", "--format=%B")
    assert b"\r\n" not in path.read_bytes()
    pend = cli(run.capsys, "pending")["changed"][0]
    assert {c["key"] for c in pend["sections"]} == {"Offene Punkte", "Fortsetzung 2026-11-03"}


def _step_10_clean(run: _Run, doc_id: str) -> None:
    """Schritt 10: nach dem Lauf melden doctor und lint keine Fehler, der Arbeitsbaum ist sauber.

    Args:
        run: Ablaufkontext.
        doc_id: Dokument-ID.
    """
    _write_wiki_with_old_version(run, doc_id)
    assert cli(run.capsys, "doctor")["errors"] == 0
    assert cli(run.capsys, "lint")["summary"]["error"] == 0
    assert git(run.env, "status", "--porcelain").strip() == ""
    assert not (run.cfg.root / ".git").exists()


def test_acceptance_steps_1_to_10(cfg, isolated_env, capsys, monkeypatch):
    """Spielt die Abnahmeschritte 1–10 aus Spezifikation 14 mit Tools und CLI durch."""
    monkeypatch.chdir(cfg.root)
    run = _Run(cfg, isolated_env, capsys, Service(cfg))
    doc_id = _step_1_create(run)
    _step_2_first_run(run, doc_id)
    _step_3_sort_in(run)
    _step_4_5_continue(run, doc_id)
    _step_6_second_run(run, doc_id)
    _step_7_8_sources_and_dated(run, doc_id)
    _step_9_windows(run)
    _step_10_clean(run, doc_id)

# Main ************************************************************************
