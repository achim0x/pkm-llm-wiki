"""Prüfung und Korrektur von Bild-Data-URIs (Spezifikation 4.9, „Prüfung bei der Übernahme“).

``image_issues`` meldet Abweichungen mit Befundcodes und Vorschlag; ``fix_text`` schreibt die Bilder
in der Form nach 4.9. Korrigiert wird nur nach Rückfrage; diese Funktionen ändern selbst keine Dateien,
außer ``fix_text`` legt mit einem Writer Bilddateien in ``documents/_attachments/`` an.

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

import base64
import hashlib
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from . import images
from .errors import PkmError
from .fsutil import write_bytes_atomic
from .imagescan import find_data_images
from .paths import MAX_NAME, slugify

if TYPE_CHECKING:
    from .config import ImageConfig
    from .writer import Writer

# Variables *******************************************************************

ATTACHMENTS = "documents/_attachments"
LEGACY_PROBLEMS = ("reference_style", "html_img", "angle_brackets", "base64_whitespace", "media_type_mismatch",
                   "invalid_data")
NOTATION_PROBLEMS = {"reference": "reference_style", "html": "html_img", "angle": "angle_brackets"}
MIME = {"png": "png", "jpg": "jpeg", "gif": "gif", "webp": "webp"}
SVG_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# Classes *********************************************************************


@dataclass
class Analysis:  # pylint: disable=too-many-instance-attributes
    """Prüfergebnis eines eingebetteten Bildes.

    Attributes:
        ref: Bild.
        problems: Befundcodes.
        fmt: Format nach der Signatur (``png``, ``jpg``, ``svg``, ``gif``, ``webp`` oder leer).
        data: Dekodierte Bytes.
        legacy: Bestehendes Base64-PNG/JPEG (nur Schreibweise wird geprüft).
        removed: Bei SVG die Teile, die die Bereinigung entfernt.
        line: Zeilenindex (0-basiert) der Verwendung.
        fixable: Ob eine Korrektur möglich ist.
        note: Hinweis, warum keine Korrektur möglich ist.
    """

    ref: images.ImageRef
    problems: list[str] = field(default_factory=list)
    fmt: str = ""
    data: bytes = b""
    legacy: bool = False
    removed: list[str] = field(default_factory=list)
    line: int = 0
    fixable: bool = True
    note: str = ""

# Functions *******************************************************************


# Prüfen **********************************************************************
def _header(link: str) -> tuple[str, list[str], bool, str]:
    """Kopf einer Data-URI zerlegen.

    Args:
        link: Data-URI.

    Returns:
        Tupel aus (Medientyp, Zusätze ohne ``base64``, Base64, Nutzdaten).
    """
    head, _, payload = link.partition(",")
    parts = [p.strip().lower() for p in head[5:].split(";")]
    return parts[0], [p for p in parts[1:] if p and p != "base64"], "base64" in parts[1:], payload


def signature(data: bytes) -> str:
    """Format an den ersten Bytes erkennen.

    Args:
        data: Bytes.

    Returns:
        ``png``, ``jpg``, ``gif``, ``webp``, ``svg`` oder leer.
    """
    head = data[:512].lstrip().lower()
    fmt = ""
    if data.startswith(images.PNG_SIGNATURE):
        fmt = "png"
    elif data.startswith(b"\xff\xd8"):
        fmt = "jpg"
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        fmt = "gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        fmt = "webp"
    elif head.startswith(b"<") and b"<svg" in head:
        fmt = "svg"
    return fmt


def _decode(link: str) -> bytes:
    """Data-URI dekodieren (auch mit Leerraum im Base64 und nicht kodiertem SVG).

    Args:
        link: Data-URI.

    Returns:
        Bytes (leer, wenn nicht dekodierbar).
    """
    _, _, b64, payload = _header(link)
    try:
        data = base64.b64decode(re.sub(r"\s+", "", payload), validate=True) if b64 else unquote(payload).encode("utf-8")
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        data = b""
    return data


def _own_line(text: str, ref: images.ImageRef, starts: list[int]) -> bool:
    """Prüfen, ob ein Bild allein in seiner Zeile steht.

    Args:
        text: Markdown.
        ref: Bild.
        starts: Startpositionen aller Bilder.

    Returns:
        ``True``, wenn die Zeile außer dem Bild nur Leerraum enthält.
    """
    line_start = text.rfind("\n", 0, ref.start) + 1
    line_end = text.find("\n", ref.end)
    line_end = len(text) if line_end < 0 else line_end
    others = [s for s in starts if line_start <= s < line_end and s != ref.start]
    return not (text[line_start:ref.start].strip() or text[ref.end:line_end].strip() or others)


def _svg_checks(a: Analysis, payload: str, params: list[str], b64: bool, limits: ImageConfig) -> None:
    """SVG-spezifische Befunde.

    Args:
        a: Prüfergebnis (wird ergänzt).
        payload: Nutzdaten der URI.
        params: Zusätze im Medientyp.
        b64: Base64-kodiert.
        limits: Bildgrenzen.
    """
    if params:
        a.problems.append("svg_parameters")
    if b64:
        a.problems.append("svg_base64")
    elif any(ch in images.URL_UNSAFE for ch in re.sub(r"%[0-9A-Fa-f]{2}", "", payload)):
        a.problems.append("unencoded_chars")
    svg = a.data.decode("utf-8", "replace")
    a.removed = images.svg_problems(svg)
    if a.removed:
        a.problems.append("svg_unsafe")
    try:
        images.sanitize_svg(svg, limits.svg_max_kb)
    except PkmError as exc:
        if exc.status == "svg_too_complex" and "Rastergrafik" in exc.message:
            a.fixable, a.note = False, "SVG mit eingebetteter Rastergrafik; als PNG neu ablegen"
        elif exc.status == "svg_too_complex":
            a.problems.append("too_large_for_inline")
        else:
            a.problems.append("invalid_data")
            a.fixable, a.note = False, exc.message


def analyze(  # pylint: disable=too-many-arguments
    text: str, ref: images.ImageRef, limits: ImageConfig, *, legacy: bool, scratch: bool, wiki: bool,
    starts: list[int], names: dict[str, int],
) -> Analysis:
    """Ein eingebettetes Bild nach 4.9 prüfen.

    Args:
        text: Markdown.
        ref: Bild.
        limits: Bildgrenzen.
        legacy: Bestehende Base64-PNG/JPEG nur auf Schreibweise prüfen.
        scratch: Ziel liegt in ``scratch/`` (keine Dateien).
        wiki: Wiki-Seite (keine Dateien, keine Größengrenze).
        starts: Startpositionen aller Bilder.
        names: Anzahl je ausdrücklich gesetztem Bildnamen.

    Returns:
        Das Prüfergebnis.
    """
    occ = ref.occ
    mime, params, b64, payload = _header(ref.link)
    a = Analysis(ref, line=text.count("\n", 0, ref.start))
    a.data = _decode(ref.link)
    a.fmt = signature(a.data)
    declared = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/svg+xml": "svg",
                "image/gif": "gif", "image/webp": "webp"}.get(mime, "")
    if occ is not None and occ.notation in NOTATION_PROBLEMS:
        a.problems.append(NOTATION_PROBLEMS[occ.notation])
    a.legacy = legacy and b64 and a.fmt in ("png", "jpg")
    if not a.data or not a.fmt:
        a.problems.append("invalid_data")
        a.fixable, a.note = False, "nicht dekodierbar oder kein Bild"
    elif a.fmt in ("png", "jpg") and b64 and re.search(r"\s", payload):
        a.problems.append("base64_whitespace")
    if a.data and a.fmt and declared != a.fmt:
        a.problems.append("media_type_mismatch")
    if a.fmt == "svg":
        _svg_checks(a, payload, params, b64, limits)
    if a.fmt in ("gif", "webp"):
        a.problems.append("unsupported_type")
        a.fixable = a.fixable and not (scratch or wiki)
    if a.legacy:
        a.problems = [p for p in a.problems if p in LEGACY_PROBLEMS]
    elif a.fmt:
        _strict_checks(a, text, limits, scratch or wiki, starts, names)
    return a


def _strict_checks(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    a: Analysis, text: str, limits: ImageConfig, no_files: bool, starts: list[int],
                   names: dict[str, int]) -> None:
    """Prüfungen für neue Bilder: Zeile, Name, Alternativtext, Größe.

    Args:
        a: Prüfergebnis (wird ergänzt).
        text: Markdown.
        limits: Bildgrenzen.
        no_files: Keine Dateien möglich (``scratch/``, Wiki).
        starts: Startpositionen aller Bilder.
        names: Anzahl je ausdrücklich gesetztem Bildnamen.
    """
    ref = a.ref
    title = ref.occ.title if ref.occ is not None else None
    if not _own_line(text, ref, starts):
        a.problems.append("not_own_line")
    if not title or not title.startswith("pkm:"):
        a.problems.append("missing_name")
    elif not ref.named:
        a.problems.append("invalid_name")
    elif names.get(ref.name, 0) > 1:
        a.problems.append("duplicate_name")
    if not ref.alt:
        a.problems.append("missing_alt")
    if not no_files and a.fixable and a.fmt in ("png", "jpg", "svg") and "too_large_for_inline" not in a.problems:
        if len(_conforming_uri(a)) > limits.inline_max_kb * 1024:
            a.problems.append("too_large_for_inline")


def _conforming_uri(a: Analysis) -> str:
    """Data-URI des Bildes in der Form nach 4.9.

    Args:
        a: Prüfergebnis.

    Returns:
        Data-URI (SVG bereinigt; Rasterbilder mit unveränderten Bytes).
    """
    if a.fmt == "svg":
        svg = images.sanitize_svg(a.data.decode("utf-8", "replace"), 10 ** 6)
        uri = images.svg_data_uri(svg)
    else:
        uri = f"data:image/{MIME.get(a.fmt, a.fmt)};base64," + base64.b64encode(a.data).decode("ascii")
    return uri


def _suggested_alt(a: Analysis, section_of: Any) -> str:
    """Vorschlag für einen fehlenden Alternativtext.

    Args:
        a: Prüfergebnis.
        section_of: Funktion Position → Abschnitt.

    Returns:
        Referenzname, SVG-``<title>`` oder umgebende Überschrift (leer, wenn nichts passt).
    """
    occ = a.ref.occ
    title = SVG_TITLE_RE.search(a.data.decode("utf-8", "replace")) if a.fmt == "svg" else None
    candidates = [occ.label if occ is not None and occ.label else "", title.group(1).strip() if title else "",
                  section_of(a.ref.start) or "" if section_of else ""]
    return next((c for c in candidates if c and c != "_preamble"), "")


def _issue(text: str, a: Analysis, section_of: Any, scratch: bool) -> dict[str, Any]:
    """Eintrag für ``image_issues``.

    Args:
        text: Markdown.
        a: Prüfergebnis.
        section_of: Funktion Position → Abschnitt.
        scratch: Ziel in ``scratch/``.

    Returns:
        ``ref``, ``line``, ``section``, ``format``, ``size``, ``problems``, ``fixable``, ``proposal``.
    """
    occ = a.ref.occ
    many = occ is not None and len(occ.usages) > 1
    mode = "file" if not scratch and {"too_large_for_inline", "unsupported_type"} & set(a.problems) else "inline"
    proposal = {"name": a.ref.name, "alt": a.ref.alt or _suggested_alt(a, section_of),
                "mode": mode, "removed": a.removed}
    if a.legacy:
        proposal = {"name": None, "alt": a.ref.alt, "mode": "inline", "removed": []}
    entry: dict[str, Any] = {"ref": a.ref.name, "line": a.line + 1, "section": section_of(a.ref.start) if section_of
                             else None, "format": a.fmt, "size": len(a.data), "problems": a.problems,
                             "fixable": a.fixable, "proposal": proposal}
    if many:
        entry["note"] = "Referenz mehrfach verwendet: " + ", ".join(
            str(text.count("\n", 0, s) + 1) for s, _ in occ.usages) + " (Zeilen); Bild nur an einer Stelle möglich"
    elif a.note:
        entry["note"] = a.note
    return entry


def analyses(  # pylint: disable=too-many-arguments
    text: str, limits: ImageConfig, *, legacy: bool = True, scratch: bool = False, wiki: bool = False,
             only_links: set[str] | None = None) -> list[Analysis]:
    """Alle eingebetteten Bilder eines Textes prüfen.

    Args:
        text: Markdown.
        limits: Bildgrenzen.
        legacy: Bestehende Base64-PNG/JPEG nur auf Schreibweise prüfen.
        scratch: Ziel in ``scratch/``.
        wiki: Wiki-Seite.
        only_links: Nur Bilder mit diesen URIs prüfen (z. B. neue im übergebenen Text).

    Returns:
        Prüfergebnisse aller geprüften Bilder (auch ohne Befund).
    """
    refs = images.find_images(text)
    starts = [r.start for r in refs]
    names: dict[str, int] = {}
    for r in refs:
        if r.named:
            names[r.name] = names.get(r.name, 0) + 1
    return [analyze(text, r, limits, legacy=legacy, scratch=scratch, wiki=wiki, starts=starts, names=names)
            for r in refs if r.inline and (only_links is None or r.link in only_links)]


def unused_definitions(text: str) -> list[dict[str, Any]]:
    """Referenzdefinitionen mit Data-URI, die nirgends verwendet werden.

    Args:
        text: Markdown.

    Returns:
        Einträge für ``image_issues`` (``problems: [unused_definition]``).
    """
    out = []
    for occ in find_data_images(text):
        if occ.notation == "reference" and not occ.usages and occ.def_span is not None:
            out.append({"ref": slugify(occ.label or "bild", 40), "line": text.count("\n", 0, occ.def_span[0]) + 1,
                        "section": None, "format": "", "size": occ.uri_end - occ.uri_start,
                        "problems": ["unused_definition"], "fixable": True,
                        "proposal": {"name": None, "alt": "", "mode": "remove", "removed": ["definition"]}})
    return out


def image_issues(  # pylint: disable=too-many-arguments
    text: str, limits: ImageConfig, *, legacy: bool = True, scratch: bool = False, wiki: bool = False,
                 section_of: Any = None, only_links: set[str] | None = None) -> list[dict[str, Any]]:
    """Befunde zu abweichenden Data-URIs (4.9).

    Args:
        text: Markdown.
        limits: Bildgrenzen.
        legacy: Bestehende Base64-PNG/JPEG nur auf Schreibweise prüfen.
        scratch: Ziel in ``scratch/``.
        wiki: Wiki-Seite.
        section_of: Funktion Position → Abschnitt.
        only_links: Nur Bilder mit diesen URIs prüfen.

    Returns:
        Je abweichendem Bild ein Eintrag, dazu unbenutzte Definitionen (nur ohne ``only_links``).
    """
    found = [_issue(text, a, section_of, scratch)
             for a in analyses(text, limits, legacy=legacy, scratch=scratch, wiki=wiki, only_links=only_links)
             if a.problems]
    return found + (unused_definitions(text) if only_links is None else [])


# Korrigieren *****************************************************************
def _unique(name: str, used: set[str]) -> str:
    """Eindeutigen Namen bilden (Suffix ``-2``, ``-3``).

    Args:
        name: Wunschname.
        used: Vergebene Namen (wird ergänzt).

    Returns:
        Der Name.
    """
    candidate, k = name, 1
    while candidate in used:
        k += 1
        candidate = f"{name}-{k}"
    used.add(candidate)
    return candidate


def _target_link(a: Analysis, writer: Writer | None, doc_rel: str, files: list[str]) -> str:
    """Ablage als Datei in ``documents/_attachments/`` (bei Probeläufen nur der künftige Pfad).

    Args:
        a: Prüfergebnis.
        writer: Writer oder ``None`` (Vorschlag ohne Schreiben).
        doc_rel: Pfad des Dokuments.
        files: Neu geschriebene Dateien (wird ergänzt).

    Returns:
        Relativer Link auf die Datei.
    """
    stem = slugify(a.ref.name, MAX_NAME)
    if writer is None:
        rel = f"{ATTACHMENTS}/{stem}_YYYY-MM-DD.{a.fmt}"
    else:
        rel = writer.free_name(ATTACHMENTS, stem, f"_{writer.svc.now().date().isoformat()}", f".{a.fmt}")
        write_bytes_atomic(writer.vault.path(rel), a.data)
        files.append(rel)
    return images.relative_link(doc_rel, rel)


def _replacement(a: Analysis, ctx: dict[str, Any]) -> str:
    """Bild in der Form nach 4.9.

    Args:
        a: Prüfergebnis.
        ctx: ``writer``, ``doc_rel``, ``files``, ``used``, ``image_alt``, ``proposals``.

    Returns:
        Markdown des Bildes (ohne Zeilenumbrüche).
    """
    ref, occ = a.ref, a.ref.occ
    width = f"|{occ.width}" if occ is not None and occ.width else ""
    raw_alt = (occ.alt if occ is not None else ref.alt) or ""
    if a.legacy:
        title = f' "{occ.title}"' if occ is not None and occ.title else ""
        uri = f"data:image/{MIME[a.fmt]};base64," + base64.b64encode(a.data).decode("ascii")
        result = f"![{raw_alt}{width if '|' not in raw_alt else ''}]({uri}{title})"
    else:
        name = ref.name
        if "duplicate_name" in a.problems and name in ctx["kept"]:
            name = _unique(name, ctx["used"])
        ctx["kept"].add(name)
        alt = ctx["image_alt"].get(ref.name) or ref.alt or ctx["proposals"].get(ref.name, "")
        alt = " ".join(str(alt).split()).replace("[", "(").replace("]", ")")
        keep_width = raw_alt.split("|", 1)[1] if "|" in raw_alt else occ.width if occ is not None else None
        alt = f"{alt}|{keep_width}" if keep_width else alt
        to_file = not ctx["no_files"] and {"too_large_for_inline", "unsupported_type"} & set(a.problems)
        link = _target_link(a, ctx["writer"], ctx["doc_rel"], ctx["files"]) if to_file else _conforming_uri(a)
        result = f'![{alt}]({link} "pkm:{name}")'
    return result


def _line_wrapped(text: str, start: int, end: int, line: str) -> tuple[int, int, str]:
    """Ersatz so einrahmen, dass das Bild in einer eigenen Zeile steht; der Text drumherum bleibt.

    Leerzeichen direkt vor bzw. nach dem Bild werden durch den Zeilenumbruch ersetzt.

    Args:
        text: Markdown.
        start: Beginn des Bildes.
        end: Ende des Bildes.
        line: Neues Bild.

    Returns:
        Tupel aus (Beginn, Ende, Ersatztext).
    """
    before = text[text.rfind("\n", 0, start) + 1:start]
    after_end = text.find("\n", end)
    after = text[end:len(text) if after_end < 0 else after_end]
    if before.strip():
        start -= len(before) - len(before.rstrip(" \t"))
    if after.strip():
        end += len(after) - len(after.lstrip(" \t"))
    return start, end, ("\n" if before.strip() else "") + line + ("\n" if after.strip() else "")


def fix_text(  # pylint: disable=too-many-arguments,too-many-locals
    text: str, limits: ImageConfig, *, writer: Writer | None = None, doc_rel: str = "", names: list[str] | None = None,
    image_alt: dict[str, str] | None = None, confirm_shortening: bool = False, legacy: bool = True,
    scratch: bool = False, wiki: bool = False, only_links: set[str] | None = None,
) -> tuple[str, list[str]]:
    """Abweichende Data-URIs nach 4.9 korrigieren; der übrige Text bleibt byte-genau erhalten.

    Args:
        text: Markdown.
        limits: Bildgrenzen.
        writer: Writer zum Anlegen von Bilddateien (``None``: nur Vorschlag, keine Dateien).
        doc_rel: Pfad des Dokuments.
        names: Nur diese Bilder (Namen aus ``image_issues``).
        image_alt: Alternativtexte je Name.
        confirm_shortening: Entfernen unbenutzter Definitionen bestätigt.
        legacy: Bestehende Base64-PNG/JPEG nur in der Schreibweise korrigieren.
        scratch: Ziel in ``scratch/``.
        wiki: Wiki-Seite.
        only_links: Nur Bilder mit diesen URIs.

    Returns:
        Tupel aus (neuer Text, neu geschriebene Bilddateien).

    Raises:
        PkmError: ``ambiguous`` bei mehrfach verwendeten Referenzen, ``large_shortening`` bei
            unbenutzten Definitionen ohne Bestätigung.
    """
    found = [a for a in analyses(text, limits, legacy=legacy, scratch=scratch, wiki=wiki, only_links=only_links)
             if a.problems and a.fixable and (names is None or a.ref.name in names)]
    ctx: dict[str, Any] = {"writer": writer, "doc_rel": doc_rel, "files": [], "image_alt": dict(image_alt or {}),
                           "used": {r.name for r in images.find_images(text)}, "no_files": scratch or wiki,
                           "kept": set(),
                           "proposals": {i["ref"]: i["proposal"]["alt"] for i in image_issues(
                               text, limits, legacy=legacy, scratch=scratch, wiki=wiki, only_links=only_links)}}
    spans: list[tuple[int, int, str]] = []
    for a in found:
        occ = a.ref.occ
        if occ is not None and len(occ.usages) > 1:
            raise PkmError("ambiguous", f"Referenz [{occ.label}] wird mehrfach verwendet; Bildnamen sind eindeutig.",
                           lines=[text.count("\n", 0, s) + 1 for s, _ in occ.usages], image=a.ref.name)
        spans.append(_line_wrapped(text, a.ref.start, a.ref.end, _replacement(a, ctx)))
        if occ is not None and occ.def_span is not None:
            spans.append((occ.def_span[0], occ.def_span[1], ""))
    unused = [u for u in unused_definitions(text) if only_links is None and (names is None or u["ref"] in names)]
    if unused and not confirm_shortening:
        raise PkmError("large_shortening", "Unbenutzte Bild-Definitionen würden entfernt; bitte bestätigen "
                       "(confirm_shortening).", removed_images=[u["ref"] for u in unused])
    for occ in find_data_images(text) if unused else []:
        if occ.notation == "reference" and not occ.usages and occ.def_span is not None:
            spans.append((occ.def_span[0], occ.def_span[1], ""))
    out, pos = [], 0
    for start, end, repl in sorted(spans):
        out += [text[pos:start], repl]
        pos = end
    return "".join(out) + text[pos:], ctx["files"]


# Vergleich *******************************************************************
def canonical(text: str, limits: ImageConfig) -> tuple[str, list[str]]:
    """Text für den Vergleich „nur Bildschreibweise geändert“ (4.9, Belege nach einer Korrektur).

    Jedes eingebettete Bild wird zu ``![<alt>](pkm-image:<name>)``, Referenzdefinitionen entfallen,
    Leerraum wird zusammengefasst. Dazu die Hashes der dekodierten Bilder (SVG nach der Bereinigung;
    unsichere SVG bekommen einen eigenen Marker, damit sie als geändert gelten).

    Args:
        text: Markdown (z. B. ein Abschnitt).
        limits: Bildgrenzen.

    Returns:
        Tupel aus (kanonischer Text, Bild-Hashes in Reihenfolge).
    """
    spans: list[tuple[int, int, str]] = []
    digests: list[str] = []
    for a in analyses(text, limits, legacy=True):
        spans.append((a.ref.start, a.ref.end, f"![{a.ref.alt}](pkm-image:{a.ref.name})"))
        if a.ref.occ is not None and a.ref.occ.def_span is not None:
            spans.append((a.ref.occ.def_span[0], a.ref.occ.def_span[1], ""))
        data = a.data
        if a.fmt == "svg":
            try:
                data = images.sanitize_svg(a.data.decode("utf-8", "replace"), 10 ** 6).encode("utf-8")
            except PkmError:
                data = a.data
        digests.append(("unsafe:" if a.removed else "") + hashlib.sha256(data).hexdigest())
    for occ in find_data_images(text):
        if occ.notation == "reference" and not occ.usages and occ.def_span is not None:
            spans.append((occ.def_span[0], occ.def_span[1], ""))
    out, pos = [], 0
    for start, end, repl in sorted(set(spans)):
        if start >= pos:
            out += [text[pos:start], repl]
            pos = end
    return " ".join(("".join(out) + text[pos:]).split()), digests


def body_notation_only(old: str, new: str, limits: ImageConfig) -> bool:
    """Prüfen, ob sich zwei ganze Bodys nur in der Bildschreibweise unterscheiden.

    Args:
        old: Früherer Body.
        new: Aktueller Body.
        limits: Bildgrenzen.

    Returns:
        Wie ``notation_only`` für den ganzen Text (erfasst auch Referenzen über Abschnitte hinweg).
    """
    return notation_only(old, new, limits)


def notation_only(old: str, new: str, limits: ImageConfig) -> bool:
    """Prüfen, ob sich zwei Texte nur in der Bildschreibweise unterscheiden.

    Args:
        old: Früherer Text.
        new: Aktueller Text.
        limits: Bildgrenzen.

    Returns:
        ``True``, wenn sie verschieden sind, kanonisch aber gleich, und kein Bild unsicher war.
    """
    a, b = canonical(old, limits), canonical(new, limits)
    return old != new and a == b and not any(d.startswith("unsafe:") for d in a[1])

# Main ************************************************************************
