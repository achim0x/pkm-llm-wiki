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
from .errors import PkmError
from .parse import body_lines
from .state import load_state
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


def _raise_target(cit: Citation, resolver: Resolver, cache: dict[str, Any]) -> tuple[int, str | None] | None:
    """New version for a citation whose section is unchanged or changed only in image notation
    (6.4, 4.9).

    Args:
        cit: Citation.
        resolver: Resolver.
        cache: Values shared by all citations of a run (recorded ``assets``).

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
        elif newer and current and _notation_only(cit, res, resolver, cache):
            target = (res.current_version, hashes.short(current))
    return target


def _old_link_hash(cit: Citation, cited: Any, resolver: Resolver, cache: dict[str, Any]) -> Any:
    """Hashes of the image files linked by the cited (earlier) version of a document.

    The links of the earlier text are resolved against its own path at that time; files that no longer exist
    there (document or images moved, ``rename_document``, ``move_images``) are taken from the recorded
    ``assets`` in ``state.json`` and otherwise from Git at the commit of the cited version.

    Args:
        cit: Citation.
        cited: Document in the cited version.
        resolver: Resolver.
        cache: Values shared by all citations of a run.

    Returns:
        Function ``ImageRef`` → SHA-256 or ``None``.
    """
    svc = resolver.svc
    if "assets" not in cache:
        try:
            cache["assets"] = load_state(svc.cfg)["documents"]
        except PkmError:
            cache["assets"] = {}
    recorded = (cache["assets"].get(cit.doc_id or "") or {}).get("assets") or {}
    try:
        commit = svc.commit_for_version(cit.doc_id or "", cit.version or 0).sha if svc.versioning else None
    except PkmError:
        commit = None
    return resolver.asset_map().link_hash(cited.rel, recorded, commit)


def _notation_only(cit: Citation, res: Resolution, resolver: Resolver, cache: dict[str, Any]) -> bool:
    """Check whether the cited section changed only in image notation since the cited version.

    Also when the document or its image files were moved in between: the earlier text is compared with the
    hashes of the files it linked to at that time (``_old_link_hash``). Equal canonical text means the quote
    (also ``[img:<name>]``) is still in the section.

    Args:
        cit: Citation.
        res: Resolution (current version).
        resolver: Resolver (for the cited version).
        cache: Values shared by all citations of a run.

    Returns:
        ``True`` if only the image notation changed (section or whole body).
    """
    cited = resolver.version_doc(cit.doc_id, cit.version) if cit.doc_id and cit.version else None
    limits = resolver.svc.cfg.images
    old_sec = section_text(cited, cit.section_key) if cited else None
    new_sec = section_text(res.doc, cit.section_key) if res.doc else None
    new_hash = resolver.asset_map().link_hash(res.doc.rel) if res.doc is not None else None
    old_hash = _old_link_hash(cit, cited, resolver, cache) if cited is not None else None
    same_sec = old_sec is not None and new_sec is not None and imagefix.notation_only(
        old_sec, new_sec, limits, old_hash, new_hash)
    same_body = cited is not None and res.doc is not None and imagefix.body_notation_only(
        cited.body or "", res.doc.body or "", limits, old_hash, new_hash)
    return same_sec or same_body


def raise_versions(svc: Service, pages: list[str] | None = None) -> dict[str, Any]:
    """Raise citations of unchanged sections to the current version (only ``v:``, ``sha:`` stays).

    A citation is raised if the original has a newer version and the cited section there has the same hash
    as in the citation (only ``v:``), or differs only in the image notation (``v:`` and ``sha:``, 4.9; also after
    moving the document or its image files). Citations of changed sections stay unchanged.

    Args:
        svc: Service.
        pages: Wiki pages or ``None`` for all.

    Returns:
        Number of changed pages and the changes (per citation ``version`` and ``sha_changed``).
    """
    resolver = Resolver(svc)
    cache: dict[str, Any] = {}
    changes = []
    for rel in wiki_targets(svc, pages):
        doc = svc.vault.load(rel)
        if doc.parsed is None or doc.error:
            continue
        lines = body_lines(doc.parsed.body)
        page_changes = []
        for cit in parse_page(doc).definitions.values():
            target = _raise_target(cit, resolver, cache)
            if target is not None:
                new_line = _raised_line(lines[cit.line], *target)
                if new_line != lines[cit.line]:
                    page_changes.append({"id": cit.label, "old": lines[cit.line], "new": new_line,
                                         "version": target[0], "sha_changed": target[1] is not None})
                    lines[cit.line] = new_line
        if page_changes:
            write_if_changed(svc, rel, doc.parsed.frontmatter_text + "\n".join(lines) + "\n")
            changes.append({"page": rel, "changes": page_changes})
    return {"status": "ok", "pages_changed": len(changes), "changes": changes}

# Main ************************************************************************
