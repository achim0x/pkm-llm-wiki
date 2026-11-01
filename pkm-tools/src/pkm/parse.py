"""Frontmatter, Body und Abschnitte (Spezifikation 4.8, Schritte 2 und 3).

Eingabe ist immer bereits normalisierter Text (normalize.normalize_text).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from .errors import PkmError

PREAMBLE = "_preamble"

ATX_RE = re.compile(r"^ {0,3}(#{1,2})(?:[ \t]+(.*?))?[ \t]*$")
ATX_CLOSE_RE = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
FENCE_OPEN_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")


class _Loader(yaml.SafeLoader):
    """SafeLoader ohne automatische Datums-Umwandlung: Zeitstempel bleiben Strings."""


_Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_yaml(text: str) -> Any:
    return yaml.load(text, Loader=_Loader)  # noqa: S506 - SafeLoader-Unterklasse


@dataclass
class Section:
    key: str
    level: int  # 0 = Vorspann, 1 oder 2
    heading: str | None  # Überschriftenzeile ohne LF
    start: int  # Index der ersten Zeile (Überschrift bzw. Vorspann) in body_lines
    end: int  # exklusiv
    content_lines: list[str] = field(default_factory=list)  # ohne Überschrift, ohne LF

    @property
    def content(self) -> str:
        return "\n".join(self.content_lines)


@dataclass
class Parsed:
    text: str
    has_frontmatter: bool
    frontmatter_text: str  # inklusive Begrenzungszeilen, mit LF am Ende; "" ohne Frontmatter
    fm_inner_lines: list[str]  # YAML-Zeilen ohne Begrenzer
    meta: dict[str, Any]
    fm_error: str | None
    body: str
    sections: list[Section]

    @property
    def body_lines(self) -> list[str]:
        return body_lines(self.body)

    def section_keys(self) -> list[str]:
        return [s.key for s in self.sections]

    def section(self, key: str) -> Section | None:
        for s in self.sections:
            if s.key == key:
                return s
        return None


def split_frontmatter(text: str) -> tuple[bool, str, list[str], str, str | None]:
    """→ (vorhanden, frontmatter_text, innere Zeilen, body, fehler)."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return False, "", [], text, None
    for i in range(1, len(lines)):
        if lines[i] in ("---", "..."):
            fm_text = "\n".join(lines[: i + 1]) + "\n"
            body = "\n".join(lines[i + 1 :])
            return True, fm_text, lines[1:i], body, None
    return True, "", [], text, "Frontmatter ohne Abschlusszeile (--- oder ...)."


def parse_meta(inner_lines: list[str]) -> tuple[dict[str, Any], str | None]:
    raw = "\n".join(inner_lines)
    if not raw.strip():
        return {}, None
    try:
        data = load_yaml(raw)
    except yaml.YAMLError as exc:
        return {}, f"Ungültiges YAML im Frontmatter: {exc}"
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return {}, "Frontmatter ist keine Zuordnung (key: value)."
    return {str(k): v for k, v in data.items()}, None


def heading_key(raw: str) -> str:
    """Abschnittsschlüssel aus dem Überschrifteninhalt (ohne führende #)."""
    raw = ATX_CLOSE_RE.sub("", raw) if raw else ""
    return " ".join(raw.split())


def normalize_key_input(key: str) -> str:
    """Nutzereingabe für `section` auf die Schlüsselform bringen (`## Text` → `Text`)."""
    key = key.strip()
    if key == PREAMBLE:
        return key
    m = re.match(r"^#{1,6}[ \t]+(.*)$", key)
    if m:
        key = m.group(1)
    base, sep, num = key.rpartition("#")
    if sep and num.isdigit() and base:
        return f"{heading_key(base)}#{num}"
    return heading_key(key)


def find_headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """Grenzüberschriften (Ebene 1/2) außerhalb eingezäunter Codeblöcke: (zeile, ebene, roh)."""
    result: list[tuple[int, int, str]] = []
    fence: tuple[str, int] | None = None
    for i, line in enumerate(lines):
        if fence is not None:
            ch, length = fence
            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)
            if indent <= 3 and stripped.startswith(ch * length):
                run = len(stripped) - len(stripped.lstrip(ch))
                if run >= length and not stripped[run:].strip():
                    fence = None
            continue
        m = FENCE_OPEN_RE.match(line)
        if m:
            marker, info = m.group(2), m.group(3)
            if not (marker[0] == "`" and "`" in info):
                fence = (marker[0], len(marker))
                continue
        m = ATX_RE.match(line)
        if m:
            result.append((i, len(m.group(1)), m.group(2) or ""))
    return result


def _normalized_content_empty(lines: list[str]) -> bool:
    return all(not ln.strip() for ln in lines)


def body_lines(body: str) -> list[str]:
    """Zeilen ohne LF. Das LF am Dateiende erzeugt kein zusätzliches leeres Element."""
    lines = body.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def split_sections(body: str) -> list[Section]:
    lines = body_lines(body)
    heads = find_headings(lines)
    sections: list[Section] = []
    first = heads[0][0] if heads else len(lines)
    pre = lines[:first]
    if not _normalized_content_empty(pre):
        sections.append(Section(PREAMBLE, 0, None, 0, first, pre))
    seen: dict[str, int] = {}
    for idx, (line_no, level, raw) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        base = heading_key(raw)
        n = seen.get(base, 0) + 1
        seen[base] = n
        key = base if n == 1 else f"{base}#{n}"
        sections.append(Section(key, level, lines[line_no], line_no, end, lines[line_no + 1 : end]))
    return sections


def parse(text: str) -> Parsed:
    has_fm, fm_text, inner, body, err = split_frontmatter(text)
    meta: dict[str, Any] = {}
    if has_fm and err is None:
        meta, err = parse_meta(inner)
    if err is not None:
        # Ungültiges Frontmatter: Rohtext bleibt lesbar, Abschnitte über den ganzen Text.
        return Parsed(text, True, "", [], {}, err, text, split_sections(text))
    return Parsed(text, has_fm, fm_text, inner, meta, None, body, split_sections(body))


def require_valid(p: Parsed) -> None:
    if p.fm_error:
        raise PkmError("invalid_frontmatter", p.fm_error)


def strip_frontmatter(content: str) -> str:
    """Mitgeliefertes Frontmatter aus Chat-Inhalt entfernen (create/rewrite)."""
    has_fm, _fm, _inner, body, err = split_frontmatter(content)
    if has_fm and err is None:
        return body
    return content
