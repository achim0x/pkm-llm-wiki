"""Frontmatter schreiben (Spezifikation 4.1, Entscheidung 16 Nr. 16).

Serverfelder werden zeilengenau gesetzt; der Rest des Frontmatters bleibt unverändert.
`dump_meta` schreibt ein vollständiges Frontmatter (für create_document und update_frontmatter).
"""

from __future__ import annotations

import json
import re
from typing import Any

from .parse import load_yaml, split_frontmatter

PROTECTED = ("id", "version", "created", "updated")


def format_scalar(value: Any) -> str:
    """YAML-Darstellung eines Werts: einfach, wenn eindeutig, sonst JSON (gültiges YAML)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list | tuple | dict):
        return json.dumps(value, ensure_ascii=False)
    s = str(value)
    plain_ok = (
        s
        and s == s.strip()
        and "\n" not in s
        and not s.startswith(("[", "{", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`", "#", "-", "?", ":", ","))
        and ": " not in s
        and " #" not in s
        and not s.endswith(":")
    )
    if plain_ok:
        try:
            if load_yaml(f"k: {s}") == {"k": s}:
                return s
        except Exception:  # noqa: BLE001
            pass
    return json.dumps(s, ensure_ascii=False)


def dump_meta(meta: dict[str, Any]) -> str:
    """Frontmatter-Block inklusive Begrenzungszeilen, Reihenfolge wie im dict."""
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {format_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _field_re(key: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(key)}[ \t]*:")


def set_fields_linewise(text: str, fields: dict[str, Any]) -> str:
    """Felder im Frontmatter zeilengenau setzen; fehlt das Frontmatter, wird es angelegt.

    Erwartet normalisierten Text mit gültigem oder fehlendem Frontmatter.
    """
    has_fm, fm_text, inner, body, err = split_frontmatter(text)
    if err is not None:
        raise ValueError(err)
    if not has_fm:
        return dump_meta(fields) + text
    inner = list(inner)
    for key, value in fields.items():
        rendered = f"{key}: {format_scalar(value)}"
        rx = _field_re(key)
        for i, line in enumerate(inner):
            if rx.match(line):
                # Fortsetzungszeilen (eingerückt) des alten Werts entfernen
                j = i + 1
                while j < len(inner) and inner[j][:1] in (" ", "\t") and inner[j].strip():
                    j += 1
                inner[i : j] = [rendered]
                break
        else:
            inner.append(rendered)
    closing = fm_text.rstrip("\n").split("\n")[-1]
    return "\n".join(["---", *inner, closing]) + "\n" + body


def compose(frontmatter_text: str, body: str) -> str:
    return frontmatter_text + body
