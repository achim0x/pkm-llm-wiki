"""Fixed texts of the generated wiki files in the wiki language (``PKM_LANGUAGE``, 4.2–4.5).

``wiki/index.md``, ``wiki/_status.md`` and the heading of ``wiki/log.md`` use these texts. No tool parses
them back, so the language can change at any time; the files are simply regenerated.

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

# Imports *********************************************************************

from __future__ import annotations

# Variables *******************************************************************

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "index_title": "Wiki index", "no_pages": "_No pages yet._", "no_summary": "_(no summary)_",
        "source": "source", "sources": "sources", "topic": "Topics", "entity": "Entities",
        "summary": "Summaries", "synthesis": "Syntheses", "other": "Other",
        "status_title": "Status", "unprocessed": "Not yet processed",
        "inbox_done": "Still in the inbox, already processed", "problems": "Problems",
        "orphans": "Orphaned attachments", "questions": "Questions",
        "new": "new", "without_id": ", without ID", "rename": ", name proposal: {name}", "changed": "changed: {keys}",
        "order_only": "only order changed", "images_only": "only image files changed",
        "migrated": "image files now recorded as attachments", "meta_only": "metadata only",
        "moved": "moved from {src}", "no_pages_affected": "no wiki pages",
        "deleted": "deleted (last v{version}), affects: {pages}", "proposal": "proposal: {folder}",
        "no_proposal": "no proposal", "conflict_copy": "Cloud storage conflict copy: {path} (please merge in Obsidian)",
        "duplicate_id": "Duplicate ID {id}: {paths}", "case_collision": "Differ only in upper/lower case: {paths}",
        "log_title": "Maintenance log",
    },
    "de": {
        "index_title": "Wiki-Index", "no_pages": "_Noch keine Seiten._", "no_summary": "_(keine Kurzfassung)_",
        "source": "Quelle", "sources": "Quellen", "topic": "Themen", "entity": "Entitäten",
        "summary": "Zusammenfassungen", "synthesis": "Synthesen", "other": "Sonstige",
        "status_title": "Status", "unprocessed": "Noch nicht verarbeitet",
        "inbox_done": "Noch im Eingang, bereits verarbeitet", "problems": "Probleme",
        "orphans": "Verwaiste Anhänge", "questions": "Fragen",
        "new": "neu", "without_id": ", ohne ID", "rename": ", Namensvorschlag: {name}", "changed": "geändert: {keys}",
        "order_only": "nur Reihenfolge geändert", "images_only": "nur Bilddateien geändert",
        "migrated": "Bilddateien jetzt als Anhänge erfasst", "meta_only": "nur Metadaten",
        "moved": "verschoben von {src}", "no_pages_affected": "keine Wiki-Seiten",
        "deleted": "gelöscht (zuletzt v{version}), betrifft: {pages}", "proposal": "Vorschlag: {folder}",
        "no_proposal": "kein Vorschlag",
        "conflict_copy": "Konfliktkopie des Cloud-Speichers: {path} (bitte in Obsidian zusammenführen)",
        "duplicate_id": "Doppelte ID {id}: {paths}",
        "case_collision": "Unterscheiden sich nur in Groß-/Kleinschreibung: {paths}",
        "log_title": "Pflegeprotokoll",
    },
}

# Classes *********************************************************************

# Functions *******************************************************************


def text(language: str, key: str, **values: object) -> str:
    """Fixed text in the wiki language.

    Args:
        language: ``en`` or ``de`` (others fall back to English).
        key: Key in ``TEXTS``.
        **values: Values for the placeholders.

    Returns:
        The text.
    """
    return TEXTS.get(language, TEXTS["en"])[key].format(**values)

# Main ************************************************************************
