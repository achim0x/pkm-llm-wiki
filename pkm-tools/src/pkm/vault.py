"""Vault-Modell: Dateien finden, laden und adressieren (Spezifikation 3, 7.1)."""

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

AREAS = ("documents", "wiki")
TMP_PREFIX = ".pkm-tmp-"
WIKILINK_RE = re.compile(r"!?\[\[([^\]\|#]*)(?:#([^\]\|]*))?(?:\|[^\]]*)?\]\]")


@dataclass
class Doc:
    rel: str
    kind: str  # "md" | "bin"
    size: int
    mtime_ns: int
    text: str | None = None
    parsed: Parsed | None = None
    hashes: hashes.DocHashes | None = None
    bin_hash: str | None = None
    error: str | None = None  # invalid_encoding | invalid_frontmatter
    error_message: str | None = None

    @property
    def area(self) -> str:
        return self.rel.split("/", 1)[0]

    @property
    def meta(self) -> dict[str, Any]:
        return self.parsed.meta if self.parsed else {}

    @property
    def id(self) -> str | None:
        value = self.meta.get("id")
        return value if is_valid_id(value) else None

    @property
    def version(self) -> int | None:
        value = self.meta.get("version")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def stem(self) -> str:
        return PurePosixPath(self.rel).stem

    @property
    def title(self) -> str:
        t = self.meta.get("title")
        if isinstance(t, str) and t.strip():
            return t.strip()
        if self.parsed:
            for s in self.parsed.sections:
                if s.level == 1:
                    return s.key
        return self.stem if self.kind == "md" else PurePosixPath(self.rel).name

    @property
    def editable(self) -> bool:
        return self.area == "documents" and self.kind == "md" and self.error is None

    @property
    def link_path(self) -> str:
        """Pfad, wie er in Wikilinks steht (Markdown ohne Endung)."""
        return self.rel[:-3] if self.kind == "md" else self.rel

    @property
    def wikilink(self) -> str:
        return f"[[{self.link_path}]]"

    @property
    def body(self) -> str:
        if self.parsed is None:
            return ""
        return self.parsed.body

    def link_keys(self) -> set[str]:
        name = self.stem if self.kind == "md" else PurePosixPath(self.rel).name
        return {self.link_path.casefold(), name.casefold()}


def is_markdown(rel: str) -> bool:
    return rel.lower().endswith(".md")


def load_text_doc(rel: str, data: bytes, size: int = 0, mtime_ns: int = 0) -> Doc:
    doc = Doc(rel, "md", size or len(data), mtime_ns)
    try:
        text = normalize_bytes(data)
    except PkmError as exc:
        doc.error, doc.error_message = exc.status, exc.message
        return doc
    doc.text = text
    doc.parsed = parse(text)
    if doc.parsed.fm_error:
        doc.error, doc.error_message = "invalid_frontmatter", doc.parsed.fm_error
    doc.hashes = hashes.compute(text, doc.parsed)
    return doc


def extract_links(body: str) -> list[str]:
    seen: list[str] = []
    for m in WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.append(target)
    return seen


def link_key(target: str) -> str:
    t = nfc(target.strip()).replace("\\", "/")
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.casefold()


def summary_of(doc: Doc) -> str:
    """Kurzfassung: bei Wiki-Seiten das erste Zitat nach dem Frontmatter, sonst erster Absatz."""
    if doc.parsed is None:
        return ""
    lines = doc.parsed.body_lines
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith(">"):
        quote: list[str] = []
        while i < len(lines) and lines[i].lstrip().startswith(">"):
            quote.append(lines[i].lstrip()[1:].strip())
            i += 1
        text = " ".join(q for q in quote if q)
        return re.sub(r"^\*\*[^*]+:\*\*\s*", "", text)[:400]
    if doc.area == "wiki":
        return ""
    para: list[str] = []
    for s in doc.parsed.sections:
        for line in s.content_lines:
            if line.strip():
                para.append(line.strip())
            elif para:
                break
        if para:
            break
    return " ".join(para)[:200]


