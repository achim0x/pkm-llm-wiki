"""`pkm lint` (Spezifikation 8, 4.8): Struktur, Belege, Dokumente, Plattform. JSON-Bericht."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from . import hashes
from .citations import CONTENT_SECTIONS, Resolver, _norm_ws, expected_sources, parse_page
from .errors import PkmError
from .parse import body_lines, find_setext
from .paths import case_collisions, is_conflict_copy, is_platform_safe_name
from .vault import Doc, extract_links, is_markdown, link_key, summary_of
from .wikigen import FOLDER_TYPES, GENERATED, wiki_pages

if TYPE_CHECKING:
    from .service import Service

WIKI_TYPES = ("topic", "entity", "summary", "synthesis")
CONFIDENCE = ("high", "medium", "low")
BAD_ANCHOR_CHARS = set("#^[]|")
SUFFIX_LIKE_RE = re.compile(r"#([0-9]+)$")
SEVERITIES = ("error", "warning", "info")


class Report:
    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []

    def add(self, check: str, severity: str, path: str | None, message: str, **detail: Any) -> None:
        item: dict[str, Any] = {"check": check, "severity": severity, "path": path, "message": message}
        if detail:
            item["detail"] = detail
        self.findings.append(item)

    def result(self) -> dict[str, Any]:
        counts = Counter(f["severity"] for f in self.findings)
        return {
            "status": "ok",
            "summary": {s: counts.get(s, 0) for s in SEVERITIES},
            "findings": self.findings,
        }


class Linter:
    def __init__(self, svc: Service) -> None:
        self.svc = svc
        self.vault = svc.vault
        self.r = Report()
        self.all_files = list(self.vault.iter_files())
        self.keys: dict[str, set[str]] = defaultdict(set)
        for rel in self.all_files:
            name = PurePosixPath(rel).name
            stem = name[:-3] if is_markdown(name) else name
            self.keys[link_key(rel)].add(rel)
            self.keys[stem.casefold()].add(rel)
            self.keys[name.casefold()].add(rel)
        self.pages = wiki_pages(svc)
        self.docs: list[Doc] = []
        for rel in self.all_files:
            if rel.startswith("documents/"):
                try:
                    self.docs.append(self.vault.load(rel))
                except PkmError:
                    continue

    def run(self) -> dict[str, Any]:
        self.platform()
        self.documents()
        self.structure()
        self.citations()
        return self.r.result()

    # ------------------------------------------------------------ Plattform
    def platform(self) -> None:
        for rel in self.all_files:
            name = PurePosixPath(rel).name
            if is_conflict_copy(name):
                self.r.add("conflict_copy", "error", rel, "Nextcloud-Konfliktkopie; Fassungen in Obsidian zusammenführen.")
            for part in PurePosixPath(rel).parts:
                if not is_platform_safe_name(part):
                    self.r.add("unsafe_filename", "warning", rel, f"Name „{part}“ ist nicht auf allen Systemen gültig.")
                    break
        for group in case_collisions(self.all_files):
            self.r.add("case_collision", "error", group[0], "Namen unterscheiden sich nur in Groß-/Kleinschreibung.",
                       paths=group)

    # ------------------------------------------------------------ Dokumente
    def documents(self) -> None:
        by_id: dict[str, list[str]] = defaultdict(list)
        git_ok = self.svc.git.problem() is None
        for doc in self.docs:
            if doc.kind != "md":
                continue
            if doc.error:
                self.r.add(doc.error, "error", doc.rel, doc.error_message or doc.error)
                continue
            if is_conflict_copy(PurePosixPath(doc.rel).name):
                continue
            if not doc.id:
                self.r.add("missing_id", "warning", doc.rel, "Dokument ohne gültige ID (pkm ids).")
            else:
                by_id[doc.id].append(doc.rel)
            if doc.version is None:
                self.r.add("missing_version", "warning", doc.rel, "Dokument ohne Version (pkm ids).")
            if git_ok and doc.id and doc.version is not None and not self.svc.git.is_dirty(doc.rel):
                versions = [c.version for c in self.svc.versions(doc.id) if c.path]
                if versions and versions[-1] != doc.version:
                    self.r.add("version_mismatch", "error", doc.rel,
                               f"version {doc.version} passt nicht zum Verlauf (zuletzt v{versions[-1]}).")
            self.headings(doc)
        for doc_id, paths in by_id.items():
            if len(paths) > 1:
                self.r.add("duplicate_id", "error", sorted(paths)[0], f"ID {doc_id} mehrfach vergeben.", paths=sorted(paths))

    def headings(self, doc: Doc) -> None:
        assert doc.parsed is not None
        lines = body_lines(doc.parsed.body)
        for i in find_setext(lines):
            self.r.add("setext_heading", "info", doc.rel,
                       f"Setext-Überschrift (Zeile {i + 1} im Inhalt) ist keine Abschnittsgrenze; bitte # verwenden.")
        headings = [s for s in doc.parsed.sections if s.level]
        bases = {s.base for s in headings}
        reported: set[str] = set()
        for sec in headings:
            if sec.key != sec.base and sec.base not in reported:
                reported.add(sec.base)
                self.r.add("duplicate_heading", "warning", doc.rel, f"Überschrift „{sec.base}“ kommt mehrfach vor.")
            m = SUFFIX_LIKE_RE.search(sec.base)
            if m and sec.key == sec.base:
                stem = sec.base[: m.start()]
                if stem in bases:
                    self.r.add("heading_suffix_collision", "error", doc.rel,
                               f"Überschrift „{sec.base}“ kollidiert mit dem Duplikat-Suffix von „{stem}“; "
                               f"bitte umformulieren (z. B. „{stem} {m.group(1)}“).")
                else:
                    self.r.add("heading_suffix_like", "warning", doc.rel,
                               f"Überschrift „{sec.base}“ endet auf # plus Ziffern und kann mit einem "
                               f"Duplikat-Suffix verwechselt werden; bitte umformulieren (z. B. „{stem} {m.group(1)}“).")
            text = sec.base[: m.start()] if m else sec.base
            if BAD_ANCHOR_CHARS & set(text):
                self.r.add("heading_bad_chars", "warning", doc.rel,
                           f"Überschrift „{sec.base}“ enthält Zeichen, die Obsidian-Anker brechen (# ^ [ ] |).")

    # ------------------------------------------------------------- Struktur
    def resolve_link(self, target: str) -> set[str]:
        return self.keys.get(link_key(target), set())

    def structure(self) -> None:
        incoming: dict[str, int] = Counter()
        unresolved: Counter[str] = Counter()
        for page in self.pages:
            if page.error:
                self.r.add(page.error, "error", page.rel, page.error_message or page.error)
                continue
            folder = page.rel.split("/")[1] if page.rel.count("/") >= 2 else ""
            typ = page.meta.get("type")
            if typ not in WIKI_TYPES:
                self.r.add("invalid_type", "warning", page.rel, f"type fehlt oder ist ungültig: {typ!r}.")
            elif folder in FOLDER_TYPES and FOLDER_TYPES[folder] != typ:
                self.r.add("type_folder_mismatch", "info", page.rel, f"type {typ} passt nicht zum Ordner {folder}/.")
            conf = page.meta.get("confidence")
            if conf is not None and conf not in CONFIDENCE:
                self.r.add("invalid_confidence", "warning", page.rel, f"confidence ungültig: {conf!r}.")
            if not summary_of(page):
                self.r.add("missing_summary", "warning", page.rel, "Kurzfassung (erstes Zitat >) fehlt.")
            for target in extract_links(page.body):
                found = self.resolve_link(target)
                if not found:
                    unresolved[target] += 1
                    self.r.add("broken_link", "error", page.rel, f"Link-Ziel nicht gefunden: [[{target}]].")
                elif len(found) > 1:
                    self.r.add("ambiguous_link", "warning", page.rel, f"Link [[{target}]] ist mehrdeutig.",
                               candidates=sorted(found))
                else:
                    (dest,) = found
                    if dest != page.rel:
                        incoming[dest] += 1
        for page in self.pages:
            if page.rel.split("/")[1] in FOLDER_TYPES and not incoming.get(page.rel):
                self.r.add("orphan_page", "warning", page.rel, "Keine andere Wiki-Seite verweist auf diese Seite.")
        for target, n in unresolved.items():
            if n >= 2:
                self.r.add("missing_page", "info", None, f"[[{target}]] wird {n}-mal verlinkt, die Seite fehlt.")
        names = set()
        for page in self.pages:
            names.add(page.stem.casefold())
            names.add(page.title.casefold())
            aliases = page.meta.get("aliases")
            if isinstance(aliases, list):
                names.update(str(a).casefold() for a in aliases)
        topics: Counter[str] = Counter()
        for doc in self.docs:
            t = doc.meta.get("topics")
            if isinstance(t, list):
                topics.update({str(x).casefold() for x in t})
        for topic, n in sorted(topics.items()):
            if n >= 3 and topic not in names:
                self.r.add("topic_without_page", "info", None, f"Thema „{topic}“ in {n} Dokumenten, aber ohne Wiki-Seite.")

    # --------------------------------------------------------------- Belege
    def citations(self) -> None:
        resolver = Resolver(self.svc)
        for page in self.pages:
            if page.error:
                continue
            pc = parse_page(page)
            labels_ref = {lab for lab, _ in pc.references}
            for label in sorted(labels_ref - set(pc.definitions)):
                self.r.add("footnote_undefined", "error", page.rel, f"Fußnote [^{label}] ohne Definition.")
            for label in sorted(set(pc.definitions) - labels_ref):
                self.r.add("footnote_unused", "info", page.rel, f"Fußnote [^{label}] wird nicht verwendet.")
            for st in pc.statements:
                if st.section in CONTENT_SECTIONS and not st.labels:
                    self.r.add("statement_without_citation", "warning", page.rel,
                               f"Aussage ohne Beleg: „{st.text[:80]}“", section=st.section)
            if page.meta.get("sources") != expected_sources(pc):
                self.r.add("sources_out_of_sync", "warning", page.rel, "sources passt nicht zu den Fußnoten (pkm sync-citations).")
            for cit in pc.definitions.values():
                self.citation(page, cit, resolver)

    def citation(self, page: Doc, cit: Any, resolver: Resolver) -> None:
        where = {"footnote": cit.label}
        for problem in cit.problems:
            self.r.add("citation_format", "error", page.rel, f"[^{cit.label}]: {problem}.", **where)
        if not cit.path:
            return
        target = cit.target_rel or ""
        if not target.startswith("documents/"):
            sev_check = "citation_to_wiki" if target.startswith("wiki/") else "citation_outside_documents"
            self.r.add(sev_check, "error", page.rel, f"[^{cit.label}] zeigt nicht auf documents/: {cit.path}.", **where)
            return
        res = resolver.resolve(cit)
        if res.status == "missing":
            self.r.add("citation_missing", "error", page.rel, f"[^{cit.label}] Original nicht gefunden: {cit.path}.", **where)
        if res.moved:
            self.r.add("citation_moved", "warning", page.rel,
                       f"[^{cit.label}] Original verschoben nach {res.current_path} (pkm fix-citations).", **where)
        if res.status == "newer_version":
            self.r.add("citation_newer_version", "warning", page.rel,
                       f"[^{cit.label}] Abschnitt hat sich seit v{cit.version} geändert (aktuell v{res.current_version}).",
                       **where)
        if not cit.markdown:
            return
        if res.cited_sections is not None:
            key = cit.section_key
            if key not in res.cited_sections:
                self.r.add("anchor_missing", "warning", page.rel,
                           f"[^{cit.label}] Abschnitt „{key}“ gibt es in v{cit.version} nicht.", **where)
            elif cit.sha and not hashes.matches(res.cited_sections[key], cit.sha):
                self.r.add("sha_mismatch", "error", page.rel,
                           f"[^{cit.label}] sha passt nicht zum Abschnitt in v{cit.version}.", **where)
            if cit.quote and res.cited_text is not None and _norm_ws(cit.quote) not in _norm_ws(res.cited_text):
                self.r.add("quote_not_found", "error", page.rel,
                           f"[^{cit.label}] Zitat steht nicht in v{cit.version}, Abschnitt „{key}“.", **where)
        elif cit.doc_id and cit.version and res.status != "missing":
            self.r.add("cited_version_missing", "error", page.rel,
                       f"[^{cit.label}] v{cit.version} von {cit.doc_id} nicht im Verlauf.", **where)


def lint(svc: Service) -> dict[str, Any]:
    return Linter(svc).run()


CHECK_GROUPS = {
    "Plattform": ("conflict_copy", "unsafe_filename", "case_collision"),
    "Dokumente": ("missing_id", "missing_version", "version_mismatch", "duplicate_id", "invalid_encoding",
                  "invalid_frontmatter", "setext_heading", "duplicate_heading", "heading_bad_chars",
                  "heading_suffix_like", "heading_suffix_collision"),
}


def write_report(svc: Service, result: dict[str, Any]) -> str:
    """Bericht nach `wiki/_lint/YYYY-MM-DD.md` (deutsch)."""
    from .wikigen import write_if_changed

    date = svc.now().date().isoformat()
    rel = f"wiki/_lint/{date}.md"
    s = result["summary"]
    lines = [f"# Lint-Bericht {date}", "",
             f"{s['error']} Fehler, {s['warning']} Warnungen, {s['info']} Hinweise.", ""]
    labels = {"error": "Fehler", "warning": "Warnungen", "info": "Hinweise"}
    for sev in SEVERITIES:
        items = [f for f in result["findings"] if f["severity"] == sev]
        if not items:
            continue
        lines += [f"## {labels[sev]} ({len(items)})", ""]
        for f in items:
            where = f" – {f['path']}" if f.get("path") else ""
            lines.append(f"- `{f['check']}`{where}: {f['message']}")
        lines.append("")
    write_if_changed(svc, rel, "\n".join(lines))
    return rel


__all__ = ["GENERATED", "lint", "write_report"]
