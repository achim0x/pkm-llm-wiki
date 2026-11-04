"""Hashes according to specification 4.8, step 4. The only place for hash calculations.

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

EMPTY_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # SHA-256 of the empty text

# Classes *********************************************************************


@dataclass(frozen=True)
class DocHashes:
    """All hashes of a Markdown document.

    Attributes:
        file_hash: Hash of the whole normalized file (``hash``/``expected_hash``).
        body_hash: Hash of the sequence of sections with keys and section hashes.
        meta_hash: Hash of the metadata relevant for content.
        sections: Section hash per key.
    """

    file_hash: str
    body_hash: str
    meta_hash: str
    sections: dict[str, str]

# Functions *******************************************************************


def sha256_bytes(data: bytes) -> str:
    """SHA-256 over bytes.

    Args:
        data: Arbitrary bytes.

    Returns:
        64 hex characters in lower case.
    """
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """SHA-256 over UTF-8 encoded text.

    Args:
        text: Any text.

    Returns:
        64 hex characters in lower case.
    """
    return sha256_bytes(text.encode("utf-8"))


def file_hash(normalized_text: str) -> str:
    """File hash (``hash``/``expected_hash``/``file_hash``).

    Args:
        normalized_text: Whole normalized file including frontmatter.

    Returns:
        SHA-256 of the text.
    """
    return sha256_text(normalized_text)


def normalize_section_content(lines: list[str]) -> str:
    """Normalize section content for the hash.

    Lines are trimmed on the right, blank lines at the edges removed and runs of blank lines
    collapsed into one.

    Args:
        lines: Section lines without the heading.

    Returns:
        The normalized lines, joined with LF.
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
    """Hash of a section (without the heading line).

    Args:
        section: The section.

    Returns:
        SHA-256 of the normalized content.
    """
    return sha256_text(normalize_section_content(section.content_lines))


def section_hashes(p: Parsed) -> dict[str, str]:
    """Hashes of all sections.

    Args:
        p: Parsed document.

    Returns:
        Section hash per key in document order.
    """
    return {s.key: section_hash(s) for s in p.sections}


def body_hash(p: Parsed) -> str:
    """Hash of the sequence of sections (order included).

    Args:
        p: Parsed document.

    Returns:
        SHA-256 over the lines ``<key>\\t<section-hash>\\n``.
    """
    return sha256_text("".join(f"{s.key}\t{section_hash(s)}\n" for s in p.sections))


def _jsonable(value: Any) -> Any:
    """Prepare a value for ``meta_hash``: values as strings in frontmatter notation.

    Args:
        value: Any YAML value.

    Returns:
        String, list or dictionary of such strings, or ``None``.
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
    """Hash of the metadata relevant for content (4.8).

    Input: ``title``, ``short_citation`` (also in the old spelling ``short citation``),
    ``date_document``, ``tags``, ``related``, ``kind``. ``status_markdown``, date fields, ``id``
    and ``version`` are deliberately excluded.

    Args:
        meta: Frontmatter fields.

    Returns:
        SHA-256 of the canonical JSON (sorted, UTF-8, without whitespace).
    """
    fields = dict(meta)
    if SHORT_CITATION not in fields and LEGACY_SHORT_CITATION in fields:
        fields[SHORT_CITATION] = fields[LEGACY_SHORT_CITATION]
    data = {k: _jsonable(fields[k]) for k in META_FIELDS if k in fields}
    return sha256_text(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def short(h: str) -> str:
    """Short form of a hash for citations and display.

    Args:
        h: Full hash.

    Returns:
        The first six characters.
    """
    return h[:SHORT]


def matches(stored: str, given: str) -> bool:
    """Compare a full hash with a (possibly shortened) prefix.

    Args:
        stored: Full hash.
        given: Prefix, case-insensitive.

    Returns:
        ``True`` if ``given`` is not empty and ``stored`` starts with it.
    """
    given = given.strip().lower()
    return bool(given) and stored.lower().startswith(given)


def compute(normalized_text: str, p: Parsed) -> DocHashes:
    """Compute all hashes of a document.

    Args:
        normalized_text: Normalized file text.
        p: Parsed document for this text.

    Returns:
        The hashes.
    """
    return DocHashes(file_hash(normalized_text), body_hash(p), meta_hash(p.meta), section_hashes(p))

# Main ************************************************************************
