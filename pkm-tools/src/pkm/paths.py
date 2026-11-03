"""Pfadprüfung, Unicode-NFC und plattformfeste Dateinamen (Spezifikation 5.5, 7.5).

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
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from .errors import PkmError

# Variables *******************************************************************

MAX_NAME = 120
WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss", "ẞ": "SS"}
CONFLICT_RE = re.compile(r"conflicted copy|konflikt", re.IGNORECASE)

# Classes *********************************************************************

# Functions *******************************************************************


def nfc(s: str) -> str:
    """Text in Unicode-Normalform NFC bringen.

    Args:
        s: Beliebiger Text, z. B. ein Dateiname in NFD von macOS.

    Returns:
        Der Text in NFC.
    """
    return unicodedata.normalize("NFC", s)


def transliterate(s: str) -> str:
    """Umlaute und ß ausschreiben (ä → ae, ß → ss).

    Args:
        s: Beliebiger Text.

    Returns:
        Der Text mit ausgeschriebenen Umlauten.
    """
    return "".join(UMLAUTS.get(ch, ch) for ch in s)


def safe_resolve(root: Path, rel: str) -> Path:
    """Relativen Pfad prüfen und unterhalb des Vaults auflösen.

    Erlaubt sind weder ``..`` noch absolute Pfade noch Symlinks, die aus dem Vault zeigen.

    Args:
        root: Vault-Wurzel (aufgelöst).
        rel: Relativer Pfad, ``\\`` wird als ``/`` behandelt.

    Returns:
        Den Pfad im Vault (nicht aufgelöst, damit der Name erhalten bleibt).

    Raises:
        PkmError: ``invalid_path`` bei leeren, absoluten oder ausbrechenden Pfaden.
    """
    rel = nfc(rel.strip().replace("\\", "/"))
    if not rel:
        raise PkmError("invalid_path", "Leerer Pfad.")
    pure = PurePosixPath(rel)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", rel):
        raise PkmError("invalid_path", "Absolute Pfade sind nicht erlaubt.", path=rel)
    if any(part == ".." for part in pure.parts):
        raise PkmError("invalid_path", "`..` ist in Pfaden nicht erlaubt.", path=rel)
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(root)
    except ValueError as exc:
        raise PkmError("invalid_path", "Pfad zeigt aus dem Vault heraus.", path=rel) from exc
    return candidate


def slugify(title: str, max_len: int = 80) -> str:
    """Dateinamenstauglichen Slug bilden: Kleinbuchstaben, Bindestriche, Umlaute ausgeschrieben.

    Args:
        title: Titel des Dokuments.
        max_len: Höchstlänge des Slugs.

    Returns:
        Slug, der auf macOS und Windows gültig ist (nie leer, nie ein reservierter Name).
    """
    s = transliterate(nfc(title))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = s[:max_len].rstrip("-") or "dokument"
    if s.split(".", maxsplit=1)[0] in WINDOWS_RESERVED:
        s = f"{s}-doc"
    return s


def fit_stem(stem: str, rest: str) -> str:
    """Namensstamm so kürzen, dass ``stem + rest`` höchstens ``MAX_NAME`` Zeichen hat.

    Args:
        stem: Slug.
        rest: Fester Rest des Namens (Suffix, Datum, Endung), wird nie gekürzt.

    Returns:
        Gekürzter Slug ohne Bindestrich am Ende (mindestens ein Zeichen).
    """
    room = max(1, MAX_NAME - len(rest))
    return stem[:room].rstrip("-") or stem[:1]


def is_platform_safe_name(name: str) -> bool:
    """Prüfen, ob ein Datei- oder Ordnername auf macOS und Windows gültig ist (5.5).

    Args:
        name: Einzelner Namensbestandteil ohne ``/``.

    Returns:
        ``True``, wenn der Name zulässig ist.
    """
    return bool(
        name
        and len(name) <= MAX_NAME
        and not INVALID_CHARS.search(name)
        and not name.endswith((".", " "))
        and name.split(".", maxsplit=1)[0].lower() not in WINDOWS_RESERVED
    )


def is_conflict_copy(name: str) -> bool:
    """Nextcloud-Konfliktkopie am Dateinamen erkennen.

    Args:
        name: Dateiname.

    Returns:
        ``True``, wenn der Name „conflicted copy“ oder „Konflikt“ enthält.
    """
    return bool(CONFLICT_RE.search(name))


def case_collisions(paths: Iterable[str]) -> list[list[str]]:
    """Pfade finden, die sich nur in Groß-/Kleinschreibung unterscheiden.

    Args:
        paths: Relative Pfade.

    Returns:
        Gruppen (sortiert) kollidierender Pfade; leer, wenn es keine gibt.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        groups[nfc(p).casefold()].append(p)
    return [sorted(g) for g in groups.values() if len(g) > 1]

# Main ************************************************************************
