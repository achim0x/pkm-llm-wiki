"""Schreibende Operationen (Spezifikation 5.4, 6, 7.2).

Ablauf jeder Änderung: Git prüfen → Ziel prüfen → Hash-Schutz → Stand von Hand ggf. als
eigene Version committen → Änderung anwenden → Version +1, `updated` → atomar schreiben →
Commit nur dieser Datei → bei Fehler Datei zurücksetzen.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

from .errors import PkmError
from .frontmatter import PROTECTED, dump_meta, set_fields_linewise
from .gitlayer import build_message
from .ids import new_id
from .normalize import encode, normalize_fragment, normalize_text
from .parse import PREAMBLE, body_lines, normalize_key_input, strip_frontmatter
from .paths import is_conflict_copy, slugify
from .vault import Doc, load_text_doc

if TYPE_CHECKING:
    from .service import Service

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

INBOX = "documents/_inbox"
DIFF_LINES = 80
SHORTENING_RATIO = 0.6
KINDS = ("note", "correction")


def _count(haystack: str, needle: str) -> int:
    n, start = 0, 0
    while True:
        i = haystack.find(needle, start)
        if i < 0:
            return n
        n += 1
        start = i + 1


def _insert_block(lines: list[str], after: int, block: list[str]) -> list[str]:
    """Block nach Zeile `after` einfügen, mit Leerzeile davor und ggf. danach."""
    head, tail = lines[: after + 1], lines[after + 1 :]
    out = head + ([""] if head and head[-1].strip() else []) + block
    if tail and tail[0].strip():
        out.append("")
    return out + tail


def _last_nonblank(lines: list[str], start: int, end: int) -> int:
    for i in range(end - 1, start - 1, -1):
        if lines[i].strip():
            return i
    return start


class Writer:
    def __init__(self, svc: Service) -> None:
        self.svc = svc
        self.cfg = svc.cfg
        self.git = svc.git
        self.vault = svc.vault

    # ------------------------------------------------------------ Grundlagen
    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        if fcntl is None or not self.cfg.git_dir.is_dir():
            yield
            return
        with open(self.cfg.git_dir / "pkm.lock", "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def now_iso(self) -> str:
        return self.svc.now().isoformat(timespec="seconds")

    def check_size(self, text: str, what: str) -> None:
        if len(text.encode("utf-8")) > self.cfg.max_bytes:
            raise PkmError("too_large", f"{what} ist größer als {self.cfg.max_kb} KB (PKM_MAX_KB).")

    def write_atomic(self, rel: str, text: str) -> None:
        p = self.vault.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".pkm-tmp-{uuid.uuid4().hex}-{p.name}")
        mode = p.stat().st_mode & 0o777 if p.exists() else None
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

    def write_and_commit(self, rel: str, text: str, message: str, extra_paths: list[str] | None = None,
                         as_user: bool = False) -> str:
        """Schreiben und committen; schlägt der Commit fehl, wird die Datei zurückgesetzt."""
        p = self.vault.path(rel)
        old = p.read_bytes() if p.exists() else None
        self.write_atomic(rel, text)
        try:
            return self.git.commit_paths([rel, *(extra_paths or [])], message, as_user=as_user)
        except PkmError as exc:
            if old is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(old)
            raise PkmError("commit_failed", f"Commit fehlgeschlagen, Datei zurückgesetzt. {exc.message}") from exc

    def editable_doc(self, target: str) -> Doc:
        rel = self.svc.resolve(target)
        if not rel.startswith("documents/"):
            raise PkmError("forbidden", "Nur Dokumente unter documents/ sind änderbar; wiki/ ist aus Chats nur lesbar.", path=rel)
        if not rel.lower().endswith(".md"):
            raise PkmError("forbidden", "Nur Markdown-Dateien sind änderbar.", path=rel)
        doc = self.vault.load(rel)
        if doc.error:
            raise PkmError(doc.error, doc.error_message or doc.error, path=rel)
        return doc

    @staticmethod
    def check_hash(doc: Doc, expected_hash: str | None) -> None:
        current = doc.hashes.file_hash if doc.hashes else ""
        if not expected_hash or expected_hash.strip().lower() != current:
            raise PkmError(
                "conflict",
                "Die Datei wurde seit dem Lesen geändert (oder expected_hash fehlt). Bitte neu lesen.",
                path=doc.rel, current_hash=current, version=doc.version,
            )

    # --------------------------------------------- Stand von Hand als Version
    def commit_user_state(self, doc: Doc) -> Doc:
        """Weicht die Datei vom letzten Commit ab, diesen Stand vorher als eigene Version committen."""
        rel = doc.rel
        dirty = self.git.is_dirty(rel)
        if doc.id and not dirty:
            return doc
        text = doc.text or ""
        extra: list[str] = []
        fields: dict[str, Any] = {}
        if not doc.id:
            doc_id = new_id(self.svc.now(), exists=lambda i: i in self.svc.known_ids())
            version, label, note = 1, "v1", "Erstfassung von Hand, ID vergeben"
            fields = {"id": doc_id, "version": 1}
        else:
            doc_id = doc.id
            prev = next((c for c in reversed(self.svc.versions(doc_id)) if c.path), None)
            if prev is None:
                version = doc.version or 1
                label, note = f"v{version}", "Erstfassung von Hand"
                if doc.version != version:
                    fields["version"] = version
            else:
                prev_doc = load_text_doc(prev.path or "", self.git.show_file(prev.sha, prev.path or ""))
                moved = prev.path != rel
                if moved and not self.vault.exists(prev.path or ""):
                    extra.append(prev.path or "")
                same = (
                    prev_doc.hashes is not None and doc.hashes is not None
                    and prev_doc.hashes.body_hash == doc.hashes.body_hash
                    and prev_doc.hashes.meta_hash == doc.hashes.meta_hash
                )
                if moved and same:
                    version = prev.version or 1
                    label, note = "moved", f"verschoben: {prev.path} → {rel}"
                else:
                    version = (prev.version or 0) + 1
                    label = f"v{version}"
                    note = "Änderung von Hand" + (f", verschoben von {prev.path}" if moved else "")
                    fields["updated"] = self.now_iso()
                if doc.version != version:
                    fields["version"] = version
        if fields:
            text = set_fields_linewise(text, fields)
        msg = build_message(doc.title, label, note, doc_id, version, "user")
        self.write_and_commit(rel, text, msg, extra, as_user=True)
        return self.vault.load(rel)

    # ----------------------------------------------------------- Abschluss
    def finish(self, doc: Doc, new_text: str, note: str, source: str = "chat") -> dict[str, Any]:
        old_text = doc.text or ""
        new_text = normalize_text(new_text)
        if new_text == old_text:
            return {
                "id": doc.id, "path": doc.rel, "status": "unchanged", "version": doc.version,
                "new_hash": doc.hashes.file_hash if doc.hashes else None, "commit": None, "diff": "",
            }
        version = (doc.version or 0) + 1
        new_text = set_fields_linewise(new_text, {"version": version, "updated": self.now_iso()})
        self.check_size(new_text, "Das Dokument")
        new_doc = load_text_doc(doc.rel, new_text.encode("utf-8"))
        if new_doc.error:
            raise PkmError(new_doc.error, new_doc.error_message or "Ergebnis ungültig.")
        msg = build_message(new_doc.title, f"v{version}", note, doc.id or "", version, source)
        sha = self.write_and_commit(doc.rel, new_text, msg)
        from .service import unified_diff

        return {
            "id": doc.id, "path": doc.rel, "status": "changed", "version": version,
            "new_hash": new_doc.hashes.file_hash if new_doc.hashes else None, "commit": sha[:10],
            "diff": unified_diff(old_text, new_text, f"v{doc.version}", f"v{version}", DIFF_LINES),
        }

    def change(self, target: str, expected_hash: str | None, transform: Callable[[Doc], str],
               note: str, source: str = "chat") -> dict[str, Any]:
        with self.lock():
            self.git.require_ok()
            doc = self.editable_doc(target)
            self.check_hash(doc, expected_hash)
            doc = self.commit_user_state(doc)
            return self.finish(doc, transform(doc), note, source)

    # --------------------------------------------------------------- Tools
    def create_document(self, title: str, content: str, topics: list[str] | None = None,
                        context: str | None = None, related: list[str] | None = None,
                        kind: str | None = None, source: str | None = None,
                        note: str | None = None) -> dict[str, Any]:
        title = " ".join((title or "").split())
        if not title:
            raise PkmError("invalid_argument", "title fehlt.")
        kind = kind or "note"
        if kind not in KINDS:
            raise PkmError("invalid_argument", "kind muss note oder correction sein.")
        body = strip_frontmatter(normalize_fragment(content or ""))
        self.check_size(body, "Der Inhalt")
        links = [f"[[{self._link_target(r)}]]" for r in (related or [])]
        with self.lock():
            self.git.require_ok()
            now = self.svc.now()
            doc_id = new_id(now, exists=lambda i: i in self.svc.known_ids())
            stamp = now.isoformat(timespec="seconds")
            meta: dict[str, Any] = {"id": doc_id, "version": 1, "title": title, "created": stamp,
                                    "updated": stamp, "source": source or "claude-chat"}
            if context:
                meta["context"] = " ".join(context.split())
            if topics:
                meta["topics"] = [str(t) for t in topics]
            if links:
                meta["related"] = links
            meta["kind"] = kind
            text = normalize_text(dump_meta(meta) + "\n" + body.lstrip("\n"))
            rel = self._free_inbox_name(now.date().isoformat(), title)
            msg = build_message(title, "v1", note or "neu angelegt", doc_id, 1, "chat")
            sha = self.write_and_commit(rel, text, msg)
        from .service import unified_diff

        doc = self.vault.load(rel)
        return {
            "id": doc_id, "path": rel, "status": "created", "version": 1,
            "new_hash": doc.hashes.file_hash if doc.hashes else None, "commit": sha[:10],
            "diff": unified_diff("", text, "/dev/null", rel, DIFF_LINES),
        }

    def _link_target(self, target: str) -> str:
        rel = self.svc.resolve(target)
        return rel[:-3] if rel.lower().endswith(".md") else rel

    def _free_inbox_name(self, date: str, title: str) -> str:
        base = f"{date}_{slugify(title)}"
        existing = {r.casefold() for r in self.vault.iter_files(("documents",))}
        n = 1
        while True:
            name = f"{base}.md" if n == 1 else f"{base}-{n}.md"
            rel = f"{INBOX}/{name}"
            if rel.casefold() not in existing and not self.vault.path(rel).exists():
                return rel
            n += 1

    def rewrite_document(self, target: str, content: str, expected_hash: str | None,
                         note: str | None = None, confirm_shortening: bool = False) -> dict[str, Any]:
        new_body = strip_frontmatter(normalize_fragment(content or ""))
        self.check_size(new_body, "Der Inhalt")

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            old_body = normalize_text(doc.parsed.body)
            new_norm = normalize_text(new_body)
            from .parse import split_sections

            new_keys = {s.key for s in split_sections(new_norm)}
            missing = [k for k in doc.parsed.section_keys() if k not in new_keys]
            ratio = len(new_norm) / len(old_body) if old_body else 1.0
            if not confirm_shortening and (ratio < SHORTENING_RATIO or missing):
                raise PkmError(
                    "large_shortening",
                    "Der neue Inhalt ist deutlich kürzer oder es fehlen Abschnitte. "
                    "Bitte vom Nutzer bestätigen lassen und mit confirm_shortening=true erneut aufrufen.",
                    missing_sections=missing, old_chars=len(old_body), new_chars=len(new_norm),
                    ratio=round(ratio, 2), path=doc.rel,
                )
            return doc.parsed.frontmatter_text + "\n" + new_norm.lstrip("\n")

        return self.change(target, expected_hash, transform, note or "neu gefasst")

    def append_to_document(self, target: str, text: str, expected_hash: str | None,
                           section: str | None = None, note: str | None = None) -> dict[str, Any]:
        block = normalize_fragment(text or "").strip("\n").split("\n")
        if not "".join(block).strip():
            raise PkmError("invalid_argument", "text ist leer.")
        self.check_size("\n".join(block), "Der Text")

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            lines = body_lines(doc.parsed.body)
            sections = doc.parsed.sections
            if section is None:
                out = _insert_block(lines, len(lines) - 1, block) if lines else block
            else:
                key = normalize_key_input(section)
                sec = doc.parsed.section(key)
                if key == PREAMBLE:
                    if sec is not None:
                        out = _insert_block(lines, _last_nonblank(lines, sec.start, sec.end), block)
                    else:
                        first = sections[0].start if sections else len(lines)
                        lead = 0
                        while lead < first and not lines[lead].strip():
                            lead += 1
                        out = lines[:lead] + block + ([""] if first < len(lines) else []) + lines[lead:]
                elif sec is None:
                    heading = [f"## {key}", ""]
                    out = _insert_block(lines, len(lines) - 1, heading + block) if lines else heading + block
                else:
                    dups = [s.key for s in sections if s.level and s.base == key and s.key != key]
                    if "#" not in key and dups:
                        raise PkmError(
                            "ambiguous", f"Abschnitt „{key}“ kommt mehrfach vor. Bitte mit Suffix angeben.",
                            candidates=[key, *dups],
                        )
                    out = _insert_block(lines, _last_nonblank(lines, sec.start, sec.end), block)
            return doc.parsed.frontmatter_text + "\n".join(out) + "\n"

        default = f"ergänzt: {section}" if section else "ergänzt am Ende"
        return self.change(target, expected_hash, transform, note or default)

    def edit_document(self, target: str, old: str, new: str, expected_hash: str | None,
                      note: str | None = None) -> dict[str, Any]:
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

    def update_frontmatter(self, target: str, expected_hash: str | None, set: dict[str, Any] | None = None,
                           add: dict[str, Any] | None = None, remove: list[str] | None = None,
                           note: str | None = None) -> dict[str, Any]:
        set_ = dict(set or {})
        add = dict(add or {})
        remove = list(remove or [])
        touched = [*set_, *add, *remove]
        if not touched:
            raise PkmError("invalid_argument", "Keine Änderung angegeben (set, add oder remove).")
        bad = [k for k in touched if k in PROTECTED]
        if bad:
            raise PkmError("protected_field", f"Geschützte Felder: {', '.join(bad)}", fields=bad)

        def transform(doc: Doc) -> str:
            assert doc.parsed is not None
            meta = dict(doc.meta)
            meta.update(set_)
            for key, values in add.items():
                values = values if isinstance(values, list) else [values]
                current = meta.get(key)
                if current is None:
                    current = []
                if not isinstance(current, list):
                    raise PkmError("invalid_argument", f"Feld {key} ist keine Liste.", field=key)
                meta[key] = current + [v for v in values if v not in current]
            for key in remove:
                meta.pop(key, None)
            return dump_meta(meta) + doc.parsed.body

        return self.change(target, expected_hash, transform, note or f"Metadaten: {', '.join(dict.fromkeys(touched))}")

    def restore_document(self, target: str, version: int, expected_hash: str | None,
                         source: str = "chat") -> dict[str, Any]:
        def transform(doc: Doc) -> str:
            assert doc.parsed is not None and doc.id
            _, old_text = self.svc.text_at_version(doc.id, int(version))
            old = load_text_doc(doc.rel, old_text.encode("utf-8"))
            if old.parsed is None:
                raise PkmError("invalid_encoding", f"Version {version} ist nicht lesbar.")
            return doc.parsed.frontmatter_text + old.parsed.body

        return self.change(target, expected_hash, transform, f"wiederhergestellt aus v{int(version)}", source)


__all__ = ["Writer", "is_conflict_copy"]
