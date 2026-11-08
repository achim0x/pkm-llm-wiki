"""Path checks, Unicode NFC and platform-safe file names (specification 5.5, 7.5).

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
SUBTITLE_RE = re.compile(r"\s+[–—-]\s+|:\s+")
UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss", "ẞ": "SS"}

# Classes *********************************************************************

# Functions *******************************************************************


def nfc(s: str) -> str:
    """Convert text to Unicode normal form NFC.

    Args:
        s: Any text, e.g. a file name in NFD from macOS.

    Returns:
        The text in NFC.
    """
    return unicodedata.normalize("NFC", s)


def transliterate(s: str) -> str:
    """Spell out umlauts and ß (ä → ae, ß → ss).

    Args:
        s: Any text.

    Returns:
        The text with spelled-out umlauts.
    """
    return "".join(UMLAUTS.get(ch, ch) for ch in s)


def safe_resolve(root: Path, rel: str) -> Path:
    """Check a relative path and resolve it inside the vault.

    Neither ``..`` nor absolute paths nor symlinks pointing out of the vault are allowed.

    Args:
        root: Vault root (resolved).
        rel: Relative path; ``\\`` is treated as ``/``.

    Returns:
        The path in the vault (not resolved, so that the name is kept).

    Raises:
        PkmError: ``invalid_path`` for empty, absolute or escaping paths.
    """
    rel = nfc(rel.strip().replace("\\", "/"))
    if not rel:
        raise PkmError("invalid_path", "Empty path.")
    pure = PurePosixPath(rel)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", rel):
        raise PkmError("invalid_path", "Absolute paths are not allowed.", path=rel)
    if any(part == ".." for part in pure.parts):
        raise PkmError("invalid_path", "`..` is not allowed in paths.", path=rel)
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(root)
    except ValueError as exc:
        raise PkmError("invalid_path", "Path points out of the vault.", path=rel) from exc
    return candidate


def slugify(title: str, max_len: int = 80) -> str:
    """Build a slug suitable for file names: lower case, hyphens, umlauts spelled out.

    Args:
        title: Title of the document.
        max_len: Maximum length of the slug.

    Returns:
        Slug that is valid on macOS and Windows (never empty, never a reserved name).
    """
    s = transliterate(nfc(title))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = s[:max_len].rstrip("-") or "document"
    if s.split(".", maxsplit=1)[0] in WINDOWS_RESERVED:
        s = f"{s}-doc"
    return s


def slug_words(text: str, max_len: int = 60) -> str:
    """Slug for a file name, shortened at a word boundary (hyphen) instead of in the middle of a word.

    Args:
        text: E.g. the alt text of an image.
        max_len: Maximum length.

    Returns:
        Slug; cut at the last hyphen within ``max_len`` if that keeps at least half of it.
    """
    s = slugify(text, 10 * max_len)
    if len(s) > max_len:
        cut = s[:max_len + 1].rfind("-")
        s = (s[:cut] if cut >= max_len // 2 else s[:max_len]).rstrip("-")
    return s


def title_slug(title: str, max_len: int = 60) -> str:
    """Short slug for a proposed document name: without subtitle, cut at a word boundary (4.1).

    Args:
        title: Title, e.g. ``Training from the Back of the Room – 65 Wege …``.
        max_len: Maximum length (``PKM_SLUG_MAX``).

    Returns:
        Slug of the text before the first `` – ``, `` - `` or ``: ``, at most ``max_len`` characters.
    """
    head = SUBTITLE_RE.split(title, maxsplit=1)[0].strip()
    return slug_words(head or title, max_len)


def fit_stem(stem: str, rest: str) -> str:
    """Shorten a name stem so that ``stem + rest`` has at most ``MAX_NAME`` characters.

    Args:
        stem: Slug.
        rest: Fixed rest of the name (suffix, date, extension); never shortened.

    Returns:
        Shortened slug without a trailing hyphen (at least one character).
    """
    room = max(1, MAX_NAME - len(rest))
    return stem[:room].rstrip("-") or stem[:1]


def is_platform_safe_name(name: str) -> bool:
    """Check whether a file or folder name is valid on macOS and Windows (5.5).

    Args:
        name: Single name component without ``/``.

    Returns:
        ``True`` if the name is allowed.
    """
    return bool(
        name
        and len(name) <= MAX_NAME
        and not INVALID_CHARS.search(name)
        and not name.endswith((".", " "))
        and name.split(".", maxsplit=1)[0].lower() not in WINDOWS_RESERVED
    )


def case_collisions(paths: Iterable[str]) -> list[list[str]]:
    """Find paths that differ only in upper/lower case.

    Args:
        paths: Relative paths.

    Returns:
        Groups (sorted) of colliding paths; empty if there are none.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        groups[nfc(p).casefold()].append(p)
    return [sorted(g) for g in groups.values() if len(g) > 1]

# Main ************************************************************************
