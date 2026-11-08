"""Writing operations (specification 5.4, 6, 7.2).

Flow of every change: check Git → check target → hash protection → commit a manual state as its
own version if needed → apply the change → version +1, ``updated`` → write atomically →
commit only this file → on errors reset the file.

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

import contextlib
import os
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from . import docimages
from .appendtext import append_lines
from .diffs import unified_diff
from .errors import NO_VERSIONING, PkmError
from .frontmatter import PROTECTED, dump_meta, set_fields_linewise
from .fsutil import file_lock, replace_file
from .gitlayer import Commit, build_message
from .ids import new_id
from .normalize import encode, normalize_fragment, normalize_text
from .parse import strip_frontmatter
from .paths import fit_stem, is_platform_safe_name, slug_words
from .schema import DEFAULT_KIND, DEFAULT_TOOLCHAIN, FIELD_ORDER, KINDS, normalize_tags, order_meta, stamp
from .vault import SCRATCH, Doc, load_text_doc
from .writeguard import check_shortening, check_size

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

INBOX = "documents/_inbox"
CREATE_AREAS = ("documents", SCRATCH)
DIFF_LINES = 80
FILE_MODE_MASK = 0o777

# Classes *********************************************************************


@dataclass
class _UserVersion:
    """Plan for committing a manually changed state.

    Attributes:
        doc_id: Document ID (possibly newly assigned).
        version: Version number of the commit.
        label: Suffix in the subject (``v<n>`` or ``moved``).
        note: Change note.
        fields: Frontmatter fields to set beforehand.
        extra_paths: Further paths in the commit (old path for a move).
    """

    doc_id: str
    version: int
    label: str
    note: str
    fields: dict[str, Any] = field(default_factory=dict)
    extra_paths: list[str] = field(default_factory=list)


class Writer:
    """All writing operations on documents (MCP tools and CLI)."""

    def __init__(self, svc: Service) -> None:
        """Create the writer.

        Args:
            svc: Service with configuration, vault and Git.
        """
        self.svc = svc
        self.cfg = svc.cfg
        self.git = svc.git
        self.vault = svc.vault

    # Basics *******************************************************************

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        """Serialize write operations of MCP and CLI via a lock file.

        Yields:
            Nothing; the lock holds within the ``with`` block.
        """
        if self.cfg.git_dir.is_dir():
            with file_lock(self.cfg.git_dir / "pkm.lock"):
                yield
        elif not self.svc.versioning:
            self.cfg.cache_dir.mkdir(parents=True, exist_ok=True)
            with file_lock(self.cfg.cache_dir / "pkm.lock"):
                yield
        else:
            yield

    def require_git(self) -> None:
        """Make sure Git is ready for writing, if version control is on.

        Raises:
            PkmError: ``git_unavailable`` with the reason.
        """
        if self.svc.versioning:
            self.git.require_ok()

    def now_stamp(self) -> str:
        """Current time for date fields: local time without time zone (4.1).

        Returns:
            Timestamp, e.g. ``2026-11-02T19:05:00``.
        """
        return stamp(self.svc.now())

    def check_size(self, text: str, what: str, confirmed: bool = False) -> None:
        """Check the size limit ``PKM_MAX_KB`` against the text without data URIs (``writeguard``).

        Args:
            text: Text to check.
            what: Label for the error message.
            confirmed: Larger text confirmed by the user (``confirm_large``).
        """
        check_size(text, what, self.cfg.max_kb, confirmed)

    def write_atomic(self, rel: str, text: str) -> None:
        """Write a file atomically (temporary file, then rename), keeping the file permissions.

        Args:
            rel: Relative path.
            text: Content; brought into write form.
        """
        p = self.vault.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".pkm-tmp-{uuid.uuid4().hex}-{p.name}")
        mode = p.stat().st_mode & FILE_MODE_MASK if p.exists() else None
        try:
            with open(tmp, "wb") as fh:
                fh.write(encode(text))
                fh.flush()
                os.fsync(fh.fileno())
            if mode is not None:
                os.chmod(tmp, mode)
            replace_file(tmp, p)
        finally:
            if tmp.exists():
                tmp.unlink()

    def write_and_commit(
        self, rel: str, text: str, message: str, extra_paths: list[str] | None = None, as_user: bool = False
    ) -> str:
        """Write and commit; if the commit fails, the file is reset.

        Args:
            rel: Relative path.
            text: New content.
            message: Commit message.
            extra_paths: Further paths in the commit (e.g. old path for a move).
            as_user: Commit with the user's Git identity.

        Returns:
            Hash of the commit; empty without version control (then only written).

        Raises:
            PkmError: ``commit_failed`` (the file is then back in its old state).
        """
        p = self.vault.path(rel)
        old = p.read_bytes() if p.exists() else None
        self.write_atomic(rel, text)
        sha = ""
        if self.svc.versioning:
            try:
                sha = self.git.commit_paths([rel, *(extra_paths or [])], message, as_user=as_user)
            except PkmError as exc:
                if old is None:
                    p.unlink(missing_ok=True)
                else:
                    p.write_bytes(old)
                raise PkmError("commit_failed", f"Commit failed, file reset. {exc.message}") from exc
        return sha

    def editable_doc(self, target: str) -> Doc:
        """Resolve a target and check whether it may be changed.

        Args:
            target: Path, wikilink or ``id:``.

        Returns:
            The loaded document.

        Raises:
            PkmError: ``forbidden`` outside ``documents/`` and ``scratch/`` or for non-Markdown,
                ``invalid_encoding``/``invalid_frontmatter`` for unreadable files.
        """
        rel = self.svc.resolve(target)
        if not rel.startswith(("documents/", f"{SCRATCH}/")):
            raise PkmError(
                "forbidden", "Only files below documents/ and scratch/ can be changed; wiki/ is read-only from chats.",
                path=rel,
            )
        if not rel.lower().endswith(".md"):
            raise PkmError("forbidden", "Only Markdown files can be changed.", path=rel)
        doc = self.vault.load(rel)
        if doc.error:
            raise PkmError(doc.error, doc.error_message or doc.error, path=rel)
        return doc

    @staticmethod
    def check_hash(doc: Doc, expected_hash: str | None) -> None:
        """Hash protection: ``expected_hash`` must match the current file hash.

        Args:
            doc: Current document.
            expected_hash: Hash from ``read`` or the last write return value.

        Raises:
            PkmError: ``conflict`` with ``current_hash`` if it is missing or differs.
        """
        current = doc.hashes.file_hash if doc.hashes else ""
        if not expected_hash or expected_hash.strip().lower() != current:
            raise PkmError(
                "conflict",
                "The file was changed since it was read (or expected_hash is missing). Please read it again.",
                path=doc.rel, current_hash=current, version=doc.version,
            )

    # Manual state as a version (5.4) ******************************************

    def commit_user_state(self, doc: Doc) -> Doc:
        """If the file differs from the last commit, commit this state as its own version first.

        Args:
            doc: Current document.

        Without version control only a missing ID is assigned (version 1, without commit).

        Returns:
            The (possibly reloaded) document after the commit.
        """
        if not doc.id or (self.svc.versioning and self.git.is_dirty(doc.rel)):
            plan = self._plan_user_version(doc)
            text = set_fields_linewise(doc.text or "", plan.fields) if plan.fields else doc.text or ""
            msg = build_message(doc.title, plan.label, plan.note, plan.doc_id, plan.version, "user")
            self.write_and_commit(doc.rel, text, msg, plan.extra_paths, as_user=True)
            doc = self.vault.load(doc.rel)
        return doc

    def _plan_user_version(self, doc: Doc) -> _UserVersion:
        """Determine version, subject and fields for a manual state.

        Args:
            doc: Current document.

        Returns:
            The plan for the commit.
        """
        if not doc.id:
            doc_id = new_id(self.svc.now(), exists=lambda i: i in self.svc.known_ids())
            plan = _UserVersion(doc_id, 1, "v1", "first version by hand, ID assigned", {"id": doc_id, "version": 1})
        else:
            prev = next((c for c in reversed(self.svc.versions(doc.id)) if c.path), None)
            if prev is None:
                version = doc.version or 1
                plan = _UserVersion(doc.id, version, f"v{version}", "first version by hand")
            else:
                plan = self._plan_from_previous(doc, prev)
            if doc.version != plan.version:
                plan.fields["version"] = plan.version
        return plan

    def _plan_from_previous(self, doc: Doc, prev: Commit) -> _UserVersion:
        """Plan for an already versioned document (change and/or move).

        A pure move without a change of content does not raise the version (16 no. 17).

        Args:
            doc: Current document with ID.
            prev: Last commit of this document.

        Returns:
            The plan for the commit.
        """
        prev_path = prev.path or ""
        prev_doc = load_text_doc(prev_path, self.git.show_file(prev.sha, prev_path))
        moved = prev_path != doc.rel
        same = (
            prev_doc.hashes is not None and doc.hashes is not None
            and prev_doc.hashes.body_hash == doc.hashes.body_hash
            and prev_doc.hashes.meta_hash == doc.hashes.meta_hash
        )
        assert doc.id is not None
        if moved and same:
            plan = _UserVersion(doc.id, prev.version or 1, "moved", f"moved: {prev_path} → {doc.rel}")
        else:
            version = (prev.version or 0) + 1
            note = "change by hand" + (f", moved from {prev_path}" if moved else "")
            plan = _UserVersion(doc.id, version, f"v{version}", note, {"date_updated": self.now_stamp()})
        if moved and not self.vault.exists(prev_path):
            plan.extra_paths.append(prev_path)
        return plan

    # Finishing ****************************************************************

    def finish(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, doc: Doc, new_text: str, note: str, source: str = "chat", extra_paths: list[str] | None = None,
        trailer: str | None = None, check_limit: bool = True,
    ) -> dict[str, Any]:
        """Write the new version as a new version and commit it.

        Args:
            doc: Document before the change.
            new_text: New full text (server fields are set here).
            note: Change note.
            source: ``chat``, ``user`` or ``agent``.
            extra_paths: Further files in the same commit (e.g. new image files).
            trailer: Additional commit line, e.g. ``PKM-Fix: images``.
            check_limit: Check ``PKM_MAX_KB`` (off for pure frontmatter changes and ``fix_images``).

        Returns:
            ``{id, path, status, version, new_hash, commit, diff}``; ``status`` is ``changed``
            or ``unchanged`` (then without commit).

        Raises:
            PkmError: ``too_large`` or errors of the result (e.g. invalid frontmatter).
        """
        old_text = doc.text or ""
        new_text = normalize_text(new_text)
        if new_text == old_text:
            result = {
                "id": doc.id, "path": doc.rel, "status": "unchanged", "version": doc.version,
                "new_hash": doc.hashes.file_hash if doc.hashes else None, "commit": None, "diff": "",
            }
        else:
            version = (doc.version or 0) + 1
            new_text = set_fields_linewise(new_text, {"version": version, "date_updated": self.now_stamp()})
            if check_limit:
                self.check_size(new_text, "The document")
            new_doc = load_text_doc(doc.rel, new_text.encode("utf-8"))
            if new_doc.error:
                raise PkmError(new_doc.error, new_doc.error_message or "Result invalid.")
            msg = build_message(new_doc.title, f"v{version}", note, doc.id or "", version, source)
            msg = msg.rstrip("\n") + f"\n{trailer}\n" if trailer else msg
            sha = self.write_and_commit(doc.rel, new_text, msg, extra_paths)
            result = {
                "id": doc.id, "path": doc.rel, "status": "changed", "version": version,
                "new_hash": new_doc.hashes.file_hash if new_doc.hashes else None, "commit": sha[:10] or None,
                "diff": unified_diff(old_text, new_text, f"v{doc.version}", f"v{version}", DIFF_LINES),
            }
        return result

    def change(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self, target: str, expected_hash: str | None, transform: Callable[[Doc], str], note: str, source: str = "chat",
        images: list[dict[str, Any]] | None = None, fix: dict[str, Any] | None = None, check_limit: bool = True,
    ) -> dict[str, Any]:
        """Common flow of all change tools.

        Args:
            target: Target.
            expected_hash: Hash from ``read``.
            transform: Creates the new full text from the document.
            note: Change note.
            source: ``chat`` or ``user``.
            images: New images for placeholders ``{{image:<name>}}`` in the text (4.9).
            fix: ``fix_images`` and ``image_alt`` for data URIs in the given text (4.9, 7.2).
            check_limit: Check ``PKM_MAX_KB`` (off for pure frontmatter changes).

        Returns:
            Return value of ``finish``, with ``images`` for new images, with ``image_warnings`` for
            nonconforming images in the existing text.
        """
        with self.lock():
            doc = self.editable_doc(target)
            if doc.versioned:
                self.require_git()
            self.check_hash(doc, expected_hash)
            if doc.versioned:
                doc = self.commit_user_state(doc)
            text, files, warnings = docimages.check_text_images(self, doc, transform(doc), fix)
            try:
                text, new_files, infos = docimages.place_images(self, doc, text, images)
                files += new_files
                result = (self.finish(doc, text, note, source, files, check_limit=check_limit) if doc.versioned
                          else self.finish_scratch(doc, text, check_limit=check_limit))
            except PkmError:
                docimages.remove_files(self, files)
                raise
        if infos:
            result["images"] = infos
        if warnings:
            result["image_warnings"] = warnings
        return result

    def finish_scratch(self, doc: Doc, new_text: str, check_limit: bool = True) -> dict[str, Any]:
        """Write a new version of a file in ``scratch/``: without version and without commit.

        ``date_updated`` is only set if the file has a frontmatter.

        Args:
            doc: File before the change.
            new_text: New full text.
            check_limit: Check ``PKM_MAX_KB``.

        Returns:
            ``{path, status, new_hash, diff}``; ``status`` is ``changed`` or ``unchanged``.

        Raises:
            PkmError: ``too_large`` or errors of the result.
        """
        old_text = doc.text or ""
        new_text = normalize_text(new_text)
        result: dict[str, Any] = {"path": doc.rel, "status": "unchanged",
                                  "new_hash": doc.hashes.file_hash if doc.hashes else None, "diff": ""}
        if new_text != old_text:
            new_doc = load_text_doc(doc.rel, new_text.encode("utf-8"))
            if new_doc.parsed is not None and new_doc.parsed.has_frontmatter and not new_doc.error:
                new_text = set_fields_linewise(new_text, {"date_updated": self.now_stamp()})
                new_doc = load_text_doc(doc.rel, new_text.encode("utf-8"))
            if new_doc.error:
                raise PkmError(new_doc.error, new_doc.error_message or "Result invalid.")
            if check_limit:
                self.check_size(new_text, "The file")
            self.write_atomic(doc.rel, new_text)
            result = {
                "path": doc.rel, "status": "changed",
                "new_hash": new_doc.hashes.file_hash if new_doc.hashes else None,
                "diff": unified_diff(old_text, new_text, "before", "after", DIFF_LINES),
            }
        return result

    # Tools ********************************************************************

    def create_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        short_citation: str | None = None,
        date_document: str | None = None,
        context: str | None = None,
        related: list[str] | None = None,
        kind: str | None = None,
        toolchain: str | None = None,
        note: str | None = None,
        area: str = "documents",
        folder: str | None = None,
        images: list[dict[str, Any]] | None = None,
        fix_images: bool = False,
        image_alt: dict[str, str] | None = None,
        confirm_large: bool = False,
    ) -> dict[str, Any]:
        """Tool ``create_document``: new document in ``documents/_inbox/`` (version 1) or note in ``scratch/``.

        Args:
            title: Title; the file name is derived from it as well.
            content: Content without frontmatter (a supplied one is removed).
            tags: Tags (lower case, hyphens).
            short_citation: Short citation, e.g. ``EN 61000-4-6:2014``.
            date_document: Issue date as printed.
            context: Occasion, e.g. chat title.
            related: Related documents (path, wikilink or ID).
            kind: ``note`` (default), ``standard``, ``regulation`` or ``correction``.
            toolchain: Becomes ``toolchain_markdown``; ``pkm-mcp`` if omitted.
            note: Change note for the commit.
            area: ``documents`` (default) or ``scratch``.
            folder: Only for ``scratch``: subfolder in ``scratch/``.
            images: Images for placeholders ``{{image:<name>}}`` in the content (4.9).
            fix_images: Fix nonconforming data URIs in the text after confirmation (4.9).
            image_alt: Alt texts per image name for ``missing_alt``.
            confirm_large: Text larger than ``PKM_MAX_KB`` confirmed by the user.

        Returns:
            ``{id, path, status: created, version: 1, new_hash, commit, diff}``; for ``scratch``
            ``{path, status: created, new_hash, diff}``.

        Raises:
            PkmError: ``invalid_argument``, ``too_large``, ``not_found`` (``related``) or
                ``git_unavailable``.
        """
        title = " ".join((title or "").split())
        _check_create_args(title, area, folder, kind)
        body = strip_frontmatter(normalize_fragment(content or ""))
        self.check_size(body, "The content", confirm_large)
        values = {
            "title": title,
            "short_citation": " ".join(short_citation.split()) if short_citation else None,
            "date_document": date_document.strip() if date_document else None,
            "context": " ".join(context.split()) if context else None,
            "tags": normalize_tags(tags) if tags else None,
            "related": [f"[[{self._link_target(r)}]]" for r in related] if related else None,
            "kind": kind,
        }
        if area != SCRATCH:
            values["kind"] = kind or DEFAULT_KIND
            values["toolchain_markdown"] = " ".join(toolchain.split()) if toolchain else DEFAULT_TOOLCHAIN
        fix = {"fix_images": fix_images, "image_alt": image_alt}
        return (self._write_scratch(body, _scratch_folder(folder), values, (images, fix)) if area == SCRATCH
                else self._write_new(body, note or "created", values, (images, fix)))

    def _write_new(  # pylint: disable=too-many-locals
        self, body: str, note: str, values: dict[str, Any], images: tuple[Any, Any] = (None, None)
    ) -> dict[str, Any]:
        """Write a new document with ``date_markdown``, ID and version 1 and commit it.

        Args:
            body: Content without frontmatter.
            note: Change note.
            values: Frontmatter fields from the call (``title`` … ``kind``).
            images: New images (4.9) and ``fix`` settings for data URIs in the text.

        Returns:
            Return value of ``_created_result``.
        """
        title = values["title"]
        with self.lock():
            self.require_git()
            now = self.svc.now()
            doc_id = new_id(now, exists=lambda i: i in self.svc.known_ids())
            meta = _ordered_meta({**values, "date_markdown": stamp(now), "id": doc_id, "version": 1})
            text = normalize_text(dump_meta(meta) + "\n" + body.lstrip("\n"))
            rel = self._free_inbox_name(now.date().isoformat(), title)
            empty = load_text_doc(rel, b"")
            text, files, _ = docimages.check_text_images(self, empty, text, images[1])
            try:
                text, new_files, infos = docimages.place_images(self, empty, text, images[0])
                files += new_files
                sha = self.write_and_commit(rel, text, build_message(title, "v1", note, doc_id, 1, "chat"), files)
            except PkmError:
                docimages.remove_files(self, files)
                raise
        result = self._created_result(doc_id, rel, text, sha)
        if infos:
            result["images"] = infos
        return result

    def _created_result(self, doc_id: str, rel: str, text: str, sha: str) -> dict[str, Any]:
        """Build the return value of ``create_document``.

        Args:
            doc_id: New ID.
            rel: Path of the new file.
            text: Written text.
            sha: Commit hash.

        Returns:
            ``{id, path, status: created, version: 1, new_hash, commit, diff}``.
        """
        doc = self.vault.load(rel)
        return {
            "id": doc_id, "path": rel, "status": "created", "version": 1,
            "new_hash": doc.hashes.file_hash if doc.hashes else None, "commit": sha[:10] or None,
            "diff": unified_diff("", text, "/dev/null", rel, DIFF_LINES),
        }

    def _write_scratch(
        self, body: str, folder: str, values: dict[str, Any], images: tuple[Any, Any] = (None, None)
    ) -> dict[str, Any]:
        """Create a note in ``scratch/``: small frontmatter, without ID, version and commit.

        Args:
            body: Content without frontmatter.
            folder: Checked subfolder (relative to ``scratch/``, possibly empty).
            values: Frontmatter fields from the call (empty values are dropped).
            images: New images (always embedded in ``scratch/``) and ``fix`` settings.

        Returns:
            ``{path, status: created, new_hash, diff}``.
        """
        with self.lock():
            meta = _ordered_meta({**values, "date_markdown": self.now_stamp()})
            text = normalize_text(dump_meta(meta) + "\n" + body.lstrip("\n"))
            base = "/".join(p for p in (SCRATCH, folder) if p)
            rel = self.free_name(base, slug_words(values["title"], self.cfg.slug_max))
            empty = load_text_doc(rel, b"")
            text, _, _ = docimages.check_text_images(self, empty, text, images[1])
            text, _, infos = docimages.place_images(self, empty, text, images[0])
            self.write_atomic(rel, text)
        doc = self.vault.load(rel)
        result = {"path": rel, "status": "created", "new_hash": doc.hashes.file_hash if doc.hashes else None,
                  "diff": unified_diff("", text, "/dev/null", rel, DIFF_LINES)}
        if infos:
            result["images"] = infos
        return result

    def free_name(self, base_dir: str, stem: str, tail: str = "", ext: str = ".md") -> str:
        """Find a free file name ``<stem><tail>.md`` in a folder (never overwrite).

        Args:
            base_dir: Folder relative to the vault.
            stem: Desired file name without extension.
            tail: Fixed end of the name (e.g. ``_2026-11-03``); the suffix goes before it.
            ext: File extension.

        Returns:
            Relative path; for equal names with suffix ``-2``, ``-3`` … before ``tail``. The name has
            at most ``MAX_NAME`` characters; only ``stem`` is shortened, never the suffix, ``tail`` or extension.
        """
        area = base_dir.split("/", 1)[0]
        existing = {r.casefold() for r in self.vault.iter_files((area,))}
        n = 1
        rel = f"{base_dir}/{fit_stem(stem, tail + ext)}{tail}{ext}"
        while rel.casefold() in existing or self.vault.path(rel).exists():
            n += 1
            rel = f"{base_dir}/{fit_stem(stem, f'-{n}{tail}{ext}')}-{n}{tail}{ext}"
        return rel

    def _link_target(self, target: str) -> str:
        """Target for ``related`` as a wikilink path.

        Args:
            target: Path, wikilink or ID.

        Returns:
            Path without ``.md``.
        """
        rel = self.svc.resolve(target)
        return rel[:-3] if rel.lower().endswith(".md") else rel

    def _free_inbox_name(self, date: str, title: str) -> str:
        """Find a free file name ``<slug>_YYYY-MM-DD.md`` in the inbox (never overwrite).

        Args:
            date: Date ``YYYY-MM-DD``.
            title: Title.

        Returns:
            Relative path; for equal names with a suffix before the date (``<slug>-2_YYYY-MM-DD.md``).
        """
        return self.free_name(INBOX, slug_words(title, self.cfg.slug_max), f"_{date}")

    def rewrite_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, target: str, content: str, expected_hash: str | None, note: str | None = None,
        confirm_shortening: bool = False, images: list[dict[str, Any]] | None = None, fix_images: bool = False,
        image_alt: dict[str, str] | None = None, confirm_large: bool = False,
    ) -> dict[str, Any]:
        """Tool ``rewrite_document``: replace the entire content below the frontmatter.

        Args:
            target: Target.
            content: New content without frontmatter.
            expected_hash: Hash from ``read``.
            note: Change note.
            confirm_shortening: Confirm a clear shortening, missing sections or removed images.
            images: New images for placeholders ``{{image:<name>}}`` (4.9).
            fix_images: Fix nonconforming data URIs in the text after confirmation (4.9).
            image_alt: Alt texts per image name for ``missing_alt``.
            confirm_large: Text larger than ``PKM_MAX_KB`` confirmed by the user.

        Returns:
            Return value of ``finish``.

        Raises:
            PkmError: ``large_shortening`` with ``missing_sections`` or ``removed_images`` if the content
                is shorter than 60 %, sections or images are missing and it was not confirmed;
                ``unknown_image`` for unknown placeholders.
        """
        new_body = normalize_text(strip_frontmatter(normalize_fragment(content or "")))
        self.check_size(new_body, "The content", confirm_large)

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            body = docimages.restore_body(doc.parsed.body, new_body)
            check_shortening(doc, body, confirm_shortening)
            fm = doc.parsed.frontmatter_text
            return fm + ("\n" if fm else "") + body.lstrip("\n")

        return self.change(target, expected_hash, transform, note or "rewritten", images=images,
                           fix={"fix_images": fix_images, "image_alt": image_alt}, check_limit=not confirm_large)

    def append_to_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, target: str, text: str, expected_hash: str | None, section: str | None = None, note: str | None = None,
        images: list[dict[str, Any]] | None = None, fix_images: bool = False, image_alt: dict[str, str] | None = None,
        confirm_large: bool = False,
    ) -> dict[str, Any]:
        """Tool ``append_to_document``.

        Args:
            target: Target.
            text: Markdown text to insert.
            expected_hash: Hash from ``read``.
            section: Section key (also ``_preamble`` or with suffix); a missing section is created
                as level 2; without it the text is appended at the end of the file.
            note: Change note.
            images: New images for placeholders ``{{image:<name>}}`` (4.9).
            fix_images: Fix nonconforming data URIs in the text after confirmation (4.9).
            image_alt: Alt texts per image name for ``missing_alt``.
            confirm_large: Text larger than ``PKM_MAX_KB`` confirmed by the user.

        Returns:
            Return value of ``finish``.

        Raises:
            PkmError: ``invalid_argument`` for an empty text, ``ambiguous`` for duplicate headings.
        """
        block = normalize_fragment(text or "").strip("\n").split("\n")
        if not "".join(block).strip():
            raise PkmError("invalid_argument", "text is empty.")
        self.check_size("\n".join(block), "The text", confirm_large)

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            return doc.parsed.frontmatter_text + "\n".join(append_lines(doc.parsed, block, section)) + "\n"

        default = f"appended: {section}" if section else "appended at the end"
        return self.change(target, expected_hash, transform, note or default, images=images,
                           fix={"fix_images": fix_images, "image_alt": image_alt}, check_limit=not confirm_large)

    def edit_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, target: str, old: str, new: str, expected_hash: str | None, note: str | None = None,
        images: list[dict[str, Any]] | None = None, confirm_shortening: bool = False, fix_images: bool = False,
        image_alt: dict[str, str] | None = None, confirm_large: bool = False,
    ) -> dict[str, Any]:
        """Tool ``edit_document``: replace a passage.

        Args:
            target: Target.
            old: Passage that must occur exactly once in the body.
            new: Replacement (may be empty).
            expected_hash: Hash from ``read``.
            note: Change note.
            images: New images for placeholders ``{{image:<name>}}`` (4.9).
            confirm_shortening: Confirm the removal of images.
            fix_images: Fix nonconforming data URIs in the text after confirmation (4.9).
            image_alt: Alt texts per image name for ``missing_alt``.
            confirm_large: Text larger than ``PKM_MAX_KB`` confirmed by the user.

        Returns:
            Return value of ``finish``.

        Raises:
            PkmError: ``invalid_argument`` for an empty ``old``, ``not_found`` or ``ambiguous``,
                ``large_shortening`` for removed images without confirmation.
        """
        old_n = normalize_fragment(old or "")
        new_n = normalize_fragment(new or "")
        if not old_n:
            raise PkmError("invalid_argument", "old is empty.")
        self.check_size(new_n, "The text", confirm_large)

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            body = doc.parsed.body
            new_body = docimages.edit_view(body, old_n, new_n)
            removed = docimages.removed_images(body, new_body)
            if removed and not confirm_shortening:
                raise PkmError("large_shortening", "The change removes images. Please have the user confirm it "
                               "and call again with confirm_shortening=true.", removed_images=removed, path=doc.rel)
            return doc.parsed.frontmatter_text + new_body

        return self.change(target, expected_hash, transform, note or "passage changed", images=images,
                           fix={"fix_images": fix_images, "image_alt": image_alt}, check_limit=not confirm_large)

    def add_image(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, target: str, expected_hash: str | None, image: dict[str, Any], section: str | None = None,
        caption: str | None = None, note: str | None = None,
    ) -> dict[str, Any]:
        """Tool ``add_image``: insert an image at the end of a section or of the document (4.9).

        Args:
            target: Target.
            expected_hash: Hash from ``read``.
            image: Image specification as for ``images``.
            section: Section at whose end the image is inserted; at the end of the file if omitted.
            caption: Caption (one line below the image).
            note: Change note.

        Returns:
            Like ``append_to_document``, with ``images``.
        """
        name = str((image or {}).get("name") or "")
        block = f"{{{{image:{name}}}}}" + (f"\n{' '.join(caption.split())}" if caption and caption.strip() else "")
        return self.append_to_document(target, block, expected_hash, section, note or f"image added: {name}",
                                       images=[image])

    def update_frontmatter(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        target: str,
        expected_hash: str | None,
        set: dict[str, Any] | None = None,  # pylint: disable=redefined-builtin
        add: dict[str, Any] | None = None,
        remove: list[str] | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Tool ``update_frontmatter``.

        Args:
            target: Target.
            expected_hash: Hash from ``read``.
            set: Set or overwrite fields (parameter name per specification 7.2).
            add: Append to list fields, without duplicates.
            remove: Remove fields.
            note: Change note.

        Returns:
            Return value of ``finish``.

        Raises:
            PkmError: ``invalid_argument`` without a change, ``protected_field`` for protected fields.
        """
        set_fields = dict(set or {})
        add_fields = dict(add or {})
        remove_fields = list(remove or [])
        touched = [*set_fields, *add_fields, *remove_fields]
        if not touched:
            raise PkmError("invalid_argument", "No change given (set, add or remove).")
        bad = [k for k in touched if k in PROTECTED]
        if bad:
            raise PkmError("protected_field", f"Protected fields: {', '.join(bad)}", fields=bad)

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            meta = order_meta(_updated_meta(doc.meta, set_fields, add_fields, remove_fields))
            return dump_meta(meta) + doc.parsed.body

        default = f"metadata: {', '.join(dict.fromkeys(touched))}"
        return self.change(target, expected_hash, transform, note or default, check_limit=False)

    def restore_document(
        self, target: str, version: int, expected_hash: str | None, source: str = "chat"
    ) -> dict[str, Any]:
        """Tool ``restore_document``: content of an earlier version as a new version.

        Args:
            target: Target.
            version: Version to restore.
            expected_hash: Hash from ``read``.
            source: ``chat`` (MCP) or ``user`` (CLI).

        Returns:
            Return value of ``finish`` with the note ``restored from v<n>``.

        Raises:
            PkmError: ``not_versioned`` for files in ``scratch/``.
        """
        if not self.svc.versioning:
            raise PkmError("not_versioned", NO_VERSIONING, target=target)
        if not self.vault.load(self.svc.resolve(target)).versioned:
            raise PkmError("not_versioned", "Files in scratch/ have no versions.", target=target)

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None and doc.id
            _, old_text = self.svc.text_at_version(doc.id, int(version))
            old = load_text_doc(doc.rel, old_text.encode("utf-8"))
            if old.parsed is None:
                raise PkmError("invalid_encoding", f"Version {version} is not readable.")
            return doc.parsed.frontmatter_text + old.parsed.body

        return self.change(target, expected_hash, transform, f"restored from v{int(version)}", source)

