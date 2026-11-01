"""Dokument-IDs ``d-YYYYMMDD-HHMM-xxxx`` (Spezifikation 4.1).

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
# along with this program.  If not, see <https://gnu.org>.

# *****************************************************************************

# Imports *********************************************************************

from __future__ import annotations

import re
import secrets
from collections.abc import Callable
from datetime import datetime

# Variables *******************************************************************

ALPHABET = "".join(c for c in "0123456789abcdefghijklmnopqrstuvwxyz" if c not in "01lo")
ID_RE = re.compile(rf"^d-\d{{8}}-\d{{4}}-[{ALPHABET}]{{4}}$")
MAX_ATTEMPTS = 50

# Classes *********************************************************************

# Functions *******************************************************************


def is_valid_id(value: object) -> bool:
    """Prüfen, ob ein Wert eine gültige Dokument-ID ist.

    Args:
        value: Beliebiger Wert, z. B. aus dem Frontmatter.

    Returns:
        ``True``, wenn ``value`` ein String im Format ``d-YYYYMMDD-HHMM-xxxx`` ist.
    """
    return isinstance(value, str) and bool(ID_RE.match(value))


def _random_suffix() -> str:
    """Vier Zufallszeichen aus dem ID-Alphabet erzeugen.

    Returns:
        Zufälliger Suffix für eine neue ID.
    """
    return "".join(secrets.choice(ALPHABET) for _ in range(4))


def new_id(
    now: datetime,
    exists: Callable[[str], bool] = lambda _id: False,
    rand: Callable[[], str] | None = None,
    attempts: int = MAX_ATTEMPTS,
) -> str:
    """Neue, noch nicht vergebene ID erzeugen.

    Args:
        now: Zeitpunkt der Vergabe (in ``PKM_TZ``).
        exists: Prüft, ob eine ID schon vergeben ist.
        rand: Liefert den Zufallsteil; ohne Angabe sichere Zufallszeichen.
        attempts: Höchstzahl an Versuchen.

    Returns:
        Eine freie ID.

    Raises:
        RuntimeError: Wenn nach ``attempts`` Versuchen keine freie ID gefunden wurde.
    """
    rand = rand or _random_suffix
    stamp = now.strftime("d-%Y%m%d-%H%M")
    candidates = (f"{stamp}-{rand()}" for _ in range(attempts))
    found = next((c for c in candidates if not exists(c)), None)
    if found is None:
        raise RuntimeError("Keine freie ID gefunden.")
    return found

# Main ************************************************************************
