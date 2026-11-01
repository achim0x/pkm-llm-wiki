"""Tests für test_smoke.

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

import pkm

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


def test_version():
    """Das Paket hat eine Versionsnummer."""
    assert pkm.__version__


def test_isolated_env(isolated_env):
    """Die Test-Umgebung legt den Vault ohne .git an."""
    assert isolated_env["root"].is_dir()
    assert not (isolated_env["root"] / ".git").exists()

# Main ************************************************************************
