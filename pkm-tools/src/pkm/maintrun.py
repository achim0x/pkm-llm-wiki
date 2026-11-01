"""Pflegelauf als drei Schritte für den MCP-Server ``pkm-pflege``: beginnen, Wiki-Seite schreiben, abschließen.

Alle Schritte sind deterministisch. Inhaltliche Arbeit (Seiten formulieren, Belege wählen) macht
das LLM; die mechanischen Pflege-Befehle laufen hier gebündelt in fester Reihenfolge.

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

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from .citations import fix_citations, parse_page, sync_citations
from .doctor import doctor
from .errors import PkmError
from .ids import is_valid_id
from .lint import lint, write_report
from .maint import Maintenance, page_ref
from .paths import is_platform_safe_name, safe_resolve
from .vault import Doc
from .wikigen import build_index, build_status, wiki_pages, write_if_changed

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

WRITABLE_DIRS = ("wiki/topics/", "wiki/entities/", "wiki/summaries/", "wiki/syntheses/")
LOG_PATH = "wiki/log.md"
OPERATIONS = ("ingest", "lint", "fix")

# Classes *********************************************************************

# Functions *******************************************************************


def begin_maintenance(svc: Service, with_lint: bool = False) -> dict[str, Any]:
    """Vorlauf: ``doctor``, ``versions``, ``ids``, ``pending`` und bei Verschiebungen ``fix-citations``.

    Args:
        svc: Dienst.
        with_lint: Zusätzlich den Prüfbericht liefern (für den Ablauf „Lint“).

    Returns:
        ``status`` (``ok``, ``blocked`` bei Fehlern der Umgebung, ``needs_decision`` bei doppelten
        IDs), die Ergebnisse der Einzelschritte und die zu verarbeitenden Dokumente.
    """
    check = doctor(svc, short=True)
    result: dict[str, Any] = {"status": "blocked", "doctor": check["checks"]}
    if check["status"] == "ok":
        maint = Maintenance(svc)
        versions = maint.versions()
        ids = maint.ids()
        pend = maint.pending()
        fixed = fix_citations(svc) if pend["moved"] else None
        result = {
            "status": "needs_decision" if ids["duplicates"] else "ok",
            "versions": {"committed": versions["committed"], "skipped": versions["skipped"]},
            "ids": {k: ids[k] for k in ("assigned", "duplicates", "skipped", "problems")},
            "pending": pend,
            "fixed_citations": fixed,
        }
        if with_lint:
            result["lint"] = lint(svc)
    return result


def _page_path(path: str) -> str:
    """Pfad einer beschreibbaren Wiki-Seite prüfen und vereinheitlichen.

    Args:
        path: Pfad wie ``wiki/topics/thema`` oder ``wiki/topics/thema.md``.

    Returns:
        Relativer Pfad mit ``.md``.

    Raises:
        PkmError: ``forbidden`` außerhalb der Seitenordner, ``invalid_path`` bei ungültigen Namen.
    """
    rel = path.strip().replace("\\", "/").lstrip("/")
    if PurePosixPath(rel).suffix.lower() != ".md":
        rel = f"{rel}.md"
    if not rel.startswith(WRITABLE_DIRS):
        raise PkmError("forbidden", "Schreiben nur in " + ", ".join(WRITABLE_DIRS)
                       + " (index.md, _status.md, log.md und sources sind generiert).", path=rel)
    if not all(is_platform_safe_name(part) for part in PurePosixPath(rel).parts):
        raise PkmError("invalid_path", "Ungültiger Datei- oder Ordnername.", path=rel)
    return rel


def write_wiki_page(svc: Service, path: str, content: str, expected_hash: str | None = None) -> dict[str, Any]:
    """Wiki-Seite anlegen oder ersetzen (ohne Commit; den macht ``finish_maintenance``).

    Args:
        svc: Dienst.
        path: Seite unter ``wiki/topics|entities|summaries|syntheses/``.
        content: Vollständiger Inhalt mit Frontmatter.
        expected_hash: ``hash`` aus ``read`` bei bestehenden Seiten; bei neuen Seiten weglassen.

    Returns:
        ``status`` (``created``, ``changed``, ``unchanged``), Pfad und neuer ``hash``.

    Raises:
        PkmError: ``forbidden``, ``invalid_path``, ``conflict`` oder ``too_large``.
    """
    rel = _page_path(path)
    safe_resolve(svc.cfg.root, rel)
    svc.writer.check_size(content, "Die Seite")
    with svc.writer.lock():
        exists = svc.vault.exists(rel)
        current = svc.vault.load(rel).hashes if exists else None
        if exists and (expected_hash is None or current is None or current.file_hash != expected_hash):
            raise PkmError("conflict", "Seite existiert oder wurde geändert: erst mit read lesen und dessen "
                           "hash als expected_hash angeben.", path=rel)
        if not exists and expected_hash is not None:
            raise PkmError("conflict", "Seite existiert nicht (mehr); ohne expected_hash neu anlegen.", path=rel)
        (svc.cfg.root / rel).parent.mkdir(parents=True, exist_ok=True)
        changed = write_if_changed(svc, rel, content)
        new = svc.vault.load(rel).hashes
    status = "created" if not exists else ("changed" if changed else "unchanged")
    return {"status": status, "path": rel, "hash": new.file_hash if new else None}


def _load_target(svc: Service, target: str) -> Doc:
    """Dokument aus ``documents/`` über ID oder Pfad laden.

    Args:
        svc: Dienst.
        target: ID (``d-…`` oder ``id:d-…``) oder Pfad.

    Returns:
        Das Dokument.
    """
    ref = f"id:{target}" if is_valid_id(target) else target
    return svc.load(ref, ("documents",))


def citing_pages(svc: Service, doc: Doc) -> list[str]:
    """Wiki-Seiten, die ein Dokument belegen.

    Args:
        svc: Dienst.
        doc: Dokument (Markdown über ``id``, Anhänge über den Pfad).

    Returns:
        Seiten als Verweis ohne Endung, sortiert.
    """
    pages = set()
    for page in wiki_pages(svc):
        if page.parsed is not None and not page.error:
            cits = parse_page(page).definitions.values()
            if any((doc.id and c.doc_id == doc.id) or c.target_rel == doc.rel for c in cits):
                pages.add(page_ref(page.rel))
    return sorted(pages)


def _mark_processed(svc: Service, processed: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Verarbeitete Dokumente mit den belegenden Seiten in ``state.json`` eintragen.

    Args:
        svc: Dienst.
        processed: IDs oder Pfade.

    Returns:
        Tupel aus (Einträge, Warnungen für Dokumente ohne Beleg).
    """
    maint = Maintenance(svc)
    marked: list[dict[str, Any]] = []
    warnings: list[str] = []
    for target in processed:
        doc = _load_target(svc, target)
        pages = citing_pages(svc, doc)
        if not pages:
            warnings.append(f"{doc.rel}: keine Wiki-Seite belegt dieses Dokument.")
        entry = maint.mark([target], pages)["marked"][0]
        marked.append({**entry, "pages": pages})
    return marked, warnings


