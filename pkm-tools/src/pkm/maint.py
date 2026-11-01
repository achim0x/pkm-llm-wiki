"""Pflege-Befehle der CLI (Spezifikation 8): ids, versions, pending, mark, sha, commit-wiki."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from . import hashes
from .errors import PkmError
from .frontmatter import set_fields_linewise
from .gitlayer import build_message
from .ids import is_valid_id, new_id
from .normalize import encode
from .parse import normalize_key_input
from .paths import case_collisions, is_conflict_copy
from .state import FORMAT, classify, load_state, state_key
from .vault import Doc, is_markdown, load_text_doc

if TYPE_CHECKING:
    from .service import Service

WIKI_COMMIT_PATHS = ["wiki", ".pkm/state.json"]


def page_ref(rel: str) -> str:
    """Wiki-Seite als Verweis ohne Endung (wie in state.json)."""
    return rel[:-3] if rel.lower().endswith(".md") else rel


class Maintenance:
    def __init__(self, svc: Service) -> None:
        self.svc = svc
        self.cfg = svc.cfg
        self.vault = svc.vault
        self.git = svc.git
        self.writer = svc.writer

    # ------------------------------------------------------------ Bestand
    def documents(self) -> tuple[list[Doc], list[dict[str, Any]]]:
        """Alle Dateien unter documents/ (ohne Konfliktkopien) und gefundene Probleme."""
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
        for group in case_collisions(rels):
            problems.append({"problem": "case_collision", "paths": group})
        return docs, problems

    @staticmethod
    def duplicate_ids(docs: list[Doc]) -> dict[str, list[str]]:
        by_id: dict[str, list[str]] = defaultdict(list)
        for d in docs:
            if d.id:
                by_id[d.id].append(d.rel)
        return {i: sorted(p) for i, p in by_id.items() if len(p) > 1}

    # ---------------------------------------------------------------- ids
    def ids(self) -> dict[str, Any]:
        with self.writer.lock():
            self.git.require_ok()
            docs, problems = self.documents()
            known = {d.id for d in docs if d.id}
            assigned, skipped = [], []
            for doc in docs:
                if doc.kind != "md":
                    continue
                if doc.error:
                    skipped.append({"path": doc.rel, "reason": doc.error})
                    continue
                if doc.id and doc.version is not None:
                    continue
                fields: dict[str, Any] = {}
                doc_id = doc.id
                if not doc_id:
                    doc_id = new_id(self.svc.now(), exists=lambda i: i in known)
                    known.add(doc_id)
                    fields["id"] = doc_id
                fields["version"] = 1
                text = set_fields_linewise(doc.text or "", fields)
                msg = build_message(doc.title, "v1", "ID vergeben", doc_id, 1, "agent")
                sha = self.writer.write_and_commit(doc.rel, text, msg)
                assigned.append({"path": doc.rel, "id": doc_id, "commit": sha[:10]})
            dups = self.duplicate_ids(self.documents()[0])
        return {
            "status": "ok",
            "assigned": assigned,
            "duplicates": [{"id": i, "paths": p} for i, p in sorted(dups.items())],
            "skipped": skipped,
            "problems": problems,
        }

    # ----------------------------------------------------------- versions
    def versions(self) -> dict[str, Any]:
        """Von Hand geänderte Dokumente als Version committen (5.4), Verschiebungen mit."""
        with self.writer.lock():
            self.git.require_ok()
            entries = self.git.status_entries("documents")
            dirty = {path for _xy, path in entries}
            deleted = {path for xy, path in entries if "D" in xy}
            committed: list[dict[str, Any]] = []
            skipped: list[dict[str, Any]] = []
            dups = self.duplicate_ids(self.documents()[0])
            handled: set[str] = set()
            # 1. Markdown-Dokumente mit ID (inkl. Verschiebungen per ID)
            for rel in sorted(dirty - deleted):
                if not is_markdown(rel) or not self.vault.exists(rel):
                    continue
                if is_conflict_copy(PurePosixPath(rel).name):
                    skipped.append({"path": rel, "reason": "conflict_copy"})
                    continue
                doc = self.vault.load(rel)
                if doc.error:
                    skipped.append({"path": rel, "reason": doc.error})
                    continue
                if not doc.id:
                    skipped.append({"path": rel, "reason": "missing_id"})
                    continue
                if doc.id in dups:
                    skipped.append({"path": rel, "reason": "duplicate_id"})
                    continue
                before = self.git.out("rev-parse", "HEAD").strip()
                prev_paths = {c.path for c in self.svc.versions(doc.id) if c.path}
                new_doc = self.writer.commit_user_state(doc)
                after = self.git.out("rev-parse", "HEAD").strip()
                if after != before:
                    handled.add(rel)
                    handled.update(p for p in prev_paths if p in deleted)
                    subject = self.git.out("log", "-1", "--format=%s").strip()
                    committed.append({"path": rel, "id": doc.id, "version": new_doc.version,
                                      "subject": subject, "commit": after[:10]})
            # 2. Anhänge (PDF, Bilder): neu, verschoben (per Hash), gelöscht
            committed += self._commit_binaries(dirty - handled, deleted - handled, skipped)
            # 3. Gelöschte Markdown-Dokumente
            for rel in sorted(deleted - handled):
                if not is_markdown(rel):
                    continue
                committed.append(self._commit_deleted(rel))
        return {"status": "ok", "committed": committed, "skipped": skipped}

    def _commit_deleted(self, rel: str) -> dict[str, Any]:
        old = load_text_doc(rel, self.git.show_file("HEAD", rel))
        title = old.title
        if old.id:
            msg = build_message(title, "deleted", f"gelöscht: {rel}", old.id, old.version or 1, "user")
        else:
            msg = f"doc: {title} deleted\n\ngelöscht: {rel}\n\nPKM-Source: user\n"
        sha = self.git.commit_paths([rel], msg, as_user=True)
        return {"path": rel, "id": old.id, "deleted": True, "commit": sha[:10]}

    def _commit_binaries(self, dirty: set[str], deleted: set[str], skipped: list) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        old_hashes = {}
        for rel in sorted(deleted):
            if not is_markdown(rel):
                old_hashes[rel] = hashes.sha256_bytes(self.git.show_file("HEAD", rel))
        for rel in sorted(dirty - deleted):
            if is_markdown(rel) or not self.vault.exists(rel):
                continue
            if is_conflict_copy(PurePosixPath(rel).name):
                skipped.append({"path": rel, "reason": "conflict_copy"})
                continue
            h = hashes.sha256_bytes(self.vault.path(rel).read_bytes())
            src = next((o for o, oh in old_hashes.items() if oh == h), None)
            paths = [rel]
            if src:
                paths.append(src)
                del old_hashes[src]
                note, label = f"verschoben: {src} → {rel}", "moved"
            else:
                note, label = "neu oder geändert", "added"
            msg = f"file: {PurePosixPath(rel).name} {label}\n\n{note}\n\nPKM-Source: user\n"
            sha = self.git.commit_paths(paths, msg, as_user=True)
            out.append({"path": rel, "moved_from": src, "sha256": h, "commit": sha[:10]})
        for rel in sorted(old_hashes):
            msg = f"file: {PurePosixPath(rel).name} deleted\n\ngelöscht: {rel}\n\nPKM-Source: user\n"
            sha = self.git.commit_paths([rel], msg, as_user=True)
            out.append({"path": rel, "deleted": True, "commit": sha[:10]})
        return out

    # ------------------------------------------------------------ pending
    def pending(self) -> dict[str, Any]:
        docs, problems = self.documents()
        state = load_state(self.cfg)
        entries: dict[str, dict[str, Any]] = state["documents"]
        dups = self.duplicate_ids(docs)
        for i, paths in dups.items():
            problems.append({"problem": "duplicate_id", "id": i, "paths": paths})
        result: dict[str, list] = {"new": [], "changed": [], "meta_changed": [], "moved": [], "deleted": []}
        present: set[str] = set()
        for doc in docs:
            if doc.kind == "md" and doc.error:
                continue
            key = state_key(doc)
            if doc.kind == "md" and not key:
                result["new"].append({"id": None, "path": doc.rel, "title": doc.title, "missing_id": True})
                continue
            if key in dups:
                entry = entries.get(key)
                if not entry or entry.get("path") != doc.rel:
                    continue  # Duplikat: nur die bekannte Fassung verarbeiten
            assert key is not None
            present.add(key)
            entry = entries.get(key)
            base = {"id": doc.id, "path": doc.rel, "title": doc.title}
            if doc.kind == "bin":
                base = {"id": None, "key": key, "path": doc.rel, "title": doc.title}
            if entry and entry.get("path") and entry["path"] != doc.rel:
                result["moved"].append({**base, "from": entry["path"], "to": doc.rel})
            info = classify(doc, entry)
            if info is None:
                continue
            category = info.pop("category")
            result.setdefault(category, []).append({**base, **info})
        for key, entry in sorted(entries.items()):
            if key in present:
                continue
            item = {"key": key, "path": entry.get("path"), "processed_version": entry.get("processed_version"),
                    "wiki_pages": entry.get("wiki_pages", [])}
            if not key.startswith("sha:"):
                item["id"] = key
            result["deleted"].append(item)
        result.pop("invalid", None)
        counts = {k: len(v) for k, v in result.items()}
        return {"status": "ok", **result, "problems": problems, "counts": counts}

    # --------------------------------------------------------------- mark
    def mark(self, targets: list[str], pages: list[str] | None = None, remove: bool = False) -> dict[str, Any]:
        with self.writer.lock():
            state = load_state(self.cfg)
            docs_state: dict[str, Any] = state["documents"]
            page_refs = [page_ref(self.svc.resolve(p, ("wiki",))) for p in (pages or [])]
            marked = []
            for target in targets:
                if remove:
                    key = target[3:] if target.startswith("id:") else target
                    if key not in docs_state:
                        raise PkmError("not_found", f"Kein Eintrag in state.json: {target}")
                    del docs_state[key]
                    marked.append({"key": key, "removed": True})
                    continue
                ref = f"id:{target}" if is_valid_id(target) else target
                doc = self.vault.load(self.svc.resolve(ref, ("documents",)))
                if doc.kind == "md" and (doc.error or not doc.id or doc.hashes is None):
                    raise PkmError("invalid_argument", f"{doc.rel} hat keine gültige ID/Frontmatter.", path=doc.rel)
                key = state_key(doc)
                assert key is not None
                old = docs_state.get(key, {})
                wiki_pages = list(dict.fromkeys([*old.get("wiki_pages", []), *page_refs]))
                now = self.svc.now().isoformat(timespec="seconds")
                if doc.kind == "bin":
                    entry = {"path": doc.rel, "processed_at": now, "wiki_pages": wiki_pages}
                else:
                    assert doc.hashes is not None
                    entry = {
                        "path": doc.rel,
                        "processed_version": doc.version,
                        "file_hash": doc.hashes.file_hash,
                        "body_hash": doc.hashes.body_hash,
                        "meta_hash": doc.hashes.meta_hash,
                        "sections": dict(doc.hashes.sections),
                        "processed_at": now,
                        "wiki_pages": wiki_pages,
                    }
                docs_state[key] = entry
                marked.append({"key": key, "path": doc.rel, "version": entry.get("processed_version")})
            self.save_state(state)
        return {"status": "ok", "marked": marked}

    def save_state(self, state: dict[str, Any]) -> None:
        state["version"] = FORMAT
        state["documents"] = dict(sorted(state["documents"].items()))
        text = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
        p = self.cfg.state_path
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(".state.json.tmp")
        tmp.write_bytes(encode(text))
        os.replace(tmp, p)

    # ---------------------------------------------------------------- sha
    def sha(self, target: str, section: str | None = None, full: bool = False) -> dict[str, Any]:
        doc = self.svc.load(target)
        cut = (lambda h: h) if full else hashes.short
        if doc.kind == "bin":
            return {"status": "ok", "path": doc.rel, "file_hash": cut(doc.bin_hash or "")}
        if doc.hashes is None:
            raise PkmError(doc.error or "invalid_encoding", doc.error_message or "Datei nicht lesbar.")
        if section is not None:
            key = normalize_key_input(section)
            if key not in doc.hashes.sections:
                raise PkmError("not_found", f"Abschnitt nicht gefunden: {section}",
                               sections=list(doc.hashes.sections))
            return {"status": "ok", "path": doc.rel, "id": doc.id, "version": doc.version,
                    "section": key, "sha": cut(doc.hashes.sections[key])}
        return {
            "status": "ok", "path": doc.rel, "id": doc.id, "version": doc.version,
            "sections": {k: cut(v) for k, v in doc.hashes.sections.items()},
            "body_hash": cut(doc.hashes.body_hash), "meta_hash": cut(doc.hashes.meta_hash),
            "file_hash": cut(doc.hashes.file_hash),
        }

    # -------------------------------------------------------- commit-wiki
    def commit_wiki(self, message: str) -> dict[str, Any]:
        message = " ".join((message or "").split())
        if not message:
            raise PkmError("invalid_argument", "--message fehlt.")
        if not message.startswith("pkm:"):
            message = f"pkm: {message}"
        with self.writer.lock():
            self.git.require_ok()
            paths = [p for p in WIKI_COMMIT_PATHS if (self.cfg.root / p).exists()]
            if not self.git.has_changes(*paths):
                return {"status": "unchanged", "commit": None}
            files = [p for _xy, p in self.git.status_entries(*paths)]
            sha = self.git.commit_paths(paths, f"{message}\n\nPKM-Source: agent\n")
        return {"status": "ok", "commit": sha[:10], "files": files}
