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


def section_changes(old: dict[str, str], new: dict[str, str]) -> list[dict[str, str]]:
    """Abschnittsvergleich nach 4.8: added, removed, changed, renamed.

    Ein entfallener und ein neuer Inhalt mit gleichem Hash gelten als `renamed`. Das erkennt
    auch Verschiebungen der Duplikat-Nummerierung (`Notizen#2` → `Notizen`).
    """
    same = {k for k in new if old.get(k) == new[k]}
    new_open = [k for k in new if k not in same]
    old_open = [k for k in old if k not in same]
    consumed: set[str] = set()
    renamed: dict[str, str] = {}
    for n in new_open:
        src = next((o for o in old_open if o != n and o not in consumed and old[o] == new[n]), None)
        if src is not None:
            consumed.add(src)
            renamed[n] = src
    changes: list[dict[str, str]] = []
    for n in new_open:
        if n in renamed:
            changes.append({"key": n, "change": "renamed", "from": renamed[n]})
        elif n in old and n not in consumed:
            changes.append({"key": n, "change": "changed"})
        else:
            changes.append({"key": n, "change": "added"})
    for o in old_open:
        if o in consumed:
            continue
        if o in new and o not in renamed:
            continue  # bereits als changed gemeldet
        changes.append({"key": o, "change": "removed"})
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
