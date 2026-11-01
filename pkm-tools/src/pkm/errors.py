"""Fehler mit maschinenlesbarem Status (Spezifikation 4.7, Statuswerte).

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

from typing import Any

# Variables *******************************************************************

# Classes *********************************************************************


class PkmError(Exception):
    """Fachlicher Fehler mit Statuswert aus 4.7 oder kurzem Fehlercode.

    Attributes:
        status: Maschinenlesbarer Status, z. B. ``conflict`` oder ``not_found``.
        message: Erklärung für Menschen (deutsch).
        data: Zusätzliche Angaben, die mit zurückgegeben werden.
    """

    def __init__(self, status: str, message: str, **data: Any) -> None:
        """Fehler anlegen.

        Args:
            status: Maschinenlesbarer Status.
            message: Erklärung für Menschen.
            **data: Zusätzliche Felder für die Rückgabe an den Aufrufer.
        """
        super().__init__(message)
        self.status = status
        self.message = message
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        """Fehler als Rückgabe-Objekt für MCP-Tools und CLI.

        Returns:
            Wörterbuch mit ``status``, ``message`` und den zusätzlichen Feldern.
        """
        return {"status": self.status, "message": self.message, **self.data}

# Functions *******************************************************************

# Main ************************************************************************
