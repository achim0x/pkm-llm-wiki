"""Pfadprüfung, Unicode-NFC, plattformfeste Dateinamen (Spezifikation 5.5, 7.5)."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from .errors import PkmError

MAX_NAME = 120
WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss", "ẞ": "SS"}
CONFLICT_RE = re.compile(r"conflicted copy|konflikt", re.IGNORECASE)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def transliterate(s: str) -> str:
    """Umlaute ausschreiben (ä → ae …)."""
    return "".join(UMLAUTS.get(ch, ch) for ch in s)


def rel_posix(root: Path, path: Path) -> str:
    """Relativer Pfad mit `/` in NFC."""
    return nfc(path.relative_to(root).as_posix())


def safe_resolve(root: Path, rel: str) -> Path:
    """Relativen Pfad prüfen und auflösen. Kein `..`, nichts Absolutes, keine Symlinks nach außen."""
    rel = nfc(rel.strip().replace("\\", "/"))
    if not rel:
        raise PkmError("invalid_path", "Leerer Pfad.")
    pure = PurePosixPath(rel)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", rel):
        raise PkmError("invalid_path", "Absolute Pfade sind nicht erlaubt.", path=rel)
    if any(part == ".." for part in pure.parts):
        raise PkmError("invalid_path", "`..` ist in Pfaden nicht erlaubt.", path=rel)
    candidate = root.joinpath(*pure.parts)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PkmError("invalid_path", "Pfad zeigt aus dem Vault heraus.", path=rel) from exc
    return candidate


def slugify(title: str, max_len: int = 80) -> str:
    """Dateinamenstauglicher Slug: Kleinbuchstaben, Bindestriche, Umlaute ausgeschrieben."""
    s = transliterate(nfc(title))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = s[:max_len].rstrip("-")
    if not s:
        s = "dokument"
    if s.split(".")[0] in WINDOWS_RESERVED:
        s = f"{s}-doc"
    return s


def is_platform_safe_name(name: str) -> bool:
    """Gültig auf macOS und Windows (5.5)."""
    if not name or len(name) > MAX_NAME:
        return False
    if INVALID_CHARS.search(name):
        return False
    if name.endswith((".", " ")):
        return False
    return name.split(".")[0].lower() not in WINDOWS_RESERVED


def is_conflict_copy(name: str) -> bool:
    """Nextcloud-Konfliktkopie (Dateiname enthält „conflicted copy“ bzw. „Konflikt“)."""
    return bool(CONFLICT_RE.search(name))


def case_collisions(paths: Iterable[str]) -> list[list[str]]:
    """Gruppen von Pfaden, die sich nur in Groß-/Kleinschreibung unterscheiden."""
    groups: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        groups[nfc(p).casefold()].append(p)
    return [sorted(g) for g in groups.values() if len(g) > 1]
