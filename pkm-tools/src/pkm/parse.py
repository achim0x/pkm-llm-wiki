"""Frontmatter, body and sections (specification 4.8, steps 2 and 3).

Input is always already normalized text (``normalize.normalize_text``).

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
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import yaml

# Variables *******************************************************************

PREAMBLE = "_preamble"

ATX_RE = re.compile(r"^ {0,3}(#{1,2})(?:[ \t]+(.*?))?[ \t]*$")
ATX_CLOSE_RE = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
FENCE_OPEN_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
LIST_RE = re.compile(r"^ {0,3}([-*+]|\d+[.)])[ \t]")
MAX_FENCE_INDENT = 3

# Classes *********************************************************************


class _Loader(yaml.SafeLoader):  # pylint: disable=too-many-ancestors
    """SafeLoader without automatic date conversion: timestamps stay strings."""


_Loader.yaml_implicit_resolvers = {
    key: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


@dataclass
class Section:
    """Section of a document per 4.8.

    Attributes:
        key: Section key, possibly with a duplicate suffix (``Notes#2``) or ``_preamble``.
        level: 0 for the preamble, otherwise 1 or 2.
        heading: Heading line without LF; ``None`` for the preamble.
        start: Index of the first line (heading or preamble) in the body lines.
        end: Index after the last line (exclusive).
        content_lines: Lines without heading and without LF.
        base: Heading text as key without duplicate suffix.
    """

    key: str
    level: int
    heading: str | None
    start: int
    end: int
    content_lines: list[str] = field(default_factory=list)
    base: str = ""


@dataclass
class Parsed:  # pylint: disable=too-many-instance-attributes
    """Parsed document.

    Attributes:
        text: Normalized full text.
        has_frontmatter: Whether the first line is ``---``.
        frontmatter_text: Frontmatter including delimiter lines and LF; empty without frontmatter.
        fm_inner_lines: YAML lines without delimiters.
        meta: Parsed fields.
        fm_error: Error text for an invalid frontmatter, otherwise ``None``.
        body: Everything after the frontmatter.
        sections: Sections in document order.
    """

    text: str
    has_frontmatter: bool
    frontmatter_text: str
    fm_inner_lines: list[str]
    meta: dict[str, Any]
    fm_error: str | None
    body: str
    sections: list[Section]

    @property
    def body_lines(self) -> list[str]:
        """Lines of the body.

        Returns:
            Lines without LF (see ``body_lines``).
        """
        return body_lines(self.body)

    def section_keys(self) -> list[str]:
        """All section keys.

        Returns:
            Keys in document order.
        """
        return [s.key for s in self.sections]

    def section(self, key: str) -> Section | None:
        """Find the section for a key.

        Args:
            key: Section key (with suffix for duplicates).

        Returns:
            The section or ``None``.
        """
        return next((s for s in self.sections if s.key == key), None)

# Functions *******************************************************************


def load_yaml(text: str) -> Any:
    """Load YAML safely without converting timestamps into date objects.

    Args:
        text: YAML text.

    Returns:
        The loaded data.

    Raises:
        yaml.YAMLError: For invalid YAML.
    """
    return yaml.load(text, Loader=_Loader)  # noqa: S506 - SafeLoader subclass


def split_frontmatter(text: str) -> tuple[bool, str, list[str], str, str | None]:
    """Split the frontmatter from the body (4.8, step 2).

    Args:
        text: Normalized file text.

    Returns:
        Tuple of (frontmatter present, frontmatter text, inner lines, body, error text).
        If the closing line is missing, the error text is set and the body is the whole text.
    """
    lines = text.split("\n")
    result: tuple[bool, str, list[str], str, str | None] = (False, "", [], text, None)
    if lines and lines[0] == "---":
        close = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
        if close is None:
            result = (True, "", [], text, "Frontmatter without closing line (--- or ...).")
        else:
            fm_text = "\n".join(lines[: close + 1]) + "\n"
            result = (True, fm_text, lines[1:close], "\n".join(lines[close + 1 :]), None)
    return result


def parse_meta(inner_lines: list[str]) -> tuple[dict[str, Any], str | None]:
    """Read the YAML lines of the frontmatter.

    Args:
        inner_lines: Lines between the delimiters.

    Returns:
        Tuple of (fields, error text); on errors the fields are empty.
    """
    raw = "\n".join(inner_lines)
    meta: dict[str, Any] = {}
    error: str | None = None
    if raw.strip():
        try:
            data = load_yaml(raw)
        except yaml.YAMLError as exc:
            data, error = None, f"Invalid YAML in the frontmatter: {exc}"
        if isinstance(data, dict):
            meta = {str(k): v for k, v in data.items()}
        elif data is not None:
            error = "Frontmatter is not a mapping (key: value)."
    return meta, error


def heading_key(raw: str) -> str:
    """Build the section key from the heading content (4.8, step 3).

    Args:
        raw: Heading content without the leading ``#``.

    Returns:
        Key without ATX closing sequence, with collapsed whitespace.
    """
    raw = ATX_CLOSE_RE.sub("", raw) if raw else ""
    return " ".join(raw.split())


def normalize_key_input(key: str) -> str:
    """Bring user input for ``section`` into key form (``## Text`` → ``Text``).

    Args:
        key: Input, e.g. ``"## Open  points"``, ``"Notes#2"`` or ``"_preamble"``.

    Returns:
        The normalized key.
    """
    key = key.strip()
    result = key
    if key != PREAMBLE:
        m = re.match(r"^#{1,6}[ \t]+(.*)$", key)
        if m:
            key = m.group(1)
        base, sep, num = key.rpartition("#")
        result = f"{heading_key(base)}#{num}" if sep and num.isdigit() and base else heading_key(key)
    return result


def _closes_fence(line: str, fence: tuple[str, int]) -> bool:
    """Check whether a line closes an open code fence (CommonMark).

    Args:
        line: Line without LF.
        fence: Fence character and minimum length of the open fence.

    Returns:
        ``True`` if the line closes the fence.
    """
    ch, length = fence
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    run = len(stripped) - len(stripped.lstrip(ch))
    return indent <= MAX_FENCE_INDENT and run >= length and not stripped[run:].strip()


def iter_outside_fences(lines: list[str]) -> Iterator[tuple[int, str]]:
    """Iterate over the lines outside fenced code blocks (without fence lines).

    Args:
        lines: Lines without LF.

    Yields:
        Tuples of (index, line).
    """
    fence: tuple[str, int] | None = None
    for i, line in enumerate(lines):
        if fence is not None:
            if _closes_fence(line, fence):
                fence = None
            continue
        m = FENCE_OPEN_RE.match(line)
        if m and not (m.group(2)[0] == "`" and "`" in m.group(3)):
            fence = (m.group(2)[0], len(m.group(2)))
            continue
        yield i, line


def _is_setext_underline(line: str, prev: str | None) -> bool:
    """Check whether a line is a setext underline of the previous line.

    Args:
        line: Current line.
        prev: Previous line outside code blocks or ``None``.

    Returns:
        ``True`` for a setext heading.
    """
    return bool(
        SETEXT_RE.match(line)
        and prev is not None
        and prev.strip()
        and not ATX_RE.match(prev)
        and not prev.lstrip().startswith(("#", ">"))
        and not LIST_RE.match(prev)
        and not SETEXT_RE.match(prev)
    )


def find_setext(lines: list[str]) -> list[int]:
    """Find lines with a setext underline (no section boundary, lint hint).

    Args:
        lines: Body lines without LF.

    Returns:
        Indices of the underline lines.
    """
    result: list[int] = []
    prev: str | None = None
    for i, line in iter_outside_fences(lines):
        if _is_setext_underline(line, prev):
            result.append(i)
        prev = line
    return result


def find_headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """Find boundary headings of levels 1 and 2 outside code blocks.

    Args:
        lines: Body lines without LF.

    Returns:
        List of (line index, level, raw content).
    """
    result: list[tuple[int, int, str]] = []
    for i, line in iter_outside_fences(lines):
        m = ATX_RE.match(line)
        if m:
            result.append((i, len(m.group(1)), m.group(2) or ""))
    return result


def body_lines(body: str) -> list[str]:
    """Split the body into lines.

    Args:
        body: Body text.

    Returns:
        Lines without LF; the LF at the end of the file does not create an additional empty element.
    """
    lines = body.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def _assign_keys(bases: list[str]) -> list[str]:
    """Assign section keys with duplicate suffix (4.8, step 3).

    Numbers whose key already occurs as a literal heading (e.g. "Version#2")
    or is already assigned are skipped.

    Args:
        bases: Keys of the headings without suffix, in document order.

    Returns:
        Unique keys in the same order.
    """
    literal = set(bases)
    used: set[str] = set()
    last: dict[str, int] = {}
    keys: list[str] = []
    for base in bases:
        if base not in used:
            key = base
            last.setdefault(base, 1)
        else:
            n = last.get(base, 1) + 1
            while f"{base}#{n}" in literal or f"{base}#{n}" in used:
                n += 1
            last[base] = n
            key = f"{base}#{n}"
        used.add(key)
        keys.append(key)
    return keys


def split_sections(body: str) -> list[Section]:
    """Split the body into sections (preamble, level 1 and 2).

    Args:
        body: Body text (normalized).

    Returns:
        Sections in document order; the preamble only if it has content.
    """
    lines = body_lines(body)
    heads = find_headings(lines)
    sections: list[Section] = []
    first = heads[0][0] if heads else len(lines)
    if any(ln.strip() for ln in lines[:first]):
        sections.append(Section(PREAMBLE, 0, None, 0, first, lines[:first]))
    bases = [heading_key(raw) for _, _, raw in heads]
    for idx, key in enumerate(_assign_keys(bases)):
        line_no, level, _raw = heads[idx]
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        sections.append(Section(key, level, lines[line_no], line_no, end, lines[line_no + 1 : end], bases[idx]))
    return sections


def parse(text: str) -> Parsed:
    """Fully parse normalized text.

    With an invalid frontmatter the raw text stays readable; the sections then cover the
    whole text and ``fm_error`` is set.

    Args:
        text: Normalized file text.

    Returns:
        The parsed document.
    """
    has_fm, fm_text, inner, body, err = split_frontmatter(text)
    meta: dict[str, Any] = {}
    if has_fm and err is None:
        meta, err = parse_meta(inner)
    if err is not None:
        parsed = Parsed(text, True, "", [], {}, err, text, split_sections(text))
    else:
        parsed = Parsed(text, has_fm, fm_text, inner, meta, None, body, split_sections(body))
    return parsed


def strip_frontmatter(content: str) -> str:
    """Remove frontmatter supplied with chat content (create/rewrite).

    Args:
        content: Content from the chat.

    Returns:
        Content without a valid frontmatter; an invalid one is kept as text.
    """
    has_fm, _fm, _inner, body, err = split_frontmatter(content)
    return body if has_fm and err is None else content

# Main ************************************************************************
