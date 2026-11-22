"""IP addresses in documents (specification 4.1, 4.2): find them and read the classification.

Documents often contain example or anonymized IP addresses. Whether the addresses of a document are
concrete or placeholders only the user knows; the answer is kept in the frontmatter field
``ip_addresses`` (``placeholder`` | ``concrete``), exceptions that are concrete in
``ip_addresses_concrete``. Special addresses (unspecified, loopback, link-local, broadcast) are never
reported, well-known public services (``PKM_IP_WELL_KNOWN``) are listed separately and raise no
question, and an IPv4-like number only counts as an address in a network context (not e.g. the section
number 61.3.6.1 of a standard). Only unambiguous addresses are reported: an IPv4 address needs a network
context next to it (not only somewhere in the line) and no version prefix, an IPv6 address needs ``::`` or a
hex letter. Values the user named as "not an IP address" are kept per document in ``.pkm/state.json``
(``ip_not_addresses``) and are never reported again; the document itself gets no field for them.

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
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .config import DEFAULT_WELL_KNOWN
from .images import to_placeholders

# Variables *******************************************************************

IP_FIELD = "ip_addresses"
IP_CONCRETE_FIELD = "ip_addresses_concrete"
IP_CLASSES = ("placeholder", "concrete")
NOT_IP_KEY = "ip_not_addresses"
CONTEXT_CHARS = 40
MAX_FOUND = 20
IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\w.]*\d)")
IPV6_RE = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?:/\d{1,3})?(?![\w:])")
NETWORK_RANGES = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10",
    "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
NETWORK_WORDS_RE = re.compile(
    r"\b(?:ip|ipv4|ipv6|ip-adresse|host|hostname|server|adresse|address|gateway|dns|subnetz|subnet|netz|"
    r"network|netzwerk|router|ping|ssh|curl|wget|mount|nfs|smb|cifs|port|dhcp|vlan|lan|wlan)\b", re.IGNORECASE)
NUMBER_PREFIX_RE = re.compile(r"(?:abschnitt|abschn\.|kap\.|kapitel|teil|section|chapter|§|din|vde|iec|en|iso)"
                              r"\s*[\w-]*\s*$", re.IGNORECASE)
VERSION_PREFIX_RE = re.compile(r"\b(?:version|ver\.?|v|firmware|fw|release|build|rev\.?|revision|stand|ausgabe|"
                               r"update|patch|treiber|driver)\s*[:=]?\s*$", re.IGNORECASE)
HEX_LETTER_RE = re.compile(r"[a-fA-F]")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

# Classes *********************************************************************


@dataclass
class IpFindings:
    """IP addresses of a text.

    Attributes:
        found: Addresses that may be concrete or placeholders (question to the user).
        well_known: Well-known public services (always concrete, no question).
    """

    found: list[str] = field(default_factory=list)
    well_known: list[str] = field(default_factory=list)


# Functions *******************************************************************


def _address(candidate: str) -> Any:
    """Parsed address of a candidate (with optional prefix length).

    Args:
        candidate: Text match.

    Returns:
        ``ipaddress`` object or ``None`` if invalid.
    """
    try:
        value = ipaddress.ip_address(candidate.split("/", 1)[0])
    except ValueError:
        value = None
    return value


def _special(addr: Any) -> bool:
    """Whether an address is never reported: unspecified, loopback, link-local or broadcast.

    Args:
        addr: Address.

    Returns:
        ``True`` for special addresses.
    """
    return bool(addr.is_unspecified or addr.is_loopback or addr.is_link_local
                or str(addr) == "255.255.255.255")


def _ipv4_in_context(line: str, start: int, end: int, in_code: bool) -> bool:
    """Whether an IPv4-like number in a line counts as an address (context check).

    Args:
        line: Line of text.
        start: Start of the match.
        end: End of the match.
        in_code: Whether the match is in a code block or inline code.

    Returns:
        ``True`` for a private or documentation range, port, prefix length, scheme or path, code, or network
        terms within ``CONTEXT_CHARS`` characters; ``False`` after a section, standard, chapter or version prefix.
    """
    text = line[start:end]
    addr = _address(text)
    before, after = line[:start], line[end:]
    if NUMBER_PREFIX_RE.search(before) or VERSION_PREFIX_RE.search(before):
        return False
    near = line[max(0, start - CONTEXT_CHARS):end + CONTEXT_CHARS]
    return bool(any(addr in net for net in NETWORK_RANGES) or "/" in text or re.match(r":\d{1,5}\b", after)
                or before.endswith(("//", "@")) or in_code or NETWORK_WORDS_RE.search(near))


def _ipv6_unambiguous(value: str) -> bool:
    """Whether an IPv6-like match is clearly an address (not e.g. a time or a ratio).

    Args:
        value: Text match.

    Returns:
        ``True`` with ``::`` or a hex letter and at least two non-empty groups.
    """
    groups = [g for g in value.split("/", 1)[0].split(":") if g]
    return len(groups) >= 2 and ("::" in value or bool(HEX_LETTER_RE.search(value)))


def _code_spans(line: str) -> list[tuple[int, int]]:
    """Inline code spans of a line.

    Args:
        line: Line of text.

    Returns:
        (start, end) of each span.
    """
    return [(m.start(), m.end()) for m in INLINE_CODE_RE.finditer(line)]


def find_ip_details(text: str, well_known: Iterable[str] = DEFAULT_WELL_KNOWN,
                    not_ip: Iterable[str] = ()) -> IpFindings:
    """IP addresses in a text, after the rules of 4.2 (embedded images are skipped).

    Args:
        text: Markdown.
        well_known: Addresses of well-known public services (``PKM_IP_WELL_KNOWN``).
        not_ip: Values the user named as "not an IP address" for this document.

    Returns:
        ``found`` (at most ``MAX_FOUND``) and ``well_known``, each in order of appearance without duplicates.
    """
    known = set(well_known)
    skip = {str(v).strip() for v in not_ip}
    found: dict[str, None] = {}
    public: dict[str, None] = {}
    in_fence = False
    for line in to_placeholders(text).splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        spans = _code_spans(line)
        matches = sorted([*IPV4_RE.finditer(line), *IPV6_RE.finditer(line)], key=lambda m: m.start())
        for m in matches:
            value, addr = m.group(0), _address(m.group(0))
            in_code = in_fence or any(s <= m.start() and m.end() <= e for s, e in spans)
            if addr is None or _special(addr) or value in skip or value.split("/", 1)[0] in skip:
                continue
            if addr.version == 6 and not _ipv6_unambiguous(value):
                continue
            if addr.version == 4 and not _ipv4_in_context(line, m.start(), m.end(), in_code):
                continue
            (public if str(addr) in known else found)[value] = None
    return IpFindings(list(found)[:MAX_FOUND], list(public))


def find_ips(text: str, well_known: Iterable[str] = DEFAULT_WELL_KNOWN, not_ip: Iterable[str] = ()) -> list[str]:
    """IP addresses that raise the question "concrete or placeholder?".

    Args:
        text: Markdown.
        well_known: Addresses of well-known public services.
        not_ip: Values the user named as "not an IP address".

    Returns:
        ``find_ip_details(...).found``.
    """
    return find_ip_details(text, well_known, not_ip).found


def not_ip_values(state: dict[str, Any], doc_id: str | None) -> list[str]:
    """Values of a document the user named as "not an IP address" (``state.json``, key ``ip_not_addresses``).

    Args:
        state: Processing state.
        doc_id: Document ID.

    Returns:
        The values, empty without ID or entry.
    """
    values = (state.get(NOT_IP_KEY) or {}).get(doc_id or "") if doc_id else None
    return [str(v) for v in values] if isinstance(values, list) else []


def classification(meta: dict[str, Any]) -> str | None:
    """Classification of the IP addresses of a document from the frontmatter.

    Args:
        meta: Frontmatter.

    Returns:
        ``placeholder``, ``concrete`` or ``None`` (field missing or invalid: unclassified).
    """
    value = str(meta.get(IP_FIELD) or "").strip().lower()
    return value if value in IP_CLASSES else None


def concrete_exceptions(meta: dict[str, Any]) -> set[str]:
    """Addresses the document lists as concrete in ``ip_addresses_concrete``.

    Args:
        meta: Frontmatter.

    Returns:
        Addresses (as written, also without prefix length).
    """
    values = meta.get(IP_CONCRETE_FIELD)
    items = values if isinstance(values, list) else ([values] if values else [])
    return {str(v).strip().split("/", 1)[0] for v in items if str(v).strip()}


def address_class(meta: dict[str, Any], address: str) -> str | None:
    """Classification of one address of a document: exceptions first, then ``ip_addresses``.

    Args:
        meta: Frontmatter.
        address: Address as found.

    Returns:
        ``concrete``, ``placeholder`` or ``None``.
    """
    return "concrete" if address.split("/", 1)[0] in concrete_exceptions(meta) else classification(meta)


def unclassified(meta: dict[str, Any], found: list[str]) -> list[str]:
    """Found addresses without classification (no ``ip_addresses`` and not listed as concrete).

    Args:
        meta: Frontmatter.
        found: Found addresses.

    Returns:
        The unclassified addresses.
    """
    return [a for a in found if address_class(meta, a) is None]

# Main ************************************************************************
