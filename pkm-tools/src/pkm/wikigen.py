"""Generated wiki files: ``wiki/index.md`` (4.3) and ``wiki/_status.md`` (4.4).

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

from collections import Counter
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from .errors import PkmError
from .fsutil import write_bytes_atomic
from .images import strip_images
from .maint import Maintenance
from .normalize import encode
from .state import load_state
from .vault import Doc, summary_of
from .wikitexts import text as wtext

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

GENERATED = {"wiki/index.md", "wiki/_status.md", "wiki/log.md"}
PAGE_TYPES = ("topic", "entity", "summary", "synthesis")  # order in wiki/index.md
FOLDER_TYPES = {"topics": "topic", "entities": "entity", "summaries": "summary", "syntheses": "synthesis"}
INBOX = "documents/_inbox/"
ATTACHMENTS = "documents/_attachments/"

# Classes *********************************************************************

# Functions *******************************************************************


def wiki_pages(svc: Service) -> list[Doc]:
    """All wiki pages except the generated files and lint reports.

    Args:
        svc: Service.

    Returns:
        Loaded pages.
    """
    pages = []
    for rel in svc.vault.iter_files(("wiki",)):
        if rel not in GENERATED and not rel.startswith("wiki/_lint/") and rel.lower().endswith(".md"):
            try:
                pages.append(svc.vault.load(rel))
            except PkmError:
                continue
    return pages


def page_type(doc: Doc) -> str:
    """Type of a wiki page.

    Args:
        doc: Wiki page.

    Returns:
        ``type`` from the frontmatter, otherwise derived from the folder, otherwise empty.
    """
    t = doc.meta.get("type")
    parts = doc.rel.split("/")
    folder_type = FOLDER_TYPES.get(parts[1], "") if len(parts) > 2 else ""
    return t if isinstance(t, str) and t else folder_type


def source_count(doc: Doc) -> int:
    """Number of sources of a wiki page.

    Args:
        doc: Wiki page.

    Returns:
        Length of ``sources`` (0 if the field is missing).
    """
    sources = doc.meta.get("sources")
    return len(sources) if isinstance(sources, list) else 0


def write_if_changed(svc: Service, rel: str, text: str) -> bool:
    """Write a file only if its content changes (atomically).

    Args:
        svc: Service.
        rel: Relative path.
        text: New content (brought into write form).

    Returns:
        ``True`` if it was written.
    """
    p = svc.vault.path(rel)
    data = encode(text)
    changed = not (p.exists() and p.read_bytes() == data)
    if changed:
        write_bytes_atomic(p, data)
    return changed


def _index_line(doc: Doc, lang: str) -> str:
    """Line of a page in ``wiki/index.md``.

    Args:
        doc: Wiki page.
        lang: Wiki language.

    Returns:
        ``- [[path]] – summary _(n sources, date)_`` (date without time).
    """
    summary = strip_images(summary_of(doc)) or wtext(lang, "no_summary")
    n = source_count(doc)
    updated = str(doc.meta.get("date_updated") or "")[:10]
    info = f"{n} {wtext(lang, 'source' if n == 1 else 'sources')}" + (f", {updated}" if updated else "")
    return f"- {doc.wikilink} – {summary} _({info})_"


def build_index(svc: Service) -> dict[str, Any]:
    """``pkm index``: regenerate ``wiki/index.md``, grouped by type.

    Args:
        svc: Service.

    Returns:
        Number of pages and whether the file was changed.
    """
    lang = svc.cfg.language
    pages = wiki_pages(svc)
    groups: dict[str, list[Doc]] = {}
    for doc in pages:
        groups.setdefault(page_type(doc), []).append(doc)
    other = wtext(lang, "other")
    headings = [(t, wtext(lang, t)) for t in PAGE_TYPES]
    headings += [(t, other if not t else f"{other} ({t})") for t in sorted(groups) if t not in PAGE_TYPES]
    lines = [f"# {wtext(lang, 'index_title')}", ""]
    for t, heading in headings:
        docs = sorted(groups.get(t, []), key=lambda d: (d.title.casefold(), d.rel))
        if docs:
            lines += [f"## {heading}", "", *(_index_line(d, lang) for d in docs), ""]
    if len(lines) == 2:
        lines += [wtext(lang, "no_pages"), ""]
    changed = write_if_changed(svc, "wiki/index.md", "\n".join(lines))
    return {"status": "ok", "pages": len(pages), "changed": changed}


def suggest_folder(doc: Doc, all_docs: list[Doc]) -> str | None:
    """Filing proposal: folder that holds most documents with the same ``tags``.

    Args:
        doc: Document in the inbox.
        all_docs: All documents.

    Returns:
        Folder ending in ``/`` or ``None``.
    """
    tags = doc.meta.get("tags")
    wanted = {str(t).casefold() for t in tags} if isinstance(tags, list) else set()
    votes: Counter[str] = Counter()
    for other in all_docs:
        other_tags = other.meta.get("tags")
        if (
            wanted
            and not other.rel.startswith((INBOX, ATTACHMENTS))
            and isinstance(other_tags, list)
            and wanted & {str(t).casefold() for t in other_tags}
        ):
            votes[str(PurePosixPath(other.rel).parent) + "/"] += 1
    return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if votes else None


def _quote_keys(keys: list[str]) -> str:
    """List section keys in quotes.

    Args:
        keys: Keys.

    Returns:
        E.g. ``"Result", "Open points"``.
    """
    return ", ".join(f'"{k}"' for k in keys)


def _link(rel: str) -> str:
    """Wikilink to a file.

    Args:
        rel: Relative path.

    Returns:
        ``[[path]]`` (Markdown without ``.md``).
    """
    return f"[[{rel[:-3] if rel.lower().endswith('.md') else rel}]]"


def _change_text(item: dict[str, Any], lang: str) -> str:
    """Description of a ``changed`` entry.

    Args:
        item: Entry of ``pending.changed``.
        lang: Wiki language.

    Returns:
        Changed sections, or why there are none.
    """
    keys = [c["key"] for c in item.get("sections", [])]
    if keys:
        what = wtext(lang, "changed", keys=_quote_keys(keys))
    elif item.get("assets_migrated"):
        what = wtext(lang, "migrated")
    elif item.get("images_changed"):
        what = wtext(lang, "images_only")
    else:
        what = wtext(lang, "order_only")
    return what


def _unprocessed_lines(pend: dict[str, Any], lang: str = "en") -> list[str]:
    """Lines for "Not yet processed".

    Args:
        pend: Result of ``pkm pending``.
        lang: Wiki language.

    Returns:
        One line per document.
    """
    lines: list[str] = []
    for item in pend["new"]:
        version = f" (v{item.get('version')})" if item.get("version") else ""
        extra = wtext(lang, "without_id") if item.get("missing_id") else ""
        lines.append(f"- {_link(item['path'])} – {wtext(lang, 'new')}{version}{extra}")
    for item in pend["changed"]:
        versions = f"v{item.get('processed_version')} → v{item.get('version')}"
        lines.append(f"- {_link(item['path'])} – {versions}, {_change_text(item, lang)}")
    for item in pend["meta_changed"]:
        lines.append(f"- {_link(item['path'])} – v{item.get('processed_version')} → v{item.get('version')}, "
                     f"{wtext(lang, 'meta_only')}")
    for item in pend["moved"]:
        lines.append(f"- {_link(item['to'])} – {wtext(lang, 'moved', src=item['from'])}")
    for item in pend["deleted"]:
        pages = ", ".join(item.get("wiki_pages") or []) or wtext(lang, "no_pages_affected")
        deleted = wtext(lang, "deleted", version=item.get("processed_version"), pages=pages)
        lines.append(f"- {item.get('path')} – {deleted}")
    return lines


def _inbox_lines(svc: Service, pend: dict[str, Any], docs: list[Doc]) -> list[str]:
    """Lines for "Still in the inbox, already processed" with a filing proposal.

    Args:
        svc: Service.
        pend: Result of ``pkm pending``.
        docs: All documents.

    Returns:
        One line per processed document in the inbox.
    """
    state = load_state(svc.cfg)["documents"]
    pending_paths = {i["path"] for k in ("new", "changed", "meta_changed") for i in pend[k]}
    lines = []
    for doc in docs:
        key = doc.id if doc.kind == "md" else f"sha:{doc.bin_hash}"
        if doc.rel.startswith(INBOX) and doc.rel not in pending_paths and key and key in state:
            folder = suggest_folder(doc, docs)
            lang = svc.cfg.language
            lines.append(f"- {_link(doc.rel)} → "
                         + (wtext(lang, "proposal", folder=folder) if folder else wtext(lang, "no_proposal")))
    return lines


def _problem_lines(pend: dict[str, Any], lang: str = "en") -> list[str]:
    """Lines for "Problems".

    Args:
        pend: Result of ``pkm pending``.
        lang: Wiki language.

    Returns:
        One line per problem.
    """
    lines = []
    for p in pend["problems"]:
        if p["problem"] == "conflict_copy":
            lines.append(f"- {wtext(lang, 'conflict_copy', path=p['path'])}")
        elif p["problem"] == "duplicate_id":
            lines.append(f"- {wtext(lang, 'duplicate_id', id=p['id'], paths=', '.join(p['paths']))}")
        elif p["problem"] == "case_collision":
            lines.append(f"- {wtext(lang, 'case_collision', paths=', '.join(p['paths']))}")
        else:
            lines.append(f"- {p['problem']}: {p.get('path')} – {p.get('message') or ''}".rstrip(" –"))
    return lines


def build_status(svc: Service, questions: list[str] | None = None) -> dict[str, Any]:
    """``pkm status``: regenerate ``wiki/_status.md``.

    Args:
        svc: Service.
        questions: Questions for the "Questions" section.

    Returns:
        Counters and whether the file was changed.
    """
    maint = Maintenance(svc)
    pend = maint.pending()
    docs, _ = maint.documents()
    lang = svc.cfg.language
    unprocessed = _unprocessed_lines(pend, lang)
    inbox_done = _inbox_lines(svc, pend, docs)
    problems = _problem_lines(pend, lang)
    lines = [f"# {wtext(lang, 'status_title')}", "", f"## {wtext(lang, 'unprocessed')} ({len(unprocessed)})",
             *unprocessed, "", f"## {wtext(lang, 'inbox_done')} ({len(inbox_done)})", *inbox_done, "",
             f"## {wtext(lang, 'problems')} ({len(problems)})", *problems, ""]
    orphans = pend.get("orphaned_attachments") or []
    if orphans:
        lines += [f"## {wtext(lang, 'orphans')} ({len(orphans)})", *[f"- {_link(rel)}" for rel in orphans], ""]
    if questions:
        lines += [f"## {wtext(lang, 'questions')} ({len(questions)})", *[f"- {q}" for q in questions], ""]
    changed = write_if_changed(svc, "wiki/_status.md", "\n".join(lines))
    return {"status": "ok", "unprocessed": len(unprocessed), "inbox_processed": len(inbox_done),
            "problems": len(problems), "changed": changed}

# Main ************************************************************************
