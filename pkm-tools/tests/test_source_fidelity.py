"""Tests: lint for source fidelity (cross_source_statement, synthesis_unmarked) and finish_maintenance.

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

from pkm import maintrun
from pkm.lint import lint
from pkm.sourcelint import sentences

from .conftest import write

# Variables *******************************************************************

ID_A = "d-20261108-1000-aaaa"
ID_B = "d-20261108-1000-bbbb"
DEFS = (f"[^b1]: [[documents/a#A]] · \"Regel für Beimischungen\" · id:{ID_A} · v:1 · sha:aaaaaa\n"
        f"[^b2]: [[documents/b#B]] · \"Nachteil des Produkts\" · id:{ID_B} · v:1 · sha:bbbbbb\n"
        f"[^b3]: [[documents/a#A]] · \"zweite Stelle\" · id:{ID_A} · v:1 · sha:aaaaaa\n")

# Classes *********************************************************************

# Functions *******************************************************************


def _page(cfg, rel, sections, meta=""):
    """Write a wiki page with the given sections and the citations of A and B.

    Args:
        cfg: Configuration.
        rel: Path.
        sections: Markdown of the sections (before the citations).
        meta: Additional frontmatter lines.
    """
    write(cfg, rel, f"---\ntype: topic\ntitle: T\n{meta}---\n\n> **Summary:** S.\n\n{sections}\n## Citations\n{DEFS}")


def _findings(svc, check="cross_source_statement"):
    """Findings of one check.

    Args:
        svc: Service.
        check: Check name.

    Returns:
        The findings.
    """
    return [f for f in lint(svc)["findings"] if f["check"] == check]


@pytest.mark.parametrize(("section", "severity"), [("Contradictions / open questions", "warning"),
                                                    ("Widersprüche / offene Fragen", "warning"),
                                                    ("Content", "info")])
def test_combined_sources_reported(svc, cfg, section, severity):
    """Cases 1 and 2: an item citing A and B is a warning in the contradictions section, otherwise info."""
    _page(cfg, "wiki/topics/geld.md", f"## {section}\n- Produkt aus B widerspricht der Regel.[^b1][^b2]\n\n")
    (finding,) = _findings(svc)
    assert finding["severity"] == severity and finding["path"] == "wiki/topics/geld.md"
    assert finding["detail"]["documents"] == [ID_A, ID_B] and finding["detail"]["footnotes"] == ["b1", "b2"]
    assert finding["detail"]["section"] == section
    assert finding["detail"]["text"].startswith("Produkt aus B")


def test_same_document_and_separate_sentences_not_reported(svc, cfg):
    """Case 3: two citations of the same document; separate sentences with one source each."""
    _page(cfg, "wiki/topics/geld.md", "## Contradictions / open questions\n- Regel und Ausnahme.[^b1][^b3]\n\n"
          "## Content\nX sagt das eine.[^b1] Das andere Dokument nennt einen Nachteil.[^b2]\n\n")
    assert not _findings(svc)


def test_sentence_with_footnote_in_the_middle(svc, cfg):
    """A sentence with a footnote in the middle and one at the end counts as one sentence."""
    _page(cfg, "wiki/topics/geld.md", "## Content\nX empfiehlt Beimischungen[^b1] und das Produkt hat einen "
          "Nachteil.[^b2]\n\n")
    (finding,) = _findings(svc)
    assert finding["severity"] == "info"


def test_exceptions(svc, cfg):
    """Case 4: comment at the item; lint_ignore on the page."""
    _page(cfg, "wiki/topics/geld.md", "## Contradictions / open questions\n- B nennt die Regel von X selbst."
          "[^b1][^b2] <!-- lint: cross-source ok -->\n\n")
    _page(cfg, "wiki/topics/other.md", "## Contradictions / open questions\n- A gegen B.[^b1][^b2]\n\n",
          meta="lint_ignore: [cross_source_statement]\n")
    assert not _findings(svc)


def test_synthesis_marker(svc, cfg):
    """Case 5: synthesis pages need confidence and the marker for an own interpretation."""
    write(cfg, "wiki/syntheses/a.md", "---\ntype: synthesis\ntitle: A\n---\n\n> **Summary:** S.\n\n## Content\nX.\n")
    write(cfg, "wiki/syntheses/b.md", "---\ntype: synthesis\ntitle: B\nconfidence: low\n---\n\n> **Summary:** S.\n\n"
          "Eigene Einordnung, nicht aus den Quellen.\n\n## Content\nX.\n")
    assert [f["path"] for f in _findings(svc, "synthesis_unmarked")] == ["wiki/syntheses/a.md"]


def test_sentences():
    """Sentence boundaries: ., ;, !, ? with the footnotes directly after them."""
    assert sentences("A sagt X.[^b1] B sagt Y;[^b2] Z") == ["A sagt X.[^b1]", "B sagt Y;[^b2]", "Z"]
    assert sentences("A[^b1] und B.[^b2]") == ["A[^b1] und B.[^b2]"]


def test_finish_maintenance_lists_cross_source_of_changed_pages(svc, cfg):
    """Ä4: finish_maintenance returns cross_source for pages changed in this run only."""
    write(cfg, "documents/a.md", f"---\ntitle: A\nid: {ID_A}\nversion: 1\n---\n\n## A\nRegel für Beimischungen.\n")
    write(cfg, "documents/b.md", f"---\ntitle: B\nid: {ID_B}\nversion: 1\n---\n\n## B\nNachteil des Produkts.\n")
    maintrun.begin_maintenance(svc)
    _page(cfg, "wiki/topics/geld.md", "## Contradictions / open questions\n- A gegen B.[^b1][^b2]\n\n")
    first = maintrun.finish_maintenance(svc, "- new page")
    assert [f["path"] for f in first["cross_source"]] == ["wiki/topics/geld.md"]
    second = maintrun.finish_maintenance(svc, "- nothing", operation="lint")
    assert second["cross_source"] == []

def test_label_only_source_line_not_reported(svc, cfg):
    """N5: a line "Quellen: [^b1] [^b2]" and a table with footnotes of two documents are no statements."""
    _page(cfg, "wiki/topics/geld.md", "## Content\n| Wert | Betrag |\n|---|---|\n| A | 1[^b1] |\n| B | 2[^b2] |\n\n"
          "Quellen: [^b1] [^b2]\n\nSources: [^b1][^b2]\n\n- Regel und Nachteil.[^b1][^b2]\n\n")
    (finding,) = _findings(svc)
    assert finding["detail"]["text"] == "Regel und Nachteil."


def _ip_docs(cfg, class_a, class_b):
    """Two documents A and B with IP addresses and the given classifications.

    Args:
        cfg: Configuration.
        class_a: ``ip_addresses`` of A or ``None``.
        class_b: ``ip_addresses`` of B or ``None``.
    """
    for doc_id, name, value in ((ID_A, "a", class_a), (ID_B, "b", class_b)):
        field = f"ip_addresses: {value}\n" if value else ""
        write(cfg, f"documents/{name}.md", f"---\ntitle: {name}\nid: {doc_id}\nversion: 1\n{field}---\n\n"
              f"## {name.upper()}\nHost {name} hat 192.0.2.10.\n")


@pytest.mark.parametrize(("class_a", "class_b", "reported"), [("placeholder", "concrete", True),
                                                               (None, "concrete", True),
                                                               ("concrete", "concrete", False)])
def test_ip_comparison(svc, cfg, class_a, class_b, reported):
    """N4: an IP contradiction between documents not both concrete is ip_comparison; unclassified ones are named."""
    _ip_docs(cfg, class_a, class_b)
    _page(cfg, "wiki/topics/netz.md", "## Contradictions / open questions\n- 192.0.2.10 ist in A Host a, "
          "in B Host b.[^b1][^b2] <!-- lint: cross-source ok -->\n\n")
    assert bool(_findings(svc, "ip_comparison")) is reported
    unclassified = [f["path"] for f in _findings(svc, "ip_addresses_unclassified")]
    assert unclassified == ([] if class_a else ["documents/a.md"])


def test_begin_maintenance_reports_ip_addresses_and_field(svc, cfg):
    """N1/N2: new documents with IP addresses carry ip_addresses; the field is set via set_document_metadata."""
    write(cfg, "documents/_inbox/netz.md", "---\ntitle: Netz\n---\n\n## Hosts\nRouter 192.0.2.1, NAS 192.0.2.2, "
          "IPv6 2001:db8::5, Version 1.2.3.\n")
    write(cfg, "documents/_inbox/ohne.md", "---\ntitle: Ohne\n---\n\nKeine Adressen.\n")
    begin = maintrun.begin_maintenance(svc)
    by_path = {e["path"]: e for e in begin["pending"]["new"]}
    assert by_path["documents/_inbox/netz.md"]["ip_addresses"] == {
        "found": ["192.0.2.1", "192.0.2.2", "2001:db8::5"], "classification": None}
    assert "ip_addresses" not in by_path["documents/_inbox/ohne.md"]
    doc = svc.read("documents/_inbox/netz.md")
    with pytest.raises(Exception) as exc:
        maintrun.set_document_metadata(svc, "documents/_inbox/netz.md", doc["hash"], set={"ip_addresses": "maybe"})
    assert getattr(exc.value, "status", "") == "invalid_argument"
    maintrun.set_document_metadata(svc, "documents/_inbox/netz.md", doc["hash"], set={"ip_addresses": "placeholder"})
    text = (cfg.root / "documents/_inbox/netz.md").read_text(encoding="utf-8")
    assert "ip_addresses: placeholder" in text
    begin = maintrun.begin_maintenance(svc)
    entry = next(e for e in begin["pending"]["new"] if e["path"] == "documents/_inbox/netz.md")
    assert entry["ip_addresses"]["classification"] == "placeholder"


def test_changed_document_reports_ip_addresses_only_if_they_changed(svc, cfg):
    """N2: a changed document carries ip_addresses only if its addresses changed."""
    write(cfg, "documents/netz.md", "---\ntitle: Netz\n---\n\n## Hosts\nRouter 192.0.2.1.\n")
    begin = maintrun.begin_maintenance(svc)
    doc_id = begin["ids"]["assigned"][0]["id"]
    maintrun.finish_maintenance(svc, "- processed", processed=[doc_id])
    path = cfg.root / "documents/netz.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nNeuer Text ohne Adresse.\n", encoding="utf-8")
    item = next(i for i in maintrun.begin_maintenance(svc)["pending"]["changed"] if i["id"] == doc_id)
    assert "ip_addresses" not in item
    maintrun.finish_maintenance(svc, "- processed", processed=[doc_id])
    path.write_text(path.read_text(encoding="utf-8") + "\nSwitch 192.0.2.9.\n", encoding="utf-8")
    item = next(i for i in maintrun.begin_maintenance(svc)["pending"]["changed"] if i["id"] == doc_id)
    assert item["ip_addresses"]["found"] == ["192.0.2.1", "192.0.2.9"]


# Main ************************************************************************
