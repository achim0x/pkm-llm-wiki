"""Fehler mit maschinenlesbarem Status (Spezifikation 4.7, Statuswerte)."""

from __future__ import annotations

from typing import Any


class PkmError(Exception):
    """Fachlicher Fehler. `status` ist ein Statuswert aus 4.7 oder ein kurzer Fehlercode."""

    def __init__(self, status: str, message: str, **data: Any) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "message": self.message, **self.data}
