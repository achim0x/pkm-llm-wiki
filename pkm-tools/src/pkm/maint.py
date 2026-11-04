"""Maintenance commands of the CLI (specification 8): ids, versions, pending, mark, sha, commit-wiki.

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

import json
from collections import defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from . import docimages, hashes, imagefix
from .assets import AssetMap, asset_changes, known_assets
from .cloudsync import is_conflict_copy, sibling_conflicts
from .errors import PkmError
from .frontmatter import fix_frontmatter_text, set_fields_linewise
from .fsutil import write_bytes_atomic
from .gitlayer import build_message
from .ids import is_valid_id, new_id
from .normalize import encode
from .parse import normalize_key_input
from .paths import case_collisions
from .state import FORMAT, classify, load_state, state_key
from .vault import Doc, is_markdown, load_text_doc

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

WIKI_COMMIT_PATHS = ["wiki", ".pkm/state.json"]
SCHEMA_FILE = "CLAUDE.md"
PENDING_CATEGORIES = ("new", "changed", "meta_changed", "moved", "deleted")

# Classes *********************************************************************


class Maintenance:
    """Maintenance commands for the maintenance agent (CLI)."""

    def __init__(self, svc: Service) -> None:
        """Create the maintenance commands.

        Args:
            svc: Service with configuration, vault, Git and writer.
        """
        self.svc = svc
        self.cfg = svc.cfg
        self.vault = svc.vault
        self.git = svc.git
        self.writer = svc.writer
        self.conflicts: set[str] = set()

    # Inventory ****************************************************************

    def documents(self) -> tuple[list[Doc], list[dict[str, Any]]]:
        """Load all files below ``documents/`` (without conflict copies).

        Returns:
            Tuple of (documents, problems such as conflict copies, unreadable files,
            upper/lower case collisions).
        """
        docs: list[Doc] = []
        problems: list[dict[str, Any]] = []
        rels = list(self.vault.iter_files(("documents",)))
        for rel in rels:
            if is_conflict_copy(PurePosixPath(rel).name):
                problems.append({"problem": "conflict_copy", "path": rel})
                continue
            try:
                doc = self.vault.load(rel)
            except (PkmError, OSError) as exc:
                problems.append({"problem": "unreadable", "path": rel, "message": str(exc)})
                continue
            if doc.error:
                problems.append({"problem": doc.error, "path": rel, "message": doc.error_message})
            docs.append(doc)
        siblings = sibling_conflicts({d.rel: d.id for d in docs if d.kind == "md"})
        self.conflicts = {p["path"] for p in problems if p["problem"] == "conflict_copy"} | siblings
        problems.extend({"problem": "conflict_copy", "path": rel} for rel in sorted(siblings))
        docs = [d for d in docs if d.rel not in siblings]
        problems.extend({"problem": "case_collision", "paths": group} for group in case_collisions(rels))
        return docs, problems

    @staticmethod
    def duplicate_ids(docs: list[Doc]) -> dict[str, list[str]]:
        """Find IDs that are assigned more than once.

        Args:
            docs: Documents.

        Returns:
            ID → sorted paths, only for IDs with several files.
        """
        by_id: dict[str, list[str]] = defaultdict(list)
        for d in docs:
            if d.id:
                by_id[d.id].append(d.rel)
        return {i: sorted(p) for i, p in by_id.items() if len(p) > 1}

    # ids **********************************************************************

    def ids(self) -> dict[str, Any]:
        """``pkm ids``: enter missing ``id``/``version``, one commit per document.

        Returns:
            Assigned IDs, duplicate IDs, skipped files and problems.
        """
        with self.writer.lock():
            self.git.require_ok()
            docs, problems = self.documents()
            known = {d.id for d in docs if d.id}
            assigned, skipped = [], []
            for doc in docs:
                if doc.kind == "md" and doc.error:
                    skipped.append({"path": doc.rel, "reason": doc.error})
                elif doc.kind == "md" and (not doc.id or doc.version is None):
                    assigned.append(self._assign_id(doc, known))
            dups = self.duplicate_ids(self.documents()[0])
        return {
            "status": "ok",
            "assigned": assigned,
            "duplicates": [{"id": i, "paths": p} for i, p in sorted(dups.items())],
            "skipped": skipped,
            "problems": problems,
        }

    def _assign_id(self, doc: Doc, known: set[str]) -> dict[str, Any]:
        """Enter the ID (if needed) and version 1 and commit (``PKM-Source: agent``).

        Args:
            doc: Document without ID or version.
            known: IDs already assigned; the new ID is added.

        Returns:
            Path, ID and commit.
        """
        fields: dict[str, Any] = {}
        doc_id = doc.id
        if not doc_id:
            doc_id = new_id(self.svc.now(), exists=lambda i: i in known)
            known.add(doc_id)
            fields["id"] = doc_id
        fields["version"] = 1
        text = set_fields_linewise(doc.text or "", fields)
        msg = build_message(doc.title, "v1", "ID assigned", doc_id, 1, "agent")
        sha = self.writer.write_and_commit(doc.rel, text, msg)
        return {"path": doc.rel, "id": doc_id, "commit": sha[:10]}

    # versions *****************************************************************

    def versions(self) -> dict[str, Any]:
        """``pkm versions``: commit manually changed documents as a version (5.4).

        Moves are committed along with them; attachments and deleted files as well, so that
        the working tree stays clean.

        Returns:
            Committed and skipped files.
        """
        with self.writer.lock():
            self.git.require_ok()
            entries = self.git.status_entries("documents")
            dirty = {path for _xy, path in entries}
            deleted = {path for xy, path in entries if "D" in xy}
            committed: list[dict[str, Any]] = []
            skipped: list[dict[str, Any]] = []
            dups = self.duplicate_ids(self.documents()[0])
            handled: set[str] = set()
            for rel in sorted(dirty - deleted):
                if is_markdown(rel) and self.vault.exists(rel):
                    entry = self._version_markdown(rel, dups, skipped)
                    if entry is not None:
                        handled.add(rel)
                        handled.update(p for p in entry.pop("prev_paths") if p in deleted)
                        committed.append(entry)
            modified = {path for xy, path in entries if "M" in xy and not is_markdown(path)}
            image_commits, image_paths = self._commit_changed_images(modified - handled - deleted)
            committed += image_commits
            committed += self._commit_binaries(dirty - handled - image_paths, deleted - handled, skipped)
            committed += [self._commit_deleted(rel) for rel in sorted(deleted - handled) if is_markdown(rel)]
            committed += self._commit_schema()
        return {"status": "ok", "committed": committed, "skipped": skipped}

    def _image_findings(self, docs: list[Doc], result: dict[str, list[dict[str, Any]]]) -> None:
        """Report findings on data URIs (``image_issues``) and pure changes of the image notation (4.9).

        Args:
            docs: Documents.
            result: Result lists of ``pending`` (added to).
        """
        by_rel = {d.rel: d for d in docs if d.kind == "md" and d.parsed is not None and not d.error}
        limits = self.cfg.images
        for item in [*result.get("new", []), *result.get("changed", [])]:
            doc = by_rel.get(item.get("path") or "")
            if doc is None:
                continue
            issues = imagefix.image_issues(doc.body or "", limits, section_of=docimages.section_of(doc, doc.body or ""))
            if issues:
                item["image_issues"] = issues
            old = item.get("processed_version")
            if item in result.get("changed", []) and doc.id and old and "assets_changed" not in item:
                try:
                    _, text = self.svc.text_at_version(doc.id, int(old))
                except PkmError:
                    text = None
                old_body = load_text_doc(doc.rel, text.encode("utf-8")).body if text is not None else None
                if old_body is not None and imagefix.body_notation_only(old_body, doc.body or "", limits):
                    item["image_notation_only"] = True

    def _commit_changed_images(self, modified: set[str]) -> tuple[list[dict[str, Any]], set[str]]:
        """Commit changed associated image files as a new version of the documents that use them (4.9).

        The first document gets the image file in its commit, further documents one commit each.

        Args:
            modified: Changed, already versioned attachments.

        Returns:
            Tuple of (entries for ``committed``, image files handled this way).
        """
        out: list[dict[str, Any]] = []
        handled: set[str] = set()
        referenced = AssetMap(self.svc, self.documents()[0]).referenced() if modified else {}
        for image in sorted(p for p in modified if p in referenced):
            for rel in referenced[image]:
                doc = self.vault.load(rel)
                if doc.id and doc.version is not None and not doc.error:
                    version = doc.version + 1
                    text = set_fields_linewise(doc.text or "", {"version": version,
                                                                "date_updated": self.writer.now_stamp()})
                    msg = build_message(doc.title, f"v{version}", f"image changed: {PurePosixPath(image).name}",
                                        doc.id, version, "user")
                    extra = [] if image in handled else [image]
                    sha = self.writer.write_and_commit(rel, text, msg, extra, as_user=True)
                    handled.add(image)
                    out.append({"path": rel, "id": doc.id, "version": version, "image": image, "commit": sha[:10]})
        return out, handled

    def _commit_schema(self) -> list[dict[str, Any]]:
        """Record a manually changed ``CLAUDE.md`` (schema of the vault) as a user commit.

        Returns:
            An entry for ``committed`` or an empty list.
        """
        result: list[dict[str, Any]] = []
        if self.git.has_changes(SCHEMA_FILE):
            sha = self.git.commit_paths([SCHEMA_FILE], "pkm: CLAUDE.md changed\n\nPKM-Source: user\n", as_user=True)
            result = [{"path": SCHEMA_FILE, "commit": sha[:10]}]
        return result

    def _skip_reason(self, rel: str, doc: Doc, dups: dict[str, list[str]]) -> str | None:
        """Reason to skip a Markdown document in ``versions``.

        Args:
            rel: Relative path.
            doc: Loaded document.
            dups: Duplicate IDs.

        Returns:
            ``conflict_copy``, ``invalid_*``, ``missing_id``, ``duplicate_id`` or ``None``.
        """
        reason = None
        if is_conflict_copy(PurePosixPath(rel).name) or rel in self.conflicts:
            reason = "conflict_copy"
        elif doc.error:
            reason = doc.error
        elif not doc.id:
            reason = "missing_id"
        elif doc.id in dups:
            reason = "duplicate_id"
        return reason

    def _version_markdown(
        self, rel: str, dups: dict[str, list[str]], skipped: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Commit a changed Markdown document as a version.

        Args:
            rel: Relative path.
            dups: Duplicate IDs.
            skipped: List of skipped files (added to).

        Returns:
            Entry for ``committed`` with ``prev_paths`` (earlier paths) or ``None``.
        """
        result = None
        doc = self.vault.load(rel)
        reason = self._skip_reason(rel, doc, dups)
        if reason is not None:
            skipped.append({"path": rel, "reason": reason})
        else:
            assert doc.id is not None
            before = self.git.out("rev-parse", "HEAD").strip()
            prev_paths = {c.path for c in self.svc.versions(doc.id) if c.path}
            new_doc = self.writer.commit_user_state(doc)
            after = self.git.out("rev-parse", "HEAD").strip()
            if after != before:
                result = {
                    "path": rel, "id": doc.id, "version": new_doc.version,
                    "subject": self.git.out("log", "-1", "--format=%s").strip(), "commit": after[:10],
                    "prev_paths": prev_paths,
                }
        return result

    def _commit_deleted(self, rel: str) -> dict[str, Any]:
        """Commit a deleted Markdown document.

        Args:
            rel: Path of the deleted file.

        Returns:
            Entry for ``committed``.
        """
        old = load_text_doc(rel, self.git.show_file("HEAD", rel))
        if old.id:
            msg = build_message(old.title, "deleted", f"deleted: {rel}", old.id, old.version or 1, "user")
        else:
            msg = f"doc: {old.title} deleted\n\ndeleted: {rel}\n\nPKM-Source: user\n"
        sha = self.git.commit_paths([rel], msg, as_user=True)
        return {"path": rel, "id": old.id, "deleted": True, "commit": sha[:10]}

    def _commit_binaries(
        self, dirty: set[str], deleted: set[str], skipped: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Commit attachments: new, moved (by hash) or deleted.

        Args:
            dirty: Changed paths (without those already handled).
            deleted: Deleted paths (without those already handled).
            skipped: List of skipped files (added to).

        Returns:
            Entries for ``committed``.
        """
        out: list[dict[str, Any]] = []
        old_hashes = {
            rel: hashes.sha256_bytes(self.git.show_file("HEAD", rel)) for rel in sorted(deleted) if not is_markdown(rel)
        }
        for rel in sorted(dirty - deleted):
            if is_markdown(rel) or not self.vault.exists(rel):
                continue
            if is_conflict_copy(PurePosixPath(rel).name):
                skipped.append({"path": rel, "reason": "conflict_copy"})
                continue
            h = hashes.sha256_bytes(self.vault.path(rel).read_bytes())
            src = next((o for o, oh in old_hashes.items() if oh == h), None)
            if src:
                del old_hashes[src]
            out.append(self._commit_binary(rel, src, h))
        for rel in sorted(old_hashes):
            msg = f"file: {PurePosixPath(rel).name} deleted\n\ndeleted: {rel}\n\nPKM-Source: user\n"
            out.append({"path": rel, "deleted": True, "commit": self.git.commit_paths([rel], msg, as_user=True)[:10]})
        return out

    def _commit_binary(self, rel: str, src: str | None, file_hash: str) -> dict[str, Any]:
        """Commit a new or moved attachment.

        Args:
            rel: New path.
            src: Old path for a move, otherwise ``None``.
            file_hash: SHA-256 of the file.

        Returns:
            Entry for ``committed``.
        """
        if src:
            paths, note, label = [rel, src], f"moved: {src} → {rel}", "moved"
        else:
            paths, note, label = [rel], "new or changed", "added"
        msg = f"file: {PurePosixPath(rel).name} {label}\n\n{note}\n\nPKM-Source: user\n"
        sha = self.git.commit_paths(paths, msg, as_user=True)
        return {"path": rel, "moved_from": src, "sha256": file_hash, "commit": sha[:10]}

    # pending ******************************************************************

    def pending(self) -> dict[str, Any]:
        """``pkm pending``: documents to process per 4.8.

        Returns:
            Lists ``new``, ``changed``, ``meta_changed``, ``moved``, ``deleted`` as well as ``problems``
            and ``counts``.
        """
        docs, problems = self.documents()
        entries: dict[str, dict[str, Any]] = load_state(self.cfg)["documents"]
        amap = AssetMap(self.svc, docs)
        referenced = amap.referenced()
        orphans = amap.orphans(known_assets(entries))
        dups = self.duplicate_ids(docs)
        problems.extend({"problem": "duplicate_id", "id": i, "paths": paths} for i, paths in dups.items())
        result: dict[str, list[dict[str, Any]]] = {c: [] for c in PENDING_CATEGORIES}
        present: set[str] = set()
        for doc in docs:
            if doc.kind == "bin" and (doc.rel in referenced or doc.rel in orphans):
                present.add(state_key(doc) or "")  # associated or orphaned images are not documents
            elif not (doc.kind == "md" and doc.error):
                self._pending_doc(doc, entries, dups, result, present)
        _asset_pending(docs, entries, amap, result)
        self._image_findings(docs, result)
        result["deleted"] = _deleted_entries(entries, present)
        result.pop("invalid", None)
        counts = {k: len(v) for k, v in result.items()}
        return {"status": "ok", **result, "orphaned_attachments": orphans, "problems": problems, "counts": counts}

    @staticmethod
    def _pending_doc(
        doc: Doc,
        entries: dict[str, dict[str, Any]],
        dups: dict[str, list[str]],
        result: dict[str, list[dict[str, Any]]],
        present: set[str],
    ) -> None:
        """Classify a document for ``pending``.

        Args:
            doc: Document.
            entries: Entries from ``state.json``.
            dups: Duplicate IDs; for duplicates only the known version counts.
            result: Result lists (added to).
            present: Keys found (added to).
        """
        key = state_key(doc)
        entry = entries.get(key) if key else None
        if doc.kind == "md" and not key:
            result["new"].append({"id": None, "path": doc.rel, "title": doc.title, "missing_id": True})
        elif key is not None and (key not in dups or (entry and entry.get("path") == doc.rel)):
            present.add(key)
            base: dict[str, Any] = {"id": doc.id, "path": doc.rel, "title": doc.title}
            if doc.kind == "bin":
                base = {"id": None, "key": key, "path": doc.rel, "title": doc.title}
            if entry and entry.get("path") and entry["path"] != doc.rel:
                result["moved"].append({**base, "from": entry["path"], "to": doc.rel})
            info = classify(doc, entry)
            if info is not None:
                category = info.pop("category")
                result.setdefault(category, []).append({**base, **info})

    # mark *********************************************************************

    def mark(self, targets: list[str], pages: list[str] | None = None, remove: bool = False) -> dict[str, Any]:
        """``pkm mark``: record documents as processed in ``state.json``.

        Args:
            targets: IDs, paths or (with ``remove``) keys like ``sha:…``.
            pages: Wiki pages that cite the documents.
            remove: Remove entries instead of recording them.

        Returns:
            The recorded or removed keys.

        Raises:
            PkmError: ``not_found`` or ``invalid_argument``.
        """
        with self.writer.lock():
            state = load_state(self.cfg)
            docs_state: dict[str, Any] = state["documents"]
            page_refs = [page_ref(self.svc.resolve(p, ("wiki",))) for p in (pages or [])]
            amap = None if remove else AssetMap(self.svc, self.documents()[0])
            marked = [
                _remove_entry(docs_state, t) if remove or amap is None else self._mark_entry(docs_state, t, page_refs,
                                                                                           amap)
                for t in targets
            ]
            self.save_state(state)
        return {"status": "ok", "marked": marked}

    def _mark_entry(
        self, docs_state: dict[str, Any], target: str, page_refs: list[str], amap: AssetMap
    ) -> dict[str, Any]:
        """Record a document with version and hashes.

        Args:
            docs_state: ``documents`` from ``state.json`` (changed).
            target: ID or path.
            page_refs: Wiki pages (merged with existing ones).
            amap: References to image files (for ``assets``).

        Returns:
            Key, path and processed version.

        Raises:
            PkmError: ``invalid_argument`` for Markdown without a valid ID.
        """
        ref = f"id:{target}" if is_valid_id(target) else target
        doc = self.vault.load(self.svc.resolve(ref, ("documents",)))
        key = state_key(doc)
        if key is None or (doc.kind == "md" and (doc.error or doc.hashes is None)):
            raise PkmError("invalid_argument", f"{doc.rel} has no valid ID/frontmatter.", path=doc.rel)
        wiki_pages = list(dict.fromkeys([*docs_state.get(key, {}).get("wiki_pages", []), *page_refs]))
        now = self.svc.now().isoformat(timespec="seconds")
        entry: dict[str, Any] = {"path": doc.rel, "processed_at": now, "wiki_pages": wiki_pages}
        if doc.hashes is not None:
            entry = {
                "path": doc.rel,
                "processed_version": doc.version,
                "file_hash": doc.hashes.file_hash,
                "body_hash": doc.hashes.body_hash,
                "meta_hash": doc.hashes.meta_hash,
                "sections": dict(doc.hashes.sections),
                "processed_at": now,
                "wiki_pages": wiki_pages,
                "assets": amap.assets(doc.rel),
            }
        docs_state[key] = entry
        return {"key": key, "path": doc.rel, "version": entry.get("processed_version")}

    def save_state(self, state: dict[str, Any]) -> None:
        """Write ``state.json`` atomically (entries sorted).

        Args:
            state: Processing state.
        """
        state["version"] = FORMAT
        state["documents"] = dict(sorted(state["documents"].items()))
        p = self.cfg.state_path
        p.parent.mkdir(parents=True, exist_ok=True)
        write_bytes_atomic(p, encode(json.dumps(state, ensure_ascii=False, indent=2) + "\n"))

    # sha **********************************************************************

    def sha(self, target: str, section: str | None = None, full: bool = False) -> dict[str, Any]:
        """``pkm sha``: hashes per 4.8.

        Args:
            target: Document or attachment.
            section: Section key; all hashes if omitted.
            full: Full hashes instead of six characters.

        Returns:
            For attachments ``file_hash``; with ``section`` ``id``, ``version``, ``sha``; otherwise all
            section hashes as well as ``body_hash``, ``meta_hash`` and ``file_hash``.

        Raises:
            PkmError: For unreadable files or an unknown section (``not_found``).
        """
        doc = self.svc.load(target)
        cut = (lambda h: h) if full else hashes.short
        if doc.kind == "bin":
            result: dict[str, Any] = {"status": "ok", "path": doc.rel, "file_hash": cut(doc.bin_hash or "")}
        elif doc.hashes is None:
            raise PkmError(doc.error or "invalid_encoding", doc.error_message or "File not readable.")
        elif section is not None:
            key = normalize_key_input(section)
            if key not in doc.hashes.sections:
                raise PkmError("not_found", f"Section not found: {section}", sections=list(doc.hashes.sections))
            result = {"status": "ok", "path": doc.rel, "id": doc.id, "version": doc.version,
                      "section": key, "sha": cut(doc.hashes.sections[key])}
        else:
            result = {
                "status": "ok", "path": doc.rel, "id": doc.id, "version": doc.version,
                "sections": {k: cut(v) for k, v in doc.hashes.sections.items()},
                "body_hash": cut(doc.hashes.body_hash), "meta_hash": cut(doc.hashes.meta_hash),
                "file_hash": cut(doc.hashes.file_hash),
            }
        return result

    # fix-frontmatter **********************************************************

    def fix_frontmatter(self, targets: list[str] | None = None, all_documents: bool = False) -> dict[str, Any]:
        """``pkm fix-frontmatter``: repair the frontmatter line by line (only on instruction, 4.1).

        Puts values with ``: `` or leading YAML special characters in quotes and renames
        ``short citation`` to ``short_citation``. Without a target and without ``all_documents`` the
        affected files are only listed. Every changed file with an ID is committed as a new version
        (``PKM-Source: user``); files without an ID are versioned later by ``pkm ids``.

        Args:
            targets: Paths, short names, IDs or short citations.
            all_documents: Repair all affected documents.

        Returns:
            ``dry_run`` and per file path, changes and possibly version and commit.
        """
        dry_run = not targets and not all_documents
        with self.writer.lock():
            if not dry_run:
                self.git.require_ok()
            if targets:
                docs = [self.vault.load(self.svc.resolve(t, ("documents",))) for t in targets]
            else:
                docs = [d for d in self.documents()[0] if d.kind == "md" and d.text is not None]
            files = []
            for doc in docs:
                new_text, changes = fix_frontmatter_text(doc.text or "")
                if changes:
                    entry: dict[str, Any] = {"path": doc.rel, "changes": changes}
                    if not dry_run:
                        entry.update(self._apply_fix(doc.rel, new_text))
                    files.append(entry)
        return {"status": "ok", "dry_run": dry_run, "files": files}

    def _apply_fix(self, rel: str, new_text: str) -> dict[str, Any]:
        """Write the repaired version and (if there is an ID) commit it as a version.

        Args:
            rel: Relative path.
            new_text: Repaired text.

        Returns:
            ``version`` and ``commit`` or ``committed: False`` without ID.
        """
        self.writer.write_atomic(rel, new_text)
        doc = self.vault.load(rel)
        result: dict[str, Any] = {"committed": False}
        if doc.id and not doc.error:
            new_doc = self.writer.commit_user_state(doc)
            result = {"committed": True, "version": new_doc.version,
                      "commit": self.git.out("rev-parse", "HEAD").strip()[:10]}
        return result

    # commit-wiki **************************************************************

    def commit_wiki(self, message: str) -> dict[str, Any]:
        """``pkm commit-wiki``: agent commit only for ``wiki/`` and ``.pkm/state.json``.

        Args:
            message: Commit subject; ``pkm:`` is added if it is missing.

        Returns:
            ``status: ok`` with commit and files or ``status: unchanged``.

        Raises:
            PkmError: ``invalid_argument`` without a message, ``git_unavailable``.
        """
        message = " ".join((message or "").split())
        if not message:
            raise PkmError("invalid_argument", "--message is missing.")
        if not message.startswith("pkm:"):
            message = f"pkm: {message}"
        with self.writer.lock():
            self.git.require_ok()
            paths = [p for p in WIKI_COMMIT_PATHS if (self.cfg.root / p).exists()]
            result: dict[str, Any] = {"status": "unchanged", "commit": None}
            if self.git.has_changes(*paths):
                files = [p for _xy, p in self.git.status_entries(*paths)]
                sha = self.git.commit_paths(paths, f"{message}\n\nPKM-Source: agent\n")
                result = {"status": "ok", "commit": sha[:10], "files": files}
        return result

# Functions *******************************************************************


def _asset_pending(
    docs: list[Doc], entries: dict[str, dict[str, Any]], amap: AssetMap, result: dict[str, list[dict[str, Any]]]
) -> None:
    """Report documents with changed associated image files as ``changed`` (4.9).

    Args:
        docs: Documents.
        entries: Entries from ``state.json``.
        amap: References to image files.
        result: Result lists of ``pending`` (added to).
    """
    listed = {item.get("path"): item for cat in ("changed", "meta_changed") for item in result.get(cat, [])}
    for doc in docs:
        entry = entries.get(doc.id or "") if doc.kind == "md" else None
        changed = asset_changes(entry.get("assets"), amap.assets(doc.rel)) if entry else set()
        if changed:
            sections = [{"key": k, "change": "changed"} for k in amap.sections_for(doc.rel, changed)]
            item = listed.get(doc.rel)
            if item is None:
                item = {"id": doc.id, "path": doc.rel, "title": doc.title,
                        "processed_version": entry.get("processed_version") if entry else None,
                        "version": doc.version, "sections": []}
                result["changed"].append(item)
            known = {s["key"] for s in item.get("sections", [])}
            item["sections"] = item.get("sections", []) + [s for s in sections if s["key"] not in known]
            item["assets_changed"] = sorted(changed)


def page_ref(rel: str) -> str:
    """Wiki page as a reference without extension (as in ``state.json``).

    Args:
        rel: Relative path.

    Returns:
        Path without ``.md``.
    """
    return rel[:-3] if rel.lower().endswith(".md") else rel


def _deleted_entries(entries: dict[str, dict[str, Any]], present: set[str]) -> list[dict[str, Any]]:
    """Entries from ``state.json`` whose document no longer exists.

    Args:
        entries: Entries from ``state.json``.
        present: Keys of the documents found.

    Returns:
        Entries for ``deleted`` with path, processed version and wiki pages.
    """
    deleted = []
    for key, entry in sorted(entries.items()):
        if key not in present:
            item = {"key": key, "path": entry.get("path"), "processed_version": entry.get("processed_version"),
                    "wiki_pages": entry.get("wiki_pages", [])}
            if not key.startswith("sha:"):
                item["id"] = key
            deleted.append(item)
    return deleted


def _remove_entry(docs_state: dict[str, Any], target: str) -> dict[str, Any]:
    """Remove an entry from ``state.json``.

    Args:
        docs_state: ``documents`` from ``state.json`` (changed).
        target: Key (ID, ``id:…`` or ``sha:…``).

    Returns:
        Key with ``removed: True``.

    Raises:
        PkmError: ``not_found`` if the entry does not exist.
    """
    key = target[3:] if target.startswith("id:") else target
    if key not in docs_state:
        raise PkmError("not_found", f"No entry in state.json: {target}")
    del docs_state[key]
    return {"key": key, "removed": True}

# Main ************************************************************************
