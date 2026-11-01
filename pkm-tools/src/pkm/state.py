"""Verarbeitungsstand `.pkm/state.json` und Vergleich nach Spezifikation 4.6/4.8."""

from __future__ import annotations

import json
from typing import Any

from .config import Config
from .errors import PkmError
from .vault import Doc

FORMAT = 1


def load_state(cfg: Config) -> dict[str, Any]:
    p = cfg.state_path
    if not p.is_file():
        return {"version": FORMAT, "documents": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PkmError("invalid_state", f"state.json nicht lesbar: {exc}") from exc
    data.setdefault("documents", {})
    return data


def state_key(doc: Doc) -> str | None:
    if doc.kind == "bin":
        return f"sha:{doc.bin_hash}"
    return doc.id


def section_changes(
    old: dict[str, str], new: dict[str, str]
) -> list[dict[str, str]]:
    """Abschnittsvergleich: added, removed, changed, renamed (gleicher Hash)."""
    removed = [k for k in old if k not in new]
    added = [k for k in new if k not in old]
    changes: list[dict[str, str]] = []
    for k in new:
        if k in old and old[k] != new[k]:
            changes.append({"key": k, "change": "changed"})
    used_added: set[str] = set()
    still_removed: list[str] = []
    for r in removed:
        match = next((a for a in added if a not in used_added and new[a] == old[r]), None)
        if match is not None:
            used_added.add(match)
            changes.append({"key": match, "change": "renamed", "from": r})
        else:
            still_removed.append(r)
    for a in added:
        if a not in used_added:
            changes.append({"key": a, "change": "added"})
    for r in still_removed:
        changes.append({"key": r, "change": "removed"})
    return changes


def classify(doc: Doc, entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """None = aktueller Stand ist verarbeitet. Sonst Kategorie new/changed/meta_changed."""
    if doc.kind == "bin":
        return None if entry else {"category": "new"}
    if doc.hashes is None or doc.error:
        return {"category": "invalid", "error": doc.error}
    if not entry:
        return {"category": "new", "version": doc.version}
    same_body = entry.get("body_hash") == doc.hashes.body_hash
    same_meta = entry.get("meta_hash") == doc.hashes.meta_hash
    base = {"processed_version": entry.get("processed_version"), "version": doc.version}
    if same_body and same_meta:
        return None
    if same_body:
        return {"category": "meta_changed", **base}
    return {
        "category": "changed",
        **base,
        "sections": section_changes(entry.get("sections") or {}, doc.hashes.sections),
    }