# Functions *******************************************************************


def _scratch_folder(folder: str | None) -> str:
    """Check a subfolder for ``scratch/``.

    Args:
        folder: Given subfolder (``/`` as separator) or ``None``.

    Returns:
        Cleaned relative subfolder (empty for the root of ``scratch/``).

    Raises:
        PkmError: ``invalid_path`` for ``..``, absolute or not platform-safe names.
    """
    parts = [p for p in (folder or "").replace("\\", "/").strip().strip("/").split("/") if p]
    if (folder or "").strip().startswith(("/", "\\")) or any(p == ".." or not is_platform_safe_name(p) for p in parts):
        raise PkmError("invalid_path", f"Invalid folder: {folder}", folder=folder)
    return "/".join(parts)


def _ordered_meta(values: dict[str, Any]) -> dict[str, Any]:
    """Frontmatter of a new document in the order of 4.1; empty values are dropped.

    Args:
        values: Field values.

    Returns:
        The fields in the order of ``FIELD_ORDER``.
    """
    return {k: values[k] for k in FIELD_ORDER if values.get(k) not in (None, "", [])}


def _check_create_args(title: str, area: str, folder: str | None, kind: str | None) -> None:
    """Check the parameters of ``create_document``.

    Args:
        title: Cleaned title.
        area: Target area.
        folder: Subfolder (only for ``scratch``).
        kind: Kind of the document or ``None``.

    Raises:
        PkmError: ``invalid_argument`` for a missing title, an unknown area or ``kind``.
    """
    if not title:
        raise PkmError("invalid_argument", "title is missing.")
    if area not in CREATE_AREAS:
        raise PkmError("invalid_argument", "area must be documents or scratch.")
    if folder and area != SCRATCH:
        raise PkmError("invalid_argument", "folder only exists for area scratch.")
    if kind is not None and kind not in KINDS:
        raise PkmError("invalid_argument", f"kind must be one of {', '.join(KINDS)}.")


def _updated_meta(
    meta: dict[str, Any], set_fields: dict[str, Any], add_fields: dict[str, Any], remove_fields: list[str]
) -> dict[str, Any]:
    """Compute the frontmatter fields after ``update_frontmatter``.

    Args:
        meta: Previous fields.
        set_fields: Fields to set.
        add_fields: Values to append to lists.
        remove_fields: Fields to remove.

    Returns:
        New fields (order is kept).

    Raises:
        PkmError: ``invalid_argument`` if appending to a field that is not a list.
    """
    result = dict(meta)
    result.update(set_fields)
    for key, values in add_fields.items():
        values = values if isinstance(values, list) else [values]
        current = result.get(key)
        current = [] if current is None else current
        if not isinstance(current, list):
            raise PkmError("invalid_argument", f"Field {key} is not a list.", field=key)
        result[key] = current + [v for v in values if v not in current]
    for key in remove_fields:
        result.pop(key, None)
    return result

# Main ************************************************************************
