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

# Main ************************************************************************
