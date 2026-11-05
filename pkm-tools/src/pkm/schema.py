"""Frontmatter schema for documents (specification 4.1, version 0.18).

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
FIELD_ORDER = ("title", "short_citation", "date_document", "status_markdown", "date_markdown", "toolchain_markdown",
               "id", "version", "date_updated", "context", "tags", "related", "kind")
UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}

# Classes *********************************************************************

# Functions *******************************************************************


def stamp(moment: datetime) -> str:
    """Point in time in the format of the date fields: ``YYYY-MM-DDTHH:MM:SS`` in local time without zone.

    Args:
        moment: Point in time (in ``PKM_TZ``).

    Returns:
        Timestamp without time zone.
    """
    return moment.strftime(DATE_FORMAT)


def short_citation(meta: dict[str, Any]) -> str | None:
    """Read the short citation (also in the old spelling ``short citation``).

    Args:
        meta: Frontmatter fields.

    Returns:
        The short citation as text or ``None``.
    """
    value = meta.get(SHORT_CITATION, meta.get(LEGACY_SHORT_CITATION))
    return str(value).strip() if value not in (None, "") else None


def citation_key(value: str) -> str:
    """Make a short citation comparable (NFC is assumed).

    Args:
        value: Short citation or input.

    Returns:
        Text without case, with collapsed whitespace.
    """
    return " ".join(value.split()).casefold()


def is_valid_date_value(value: Any) -> bool:
    """Check whether a date field has the format ``YYYY-MM-DDTHH:MM:SS`` or ``YYYY-MM-DD``.

    Args:
        value: Value from the frontmatter.

    Returns:
        ``True`` for a valid format without time zone.
    """
    return isinstance(value, str) and bool(DATE_VALUE_RE.match(value))


def order_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Bring frontmatter fields into schema order (4.1).

    Args:
        meta: Fields.

    Returns:
        Known fields in the order of ``FIELD_ORDER``, followed by all others in their
        previous order.
    """
    known = {k: meta[k] for k in FIELD_ORDER if k in meta}
    return {**known, **{k: v for k, v in meta.items() if k not in known}}


def field_rank(key: str) -> int | None:
    """Position of a field in the schema order.

    Args:
        key: Field name.

    Returns:
        Index in ``FIELD_ORDER`` or ``None`` for unknown fields.
    """
    return FIELD_ORDER.index(key) if key in FIELD_ORDER else None


def normalize_tag(tag: Any) -> str:
    """Normalize a tag: lower case, umlauts spelled out, whitespace as hyphen.

    Args:
        tag: Tag (a leading ``#`` is removed).

    Returns:
        The normalized tag (empty if nothing is left).
    """
    text = str(tag).strip().lstrip("#").lower()
    text = "".join(UMLAUTS.get(ch, ch) for ch in text)
    return re.sub(r"-{2,}", "-", re.sub(r"\s+", "-", text)).strip("-")


def normalize_tags(tags: list[Any]) -> list[str]:
    """Normalize tags and remove duplicates (order is kept).

    Args:
        tags: Tags.

    Returns:
        Cleaned list without empty entries.
    """
    return list(dict.fromkeys(t for t in (normalize_tag(x) for x in tags) if t))


def kind_of(meta: dict[str, Any]) -> str:
    """Kind of document.

    Args:
        meta: Frontmatter fields.

    Returns:
        Value of ``kind``; ``note`` if the field is missing.
    """
    value = meta.get("kind")
    return str(value) if value not in (None, "") else DEFAULT_KIND


def looks_converted(meta: dict[str, Any]) -> bool:
    """Check whether a document comes from a conversion (standard, data sheet …).

    Args:
        meta: Frontmatter fields.

    Returns:
        ``True`` if ``status_markdown``, ``short_citation`` or ``date_document`` is present.
    """
    return any(field in meta for field in CONVERTED_MARKERS)

# Main ************************************************************************
