"""Text normalization (specification 4.8, step 1).

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

import unicodedata

from .errors import PkmError

# Variables *******************************************************************

BOM = "﻿"

# Classes *********************************************************************

# Functions *******************************************************************


def normalize_fragment(text: str) -> str:
    """Remove a BOM, convert line endings to LF and Unicode to NFC; the end stays unchanged.

    Args:
        text: Text fragment, e.g. ``old``/``new`` of ``edit_document``.

    Returns:
        Normalized text.
    """
    if text.startswith(BOM):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def normalize_text(text: str) -> str:
    """Normalize file text: like ``normalize_fragment`` plus exactly one LF at the end.

    Args:
        text: Complete file content.

    Returns:
        Normalized text; an empty file stays empty.
    """
    stripped = normalize_fragment(text).rstrip("\n")
    return stripped + "\n" if stripped else ""


def decode(data: bytes) -> str:
    """Decode bytes as UTF-8.

    Args:
        data: File content.

    Returns:
        The decoded text.

    Raises:
        PkmError: ``invalid_encoding`` if the bytes are not valid UTF-8.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PkmError("invalid_encoding", f"File is not valid UTF-8 ({exc.reason}).") from exc
    return text


def normalize_bytes(data: bytes) -> str:
    """Decode and normalize bytes.

    Args:
        data: File content.

    Returns:
        Normalized text.

    Raises:
        PkmError: ``invalid_encoding`` for invalid UTF-8.
    """
    return normalize_text(decode(data))


def encode(text: str) -> bytes:
    """Bring text into write form: UTF-8 without BOM, LF, NFC, one trailing LF.

    Args:
        text: Text to write.

    Returns:
        The bytes to write.
    """
    return normalize_text(text).encode("utf-8")

# Main ************************************************************************
