"""Textnormalisierung (Spezifikation 4.8, Schritt 1)."""

from __future__ import annotations

import unicodedata

from .errors import PkmError

BOM = "﻿"


def normalize_text(text: str) -> str:
    """BOM entfernen, Zeilenenden → LF, NFC, genau ein LF am Ende (leere Datei bleibt leer)."""
    if text.startswith(BOM):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    stripped = text.rstrip("\n")
    return stripped + "\n" if stripped else ""


def normalize_fragment(text: str) -> str:
    """Wie normalize_text, aber ohne Anpassung des Endes (für `old`/`new` in edit_document)."""
    if text.startswith(BOM):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PkmError("invalid_encoding", f"Datei ist kein gültiges UTF-8 ({exc.reason}).") from exc


def normalize_bytes(data: bytes) -> str:
    return normalize_text(decode(data))


def encode(text: str) -> bytes:
    """Schreibform: UTF-8 ohne BOM, LF, NFC, ein abschließendes LF."""
    return normalize_text(text).encode("utf-8")
