"""Find image data URIs in every notation (specification 4.9, "check on import").

Detected are Markdown images ``![alt](data:…)``, angle brackets ``![alt](<data:…>)``, the
reference style ``![alt][ref]`` with ``[ref]: <data:…>`` and HTML ``<img src="data:…">``, also with
unencoded characters (e.g. SVG with spaces). Code blocks and inline code are skipped.

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
from dataclasses import dataclass, field

# Variables *******************************************************************

FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
CODE_SPAN_RE = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)")
INLINE_START_RE = re.compile(r"!\[(?P<alt>[^\]\n]*)\]\([ \t]*(?P<lt><)?(?=data:)", re.IGNORECASE)
DEF_RE = re.compile(r"^[ ]{0,3}\[(?P<label>[^\]\n]+)\]:[ \t]*(?P<lt><)?(?=data:)", re.IGNORECASE | re.MULTILINE)
USAGE_RE = re.compile(r"!\[(?P<alt>[^\]\n]*)\](?:\[(?P<label>[^\]\n]*)\])?(?![(\[:])")
IMG_TAG_RE = re.compile(r"<img\b", re.IGNORECASE)
SRC_RE = re.compile(r"""\bsrc\s*=\s*(["'])(?=data:)""", re.IGNORECASE)
TITLE_RE = re.compile(r"""[ \t]+(?:"(?P<d>[^"\n]*)"|'(?P<s>[^'\n]*)')""")
BASE64_RE = re.compile(r"[A-Za-z0-9+/=\s]*")
SVG_END = ("</svg>", "%3c/svg%3e", "%3c%2fsvg%3e")

# Classes *********************************************************************


@dataclass
class DataOccurrence:  # pylint: disable=too-many-instance-attributes
    """An image data URI in the text.

    Attributes:
        notation: ``inline``, ``angle``, ``reference`` or ``html``.
        start: Start of the image (for ``reference``, of the first usage).
        end: End of the image.
        uri_start: Start of the data URI.
        uri_end: End of the data URI.
        alt: Alt text as written (possibly with ``|width``).
        title: Title (``"…"``) or ``None``.
        label: Reference name (``reference`` only).
        def_span: Line of the reference definition including line end (``reference`` only).
        usages: Positions of all usages (``reference`` only).
        width: Width from ``width`` (``html`` only).
    """

    notation: str
    start: int
    end: int
    uri_start: int
    uri_end: int
    alt: str = ""
    title: str | None = None
    label: str | None = None
    def_span: tuple[int, int] | None = None
    usages: list[tuple[int, int]] = field(default_factory=list)
    width: str | None = None

# Functions *******************************************************************


def code_spans(text: str) -> list[tuple[int, int]]:
    """Ranges of fenced code blocks and inline code.

    Args:
        text: Markdown.

    Returns:
        List of (start, end).
    """
    spans: list[tuple[int, int]] = []
    pos, fence, fence_start = 0, "", 0
    for line in text.splitlines(keepends=True):
        m = FENCE_RE.match(line)
        if not fence and m:
            fence, fence_start = m.group(1), pos
        elif fence and m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
            spans.append((fence_start, pos + len(line)))
            fence = ""
        elif not fence:
            spans += [(pos + c.start(), pos + c.end()) for c in CODE_SPAN_RE.finditer(line)]
        pos += len(line)
    if fence:
        spans.append((fence_start, len(text)))
    return spans


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    """Check whether a position lies in one of the ranges.

    Args:
        pos: Position.
        spans: Ranges.

    Returns:
        ``True`` if inside.
    """
    return any(s <= pos < e for s, e in spans)


def uri_end(text: str, start: int, stop: str) -> int:
    """Determine the end of a data URI starting at ``start``.

    Base64 extends to the first character outside the alphabet (whitespace counts, but the URI does not
    end on it). SVG without Base64 extends to the end of the ``</svg>`` tag (encoded or not) in the same
    line, otherwise to the first whitespace or stop character.

    Args:
        text: Markdown.
        start: Position of ``data:``.
        stop: Characters that end the URI without an SVG end (e.g. ``)`` or ``>``).

    Returns:
        End position (exclusive).
    """
    line_end = text.find("\n", start)
    line_end = len(text) if line_end < 0 else line_end
    comma = text.find(",", start, line_end)
    end = line_end
    if comma >= 0 and text[start:comma].lower().endswith(";base64"):
        m = BASE64_RE.match(text, comma + 1)
        end = m.end() if m else comma + 1
        while end > comma + 1 and text[end - 1].isspace():
            end -= 1
    elif comma >= 0:
        low = text[comma:line_end].lower()
        ends = [low.find(t) + len(t) for t in SVG_END if low.find(t) >= 0]
        if ends:
            end = comma + min(ends)
        else:
            m = re.compile(rf"[\s{re.escape(stop)}]").search(text, comma + 1, line_end)
            end = m.start() if m else line_end
    return end


def _title_after(text: str, pos: int) -> tuple[str | None, int]:
    """Read an optional title ``"…"`` at a position.

    Args:
        text: Markdown.
        pos: Position directly after the URI or after ``>``.

    Returns:
        Tuple of (title or ``None``, position after it).
    """
    m = TITLE_RE.match(text, pos)
    title = (m.group("d") if m.group("d") is not None else m.group("s")) if m else None
    return title, (m.end() if m else pos)


def _inline(text: str, spans: list[tuple[int, int]]) -> list[DataOccurrence]:
    """Markdown images ``![alt](data:…)`` and ``![alt](<data:…>)``.

    Args:
        text: Markdown.
        spans: Code ranges.

    Returns:
        Occurrences.
    """
    out = []
    for m in INLINE_START_RE.finditer(text):
        if _inside(m.start(), spans):
            continue
        angle = bool(m.group("lt"))
        u_start = m.end()
        u_end = uri_end(text, u_start, ">" if angle else ")")
        pos = u_end + 1 if angle and text[u_end:u_end + 1] == ">" else u_end
        title, pos = _title_after(text, pos)
        close = re.compile(r"[ \t]*\)").match(text, pos)
        if close:
            out.append(DataOccurrence("angle" if angle else "inline", m.start(), close.end(), u_start, u_end,
                                      m.group("alt"), title))
    return out


def _label_key(label: str) -> str:
    """Make a reference name comparable (CommonMark: case-insensitive, whitespace collapsed).

    Args:
        label: Reference name.

    Returns:
        Key.
    """
    return " ".join(label.split()).casefold()


def _references(text: str, spans: list[tuple[int, int]]) -> list[DataOccurrence]:
    """Reference style: definitions ``[ref]: <data:…>`` with their usages ``![alt][ref]``.

    Args:
        text: Markdown.
        spans: Code ranges.

    Returns:
        Occurrences; unused definitions have no usages (``start == def_span[0]``).
    """
    defs: dict[str, DataOccurrence] = {}
    for m in DEF_RE.finditer(text):
        if _inside(m.start(), spans):
            continue
        angle = bool(m.group("lt"))
        u_start = m.end()
        u_end = uri_end(text, u_start, ">" if angle else " ")
        pos = u_end + 1 if angle and text[u_end:u_end + 1] == ">" else u_end
        title, _ = _title_after(text, pos)
        line_end = text.find("\n", m.start())
        span = (m.start(), len(text) if line_end < 0 else line_end + 1)
        key = _label_key(m.group("label"))
        if key not in defs:
            defs[key] = DataOccurrence("reference", span[0], span[0], u_start, u_end, "", title,
                                       m.group("label"), span)
    for m in USAGE_RE.finditer(text):
        label = m.group("label") or m.group("alt")
        occ = defs.get(_label_key(label)) if label is not None else None
        if occ is not None and not _inside(m.start(), spans):
            occ.usages.append((m.start(), m.end()))
    for occ in defs.values():
        if occ.usages:
            first = occ.usages[0]
            occ.start, occ.end = first
            occ.alt = USAGE_RE.match(text, first[0]).group("alt")  # type: ignore[union-attr]
    return list(defs.values())


def _html(text: str, spans: list[tuple[int, int]]) -> list[DataOccurrence]:
    """HTML images ``<img src="data:…">``.

    Args:
        text: Markdown.
        spans: Code ranges.

    Returns:
        Occurrences.
    """
    out = []
    for m in IMG_TAG_RE.finditer(text):
        line_end = text.find("\n", m.start())
        line_end = len(text) if line_end < 0 else line_end
        src = SRC_RE.search(text, m.end(), line_end)
        if src is None or _inside(m.start(), spans):
            continue
        quote = src.group(1)
        u_start = src.end()
        close_quote = text.find(quote, u_start)
        u_end = close_quote if close_quote >= 0 else uri_end(text, u_start, quote)
        tag_end = text.find(">", u_end)
        tag_end = len(text) if tag_end < 0 else tag_end + 1
        attrs = text[m.start():m.end()] + text[u_end + 1:tag_end]
        alt = re.search(r"""\balt\s*=\s*(["'])(.*?)\1""", attrs, re.IGNORECASE)
        width = re.search(r"""\bwidth\s*=\s*["']?(\d+)""", attrs, re.IGNORECASE)
        title = re.search(r"""\btitle\s*=\s*(["'])(.*?)\1""", attrs, re.IGNORECASE)
        out.append(DataOccurrence("html", m.start(), tag_end, u_start, u_end, alt.group(2) if alt else "",
                                  title.group(2) if title else None, width=width.group(1) if width else None))
    return out


def find_data_images(text: str) -> list[DataOccurrence]:
    """All image data URIs in the text (outside of code).

    Args:
        text: Markdown.

    Returns:
        Occurrences by position of the (first) usage; unused definitions included.
    """
    spans = code_spans(text)
    found = _inline(text, spans) + _references(text, spans) + _html(text, spans)
    return sorted(found, key=lambda o: o.start)


def non_image_data_links(text: str) -> list[tuple[int, str]]:
    """Other data URIs in links (e.g. ``data:text/html``) for lint.

    Args:
        text: Markdown.

    Returns:
        List of (position, media type).
    """
    spans = code_spans(text)
    rx = re.compile(r"\]\(\s*<?data:(?P<type>[a-z]+/[a-z0-9.+-]+)", re.IGNORECASE)
    return [(m.start(), m.group("type").lower()) for m in rx.finditer(text)
            if not m.group("type").lower().startswith("image/") and not _inside(m.start(), spans)]

# Main ************************************************************************
