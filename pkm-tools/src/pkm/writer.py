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

from .diffs import unified_diff
from .errors import PkmError
from .frontmatter import PROTECTED, dump_meta, set_fields_linewise
from .gitlayer import Commit, build_message
from .ids import new_id
from .normalize import encode, normalize_fragment, normalize_text
from .parse import PREAMBLE, Parsed, body_lines, normalize_key_input, split_sections, strip_frontmatter
from .paths import slugify
from .vault import Doc, load_text_doc

if TYPE_CHECKING:
    from .service import Service

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

# Variables *******************************************************************

INBOX = "documents/_inbox"
DIFF_LINES = 80
SHORTENING_RATIO = 0.6
KINDS = ("note", "correction")
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
        if fcntl is None or not self.cfg.git_dir.is_dir():
            yield
        else:
            with open(self.cfg.git_dir / "pkm.lock", "w", encoding="utf-8") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(fh, fcntl.LOCK_UN)

    def now_iso(self) -> str:
        """Aktuelle Zeit als ISO-String mit Sekunden und Zeitzone.

        Returns:
            Zeitstempel, z. B. ``2026-11-02T19:05:00+01:00``.
        """
        return self.svc.now().isoformat(timespec="seconds")

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
            os.replace(tmp, p)
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
            PkmError: ``forbidden`` außerhalb von ``documents/`` oder bei Nicht-Markdown,
                ``invalid_encoding``/``invalid_frontmatter`` bei unlesbaren Dateien.
        """
        rel = self.svc.resolve(target)
        if not rel.startswith("documents/"):
            raise PkmError(
                "forbidden", "Nur Dokumente unter documents/ sind änderbar; wiki/ ist aus Chats nur lesbar.", path=rel
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
            plan = _UserVersion(doc.id, version, f"v{version}", note, {"updated": self.now_iso()})
        if moved and not self.vault.exists(prev_path):
            plan.extra_paths.append(prev_path)
        return plan

    # Abschluss ****************************************************************

    def finish(self, doc: Doc, new_text: str, note: str, source: str = "chat") -> dict[str, Any]:
        """Neue Fassung als neue Version schreiben und committen.

        Args:
            doc: Dokument vor der Änderung.
            new_text: Neuer Gesamttext (Serverfelder werden hier gesetzt).
            note: Änderungsnotiz.
            source: ``chat``, ``user`` oder ``agent``.

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
            new_text = set_fields_linewise(new_text, {"version": version, "updated": self.now_iso()})
            self.check_size(new_text, "Das Dokument")
            new_doc = load_text_doc(doc.rel, new_text.encode("utf-8"))
            if new_doc.error:
                raise PkmError(new_doc.error, new_doc.error_message or "Ergebnis ungültig.")
            msg = build_message(new_doc.title, f"v{version}", note, doc.id or "", version, source)
            sha = self.write_and_commit(doc.rel, new_text, msg)
            result = {
                "id": doc.id, "path": doc.rel, "status": "changed", "version": version,
                "new_hash": new_doc.hashes.file_hash if new_doc.hashes else None, "commit": sha[:10],
                "diff": unified_diff(old_text, new_text, f"v{doc.version}", f"v{version}", DIFF_LINES),
            }
        return result

    def change(
        self, target: str, expected_hash: str | None, transform: Callable[[Doc], str], note: str, source: str = "chat"
    ) -> dict[str, Any]:
        """Gemeinsamer Ablauf aller Änderungs-Tools.

        Args:
            target: Ziel.
            expected_hash: Hash aus ``read``.
            transform: Erzeugt aus dem Dokument den neuen Gesamttext.
            note: Änderungsnotiz.
            source: ``chat`` oder ``user``.

        Returns:
            Rückgabe von ``finish``.
        """
        with self.lock():
            self.git.require_ok()
            doc = self.editable_doc(target)
            self.check_hash(doc, expected_hash)
            doc = self.commit_user_state(doc)
            result = self.finish(doc, transform(doc), note, source)
        return result

    # Tools ********************************************************************

    def create_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        title: str,
        content: str,
        topics: list[str] | None = None,
        context: str | None = None,
        related: list[str] | None = None,
        kind: str | None = None,
        source: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Tool ``create_document``: neues Dokument in ``documents/_inbox/`` (Version 1).

        Args:
            title: Titel; daraus wird der Dateiname gebildet.
            content: Inhalt ohne Frontmatter (ein mitgeliefertes wird entfernt).
            topics: Schlagwörter.
            context: Herkunft, z. B. Chat-Titel.
            related: Verwandte Dokumente (Pfad, Wikilink oder ID).
            kind: ``note`` (Standard) oder ``correction``.
            source: Quelle, Standard ``claude-chat``.
            note: Änderungsnotiz für den Commit.

        Returns:
            ``{id, path, status: created, version: 1, new_hash, commit, diff}``.

        Raises:
            PkmError: ``invalid_argument``, ``too_large``, ``not_found`` (``related``) oder
                ``git_unavailable``.
        """
        title = " ".join((title or "").split())
        if not title:
            raise PkmError("invalid_argument", "title fehlt.")
        kind = kind or "note"
        if kind not in KINDS:
            raise PkmError("invalid_argument", "kind muss note oder correction sein.")
        body = strip_frontmatter(normalize_fragment(content or ""))
        self.check_size(body, "Der Inhalt")
        extra = {
            "source": source or "claude-chat",
            "context": " ".join(context.split()) if context else None,
            "topics": [str(t) for t in topics] if topics else None,
            "related": [f"[[{self._link_target(r)}]]" for r in related] if related else None,
            "kind": kind,
        }
        return self._write_new(title, body, note or "neu angelegt", extra)

    def _write_new(self, title: str, body: str, note: str, extra: dict[str, Any]) -> dict[str, Any]:
        """Neues Dokument mit ID und Version 1 schreiben und committen.

        Args:
            title: Titel.
            body: Inhalt ohne Frontmatter.
            note: Änderungsnotiz.
            extra: Weitere Felder (``source``, ``context``, ``topics``, ``related``, ``kind``).

        Returns:
            Rückgabe von ``_created_result``.
        """
        with self.lock():
            self.git.require_ok()
            now = self.svc.now()
            doc_id = new_id(now, exists=lambda i: i in self.svc.known_ids())
            meta = _initial_meta(doc_id, title, now.isoformat(timespec="seconds"), extra)
            text = normalize_text(dump_meta(meta) + "\n" + body.lstrip("\n"))
            rel = self._free_inbox_name(now.date().isoformat(), title)
            sha = self.write_and_commit(rel, text, build_message(title, "v1", note, doc_id, 1, "chat"))
        return self._created_result(doc_id, rel, text, sha)

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
        """Freien Dateinamen ``YYYY-MM-DD_<slug>.md`` im Eingang finden (nie überschreiben).

        Args:
            date: Datum ``YYYY-MM-DD``.
            title: Titel.

        Returns:
            Relativer Pfad; bei Namensgleichheit mit Suffix ``-2``, ``-3`` …
        """
        base = f"{date}_{slugify(title)}"
        existing = {r.casefold() for r in self.vault.iter_files(("documents",))}
        n = 1
        rel = f"{INBOX}/{base}.md"
        while rel.casefold() in existing or self.vault.path(rel).exists():
            n += 1
            rel = f"{INBOX}/{base}-{n}.md"
        return rel

    def rewrite_document(
        self, target: str, content: str, expected_hash: str | None, note: str | None = None,
        confirm_shortening: bool = False,
    ) -> dict[str, Any]:
        """Tool ``rewrite_document``: gesamten Inhalt unterhalb des Frontmatters ersetzen.

        Args:
            target: Ziel.
            content: Neuer Inhalt ohne Frontmatter.
            expected_hash: Hash aus ``read``.
            note: Änderungsnotiz.
            confirm_shortening: Deutliche Kürzung bzw. fehlende Abschnitte bestätigen.

        Returns:
            Rückgabe von ``finish``.

        Raises:
            PkmError: ``large_shortening`` mit ``missing_sections``, wenn der Inhalt kürzer als 60 %
                ist oder Abschnitte fehlen und nicht bestätigt wurde.
        """
        new_body = normalize_text(strip_frontmatter(normalize_fragment(content or "")))
        self.check_size(new_body, "Der Inhalt")

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            _check_shortening(doc, new_body, confirm_shortening)
            return doc.parsed.frontmatter_text + "\n" + new_body.lstrip("\n")

        return self.change(target, expected_hash, transform, note or "neu gefasst")

    def append_to_document(
        self, target: str, text: str, expected_hash: str | None, section: str | None = None, note: str | None = None
    ) -> dict[str, Any]:
        """Tool ``append_to_document``.

        Args:
            target: Ziel.
            text: Einzufügender Markdown-Text.
            expected_hash: Hash aus ``read``.
            section: Abschnittsschlüssel (auch ``_preamble`` oder mit Suffix); fehlt der Abschnitt,
                wird er als Ebene 2 angelegt; ohne Angabe wird am Dateiende angehängt.
            note: Änderungsnotiz.

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
            return doc.parsed.frontmatter_text + "\n".join(_append_lines(doc.parsed, block, section)) + "\n"

        default = f"ergänzt: {section}" if section else "ergänzt am Ende"
        return self.change(target, expected_hash, transform, note or default)

    def edit_document(
        self, target: str, old: str, new: str, expected_hash: str | None, note: str | None = None
    ) -> dict[str, Any]:
        """Tool ``edit_document``: Textstelle ersetzen.

        Args:
            target: Ziel.
            old: Textstelle, die genau einmal im Body vorkommen muss.
            new: Ersatz (darf leer sein).
            expected_hash: Hash aus ``read``.
            note: Änderungsnotiz.

        Returns:
            Rückgabe von ``finish``.

        Raises:
            PkmError: ``invalid_argument`` bei leerem ``old``, ``not_found`` oder ``ambiguous``.
        """
        old_n = normalize_fragment(old or "")
        new_n = normalize_fragment(new or "")
        if not old_n:
            raise PkmError("invalid_argument", "old ist leer.")
        self.check_size(new_n, "Der Text")

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            body = doc.parsed.body
            n = _count(body, old_n)
            if n == 0:
                raise PkmError("not_found", "Die Textstelle `old` kommt im Dokument nicht vor.", path=doc.rel)
            if n > 1:
                raise PkmError("ambiguous", f"Die Textstelle `old` kommt {n}-mal vor.", count=n, path=doc.rel)
            return doc.parsed.frontmatter_text + body.replace(old_n, new_n, 1)

        return self.change(target, expected_hash, transform, note or "Textstelle geändert")

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
            meta = _updated_meta(doc.meta, set_fields, add_fields, remove_fields)
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
        """
        def transform(doc: Doc) -> str:
            assert doc.parsed is not None and doc.id
            _, old_text = self.svc.text_at_version(doc.id, int(version))
            old = load_text_doc(doc.rel, old_text.encode("utf-8"))
            if old.parsed is None:
                raise PkmError("invalid_encoding", f"Version {version} ist nicht lesbar.")
            return doc.parsed.frontmatter_text + old.parsed.body

        return self.change(target, expected_hash, transform, f"wiederhergestellt aus v{int(version)}", source)

# Functions *******************************************************************


def _initial_meta(doc_id: str, title: str, stamp: str, extra: dict[str, Any]) -> dict[str, Any]:
    """Frontmatter eines neuen Dokuments in der Reihenfolge aus 4.1.

    Args:
        doc_id: Neue ID.
        title: Titel.
        stamp: Zeitstempel für ``created`` und ``updated``.
        extra: ``source``, ``context``, ``topics``, ``related`` und ``kind`` (leere Werte entfallen).

    Returns:
        Die Felder.
    """
    meta: dict[str, Any] = {"id": doc_id, "version": 1, "title": title, "created": stamp, "updated": stamp}
    meta.update({k: v for k, v in extra.items() if v})
    return meta


def _count(haystack: str, needle: str) -> int:
    """Vorkommen zählen, auch überlappende.

    Args:
        haystack: Text.
        needle: Gesuchte Stelle (nicht leer).

    Returns:
        Anzahl der Vorkommen.
    """
    n, start = 0, haystack.find(needle)
    while start >= 0:
        n += 1
        start = haystack.find(needle, start + 1)
    return n


def _insert_block(lines: list[str], after: int, block: list[str]) -> list[str]:
    """Block nach einer Zeile einfügen, mit Leerzeile davor und ggf. danach.

    Args:
        lines: Body-Zeilen.
        after: Index der Zeile, nach der eingefügt wird.
        block: Einzufügende Zeilen.

    Returns:
        Neue Zeilenliste.
    """
    head, tail = lines[: after + 1], lines[after + 1 :]
    out = head + ([""] if head and head[-1].strip() else []) + block
    if tail and tail[0].strip():
        out.append("")
    return out + tail


def _last_nonblank(lines: list[str], start: int, end: int) -> int:
    """Letzte nicht leere Zeile in einem Bereich.

    Args:
        lines: Zeilen.
        start: Erster Index.
        end: Index nach dem Bereich.

    Returns:
        Index der letzten nicht leeren Zeile, sonst ``start``.
    """
    return next((i for i in range(end - 1, start - 1, -1) if lines[i].strip()), start)


def _append_to_preamble(lines: list[str], parsed: Parsed, block: list[str]) -> list[str]:
    """Text am Ende des Vorspanns (vor der ersten Überschrift) einfügen.

    Args:
        lines: Body-Zeilen.
        parsed: Zerlegtes Dokument.
        block: Einzufügende Zeilen.

    Returns:
        Neue Zeilenliste.
    """
    sec = parsed.section(PREAMBLE)
    if sec is not None:
        out = _insert_block(lines, _last_nonblank(lines, sec.start, sec.end), block)
    else:
        first = parsed.sections[0].start if parsed.sections else len(lines)
        lead = next((i for i in range(first) if lines[i].strip()), first)
        out = lines[:lead] + block + ([""] if first < len(lines) else []) + lines[lead:]
    return out


def _append_lines(parsed: Parsed, block: list[str], section: str | None) -> list[str]:
    """Body-Zeilen nach ``append_to_document`` berechnen.

    Args:
        parsed: Zerlegtes Dokument.
        block: Einzufügende Zeilen.
        section: Abschnittsschlüssel oder ``None`` (Dateiende).

    Returns:
        Neue Body-Zeilen.

    Raises:
        PkmError: ``ambiguous``, wenn der Schlüssel ohne Suffix auf doppelte Überschriften zeigt.
    """
    lines = body_lines(parsed.body)
    key = normalize_key_input(section) if section is not None else None
    sec = parsed.section(key) if key is not None else None
    if key is None:
        out = _insert_block(lines, len(lines) - 1, block) if lines else block
    elif key == PREAMBLE:
        out = _append_to_preamble(lines, parsed, block)
    elif sec is None:
        new_section = [f"## {key}", "", *block]
        out = _insert_block(lines, len(lines) - 1, new_section) if lines else new_section
    else:
        dups = [s.key for s in parsed.sections if s.level and s.base == key and s.key != key]
        if "#" not in key and dups:
            raise PkmError(
                "ambiguous", f"Abschnitt „{key}“ kommt mehrfach vor. Bitte mit Suffix angeben.",
                candidates=[key, *dups],
            )
        out = _insert_block(lines, _last_nonblank(lines, sec.start, sec.end), block)
    return out


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
    ratio = len(new_body) / len(old_body) if old_body else 1.0
    if not confirmed and (ratio < SHORTENING_RATIO or missing):
        raise PkmError(
            "large_shortening",
            "Der neue Inhalt ist deutlich kürzer oder es fehlen Abschnitte. "
            "Bitte vom Nutzer bestätigen lassen und mit confirm_shortening=true erneut aufrufen.",
            missing_sections=missing, old_chars=len(old_body), new_chars=len(new_body),
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
