"""Write frontmatter (specification 4.1, decision 16 no. 16).

Server fields are set line by line; the rest of the frontmatter stays unchanged.
``dump_meta`` writes a complete frontmatter (for create_document and update_frontmatter).

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
import re
from typing import Any

import yaml

from .parse import load_yaml, split_frontmatter
from .schema import LEGACY_SHORT_CITATION, SHORT_CITATION, field_rank

# Variables *******************************************************************

PROTECTED = ("id", "version", "date_markdown", "date_updated", "status_markdown")
TOP_LEVEL_FIELD_RE = re.compile(r"^([^\s#][^:]*?):(?:[ \t]+(.*))?$")
PLAIN_FORBIDDEN_START = ("[", "{", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`", "#", "-", "?", ":", ",")

# Classes *********************************************************************

# Functions *******************************************************************


def _plain_ok(s: str) -> bool:
    """Check whether a string without quotes is read unambiguously as a YAML string.

    Args:
        s: String to write.

    Returns:
        ``True`` if the plain notation yields the same string.
    """
    ok = bool(
        s
        and s == s.strip()
        and "\n" not in s
        and not s.startswith(PLAIN_FORBIDDEN_START)
        and ": " not in s
        and " #" not in s
        and not s.endswith(":")
    )
    if ok:
        try:
            ok = load_yaml(f"k: {s}") == {"k": s}
        except yaml.YAMLError:
            ok = False
    return ok


def _flow_list(items: list[Any]) -> str:
    """Write a list on one line: without quotes if unambiguous, otherwise as JSON.

    Args:
        items: List entries.

    Returns:
        E.g. ``[negotiation, softskills]`` or ``["a, b", "c"]``.
    """
    plain = all(isinstance(i, str) and _plain_ok(i) and not any(c in i for c in ",[]{}") for i in items)
    rendered = "[" + ", ".join(items) + "]" if plain else json.dumps(items, ensure_ascii=False)
    if plain:
        try:
            plain = load_yaml(f"k: {rendered}") == {"k": items}
        except yaml.YAMLError:
            plain = False
    return rendered if plain else json.dumps(items, ensure_ascii=False)


def format_scalar(value: Any) -> str:
    """YAML representation of a value: plain if unambiguous, otherwise JSON (valid YAML).

    Args:
        value: Value of a frontmatter field.

    Returns:
        The representation for the right-hand side of ``key: …``.
    """
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif value is None:
        rendered = "null"
    elif isinstance(value, int | float):
        rendered = str(value)
    elif isinstance(value, list | tuple):
        rendered = _flow_list(list(value))
    elif isinstance(value, dict):
        rendered = json.dumps(value, ensure_ascii=False)
    else:
        s = str(value)
        rendered = s if _plain_ok(s) else json.dumps(s, ensure_ascii=False)
    return rendered


def dump_meta(meta: dict[str, Any]) -> str:
    """Write a complete frontmatter.

    Args:
        meta: Fields in the desired order.

    Returns:
        Frontmatter block including delimiter lines and a final LF.
    """
    lines = ["---", *(f"{key}: {format_scalar(value)}" for key, value in meta.items()), "---"]
    return "\n".join(lines) + "\n"


def _field_re(key: str) -> re.Pattern[str]:
    """Regex for the line of a top-level field.

    Args:
        key: Field name.

    Returns:
        Compiled regex that matches ``key:`` at the start of a line.
    """
    return re.compile(rf"^{re.escape(key)}[ \t]*:")


def _render(key: str, value: Any, block_lists: bool) -> list[str]:
    """Create the lines for a field.

    Args:
        key: Field name.
        value: Value.
        block_lists: Write lists as a YAML block list (``- …``) instead of on one line.

    Returns:
        The lines without LF.
    """
    if block_lists and isinstance(value, list | tuple):
        lines = [f"{key}:"] + [f"  - {format_scalar(v)}" for v in value] if value else [f"{key}: []"]
    else:
        lines = [f"{key}: {format_scalar(value)}"]
    return lines


def _value_end(inner: list[str], start: int) -> int:
    """Determine the end of a multi-line field value.

    Args:
        inner: Frontmatter lines without delimiters.
        start: Index of the field line.

    Returns:
        Index after the last continuation line (indented or block list entry).
    """
    j = start + 1
    while j < len(inner) and inner[j].strip() and (
        inner[j][:1] in (" ", "\t") or inner[j].startswith("- ") or inner[j] == "-"
    ):
        j += 1
    return j


def _insert_position(inner: list[str], key: str) -> int:
    """Insertion point for a new field according to the schema order (4.1).

    Args:
        inner: Frontmatter lines without delimiters.
        key: New field.

    Returns:
        Index after the last existing field that precedes ``key`` in the schema; before the first
        following schema field if there is no preceding one; otherwise the end.
    """
    rank = field_rank(key)
    at = len(inner)
    if rank is not None:
        tops = [(i, m.group(1)) for i, line in enumerate(inner) if (m := TOP_LEVEL_FIELD_RE.match(line))]
        before = [i for i, k in tops if (r := field_rank(k)) is not None and r < rank]
        after = [i for i, k in tops if (r := field_rank(k)) is not None and r > rank]
        if before:
            at = _value_end(inner, max(before))
        elif after:
            at = min(after)
    return at


def _apply_fields(inner: list[str], fields: dict[str, Any], block_lists: bool) -> list[str]:
    """Replace or append fields in the frontmatter lines.

    Args:
        inner: Frontmatter lines without delimiters.
        fields: Fields to set.
        block_lists: Write lists as a YAML block list.

    Returns:
        New list of lines; unaffected lines stay unchanged.
    """
    lines = list(inner)
    for key, value in fields.items():
        rendered = _render(key, value, block_lists)
        rx = _field_re(key)
        pos = next((i for i, line in enumerate(lines) if rx.match(line)), None)
        if pos is None:
            at = _insert_position(lines, key)
            lines[at:at] = rendered
        else:
            lines[pos:_value_end(lines, pos)] = rendered
    return lines


def set_fields_linewise(text: str, fields: dict[str, Any], block_lists: bool = False) -> str:
    """Set fields in the frontmatter line by line; a missing frontmatter is created.

    Args:
        text: Normalized text with valid or without frontmatter.
        fields: Fields to set.
        block_lists: Write lists as a YAML block list.

    Returns:
        The new text; all other lines stay unchanged.

    Raises:
        ValueError: For frontmatter without a closing line.
    """
    has_fm, fm_text, inner, body, err = split_frontmatter(text)
    if err is not None:
        raise ValueError(err)
    if not has_fm:
        lines = ["---", *(ln for k, v in fields.items() for ln in _render(k, v, block_lists)), "---"]
        result = "\n".join(lines) + "\n" + text
    else:
        closing = fm_text.rstrip("\n").rsplit("\n", maxsplit=1)[-1]
        result = "\n".join(["---", *_apply_fields(inner, fields, block_lists), closing]) + "\n" + body
    return result

def _line_is_valid(line: str) -> bool:
    """Check whether a frontmatter line is valid YAML on its own.

    Args:
        line: Top-level line (``key: value``).

    Returns:
        ``True`` if the line can be read without errors.
    """
    try:
        load_yaml(line)
        valid = True
    except yaml.YAMLError:
        valid = False
    return valid


def _fix_line(line: str) -> tuple[str, list[str]]:
    """Repair a frontmatter line (4.1).

    Renames ``short citation`` to ``short_citation`` and puts values that are invalid as YAML
    (e.g. with ``: `` or a leading special character) in double quotes.

    Args:
        line: Line without LF.

    Returns:
        Tuple of (new line, descriptions of the changes).
    """
    changes: list[str] = []
    m = TOP_LEVEL_FIELD_RE.match(line)
    if m and not line[:1].isspace():
        key, value = m.group(1), (m.group(2) or "")
        if key == LEGACY_SHORT_CITATION:
            key = SHORT_CITATION
            changes.append(f"{LEGACY_SHORT_CITATION} → {SHORT_CITATION}")
        if value.strip() and not _line_is_valid(f"k: {value}"):
            value = json.dumps(value.strip(), ensure_ascii=False)
            changes.append(f"{key}: quotes added")
        if changes:
            line = f"{key}: {value}" if value else f"{key}:"
    return line, changes


def fix_frontmatter_text(text: str) -> tuple[str, list[str]]:
    """Repair the frontmatter line by line; the remaining text stays unchanged (``pkm fix-frontmatter``).

    If ``short_citation`` already exists, an additional ``short citation`` line stays unchanged.

    Args:
        text: Normalized file text.

    Returns:
        Tuple of (new text, list of changes); unchanged without frontmatter.
    """
    lines = text.split("\n")
    changes: list[str] = []
    close = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None) if lines[0] == "---" else None
    if close is not None:
        has_new_name = any(ln.startswith(f"{SHORT_CITATION}:") for ln in lines[1:close])
        for i in range(1, close):
            if not (has_new_name and lines[i].startswith(f"{LEGACY_SHORT_CITATION}:")):
                lines[i], line_changes = _fix_line(lines[i])
                changes.extend(line_changes)
    return "\n".join(lines), changes


# Main ************************************************************************
