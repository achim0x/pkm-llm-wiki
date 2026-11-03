"""Schreibende Operationen (Spezifikation 5.4, 6, 7.2).

Ablauf jeder Änderung: Git prüfen → Ziel prüfen → Hash-Schutz → Stand von Hand ggf. als
eigene Version committen → Änderung anwenden → Version +1, ``updated`` → atomar schreiben →
Commit nur dieser Datei → bei Fehler Datei zurücksetzen.

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
from .errors import PkmError
from .frontmatter import PROTECTED, dump_meta, set_fields_linewise
from .fsutil import file_lock, replace_file
from .gitlayer import Commit, build_message
from .ids import new_id
from .normalize import encode, normalize_fragment, normalize_text
from .parse import split_sections, strip_frontmatter
from .paths import MAX_NAME, fit_stem, is_platform_safe_name, slugify
from .schema import DEFAULT_KIND, DEFAULT_TOOLCHAIN, FIELD_ORDER, KINDS, normalize_tags, order_meta, stamp
from .vault import SCRATCH, Doc, load_text_doc

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

INBOX = "documents/_inbox"
CREATE_AREAS = ("documents", SCRATCH)
DIFF_LINES = 80
SHORTENING_RATIO = 0.6
FILE_MODE_MASK = 0o777

# Classes *********************************************************************


@dataclass
class _UserVersion:
    """Plan für das Committen eines von Hand geänderten Stands.

    Attributes:
        doc_id: Dokument-ID (ggf. neu vergeben).
        version: Versionsnummer des Commits.
        label: Zusatz im Betreff (``v<n>`` oder ``moved``).
        note: Änderungsnotiz.
        fields: Frontmatter-Felder, die vorher zu setzen sind.
        extra_paths: Weitere Pfade im Commit (alter Pfad bei Verschiebung).
    """

    doc_id: str
    version: int
    label: str
    note: str
    fields: dict[str, Any] = field(default_factory=dict)
    extra_paths: list[str] = field(default_factory=list)


class Writer:
    """Alle schreibenden Vorgänge auf Dokumenten (MCP-Tools und CLI)."""

    def __init__(self, svc: Service) -> None:
        """Writer anlegen.

        Args:
            svc: Dienst mit Konfiguration, Vault und Git.
        """
        self.svc = svc
        self.cfg = svc.cfg
        self.git = svc.git
        self.vault = svc.vault

    # Grundlagen ***************************************************************

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        """Schreibvorgänge von MCP und CLI über eine Sperrdatei serialisieren.

        Yields:
            Nichts; die Sperre gilt innerhalb des ``with``-Blocks.
        """
        if not self.cfg.git_dir.is_dir():
            yield
        else:
            with file_lock(self.cfg.git_dir / "pkm.lock"):
                yield

    def now_stamp(self) -> str:
        """Aktuelle Zeit für Datumsfelder: Ortszeit ohne Zeitzone (4.1).

        Returns:
            Zeitstempel, z. B. ``2026-11-02T19:05:00``.
        """
        return stamp(self.svc.now())

    def check_size(self, text: str, what: str) -> None:
        """Größengrenze ``PKM_MAX_KB`` prüfen.

        Args:
            text: Zu prüfender Text.
            what: Bezeichnung für die Fehlermeldung.

        Raises:
            PkmError: ``too_large``, wenn der Text größer ist.
        """
        if len(text.encode("utf-8")) > self.cfg.max_bytes:
            raise PkmError("too_large", f"{what} ist größer als {self.cfg.max_kb} KB (PKM_MAX_KB).")

    def write_atomic(self, rel: str, text: str) -> None:
        """Datei atomar schreiben (temporäre Datei, dann umbenennen), Dateirechte erhalten.

        Args:
            rel: Relativer Pfad.
            text: Inhalt; wird in die Schreibform gebracht.
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
        """Schreiben und committen; schlägt der Commit fehl, wird die Datei zurückgesetzt.

        Args:
            rel: Relativer Pfad.
            text: Neuer Inhalt.
            message: Commit-Nachricht.
            extra_paths: Weitere Pfade im Commit (z. B. alter Pfad bei Verschiebung).
            as_user: Mit der Git-Identität des Nutzers committen.

        Returns:
            Hash des Commits.

        Raises:
            PkmError: ``commit_failed`` (die Datei ist dann wieder im alten Zustand).
        """
        p = self.vault.path(rel)
        old = p.read_bytes() if p.exists() else None
        self.write_atomic(rel, text)
        try:
            sha = self.git.commit_paths([rel, *(extra_paths or [])], message, as_user=as_user)
        except PkmError as exc:
            if old is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(old)
            raise PkmError("commit_failed", f"Commit fehlgeschlagen, Datei zurückgesetzt. {exc.message}") from exc
        return sha

    def editable_doc(self, target: str) -> Doc:
        """Ziel auflösen und prüfen, ob es geändert werden darf.

        Args:
            target: Pfad, Wikilink oder ``id:``.

        Returns:
            Das geladene Dokument.

        Raises:
            PkmError: ``forbidden`` außerhalb von ``documents/`` und ``scratch/`` oder bei Nicht-Markdown,
                ``invalid_encoding``/``invalid_frontmatter`` bei unlesbaren Dateien.
        """
        rel = self.svc.resolve(target)
        if not rel.startswith(("documents/", f"{SCRATCH}/")):
            raise PkmError(
                "forbidden", "Nur Dateien unter documents/ und scratch/ sind änderbar; wiki/ ist aus Chats nur lesbar.",
                path=rel,
            )
        if not rel.lower().endswith(".md"):
            raise PkmError("forbidden", "Nur Markdown-Dateien sind änderbar.", path=rel)
        doc = self.vault.load(rel)
        if doc.error:
            raise PkmError(doc.error, doc.error_message or doc.error, path=rel)
        return doc

    @staticmethod
    def check_hash(doc: Doc, expected_hash: str | None) -> None:
        """Hash-Schutz: ``expected_hash`` muss zum aktuellen Datei-Hash passen.

        Args:
            doc: Aktuelles Dokument.
            expected_hash: Hash aus ``read`` oder der letzten Schreib-Rückgabe.

        Raises:
            PkmError: ``conflict`` mit ``current_hash``, wenn er fehlt oder abweicht.
        """
        current = doc.hashes.file_hash if doc.hashes else ""
        if not expected_hash or expected_hash.strip().lower() != current:
            raise PkmError(
                "conflict",
                "Die Datei wurde seit dem Lesen geändert (oder expected_hash fehlt). Bitte neu lesen.",
                path=doc.rel, current_hash=current, version=doc.version,
            )

    # Stand von Hand als Version (5.4) *****************************************

    def commit_user_state(self, doc: Doc) -> Doc:
        """Weicht die Datei vom letzten Commit ab, diesen Stand vorher als eigene Version committen.

        Args:
            doc: Aktuelles Dokument.

        Returns:
            Das (ggf. neu geladene) Dokument nach dem Commit.
        """
        if not doc.id or self.git.is_dirty(doc.rel):
            plan = self._plan_user_version(doc)
            text = set_fields_linewise(doc.text or "", plan.fields) if plan.fields else doc.text or ""
            msg = build_message(doc.title, plan.label, plan.note, plan.doc_id, plan.version, "user")
            self.write_and_commit(doc.rel, text, msg, plan.extra_paths, as_user=True)
            doc = self.vault.load(doc.rel)
        return doc

    def _plan_user_version(self, doc: Doc) -> _UserVersion:
        """Version, Betreff und Felder für einen Stand von Hand bestimmen.

        Args:
            doc: Aktuelles Dokument.

        Returns:
            Der Plan für den Commit.
        """
        if not doc.id:
            doc_id = new_id(self.svc.now(), exists=lambda i: i in self.svc.known_ids())
            plan = _UserVersion(doc_id, 1, "v1", "Erstfassung von Hand, ID vergeben", {"id": doc_id, "version": 1})
        else:
            prev = next((c for c in reversed(self.svc.versions(doc.id)) if c.path), None)
            if prev is None:
                version = doc.version or 1
                plan = _UserVersion(doc.id, version, f"v{version}", "Erstfassung von Hand")
            else:
                plan = self._plan_from_previous(doc, prev)
            if doc.version != plan.version:
                plan.fields["version"] = plan.version
        return plan

    def _plan_from_previous(self, doc: Doc, prev: Commit) -> _UserVersion:
        """Plan für ein schon versioniertes Dokument (Änderung und/oder Verschiebung).

        Reines Verschieben ohne inhaltliche Änderung erhöht die Version nicht (16 Nr. 17).

        Args:
            doc: Aktuelles Dokument mit ID.
            prev: Letzter Commit dieses Dokuments.

        Returns:
            Der Plan für den Commit.
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
            plan = _UserVersion(doc.id, prev.version or 1, "moved", f"verschoben: {prev_path} → {doc.rel}")
        else:
            version = (prev.version or 0) + 1
            note = "Änderung von Hand" + (f", verschoben von {prev_path}" if moved else "")
            plan = _UserVersion(doc.id, version, f"v{version}", note, {"date_updated": self.now_stamp()})
        if moved and not self.vault.exists(prev_path):
            plan.extra_paths.append(prev_path)
        return plan

    # Abschluss ****************************************************************

    def finish(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, doc: Doc, new_text: str, note: str, source: str = "chat", extra_paths: list[str] | None = None
    ) -> dict[str, Any]:
        """Neue Fassung als neue Version schreiben und committen.

        Args:
            doc: Dokument vor der Änderung.
            new_text: Neuer Gesamttext (Serverfelder werden hier gesetzt).
            note: Änderungsnotiz.
            source: ``chat``, ``user`` oder ``agent``.
            extra_paths: Weitere Dateien im selben Commit (z. B. neue Bilddateien).

        Returns:
            ``{id, path, status, version, new_hash, commit, diff}``; ``status`` ist ``changed``
            oder ``unchanged`` (dann ohne Commit).

        Raises:
            PkmError: ``too_large`` oder Fehler des Ergebnisses (z. B. ungültiges Frontmatter).
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
            self.check_size(new_text, "Das Dokument")
            new_doc = load_text_doc(doc.rel, new_text.encode("utf-8"))
            if new_doc.error:
                raise PkmError(new_doc.error, new_doc.error_message or "Ergebnis ungültig.")
            msg = build_message(new_doc.title, f"v{version}", note, doc.id or "", version, source)
            sha = self.write_and_commit(doc.rel, new_text, msg, extra_paths)
            result = {
                "id": doc.id, "path": doc.rel, "status": "changed", "version": version,
                "new_hash": new_doc.hashes.file_hash if new_doc.hashes else None, "commit": sha[:10],
                "diff": unified_diff(old_text, new_text, f"v{doc.version}", f"v{version}", DIFF_LINES),
            }
        return result

    def change(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, target: str, expected_hash: str | None, transform: Callable[[Doc], str], note: str, source: str = "chat",
        images: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Gemeinsamer Ablauf aller Änderungs-Tools.

        Args:
            target: Ziel.
            expected_hash: Hash aus ``read``.
            transform: Erzeugt aus dem Dokument den neuen Gesamttext.
            note: Änderungsnotiz.
            source: ``chat`` oder ``user``.
            images: Neue Bilder zu Platzhaltern ``{{image:<name>}}`` im Text (4.9).

        Returns:
            Rückgabe von ``finish``, bei neuen Bildern mit ``images``.
        """
        with self.lock():
            doc = self.editable_doc(target)
            if doc.versioned:
                self.git.require_ok()
            self.check_hash(doc, expected_hash)
            if doc.versioned:
                doc = self.commit_user_state(doc)
            text, files, infos = docimages.place_images(self, doc, transform(doc), images)
            try:
                result = (self.finish(doc, text, note, source, files) if doc.versioned
                          else self.finish_scratch(doc, text))
            except PkmError:
                docimages.remove_files(self, files)
                raise
        if infos:
            result["images"] = infos
        return result

    def finish_scratch(self, doc: Doc, new_text: str) -> dict[str, Any]:
        """Neue Fassung einer Datei in ``scratch/`` schreiben: ohne Version und ohne Commit.

        ``date_updated`` wird nur gesetzt, wenn die Datei ein Frontmatter hat.

        Args:
            doc: Datei vor der Änderung.
            new_text: Neuer Gesamttext.

        Returns:
            ``{path, status, new_hash, diff}``; ``status`` ist ``changed`` oder ``unchanged``.

        Raises:
            PkmError: ``too_large`` oder Fehler des Ergebnisses.
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
                raise PkmError(new_doc.error, new_doc.error_message or "Ergebnis ungültig.")
            self.check_size(new_text, "Die Datei")
            self.write_atomic(doc.rel, new_text)
            result = {
                "path": doc.rel, "status": "changed",
                "new_hash": new_doc.hashes.file_hash if new_doc.hashes else None,
                "diff": unified_diff(old_text, new_text, "vorher", "nachher", DIFF_LINES),
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
    ) -> dict[str, Any]:
        """Tool ``create_document``: neues Dokument in ``documents/_inbox/`` (Version 1) oder Notiz in ``scratch/``.

        Args:
            title: Titel; daraus wird auch der Dateiname gebildet.
            content: Inhalt ohne Frontmatter (ein mitgeliefertes wird entfernt).
            tags: Schlagwörter (Kleinbuchstaben, Bindestrich).
            short_citation: Kurzbezeichnung, z. B. ``EN 61000-4-6:2014``.
            date_document: Ausgabedatum wie gedruckt.
            context: Anlass, z. B. Chat-Titel.
            related: Verwandte Dokumente (Pfad, Wikilink oder ID).
            kind: ``note`` (Standard), ``standard``, ``regulation`` oder ``correction``.
            toolchain: Wird zu ``toolchain_markdown``; ohne Angabe ``pkm-mcp``.
            note: Änderungsnotiz für den Commit.
            area: ``documents`` (Standard) oder ``scratch``.
            folder: Nur bei ``scratch``: Unterordner in ``scratch/``.
            images: Bilder zu Platzhaltern ``{{image:<name>}}`` im Inhalt (4.9).

        Returns:
            ``{id, path, status: created, version: 1, new_hash, commit, diff}``; bei ``scratch``
            ``{path, status: created, new_hash, diff}``.

        Raises:
            PkmError: ``invalid_argument``, ``too_large``, ``not_found`` (``related``) oder
                ``git_unavailable``.
        """
        title = " ".join((title or "").split())
        _check_create_args(title, area, folder, kind)
        body = strip_frontmatter(normalize_fragment(content or ""))
        self.check_size(body, "Der Inhalt")
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
        return (self._write_scratch(body, _scratch_folder(folder), values, images) if area == SCRATCH
                else self._write_new(body, note or "neu angelegt", values, images))

    def _write_new(
        self, body: str, note: str, values: dict[str, Any], images: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Neues Dokument mit ``date_markdown``, ID und Version 1 schreiben und committen.

        Args:
            body: Inhalt ohne Frontmatter.
            note: Änderungsnotiz.
            values: Frontmatter-Felder aus dem Aufruf (``title`` … ``kind``).
            images: Neue Bilder (4.9).

        Returns:
            Rückgabe von ``_created_result``.
        """
        title = values["title"]
        with self.lock():
            self.git.require_ok()
            now = self.svc.now()
            doc_id = new_id(now, exists=lambda i: i in self.svc.known_ids())
            meta = _ordered_meta({**values, "date_markdown": stamp(now), "id": doc_id, "version": 1})
            text = normalize_text(dump_meta(meta) + "\n" + body.lstrip("\n"))
            rel = self._free_inbox_name(now.date().isoformat(), title)
            text, files, infos = docimages.place_images(self, load_text_doc(rel, b""), text, images)
            try:
                sha = self.write_and_commit(rel, text, build_message(title, "v1", note, doc_id, 1, "chat"), files)
            except PkmError:
                docimages.remove_files(self, files)
                raise
        result = self._created_result(doc_id, rel, text, sha)
        if infos:
            result["images"] = infos
        return result

    def _created_result(self, doc_id: str, rel: str, text: str, sha: str) -> dict[str, Any]:
        """Rückgabe von ``create_document`` bilden.

        Args:
            doc_id: Neue ID.
            rel: Pfad der neuen Datei.
            text: Geschriebener Text.
            sha: Commit-Hash.

        Returns:
            ``{id, path, status: created, version: 1, new_hash, commit, diff}``.
        """
        doc = self.vault.load(rel)
        return {
            "id": doc_id, "path": rel, "status": "created", "version": 1,
            "new_hash": doc.hashes.file_hash if doc.hashes else None, "commit": sha[:10],
            "diff": unified_diff("", text, "/dev/null", rel, DIFF_LINES),
        }

    def _write_scratch(
        self, body: str, folder: str, values: dict[str, Any], images: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Notiz in ``scratch/`` anlegen: kleines Frontmatter, ohne ID, Version und Commit.

        Args:
            body: Inhalt ohne Frontmatter.
            folder: Geprüfter Unterordner (relativ zu ``scratch/``, ggf. leer).
            values: Frontmatter-Felder aus dem Aufruf (leere Werte entfallen).
            images: Neue Bilder (in ``scratch/`` immer eingebettet).

        Returns:
            ``{path, status: created, new_hash, diff}``.
        """
        with self.lock():
            meta = _ordered_meta({**values, "date_markdown": self.now_stamp()})
            text = normalize_text(dump_meta(meta) + "\n" + body.lstrip("\n"))
            base = "/".join(p for p in (SCRATCH, folder) if p)
            rel = self.free_name(base, slugify(values["title"], MAX_NAME))
            text, _, infos = docimages.place_images(self, load_text_doc(rel, b""), text, images)
            self.write_atomic(rel, text)
        doc = self.vault.load(rel)
        result = {"path": rel, "status": "created", "new_hash": doc.hashes.file_hash if doc.hashes else None,
                  "diff": unified_diff("", text, "/dev/null", rel, DIFF_LINES)}
        if infos:
            result["images"] = infos
        return result

    def free_name(self, base_dir: str, stem: str, tail: str = "", ext: str = ".md") -> str:
        """Freien Dateinamen ``<stem><tail>.md`` in einem Ordner finden (nie überschreiben).

        Args:
            base_dir: Ordner relativ zum Vault.
            stem: Gewünschter Dateiname ohne Endung.
            tail: Fester Schluss des Namens (z. B. ``_2026-11-03``); das Suffix steht davor.
            ext: Dateiendung.

        Returns:
            Relativer Pfad; bei Namensgleichheit mit Suffix ``-2``, ``-3`` … vor ``tail``. Der Name hat
            höchstens ``MAX_NAME`` Zeichen; gekürzt wird nur ``stem``, nie Suffix, ``tail`` oder Endung.
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
        """Ziel für ``related`` als Wikilink-Pfad.

        Args:
            target: Pfad, Wikilink oder ID.

        Returns:
            Pfad ohne ``.md``.
        """
        rel = self.svc.resolve(target)
        return rel[:-3] if rel.lower().endswith(".md") else rel

    def _free_inbox_name(self, date: str, title: str) -> str:
        """Freien Dateinamen ``<slug>_YYYY-MM-DD.md`` im Eingang finden (nie überschreiben).

        Args:
            date: Datum ``YYYY-MM-DD``.
            title: Titel.

        Returns:
            Relativer Pfad; bei Namensgleichheit mit Suffix vor dem Datum (``<slug>-2_YYYY-MM-DD.md``).
        """
        return self.free_name(INBOX, slugify(title, MAX_NAME), f"_{date}")

    def rewrite_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, target: str, content: str, expected_hash: str | None, note: str | None = None,
        confirm_shortening: bool = False, images: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Tool ``rewrite_document``: gesamten Inhalt unterhalb des Frontmatters ersetzen.

        Args:
            target: Ziel.
            content: Neuer Inhalt ohne Frontmatter.
            expected_hash: Hash aus ``read``.
            note: Änderungsnotiz.
            confirm_shortening: Deutliche Kürzung, fehlende Abschnitte bzw. entfernte Bilder bestätigen.
            images: Neue Bilder zu Platzhaltern ``{{image:<name>}}`` (4.9).

        Returns:
            Rückgabe von ``finish``.

        Raises:
            PkmError: ``large_shortening`` mit ``missing_sections`` bzw. ``removed_images``, wenn der Inhalt
                kürzer als 60 % ist, Abschnitte oder Bilder fehlen und nicht bestätigt wurde;
                ``unknown_image`` bei unbekannten Platzhaltern.
        """
        new_body = normalize_text(strip_frontmatter(normalize_fragment(content or "")))
        self.check_size(new_body, "Der Inhalt")

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            body = docimages.restore_body(doc.parsed.body, new_body)
            _check_shortening(doc, body, confirm_shortening)
            fm = doc.parsed.frontmatter_text
            return fm + ("\n" if fm else "") + body.lstrip("\n")

        return self.change(target, expected_hash, transform, note or "neu gefasst", images=images)

    def append_to_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, target: str, text: str, expected_hash: str | None, section: str | None = None, note: str | None = None,
        images: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Tool ``append_to_document``.

        Args:
            target: Ziel.
            text: Einzufügender Markdown-Text.
            expected_hash: Hash aus ``read``.
            section: Abschnittsschlüssel (auch ``_preamble`` oder mit Suffix); fehlt der Abschnitt,
                wird er als Ebene 2 angelegt; ohne Angabe wird am Dateiende angehängt.
            note: Änderungsnotiz.
            images: Neue Bilder zu Platzhaltern ``{{image:<name>}}`` (4.9).

        Returns:
            Rückgabe von ``finish``.

        Raises:
            PkmError: ``invalid_argument`` bei leerem Text, ``ambiguous`` bei doppelten Überschriften.
        """
        block = normalize_fragment(text or "").strip("\n").split("\n")
        if not "".join(block).strip():
            raise PkmError("invalid_argument", "text ist leer.")
        self.check_size("\n".join(block), "Der Text")

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            return doc.parsed.frontmatter_text + "\n".join(append_lines(doc.parsed, block, section)) + "\n"

        default = f"ergänzt: {section}" if section else "ergänzt am Ende"
        return self.change(target, expected_hash, transform, note or default, images=images)

    def edit_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, target: str, old: str, new: str, expected_hash: str | None, note: str | None = None,
        images: list[dict[str, Any]] | None = None, confirm_shortening: bool = False,
    ) -> dict[str, Any]:
        """Tool ``edit_document``: Textstelle ersetzen.

        Args:
            target: Ziel.
            old: Textstelle, die genau einmal im Body vorkommen muss.
            new: Ersatz (darf leer sein).
            expected_hash: Hash aus ``read``.
            note: Änderungsnotiz.
            images: Neue Bilder zu Platzhaltern ``{{image:<name>}}`` (4.9).
            confirm_shortening: Entfernen von Bildern bestätigen.

        Returns:
            Rückgabe von ``finish``.

        Raises:
            PkmError: ``invalid_argument`` bei leerem ``old``, ``not_found`` oder ``ambiguous``,
                ``large_shortening`` bei entfernten Bildern ohne Bestätigung.
        """
        old_n = normalize_fragment(old or "")
        new_n = normalize_fragment(new or "")
        if not old_n:
            raise PkmError("invalid_argument", "old ist leer.")
        self.check_size(new_n, "Der Text")

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            body = doc.parsed.body
            new_body = docimages.edit_view(body, old_n, new_n)
            removed = docimages.removed_images(body, new_body)
            if removed and not confirm_shortening:
                raise PkmError("large_shortening", "Die Änderung entfernt Bilder. Bitte vom Nutzer bestätigen lassen "
                               "und mit confirm_shortening=true erneut aufrufen.", removed_images=removed, path=doc.rel)
            return doc.parsed.frontmatter_text + new_body

        return self.change(target, expected_hash, transform, note or "Textstelle geändert", images=images)

    def add_image(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, target: str, expected_hash: str | None, image: dict[str, Any], section: str | None = None,
        caption: str | None = None, note: str | None = None,
    ) -> dict[str, Any]:
        """Tool ``add_image``: ein Bild am Ende eines Abschnitts bzw. des Dokuments einfügen (4.9).

        Args:
            target: Ziel.
            expected_hash: Hash aus ``read``.
            image: Bildangabe wie bei ``images``.
            section: Abschnitt, an dessen Ende eingefügt wird; ohne Angabe am Dateiende.
            caption: Bildunterschrift (eine Zeile unter dem Bild).
            note: Änderungsnotiz.

        Returns:
            Wie ``append_to_document``, mit ``images``.
        """
        name = str((image or {}).get("name") or "")
        block = f"{{{{image:{name}}}}}" + (f"\n{' '.join(caption.split())}" if caption and caption.strip() else "")
        return self.append_to_document(target, block, expected_hash, section, note or f"Bild ergänzt: {name}",
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
            target: Ziel.
            expected_hash: Hash aus ``read``.
            set: Felder setzen oder überschreiben (Parametername laut Spezifikation 7.2).
            add: An Listenfelder anhängen, ohne Duplikate.
            remove: Felder entfernen.
            note: Änderungsnotiz.

        Returns:
            Rückgabe von ``finish``.

        Raises:
            PkmError: ``invalid_argument`` ohne Änderung, ``protected_field`` bei geschützten Feldern.
        """
        set_fields = dict(set or {})
        add_fields = dict(add or {})
        remove_fields = list(remove or [])
        touched = [*set_fields, *add_fields, *remove_fields]
        if not touched:
            raise PkmError("invalid_argument", "Keine Änderung angegeben (set, add oder remove).")
        bad = [k for k in touched if k in PROTECTED]
        if bad:
            raise PkmError("protected_field", f"Geschützte Felder: {', '.join(bad)}", fields=bad)

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            meta = order_meta(_updated_meta(doc.meta, set_fields, add_fields, remove_fields))
            return dump_meta(meta) + doc.parsed.body

        default = f"Metadaten: {', '.join(dict.fromkeys(touched))}"
        return self.change(target, expected_hash, transform, note or default)

    def restore_document(
        self, target: str, version: int, expected_hash: str | None, source: str = "chat"
    ) -> dict[str, Any]:
        """Tool ``restore_document``: Inhalt einer früheren Version als neue Version.

        Args:
            target: Ziel.
            version: Wiederherzustellende Version.
            expected_hash: Hash aus ``read``.
            source: ``chat`` (MCP) oder ``user`` (CLI).

        Returns:
            Rückgabe von ``finish`` mit der Notiz ``wiederhergestellt aus v<n>``.

        Raises:
            PkmError: ``not_versioned`` für Dateien in ``scratch/``.
        """
        if not self.vault.load(self.svc.resolve(target)).versioned:
            raise PkmError("not_versioned", "Dateien in scratch/ haben keine Versionen.", target=target)

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None and doc.id
            _, old_text = self.svc.text_at_version(doc.id, int(version))
            old = load_text_doc(doc.rel, old_text.encode("utf-8"))
            if old.parsed is None:
                raise PkmError("invalid_encoding", f"Version {version} ist nicht lesbar.")
            return doc.parsed.frontmatter_text + old.parsed.body

        return self.change(target, expected_hash, transform, f"wiederhergestellt aus v{int(version)}", source)

# Functions *******************************************************************


def _scratch_folder(folder: str | None) -> str:
    """Unterordner für ``scratch/`` prüfen.

    Args:
        folder: Angegebener Unterordner (``/`` als Trenner) oder ``None``.

    Returns:
        Bereinigter relativer Unterordner (leer für die Wurzel von ``scratch/``).

    Raises:
        PkmError: ``invalid_path`` bei ``..``, absoluten oder nicht plattformfesten Namen.
    """
    parts = [p for p in (folder or "").replace("\\", "/").strip().strip("/").split("/") if p]
    if (folder or "").strip().startswith(("/", "\\")) or any(p == ".." or not is_platform_safe_name(p) for p in parts):
        raise PkmError("invalid_path", f"Ungültiger Ordner: {folder}", folder=folder)
    return "/".join(parts)


def _ordered_meta(values: dict[str, Any]) -> dict[str, Any]:
    """Frontmatter eines neuen Dokuments in der Reihenfolge aus 4.1; leere Werte entfallen.

    Args:
        values: Feldwerte.

    Returns:
        Die Felder in der Reihenfolge von ``FIELD_ORDER``.
    """
    return {k: values[k] for k in FIELD_ORDER if values.get(k) not in (None, "", [])}


def _check_create_args(title: str, area: str, folder: str | None, kind: str | None) -> None:
    """Parameter von ``create_document`` prüfen.

    Args:
        title: Bereinigter Titel.
        area: Zielbereich.
        folder: Unterordner (nur bei ``scratch``).
        kind: Art des Dokuments oder ``None``.

    Raises:
        PkmError: ``invalid_argument`` bei fehlendem Titel, unbekanntem Bereich oder ``kind``.
    """
    if not title:
        raise PkmError("invalid_argument", "title fehlt.")
    if area not in CREATE_AREAS:
        raise PkmError("invalid_argument", "area muss documents oder scratch sein.")
    if folder and area != SCRATCH:
        raise PkmError("invalid_argument", "folder gibt es nur bei area scratch.")
    if kind is not None and kind not in KINDS:
        raise PkmError("invalid_argument", f"kind muss einer der Werte {', '.join(KINDS)} sein.")


def _check_shortening(doc: Doc, new_body: str, confirmed: bool) -> None:
    """Kürzungsschutz von ``rewrite_document`` (weniger als 60 % oder fehlende Abschnitte).

    Args:
        doc: Dokument vor der Änderung.
        new_body: Neuer, normalisierter Body.
        confirmed: Kürzung wurde vom Nutzer bestätigt.

    Raises:
        PkmError: ``large_shortening`` mit den fehlenden Abschnitten.
    """
    assert doc.parsed is not None
    old_body = normalize_text(doc.parsed.body)
    new_keys = {s.key for s in split_sections(new_body)}
    missing = [k for k in doc.parsed.section_keys() if k not in new_keys]
    removed = docimages.removed_images(old_body, new_body)
    ratio = len(new_body) / len(old_body) if old_body else 1.0
    if not confirmed and (ratio < SHORTENING_RATIO or missing or removed):
        raise PkmError(
            "large_shortening",
            "Der neue Inhalt ist deutlich kürzer oder es fehlen Abschnitte. "
            "Bitte vom Nutzer bestätigen lassen und mit confirm_shortening=true erneut aufrufen.",
            missing_sections=missing, removed_images=removed, old_chars=len(old_body), new_chars=len(new_body),
            ratio=round(ratio, 2), path=doc.rel,
        )


def _updated_meta(
    meta: dict[str, Any], set_fields: dict[str, Any], add_fields: dict[str, Any], remove_fields: list[str]
) -> dict[str, Any]:
    """Frontmatter-Felder nach ``update_frontmatter`` berechnen.

    Args:
        meta: Bisherige Felder.
        set_fields: Zu setzende Felder.
        add_fields: An Listen anzuhängende Werte.
        remove_fields: Zu entfernende Felder.

    Returns:
        Neue Felder (Reihenfolge bleibt erhalten).

    Raises:
        PkmError: ``invalid_argument``, wenn an ein Feld angehängt werden soll, das keine Liste ist.
    """
    result = dict(meta)
    result.update(set_fields)
    for key, values in add_fields.items():
        values = values if isinstance(values, list) else [values]
        current = result.get(key)
        current = [] if current is None else current
        if not isinstance(current, list):
            raise PkmError("invalid_argument", f"Feld {key} ist keine Liste.", field=key)
        result[key] = current + [v for v in values if v not in current]
    for key in remove_fields:
        result.pop(key, None)
    return result

# Main ************************************************************************
