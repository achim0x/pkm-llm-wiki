"""Frontmatter schreiben (Spezifikation 4.1, Entscheidung 16 Nr. 16).

Serverfelder werden zeilengenau gesetzt; der Rest des Frontmatters bleibt unverändert.
``dump_meta`` schreibt ein vollständiges Frontmatter (für create_document und update_frontmatter).

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

import json
import re
from typing import Any

import yaml

from .parse import load_yaml, split_frontmatter

# Variables *******************************************************************

PROTECTED = ("id", "version", "created", "updated")
PLAIN_FORBIDDEN_START = ("[", "{", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`", "#", "-", "?", ":", ",")

# Classes *********************************************************************

# Functions *******************************************************************


def _plain_ok(s: str) -> bool:
    """Prüfen, ob ein String ohne Anführungszeichen eindeutig als YAML-String gelesen wird.

    Args:
        s: Zu schreibender String.

    Returns:
        ``True``, wenn die einfache Schreibweise denselben String ergibt.
    """
    ok = bool(
        s
        and s == s.strip()
        and "\n" not in s
        and not s.startswith(PLAIN_FORBIDDEN_START)
        and ": " not in s
        and " #" not in s
        and not s.endswith(":")
    )
    if ok:
        try:
            ok = load_yaml(f"k: {s}") == {"k": s}
        except yaml.YAMLError:
            ok = False
    return ok


def format_scalar(value: Any) -> str:
    """YAML-Darstellung eines Werts: einfach, wenn eindeutig, sonst JSON (gültiges YAML).

    Args:
        value: Wert eines Frontmatter-Felds.

    Returns:
        Die Darstellung für die rechte Seite von ``key: …``.
    """
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif value is None:
        rendered = "null"
    elif isinstance(value, int | float):
        rendered = str(value)
    elif isinstance(value, list | tuple | dict):
        rendered = json.dumps(value, ensure_ascii=False)
    else:
        s = str(value)
        rendered = s if _plain_ok(s) else json.dumps(s, ensure_ascii=False)
    return rendered


def dump_meta(meta: dict[str, Any]) -> str:
    """Vollständiges Frontmatter schreiben.

    Args:
        meta: Felder in der gewünschten Reihenfolge.

    Returns:
        Frontmatter-Block inklusive Begrenzungszeilen und abschließendem LF.
    """
    lines = ["---", *(f"{key}: {format_scalar(value)}" for key, value in meta.items()), "---"]
    return "\n".join(lines) + "\n"


def _field_re(key: str) -> re.Pattern[str]:
    """Regex für die Zeile eines Felds auf oberster Ebene.

    Args:
        key: Feldname.

    Returns:
        Kompilierte Regex, die ``key:`` am Zeilenanfang erkennt.
    """
    return re.compile(rf"^{re.escape(key)}[ \t]*:")


def _render(key: str, value: Any, block_lists: bool) -> list[str]:
    """Zeilen für ein Feld erzeugen.

    Args:
        key: Feldname.
        value: Wert.
        block_lists: Listen als YAML-Blockliste (``- …``) statt einzeilig schreiben.

    Returns:
        Die Zeilen ohne LF.
    """
    if block_lists and isinstance(value, list | tuple):
        lines = [f"{key}:"] + [f"  - {format_scalar(v)}" for v in value] if value else [f"{key}: []"]
    else:
        lines = [f"{key}: {format_scalar(value)}"]
    return lines


def _value_end(inner: list[str], start: int) -> int:
    """Ende eines mehrzeiligen Feldwerts bestimmen.

    Args:
        inner: Frontmatter-Zeilen ohne Begrenzer.
        start: Index der Feldzeile.

    Returns:
        Index nach der letzten Fortsetzungszeile (eingerückt oder Blocklisten-Eintrag).
    """
    j = start + 1
    while j < len(inner) and inner[j].strip() and (
        inner[j][:1] in (" ", "\t") or inner[j].startswith("- ") or inner[j] == "-"
    ):
        j += 1
    return j


def _apply_fields(inner: list[str], fields: dict[str, Any], block_lists: bool) -> list[str]:
    """Felder in den Frontmatter-Zeilen ersetzen oder anhängen.

    Args:
        inner: Frontmatter-Zeilen ohne Begrenzer.
        fields: Zu setzende Felder.
        block_lists: Listen als YAML-Blockliste schreiben.

    Returns:
        Neue Zeilenliste; nicht betroffene Zeilen bleiben unverändert.
    """
    lines = list(inner)
    for key, value in fields.items():
        rendered = _render(key, value, block_lists)
        rx = _field_re(key)
        pos = next((i for i, line in enumerate(lines) if rx.match(line)), None)
        if pos is None:
            lines.extend(rendered)
        else:
            lines[pos:_value_end(lines, pos)] = rendered
    return lines


def set_fields_linewise(text: str, fields: dict[str, Any], block_lists: bool = False) -> str:
    """Felder im Frontmatter zeilengenau setzen; fehlt das Frontmatter, wird es angelegt.

    Args:
        text: Normalisierter Text mit gültigem oder ohne Frontmatter.
        fields: Zu setzende Felder.
        block_lists: Listen als YAML-Blockliste schreiben.

    Returns:
        Der neue Text; alle übrigen Zeilen bleiben unverändert.

    Raises:
        ValueError: Bei Frontmatter ohne Abschlusszeile.
    """
    has_fm, fm_text, inner, body, err = split_frontmatter(text)
    if err is not None:
        raise ValueError(err)
    if not has_fm:
        lines = ["---", *(ln for k, v in fields.items() for ln in _render(k, v, block_lists)), "---"]
        result = "\n".join(lines) + "\n" + text
    else:
        closing = fm_text.rstrip("\n").rsplit("\n", maxsplit=1)[-1]
        result = "\n".join(["---", *_apply_fields(inner, fields, block_lists), closing]) + "\n" + body
    return result

# Main ************************************************************************
