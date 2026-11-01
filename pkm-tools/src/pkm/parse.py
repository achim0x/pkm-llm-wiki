"""Frontmatter, Body und Abschnitte (Spezifikation 4.8, Schritte 2 und 3).

Eingabe ist immer bereits normalisierter Text (``normalize.normalize_text``).

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
    """SafeLoader ohne automatische Datums-Umwandlung: Zeitstempel bleiben Strings."""


_Loader.yaml_implicit_resolvers = {
    key: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


@dataclass
class Section:
    """Abschnitt eines Dokuments nach 4.8.

    Attributes:
        key: Abschnittsschlüssel, ggf. mit Duplikat-Suffix (``Notizen#2``) oder ``_preamble``.
        level: 0 für den Vorspann, sonst 1 oder 2.
        heading: Überschriftenzeile ohne LF; ``None`` beim Vorspann.
        start: Index der ersten Zeile (Überschrift bzw. Vorspann) in den Body-Zeilen.
        end: Index nach der letzten Zeile (exklusiv).
        content_lines: Zeilen ohne Überschrift und ohne LF.
        base: Überschriftentext als Schlüssel ohne Duplikat-Suffix.
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
    """Zerlegtes Dokument.

    Attributes:
        text: Normalisierter Gesamttext.
        has_frontmatter: Ob die erste Zeile ``---`` ist.
        frontmatter_text: Frontmatter inklusive Begrenzungszeilen und LF; leer ohne Frontmatter.
        fm_inner_lines: YAML-Zeilen ohne Begrenzer.
        meta: Gelesene Felder.
        fm_error: Fehlertext bei ungültigem Frontmatter, sonst ``None``.
        body: Alles nach dem Frontmatter.
        sections: Abschnitte in Dokumentreihenfolge.
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
        """Zeilen des Body.

        Returns:
            Zeilen ohne LF (siehe ``body_lines``).
        """
        return body_lines(self.body)

    def section_keys(self) -> list[str]:
        """Alle Abschnittsschlüssel.

        Returns:
            Schlüssel in Dokumentreihenfolge.
        """
        return [s.key for s in self.sections]

    def section(self, key: str) -> Section | None:
        """Abschnitt zu einem Schlüssel suchen.

        Args:
            key: Abschnittsschlüssel (mit Suffix bei Duplikaten).

        Returns:
            Den Abschnitt oder ``None``.
        """
        return next((s for s in self.sections if s.key == key), None)

# Functions *******************************************************************


def load_yaml(text: str) -> Any:
    """YAML sicher laden, ohne Zeitstempel in Datumsobjekte umzuwandeln.

    Args:
        text: YAML-Text.

    Returns:
        Die geladenen Daten.

    Raises:
        yaml.YAMLError: Bei ungültigem YAML.
    """
    return yaml.load(text, Loader=_Loader)  # noqa: S506 - SafeLoader-Unterklasse


def split_frontmatter(text: str) -> tuple[bool, str, list[str], str, str | None]:
    """Frontmatter vom Body trennen (4.8, Schritt 2).

    Args:
        text: Normalisierter Dateitext.

    Returns:
        Tupel aus (Frontmatter vorhanden, Frontmatter-Text, innere Zeilen, Body, Fehlertext).
        Fehlt die Abschlusszeile, ist der Fehlertext gesetzt und der Body der ganze Text.
    """
    lines = text.split("\n")
    result: tuple[bool, str, list[str], str, str | None] = (False, "", [], text, None)
    if lines and lines[0] == "---":
        close = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
        if close is None:
            result = (True, "", [], text, "Frontmatter ohne Abschlusszeile (--- oder ...).")
        else:
            fm_text = "\n".join(lines[: close + 1]) + "\n"
            result = (True, fm_text, lines[1:close], "\n".join(lines[close + 1 :]), None)
    return result


def parse_meta(inner_lines: list[str]) -> tuple[dict[str, Any], str | None]:
    """YAML-Zeilen des Frontmatters lesen.

    Args:
        inner_lines: Zeilen zwischen den Begrenzern.

    Returns:
        Tupel aus (Felder, Fehlertext); bei Fehlern sind die Felder leer.
    """
    raw = "\n".join(inner_lines)
    meta: dict[str, Any] = {}
    error: str | None = None
    if raw.strip():
        try:
            data = load_yaml(raw)
        except yaml.YAMLError as exc:
            data, error = None, f"Ungültiges YAML im Frontmatter: {exc}"
        if isinstance(data, dict):
            meta = {str(k): v for k, v in data.items()}
        elif data is not None:
            error = "Frontmatter ist keine Zuordnung (key: value)."
    return meta, error


def heading_key(raw: str) -> str:
    """Abschnittsschlüssel aus dem Überschrifteninhalt bilden (4.8, Schritt 3).

    Args:
        raw: Überschrifteninhalt ohne die führenden ``#``.

    Returns:
        Schlüssel ohne ATX-Abschluss, mit zusammengefasstem Leerraum.
    """
    raw = ATX_CLOSE_RE.sub("", raw) if raw else ""
    return " ".join(raw.split())


def normalize_key_input(key: str) -> str:
    """Nutzereingabe für ``section`` auf die Schlüsselform bringen (``## Text`` → ``Text``).

    Args:
        key: Eingabe, z. B. ``"## Offene  Punkte"``, ``"Notizen#2"`` oder ``"_preamble"``.

    Returns:
        Der normalisierte Schlüssel.
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
    """Prüfen, ob eine Zeile einen offenen Codezaun schließt (CommonMark).

    Args:
        line: Zeile ohne LF.
        fence: Zaunzeichen und Mindestlänge des offenen Zauns.

    Returns:
        ``True``, wenn die Zeile den Zaun schließt.
    """
    ch, length = fence
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    run = len(stripped) - len(stripped.lstrip(ch))
    return indent <= MAX_FENCE_INDENT and run >= length and not stripped[run:].strip()


def iter_outside_fences(lines: list[str]) -> Iterator[tuple[int, str]]:
    """Zeilen außerhalb eingezäunter Codeblöcke durchlaufen (ohne Zaunzeilen).

    Args:
        lines: Zeilen ohne LF.

    Yields:
        Tupel aus (Index, Zeile).
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
    """Prüfen, ob eine Zeile eine Setext-Unterstreichung der vorigen Zeile ist.

    Args:
        line: Aktuelle Zeile.
        prev: Vorige Zeile außerhalb von Codeblöcken oder ``None``.

    Returns:
        ``True`` bei einer Setext-Überschrift.
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
    """Zeilen mit Setext-Unterstreichung finden (keine Abschnittsgrenze, Lint-Hinweis).

    Args:
        lines: Body-Zeilen ohne LF.

    Returns:
        Indizes der Unterstreichungszeilen.
    """
    result: list[int] = []
    prev: str | None = None
    for i, line in iter_outside_fences(lines):
        if _is_setext_underline(line, prev):
            result.append(i)
        prev = line
    return result


def find_headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """Grenzüberschriften der Ebenen 1 und 2 außerhalb von Codeblöcken finden.

    Args:
        lines: Body-Zeilen ohne LF.

    Returns:
        Liste von (Zeilenindex, Ebene, Rohinhalt).
    """
    result: list[tuple[int, int, str]] = []
    for i, line in iter_outside_fences(lines):
        m = ATX_RE.match(line)
        if m:
            result.append((i, len(m.group(1)), m.group(2) or ""))
    return result


def body_lines(body: str) -> list[str]:
    """Body in Zeilen zerlegen.

    Args:
        body: Body-Text.

    Returns:
        Zeilen ohne LF; das LF am Dateiende erzeugt kein zusätzliches leeres Element.
    """
    lines = body.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def _assign_keys(bases: list[str]) -> list[str]:
    """Abschnittsschlüssel mit Duplikat-Suffix vergeben (4.8, Schritt 3).

    Nummern, deren Schlüssel schon als wörtliche Überschrift vorkommt (z. B. „Version#2“)
    oder bereits vergeben ist, werden übersprungen.

    Args:
        bases: Schlüssel der Überschriften ohne Suffix, in Dokumentreihenfolge.

    Returns:
        Eindeutige Schlüssel in derselben Reihenfolge.
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
    """Body in Abschnitte zerlegen (Vorspann, Ebene 1 und 2).

    Args:
        body: Body-Text (normalisiert).

    Returns:
        Abschnitte in Dokumentreihenfolge; der Vorspann nur, wenn er Inhalt hat.
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
    """Normalisierten Text vollständig zerlegen.

    Bei ungültigem Frontmatter bleibt der Rohtext lesbar; die Abschnitte umfassen dann den
    ganzen Text und ``fm_error`` ist gesetzt.

    Args:
        text: Normalisierter Dateitext.

    Returns:
        Das zerlegte Dokument.
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
    """Mitgeliefertes Frontmatter aus Chat-Inhalt entfernen (create/rewrite).

    Args:
        content: Inhalt aus dem Chat.

    Returns:
        Inhalt ohne gültiges Frontmatter; ungültiges bleibt als Text erhalten.
    """
    has_fm, _fm, _inner, body, err = split_frontmatter(content)
    return body if has_fm and err is None else content

# Main ************************************************************************
