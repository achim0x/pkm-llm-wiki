"""Frontmatter-Schema für Dokumente (Spezifikation 4.1, Fassung 0.18).

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

import re
from datetime import datetime
from typing import Any

# Variables *******************************************************************

CONVERSION_FIELDS = ("title", "short_citation", "date_document", "status_markdown", "date_markdown",
                     "toolchain_markdown")
SHORT_CITATION = "short_citation"
LEGACY_SHORT_CITATION = "short citation"
KINDS = ("note", "standard", "regulation", "correction")
DEFAULT_KIND = "note"
DEFAULT_TOOLCHAIN = "pkm-mcp"
DATE_FIELDS = ("date_markdown", "date_updated")
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
DATE_VALUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$")
CONVERTED_MARKERS = ("status_markdown", SHORT_CITATION, LEGACY_SHORT_CITATION, "date_document")

# Classes *********************************************************************

# Functions *******************************************************************


def stamp(moment: datetime) -> str:
    """Zeitpunkt im Format der Datumsfelder: ``YYYY-MM-DDTHH:MM:SS`` in Ortszeit ohne Zeitzone.

    Args:
        moment: Zeitpunkt (in ``PKM_TZ``).

    Returns:
        Zeitstempel ohne Zeitzonen-Angabe.
    """
    return moment.strftime(DATE_FORMAT)


def short_citation(meta: dict[str, Any]) -> str | None:
    """Kurzbezeichnung lesen (auch in der alten Schreibweise ``short citation``).

    Args:
        meta: Frontmatter-Felder.

    Returns:
        Die Kurzbezeichnung als Text oder ``None``.
    """
    value = meta.get(SHORT_CITATION, meta.get(LEGACY_SHORT_CITATION))
    return str(value).strip() if value not in (None, "") else None


def citation_key(value: str) -> str:
    """Kurzbezeichnung vergleichbar machen (NFC wird vorausgesetzt).

    Args:
        value: Kurzbezeichnung oder Eingabe.

    Returns:
        Text ohne Groß-/Kleinschreibung, mit zusammengefasstem Leerraum.
    """
    return " ".join(value.split()).casefold()


def is_valid_date_value(value: Any) -> bool:
    """Prüfen, ob ein Datumsfeld das Format ``YYYY-MM-DDTHH:MM:SS`` oder ``YYYY-MM-DD`` hat.

    Args:
        value: Wert aus dem Frontmatter.

    Returns:
        ``True`` bei gültigem Format ohne Zeitzonen-Angabe.
    """
    return isinstance(value, str) and bool(DATE_VALUE_RE.match(value))


def kind_of(meta: dict[str, Any]) -> str:
    """Art des Dokuments.

    Args:
        meta: Frontmatter-Felder.

    Returns:
        Wert von ``kind``; ``note``, wenn das Feld fehlt.
    """
    value = meta.get("kind")
    return str(value) if value not in (None, "") else DEFAULT_KIND


def looks_converted(meta: dict[str, Any]) -> bool:
    """Prüfen, ob ein Dokument aus einer Umwandlung stammt (Norm, Datenblatt …).

    Args:
        meta: Frontmatter-Felder.

    Returns:
        ``True``, wenn ``status_markdown``, ``short_citation`` oder ``date_document`` vorhanden ist.
    """
    return any(field in meta for field in CONVERTED_MARKERS)

# Main ************************************************************************
