"""Document IDs ``d-YYYYMMDD-HHMM-xxxx`` (specification 4.1).

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
    """Check whether a value is a valid document ID.

    Args:
        value: Any value, e.g. from the frontmatter.

    Returns:
        ``True`` if ``value`` is a string in the format ``d-YYYYMMDD-HHMM-xxxx``.
    """
    return isinstance(value, str) and bool(ID_RE.match(value))


def _random_suffix() -> str:
    """Generate four random characters from the ID alphabet.

    Returns:
        Random suffix for a new ID.
    """
    return "".join(secrets.choice(ALPHABET) for _ in range(4))


def new_id(
    now: datetime,
    exists: Callable[[str], bool] = lambda _id: False,
    rand: Callable[[], str] | None = None,
    attempts: int = MAX_ATTEMPTS,
) -> str:
    """Generate a new ID that is not yet in use.

    Args:
        now: Time of assignment (in ``PKM_TZ``).
        exists: Checks whether an ID is already in use.
        rand: Returns the random part; secure random characters by default.
        attempts: Maximum number of attempts.

    Returns:
        A free ID.

    Raises:
        RuntimeError: If no free ID was found after ``attempts`` attempts.
    """
    rand = rand or _random_suffix
    stamp = now.strftime("d-%Y%m%d-%H%M")
    candidates = (f"{stamp}-{rand()}" for _ in range(attempts))
    found = next((c for c in candidates if not exists(c)), None)
    if found is None:
        raise RuntimeError("No free ID found.")
    return found

# Main ************************************************************************
