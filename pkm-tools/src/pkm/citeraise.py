"""Raise citations to the current version (specification 6.4, 4.9): only ``v:`` for unchanged sections,
``v:`` and ``sha:`` if only the image notation changed.

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
from typing import TYPE_CHECKING, Any

from . import hashes, imagefix
from .citations import Citation, Resolution, Resolver, parse_page, section_text, wiki_targets
from .parse import body_lines
from .wikigen import write_if_changed

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


def _raised_line(line: str, version: int, sha: str | None = None) -> str:
    """Citation line with a new version ``v:`` (and, if given, a new ``sha:``).

    Args:
        line: Previous line.
        version: New version.
        sha: New short hash or ``None`` (unchanged).

    Returns:
        The line with the replaced parts (other parts unchanged).
    """
    line = re.sub(r"(·\s*)v:\s*\d+", lambda m: f"{m.group(1)}v:{version}", line, count=1)
    return re.sub(r"(·\s*)sha:\s*[0-9a-f]+", lambda m: f"{m.group(1)}sha:{sha}", line, count=1) if sha else line


def _raise_target(cit: Citation, resolver: Resolver) -> tuple[int, str | None] | None:
    """New version for a citation whose section is unchanged or changed only in image notation
    (6.4, 4.9).

    Args:
        cit: Citation.
        resolver: Resolver.

    Returns:
        Tuple of (current version, new short hash or ``None``), or ``None`` if nothing is to be raised.
    """
    target = None
    res = resolver.resolve(cit) if cit.markdown and cit.version and cit.sha else None
    if res is not None and res.doc is not None and res.doc.hashes and res.current_version:
        key = cit.section_key or ""
        current = res.doc.hashes.sections.get(key)
        newer = cit.version is not None and cit.version < res.current_version
        if newer and current and hashes.matches(current, cit.sha or ""):
            target = (res.current_version, None)
        elif newer and current and _notation_only(cit, res, resolver):
            target = (res.current_version, hashes.short(current))
    return target


def _notation_only(cit: Citation, res: Resolution, resolver: Resolver) -> bool:
    """Check whether the cited section changed only in image notation since the cited version.

    Args:
        cit: Citation.
        res: Resolution (current version).
        resolver: Resolver (for the cited version).

    Returns:
        ``True`` if only the image notation changed (section or whole body).
    """
    cited = resolver.version_doc(cit.doc_id, cit.version) if cit.doc_id and cit.version else None
    limits = resolver.svc.cfg.images
    old_sec = section_text(cited, cit.section_key) if cited else None
    new_sec = section_text(res.doc, cit.section_key) if res.doc else None
    same_sec = old_sec is not None and new_sec is not None and imagefix.notation_only(old_sec, new_sec, limits)
    same_body = cited is not None and res.doc is not None and imagefix.body_notation_only(
        cited.body or "", res.doc.body or "", limits)
    return same_sec or same_body


def raise_versions(svc: Service, pages: list[str] | None = None) -> dict[str, Any]:
    """Raise citations of unchanged sections to the current version (only ``v:``, ``sha:`` stays).

    A citation is raised if the original has a newer version and the cited section there has
    the same hash as in the citation. Citations of changed sections stay unchanged.

    Args:
        svc: Service.
        pages: Wiki pages or ``None`` for all.

    Returns:
        Number of changed pages and the changes.
    """
    resolver = Resolver(svc)
    changes = []
    for rel in wiki_targets(svc, pages):
        doc = svc.vault.load(rel)
        if doc.parsed is None or doc.error:
            continue
        lines = body_lines(doc.parsed.body)
        page_changes = []
        for cit in parse_page(doc).definitions.values():
            target = _raise_target(cit, resolver)
            if target is not None:
                new_line = _raised_line(lines[cit.line], *target)
                if new_line != lines[cit.line]:
                    page_changes.append({"id": cit.label, "old": lines[cit.line], "new": new_line})
                    lines[cit.line] = new_line
        if page_changes:
            write_if_changed(svc, rel, doc.parsed.frontmatter_text + "\n".join(lines) + "\n")
            changes.append({"page": rel, "changes": page_changes})
    return {"status": "ok", "pages_changed": len(changes), "changes": changes}

# Main ************************************************************************
