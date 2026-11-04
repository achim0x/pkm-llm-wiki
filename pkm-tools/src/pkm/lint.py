"""``pkm lint`` (Spezifikation 8, 4.8): Struktur, Belege, Dokumente, Plattform. JSON-Bericht.

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

import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from . import hashes
from .citations import CONTENT_SECTIONS, Citation, Resolution, Resolver, expected_sources, norm_ws, parse_page
from .cloudsync import conflict_copies
from .errors import PkmError
from .frontmatter import fix_frontmatter_text
from .imagelint import check_images, has_image, image_quote
from .parse import Section, body_lines, find_setext
from .parse import parse as parse_text
from .paths import case_collisions, is_platform_safe_name
from .schema import (
    DATE_FIELDS,
    KINDS,
    LEGACY_SHORT_CITATION,
    is_valid_date_value,
    looks_converted,
)
from .vault import Doc, extract_links, is_markdown, link_key, summary_of
from .wikigen import FOLDER_TYPES, wiki_pages, write_if_changed

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

WIKI_TYPES = ("topic", "entity", "summary", "synthesis")
CONFIDENCE = ("high", "medium", "low")
BAD_ANCHOR_CHARS = set("#^[]|")
SUFFIX_LIKE_RE = re.compile(r"#([0-9]+)$")
SEVERITIES = ("error", "warning", "info")
SEVERITY_LABELS = {"error": "Fehler", "warning": "Warnungen", "info": "Hinweise"}
MIN_MISSING_PAGE_LINKS = 2
MIN_TOPIC_DOCUMENTS = 3
STATEMENT_PREVIEW = 80

# Classes *********************************************************************


class Report:
    """Sammelt Befunde."""

    def __init__(self) -> None:
        """Leeren Bericht anlegen."""
        self.findings: list[dict[str, Any]] = []

    def add(self, check: str, severity: str, path: str | None, message: str, **detail: Any) -> None:
        """Befund hinzufügen.

        Args:
            check: Name der Prüfung, z. B. ``broken_link``.
            severity: ``error``, ``warning`` oder ``info``.
            path: Betroffene Datei oder ``None``.
            message: Beschreibung (deutsch).
            **detail: Zusätzliche Angaben.
        """
        item: dict[str, Any] = {"check": check, "severity": severity, "path": path, "message": message}
        if detail:
            item["detail"] = detail
        self.findings.append(item)

    def result(self) -> dict[str, Any]:
        """Bericht als JSON-Objekt.

        Returns:
            ``status``, ``summary`` (Anzahl je Schweregrad) und ``findings``.
        """
        counts = Counter(f["severity"] for f in self.findings)
        return {"status": "ok", "summary": {s: counts.get(s, 0) for s in SEVERITIES}, "findings": self.findings}


class Linter:  # pylint: disable=too-many-instance-attributes
    """Führt alle Prüfungen aus Spezifikation 8 und 4.8 aus."""

    def __init__(self, svc: Service) -> None:
        """Bestand einlesen.

        Args:
            svc: Dienst.
        """
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
        self.conflicts = conflict_copies(self.all_files, {d.rel: d.id for d in self.docs if d.kind == "md"})

    def run(self) -> dict[str, Any]:
        """Alle Prüfungen ausführen.

        Returns:
            Der Bericht.
        """
        self.platform()
        self.documents()
        check_images(self.r.add, self.svc, self.docs, self.pages)
        self.structure()
        self.citations()
        return self.r.result()

    # Plattform ****************************************************************

    def platform(self) -> None:
        """Konfliktkopien, nicht plattformfeste Namen und Groß-/Kleinschreibungs-Kollisionen."""
        for rel in self.all_files:
            if rel in self.conflicts:
                self.r.add("conflict_copy", "error", rel,
                           "Konfliktkopie des Cloud-Speichers; Fassungen in Obsidian zusammenführen.")
            bad = next((part for part in PurePosixPath(rel).parts if not is_platform_safe_name(part)), None)
            if bad is not None:
                self.r.add("unsafe_filename", "warning", rel, f"Name „{bad}“ ist nicht auf allen Systemen gültig.")
        for group in case_collisions(self.all_files):
            self.r.add("case_collision", "error", group[0], "Namen unterscheiden sich nur in Groß-/Kleinschreibung.",
                       paths=group)

    # Dokumente ****************************************************************

    def documents(self) -> None:
        """ID, Version, Abgleich mit dem Verlauf, doppelte IDs, Kodierung, Frontmatter, Überschriften."""
        by_id: dict[str, list[str]] = defaultdict(list)
        git_ok = self.svc.git.problem() is None
        for doc in self.docs:
            if doc.kind == "md" and doc.error:
                self.r.add(doc.error, "error", doc.rel, _error_message(doc))
            elif doc.kind == "md" and doc.rel not in self.conflicts:
                self._document(doc, git_ok)
                if doc.id:
                    by_id[doc.id].append(doc.rel)
        for doc_id, paths in by_id.items():
            if len(paths) > 1:
                self.r.add("duplicate_id", "error", sorted(paths)[0], f"ID {doc_id} mehrfach vergeben.",
                           paths=sorted(paths))

    def _document(self, doc: Doc, git_ok: bool) -> None:
        """Prüfungen für ein gültiges Markdown-Dokument.

        Args:
            doc: Dokument.
            git_ok: Ob Git verfügbar ist (für den Abgleich mit dem Verlauf).
        """
        self._frontmatter(doc)
        if not doc.id:
            self.r.add("missing_id", "warning", doc.rel, "Dokument ohne gültige ID (pkm ids).")
        if doc.version is None:
            self.r.add("missing_version", "warning", doc.rel, "Dokument ohne Version (pkm ids).")
        if git_ok and doc.id and doc.version is not None and not self.svc.git.is_dirty(doc.rel):
            versions = [c.version for c in self.svc.versions(doc.id) if c.path]
            if versions and versions[-1] != doc.version:
                self.r.add("version_mismatch", "error", doc.rel,
                           f"version {doc.version} passt nicht zum Verlauf (zuletzt v{versions[-1]}).")
        self.headings(doc)

    def _frontmatter(self, doc: Doc) -> None:
        """Frontmatter nach 4.1 prüfen: Herkunftsfelder, alte Feldnamen, ``kind``, Datumsfelder, ``tags``.

        Args:
            doc: Dokument mit gültigem Frontmatter.
        """
        meta = doc.meta
        for field, label in (("date_markdown", "date_markdown"), ("toolchain_markdown", "toolchain_markdown")):
            if field not in meta:
                self.r.add(f"missing_{field}", "info", doc.rel, f"Feld {label} fehlt (wird nicht ergänzt).")
        if LEGACY_SHORT_CITATION in meta:
            self.r.add("legacy_short_citation", "info", doc.rel,
                       "Feld „short citation“ mit Leerzeichen; pkm fix-frontmatter benennt es um (nur auf Anweisung).")
        if "kind" not in meta and looks_converted(meta):
            self.r.add("missing_kind", "info", doc.rel,
                       "Umgewandeltes Dokument ohne kind (standard oder regulation von Hand ergänzen).")
        elif "kind" in meta and meta["kind"] not in KINDS:
            self.r.add("invalid_kind", "error", doc.rel, f"Unbekannter Wert in kind: {meta['kind']!r}.")
        self._dates_and_tags(doc)

    def _dates_and_tags(self, doc: Doc) -> None:
        """Format der Datumsfelder und der Tags prüfen (Dokumente und Wiki-Seiten).

        Args:
            doc: Datei mit gültigem Frontmatter.
        """
        for field in DATE_FIELDS:
            if field in doc.meta and not is_valid_date_value(doc.meta[field]):
                self.r.add("invalid_date", "warning", doc.rel,
                           f"{field} hat nicht das Format YYYY-MM-DDTHH:MM:SS bzw. YYYY-MM-DD (ohne Zeitzone): "
                           f"{doc.meta[field]!r}.")
        tags = doc.meta.get("tags")
        if tags is not None and (not isinstance(tags, list) or any(" " in str(t).strip() for t in tags)):
            self.r.add("invalid_tags", "warning", doc.rel,
                       "tags muss eine Liste ohne Leerzeichen in den Einträgen sein.")

    def headings(self, doc: Doc) -> None:
        """Überschriften nach 4.8: Setext, Duplikate, Anker-Zeichen, Text auf ``#`` plus Ziffern.

        Args:
            doc: Dokument mit gültigem Inhalt.
        """
        assert doc.parsed is not None
        for i in find_setext(body_lines(doc.parsed.body)):
            self.r.add("setext_heading", "info", doc.rel,
                       f"Setext-Überschrift (Zeile {i + 1} im Inhalt) ist keine Abschnittsgrenze; bitte # verwenden.")
        headings = [s for s in doc.parsed.sections if s.level]
        bases = {s.base for s in headings}
        reported: set[str] = set()
        for sec in headings:
            if sec.key != sec.base and sec.base not in reported:
                reported.add(sec.base)
                self.r.add("duplicate_heading", "warning", doc.rel, f"Überschrift „{sec.base}“ kommt mehrfach vor.")
            self._heading_text(doc, sec, bases)

    def _heading_text(self, doc: Doc, sec: Section, bases: set[str]) -> None:
        """Überschriftentext prüfen (Suffix-Verwechslung und Zeichen, die Anker brechen).

        Args:
            doc: Dokument.
            sec: Abschnitt mit Überschrift.
            bases: Alle Überschriftentexte des Dokuments.
        """
        m = SUFFIX_LIKE_RE.search(sec.base)
        if m and sec.key == sec.base:
            stem = sec.base[: m.start()]
            hint = f"bitte umformulieren (z. B. „{stem} {m.group(1)}“)"
            if stem in bases:
                self.r.add("heading_suffix_collision", "error", doc.rel,
                           f"Überschrift „{sec.base}“ kollidiert mit dem Duplikat-Suffix von „{stem}“; {hint}.")
            else:
                self.r.add("heading_suffix_like", "warning", doc.rel,
                           f"Überschrift „{sec.base}“ endet auf # plus Ziffern und kann mit einem "
                           f"Duplikat-Suffix verwechselt werden; {hint}.")
        text = sec.base[: m.start()] if m else sec.base
        if BAD_ANCHOR_CHARS & set(text):
            self.r.add("heading_bad_chars", "warning", doc.rel,
                       f"Überschrift „{sec.base}“ enthält Zeichen, die Obsidian-Anker brechen (# ^ [ ] |).")

    # Struktur *****************************************************************

    def resolve_link(self, target: str) -> set[str]:
        """Wikilink-Ziel im Bestand suchen.

        Args:
            target: Link-Ziel.

        Returns:
            Passende Pfade (leer, eins oder mehrere).
        """
        return self.keys.get(link_key(target), set())

    def structure(self) -> None:
        """Typ, Konfidenz, Kurzfassung, Links, verwaiste und fehlende Seiten, Themen ohne Seite."""
        incoming: Counter[str] = Counter()
        unresolved: Counter[str] = Counter()
        for page in self.pages:
            if page.error:
                self.r.add(page.error, "error", page.rel, page.error_message or page.error)
            else:
                self._page_meta(page)
                self._page_links(page, incoming, unresolved)
        for page in self.pages:
            if page.rel.split("/")[1] in FOLDER_TYPES and not incoming.get(page.rel):
                self.r.add("orphan_page", "warning", page.rel, "Keine andere Wiki-Seite verweist auf diese Seite.")
        for target, n in unresolved.items():
            if n >= MIN_MISSING_PAGE_LINKS:
                self.r.add("missing_page", "info", None, f"[[{target}]] wird {n}-mal verlinkt, die Seite fehlt.")
        self._topics_without_page()

    def _page_meta(self, page: Doc) -> None:
        """Frontmatter und Kurzfassung einer Wiki-Seite prüfen.

        Args:
            page: Wiki-Seite.
        """
        folder = page.rel.split("/")[1] if page.rel.count("/") >= 2 else ""
        typ = page.meta.get("type")
        if typ not in WIKI_TYPES:
            self.r.add("invalid_type", "warning", page.rel, f"type fehlt oder ist ungültig: {typ!r}.")
        elif folder in FOLDER_TYPES and FOLDER_TYPES[folder] != typ:
            self.r.add("type_folder_mismatch", "info", page.rel, f"type {typ} passt nicht zum Ordner {folder}/.")
        self._dates_and_tags(page)
        conf = page.meta.get("confidence")
        if conf is not None and conf not in CONFIDENCE:
            self.r.add("invalid_confidence", "warning", page.rel, f"confidence ungültig: {conf!r}.")
        if not summary_of(page):
            self.r.add("missing_summary", "warning", page.rel, "Kurzfassung (erstes Zitat >) fehlt.")

    def _page_links(self, page: Doc, incoming: Counter[str], unresolved: Counter[str]) -> None:
        """Links einer Wiki-Seite prüfen und zählen.

        Args:
            page: Wiki-Seite.
            incoming: Eingehende Links je Seite (wird ergänzt).
            unresolved: Nicht gefundene Ziele (wird ergänzt).
        """
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

    def _topics_without_page(self) -> None:
        """Themen, die in mehreren Dokumenten vorkommen, aber keine Wiki-Seite haben."""
        names = set()
        for page in self.pages:
            names.update({page.stem.casefold(), page.title.casefold()})
            aliases = page.meta.get("aliases")
            if isinstance(aliases, list):
                names.update(str(a).casefold() for a in aliases)
        topics: Counter[str] = Counter()
        for doc in self.docs:
            t = doc.meta.get("tags")
            if isinstance(t, list):
                topics.update({str(x).casefold() for x in t})
        for topic, n in sorted(topics.items()):
            if n >= MIN_TOPIC_DOCUMENTS and topic not in names:
                self.r.add("topic_without_page", "info", None,
                           f"Thema „{topic}“ in {n} Dokumenten, aber ohne Wiki-Seite.")

    # Belege *******************************************************************

    def citations(self) -> None:
        """Fußnoten, Aussagen ohne Beleg, ``sources`` und jeden einzelnen Beleg prüfen."""
        resolver = Resolver(self.svc)
        for page in self.pages:
            if not page.error:
                pc = parse_page(page)
                labels_ref = {lab for lab, _ in pc.references}
                for label in sorted(labels_ref - set(pc.definitions)):
                    self.r.add("footnote_undefined", "error", page.rel, f"Fußnote [^{label}] ohne Definition.")
                for label in sorted(set(pc.definitions) - labels_ref):
                    self.r.add("footnote_unused", "info", page.rel, f"Fußnote [^{label}] wird nicht verwendet.")
                for st in pc.statements:
                    if st.section in CONTENT_SECTIONS and not st.labels:
                        self.r.add("statement_without_citation", "warning", page.rel,
                                   f"Aussage ohne Beleg: „{st.text[:STATEMENT_PREVIEW]}“", section=st.section)
                if page.meta.get("sources") != expected_sources(pc):
                    self.r.add("sources_out_of_sync", "warning", page.rel,
                               "sources passt nicht zu den Fußnoten (pkm sync-citations).")
                for cit in pc.definitions.values():
                    self.citation(page, cit, resolver)

    def citation(self, page: Doc, cit: Citation, resolver: Resolver) -> None:
        """Einen Beleg prüfen: Format, Ziel, Auflösung und Inhalt.

        Args:
            page: Wiki-Seite.
            cit: Beleg.
            resolver: Auflöser.
        """
        for problem in cit.problems:
            self.r.add("citation_format", "error", page.rel, f"[^{cit.label}]: {problem}.", footnote=cit.label)
        target = cit.target_rel or ""
        if cit.path and not target.startswith("documents/"):
            check = {"wiki": "citation_to_wiki", "scratch": "citation_to_scratch"}.get(
                target.split("/", 1)[0], "citation_outside_documents")
            self.r.add(check, "error", page.rel, f"[^{cit.label}] zeigt nicht auf documents/: {cit.path}.",
                       footnote=cit.label)
        elif cit.path:
            res = resolver.resolve(cit)
            self._citation_status(page, cit, res)
            if cit.markdown:
                self._citation_content(page, cit, res)
                sections = res.doc.hashes.sections if res.doc is not None and res.doc.hashes else {}
                if sections.get(cit.section_key or "") == hashes.EMPTY_HASH:
                    self.r.add("citation_empty_section", "warning", page.rel,
                               f"[^{cit.label}] belegt den Abschnitt „{cit.section_key}“ ohne eigenen Text; "
                               "den Unterabschnitt mit dem Zitat belegen.", footnote=cit.label)

    def _citation_status(self, page: Doc, cit: Citation, res: Resolution) -> None:
        """Befunde aus der Auflösung (fehlt, verschoben, neuere Version).

        Args:
            page: Wiki-Seite.
            cit: Beleg.
            res: Auflösung.
        """
        if res.status == "missing":
            self.r.add("citation_missing", "error", page.rel, f"[^{cit.label}] Original nicht gefunden: {cit.path}.",
                       footnote=cit.label)
        if res.moved:
            self.r.add("citation_moved", "warning", page.rel,
                       f"[^{cit.label}] Original verschoben nach {res.current_path} (pkm fix-citations).",
                       footnote=cit.label)
        if res.status == "newer_version":
            self.r.add("citation_newer_version", "warning", page.rel,
                       f"[^{cit.label}] Abschnitt hat sich seit v{cit.version} geändert "
                       f"(aktuell v{res.current_version}).", footnote=cit.label)

    def _citation_content(self, page: Doc, cit: Citation, res: Resolution) -> None:
        """Anker, sha und Zitat gegen die belegte Version prüfen.

        Args:
            page: Wiki-Seite.
            cit: Markdown-Beleg.
            res: Auflösung.
        """
        key = cit.section_key
        if res.cited_sections is None:
            if cit.doc_id and cit.version and res.status != "missing":
                self.r.add("cited_version_missing", "error", page.rel,
                           f"[^{cit.label}] v{cit.version} von {cit.doc_id} nicht im Verlauf.", footnote=cit.label)
        elif key not in res.cited_sections:
            self.r.add("anchor_missing", "warning", page.rel,
                       f"[^{cit.label}] Abschnitt „{key}“ gibt es in v{cit.version} nicht.", footnote=cit.label)
        elif cit.sha and not hashes.matches(res.cited_sections[key], cit.sha):
            self.r.add("sha_mismatch", "error", page.rel,
                       f"[^{cit.label}] sha passt nicht zum Abschnitt in v{cit.version}.", footnote=cit.label)
        image = image_quote(cit.quote)
        if image and res.cited_sections is not None and not has_image(res.cited_text, image):
            self.r.add("citation_image_missing", "error", page.rel,
                       f"[^{cit.label}] Bild „{image}“ steht nicht in v{cit.version}, Abschnitt „{key}“.",
                       footnote=cit.label)
        if (not image and res.cited_sections is not None and cit.quote and res.cited_text is not None
                and norm_ws(cit.quote) not in norm_ws(res.cited_text)):
            self.r.add("quote_not_found", "error", page.rel,
                       f"[^{cit.label}] Zitat steht nicht in v{cit.version}, Abschnitt „{key}“.", footnote=cit.label)

# Functions *******************************************************************


def _error_message(doc: Doc) -> str:
    """Fehlertext für unlesbare Dokumente, mit Hinweis auf ``pkm fix-frontmatter``, wenn das hilft.

    Args:
        doc: Dokument mit ``error``.

    Returns:
        Fehlertext.
    """
    message = doc.error_message or doc.error or ""
    if doc.error == "invalid_frontmatter" and doc.text is not None:
        fixed, changes = fix_frontmatter_text(doc.text)
        if changes and parse_text(fixed).fm_error is None:
            message += " Fehlende Anführungszeichen: pkm fix-frontmatter behebt das (nur auf Anweisung)."
    return message


def lint(svc: Service) -> dict[str, Any]:
    """``pkm lint``.

    Args:
        svc: Dienst.

    Returns:
        Der Prüfbericht.
    """
    return Linter(svc).run()


def write_report(svc: Service, result: dict[str, Any]) -> str:
    """Bericht nach ``wiki/_lint/YYYY-MM-DD.md`` schreiben (deutsch).

    Args:
        svc: Dienst.
        result: Ergebnis von ``lint``.

    Returns:
        Relativer Pfad des Berichts.
    """
    date = svc.now().date().isoformat()
    rel = f"wiki/_lint/{date}.md"
    s = result["summary"]
    lines = [f"# Lint-Bericht {date}", "", f"{s['error']} Fehler, {s['warning']} Warnungen, {s['info']} Hinweise.", ""]
    for sev in SEVERITIES:
        items = [f for f in result["findings"] if f["severity"] == sev]
        if items:
            lines += [f"## {SEVERITY_LABELS[sev]} ({len(items)})", ""]
            for f in items:
                where = f" – {f['path']}" if f.get("path") else ""
                lines.append(f"- `{f['check']}`{where}: {f['message']}")
            lines.append("")
    write_if_changed(svc, rel, "\n".join(lines))
    return rel

# Main ************************************************************************
