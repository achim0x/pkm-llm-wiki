"""Textnormalisierung (Spezifikation 4.8, Schritt 1).

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

import unicodedata

from .errors import PkmError

# Variables *******************************************************************

BOM = "﻿"

# Classes *********************************************************************

# Functions *******************************************************************


def normalize_fragment(text: str) -> str:
    """BOM entfernen, Zeilenenden auf LF und Unicode auf NFC bringen; das Ende bleibt unverändert.

    Args:
        text: Textstück, z. B. ``old``/``new`` von ``edit_document``.

    Returns:
        Normalisierter Text.
    """
    if text.startswith(BOM):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def normalize_text(text: str) -> str:
    """Datei-Text normalisieren: wie ``normalize_fragment`` plus genau ein LF am Ende.

    Args:
        text: Vollständiger Dateiinhalt.

    Returns:
        Normalisierter Text; eine leere Datei bleibt leer.
    """
    stripped = normalize_fragment(text).rstrip("\n")
    return stripped + "\n" if stripped else ""


def decode(data: bytes) -> str:
    """Bytes als UTF-8 dekodieren.

    Args:
        data: Dateiinhalt.

    Returns:
        Der dekodierte Text.

    Raises:
        PkmError: ``invalid_encoding``, wenn die Bytes kein gültiges UTF-8 sind.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PkmError("invalid_encoding", f"Datei ist kein gültiges UTF-8 ({exc.reason}).") from exc
    return text


def normalize_bytes(data: bytes) -> str:
    """Bytes dekodieren und normalisieren.

    Args:
        data: Dateiinhalt.

    Returns:
        Normalisierter Text.

    Raises:
        PkmError: ``invalid_encoding`` bei ungültigem UTF-8.
    """
    return normalize_text(decode(data))


def encode(text: str) -> bytes:
    """Text in die Schreibform bringen: UTF-8 ohne BOM, LF, NFC, ein abschließendes LF.

    Args:
        text: Zu schreibender Text.

    Returns:
        Die zu schreibenden Bytes.
    """
    return normalize_text(text).encode("utf-8")

# Main ************************************************************************
