"""Normalisierung, Abschnitte und Hashes (Spezifikation 4.8, Tests aus 14).

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

import hashlib
import json
from pathlib import Path

import pytest

from pkm import hashes
from pkm.errors import PkmError
from pkm.normalize import decode, encode, normalize_bytes, normalize_fragment, normalize_text
from pkm.parse import normalize_key_input, parse

# Variables *******************************************************************

VECTORS = json.loads((Path(__file__).parent / "vectors" / "sections.json").read_text(encoding="utf-8"))

# Classes *********************************************************************

# Functions *******************************************************************


def sha(s: str) -> str:
    """SHA-256 eines Texts (unabhängige Vergleichsberechnung).

    Args:
        s: Text.

    Returns:
        64 Hex-Zeichen.
    """
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# Schritt 1 *******************************************************************
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("\ufeffa\n", "a\n"),
        ("a\r\nb\r\n", "a\nb\n"),
        ("a\rb\r", "a\nb\n"),
        ("a", "a\n"),
        ("a\n\n\n", "a\n"),
        ("", ""),
        ("\n\n", ""),
        ("U\u0308ber\n", "Über\n"),  # NFD → NFC
        ("a  \nb\n", "a  \nb\n"),  # Leerzeichen in Zeilen bleiben
    ],
)
def test_normalize_text(raw, expected):
    """Normalisierung nach 4.8, Schritt 1."""
    assert normalize_text(raw) == expected


def test_invalid_utf8():
    """Ungültiges UTF-8 ergibt invalid_encoding."""
    with pytest.raises(PkmError) as e:
        decode(b"\xff\xfeabc")
    assert e.value.status == "invalid_encoding"


def test_crlf_and_lf_same_hash():
    """CRLF- und LF-Fassung haben denselben Datei-Hash."""
    lf = normalize_bytes("---\ntitle: Ä\n---\n## A\nx\n".encode())
    crlf = normalize_bytes("\ufeff---\r\ntitle: Ä\r\n---\r\n## A\r\nx\r\n".encode())
    assert hashes.file_hash(lf) == hashes.file_hash(crlf)


def test_encode_write_form():
    """Die Schreibform ist UTF-8 ohne BOM mit LF am Ende."""
    assert encode("\ufeffa\r\nb") == b"a\nb\n"


def test_fragment_keeps_end():
    """Fragmente behalten ihr Ende."""
    assert normalize_fragment("a\r\nb") == "a\nb"


# Schritte 2–4 mit Testvektoren ***********************************************
@pytest.mark.parametrize("vec", VECTORS, ids=[v["name"] for v in VECTORS])
def test_vectors(vec):
    """Abschnitte und Hashes stimmen mit den Testvektoren überein."""
    text = normalize_text(vec["input"])
    p = parse(text)
    if vec.get("fm_error"):
        assert p.fm_error
        return
    assert p.fm_error is None
    if "meta" in vec:
        assert p.meta == vec["meta"]
    assert [[s.key, hashes.normalize_section_content(s.content_lines)] for s in p.sections] == vec["sections"]
    expected = {k: sha(c) for k, c in vec["sections"]}
    assert hashes.section_hashes(p) == expected
    assert hashes.body_hash(p) == sha("".join(f"{k}\t{sha(c)}\n" for k, c in vec["sections"]))


def test_whitespace_change_keeps_section_hash():
    """Reine Leerraum-Änderungen ändern den Abschnitts-Hash nicht."""
    a = parse(normalize_text("## A\nx\n\ny\n"))
    b = parse(normalize_text("## A\n\nx   \n\n\n\ny\n\n## B\n"))
    assert hashes.section_hashes(a)["A"] == hashes.section_hashes(b)["A"]


def test_empty_section_hash():
    """Ein leerer Abschnitt hat den Hash des leeren Strings."""
    p = parse("## A\n")
    assert hashes.section_hashes(p)["A"] == sha("")


def test_updated_changes_only_file_hash():
    """Eine Änderung nur an date_updated ändert nur den Datei-Hash."""
    t1 = normalize_text("---\nid: d-20261031-2340-k7q2\ntitle: T\ndate_updated: 2026-11-01T10:00:00\n---\n## A\nx\n")
    t2 = t1.replace("10:00:00", "11:00:00")
    h1, h2 = hashes.compute(t1, parse(t1)), hashes.compute(t2, parse(t2))
    assert h1.file_hash != h2.file_hash
    assert h1.body_hash == h2.body_hash
    assert h1.meta_hash == h2.meta_hash


def test_meta_hash_fields():
    """meta_hash umfasst title, short_citation, date_document, tags, related und kind als Zeichenketten."""
    p = parse("---\ntitle: T\nshort_citation: EN 1:2014\ndate_document: 2014\ntags: [a, b]\nkind: note\n"
              "version: 3\nstatus_markdown: draft\ndate_markdown: 2026-10-25\n---\n")
    canon = json.dumps({"date_document": "2014", "kind": "note", "short_citation": "EN 1:2014", "tags": ["a", "b"],
                        "title": "T"}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert hashes.meta_hash(p.meta) == sha(canon)
    p2 = parse("---\ntitle: T\ntags: [a, c]\n---\n")
    assert hashes.meta_hash(p2.meta) != hashes.meta_hash(p.meta)


def test_meta_hash_ignores_status_and_reads_legacy_name():
    """status_markdown ändert meta_hash nicht; „short citation“ zählt wie short_citation."""
    base = "---\ntitle: T\nshort_citation: EN 1:2014\nstatus_markdown: draft\n---\n"
    released = base.replace("draft", "released")
    legacy = base.replace("short_citation:", "short citation:")
    hashes_ = {hashes.meta_hash(parse(t).meta) for t in (base, released, legacy)}
    assert len(hashes_) == 1


def test_timestamps_stay_strings():
    """Zeitstempel im Frontmatter bleiben Strings."""
    p = parse("---\ncreated: 2026-10-31T23:40:12+01:00\n---\n")
    assert p.meta["created"] == "2026-10-31T23:40:12+01:00"


def test_reorder_changes_body_hash_not_sections():
    """Umsortieren ändert body_hash, nicht die Abschnitts-Hashes."""
    a = parse("## A\nx\n## B\ny\n")
    b = parse("## B\ny\n## A\nx\n")
    assert hashes.section_hashes(a) == hashes.section_hashes(b)
    assert hashes.body_hash(a) != hashes.body_hash(b)


def test_short_and_matches():
    """Kurz-Hash und Präfixvergleich."""
    h = sha("x")
    assert hashes.short(h) == h[:6]
    assert hashes.matches(h, h[:6].upper())
    assert not hashes.matches(h, "")


@pytest.mark.parametrize(
    "inp, key",
    [("Ergebnis", "Ergebnis"), ("## Offene  Punkte", "Offene Punkte"), ("Notizen#2", "Notizen#2"),
     ("_preamble", "_preamble"), ("  Kontext / Begründung ", "Kontext / Begründung")],
)
def test_normalize_key_input(inp, key):
    """Eingaben für section werden in Schlüssel umgewandelt."""
    assert normalize_key_input(inp) == key

# Main ************************************************************************
