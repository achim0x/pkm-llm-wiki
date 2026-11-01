"""Belege: Parser, Auflösung, show_citations, fix-/sync-citations (Spezifikation 4.2, 5.2, 7.3)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import quote as urlquote

from . import hashes
from .errors import PkmError
from .frontmatter import set_fields_linewise
from .ids import is_valid_id
from .parse import PREAMBLE, Parsed, body_lines, normalize_key_input
from .vault import Doc, is_markdown, load_text_doc

if TYPE_CHECKING:
    from .service import Service

DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:[ \t]*(.*)$")
REF_RE = re.compile(r"\[\^([^\]\s]+)\](?!:)")
LINK_RE = re.compile(r"^!?\[\[([^\]\|#]*)(?:#([^\]\|]*))?(?:\|[^\]]*)?\]\]")
SEP_RE = re.compile(r"\s+·\s+")
LIST_ITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
QUOTE_PAIRS = (("„", "“"), ("“", "”"), ('"', '"'), ("»", "«"), ("«", "»"))
MAX_QUOTE = 200
MAX_EXCERPT = 1500
CONTENT_SECTIONS = ("Inhalt", "Widersprüche / offene Fragen")


@dataclass
class Citation:
    label: str
    line: int  # Zeilenindex im Body
    raw: str
    path: str | None = None
    anchor: str | None = None
    page: int | None = None
    explicit_key: str | None = None  # §:
    quote: str | None = None
    doc_id: str | None = None
    version: int | None = None
    sha: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def markdown(self) -> bool:
        if not self.path:
            return True
        suffix = PurePosixPath(self.path).suffix.lower()
        return suffix in ("", ".md")

    @property
    def target_rel(self) -> str | None:
        if not self.path:
            return None
        if self.markdown and not self.path.lower().endswith(".md"):
            return f"{self.path}.md"
        return self.path

    @property
    def link_path(self) -> str | None:
        if not self.path:
            return None
        return self.path[:-3] if self.path.lower().endswith(".md") else self.path

    @property
    def section_key(self) -> str | None:
        if not self.markdown:
            return None
        if self.explicit_key:
            return self.explicit_key
        if self.anchor:
            return normalize_key_input(self.anchor)
        return PREAMBLE


@dataclass
class Statement:
    text: str
    labels: list[str]
    section: str
    line: int
    segments: list[tuple[str, list[str]]] = field(default_factory=list)  # Text bis zur Fußnotengruppe

    def labels_for(self, needle: str) -> list[str]:
        """Belege für ein Textstück: die Fußnoten direkt nach der Stelle, sonst die des Absatzes."""
        for text, labels in self.segments:
            if needle in _norm_ws(text):
                return labels or self.labels
        return self.labels


REF_GROUP_RE = re.compile(r"((?:\[\^[^\]\s]+\](?!:))+)")


def _segments(text: str) -> list[tuple[str, list[str]]]:
    parts = REF_GROUP_RE.split(text)
    out: list[tuple[str, list[str]]] = []
    for i in range(0, len(parts), 2):
        seg = parts[i]
        labels = [m.group(1) for m in REF_RE.finditer(parts[i + 1])] if i + 1 < len(parts) else []
        if seg.strip() or labels:
            out.append((_clean_statement(seg), labels))
    return out


@dataclass
class PageCitations:
    doc: Doc
    definitions: dict[str, Citation]
    references: list[tuple[str, int]]
    statements: list[Statement]

    def labels_in_order(self) -> list[str]:
        seen: list[str] = []
        for label, _ in self.references:
            if label not in seen:
                seen.append(label)
        for label in self.definitions:
            if label not in seen:
                seen.append(label)
        return seen

    def statement_for(self, label: str) -> str | None:
        for st in self.statements:
            if label in st.labels:
                return st.text
        return None


def _strip_quote(part: str) -> str | None:
    for left, right in QUOTE_PAIRS:
        if part.startswith(left) and part.endswith(right) and len(part) >= 2:
            return part[len(left) : len(part) - len(right)]
    return None


def parse_citation(label: str, rest: str, line: int) -> Citation:
    cit = Citation(label, line, rest)
    parts = [p.strip() for p in SEP_RE.split(rest.strip()) if p.strip()]
    if not parts:
        cit.problems.append("leer")
        return cit
    first = parts[0]
    m = LINK_RE.match(first)
    if m:
        cit.path = m.group(1).strip() or None
        anchor = (m.group(2) or "").strip() or None
        if anchor and re.fullmatch(r"page=\d+", anchor):
            cit.page = int(anchor.split("=", 1)[1])
        cit.anchor = anchor
        tail = first[m.end() :].strip()
        parts = ([tail] if tail else []) + parts[1:]
    else:
        cit.problems.append("Link fehlt")
    for part in parts:
        if part.startswith("§:"):
            cit.explicit_key = part[2:].strip() or None
        elif part.startswith("id:"):
            cit.doc_id = part[3:].strip()
            if not is_valid_id(cit.doc_id):
                cit.problems.append("ungültige ID")
        elif part.startswith("v:"):
            value = part[2:].strip()
            if value.isdigit():
                cit.version = int(value)
            else:
                cit.problems.append("ungültige Version")
        elif part.startswith("sha:"):
            value = part[4:].strip().lower()
            if re.fullmatch(r"[0-9a-f]{6,64}", value):
                cit.sha = value
            else:
                cit.problems.append("ungültiger sha")
        elif (q := _strip_quote(part)) is not None:
            cit.quote = q
        else:
            cit.problems.append(f"unbekannter Teil: {part[:40]}")
    if cit.sha is None:
        cit.problems.append("sha fehlt")
    if cit.markdown:
        if cit.doc_id is None:
            cit.problems.append("id fehlt")
        if cit.version is None:
            cit.problems.append("v fehlt")
        if cit.quote is None:
            cit.problems.append("Zitat fehlt")
    if cit.quote is not None and len(cit.quote) > MAX_QUOTE:
        cit.problems.append(f"Zitat länger als {MAX_QUOTE} Zeichen")
    return cit


def _clean_statement(text: str) -> str:
    text = REF_RE.sub("", text)
    text = LIST_ITEM_RE.sub("", text, count=1)
    return " ".join(text.split())


def _block_statements(block: list[tuple[int, str]], section: str) -> list[Statement]:
    """Absatz → Aussage; in Listen ist jeder Eintrag eine eigene Aussage."""
    if not block:
        return []
    items = [block] if not any(LIST_ITEM_RE.match(t) for _, t in block) else [[b] for b in block]
    out = []
    for item in items:
        text = " ".join(t for _, t in item)
        labels = [r.group(1) for r in REF_RE.finditer(text)]
        clean = _clean_statement(text)
        if clean:
            out.append(Statement(clean, labels, section, item[0][0], _segments(text)))
    return out


def parse_page(doc: Doc) -> PageCitations:
    if doc.parsed is None:
        raise PkmError(doc.error or "invalid_encoding", doc.error_message or "Seite nicht lesbar.", path=doc.rel)
    lines = body_lines(doc.parsed.body)
    definitions: dict[str, Citation] = {}
    references: list[tuple[str, int]] = []
    def_lines: set[int] = set()
    for i, line in enumerate(lines):
        m = DEF_RE.match(line)
        if m:
            definitions.setdefault(m.group(1), parse_citation(m.group(1), m.group(2), i))
            def_lines.add(i)
            continue
        for ref in REF_RE.finditer(line):
            references.append((ref.group(1), i))
    statements: list[Statement] = []
    for sec in doc.parsed.sections:
        start = sec.start + (1 if sec.heading is not None else 0)
        block: list[tuple[int, str]] = []
        for i in range(start, sec.end):
            if i in def_lines or not lines[i].strip():
                statements += _block_statements(block, sec.key)
                block = []
            else:
                block.append((i, lines[i]))
        statements += _block_statements(block, sec.key)
    return PageCitations(doc, definitions, references, statements)


# ------------------------------------------------------------- Auflösung (5.2)
@dataclass
class Resolution:
    status: str  # ok | moved | newer_version | missing
    current_path: str | None
    moved: bool
    doc: Doc | None
    current_version: int | None
    cited_text: str | None = None  # Abschnitt in der belegten Version
    cited_sections: dict[str, str] | None = None


class Resolver:
    def __init__(self, svc: Service) -> None:
        self.svc = svc
        self._versions: dict[tuple[str, int], Doc | None] = {}
        self._bin_index: dict[str, list[str]] | None = None

    def version_doc(self, doc_id: str, version: int) -> Doc | None:
        key = (doc_id, version)
        if key not in self._versions:
            try:
                path, text = self.svc.text_at_version(doc_id, version)
                self._versions[key] = load_text_doc(path, text.encode("utf-8"))
            except PkmError:
                self._versions[key] = None
        return self._versions[key]

    def _bins(self) -> dict[str, list[str]]:
        if self._bin_index is None:
            index: dict[str, list[str]] = {}
            for rel in self.svc.vault.iter_files(("documents",)):
                if not is_markdown(rel):
                    try:
                        h = hashes.sha256_bytes(self.svc.vault.path(rel).read_bytes())
                    except OSError:
                        continue
                    index.setdefault(h, []).append(rel)
            self._bin_index = index
        return self._bin_index

    def _load(self, rel: str | None) -> Doc | None:
        if not rel:
            return None
        try:
            if not rel.startswith("documents/") or not self.svc.vault.exists(rel):
                return None
            return self.svc.vault.load(rel)
        except PkmError:
            return None

    def resolve(self, cit: Citation) -> Resolution:
        if not cit.markdown:
            return self._resolve_bin(cit)
        doc, moved = None, False
        candidate = self._load(cit.target_rel)
        if candidate is not None and (cit.doc_id is None or candidate.id == cit.doc_id):
            doc = candidate
        elif cit.doc_id and is_valid_id(cit.doc_id):
            found = [p for p in self.svc.find_id(cit.doc_id) if p.startswith("documents/")]
            if found:
                doc, moved = self._load(found[0]), True
        cited = self.version_doc(cit.doc_id, cit.version) if cit.doc_id and cit.version else None
        key = cit.section_key
        cited_text = None
        cited_sections = cited.hashes.sections if cited and cited.hashes else None
        if cited and cited.parsed and key:
            sec = cited.parsed.section(key)
            if sec is not None:
                cited_text = render_section(sec)
        if doc is None:
            return Resolution("missing", None, False, None, None, cited_text, cited_sections)
        status = "moved" if moved else "ok"
        if cit.version is not None and doc.version is not None and cit.version < doc.version:
            current = doc.hashes.sections.get(key or "") if doc.hashes else None
            if not (current and cit.sha and hashes.matches(current, cit.sha)):
                status = "newer_version"
        return Resolution(status, doc.rel, moved, doc, doc.version, cited_text, cited_sections)

    def _resolve_bin(self, cit: Citation) -> Resolution:
        rel = cit.target_rel
        if rel and rel.startswith("documents/") and self.svc.vault.exists(rel):
            h = hashes.sha256_bytes(self.svc.vault.path(rel).read_bytes())
            if not cit.sha or hashes.matches(h, cit.sha):
                return Resolution("ok", rel, False, None, None)
        if cit.sha:
            for h, paths in self._bins().items():
                if hashes.matches(h, cit.sha):
                    return Resolution("moved", sorted(paths)[0], True, None, None)
        return Resolution("missing", None, False, None, None)


def render_section(sec: Any) -> str:
    lines = ([sec.heading] if sec.heading else []) + list(sec.content_lines)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def section_text(doc: Doc, key: str | None) -> str | None:
    if doc.parsed is None or key is None:
        return None
    sec = doc.parsed.section(key)
    return render_section(sec) if sec is not None else None


def _excerpt(text: str | None) -> str | None:
    if text is None:
        return None
    return text if len(text) <= MAX_EXCERPT else text[:MAX_EXCERPT] + "…"


def _norm_ws(text: str) -> str:
    return " ".join(text.split()).casefold()


def obsidian_link(vault_name: str | None, rel: str | None) -> str | None:
    if not vault_name or not rel:
        return None
    file = rel[:-3] if rel.lower().endswith(".md") else rel
    return f"obsidian://open?vault={urlquote(vault_name, safe='')}&file={urlquote(file, safe='')}"


def citations_overview(pc: PageCitations) -> list[dict[str, Any]]:
    """Geparste Belege ohne Prüfung (für `read` von Wiki-Seiten)."""
    return [
        {
            "id": c.label, "path": c.path, "anchor": c.anchor, "section": c.section_key, "quote": c.quote,
            "doc_id": c.doc_id, "version": c.version, "sha": c.sha, "statement": pc.statement_for(c.label),
            "problems": c.problems,
        }
        for c in pc.definitions.values()
    ]


def show_citations(svc: Service, target: str, statement: str | None = None,
                   with_excerpt: bool = False) -> dict[str, Any]:
    rel = svc.resolve(target, ("wiki",))
    pc = parse_page(svc.vault.load(rel))
    labels = pc.labels_in_order()
    if statement:
        needle = _norm_ws(statement)
        matching = [st for st in pc.statements if needle in _norm_ws(st.text)]
        if not matching:
            raise PkmError("not_found", "Keine Aussage mit diesem Text auf der Seite gefunden.", page=rel)
        wanted = {lab for st in matching for lab in st.labels_for(needle)}
        labels = [lab for lab in labels if lab in wanted]
    resolver = Resolver(svc)
    out = []
    for label in labels:
        cit = pc.definitions.get(label)
        if cit is None:
            out.append({"id": label, "status": "missing_definition", "statement": pc.statement_for(label)})
            continue
        res = resolver.resolve(cit)
        entry: dict[str, Any] = {
            "id": label,
            "statement": pc.statement_for(label),
            "original": res.current_path,
            "anchor": cit.anchor,
            "section": cit.section_key,
            "quote": cit.quote,
            "doc_id": cit.doc_id,
            "cited_version": cit.version,
            "current_version": res.current_version,
            "status": res.status,
        }
        if cit.problems:
            entry["problems"] = cit.problems
        if with_excerpt and cit.markdown:
            entry["cited_excerpt"] = _excerpt(res.cited_text)
            current = section_text(res.doc, cit.section_key) if res.doc else None
            if current is not None and current != res.cited_text:
                entry["current_excerpt"] = _excerpt(current)
        link = obsidian_link(svc.cfg.vault_name, res.current_path)
        if link:
            entry["obsidian_link"] = link
        out.append(entry)
    return {"status": "ok", "page": rel, "citations": out}


# ------------------------------------------------------------- Seiten ändern
def _wiki_targets(svc: Service, pages: list[str] | None) -> list[str]:
    if pages:
        return [svc.resolve(p, ("wiki",)) for p in pages]
    from .wikigen import wiki_pages

    return [d.rel for d in wiki_pages(svc)]


def _render_first(link_path: str, key: str | None, page: int | None) -> str:
    anchor = None
    explicit = None
    if page is not None:
        anchor = f"page={page}"
    elif key and key != PREAMBLE:
        base, sep, num = key.rpartition("#")
        if sep and num.isdigit() and base:
            anchor, explicit = base, key
        else:
            anchor = key
    link = f"[[{link_path}{'#' + anchor if anchor else ''}]]"
    return link + (f" §:{explicit}" if explicit else "")


def rewrite_definition(cit: Citation, link_path: str, key: str | None) -> str:
    parts = [p.strip() for p in SEP_RE.split(cit.raw.strip()) if p.strip()]
    m = LINK_RE.match(parts[0]) if parts else None
    tail = parts[0][m.end():].strip() if m else ""
    rest = ([tail] if tail else []) + parts[1:]
    rest = [p for p in rest if not p.startswith("§:")]
    return f"[^{cit.label}]: " + " · ".join([_render_first(link_path, key, cit.page), *rest])


def _write_page(svc: Service, rel: str, text: str) -> None:
    from .wikigen import write_if_changed

    write_if_changed(svc, rel, text)


def fix_citations(svc: Service, pages: list[str] | None = None) -> dict[str, Any]:
    resolver = Resolver(svc)
    changes = []
    for rel in _wiki_targets(svc, pages):
        doc = svc.vault.load(rel)
        if doc.parsed is None or doc.error:
            continue
        pc = parse_page(doc)
        lines = body_lines(doc.parsed.body)
        page_changes = []
        for cit in pc.definitions.values():
            if not cit.path:
                continue
            res = resolver.resolve(cit)
            new_path = cit.link_path
            if res.moved and res.current_path:
                new_path = res.current_path[:-3] if res.current_path.lower().endswith(".md") else res.current_path
            new_key = cit.section_key
            if res.doc is not None and res.doc.hashes and new_key and new_key not in res.doc.hashes.sections and cit.sha:
                match = [k for k, h in res.doc.hashes.sections.items() if hashes.matches(h, cit.sha)]
                if len(match) == 1:
                    new_key = match[0]
            if new_path == cit.link_path and new_key == cit.section_key:
                continue
            new_line = rewrite_definition(cit, new_path or "", new_key)
            if new_line != lines[cit.line]:
                page_changes.append({"id": cit.label, "old": lines[cit.line], "new": new_line})
                lines[cit.line] = new_line
        if page_changes:
            _write_page(svc, rel, doc.parsed.frontmatter_text + "\n".join(lines) + "\n")
            sync_citations(svc, [rel])
            changes.append({"page": rel, "changes": page_changes})
    return {"status": "ok", "pages_changed": len(changes), "changes": changes}


def expected_sources(pc: PageCitations) -> list[str]:
    links = {f"[[{c.link_path}]]" for c in pc.definitions.values() if c.link_path}
    return sorted(links)


def sync_citations(svc: Service, pages: list[str] | None = None) -> dict[str, Any]:
    changed = []
    for rel in _wiki_targets(svc, pages):
        doc = svc.vault.load(rel)
        if doc.parsed is None or doc.error:
            continue
        sources = expected_sources(parse_page(doc))
        if doc.meta.get("sources") == sources:
            continue
        text = set_fields_linewise(doc.text or "", {"sources": sources}, block_lists=True)
        _write_page(svc, rel, text)
        changed.append({"page": rel, "sources": sources})
    return {"status": "ok", "pages_changed": len(changed), "changes": changed}


def page_citations_for_read(doc: Doc) -> list[dict[str, Any]]:
    try:
        return citations_overview(parse_page(doc))
    except PkmError:
        return []


__all__ = [
    "CONTENT_SECTIONS", "Citation", "PageCitations", "Parsed", "Resolver", "fix_citations", "parse_page",
    "show_citations", "sync_citations", "_norm_ws",
]
