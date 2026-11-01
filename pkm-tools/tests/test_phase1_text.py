"""Normalisierung, Abschnitte und Hashes (Spezifikation 4.8, Tests aus 14)."""

import hashlib
import json
from pathlib import Path

import pytest

from pkm import hashes
from pkm.errors import PkmError
from pkm.normalize import decode, encode, normalize_bytes, normalize_fragment, normalize_text
from pkm.parse import normalize_key_input, parse

VECTORS = json.loads((Path(__file__).parent / "vectors" / "sections.json").read_text(encoding="utf-8"))


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# --- Schritt 1 ---
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
    assert normalize_text(raw) == expected


def test_invalid_utf8():
    with pytest.raises(PkmError) as e:
        decode(b"\xff\xfeabc")
    assert e.value.status == "invalid_encoding"


def test_crlf_and_lf_same_hash():
    lf = normalize_bytes("---\ntitle: Ä\n---\n## A\nx\n".encode())
    crlf = normalize_bytes("\ufeff---\r\ntitle: Ä\r\n---\r\n## A\r\nx\r\n".encode())
    assert hashes.file_hash(lf) == hashes.file_hash(crlf)


def test_encode_write_form():
    assert encode("\ufeffa\r\nb") == b"a\nb\n"


def test_fragment_keeps_end():
    assert normalize_fragment("a\r\nb") == "a\nb"


# --- Schritte 2–4 mit Testvektoren ---
@pytest.mark.parametrize("vec", VECTORS, ids=[v["name"] for v in VECTORS])
def test_vectors(vec):
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
    a = parse(normalize_text("## A\nx\n\ny\n"))
    b = parse(normalize_text("## A\n\nx   \n\n\n\ny\n\n## B\n"))
    assert hashes.section_hashes(a)["A"] == hashes.section_hashes(b)["A"]


def test_empty_section_hash():
    p = parse("## A\n")
    assert hashes.section_hashes(p)["A"] == sha("")


def test_updated_changes_only_file_hash():
    t1 = normalize_text("---\nid: d-20261031-2340-k7q2\ntitle: T\nupdated: 2026-11-01T10:00:00+01:00\n---\n## A\nx\n")
    t2 = t1.replace("10:00:00", "11:00:00")
    h1, h2 = hashes.compute(t1, parse(t1)), hashes.compute(t2, parse(t2))
    assert h1.file_hash != h2.file_hash
    assert h1.body_hash == h2.body_hash
    assert h1.meta_hash == h2.meta_hash


def test_meta_hash_fields():
    p = parse("---\ntitle: T\ntopics: [a, b]\nkind: note\nversion: 3\n---\n")
    canon = json.dumps({"kind": "note", "title": "T", "topics": ["a", "b"]}, sort_keys=True,
                       ensure_ascii=False, separators=(",", ":"))
    assert hashes.meta_hash(p.meta) == sha(canon)
    p2 = parse("---\ntitle: T\ntopics: [a, c]\n---\n")
    assert hashes.meta_hash(p2.meta) != hashes.meta_hash(p.meta)


def test_timestamps_stay_strings():
    p = parse("---\ncreated: 2026-10-31T23:40:12+01:00\n---\n")
    assert p.meta["created"] == "2026-10-31T23:40:12+01:00"


def test_reorder_changes_body_hash_not_sections():
    a = parse("## A\nx\n## B\ny\n")
    b = parse("## B\ny\n## A\nx\n")
    assert hashes.section_hashes(a) == hashes.section_hashes(b)
    assert hashes.body_hash(a) != hashes.body_hash(b)


def test_short_and_matches():
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
    assert normalize_key_input(inp) == key