def append_log(svc: Service, operation: str, title: str | None, entry: str) -> str:
    """Eintrag an ``wiki/log.md`` anhängen (nur anhängen, nie ändern).

    Args:
        svc: Dienst.
        operation: ``ingest``, ``lint`` oder ``fix``.
        title: Kurzangabe hinter der Überschrift, z. B. ``1 neu, 1 geändert``.
        entry: Inhalt (Markdown-Liste).

    Returns:
        Die erzeugte Überschrift.
    """
    stamp = svc.now().strftime("%Y-%m-%d %H:%M")
    heading = f"## [{stamp}] {operation}" + (f" | {' '.join(title.split())}" if title else "")
    p = svc.cfg.root / LOG_PATH
    old = p.read_text(encoding="utf-8").rstrip("\n") if p.is_file() else "# Pflege-Log"
    write_if_changed(svc, LOG_PATH, f"{old}\n\n{heading}\n{entry.strip()}\n")
    return heading


def finish_maintenance(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    svc: Service,
    log_entry: str,
    operation: str = "ingest",
    log_title: str | None = None,
    processed: list[str] | None = None,
    removed: list[str] | None = None,
    questions: list[str] | None = None,
    lint_report: bool = False,
) -> dict[str, Any]:
    """Abschluss: Belege, ``mark``, Log, Index, Status, Lint und Agenten-Commit.

    Args:
        svc: Dienst.
        log_entry: Inhalt des Log-Eintrags (Markdown-Liste).
        operation: ``ingest``, ``lint`` oder ``fix``.
        log_title: Kurzangabe für die Log-Überschrift.
        processed: Verarbeitete Dokumente (IDs oder Pfade); die belegenden Seiten werden ermittelt.
        removed: Schlüssel gelöschter Dokumente, die aus ``state.json`` entfernt werden.
        questions: Rückfragen für ``wiki/_status.md``.
        lint_report: Prüfbericht nach ``wiki/_lint/`` schreiben.

    Returns:
        Ergebnisse der Einzelschritte, Warnungen, Prüfbericht und Commit.

    Raises:
        PkmError: ``invalid_argument`` bei unbekannter Operation oder leerem Log-Eintrag.
    """
    if operation not in OPERATIONS:
        raise PkmError("invalid_argument", f"operation muss eines von {', '.join(OPERATIONS)} sein.")
    if not log_entry.strip():
        raise PkmError("invalid_argument", "log_entry darf nicht leer sein.")
    result: dict[str, Any] = {
        "status": "ok",
        "fixed_citations": fix_citations(svc),
        "synced_sources": sync_citations(svc)["pages_changed"],
    }
    marked, warnings = _mark_processed(svc, processed or [])
    result["marked"] = marked
    result["removed"] = Maintenance(svc).mark(removed, remove=True)["marked"] if removed else []
    result["log"] = append_log(svc, operation, log_title, log_entry)
    result["index"] = build_index(svc)
    result["wiki_status"] = build_status(svc, questions)
    report = lint(svc)
    if lint_report:
        report["report"] = write_report(svc, report)
    result["lint"] = report
    result["commit"] = Maintenance(svc).commit_wiki(_commit_message(operation, len(marked)))
    result["warnings"] = warnings
    return result


def _commit_message(operation: str, count: int) -> str:
    """Betreff des Agenten-Commits.

    Args:
        operation: ``ingest``, ``lint`` oder ``fix``.
        count: Anzahl verarbeiteter Dokumente.

    Returns:
        Z. B. ``pkm: ingest 2 documents``.
    """
    suffix = f" {count} document{'s' if count != 1 else ''}" if count else ""
    return f"pkm: {operation}{suffix}"

# Main ************************************************************************
