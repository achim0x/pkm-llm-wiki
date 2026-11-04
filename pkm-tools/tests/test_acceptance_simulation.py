"""Acceptance (specification 14) as a simulation: every step with the real tools and the CLI.

The calls of the chat or the maintenance agent are run directly here. It is checked that the
tools support every step; the behaviour of the LLM is checked by the manual acceptance (docs/abnahme.md).

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
    """Context of the acceptance flow.

    Attributes:
        cfg: Configuration.
        env: Isolated environment.
        capsys: pytest fixture for CLI output.
        svc: Service (calls of the chat).
        path: Current path of the document.
    """

    cfg: Config
    env: dict[str, Path]
    capsys: pytest.CaptureFixture[str]
    svc: Service
    path: str = ""

# Functions *******************************************************************


def cli(capsys, *argv):
    """Run a CLI command and return the JSON result.

    Args:
        capsys: pytest fixture for reading the output.
        *argv: Arguments for ``pkm``.

    Returns:
        The printed JSON object.
    """
    code = main(list(argv))
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    return out


def cite(sha, link, key, quote):
    """Build a citation line (without footnote name).

    Args:
        sha: Result of ``pkm sha`` with ``id``, ``version`` and ``sha``.
        link: Document path without ``.md``.
        key: Section key.
        quote: Literal quote.

    Returns:
        The citation text per specification 4.2.
    """
    return f"[[{link}#{key}]] · „{quote}“ · id:{sha['id']} · v:{sha['version']} · sha:{sha['sha']}"


def write_wiki(cfg, capsys, link, lines_extra=""):
    """Write the topic and summary page the way the maintenance agent would.

    Args:
        cfg: Configuration.
        capsys: pytest fixture for the CLI calls.
        link: Current document path without ``.md``.
        lines_extra: Additional lines in the section "Content".

    Returns:
        Result of ``pkm sha`` for the section "Entscheidungen".
    """
    ent = cli(capsys, "sha", f"[[{link}]]", "--section", "Entscheidungen")
    ctx = cli(capsys, "sha", f"[[{link}]]", "--section", "Kontext / Begründung")
    quote_ent = "Schwimmerschalter statt Ultraschall" if ent["version"] > 1 else "Ultraschallsensor am Deckel"
    page = f"""---
type: topic
title: Zisterne
sources: []
date_updated: 2026-11-02T21:10:00
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
date_updated: 2026-11-02T21:10:00
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
    """Finish a maintenance run: sync-citations, mark, index, status, lint, commit-wiki.

    Args:
        capsys: pytest fixture for the CLI calls.
        doc_id: Processed document.
        message: Commit subject.
    """
    cli(capsys, "sync-citations")
    cli(capsys, "mark", doc_id, "--pages", "wiki/topics/zisterne", "wiki/summaries/ueberlaufsensor")
    cli(capsys, "index")
    cli(capsys, "status")
    lint = cli(capsys, "lint")
    assert lint["summary"]["error"] == 0, lint["findings"]
    assert cli(capsys, "commit-wiki", "-m", message)["status"] == "ok"


def _step_1_create(run: _Run) -> str:
    """Step 1: filing from the chat (after search and a confirmed draft).

    Args:
        run: Flow context.

    Returns:
        The new document ID.
    """
    assert not run.svc.search("Überlaufsensor", scope="documents")["results"]
    doc = run.svc.create_document(title="Zisterne – Überlaufsensor", content=FIRST, tags=["zisterne"],
                                  context="Chat: Überlaufsensor")
    assert doc["path"].startswith("documents/_inbox/") and doc["version"] == 1
    assert git(run.env, "show", "--name-only", "--format=%s", "HEAD").split("\n")[0].endswith(" v1")
    run.path = doc["path"]
    return doc["id"]


def _step_2_first_run(run: _Run, doc_id: str) -> None:
    """Step 2: first maintenance run; the agent commit contains only wiki/ and state.json.

    Args:
        run: Flow context.
        doc_id: Document ID.
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
    """Step 3: file in Obsidian; Obsidian rewrites the links.

    Args:
        run: Flow context.
    """
    root = run.cfg.root
    (root / "documents/haus").mkdir()
    (root / run.path).rename(root / SORTED)
    for page in ("wiki/topics/zisterne.md", "wiki/summaries/ueberlaufsensor.md"):
        p = root / page
        p.write_text(p.read_text(encoding="utf-8").replace(run.path[:-3], SORTED[:-3]), encoding="utf-8", newline="\n")
    checks = {f["check"] for f in cli(run.capsys, "lint")["findings"]}
    assert "citation_moved" not in checks and "citation_missing" not in checks


def _step_4_5_continue(run: _Run, doc_id: str) -> None:
    """Steps 4 and 5: continuation in a new chat (find, read, rewrite) and history.

    Args:
        run: Flow context.
        doc_id: Document ID.
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
    """Write the wiki with "Up to version 1: …" and a citation of v1 and finish the run.

    Args:
        run: Flow context.
        doc_id: Document ID.
    """
    shown = cli(run.capsys, "show", f"id:{doc_id}", "--version", "1", "--section", "Entscheidungen")
    old_ent = {"id": doc_id, "version": 1, "sha": shown["section_hash"][:6]}
    write_wiki(run.cfg, run.capsys, SORTED[:-3], "Bis Version 1: Ultraschallsensor am Deckel.[^b3]\n")
    p = run.cfg.root / "wiki/topics/zisterne.md"
    footnote = cite(old_ent, SORTED[:-3], "Entscheidungen", "Ultraschallsensor am Deckel")
    p.write_text(p.read_text(encoding="utf-8") + f"[^b3]: {footnote}\n", encoding="utf-8", newline="\n")
    finish_run(run.capsys, doc_id, "pkm: ingest 1 documents")


def _step_6_second_run(run: _Run, doc_id: str) -> None:
    """Step 6: second maintenance run; only changed sections, "up to version 1" with a citation of v1.

    Args:
        run: Flow context.
        doc_id: Document ID.
    """
    cli(run.capsys, "versions")
    changed = cli(run.capsys, "pending")["changed"][0]
    assert changed["processed_version"] == 1 and changed["version"] == 2
    assert {c["key"] for c in changed["sections"]} == {"Ergebnis", "Entscheidungen", "Offene Punkte",
                                                      "Kontext / Begründung"}
    _write_wiki_with_old_version(run, doc_id)


def _step_7_8_sources_and_dated(run: _Run, doc_id: str) -> None:
    """Steps 7 and 8: name the sources; dated section only on instruction.

    Args:
        run: Flow context.
        doc_id: Document ID.
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
    """Step 9: a change on Windows (CRLF, Obsidian) results in a version with PKM-Source: user.

    Args:
        run: Flow context.
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
    """Step 10: after the run doctor and lint report no errors, the working tree is clean.

    Args:
        run: Flow context.
        doc_id: Document ID.
    """
    _write_wiki_with_old_version(run, doc_id)
    assert cli(run.capsys, "doctor")["errors"] == 0
    assert cli(run.capsys, "lint")["summary"]["error"] == 0
    assert git(run.env, "status", "--porcelain").strip() == ""
    assert not (run.cfg.root / ".git").exists()


def test_acceptance_steps_1_to_10(cfg, isolated_env, capsys, monkeypatch):
    """Plays through the acceptance steps 1–10 of specification 14 with tools and CLI."""
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
