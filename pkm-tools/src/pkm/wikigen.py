"""Generierte Wiki-Dateien: `wiki/index.md` (4.3) und `wiki/_status.md` (4.4)."""

from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from .errors import PkmError
from .normalize import encode
from .state import load_state
from .vault import Doc, summary_of

if TYPE_CHECKING:
    from .service import Service

GENERATED = {"wiki/index.md", "wiki/_status.md", "wiki/log.md"}
TYPE_HEADINGS = [
    ("topic", "Themen"),
    ("entity", "Entitäten"),
    ("summary", "Zusammenfassungen"),
    ("synthesis", "Synthesen"),
]
FOLDER_TYPES = {"topics": "topic", "entities": "entity", "summaries": "summary", "syntheses": "synthesis"}
INBOX = "documents/_inbox/"


def wiki_pages(svc: Service) -> list[Doc]:
    pages = []
    for rel in svc.vault.iter_files(("wiki",)):
        if rel in GENERATED or rel.startswith("wiki/_lint/") or not rel.lower().endswith(".md"):
            continue
        try:
            pages.append(svc.vault.load(rel))
        except PkmError:
            continue
    return pages


def page_type(doc: Doc) -> str:
    t = doc.meta.get("type")
    if isinstance(t, str) and t:
        return t
    parts = doc.rel.split("/")
    return FOLDER_TYPES.get(parts[1], "") if len(parts) > 2 else ""


def source_count(doc: Doc) -> int:
    sources = doc.meta.get("sources")
    return len(sources) if isinstance(sources, list) else 0


def write_if_changed(svc: Service, rel: str, text: str) -> bool:
    p = svc.vault.path(rel)
    data = encode(text)
    if p.exists() and p.read_bytes() == data:
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".pkm-tmp-{p.name}")
    tmp.write_bytes(data)
    tmp.replace(p)
    return True


def build_index(svc: Service) -> dict[str, Any]:
    pages = wiki_pages(svc)
    groups: dict[str, list[Doc]] = {}
    for doc in pages:
        groups.setdefault(page_type(doc), []).append(doc)
    lines = ["# Wiki-Index", ""]
    known = [t for t, _ in TYPE_HEADINGS]
    order = TYPE_HEADINGS + [(t, "Sonstige" if not t else f"Sonstige ({t})") for t in sorted(groups) if t not in known]
    for t, heading in order:
        docs = sorted(groups.get(t, []), key=lambda d: (d.title.casefold(), d.rel))
        if not docs:
            continue
        lines += [f"## {heading}", ""]
        for d in docs:
            summary = summary_of(d) or "_(keine Kurzfassung)_"
            n = source_count(d)
            updated = str(d.meta.get("updated") or "")
            info = f"{n} {'Quelle' if n == 1 else 'Quellen'}" + (f", {updated}" if updated else "")
            lines.append(f"- {d.wikilink} – {summary} _({info})_")
        lines.append("")
    if len(lines) == 2:
        lines += ["_Noch keine Seiten._", ""]
    changed = write_if_changed(svc, "wiki/index.md", "\n".join(lines))
    return {"status": "ok", "pages": len(pages), "changed": changed}


def suggest_folder(svc: Service, doc: Doc, all_docs: list[Doc]) -> str | None:
    """Ordner, in dem die meisten Dokumente mit gleichen `topics` liegen."""
    topics = doc.meta.get("topics")
    if not isinstance(topics, list) or not topics:
        return None
    wanted = {str(t).casefold() for t in topics}
    votes: Counter[str] = Counter()
    for other in all_docs:
        if other.rel.startswith(INBOX) or other.rel.startswith("documents/_attachments/"):
            continue
        other_topics = other.meta.get("topics")
        if isinstance(other_topics, list) and wanted & {str(t).casefold() for t in other_topics}:
            votes[str(PurePosixPath(other.rel).parent) + "/"] += 1
    if not votes:
        return None
    return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _quote_keys(keys: list[str]) -> str:
    return ", ".join(f"„{k}“" for k in keys)


def build_status(svc: Service, questions: list[str] | None = None) -> dict[str, Any]:
    from .maint import Maintenance

    pend = Maintenance(svc).pending()
    docs, _ = Maintenance(svc).documents()
    unprocessed: list[str] = []
    for item in pend["new"]:
        version = f" (v{item.get('version')})" if item.get("version") else ""
        extra = ", ohne ID" if item.get("missing_id") else ""
        unprocessed.append(f"- {_link(item['path'])} – neu{version}{extra}")
    for item in pend["changed"]:
        keys = [c["key"] for c in item.get("sections", [])]
        what = f"geändert: {_quote_keys(keys)}" if keys else "nur Reihenfolge geändert"
        unprocessed.append(f"- {_link(item['path'])} – v{item.get('processed_version')} → v{item.get('version')}, {what}")
    for item in pend["meta_changed"]:
        unprocessed.append(
            f"- {_link(item['path'])} – v{item.get('processed_version')} → v{item.get('version')}, nur Metadaten"
        )
    for item in pend["moved"]:
        unprocessed.append(f"- {_link(item['to'])} – verschoben von {item['from']}")
    for item in pend["deleted"]:
        pages = ", ".join(item.get("wiki_pages") or []) or "keine Wiki-Seiten"
        unprocessed.append(f"- {item.get('path')} – gelöscht (zuletzt v{item.get('processed_version')}), betrifft: {pages}")

    state = load_state(svc.cfg)["documents"]
    pending_paths = {i["path"] for k in ("new", "changed", "meta_changed") for i in pend[k]}
    inbox_done: list[str] = []
    for doc in docs:
        if not doc.rel.startswith(INBOX) or doc.rel in pending_paths:
            continue
        key = doc.id if doc.kind == "md" else f"sha:{doc.bin_hash}"
        if key and key in state:
            folder = suggest_folder(svc, doc, docs)
            hint = f"Vorschlag: {folder}" if folder else "kein Vorschlag"
            inbox_done.append(f"- {_link(doc.rel)} → {hint}")

    problems: list[str] = []
    for p in pend["problems"]:
        if p["problem"] == "conflict_copy":
            problems.append(f"- Nextcloud-Konfliktkopie: {p['path']} (bitte in Obsidian zusammenführen)")
        elif p["problem"] == "duplicate_id":
            problems.append(f"- Doppelte ID {p['id']}: {', '.join(p['paths'])}")
        elif p["problem"] == "case_collision":
            problems.append(f"- Nur in Groß-/Kleinschreibung verschieden: {', '.join(p['paths'])}")
        else:
            problems.append(f"- {p['problem']}: {p.get('path')} – {p.get('message') or ''}".rstrip(" –"))

    lines = ["# Status", "", f"## Noch nicht verarbeitet ({len(unprocessed)})", *unprocessed, "",
             f"## Noch im Eingang, bereits verarbeitet ({len(inbox_done)})", *inbox_done, "",
             f"## Probleme ({len(problems)})", *problems, ""]
    if questions:
        lines += [f"## Rückfragen ({len(questions)})", *[f"- {q}" for q in questions], ""]
    changed = write_if_changed(svc, "wiki/_status.md", "\n".join(lines))
    return {"status": "ok", "unprocessed": len(unprocessed), "inbox_processed": len(inbox_done),
            "problems": len(problems), "changed": changed}


def _link(rel: str) -> str:
    return f"[[{rel[:-3] if rel.lower().endswith('.md') else rel}]]"
