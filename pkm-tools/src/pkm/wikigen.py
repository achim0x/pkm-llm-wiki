"""Generierte Wiki-Dateien: ``wiki/index.md`` (4.3) und ``wiki/_status.md`` (4.4).

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

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

GENERATED = {"wiki/index.md", "wiki/_status.md", "wiki/log.md"}
TYPE_HEADINGS = [
    ("topic", "Themen"),
    ("entity", "Entitäten"),
    ("summary", "Zusammenfassungen"),
    ("synthesis", "Synthesen"),
]
FOLDER_TYPES = {"topics": "topic", "entities": "entity", "summaries": "summary", "syntheses": "synthesis"}
INBOX = "documents/_inbox/"
ATTACHMENTS = "documents/_attachments/"

# Classes *********************************************************************

# Functions *******************************************************************


def wiki_pages(svc: Service) -> list[Doc]:
    """Alle Wiki-Seiten außer den generierten Dateien und Lint-Berichten.

    Args:
        svc: Dienst.

    Returns:
        Geladene Seiten.
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
    """Typ einer Wiki-Seite.

    Args:
        doc: Wiki-Seite.

    Returns:
        ``type`` aus dem Frontmatter, sonst aus dem Ordner abgeleitet, sonst leer.
    """
    t = doc.meta.get("type")
    parts = doc.rel.split("/")
    folder_type = FOLDER_TYPES.get(parts[1], "") if len(parts) > 2 else ""
    return t if isinstance(t, str) and t else folder_type


def source_count(doc: Doc) -> int:
    """Anzahl der Quellen einer Wiki-Seite.

    Args:
        doc: Wiki-Seite.

    Returns:
        Länge von ``sources`` (0, wenn das Feld fehlt).
    """
    sources = doc.meta.get("sources")
    return len(sources) if isinstance(sources, list) else 0


def write_if_changed(svc: Service, rel: str, text: str) -> bool:
    """Datei nur schreiben, wenn sich der Inhalt ändert (atomar).

    Args:
        svc: Dienst.
        rel: Relativer Pfad.
        text: Neuer Inhalt (wird in die Schreibform gebracht).

    Returns:
        ``True``, wenn geschrieben wurde.
    """
    p = svc.vault.path(rel)
    data = encode(text)
    changed = not (p.exists() and p.read_bytes() == data)
    if changed:
        write_bytes_atomic(p, data)
    return changed


def _index_line(doc: Doc) -> str:
    """Zeile einer Seite in ``wiki/index.md``.

    Args:
        doc: Wiki-Seite.

    Returns:
        ``- [[pfad]] – Kurzfassung _(n Quellen, Datum)_`` (Datum ohne Uhrzeit).
    """
    summary = strip_images(summary_of(doc)) or "_(keine Kurzfassung)_"
    n = source_count(doc)
    updated = str(doc.meta.get("date_updated") or "")[:10]
    info = f"{n} {'Quelle' if n == 1 else 'Quellen'}" + (f", {updated}" if updated else "")
    return f"- {doc.wikilink} – {summary} _({info})_"


def build_index(svc: Service) -> dict[str, Any]:
    """``pkm index``: ``wiki/index.md`` neu erzeugen, gruppiert nach Typ.

    Args:
        svc: Dienst.

    Returns:
        Anzahl der Seiten und ob die Datei geändert wurde.
    """
    pages = wiki_pages(svc)
    groups: dict[str, list[Doc]] = {}
    for doc in pages:
        groups.setdefault(page_type(doc), []).append(doc)
    known = [t for t, _ in TYPE_HEADINGS]
    others = [(t, "Sonstige" if not t else f"Sonstige ({t})") for t in sorted(groups) if t not in known]
    lines = ["# Wiki-Index", ""]
    for t, heading in TYPE_HEADINGS + others:
        docs = sorted(groups.get(t, []), key=lambda d: (d.title.casefold(), d.rel))
        if docs:
            lines += [f"## {heading}", "", *(_index_line(d) for d in docs), ""]
    if len(lines) == 2:
        lines += ["_Noch keine Seiten._", ""]
    changed = write_if_changed(svc, "wiki/index.md", "\n".join(lines))
    return {"status": "ok", "pages": len(pages), "changed": changed}


