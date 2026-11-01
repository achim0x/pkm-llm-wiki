"""Dokument-IDs `d-YYYYMMDD-HHMM-xxxx` (Spezifikation 4.1)."""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable
from datetime import datetime

ALPHABET = "".join(c for c in "0123456789abcdefghijklmnopqrstuvwxyz" if c not in "01lo")
ID_RE = re.compile(rf"^d-\d{{8}}-\d{{4}}-[{ALPHABET}]{{4}}$")


def is_valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(ID_RE.match(value))


def new_id(
    now: datetime,
    exists: Callable[[str], bool] = lambda _id: False,
    rand: Callable[[], str] | None = None,
    attempts: int = 50,
) -> str:
    rand = rand or (lambda: "".join(secrets.choice(ALPHABET) for _ in range(4)))
    stamp = now.strftime("d-%Y%m%d-%H%M")
    for _ in range(attempts):
        candidate = f"{stamp}-{rand()}"
        if not exists(candidate):
            return candidate
    raise RuntimeError("Keine freie ID gefunden.")
