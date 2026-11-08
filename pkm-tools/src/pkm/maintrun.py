"""Maintenance run as three steps for the MCP server ``pkm-maintenance``: begin, write wiki page, finish.

All steps are deterministic. The content work (writing pages, choosing citations) is done by
the LLM; the mechanical maintenance commands run here bundled in a fixed order.

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

from . import docimages, imagefix, images
from .assets import AssetMap
from .citations import fix_citations, parse_page, sync_citations
from .citeraise import raise_versions
from .config import DEFAULT_LANGUAGE, DOC_LANGUAGES, WIKI_SECTIONS
from .doctor import doctor
from .errors import PkmError
from .frontmatter import set_fields_linewise
from .ids import is_valid_id
from .inboxnames import add_rename_proposals, rename_inbox_document
from .lint import lint, write_report
from .maint import Maintenance, page_ref
from .paths import is_platform_safe_name, safe_resolve
from .schema import KINDS, normalize_tags
from .vault import Doc
from .wikigen import build_index, build_status, wiki_pages, write_if_changed
from .wikitexts import text

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
    """Preparation: ``doctor``, ``versions``, ``ids``, ``pending`` and, for moves, ``fix-citations``.

    Args:
        svc: Service.
        with_lint: Additionally return the lint report (for the "lint" flow).

    Returns:
        ``status`` (``ok``, ``blocked`` for environment errors, ``needs_decision`` for duplicate
        IDs), ``wiki_language`` (also given here because server instructions do not reach the model
        in every client, e.g. Cowork), the results of the individual steps and the documents to process.
    """
    check = doctor(svc, short=True)
    result: dict[str, Any] = {"status": "blocked", "wiki_language": wiki_language(svc.cfg.language),
                              "doctor": check["checks"]}
    if check["status"] == "ok":
        maint = Maintenance(svc)
        versions = maint.versions()
        ids = maint.ids()
        pend = maint.pending()
        add_missing_fields(svc, pend["new"])
        add_rename_proposals(svc, pend["new"])
        fixed = fix_citations(svc) if pend["moved"] else None
        result = {
            "status": "needs_decision" if ids["duplicates"] else "ok",
            "wiki_language": result["wiki_language"],
            "versions": {"committed": versions["committed"], "skipped": versions["skipped"]},
            "ids": {k: ids[k] for k in ("assigned", "duplicates", "skipped", "problems")},
            "pending": pend,
            "fixed_citations": fixed,
            "known_tags": known_tags(svc),
        }
        if with_lint:
            result["lint"] = lint(svc)
    return result


def wiki_language(language: str) -> dict[str, Any]:
    """Language of new wiki pages, log entries and reports (``PKM_LANGUAGE``, 4.2).

    Args:
        language: ``en`` or ``de``.

    Returns:
        ``code``, ``name``, ``summary_label`` and ``sections`` (headings of new wiki pages).
    """
    key = language if language in WIKI_SECTIONS else DEFAULT_LANGUAGE
    label, sections = WIKI_SECTIONS[key]
    return {"code": key, "name": DOC_LANGUAGES[key][0], "summary_label": label, "sections": list(sections)}


def _empty(value: Any) -> bool:
    """Check whether a frontmatter value is missing or empty.

    Args:
        value: Value.

    Returns:
        ``True`` for ``None``, empty text or an empty list.
    """
    return value is None or (isinstance(value, str | list) and not (value.strip() if isinstance(value, str) else value))


def add_missing_fields(svc: Service, new_docs: list[dict[str, Any]]) -> None:
    """Add the missing fields ``title``, ``context``, ``tags``, ``kind`` for each new Markdown document.

    Args:
        svc: Service.
        new_docs: Entries from ``pending.new`` (``missing_fields`` is added to them).
    """
    for entry in new_docs:
        rel = entry.get("path")
        if rel and str(rel).lower().endswith(".md") and svc.vault.exists(rel):
            meta = svc.vault.load(rel).meta
            entry["missing_fields"] = [f for f in SUGGESTED_FIELDS if _empty(meta.get(f))]


def known_tags(svc: Service) -> dict[str, int]:
    """Existing tags from ``documents/`` and ``wiki/`` with their frequency.

    Args:
        svc: Service.

    Returns:
        Tag → count, most frequent first.
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
    """Compute and check the fields to write for ``set_document_metadata``.

    Args:
        meta: Previous frontmatter.
        set_fields: Fields to set.
        add_fields: Values to append to lists (``tags`` only).
        overwrite: Overwrite existing values.

    Returns:
        Field → new value (changed fields only).

    Raises:
        PkmError: ``protected_field`` outside the whitelist, ``invalid_argument`` for invalid
            values, ``field_exists`` for existing values without ``overwrite``.
    """
    bad = [k for k in [*set_fields, *add_fields] if k not in METADATA_FIELDS] + [k for k in add_fields if k != "tags"]
    if bad:
        raise PkmError("protected_field", "Only " + ", ".join(METADATA_FIELDS)
                       + " are allowed (add only for tags).", fields=sorted(set(bad)))
    fields: dict[str, Any] = {}
    for key, value in set_fields.items():
        new = normalize_tags(value if isinstance(value, list) else [value]) if key == "tags" else " ".join(
            str(value).split())
        if _empty(new) or (key == "kind" and new not in KINDS):
            raise PkmError("invalid_argument", f"Invalid value for {key}: {value!r}"
                           + (f" (allowed: {', '.join(KINDS)})" if key == "kind" else ""), field=key)
        if not _empty(meta.get(key)) and meta.get(key) != new and not overwrite:
            raise PkmError("field_exists", f"{key} is already set ({meta.get(key)!r}); change only with overwrite.",
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
    """Enter the metadata of a document after confirmation by the user (new version, ``PKM-Source: agent``).

    Only ``title``, ``context``, ``tags``, ``kind`` and ``short_citation`` are allowed. Fields are
    inserted line by line at the position given by the schema; all other lines stay unchanged.

    Args:
        svc: Service.
        target: Document in ``documents/`` (path, wikilink or ``id:``).
        expected_hash: ``hash`` from ``read``.
        set: Fields to set.
        add: Values to append to ``tags``.
        overwrite: Overwrite existing values (only on explicit request by the user).
        note: Change note.

    Returns:
        Return value of ``finish`` (new version, commit) or ``unchanged``.

    Raises:
        PkmError: ``invalid_argument`` without fields, otherwise like ``_metadata_fields`` and ``change``.
    """
    if not set and not add:
        raise PkmError("invalid_argument", "No fields given (set or add).")
    rel = svc.resolve(target, ("documents",))
    fields = _metadata_fields(svc.vault.load(rel).meta, dict(set or {}), dict(add or {}), overwrite)

    def transform(doc: Doc) -> str:
        """Set the fields line by line.

        Args:
            doc: Document.

        Returns:
            New text.
        """
        return set_fields_linewise(doc.text or "", fields) if fields else doc.text or ""

    default = "metadata after confirmation: " + ", ".join(fields or set or add or {})
    return svc.writer.change(rel, expected_hash, transform, note or default, source="agent", check_limit=False)


def _page_path(path: str) -> str:
    """Check and normalize the path of a writable wiki page.

    Args:
        path: Path like ``wiki/topics/topic`` or ``wiki/topics/topic.md``.

    Returns:
        Relative path with ``.md``.

    Raises:
        PkmError: ``forbidden`` outside the page folders, ``invalid_path`` for invalid names.
    """
    rel = path.strip().replace("\\", "/").lstrip("/")
    if PurePosixPath(rel).suffix.lower() != ".md":
        rel = f"{rel}.md"
    if not rel.startswith(WRITABLE_DIRS):
        raise PkmError("forbidden", "Writing only in " + ", ".join(WRITABLE_DIRS)
                       + " (index.md, _status.md, log.md and sources are generated).", path=rel)
    if not all(is_platform_safe_name(part) for part in PurePosixPath(rel).parts):
        raise PkmError("invalid_path", "Invalid file or folder name.", path=rel)
    return rel


def write_wiki_page(
    svc: Service, path: str, content: str, expected_hash: str | None = None, fix_images: bool = False
) -> dict[str, Any]:
    """Create or replace a wiki page (without commit; ``finish_maintenance`` does that).

    Image placeholders from ``read`` are replaced byte for byte by the originals. New data URIs must
    conform to the form of 4.9; with ``fix_images`` the server fixes them without asking.

    Args:
        svc: Service.
        path: Page below ``wiki/topics|entities|summaries|syntheses/``.
        content: Complete content with frontmatter.
        expected_hash: ``hash`` from ``read`` for existing pages; omit for new pages.
        fix_images: Fix nonconforming data URIs.

    Returns:
        ``status`` (``created``, ``changed``, ``unchanged``), path and new ``hash``.

    Raises:
        PkmError: ``forbidden``, ``invalid_path``, ``conflict``, ``too_large``, ``unknown_image`` or
            ``nonconforming_image``.
    """
    rel = _page_path(path)
    safe_resolve(svc.cfg.root, rel)
    svc.writer.check_size(content, "The page")
    with svc.writer.lock():
        exists = svc.vault.exists(rel)
        current = svc.vault.load(rel).hashes if exists else None
        if exists and (expected_hash is None or current is None or current.file_hash != expected_hash):
            raise PkmError("conflict", "Page exists or was changed: read it with read first and pass its "
                           "hash as expected_hash.", path=rel)
        if not exists and expected_hash is not None:
            raise PkmError("conflict", "Page does not exist (any more); create it without expected_hash.", path=rel)
        content = _checked_page(svc, rel, content, exists, fix_images)
        (svc.cfg.root / rel).parent.mkdir(parents=True, exist_ok=True)
        changed = write_if_changed(svc, rel, content)
        new = svc.vault.load(rel).hashes
    status = "created" if not exists else ("changed" if changed else "unchanged")
    return {"status": status, "path": rel, "hash": new.file_hash if new else None}


def _checked_page(svc: Service, rel: str, content: str, exists: bool, fix_images: bool) -> str:
    """Content of a wiki page: translate placeholders back, check new data URIs (4.9).

    Args:
        svc: Service.
        rel: Path of the page.
        content: New content.
        exists: Whether the page already exists.
        fix_images: Fix nonconforming data URIs.

    Returns:
        The content to write.

    Raises:
        PkmError: ``unknown_image`` or ``nonconforming_image``.
    """
    old = svc.vault.load(rel).text or "" if exists else ""
    old_refs = images.find_images(old)
    content = images.restore_placeholders(content, old_refs)
    new_links = {r.link for r in images.find_images(content) if r.inline} - {r.link for r in old_refs if r.inline}
    issues = imagefix.image_issues(content, svc.cfg.images, legacy=False, wiki=True, only_links=new_links) \
        if new_links else []
    if issues and (not fix_images or not all(i["fixable"] for i in issues)):
        raise PkmError("nonconforming_image", "Data URIs do not conform to 4.9; fix them with fix_images=true "
                       "or rebuild the SVG.", image_issues=issues, path=rel)
    if issues:
        content, _ = imagefix.fix_text(content, svc.cfg.images, legacy=False, wiki=True, only_links=new_links)
    return content


def fix_document_images(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    svc: Service, target: str, expected_hash: str, images_only: list[str] | None = None,
    image_alt: dict[str, str] | None = None, apply: bool = False, confirm_shortening: bool = False,
    note: str | None = None, extract: bool = False, min_kb: int = imagefix.EXTRACT_MIN_KB,
) -> dict[str, Any]:
    """Tool ``fix_images`` in the maintenance server: only ``documents/``, commit with ``PKM-Source: agent`` (7.7).

    Args:
        svc: Service.
        target: Document.
        expected_hash: Hash from ``read``.
        images_only: Only these images.
        image_alt: Alt texts per name.
        apply: Write instead of only proposing.
        confirm_shortening: Removal of unused definitions confirmed.
        note: Change note.
        extract: Store large embedded raster images as files.
        min_kb: Threshold for ``extract``.

    Returns:
        Return value of ``docimages.fix_document``.
    """
    return docimages.fix_document(svc.writer, target, expected_hash, images_only=images_only, image_alt=image_alt,
                                  apply=apply, confirm_shortening=confirm_shortening, note=note, source="agent",
                                  areas=("documents/",), extract=extract, min_kb=min_kb)


def rename_document(
    svc: Service, target: str, expected_hash: str, apply: bool = False, name: str | None = None
) -> dict[str, Any]:
    """Name a new document in the inbox after the convention, with its image folder (after confirmation).

    Args:
        svc: Service.
        target: Document in ``documents/_inbox/``.
        expected_hash: ``hash`` from ``read``.
        apply: Carry out; without it only the proposal.
        name: Desired name instead of the title.

    Returns:
        Result of ``rename_inbox_document``.
    """
    return rename_inbox_document(svc, target, expected_hash, apply=apply, stem=name)


def _load_target(svc: Service, target: str) -> Doc:
    """Load a document from ``documents/`` by ID or path.

    Args:
        svc: Service.
        target: ID (``d-…`` or ``id:d-…``) or path.

    Returns:
        The document.
    """
    ref = f"id:{target}" if is_valid_id(target) else target
    return svc.load(ref, ("documents",))


def citing_pages(svc: Service, doc: Doc) -> list[str]:
    """Wiki pages that cite a document.

    Args:
        svc: Service.
        doc: Document (Markdown via ``id``, attachments via the path).

    Returns:
        Pages as references without extension, sorted.
    """
    pages = set()
    for page in wiki_pages(svc):
        if page.parsed is not None and not page.error:
            cits = parse_page(page).definitions.values()
            if any((doc.id and c.doc_id == doc.id) or c.target_rel == doc.rel for c in cits):
                pages.add(page_ref(page.rel))
    return sorted(pages)


def _mark_processed(svc: Service, processed: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Record processed documents with the citing pages in ``state.json``.

    Args:
        svc: Service.
        processed: IDs or paths.

    Attachments (image files linked by a document, 4.9) need no entry of their own: they are processed
    with their document and are skipped without a warning.

    Returns:
        Tuple of (entries, warnings for documents without a citation).
    """
    maint = Maintenance(svc)
    marked: list[dict[str, Any]] = []
    warnings: list[str] = []
    referenced = AssetMap(svc, maint.documents()[0]).referenced() if processed else {}
    for target in processed:
        doc = _load_target(svc, target)
        if doc.kind == "bin" and doc.rel in referenced:
            marked.append({"path": doc.rel, "skipped": "attachment", "attachment_of": referenced[doc.rel]})
            continue
        pages = citing_pages(svc, doc)
        if not pages:
            warnings.append(f"{doc.rel}: no wiki page cites this document.")
        entry = maint.mark([target], pages)["marked"][0]
        marked.append({**entry, "pages": pages})
    return marked, warnings


def append_log(svc: Service, operation: str, title: str | None, entry: str) -> str:
    """Append an entry to ``wiki/log.md`` (append only, never change).

    Args:
        svc: Service.
        operation: ``ingest``, ``lint`` or ``fix``.
        title: Short note after the heading, e.g. ``1 new, 1 changed``.
        entry: Content (Markdown list).

    Returns:
        The generated heading.
    """
    stamp = svc.now().strftime("%Y-%m-%d %H:%M")
    heading = f"## [{stamp}] {operation}" + (f" | {' '.join(title.split())}" if title else "")
    p = svc.cfg.root / LOG_PATH
    old = p.read_text(encoding="utf-8").rstrip("\n") if p.is_file() else f"# {text(svc.cfg.language, 'log_title')}"
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
    """Finish: citations (moved, renamed, version raised), ``mark``, log, index, status, lint, commit.

    Args:
        svc: Service.
        log_entry: Content of the log entry (Markdown list).
        operation: ``ingest``, ``lint`` or ``fix``.
        log_title: Short note for the log heading.
        processed: Processed documents (IDs or paths); the citing pages are determined.
        removed: Keys of deleted documents that are removed from ``state.json``.
        questions: Questions for ``wiki/_status.md``.
        lint_report: Write the lint report to ``wiki/_lint/``.

    Returns:
        Results of the individual steps, warnings, lint report and commit.

    Raises:
        PkmError: ``invalid_argument`` for an unknown operation or an empty log entry.
    """
    if operation not in OPERATIONS:
        raise PkmError("invalid_argument", f"operation must be one of {', '.join(OPERATIONS)}.")
    if not log_entry.strip():
        raise PkmError("invalid_argument", "log_entry must not be empty.")
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
    """Subject of the agent commit.

    Args:
        operation: ``ingest``, ``lint`` or ``fix``.
        count: Number of processed documents.

    Returns:
        E.g. ``pkm: ingest 2 documents``.
    """
    suffix = f" {count} document{'s' if count != 1 else ''}" if count else ""
    return f"pkm: {operation}{suffix}"

# Main ************************************************************************
