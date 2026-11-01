"""Hashes nach Spezifikation 4.8, Schritt 4. Einzige Stelle für Hash-Berechnungen."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .parse import Parsed, Section

META_FIELDS = ("title", "topics", "related", "kind")
SHORT = 6


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def file_hash(normalized_text: str) -> str:
    """`hash`/`expected_hash`/`file_hash`: gesamte normalisierte Datei."""
    return sha256_text(normalized_text)


def normalize_section_content(lines: list[str]) -> str:
    """Zeilen rechts trimmen, Leerzeilen am Rand entfernen, Leerzeilenfolgen zusammenfassen."""
    out: list[str] = []
    for line in lines:
        line = line.rstrip()
        if not line and (not out or not out[-1]):
            continue
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def section_hash(section: Section) -> str:
    return sha256_text(normalize_section_content(section.content_lines))


def section_hashes(p: Parsed) -> dict[str, str]:
    return {s.key: section_hash(s) for s in p.sections}


def body_hash(p: Parsed) -> str:
    return sha256_text("".join(f"{s.key}\t{section_hash(s)}\n" for s in p.sections))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def meta_hash(meta: dict[str, Any]) -> str:
    data = {k: _jsonable(meta[k]) for k in META_FIELDS if k in meta}
    canon = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(canon)


def short(h: str) -> str:
    return h[:SHORT]


def matches(stored: str, given: str) -> bool:
    """Vergleich voller Hash mit (ggf. gekürztem) Präfix."""
    given = given.strip().lower()
    return bool(given) and stored.lower().startswith(given)


@dataclass(frozen=True)
class DocHashes:
    file_hash: str
    body_hash: str
    meta_hash: str
    sections: dict[str, str]


def compute(normalized_text: str, p: Parsed) -> DocHashes:
    return DocHashes(file_hash(normalized_text), body_hash(p), meta_hash(p.meta), section_hashes(p))
