"""Tests: ``pkm init`` creates Obsidian's ``.obsidian/types.json`` or adds to it.

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

import json

from pkm.config import Config
from pkm.doctor import doctor
from pkm.vaultinit import PROPERTY_TYPES, TYPES_FILE, ensure_property_types, init_vault

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


def _types(root):
    """Read the content of types.json.

    Args:
        root: Vault root.

    Returns:
        Section ``types``.
    """
    return json.loads((root / TYPES_FILE).read_text(encoding="utf-8"))["types"]


def _check(svc):
    """Get the doctor check of the property types.

    Args:
        svc: Service.

    Returns:
        Check result.
    """
    return next(c for c in doctor(svc)["checks"] if c["check"] == "obsidian_property_types")


def test_init_creates_types_json(svc, cfg):
    """After pkm init all schema fields are in types.json with their type; doctor is satisfied."""
    assert _types(cfg.root) == PROPERTY_TYPES
    assert _types(cfg.root)["date_markdown"] == "datetime"
    assert _types(cfg.root)["version"] == "number"
    assert _types(cfg.root)["related"] == "multitext"
    assert _check(svc)["ok"]


def test_init_merges_and_keeps_user_types(svc, cfg):
    """Existing entries stay, missing ones are added, deviations reported."""
    p = cfg.root / TYPES_FILE
    p.write_text(json.dumps({"types": {"rating": "number", "version": "text"}}), encoding="utf-8", newline="\n")
    assert not _check(svc)["ok"]
    res = init_vault(Config.from_env())
    types = _types(cfg.root)
    assert types["rating"] == "number" and types["version"] == "text"
    assert types["date_updated"] == "datetime"
    assert TYPES_FILE in res["updated_files"]
    assert any("version=text" in w for w in res["warnings"])
    assert "version=text" in _check(svc)["message"]


def test_init_idempotent_types(cfg):
    """A second run does not change types.json."""
    before = (cfg.root / TYPES_FILE).read_bytes()
    res = ensure_property_types(cfg.root)
    assert not res["added"] and not res["created"]
    assert (cfg.root / TYPES_FILE).read_bytes() == before


def test_unreadable_types_json_untouched(svc, cfg):
    """A broken types.json is not overwritten but reported."""
    p = cfg.root / TYPES_FILE
    p.write_text("{kaputt", encoding="utf-8", newline="\n")
    res = ensure_property_types(cfg.root)
    assert res["warning"] and p.read_text(encoding="utf-8") == "{kaputt"
    assert not _check(svc)["ok"]

# Main ************************************************************************
