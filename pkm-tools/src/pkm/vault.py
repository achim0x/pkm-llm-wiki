"""Vault-Modell: Dateien finden, laden und adressieren (Spezifikation 3, 7.1).

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

import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from . import hashes
from .config import Config
from .errors import PkmError
from .ids import is_valid_id
from .normalize import normalize_bytes
from .parse import PREAMBLE, Parsed, parse
from .paths import nfc, safe_resolve

# Variables *******************************************************************

AREAS = ("documents", "wiki")
WIKILINK_RE = re.compile(r"!?\[\[([^\]\|#]*)(?:#([^\]\|]*))?(?:\|[^\]]*)?\]\]")
FULL_WIKILINK_RE = re.compile(r"!?\[\[([^\]\|#]*)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
SUMMARY_LABEL_RE = re.compile(r"^\*\*[^*]+:\*\*\s*")
MAX_SUMMARY_WIKI = 400
MAX_SUMMARY_DOC = 200
ID_SCAN_BYTES = 4096

__all__ = ["AREAS", "PREAMBLE", "Doc", "Vault", "extract_links", "link_key", "load_text_doc", "summary_of"]

# Classes *********************************************************************


@dataclass
class Doc:  # pylint: disable=too-many-instance-attributes
    """Eine Datei im Vault (Markdown oder Anhang).

    Attributes:
        rel: Relativer Pfad mit ``/`` in NFC.
        kind: ``md`` oder ``bin``.
        size: Dateigröße in Bytes.
        mtime_ns: Änderungszeit in Nanosekunden.
        text: Normalisierter Text (nur Markdown, ``None`` bei ungültiger Kodierung).
        parsed: Zerlegtes Dokument (nur Markdown).
        hashes: Hashes nach 4.8 (nur Markdown).
        bin_hash: SHA-256 der Rohbytes (nur Anhänge).
        error: ``invalid_encoding`` oder ``invalid_frontmatter``.
        error_message: Erklärung zum Fehler.
    """

    rel: str
    kind: str
    size: int
    mtime_ns: int
    text: str | None = None
    parsed: Parsed | None = None
    hashes: hashes.DocHashes | None = None
    bin_hash: str | None = None
    error: str | None = None
    error_message: str | None = None

    @property
    def area(self) -> str:
        """Bereich der Datei.

        Returns:
            ``documents`` oder ``wiki``.
        """
        return self.rel.split("/", 1)[0]

    @property
    def meta(self) -> dict[str, Any]:
        """Frontmatter-Felder.

        Returns:
            Die Felder; leer bei Anhängen oder ungültigem Frontmatter.
        """
        return self.parsed.meta if self.parsed else {}

    @property
    def id(self) -> str | None:
        """Dokument-ID aus dem Frontmatter.

        Returns:
            Die ID, wenn sie gültig ist, sonst ``None``.
        """
        value = self.meta.get("id")
        return value if is_valid_id(value) else None

    @property
    def version(self) -> int | None:
        """Versionsnummer aus dem Frontmatter.

        Returns:
            Die Version als ganze Zahl oder ``None``.
        """
        value = self.meta.get("version")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def stem(self) -> str:
        """Dateiname ohne Endung.

        Returns:
            Der Stamm des Dateinamens.
        """
        return PurePosixPath(self.rel).stem

    @property
    def title(self) -> str:
        """Titel für Anzeige und Commits.

        Returns:
            ``title`` aus dem Frontmatter, sonst die erste Überschrift der Ebene 1, sonst den
            Dateinamen (bei Anhängen mit Endung).
        """
        t = self.meta.get("title")
        result = t.strip() if isinstance(t, str) and t.strip() else ""
        if not result and self.parsed:
            result = next((s.key for s in self.parsed.sections if s.level == 1), "")
        if not result:
            result = self.stem if self.kind == "md" else PurePosixPath(self.rel).name
        return result

    @property
    def editable(self) -> bool:
        """Ob die Datei per MCP geändert werden darf.

        Returns:
            ``True`` für gültige Markdown-Dateien unter ``documents/``.
        """
        return self.area == "documents" and self.kind == "md" and self.error is None

    @property
    def link_path(self) -> str:
        """Pfad, wie er in Wikilinks steht.

        Returns:
            Markdown ohne ``.md``, Anhänge mit Endung.
        """
        return self.rel[:-3] if self.kind == "md" else self.rel

    @property
    def wikilink(self) -> str:
        """Wikilink auf die Datei.

        Returns:
            ``[[<link_path>]]``.
        """
        return f"[[{self.link_path}]]"

    @property
    def body(self) -> str:
        """Body ohne Frontmatter.

        Returns:
            Den Body oder einen leeren Text, wenn die Datei nicht lesbar ist.
        """
        return self.parsed.body if self.parsed is not None else ""

    def link_keys(self) -> set[str]:
        """Schlüssel, unter denen Wikilinks auf diese Datei zeigen.

        Returns:
            Vollständiger Link-Pfad und Dateiname (ohne ``.md``), jeweils casefold.
        """
        name = self.stem if self.kind == "md" else PurePosixPath(self.rel).name
        return {self.link_path.casefold(), name.casefold()}


class Vault:
    """Zugriff auf die Dateien unter ``documents/`` und ``wiki/``."""

    def __init__(self, cfg: Config) -> None:
        """Vault-Zugriff anlegen.

        Args:
            cfg: Konfiguration.
        """
        self.cfg = cfg
        self.root = cfg.root

    # Bestand ******************************************************************

    def iter_files(self, areas: tuple[str, ...] = AREAS) -> Iterator[str]:
        """Alle Dateien der Bereiche durchlaufen (versteckte Dateien und Ordner ausgenommen).

        Args:
            areas: Bereiche, z. B. ``("documents",)``.

        Yields:
            Relative Pfade in NFC, sortiert je Ordner.
        """
        for area in areas:
            base = self.root / area
            if base.is_dir():
                for dirpath, dirnames, filenames in os.walk(base):
                    dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
                    for name in sorted(filenames):
                        if not name.startswith("."):
                            yield nfc((Path(dirpath) / name).relative_to(self.root).as_posix())

    def path(self, rel: str) -> Path:
        """Relativen Pfad sicher im Vault auflösen.

        Args:
            rel: Relativer Pfad.

        Returns:
            Pfad im Vault.

        Raises:
            PkmError: ``invalid_path`` bei unzulässigen Pfaden.
        """
        return safe_resolve(self.root, rel)

    def exists(self, rel: str) -> bool:
        """Prüfen, ob eine Datei existiert.

        Args:
            rel: Relativer Pfad.

        Returns:
            ``True``, wenn es eine Datei ist.
        """
        return self.path(rel).is_file()

    def load(self, rel: str) -> Doc:
        """Datei laden und (bei Markdown) zerlegen und hashen.

        Args:
            rel: Relativer Pfad.

        Returns:
            Das Dokument.

        Raises:
            PkmError: ``not_found``, wenn die Datei fehlt.
        """
        p = self.path(rel)
        if not p.is_file():
            raise PkmError("not_found", f"Datei nicht gefunden: {rel}", target=rel)
        st = p.stat()
        if is_markdown(rel):
            doc = load_text_doc(rel, p.read_bytes(), st.st_size, st.st_mtime_ns)
        else:
            doc = Doc(rel, "bin", st.st_size, st.st_mtime_ns, bin_hash=hashes.sha256_bytes(p.read_bytes()))
        return doc

    # Adressierung (7.1) *******************************************************

    def resolve(
        self,
        target: str,
        areas: tuple[str, ...] = AREAS,
        find_id: Callable[[str], list[str]] | None = None,
    ) -> str:
        """Ziel (Pfad, Wikilink, Kurzname oder ``id:``) in einen relativen Pfad auflösen.

        Args:
            target: Ziel, z. B. ``documents/haus/zisterne.md``, ``[[zisterne]]`` oder ``id:d-…``.
            areas: Erlaubte Bereiche.
            find_id: Suche nach ID (z. B. über den Index); ohne Angabe ``scan_id``.

        Returns:
            Relativer Pfad der gefundenen Datei.

        Raises:
            PkmError: ``not_found``, ``ambiguous`` (mit Kandidaten), ``forbidden`` oder ``invalid_path``.
        """
        if not isinstance(target, str) or not target.strip():
            raise PkmError("not_found", "Leeres Ziel.")
        t = nfc(target.strip())
        if t.startswith("id:"):
            rel = self._resolve_id(t[3:].strip(), target, areas, find_id)
        else:
            m = FULL_WIKILINK_RE.fullmatch(t)
            t = (m.group(1).strip() if m else t).replace("\\", "/").strip("/")
            rel = self._resolve_path(t, target, areas) if "/" in t else self._resolve_short(t, target, areas)
        return rel

    def _resolve_id(
        self, doc_id: str, target: str, areas: tuple[str, ...], find_id: Callable[[str], list[str]] | None
    ) -> str:
        """Ziel über die Dokument-ID auflösen.

        Args:
            doc_id: Dokument-ID.
            target: Ursprüngliches Ziel (für Fehlermeldungen).
            areas: Erlaubte Bereiche.
            find_id: Suche nach ID oder ``None`` für ``scan_id``.

        Returns:
            Relativer Pfad.

        Raises:
            PkmError: ``not_found`` oder ``ambiguous``.
        """
        if not is_valid_id(doc_id):
            raise PkmError("not_found", f"Ungültige ID: {doc_id}", target=target)
        found = [r for r in (find_id or self.scan_id)(doc_id) if r.split("/", 1)[0] in areas]
        return _one(found, target)

    def _resolve_path(self, t: str, target: str, areas: tuple[str, ...]) -> str:
        """Ziel mit ``/`` als Pfad (mit oder ohne ``.md``) auflösen.

        Args:
            t: Bereinigter Pfad.
            target: Ursprüngliches Ziel (für Fehlermeldungen).
            areas: Erlaubte Bereiche.

        Returns:
            Relativer Pfad.

        Raises:
            PkmError: ``not_found``, ``forbidden`` oder ``invalid_path``.
        """
        found = next((p for p in (self.path(t), self.path(f"{t}.md")) if p.is_file()), None)
        if found is None:
            raise PkmError("not_found", f"Nicht gefunden: {target}", target=target)
        rel = nfc(found.relative_to(self.root).as_posix())
        if rel.split("/", 1)[0] not in areas:
            raise PkmError("forbidden", f"Nur {', '.join(areas)} sind hier erlaubt.", target=target)
        return rel

    def _resolve_short(self, t: str, target: str, areas: tuple[str, ...]) -> str:
        """Kurznamen ohne Ordner auflösen (Dateiname ohne Endung, ohne Groß-/Kleinschreibung).

        Args:
            t: Kurzname.
            target: Ursprüngliches Ziel (für Fehlermeldungen).
            areas: Erlaubte Bereiche.

        Returns:
            Relativer Pfad.

        Raises:
            PkmError: ``not_found`` oder ``ambiguous``.
        """
        key = link_key(t)
        found = []
        for rel in self.iter_files(areas):
            name = PurePosixPath(rel).name
            stem = name[:-3] if is_markdown(name) else name
            if key in (stem.casefold(), name.casefold()):
                found.append(rel)
        return _one(found, target)

    def scan_id(self, doc_id: str) -> list[str]:
        """ID ohne Index suchen (langsam, Rückfallebene).

        Args:
            doc_id: Dokument-ID.

        Returns:
            Alle Markdown-Dateien mit dieser ID.
        """
        needle = doc_id.encode()
        found = []
        for rel in self.iter_files():
            if is_markdown(rel) and needle in self._head(rel) and self.load(rel).id == doc_id:
                found.append(rel)
        return found

    def _head(self, rel: str) -> bytes:
        """Anfang einer Datei lesen (für die schnelle ID-Suche).

        Args:
            rel: Relativer Pfad.

        Returns:
            Die ersten Bytes oder leere Bytes, wenn die Datei nicht lesbar ist.
        """
        try:
            data = self.path(rel).read_bytes()[:ID_SCAN_BYTES]
        except OSError:
            data = b""
        return data

# Functions *******************************************************************


def _one(found: list[str], target: str) -> str:
    """Genau einen Treffer verlangen.

    Args:
        found: Gefundene Pfade.
        target: Ursprüngliches Ziel (für Fehlermeldungen).

    Returns:
        Den einzigen Treffer.

    Raises:
        PkmError: ``not_found`` ohne Treffer, ``ambiguous`` mit Kandidaten bei mehreren.
    """
    if not found:
        raise PkmError("not_found", f"Nicht gefunden: {target}", target=target)
    if len(found) > 1:
        raise PkmError("ambiguous", f"Mehrdeutig: {target}", target=target, candidates=sorted(found))
    return found[0]


def is_markdown(rel: str) -> bool:
    """Prüfen, ob ein Pfad eine Markdown-Datei bezeichnet.

    Args:
        rel: Pfad oder Dateiname.

    Returns:
        ``True`` bei Endung ``.md`` (Groß-/Kleinschreibung egal).
    """
    return rel.lower().endswith(".md")


def load_text_doc(rel: str, data: bytes, size: int = 0, mtime_ns: int = 0) -> Doc:
    """Markdown-Dokument aus Bytes laden.

    Args:
        rel: Relativer Pfad.
        data: Dateiinhalt.
        size: Dateigröße; ohne Angabe die Länge von ``data``.
        mtime_ns: Änderungszeit.

    Returns:
        Das Dokument; bei Fehlern sind ``error`` und ``error_message`` gesetzt.
    """
    doc = Doc(rel, "md", size or len(data), mtime_ns)
    try:
        text = normalize_bytes(data)
    except PkmError as exc:
        doc.error, doc.error_message = exc.status, exc.message
        text = None
    if text is not None:
        doc.text = text
        doc.parsed = parse(text)
        if doc.parsed.fm_error:
            doc.error, doc.error_message = "invalid_frontmatter", doc.parsed.fm_error
        doc.hashes = hashes.compute(text, doc.parsed)
    return doc


def extract_links(body: str) -> list[str]:
    """Wikilink-Ziele aus einem Text sammeln.

    Args:
        body: Markdown-Text.

    Returns:
        Ziele ohne Anker und Alias, ohne Duplikate, in Reihenfolge des Auftretens.
    """
    seen: list[str] = []
    for m in WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.append(target)
    return seen


def link_key(target: str) -> str:
    """Wikilink-Ziel vergleichbar machen.

    Args:
        target: Link-Ziel.

    Returns:
        Ziel in NFC, mit ``/``, ohne ``.md``, casefold.
    """
    t = nfc(target.strip()).replace("\\", "/")
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.casefold()


def summary_of(doc: Doc) -> str:
    """Kurzfassung eines Dokuments.

    Args:
        doc: Dokument.

    Returns:
        Bei Wiki-Seiten das erste Zitat nach dem Frontmatter (ohne fettes Etikett wie
        „Kurzfassung:“), bei Dokumenten das erste Zitat oder der erste Absatz; sonst leer.
    """
    summary = ""
    if doc.parsed is not None:
        lines = [ln.lstrip() for ln in doc.parsed.body_lines]
        i = next((n for n, ln in enumerate(lines) if ln.strip()), len(lines))
        if i < len(lines) and lines[i].startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            summary = SUMMARY_LABEL_RE.sub("", " ".join(q for q in quote if q))[:MAX_SUMMARY_WIKI]
        elif doc.area != "wiki":
            summary = _first_paragraph(doc.parsed)[:MAX_SUMMARY_DOC]
    return summary


def _first_paragraph(parsed: Parsed) -> str:
    """Ersten Absatz über alle Abschnitte suchen.

    Args:
        parsed: Zerlegtes Dokument.

    Returns:
        Den ersten Absatz (Zeilen mit Leerzeichen verbunden) oder einen leeren Text.
    """
    para: list[str] = []
    for section in parsed.sections:
        for line in section.content_lines:
            if line.strip():
                para.append(line.strip())
            elif para:
                break
        if para:
            break
    return " ".join(para)


def section_summary(doc: Doc) -> list[dict[str, Any]]:
    """Abschnittsübersicht für ``read``.

    Args:
        doc: Dokument.

    Returns:
        Je Abschnitt Schlüssel, Ebene und Kurz-Hash; leer bei nicht lesbaren Dateien.
    """
    result: list[dict[str, Any]] = []
    if doc.parsed is not None and doc.hashes is not None:
        result = [
            {"key": s.key, "level": s.level, "sha": hashes.short(doc.hashes.sections[s.key])}
            for s in doc.parsed.sections
        ]
    return result


# Main ************************************************************************
