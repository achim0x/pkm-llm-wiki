"""Belege: Parser, Auflösung, show_citations, fix-/sync-citations (Spezifikation 4.2, 5.2, 7.3).

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
# along with this program.  If not, see <https://gnu.org>.

# *****************************************************************************

# Imports *********************************************************************

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
from .parse import PREAMBLE, Section, body_lines, normalize_key_input
from .vault import Doc, is_markdown, load_text_doc
from .wikigen import wiki_pages, write_if_changed

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:[ \t]*(.*)$")
REF_RE = re.compile(r"\[\^([^\]\s]+)\](?!:)")
REF_GROUP_RE = re.compile(r"((?:\[\^[^\]\s]+\](?!:))+)")
LINK_RE = re.compile(r"^!?\[\[([^\]\|#]*)(?:#([^\]\|]*))?(?:\|[^\]]*)?\]\]")
SEP_RE = re.compile(r"\s+·\s+")
LIST_ITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
PAGE_ANCHOR_RE = re.compile(r"page=(\d+)")
SHA_VALUE_RE = re.compile(r"[0-9a-f]{6,64}")
QUOTE_PAIRS = (("„", "“"), ("“", "”"), ('"', '"'), ("»", "«"), ("«", "»"))
MAX_QUOTE = 200
MAX_EXCERPT = 1500
MAX_UNKNOWN_PART = 40
CONTENT_SECTIONS = ("Inhalt", "Widersprüche / offene Fragen")

# Classes *********************************************************************


@dataclass
class Citation:  # pylint: disable=too-many-instance-attributes
    """Ein Beleg (Fußnotendefinition) nach 4.2.

    Attributes:
        label: Fußnotenname, z. B. ``b1``.
        line: Zeilenindex der Definition im Body.
        raw: Text nach ``[^label]:``.
        path: Link-Ziel wie geschrieben (ohne Anker).
        anchor: Anker (Überschrift oder ``page=n``).
        page: PDF-Seite bei ``#page=n``.
        explicit_key: Genauer Abschnittsschlüssel aus ``§:``.
        quote: Wörtliches Zitat.
        doc_id: ``id:``.
        version: ``v:``.
        sha: ``sha:`` (Präfix des Abschnitts- bzw. Datei-Hashes).
        problems: Formatfehler (deutsch).
    """

    label: str
    line: int
    raw: str
    path: str | None = None
    anchor: str | None = None
    page: int | None = None
    explicit_key: str | None = None
    quote: str | None = None
    doc_id: str | None = None
    version: int | None = None
    sha: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def markdown(self) -> bool:
        """Ob der Beleg auf ein Markdown-Dokument zeigt.

        Returns:
            ``True`` ohne Endung oder bei ``.md``.
        """
        return not self.path or PurePosixPath(self.path).suffix.lower() in ("", ".md")

    @property
    def target_rel(self) -> str | None:
        """Pfad der Zieldatei.

        Returns:
            Pfad mit ``.md`` bei Markdown, sonst wie geschrieben; ``None`` ohne Link.
        """
        result = self.path
        if self.path and self.markdown and not self.path.lower().endswith(".md"):
            result = f"{self.path}.md"
        return result

    @property
    def link_path(self) -> str | None:
        """Pfad, wie er im Wikilink steht.

        Returns:
            Pfad ohne ``.md``; ``None`` ohne Link.
        """
        return self.path[:-3] if self.path and self.path.lower().endswith(".md") else self.path

    @property
    def section_key(self) -> str | None:
        """Belegter Abschnitt.

        Returns:
            ``§:``-Schlüssel, sonst der Anker als Schlüssel, sonst ``_preamble``; ``None`` bei Anhängen.
        """
        key = None
        if self.markdown:
            key = self.explicit_key or (normalize_key_input(self.anchor) if self.anchor else PREAMBLE)
        return key


@dataclass
class Statement:
    """Aussage (Absatz oder Listeneintrag) mit ihren Fußnoten.

    Attributes:
        text: Text ohne Fußnotenmarken.
        labels: Fußnoten im Absatz.
        section: Abschnittsschlüssel.
        line: Zeilenindex im Body.
        segments: Textstücke jeweils bis zur nächsten Fußnotengruppe mit deren Fußnoten.
    """

    text: str
    labels: list[str]
    section: str
    line: int
    segments: list[tuple[str, list[str]]] = field(default_factory=list)

    def labels_for(self, needle: str) -> list[str]:
        """Belege für ein Textstück.

        Args:
            needle: Normalisiertes Textstück (siehe ``norm_ws``).

        Returns:
            Die Fußnoten direkt nach der Stelle, sonst die des ganzen Absatzes.
        """
        hit = next((labels for text, labels in self.segments if needle in norm_ws(text)), None)
        return hit or self.labels


@dataclass
class PageCitations:
    """Alle Belege und Aussagen einer Wiki-Seite.

    Attributes:
        doc: Die Seite.
        definitions: Fußnotendefinitionen je Name.
        references: Fußnotenverweise als (Name, Zeilenindex).
        statements: Aussagen in Dokumentreihenfolge.
    """

    doc: Doc
    definitions: dict[str, Citation]
    references: list[tuple[str, int]]
    statements: list[Statement]

    def labels_in_order(self) -> list[str]:
        """Fußnotennamen in Reihenfolge der Verwendung, danach unbenutzte Definitionen.

        Returns:
            Namen ohne Duplikate.
        """
        return list(dict.fromkeys([label for label, _ in self.references] + list(self.definitions)))

    def statement_for(self, label: str) -> str | None:
        """Erste Aussage, die eine Fußnote verwendet.

        Args:
            label: Fußnotenname.

        Returns:
            Aussagetext oder ``None``.
        """
        return next((st.text for st in self.statements if label in st.labels), None)


@dataclass
class Resolution:  # pylint: disable=too-many-instance-attributes
    """Ergebnis der Auflösung eines Belegs nach 5.2.

    Attributes:
        status: ``ok``, ``moved``, ``newer_version`` oder ``missing``.
        current_path: Aktueller Pfad des Originals.
        moved: Ob das Original über ID bzw. Hash an anderem Ort gefunden wurde.
        doc: Aktuelles Original (nur Markdown).
        current_version: Aktuelle Version (nur Markdown).
        cited_text: Belegter Abschnitt in der belegten Version.
        cited_sections: Abschnitts-Hashes der belegten Version.
    """

    status: str
    current_path: str | None
    moved: bool
    doc: Doc | None
    current_version: int | None
    cited_text: str | None = None
    cited_sections: dict[str, str] | None = None


class Resolver:
    """Löst Belege auf; merkt sich gelesene Versionen und Anhang-Hashes."""

    def __init__(self, svc: Service) -> None:
        """Auflöser anlegen.

        Args:
            svc: Dienst.
        """
        self.svc = svc
        self._versions: dict[tuple[str, int], Doc | None] = {}
        self._bin_index: dict[str, list[str]] | None = None

    def version_doc(self, doc_id: str, version: int) -> Doc | None:
        """Dokument in einer Version aus Git.

        Args:
            doc_id: Dokument-ID.
            version: Versionsnummer.

        Returns:
            Das Dokument oder ``None``, wenn die Version nicht im Verlauf ist.
        """
        key = (doc_id, version)
        if key not in self._versions:
            try:
                path, text = self.svc.text_at_version(doc_id, version)
                self._versions[key] = load_text_doc(path, text.encode("utf-8"))
            except PkmError:
                self._versions[key] = None
        return self._versions[key]

    def _bins(self) -> dict[str, list[str]]:
        """Hash → Pfade aller Anhänge unter ``documents/`` (einmal berechnet).

        Returns:
            Zuordnung von SHA-256 zu Pfaden.
        """
        if self._bin_index is None:
            index: dict[str, list[str]] = {}
            for rel in self.svc.vault.iter_files(("documents",)):
                if not is_markdown(rel):
                    try:
                        index.setdefault(hashes.sha256_bytes(self.svc.vault.path(rel).read_bytes()), []).append(rel)
                    except OSError:
                        continue
            self._bin_index = index
        return self._bin_index

    def _load(self, rel: str | None) -> Doc | None:
        """Datei unter ``documents/`` laden, falls vorhanden.

        Args:
            rel: Relativer Pfad oder ``None``.

        Returns:
            Das Dokument oder ``None``.
        """
        doc = None
        try:
            if rel and rel.startswith("documents/") and self.svc.vault.exists(rel):
                doc = self.svc.vault.load(rel)
        except PkmError:
            doc = None
        return doc

    def _find_markdown(self, cit: Citation) -> tuple[Doc | None, bool]:
        """Original zu einem Markdown-Beleg finden: erst Pfad mit passender ID, dann ID.

        Args:
            cit: Beleg.

        Returns:
            Tupel aus (Dokument oder ``None``, verschoben).
        """
        doc, moved = None, False
        candidate = self._load(cit.target_rel)
        if candidate is not None and (cit.doc_id is None or candidate.id == cit.doc_id):
            doc = candidate
        elif cit.doc_id and is_valid_id(cit.doc_id):
            found = [p for p in self.svc.find_id(cit.doc_id) if p.startswith("documents/")]
            if found:
                doc, moved = self._load(found[0]), True
        return doc, moved

    def resolve(self, cit: Citation) -> Resolution:
        """Beleg auflösen und Status bestimmen (5.2).

        Args:
            cit: Beleg.

        Returns:
            Die Auflösung; bei Markdown mit belegtem Abschnitt aus der belegten Version.
        """
        if not cit.markdown:
            result = self._resolve_bin(cit)
        else:
            doc, moved = self._find_markdown(cit)
            cited = self.version_doc(cit.doc_id, cit.version) if cit.doc_id and cit.version else None
            cited_text = section_text(cited, cit.section_key) if cited else None
            cited_sections = cited.hashes.sections if cited and cited.hashes else None
            if doc is None:
                result = Resolution("missing", None, False, None, None, cited_text, cited_sections)
            else:
                status = "moved" if moved else "ok"
                if cit.version is not None and doc.version is not None and cit.version < doc.version:
                    current = doc.hashes.sections.get(cit.section_key or "") if doc.hashes else None
                    if not (current and cit.sha and hashes.matches(current, cit.sha)):
                        status = "newer_version"
                result = Resolution(status, doc.rel, moved, doc, doc.version, cited_text, cited_sections)
        return result

    def _resolve_bin(self, cit: Citation) -> Resolution:
        """Beleg auf einen Anhang auflösen (Pfad und Hash, sonst Hash im Bestand).

        Args:
            cit: Beleg.

        Returns:
            Die Auflösung.
        """
        result = Resolution("missing", None, False, None, None)
        rel = cit.target_rel
        if rel and rel.startswith("documents/") and self.svc.vault.exists(rel):
            h = hashes.sha256_bytes(self.svc.vault.path(rel).read_bytes())
            if not cit.sha or hashes.matches(h, cit.sha):
                result = Resolution("ok", rel, False, None, None)
        if result.status == "missing" and cit.sha:
            paths = next((p for h, p in self._bins().items() if hashes.matches(h, cit.sha)), None)
            if paths:
                result = Resolution("moved", sorted(paths)[0], True, None, None)
        return result

# Functions *******************************************************************


def _strip_quote(part: str) -> str | None:
    """Zitat aus einem Belegteil lösen.

    Args:
        part: Teil zwischen `` · ``.

    Returns:
        Text ohne Anführungszeichen oder ``None``, wenn der Teil kein Zitat ist.
    """
    return next(
        (part[len(left) : len(part) - len(right)] for left, right in QUOTE_PAIRS
         if part.startswith(left) and part.endswith(right) and len(part) >= 2),
        None,
    )


def _parse_part(cit: Citation, part: str) -> None:
    """Einen Teil der Beleg-Zeile auswerten.

    Args:
        cit: Beleg (wird ergänzt).
        part: Teil zwischen `` · ``.
    """
    quote = _strip_quote(part)
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
        if SHA_VALUE_RE.fullmatch(value):
            cit.sha = value
        else:
            cit.problems.append("ungültiger sha")
    elif quote is not None:
        cit.quote = quote
    else:
        cit.problems.append(f"unbekannter Teil: {part[:MAX_UNKNOWN_PART]}")


def _check_required(cit: Citation) -> None:
    """Pflichtteile des Belegs prüfen und Probleme ergänzen.

    Args:
        cit: Beleg (wird ergänzt).
    """
    if cit.sha is None:
        cit.problems.append("sha fehlt")
    if cit.markdown:
        missing = [name for name, value in (("id", cit.doc_id), ("v", cit.version)) if value is None]
        cit.problems.extend(f"{name} fehlt" for name in missing)
        if cit.quote is None:
            cit.problems.append("Zitat fehlt")
    if cit.quote is not None and len(cit.quote) > MAX_QUOTE:
        cit.problems.append(f"Zitat länger als {MAX_QUOTE} Zeichen")


def parse_citation(label: str, rest: str, line: int) -> Citation:
    """Beleg-Zeile nach 4.2 lesen.

    Args:
        label: Fußnotenname.
        rest: Text nach ``[^label]:``.
        line: Zeilenindex im Body.

    Returns:
        Der Beleg; Formatfehler stehen in ``problems``.
    """
    cit = Citation(label, line, rest)
    parts = [p.strip() for p in SEP_RE.split(rest.strip()) if p.strip()]
    if not parts:
        cit.problems.append("leer")
    else:
        m = LINK_RE.match(parts[0])
        if m:
            cit.path = m.group(1).strip() or None
            cit.anchor = (m.group(2) or "").strip() or None
            page = PAGE_ANCHOR_RE.fullmatch(cit.anchor or "")
            cit.page = int(page.group(1)) if page else None
            tail = parts[0][m.end() :].strip()
            parts = ([tail] if tail else []) + parts[1:]
        else:
            cit.problems.append("Link fehlt")
        for part in parts:
            _parse_part(cit, part)
        _check_required(cit)
    return cit


def _clean_statement(text: str) -> str:
    """Fußnotenmarken und Listenzeichen entfernen, Leerraum zusammenfassen.

    Args:
        text: Rohtext.

    Returns:
        Bereinigter Text.
    """
    text = LIST_ITEM_RE.sub("", REF_RE.sub("", text), count=1)
    return " ".join(text.split())


def _segments(text: str) -> list[tuple[str, list[str]]]:
    """Text an Fußnotengruppen zerlegen.

    Args:
        text: Rohtext mit Fußnotenmarken.

    Returns:
        Liste aus (Textstück bis zur Gruppe, Fußnoten der Gruppe).
    """
    parts = REF_GROUP_RE.split(text)
    out: list[tuple[str, list[str]]] = []
    for i in range(0, len(parts), 2):
        labels = [m.group(1) for m in REF_RE.finditer(parts[i + 1])] if i + 1 < len(parts) else []
        if parts[i].strip() or labels:
            out.append((_clean_statement(parts[i]), labels))
    return out


def _block_statements(block: list[tuple[int, str]], section: str) -> list[Statement]:
    """Absatz in Aussagen umwandeln; in Listen ist jeder Eintrag eine eigene Aussage.

    Args:
        block: Zeilen des Absatzes als (Index, Text).
        section: Abschnittsschlüssel.

    Returns:
        Aussagen.
    """
    items = [block] if not any(LIST_ITEM_RE.match(t) for _, t in block) else [[b] for b in block]
    out = []
    for item in items:
        if item:
            text = " ".join(t for _, t in item)
            clean = _clean_statement(text)
            if clean:
                labels = [r.group(1) for r in REF_RE.finditer(text)]
                out.append(Statement(clean, labels, section, item[0][0], _segments(text)))
    return out


def parse_page(doc: Doc) -> PageCitations:
    """Wiki-Seite in Belege, Verweise und Aussagen zerlegen.

    Args:
        doc: Wiki-Seite.

    Returns:
        Die Belege der Seite.

    Raises:
        PkmError: Wenn die Seite nicht lesbar ist.
    """
    if doc.parsed is None:
        raise PkmError(doc.error or "invalid_encoding", doc.error_message or "Seite nicht lesbar.", path=doc.rel)
    lines = body_lines(doc.parsed.body)
    definitions: dict[str, Citation] = {}
    references: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        m = DEF_RE.match(line)
        if m:
            definitions.setdefault(m.group(1), parse_citation(m.group(1), m.group(2), i))
        else:
            references.extend((ref.group(1), i) for ref in REF_RE.finditer(line))
    def_lines = {i for i, ln in enumerate(lines) if DEF_RE.match(ln)}
    statements: list[Statement] = []
    for sec in doc.parsed.sections:
        block: list[tuple[int, str]] = []
        for i in range(sec.start + (1 if sec.heading is not None else 0), sec.end):
            if i in def_lines or not lines[i].strip():
                statements += _block_statements(block, sec.key)
                block = []
            else:
                block.append((i, lines[i]))
        statements += _block_statements(block, sec.key)
    return PageCitations(doc, definitions, references, statements)


def render_section(sec: Section) -> str:
    """Abschnitt als Text (Überschrift und Inhalt, ohne abschließende Leerzeilen).

    Args:
        sec: Abschnitt.

    Returns:
        Der Text.
    """
    lines = ([sec.heading] if sec.heading else []) + list(sec.content_lines)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def section_text(doc: Doc, key: str | None) -> str | None:
    """Text eines Abschnitts.

    Args:
        doc: Dokument.
        key: Abschnittsschlüssel.

    Returns:
        Der Text oder ``None``, wenn es den Abschnitt nicht gibt.
    """
    sec = doc.parsed.section(key) if doc.parsed is not None and key is not None else None
    return render_section(sec) if sec is not None else None


def _excerpt(text: str | None) -> str | None:
    """Text auf ``MAX_EXCERPT`` Zeichen kürzen.

    Args:
        text: Text oder ``None``.

    Returns:
        Gekürzter Text (mit „…“) oder ``None``.
    """
    return text if text is None or len(text) <= MAX_EXCERPT else text[:MAX_EXCERPT] + "…"


def norm_ws(text: str) -> str:
    """Text für Vergleiche normalisieren (Leerraum zusammenfassen, casefold).

    Args:
        text: Text.

    Returns:
        Normalisierter Text.
    """
    return " ".join(text.split()).casefold()


def obsidian_link(vault_name: str | None, rel: str | None) -> str | None:
    """``obsidian://``-Link auf eine Datei.

    Args:
        vault_name: Name des Obsidian-Vaults (``PKM_VAULT_NAME``).
        rel: Relativer Pfad.

    Returns:
        Der Link oder ``None``, wenn Vault-Name oder Pfad fehlen.
    """
    link = None
    if vault_name and rel:
        file = rel[:-3] if rel.lower().endswith(".md") else rel
        link = f"obsidian://open?vault={urlquote(vault_name, safe='')}&file={urlquote(file, safe='')}"
    return link


def citations_overview(pc: PageCitations) -> list[dict[str, Any]]:
    """Geparste Belege ohne Prüfung (für ``read`` von Wiki-Seiten).

    Args:
        pc: Belege der Seite.

    Returns:
        Je Beleg Pfad, Anker, Abschnitt, Zitat, ID, Version, sha, Aussage und Probleme.
    """
    return [
        {
            "id": c.label, "path": c.path, "anchor": c.anchor, "section": c.section_key, "quote": c.quote,
            "doc_id": c.doc_id, "version": c.version, "sha": c.sha, "statement": pc.statement_for(c.label),
            "problems": c.problems,
        }
        for c in pc.definitions.values()
    ]


def _citation_entry(
    svc: Service, pc: PageCitations, cit: Citation, res: Resolution, with_excerpt: bool
) -> dict[str, Any]:
    """Eintrag für ``show_citations``.

    Args:
        svc: Dienst.
        pc: Belege der Seite.
        cit: Beleg.
        res: Auflösung des Belegs.
        with_excerpt: Wortlaut aus belegter (und ggf. aktueller) Version mitliefern.

    Returns:
        Der Eintrag.
    """
    entry: dict[str, Any] = {
        "id": cit.label,
        "statement": pc.statement_for(cit.label),
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
    return entry


def show_citations(
    svc: Service, target: str, statement: str | None = None, with_excerpt: bool = False
) -> dict[str, Any]:
    """Tool ``show_citations``.

    Args:
        svc: Dienst.
        target: Wiki-Seite.
        statement: Textstück; grenzt auf die Belege dieser Stelle bzw. des Absatzes ein.
        with_excerpt: Wortlaut aus belegter und ggf. aktueller Version (je höchstens 1.500 Zeichen).

    Returns:
        Seite und Belege mit Original, Abschnitt, Zitat, Versionen, Status und ggf. Obsidian-Link.

    Raises:
        PkmError: ``not_found``, wenn ``statement`` auf der Seite nicht vorkommt.
    """
    rel = svc.resolve(target, ("wiki",))
    pc = parse_page(svc.vault.load(rel))
    labels = pc.labels_in_order()
    if statement:
        needle = norm_ws(statement)
        matching = [st for st in pc.statements if needle in norm_ws(st.text)]
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
        else:
            out.append(_citation_entry(svc, pc, cit, resolver.resolve(cit), with_excerpt))
    return {"status": "ok", "page": rel, "citations": out}


def _wiki_targets(svc: Service, pages: list[str] | None) -> list[str]:
    """Zu bearbeitende Wiki-Seiten.

    Args:
        svc: Dienst.
        pages: Angegebene Seiten oder ``None`` für alle.

    Returns:
        Relative Pfade.
    """
    return [svc.resolve(p, ("wiki",)) for p in pages] if pages else [d.rel for d in wiki_pages(svc)]


def _render_first(link_path: str, key: str | None, page: int | None) -> str:
    """Ersten Teil einer Beleg-Zeile bilden (Link mit Anker, ggf. ``§:``).

    Args:
        link_path: Pfad ohne ``.md``.
        key: Abschnittsschlüssel.
        page: PDF-Seite.

    Returns:
        Z. B. ``[[documents/a#Notizen]] §:Notizen#2``.
    """
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
    """Beleg-Zeile mit neuem Pfad bzw. Abschnitt; übrige Teile bleiben erhalten.

    Args:
        cit: Beleg.
        link_path: Neuer Pfad ohne ``.md``.
        key: Neuer Abschnittsschlüssel.

    Returns:
        Die neue Zeile.
    """
    parts = [p.strip() for p in SEP_RE.split(cit.raw.strip()) if p.strip()]
    m = LINK_RE.match(parts[0]) if parts else None
    tail = parts[0][m.end():].strip() if m else ""
    rest = [p for p in ([tail] if tail else []) + parts[1:] if not p.startswith("§:")]
    return f"[^{cit.label}]: " + " · ".join([_render_first(link_path, key, cit.page), *rest])


def _fixed_target(cit: Citation, res: Resolution) -> tuple[str | None, str | None]:
    """Neuen Pfad und Abschnitt eines Belegs bestimmen (verschoben bzw. umbenannt).

    Args:
        cit: Beleg.
        res: Auflösung.

    Returns:
        Tupel aus (Pfad ohne ``.md``, Abschnittsschlüssel).
    """
    new_path = cit.link_path
    if res.moved and res.current_path:
        new_path = res.current_path[:-3] if res.current_path.lower().endswith(".md") else res.current_path
    new_key = cit.section_key
    sections = res.doc.hashes.sections if res.doc is not None and res.doc.hashes else {}
    if sections and new_key and new_key not in sections and cit.sha:
        match = [k for k, h in sections.items() if hashes.matches(h, cit.sha)]
        if len(match) == 1:
            new_key = match[0]
    return new_path, new_key


def _fix_page(svc: Service, rel: str, resolver: Resolver) -> list[dict[str, str]]:
    """Belege einer Seite korrigieren und die Seite schreiben.

    Args:
        svc: Dienst.
        rel: Wiki-Seite.
        resolver: Auflöser.

    Returns:
        Geänderte Zeilen als (id, old, new).
    """
    doc = svc.vault.load(rel)
    changes: list[dict[str, str]] = []
    if doc.parsed is not None and not doc.error:
        lines = body_lines(doc.parsed.body)
        for cit in parse_page(doc).definitions.values():
            if cit.path:
                new_path, new_key = _fixed_target(cit, resolver.resolve(cit))
                new_line = rewrite_definition(cit, new_path or "", new_key)
                if (new_path, new_key) != (cit.link_path, cit.section_key) and new_line != lines[cit.line]:
                    changes.append({"id": cit.label, "old": lines[cit.line], "new": new_line})
                    lines[cit.line] = new_line
        if changes:
            write_if_changed(svc, rel, doc.parsed.frontmatter_text + "\n".join(lines) + "\n")
            sync_citations(svc, [rel])
    return changes


def fix_citations(svc: Service, pages: list[str] | None = None) -> dict[str, Any]:
    """``pkm fix-citations``: Belege auf verschobene Originale und umbenannte Abschnitte korrigieren.

    Args:
        svc: Dienst.
        pages: Wiki-Seiten oder ``None`` für alle.

    Returns:
        Anzahl geänderter Seiten und die Änderungen.
    """
    resolver = Resolver(svc)
    changes = []
    for rel in _wiki_targets(svc, pages):
        page_changes = _fix_page(svc, rel, resolver)
        if page_changes:
            changes.append({"page": rel, "changes": page_changes})
    return {"status": "ok", "pages_changed": len(changes), "changes": changes}


def expected_sources(pc: PageCitations) -> list[str]:
    """``sources`` aus den Fußnoten.

    Args:
        pc: Belege der Seite.

    Returns:
        Sortierte, eindeutige Wikilinks auf die Originale.
    """
    return sorted({f"[[{c.link_path}]]" for c in pc.definitions.values() if c.link_path})


def sync_citations(svc: Service, pages: list[str] | None = None) -> dict[str, Any]:
    """``pkm sync-citations``: ``sources`` aus den Fußnoten neu erzeugen.

    Args:
        svc: Dienst.
        pages: Wiki-Seiten oder ``None`` für alle.

    Returns:
        Anzahl geänderter Seiten und die neuen ``sources``.
    """
    changed = []
    for rel in _wiki_targets(svc, pages):
        doc = svc.vault.load(rel)
        if doc.parsed is not None and not doc.error:
            sources = expected_sources(parse_page(doc))
            if doc.meta.get("sources") != sources:
                write_if_changed(svc, rel, set_fields_linewise(doc.text or "", {"sources": sources}, block_lists=True))
                changed.append({"page": rel, "sources": sources})
    return {"status": "ok", "pages_changed": len(changed), "changes": changed}


def page_citations_for_read(doc: Doc) -> list[dict[str, Any]]:
    """Belege einer Wiki-Seite für ``read`` (ohne Prüfung).

    Args:
        doc: Wiki-Seite.

    Returns:
        Übersicht der Belege; leer, wenn die Seite nicht lesbar ist.
    """
    try:
        overview = citations_overview(parse_page(doc))
    except PkmError:
        overview = []
    return overview

# Main ************************************************************************
