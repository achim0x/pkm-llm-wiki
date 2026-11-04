"""Tests: Cloud-Speicher – Konfliktkopien aller bekannten Dienste, Cloud-Ordner, Dateien „nur online“.

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

import os

import pytest

from pkm import cloudsync
from pkm.doctor import doctor
from pkm.lint import lint
from pkm.maint import Maintenance

from .conftest import write

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.mark.parametrize("name", [
    "notiz (conflicted copy 2026-11-01 120000).md",  # Nextcloud, ownCloud
    "Budget (John's conflicted copy 2026-04-15).md",  # Dropbox
    "notiz (Konflikt).md",
    "notiz (in Konflikt stehende Kopie von Achim 2026-11-01).md",  # Dropbox deutsch
    "notiz [Conflict].md",  # Google Drive
    "notiz (conflicted copy from MacBook on 2026-11-01).md",  # Google Drive (Backup and Sync)
    "Notiz.sync-conflict-20261104-120000-ABCDEFG.md",  # Syncthing
    "notiz [conflicted].md",  # pCloud
    "Notiz (Case Conflict).md",  # Dropbox
])
def test_conflict_names(name):
    """Bekannte Namensmuster werden erkannt."""
    assert cloudsync.is_conflict_copy(name)


@pytest.mark.parametrize("name", ["konfliktmanagement.md", "notiz.md", "conflict-resolution.md", "notiz-2.md"])
def test_no_false_positives(name):
    """Normale Namen sind keine Konfliktkopien."""
    assert not cloudsync.is_conflict_copy(name)


def test_sibling_conflicts_need_same_id():
    """OneDrive, iCloud, Google Drive: Kopie neben dem Original zählt nur bei gleicher ID."""
    ids = {
        "documents/notiz.md": "d-1",
        "documents/notiz-MacBook-Pro.md": "d-1",  # OneDrive
        "documents/notiz 2.md": "d-1",  # iCloud Drive
        "documents/notiz (1).md": "d-1",  # Google Drive, Finder
        "documents/Kopie von notiz.md": "d-1",  # Google Drive
        "documents/notiz-pumpe.md": "d-2",  # eigenes Dokument
        "documents/scratch-2.md": None,
    }
    assert cloudsync.sibling_conflicts(ids) == {"documents/notiz-MacBook-Pro.md", "documents/notiz 2.md",
                                                "documents/notiz (1).md", "documents/Kopie von notiz.md"}


def test_onedrive_copy_is_skipped_and_reported(svc, cfg):
    """Eine OneDrive-Kopie mit gleicher ID wird nicht verarbeitet, sondern gemeldet."""
    text = "---\nid: d-20261104-0900-abcd\nversion: 1\n---\nText\n"
    write(cfg, "documents/notiz.md", text)
    write(cfg, "documents/notiz-DESKTOP-ABC.md", text.replace("Text", "Text anders"))
    pend = Maintenance(svc).pending()
    assert {"problem": "conflict_copy", "path": "documents/notiz-DESKTOP-ABC.md"} in pend["problems"]
    assert not any(d["path"] == "documents/notiz-DESKTOP-ABC.md" for d in pend["new"])
    assert not [p for p in pend["problems"] if p["problem"] == "duplicate_id"]
    assert "conflict_copy" in [f["check"] for f in lint(svc)["findings"]
                               if f.get("path") == "documents/notiz-DESKTOP-ABC.md"]
    check = next(c for c in doctor(svc)["checks"] if c["check"] == "conflict_copies")
    assert not check["ok"] and "notiz-DESKTOP-ABC.md" in check["message"]


@pytest.mark.parametrize("parts, service", [
    (("OneDrive - Firma", "Vault"), "OneDrive"),
    (("Library", "CloudStorage", "GoogleDrive-a@b.de", "My Drive"), "Google Drive"),
    (("Dropbox", "Vault"), "Dropbox"),
    (("Library", "Mobile Documents", "com~apple~CloudDocs"), "iCloud Drive"),
    (("Nextcloud", "Vault"), "Nextcloud"),
])
def test_cloud_service(tmp_path, parts, service):
    """Cloud-Ordner werden am Namen erkannt."""
    assert cloudsync.cloud_service(tmp_path.joinpath(*parts)) == service


def test_cloud_service_markers(tmp_path):
    """Ordner mit Syncthing-Markierung gelten als Cloud-Ordner; normale Ordner nicht."""
    (tmp_path / "sync" / ".stfolder").mkdir(parents=True)
    assert cloudsync.cloud_service(tmp_path / "sync" / "pkm") == "Syncthing"
    assert cloudsync.cloud_service(tmp_path / "local" / "pkm") is None


def test_doctor_reports_cloud_dirs_and_online_only(svc, cfg, monkeypatch):
    """doctor: Git-Verzeichnis im Cloud-Ordner ist ein Fehler; Platzhalter-Dateien eine Warnung."""
    checks = {c["check"]: c for c in doctor(svc)["checks"]}
    assert checks["git_dir_cloud"]["ok"] and checks["vault_online_only"]["ok"]
    assert "Nextcloud" in checks["vault_cloud"]["message"]
    monkeypatch.setattr(cloudsync, "is_online_only", lambda p: p.name == "fern.md")
    write(cfg, "documents/fern.md", "x")
    check = next(c for c in doctor(svc)["checks"] if c["check"] == "vault_online_only")
    assert not check["ok"] and check["severity"] == "warning" and "documents/fern.md" in check["message"]
    assert not cloudsync.is_online_only(cfg.root / "fehlt.md")
    assert os.path.exists(cfg.root / "documents/fern.md")

# Main ************************************************************************
