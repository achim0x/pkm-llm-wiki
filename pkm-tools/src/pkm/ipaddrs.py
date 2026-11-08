"""IP addresses in documents (specification 4.1, 9.5): find them and read the classification.

Documents often contain example or anonymized IP addresses. Whether the addresses of a document are
concrete or placeholders only the user knows; the answer is kept in the frontmatter field
``ip_addresses`` (``placeholder`` | ``concrete``). Until then nothing may be derived from them.

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

import ipaddress
import re
from typing import Any

from .images import to_placeholders

# Variables *******************************************************************

IP_FIELD = "ip_addresses"
IP_CLASSES = ("placeholder", "concrete")
MAX_FOUND = 20
IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\w.]*\d)")
IPV6_RE = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?:/\d{1,3})?(?![\w:])")

# Classes *********************************************************************

# Functions *******************************************************************


def _valid(candidate: str) -> str | None:
    """Normalized address if the candidate is a valid IPv4/IPv6 address (with optional prefix length).

    Args:
        candidate: Text match.

    Returns:
        The address as written (without trailing characters) or ``None``.
    """
    address = candidate.split("/", 1)[0]
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return None
    return candidate if ":" not in address or address.count(":") >= 2 else None


def find_ips(text: str) -> list[str]:
    """IP addresses in a text (embedded images are skipped).

    Args:
        text: Markdown.

    Returns:
        IPv4/IPv6 addresses in order of appearance, without duplicates, at most ``MAX_FOUND``.
    """
    plain = to_placeholders(text)
    found: dict[str, None] = {}
    for m in sorted([*IPV4_RE.finditer(plain), *IPV6_RE.finditer(plain)], key=lambda m: m.start()):
        value = _valid(m.group(0))
        if value and value not in found:
            found[value] = None
    return list(found)[:MAX_FOUND]


def classification(meta: dict[str, Any]) -> str | None:
    """Classification of the IP addresses of a document from the frontmatter.

    Args:
        meta: Frontmatter.

    Returns:
        ``placeholder``, ``concrete`` or ``None`` (field missing or invalid: unclassified).
    """
    value = str(meta.get(IP_FIELD) or "").strip().lower()
    return value if value in IP_CLASSES else None

# Main ************************************************************************
