"""Errors with a machine-readable status (specification 4.7, status values).

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

from typing import Any

# Variables *******************************************************************

# Classes *********************************************************************


class PkmError(Exception):
    """Domain error with a status value from 4.7 or a short error code.

    Attributes:
        status: Machine-readable status, e.g. ``conflict`` or ``not_found``.
        message: Explanation for humans.
        data: Additional details returned along with the error.
    """

    def __init__(self, status: str, message: str, **data: Any) -> None:
        """Create the error.

        Args:
            status: Machine-readable status.
            message: Explanation for humans.
            **data: Additional fields returned to the caller.
        """
        super().__init__(message)
        self.status = status
        self.message = message
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        """Error as a result object for MCP tools and the CLI.

        Returns:
            Dictionary with ``status``, ``message`` and the additional fields.
        """
        return {"status": self.status, "message": self.message, **self.data}

# Functions *******************************************************************

# Main ************************************************************************
