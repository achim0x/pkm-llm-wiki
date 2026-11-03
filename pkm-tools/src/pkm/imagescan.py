"""Bild-Data-URIs in jeder Schreibweise finden (Spezifikation 4.9, „Prüfung bei der Übernahme“).

Erkannt werden Markdown-Bilder ``![alt](data:…)``, spitze Klammern ``![alt](<data:…>)``, der
Referenzstil ``![alt][ref]`` mit ``[ref]: <data:…>`` und HTML ``<img src="data:…">``, auch mit nicht
kodierten Zeichen (z. B. SVG mit Leerzeichen). Codeblöcke und Inline-Code werden übergangen.

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
    """Eine Bild-Data-URI im Text.

    Attributes:
        notation: ``inline``, ``angle``, ``reference`` oder ``html``.
        start: Beginn des Bildes (bei ``reference`` der ersten Verwendung).
        end: Ende des Bildes.
        uri_start: Beginn der Data-URI.
        uri_end: Ende der Data-URI.
        alt: Alternativtext wie geschrieben (ggf. mit ``|breite``).
        title: Titel (``"…"``) oder ``None``.
        label: Referenzname (nur ``reference``).
        def_span: Zeile der Referenzdefinition einschließlich Zeilenende (nur ``reference``).
        usages: Positionen aller Verwendungen (nur ``reference``).
        width: Breite aus ``width`` (nur ``html``).
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
    """Bereiche von eingezäunten Codeblöcken und Inline-Code.

    Args:
        text: Markdown.

    Returns:
        Liste aus (Beginn, Ende).
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
    """Prüfen, ob eine Position in einem der Bereiche liegt.

    Args:
        pos: Position.
        spans: Bereiche.

    Returns:
        ``True`` innerhalb.
    """
    return any(s <= pos < e for s, e in spans)


def uri_end(text: str, start: int, stop: str) -> int:
    """Ende einer Data-URI ab ``start`` bestimmen.

    Base64 reicht bis zum ersten Zeichen außerhalb des Alphabets (Leerraum zählt mit, endet aber nicht
    darauf). SVG ohne Base64 reicht bis zum Ende des ``</svg>``-Tags (kodiert oder nicht) in derselben
    Zeile, sonst bis zum ersten Leerraum bzw. Stoppzeichen.

    Args:
        text: Markdown.
        start: Position von ``data:``.
        stop: Zeichen, die die URI ohne SVG-Ende beenden (z. B. ``)`` oder ``>``).

    Returns:
        Endposition (exklusiv).
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
    """Optionalen Titel ``"…"`` ab einer Position lesen.

    Args:
        text: Markdown.
        pos: Position direkt nach der URI bzw. nach ``>``.

    Returns:
        Tupel aus (Titel oder ``None``, Position danach).
    """
    m = TITLE_RE.match(text, pos)
    title = (m.group("d") if m.group("d") is not None else m.group("s")) if m else None
    return title, (m.end() if m else pos)


def _inline(text: str, spans: list[tuple[int, int]]) -> list[DataOccurrence]:
    """Markdown-Bilder ``![alt](data:…)`` und ``![alt](<data:…>)``.

    Args:
        text: Markdown.
        spans: Code-Bereiche.

    Returns:
        Vorkommen.
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
    """Referenzname vergleichbar machen (CommonMark: ohne Groß-/Kleinschreibung, Leerraum zusammengefasst).

    Args:
        label: Referenzname.

    Returns:
        Schlüssel.
    """
    return " ".join(label.split()).casefold()


def _references(text: str, spans: list[tuple[int, int]]) -> list[DataOccurrence]:
    """Referenzstil: Definitionen ``[ref]: <data:…>`` mit ihren Verwendungen ``![alt][ref]``.

    Args:
        text: Markdown.
        spans: Code-Bereiche.

    Returns:
        Vorkommen; unbenutzte Definitionen haben keine Verwendungen (``start == def_span[0]``).
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
    """HTML-Bilder ``<img src="data:…">``.

    Args:
        text: Markdown.
        spans: Code-Bereiche.

    Returns:
        Vorkommen.
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
    """Alle Bild-Data-URIs im Text (außerhalb von Code).

    Args:
        text: Markdown.

    Returns:
        Vorkommen nach Position der (ersten) Verwendung; unbenutzte Definitionen eingeschlossen.
    """
    spans = code_spans(text)
    found = _inline(text, spans) + _references(text, spans) + _html(text, spans)
    return sorted(found, key=lambda o: o.start)


def non_image_data_links(text: str) -> list[tuple[int, str]]:
    """Andere Data-URIs in Links (z. B. ``data:text/html``) für Lint.

    Args:
        text: Markdown.

    Returns:
        Liste aus (Position, Medientyp).
    """
    spans = code_spans(text)
    rx = re.compile(r"\]\(\s*<?data:(?P<type>[a-z]+/[a-z0-9.+-]+)", re.IGNORECASE)
    return [(m.start(), m.group("type").lower()) for m in rx.finditer(text)
            if not m.group("type").lower().startswith("image/") and not _inside(m.start(), spans)]

# Main ************************************************************************