class Vault:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.root = cfg.root

    # --- Bestand ---
    def iter_files(self, areas: tuple[str, ...] = AREAS) -> Iterator[str]:
        for area in areas:
            base = self.root / area
            if not base.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
                for name in sorted(filenames):
                    if name.startswith("."):
                        continue
                    yield nfc((Path(dirpath) / name).relative_to(self.root).as_posix())

    def path(self, rel: str) -> Path:
        return safe_resolve(self.root, rel)

    def exists(self, rel: str) -> bool:
        return self.path(rel).is_file()

    def load(self, rel: str) -> Doc:
        p = self.path(rel)
        if not p.is_file():
            raise PkmError("not_found", f"Datei nicht gefunden: {rel}", target=rel)
        st = p.stat()
        if is_markdown(rel):
            return load_text_doc(rel, p.read_bytes(), st.st_size, st.st_mtime_ns)
        doc = Doc(rel, "bin", st.st_size, st.st_mtime_ns)
        doc.bin_hash = hashes.sha256_bytes(p.read_bytes())
        return doc

    # --- Adressierung (7.1) ---
    def resolve(
        self,
        target: str,
        areas: tuple[str, ...] = AREAS,
        find_id: Callable[[str], list[str]] | None = None,
    ) -> str:
        if not isinstance(target, str) or not target.strip():
            raise PkmError("not_found", "Leeres Ziel.")
        t = nfc(target.strip())
        if t.startswith("id:"):
            doc_id = t[3:].strip()
            if not is_valid_id(doc_id):
                raise PkmError("not_found", f"Ungültige ID: {doc_id}", target=target)
            found = [r for r in (find_id or self.scan_id)(doc_id) if r.split("/", 1)[0] in areas]
            return self._one(found, target)
        m = re.fullmatch(r"!?\[\[([^\]\|#]*)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]", t)
        if m:
            t = m.group(1).strip()
        t = t.replace("\\", "/").strip("/")
        if "/" in t:
            for cand in (t, f"{t}.md"):
                try:
                    p = self.path(cand)
                except PkmError:
                    raise
                if p.is_file():
                    rel = nfc(p.relative_to(self.root).as_posix())
                    if rel.split("/", 1)[0] not in areas:
                        raise PkmError("forbidden", f"Nur {', '.join(areas)} sind hier erlaubt.", target=target)
                    return rel
            raise PkmError("not_found", f"Nicht gefunden: {target}", target=target)
        key = link_key(t)
        found = []
        for rel in self.iter_files(areas):
            name = PurePosixPath(rel).name
            stem = name[:-3] if is_markdown(name) else name
            if stem.casefold() == key or name.casefold() == key:
                found.append(rel)
        return self._one(found, target)

    @staticmethod
    def _one(found: list[str], target: str) -> str:
        if not found:
            raise PkmError("not_found", f"Nicht gefunden: {target}", target=target)
        if len(found) > 1:
            raise PkmError("ambiguous", f"Mehrdeutig: {target}", target=target, candidates=sorted(found))
        return found[0]

    def scan_id(self, doc_id: str) -> list[str]:
        """ID ohne Index suchen (langsam, Rückfallebene)."""
        found = []
        for rel in self.iter_files():
            if not is_markdown(rel):
                continue
            try:
                head = self.path(rel).read_bytes()[:4096]
            except OSError:
                continue
            if doc_id.encode() in head and self.load(rel).id == doc_id:
                found.append(rel)
        return found


def section_summary(doc: Doc) -> list[dict[str, Any]]:
    if doc.parsed is None or doc.hashes is None:
        return []
    return [
        {"key": s.key, "level": s.level, "sha": hashes.short(doc.hashes.sections[s.key])}
        for s in doc.parsed.sections
    ]


__all__ = ["AREAS", "Doc", "PREAMBLE", "Vault", "extract_links", "link_key", "load_text_doc", "summary_of"]
