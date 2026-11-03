"""Gemeinsame Fixtures: temporärer Vault mit getrenntem Git-Verzeichnis.

Die Umgebung wird vollständig isoliert (eigenes HOME, eigene globale Git-Konfiguration),
damit Einstellungen des Rechners (z. B. Commit-Signierung) die Tests nicht beeinflussen.

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
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from pkm.config import Config
from pkm.gitlayer import Git, build_message
from pkm.service import Service
from pkm.vaultinit import init_vault

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="isolated_env")
def fixture_isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Isolierte Umgebung: eigenes HOME, eigene Git-Konfiguration, Vault- und App-Ordner.

    Args:
        tmp_path: Temporärer Ordner von pytest.
        monkeypatch: Zum Setzen der Umgebungsvariablen.

    Returns:
        Pfade ``root``, ``git_dir``, ``cache_dir``, ``home`` und ``gitconfig``.
    """
    home = tmp_path / "home"
    home.mkdir()
    gitconfig = home / ".gitconfig"
    gitconfig.write_text("[user]\n\tname = Test User\n\temail = test@example.org\n", encoding="utf-8", newline="\n")
    root = tmp_path / "Nextcloud" / "Vault"
    root.mkdir(parents=True)
    app = tmp_path / "app"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("PKM_ROOT", str(root))
    monkeypatch.setenv("PKM_GIT_DIR", str(app / "git"))
    monkeypatch.setenv("PKM_CACHE_DIR", str(app))
    monkeypatch.setenv("PKM_TZ", "Europe/Berlin")
    for var in ("PKM_MAX_KB", "PKM_VAULT_NAME", "PKM_GIT_AUTHOR", "PKM_INLINE_MAX_KB", "PKM_SVG_MAX_KB",
                "PKM_IMAGE_MAX_MB", "PKM_IMAGE_PARAM_MAX_KB", "PKM_IMPORT_DIR", "PKM_SVG_RASTER"):
        monkeypatch.delenv(var, raising=False)
    return {"root": root, "git_dir": app / "git", "cache_dir": app, "home": home, "gitconfig": gitconfig}


def git(env: dict[str, Path], *args: str) -> str:
    """Git im Testvault mit getrenntem Git-Verzeichnis aufrufen.

    Args:
        env: Isolierte Umgebung (``git_dir`` und ``root``).
        *args: Git-Unterbefehl und Argumente.

    Returns:
        Standardausgabe von Git.
    """
    out = subprocess.run(
        ["git", f"--git-dir={env['git_dir']}", f"--work-tree={env['root']}", *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
        env=os.environ.copy(),
    )
    return out.stdout


@pytest.fixture(name="cfg")
def fixture_cfg(isolated_env):
    """Konfiguration mit initialisiertem Vault (``pkm init``).

    Args:
        isolated_env: Isolierte Umgebung (nur für die Vorbereitung).

    Returns:
        Die Konfiguration.
    """
    del isolated_env  # nur für die Vorbereitung benötigt

    c = Config.from_env()
    init_vault(c)
    return c


@pytest.fixture(name="svc")
def fixture_svc(cfg):
    """Dienst für den initialisierten Vault.

    Args:
        cfg: Konfiguration.

    Returns:
        Der Dienst.
    """
    return Service(cfg)


def write(env_or_cfg, rel: str, text: str) -> Path:
    """Datei im Vault schreiben (Ordner werden angelegt).

    Args:
        env_or_cfg: Isolierte Umgebung oder Konfiguration.
        rel: Relativer Pfad.
        text: Inhalt (UTF-8).

    Returns:
        Pfad der geschriebenen Datei.
    """
    root = env_or_cfg["root"] if isinstance(env_or_cfg, dict) else env_or_cfg.root
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


def commit_doc(cfg: Config, rel: str, text: str, doc_id: str, version: int) -> str:
    """Dokument schreiben und mit PKM-Zeilen committen.

    Args:
        cfg: Konfiguration.
        rel: Relativer Pfad.
        text: Inhalt.
        doc_id: Dokument-ID für ``PKM-Id``.
        version: Versionsnummer für ``PKM-Version``.
        source: ``PKM-Source``.
        title: Titel im Betreff.

    Returns:
        Hash des Commits.
    """
    write(cfg, rel, text)
    message = build_message("T", f"v{version}", "", doc_id, version, "user")
    return Git(cfg.git_dir, cfg.root).commit_paths([rel], message)

def remove_tree(path: Path) -> None:
    """Ordner löschen, auch schreibgeschützte Dateien (Git-Objekte unter Windows).

    Args:
        path: Zu löschender Ordner.
    """
    def make_writable(func, target, _exc):  # pylint: disable=unused-argument
        """Schreibschutz aufheben und den Löschversuch wiederholen.

        Args:
            func: Fehlgeschlagene Funktion (z. B. ``os.unlink``).
            target: Betroffener Pfad.
            _exc: Ausnahme (ungenutzt).
        """
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable)  # pylint: disable=unexpected-keyword-arg
    else:
        shutil.rmtree(path, onerror=make_writable)  # pylint: disable=deprecated-argument


# Main ************************************************************************
