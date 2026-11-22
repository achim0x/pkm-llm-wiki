"""Anonymize IP addresses in a document (specification 4.1, 7.7), only after the user's confirmation.

Every found address is replaced by an address from the ranges reserved for documentation (IPv4
``192.0.2.0/24``, ``198.51.100.0/24``, ``203.0.113.0/24``, IPv6 ``2001:db8::/32``): the same address always
gets the same placeholder, the prefix length stays, and addresses that are already in these ranges stay as
they are. Without ``apply`` only the mapping and the changed lines are returned. With ``apply`` the document
gets a new version (``PKM-Source: agent``); if all found addresses were replaced it is marked
``ip_addresses: placeholder``. Earlier versions in Git (or the backup without Git) still contain the
original addresses.

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

import difflib
import ipaddress
import re
from typing import TYPE_CHECKING, Any

from .errors import PkmError
from .frontmatter import set_fields_linewise
from .ipaddrs import IP_FIELD, find_ip_details, not_ip_values
from .parse import split_frontmatter
from .vault import Doc

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

DOC_V4 = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
DOC_V6 = ipaddress.ip_network("2001:db8::/32")
MAX_CHANGED_LINES = 40

# Classes *********************************************************************

# Functions *******************************************************************


def _is_documentation(addr: Any) -> bool:
    """Whether an address already lies in a range reserved for documentation.

    Args:
        addr: ``ipaddress`` object.

    Returns:
        ``True`` for ``192.0.2.0/24``, ``198.51.100.0/24``, ``203.0.113.0/24`` and ``2001:db8::/32``.
    """
    return addr in DOC_V6 if addr.version == 6 else any(addr in net for net in DOC_V4)


def _placeholders(version: int, taken: set[str]) -> Any:
    """Free placeholder addresses of one IP version, in order.

    Args:
        version: 4 or 6.
        taken: Addresses that are already used in the document.

    Yields:
        Addresses as text.
    """
    hosts = (str(DOC_V6.network_address + i) for i in range(1, 65536)) if version == 6 else (
        str(h) for net in DOC_V4 for h in net.hosts())
    for host in hosts:
        if host not in taken:
            yield host


def ip_mapping(found: list[str]) -> dict[str, str]:
    """Placeholder for every found address (without prefix length); documentation addresses stay out.

    Args:
        found: Found values (with optional prefix length).

    Returns:
        Original address → placeholder address.
    """
    addrs = {v.split("/", 1)[0] for v in found}
    taken = {a for a in addrs if _is_documentation(ipaddress.ip_address(a))}
    free = {4: _placeholders(4, taken), 6: _placeholders(6, taken)}
    mapping: dict[str, str] = {}
    for value in found:
        addr = value.split("/", 1)[0]
        parsed = ipaddress.ip_address(addr)
        if addr not in mapping and addr not in taken:
            mapping[addr] = next(free[parsed.version])
    return mapping


def replace_addresses(body: str, mapping: dict[str, str]) -> str:
    """Replace the addresses in a text (whole values only, longest first).

    Args:
        body: Text below the frontmatter.
        mapping: Original → placeholder.

    Returns:
        The new text.
    """
    for old in sorted(mapping, key=len, reverse=True):
        after = r"(?![\w:])" if ":" in old else r"(?!\w|\.\d)"  # IPv4 may be followed by a port
        body = re.sub(rf"(?<![\w.:]){re.escape(old)}{after}", mapping[old], body)
    return body


def _changed_lines(old: str, new: str) -> list[str]:
    """Lines that differ between two texts (at most ``MAX_CHANGED_LINES``).

    Args:
        old: Text before.
        new: Text after.

    Returns:
        Lines of a unified diff without context (``-`` before, ``+`` after).
    """
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)
    return [ln for ln in diff if ln[:1] in "+-" and not ln.startswith(("+++", "---"))][:MAX_CHANGED_LINES]


def _plan(svc: Service, doc: Doc, values: list[str] | None) -> tuple[dict[str, str], bool]:
    """Mapping for the found (or chosen) addresses of a document.

    Args:
        svc: Service.
        doc: Document.
        values: Only these values; all found ones if omitted.

    Returns:
        Mapping and whether it covers all found addresses.

    Raises:
        PkmError: ``invalid_argument`` if there is nothing to replace.
    """
    found = find_ip_details(doc.body or "", svc.cfg.ip_well_known, not_ip_values(svc.state(), doc.id)).found
    chosen = found if not values else [v for v in found if v in values or v.split("/", 1)[0] in values]
    mapping = ip_mapping(chosen)
    if not mapping:
        raise PkmError("invalid_argument", "No IP addresses to anonymize in this document.", found=found)
    return mapping, set(ip_mapping(found)) <= set(mapping)


def anonymize_ip_addresses(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    svc: Service, target: str, expected_hash: str, values: list[str] | None = None, apply: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    """Tool ``anonymize_ip_addresses``: replace IP addresses of a document by documentation addresses.

    Args:
        svc: Service.
        target: Document in ``documents/`` (path, wikilink or ``id:``).
        expected_hash: ``hash`` from ``read``.
        values: Only these of the found values; all found ones if omitted.
        apply: Write the change; without it only the preview.
        note: Change note.

    Returns:
        ``mapping`` and ``changes`` (preview), with ``apply`` additionally the result of the change.

    Raises:
        PkmError: ``invalid_argument`` if there is nothing to replace, otherwise like ``Writer.change``.
    """
    doc = svc.vault.load(svc.resolve(target, ("documents",)))
    mapping, complete = _plan(svc, doc, values)

    def transform(current: Doc) -> str:
        """Replace the addresses below the frontmatter and mark the document as placeholder if complete.

        Args:
            current: Document.

        Returns:
            New text.
        """
        text = current.text or ""
        has_fm, fm_text, _, body, err = split_frontmatter(text)
        new = fm_text + replace_addresses(body, mapping) if has_fm and err is None else replace_addresses(text, mapping)
        return set_fields_linewise(new, {IP_FIELD: "placeholder"}) if complete else new

    result: dict[str, Any] = {"status": "preview", "path": doc.rel, "mapping": mapping,
                              "changes": _changed_lines(doc.text or "", transform(doc)), "marked_placeholder": complete}
    if apply:
        default = f"IP addresses anonymized after confirmation ({len(mapping)})"
        result = {**svc.writer.change(doc.rel, expected_hash, transform, note or default, source="agent",
                                      check_limit=False),
                  "mapping": mapping, "marked_placeholder": complete}
    return result

# Main ************************************************************************
