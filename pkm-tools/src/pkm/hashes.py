"""Hashes nach Spezifikation 4.8, Schritt 4. Einzige Stelle für Hash-Berechnungen.

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

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .parse import Parsed, Section
from .schema import LEGACY_SHORT_CITATION, SHORT_CITATION

# Variables *******************************************************************

META_FIELDS = ("title", "short_citation", "date_document", "tags", "related", "kind")
SHORT = 6

EMPTY_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # SHA-256 des leeren Texts

# Classes *********************************************************************


@dataclass(frozen=True)
class DocHashes:
    """Alle Hashes eines Markdown-Dokuments.

    Attributes:
        file_hash: Hash der ganzen normalisierten Datei (``hash``/``expected_hash``).
        body_hash: Hash der Abschnittsfolge mit Schlüsseln und Abschnitts-Hashes.
        meta_hash: Hash der inhaltlich relevanten Metadaten.
        sections: Abschnitts-Hash je Schlüssel.
    """

    file_hash: str
    body_hash: str
    meta_hash: str
    sections: dict[str, str]

# Functions *******************************************************************


def sha256_bytes(data: bytes) -> str:
    """SHA-256 über Bytes.

    Args:
        data: Beliebige Bytes.

    Returns:
        64 Hex-Zeichen in Kleinbuchstaben.
    """
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """SHA-256 über UTF-8-kodierten Text.

    Args:
        text: Beliebiger Text.

    Returns:
        64 Hex-Zeichen in Kleinbuchstaben.
    """
    return sha256_bytes(text.encode("utf-8"))


def file_hash(normalized_text: str) -> str:
    """Datei-Hash (``hash``/``expected_hash``/``file_hash``).

    Args:
        normalized_text: Gesamte normalisierte Datei einschließlich Frontmatter.

    Returns:
        SHA-256 des Texts.
    """
    return sha256_text(normalized_text)


def normalize_section_content(lines: list[str]) -> str:
    """Abschnittsinhalt für den Hash normalisieren.

    Zeilen werden rechts getrimmt, Leerzeilen am Rand entfernt und Folgen von Leerzeilen zu
    einer zusammengefasst.

    Args:
        lines: Abschnittszeilen ohne Überschrift.

    Returns:
        Die normalisierten Zeilen, mit LF verbunden.
    """
    out: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if line or (out and out[-1]):
            out.append(line)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def section_hash(section: Section) -> str:
    """Hash eines Abschnitts (ohne Überschriftenzeile).

    Args:
        section: Der Abschnitt.

    Returns:
        SHA-256 des normalisierten Inhalts.
    """
    return sha256_text(normalize_section_content(section.content_lines))


def section_hashes(p: Parsed) -> dict[str, str]:
    """Hashes aller Abschnitte.

    Args:
        p: Zerlegtes Dokument.

    Returns:
        Abschnitts-Hash je Schlüssel in Dokumentreihenfolge.
    """
    return {s.key: section_hash(s) for s in p.sections}


def body_hash(p: Parsed) -> str:
    """Hash der Abschnittsfolge (Reihenfolge inklusive).

    Args:
        p: Zerlegtes Dokument.

    Returns:
        SHA-256 über die Zeilen ``<schlüssel>\\t<abschnitts-hash>\\n``.
    """
    return sha256_text("".join(f"{s.key}\t{section_hash(s)}\n" for s in p.sections))


def _jsonable(value: Any) -> Any:
    """Wert für ``meta_hash`` aufbereiten: Werte als Zeichenketten in Frontmatter-Schreibweise.

    Args:
        value: Beliebiger YAML-Wert.

    Returns:
        Zeichenkette, Liste bzw. Wörterbuch solcher Zeichenketten oder ``None``.
    """
    if isinstance(value, dict):
        result: Any = {str(k): _jsonable(v) for k, v in value.items()}
    elif isinstance(value, list | tuple):
        result = [_jsonable(v) for v in value]
    elif isinstance(value, bool):
        result = "true" if value else "false"
    elif value is None:
        result = None
    else:
        result = str(value)
    return result


def meta_hash(meta: dict[str, Any]) -> str:
    """Hash der inhaltlich relevanten Metadaten (4.8).

    Eingang: ``title``, ``short_citation`` (auch in der alten Schreibweise ``short citation``),
    ``date_document``, ``tags``, ``related``, ``kind``. ``status_markdown``, Datumsfelder, ``id``
    und ``version`` sind bewusst ausgenommen.

    Args:
        meta: Frontmatter-Felder.

    Returns:
        SHA-256 des kanonischen JSON (sortiert, UTF-8, ohne Leerraum).
    """
    fields = dict(meta)
    if SHORT_CITATION not in fields and LEGACY_SHORT_CITATION in fields:
        fields[SHORT_CITATION] = fields[LEGACY_SHORT_CITATION]
    data = {k: _jsonable(fields[k]) for k in META_FIELDS if k in fields}
    return sha256_text(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def short(h: str) -> str:
    """Kurzform eines Hashes für Belege und Anzeigen.

    Args:
        h: Voller Hash.

    Returns:
        Die ersten sechs Zeichen.
    """
    return h[:SHORT]


def matches(stored: str, given: str) -> bool:
    """Vollen Hash mit einem (ggf. gekürzten) Präfix vergleichen.

    Args:
        stored: Voller Hash.
        given: Präfix, Groß-/Kleinschreibung egal.

    Returns:
        ``True``, wenn ``given`` nicht leer ist und ``stored`` damit beginnt.
    """
    given = given.strip().lower()
    return bool(given) and stored.lower().startswith(given)


def compute(normalized_text: str, p: Parsed) -> DocHashes:
    """Alle Hashes eines Dokuments berechnen.

    Args:
        normalized_text: Normalisierter Dateitext.
        p: Zerlegtes Dokument zu diesem Text.

    Returns:
        Die Hashes.
    """
    return DocHashes(file_hash(normalized_text), body_hash(p), meta_hash(p.meta), section_hashes(p))

# Main ************************************************************************
