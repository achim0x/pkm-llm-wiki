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

from collections import Counter
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from .citations import fix_citations, parse_page, raise_versions, sync_citations
from .doctor import doctor
from .errors import PkmError
from .frontmatter import set_fields_linewise
from .ids import is_valid_id
from .lint import lint, write_report
from .maint import Maintenance, page_ref
from .paths import is_platform_safe_name, safe_resolve
from .schema import KINDS, normalize_tags
from .vault import Doc
from .wikigen import build_index, build_status, wiki_pages, write_if_changed

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

WRITABLE_DIRS = ("wiki/topics/", "wiki/entities/", "wiki/summaries/", "wiki/syntheses/")
LOG_PATH = "wiki/log.md"
OPERATIONS = ("ingest", "lint", "fix")
METADATA_FIELDS = ("title", "context", "tags", "kind", "short_citation")
SUGGESTED_FIELDS = ("title", "context", "tags", "kind")

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
        add_missing_fields(svc, pend["new"])
        fixed = fix_citations(svc) if pend["moved"] else None
        result = {
            "status": "needs_decision" if ids["duplicates"] else "ok",
            "versions": {"committed": versions["committed"], "skipped": versions["skipped"]},
            "ids": {k: ids[k] for k in ("assigned", "duplicates", "skipped", "problems")},
            "pending": pend,
            "fixed_citations": fixed,
            "known_tags": known_tags(svc),
        }
        if with_lint:
            result["lint"] = lint(svc)
    return result


def _empty(value: Any) -> bool:
    """Prüfen, ob ein Frontmatter-Wert fehlt oder leer ist.

    Args:
        value: Wert.

    Returns:
        ``True`` bei ``None``, leerem Text oder leerer Liste.
    """
    return value is None or (isinstance(value, str | list) and not (value.strip() if isinstance(value, str) else value))


def add_missing_fields(svc: Service, new_docs: list[dict[str, Any]]) -> None:
    """Je neuem Markdown-Dokument die fehlenden Felder ``title``, ``context``, ``tags``, ``kind`` ergänzen.

    Args:
        svc: Dienst.
        new_docs: Einträge aus ``pending.new`` (werden um ``missing_fields`` ergänzt).
    """
    for entry in new_docs:
        rel = entry.get("path")
        if rel and str(rel).lower().endswith(".md") and svc.vault.exists(rel):
            meta = svc.vault.load(rel).meta
            entry["missing_fields"] = [f for f in SUGGESTED_FIELDS if _empty(meta.get(f))]


def known_tags(svc: Service) -> dict[str, int]:
    """Vorhandene Schlagwörter aus ``documents/`` und ``wiki/`` mit Häufigkeit.

    Args:
        svc: Dienst.

    Returns:
        Schlagwort → Anzahl, häufigste zuerst.
    """
    counts: Counter[str] = Counter()
    for rel in svc.vault.iter_files(("documents", "wiki")):
        if rel.lower().endswith(".md"):
            try:
                tags = svc.vault.load(rel).meta.get("tags")
            except PkmError:
                tags = None
            if isinstance(tags, list):
                counts.update(normalize_tags(tags))
            elif isinstance(tags, str) and tags.strip():
                counts.update(normalize_tags(tags.replace(",", " ").split()))
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def _metadata_fields(
    meta: dict[str, Any], set_fields: dict[str, Any], add_fields: dict[str, Any], overwrite: bool
) -> dict[str, Any]:
    """Zu schreibende Felder für ``set_document_metadata`` berechnen und prüfen.

    Args:
        meta: Bisheriges Frontmatter.
        set_fields: Zu setzende Felder.
        add_fields: An Listen anzuhängende Werte (nur ``tags``).
        overwrite: Vorhandene Werte überschreiben.

    Returns:
        Feld → neuer Wert (nur geänderte Felder).

    Raises:
        PkmError: ``protected_field`` außerhalb der Whitelist, ``invalid_argument`` bei ungültigen
            Werten, ``field_exists`` bei vorhandenen Werten ohne ``overwrite``.
    """
    bad = [k for k in [*set_fields, *add_fields] if k not in METADATA_FIELDS] + [k for k in add_fields if k != "tags"]
    if bad:
        raise PkmError("protected_field", "Erlaubt sind nur " + ", ".join(METADATA_FIELDS)
                       + " (add nur für tags).", fields=sorted(set(bad)))
    fields: dict[str, Any] = {}
    for key, value in set_fields.items():
        new = normalize_tags(value if isinstance(value, list) else [value]) if key == "tags" else " ".join(
            str(value).split())
        if _empty(new) or (key == "kind" and new not in KINDS):
            raise PkmError("invalid_argument", f"Ungültiger Wert für {key}: {value!r}"
                           + (f" (erlaubt: {', '.join(KINDS)})" if key == "kind" else ""), field=key)
        if not _empty(meta.get(key)) and meta.get(key) != new and not overwrite:
            raise PkmError("field_exists", f"{key} ist schon gesetzt ({meta.get(key)!r}); nur mit overwrite ändern.",
                           field=key, value=meta.get(key))
        fields[key] = new
    if "tags" in add_fields:
        current = meta.get("tags") if isinstance(meta.get("tags"), list) else []
        extra = add_fields["tags"] if isinstance(add_fields["tags"], list) else [add_fields["tags"]]
        fields["tags"] = normalize_tags([*fields.get("tags", current), *extra])
    return {k: v for k, v in fields.items() if meta.get(k) != v}


def set_document_metadata(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    svc: Service,
    target: str,
    expected_hash: str,
    set: dict[str, Any] | None = None,  # pylint: disable=redefined-builtin
    add: dict[str, Any] | None = None,
    overwrite: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    """Metadaten eines Dokuments nach Bestätigung des Nutzers eintragen (neue Version, ``PKM-Source: agent``).

    Erlaubt sind nur ``title``, ``context``, ``tags``, ``kind`` und ``short_citation``. Felder werden
    zeilengenau an der Stelle aus dem Schema eingefügt; übrige Zeilen bleiben unverändert.

    Args:
        svc: Dienst.
        target: Dokument in ``documents/`` (Pfad, Wikilink oder ``id:``).
        expected_hash: ``hash`` aus ``read``.
        set: Zu setzende Felder.
        add: An ``tags`` anzuhängende Werte.
        overwrite: Vorhandene Werte überschreiben (nur auf ausdrücklichen Wunsch des Nutzers).
        note: Änderungsnotiz.

    Returns:
        Rückgabe von ``finish`` (neue Version, Commit) bzw. ``unchanged``.

    Raises:
        PkmError: ``invalid_argument`` ohne Felder, sonst wie ``_metadata_fields`` und ``change``.
    """
    if not set and not add:
        raise PkmError("invalid_argument", "Keine Felder angegeben (set oder add).")
    rel = svc.resolve(target, ("documents",))
    fields = _metadata_fields(svc.vault.load(rel).meta, dict(set or {}), dict(add or {}), overwrite)

    def transform(doc: Doc) -> str:
        """Felder zeilengenau setzen.

        Args:
            doc: Dokument.

        Returns:
            Neuer Text.
        """
        return set_fields_linewise(doc.text or "", fields) if fields else doc.text or ""

    default = "Metadaten nach Bestätigung: " + ", ".join(fields or set or add or {})
    return svc.writer.change(rel, expected_hash, transform, note or default, source="agent")


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
    """Abschluss: Belege (verschoben, umbenannt, Version angehoben), ``mark``, Log, Index, Status, Lint, Commit.

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
        "raised_citations": raise_versions(svc),
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
