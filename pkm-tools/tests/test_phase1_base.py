"""Konfiguration, Pfade, IDs, Frontmatter (Spezifikation 4.1, 5.5, 7.1, 7.5).

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

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from pkm import paths
from pkm.config import Config
from pkm.errors import PkmError
from pkm.frontmatter import dump_meta, format_scalar, set_fields_linewise
from pkm.ids import ALPHABET, ID_RE, is_valid_id, new_id
from pkm.parse import parse

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


# Konfiguration ***************************************************************
def test_config_requires_root():
    """Ohne PKM_ROOT gibt es einen Konfigurationsfehler."""
    with pytest.raises(PkmError):
        Config.from_env({})


def test_config_defaults(tmp_path):
    """Standardwerte für Größe, Autor, Index- und Protokollpfad."""
    cfg = Config.from_env({"PKM_ROOT": str(tmp_path), "HOME": str(tmp_path / "h")})
    assert cfg.max_kb == 200
    assert cfg.git_author.startswith("pkm-mcp")
    assert cfg.index_path.name == "index.db"
    assert cfg.log_path == tmp_path.resolve() / ".pkm" / "mcp.log"


def test_cache_dir_inside_vault_rejected(tmp_path):
    """PKM_CACHE_DIR im Vault wird als Problem gemeldet."""
    cfg = Config.from_env({"PKM_ROOT": str(tmp_path), "PKM_CACHE_DIR": str(tmp_path / ".pkm")})
    assert cfg.cache_dir_problem()
    ok = Config.from_env({"PKM_ROOT": str(tmp_path / "v"), "PKM_CACHE_DIR": str(tmp_path / "c")})
    assert ok.cache_dir_problem() is None


# Pfade ***********************************************************************
def test_safe_resolve_ok(tmp_path):
    """Gültige relative Pfade werden im Vault aufgelöst."""
    assert paths.safe_resolve(tmp_path, "documents/a.md") == tmp_path / "documents" / "a.md"


@pytest.mark.parametrize("bad", ["../x.md", "/etc/passwd", "documents/../../x", "C:/x", ""])
def test_safe_resolve_rejects(tmp_path, bad):
    """Ausbrechende, absolute und leere Pfade werden abgelehnt."""
    with pytest.raises(PkmError):
        paths.safe_resolve(tmp_path, bad)


def test_symlink_outside_rejected(tmp_path):
    """Symlinks, die aus dem Vault zeigen, werden abgelehnt."""
    root = tmp_path / "root"
    (root / "documents").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        os.symlink(outside, root / "documents" / "link")
    except OSError:  # Windows ohne Entwicklermodus erlaubt keine Symlinks
        pytest.skip("Symlinks sind hier nicht erlaubt")
    with pytest.raises(PkmError):
        paths.safe_resolve(root, "documents/link/x.md")


def test_nfd_input_becomes_nfc(tmp_path):
    """NFD-Eingaben werden in NFC umgewandelt."""
    p = paths.safe_resolve(tmp_path, "documents/U\u0308ber.md")
    assert p.name == "Über.md"


@pytest.mark.parametrize(
    "title, slug",
    [("Zisterne – Überlaufsensor", "zisterne-ueberlaufsensor"), ("Größe: 5 m²", "groesse-5-m2"),
     ("CON", "con-doc"), ("???", "dokument"), ("a/b\\c:d*e", "a-b-c-d-e")],
)
def test_slugify(title, slug):
    """Slugs sind klein, mit Bindestrichen und plattformfest."""
    assert paths.slugify(title) == slug


def test_slug_length():
    """Slugs werden gekürzt."""
    assert len(paths.slugify("x" * 500)) <= 80


@pytest.mark.parametrize(
    "name, ok",
    [("a.md", True), ("con.md", False), ("a?.md", False), ("a.", False), ("a ", False), ("x" * 121, False)],
)
def test_platform_safe(name, ok):
    """Plattformfeste Dateinamen nach 5.5."""
    assert paths.is_platform_safe_name(name) is ok


def test_conflict_copy():
    """Nextcloud-Konfliktkopien werden am Namen erkannt."""
    assert paths.is_conflict_copy("notiz (conflicted copy 2026-11-01 120000).md")
    assert paths.is_conflict_copy("notiz (Konflikt).md")
    assert not paths.is_conflict_copy("notiz.md")


def test_case_collisions():
    """Namen, die sich nur in Groß-/Kleinschreibung unterscheiden, werden gruppiert."""
    assert paths.case_collisions(["a/B.md", "a/b.md", "c.md"]) == [["a/B.md", "a/b.md"]]


# IDs *************************************************************************
def test_id_format():
    """IDs haben das Format d-YYYYMMDD-HHMM-xxxx ohne 0, 1, l, o."""
    now = datetime(2026, 10, 31, 23, 40, tzinfo=ZoneInfo("Europe/Berlin"))
    i = new_id(now)
    assert ID_RE.match(i) and i.startswith("d-20261031-2340-")
    assert not set("01lo") & set(ALPHABET)


def test_id_collision_retries():
    """Bei einer Kollision wird eine neue ID gezogen."""
    now = datetime(2026, 1, 1, 0, 0)
    seq = iter(["aaaa", "bbbb"])
    i = new_id(now, exists=lambda x: x.endswith("aaaa"), rand=lambda: next(seq))
    assert i.endswith("bbbb")


def test_is_valid_id():
    """Gültige und ungültige IDs werden unterschieden."""
    assert is_valid_id("d-20261031-2340-k7q2")
    assert not is_valid_id("d-20261031-2340-k7q0")
    assert not is_valid_id("x; rm -rf")


# Frontmatter *****************************************************************
def test_linewise_keeps_comments_and_order():
    """Serverfelder werden zeilengenau gesetzt, Kommentare bleiben."""
    text = "---\ntitle: T   # Kommentar\nversion: 2\nrelated: [\"[[x]]\"]  # optional\n---\nBody\n"
    out = set_fields_linewise(text, {"version": 3, "updated": "2026-11-01T10:00:00+01:00"})
    assert out == (
        "---\ntitle: T   # Kommentar\nversion: 3\nrelated: [\"[[x]]\"]  # optional\n"
        "updated: 2026-11-01T10:00:00+01:00\n---\nBody\n"
    )


def test_linewise_creates_frontmatter_rest_unchanged():
    """Fehlendes Frontmatter wird angelegt, der Rest bleibt gleich."""
    body = "# Titel\n\nText  mit  Leerzeichen\n"
    out = set_fields_linewise(body, {"id": "d-20261031-2340-k7q2", "version": 1})
    assert out == "---\nid: d-20261031-2340-k7q2\nversion: 1\n---\n" + body


def test_dump_meta_roundtrip():
    """Geschriebenes Frontmatter wird unverändert zurückgelesen."""
    meta = {"id": "d-20261031-2340-k7q2", "version": 1, "title": "Zisterne – Überlaufsensor",
            "context": "Chat: Füllstand", "tags": ["zisterne", "home-assistant"],
            "related": ["[[documents/haus/zisterne]]"], "created": "2026-10-31T23:40:12+01:00",
            "n": "123", "flag": "yes"}
    p = parse(dump_meta(meta))
    assert p.meta == meta


@pytest.mark.parametrize("v, out", [(3, "3"), ("abc", "abc"), ("a: b", '"a: b"'), ("true", '"true"'),
                                    (["a"], '["a"]'), ("- x", '"- x"')])
def test_format_scalar(v, out):
    """Werte werden einfach oder als JSON geschrieben."""
    assert format_scalar(v) == out


def test_config_finds_vault_from_cwd(tmp_path):
    """Ohne PKM_ROOT wird der Vault aufwärts gesucht."""
    (tmp_path / "v" / ".pkm").mkdir(parents=True)
    (tmp_path / "v" / ".pkm" / "state.json").write_text("{}")
    (tmp_path / "v" / "documents" / "x").mkdir(parents=True)
    cfg = Config.from_env({"HOME": str(tmp_path)}, search_from=tmp_path / "v" / "documents" / "x")
    assert cfg.root == (tmp_path / "v").resolve()
    with pytest.raises(PkmError):
        Config.from_env({"HOME": str(tmp_path)}, search_from=tmp_path)

# Main ************************************************************************