def suggest_folder(doc: Doc, all_docs: list[Doc]) -> str | None:
    """Einsortier-Vorschlag: Ordner, in dem die meisten Dokumente mit gleichen ``tags`` liegen.

    Args:
        doc: Dokument im Eingang.
        all_docs: Alle Dokumente.

    Returns:
        Ordner mit ``/`` am Ende oder ``None``.
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
    """Abschnittsschlüssel in deutschen Anführungszeichen aufzählen.

    Args:
        keys: Schlüssel.

    Returns:
        Z. B. ``„Ergebnis“, „Offene Punkte“``.
    """
    return ", ".join(f"„{k}“" for k in keys)


def _link(rel: str) -> str:
    """Wikilink auf eine Datei.

    Args:
        rel: Relativer Pfad.

    Returns:
        ``[[pfad]]`` (Markdown ohne ``.md``).
    """
    return f"[[{rel[:-3] if rel.lower().endswith('.md') else rel}]]"


def _unprocessed_lines(pend: dict[str, Any]) -> list[str]:
    """Zeilen für „Noch nicht verarbeitet“.

    Args:
        pend: Ergebnis von ``pkm pending``.

    Returns:
        Eine Zeile je Dokument.
    """
    lines: list[str] = []
    for item in pend["new"]:
        version = f" (v{item.get('version')})" if item.get("version") else ""
        extra = ", ohne ID" if item.get("missing_id") else ""
        lines.append(f"- {_link(item['path'])} – neu{version}{extra}")
    for item in pend["changed"]:
        keys = [c["key"] for c in item.get("sections", [])]
        what = f"geändert: {_quote_keys(keys)}" if keys else "nur Reihenfolge geändert"
        lines.append(f"- {_link(item['path'])} – v{item.get('processed_version')} → v{item.get('version')}, {what}")
    for item in pend["meta_changed"]:
        lines.append(
            f"- {_link(item['path'])} – v{item.get('processed_version')} → v{item.get('version')}, nur Metadaten"
        )
    for item in pend["moved"]:
        lines.append(f"- {_link(item['to'])} – verschoben von {item['from']}")
    for item in pend["deleted"]:
        pages = ", ".join(item.get("wiki_pages") or []) or "keine Wiki-Seiten"
        lines.append(f"- {item.get('path')} – gelöscht (zuletzt v{item.get('processed_version')}), betrifft: {pages}")
    return lines


def _inbox_lines(svc: Service, pend: dict[str, Any], docs: list[Doc]) -> list[str]:
    """Zeilen für „Noch im Eingang, bereits verarbeitet“ mit Einsortier-Vorschlag.

    Args:
        svc: Dienst.
        pend: Ergebnis von ``pkm pending``.
        docs: Alle Dokumente.

    Returns:
        Eine Zeile je verarbeitetem Dokument im Eingang.
    """
    state = load_state(svc.cfg)["documents"]
    pending_paths = {i["path"] for k in ("new", "changed", "meta_changed") for i in pend[k]}
    lines = []
    for doc in docs:
        key = doc.id if doc.kind == "md" else f"sha:{doc.bin_hash}"
        if doc.rel.startswith(INBOX) and doc.rel not in pending_paths and key and key in state:
            folder = suggest_folder(doc, docs)
            lines.append(f"- {_link(doc.rel)} → {f'Vorschlag: {folder}' if folder else 'kein Vorschlag'}")
    return lines


def _problem_lines(pend: dict[str, Any]) -> list[str]:
    """Zeilen für „Probleme“.

    Args:
        pend: Ergebnis von ``pkm pending``.

    Returns:
        Eine Zeile je Problem.
    """
    lines = []
    for p in pend["problems"]:
        if p["problem"] == "conflict_copy":
            lines.append(f"- Nextcloud-Konfliktkopie: {p['path']} (bitte in Obsidian zusammenführen)")
        elif p["problem"] == "duplicate_id":
            lines.append(f"- Doppelte ID {p['id']}: {', '.join(p['paths'])}")
        elif p["problem"] == "case_collision":
            lines.append(f"- Nur in Groß-/Kleinschreibung verschieden: {', '.join(p['paths'])}")
        else:
            lines.append(f"- {p['problem']}: {p.get('path')} – {p.get('message') or ''}".rstrip(" –"))
    return lines


def build_status(svc: Service, questions: list[str] | None = None) -> dict[str, Any]:
    """``pkm status``: ``wiki/_status.md`` neu erzeugen.

    Args:
        svc: Dienst.
        questions: Rückfragen für den Abschnitt „Rückfragen“.

    Returns:
        Zähler und ob die Datei geändert wurde.
    """
    maint = Maintenance(svc)
    pend = maint.pending()
    docs, _ = maint.documents()
    unprocessed = _unprocessed_lines(pend)
    inbox_done = _inbox_lines(svc, pend, docs)
    problems = _problem_lines(pend)
    lines = ["# Status", "", f"## Noch nicht verarbeitet ({len(unprocessed)})", *unprocessed, "",
             f"## Noch im Eingang, bereits verarbeitet ({len(inbox_done)})", *inbox_done, "",
             f"## Probleme ({len(problems)})", *problems, ""]
    orphans = pend.get("orphaned_attachments") or []
    if orphans:
        lines += [f"## Verwaiste Anhänge ({len(orphans)})", *[f"- {_link(rel)}" for rel in orphans], ""]
    if questions:
        lines += [f"## Rückfragen ({len(questions)})", *[f"- {q}" for q in questions], ""]
    changed = write_if_changed(svc, "wiki/_status.md", "\n".join(lines))
    return {"status": "ok", "unprocessed": len(unprocessed), "inbox_processed": len(inbox_done),
            "problems": len(problems), "changed": changed}

# Main ************************************************************************
