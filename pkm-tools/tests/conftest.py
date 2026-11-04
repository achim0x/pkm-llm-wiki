"""Shared fixtures: temporary vault with a separate Git directory.

The environment is fully isolated (own HOME, own global Git configuration),
so that settings of the machine (e.g. commit signing) do not affect the tests.

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
    """Isolated environment: own HOME, own Git configuration, vault and app folders.

    Args:
        tmp_path: Temporary folder of pytest.
        monkeypatch: For setting environment variables.

    Returns:
        Paths ``root``, ``git_dir``, ``cache_dir``, ``home`` and ``gitconfig``.
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
    """Call Git in the test vault with a separate Git directory.

    Args:
        env: Isolated environment (``git_dir`` and ``root``).
        *args: Git subcommand and arguments.

    Returns:
        Standard output of Git.
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
    """Configuration with an initialized vault (``pkm init``).

    Args:
        isolated_env: Isolated environment (only for the setup).

    Returns:
        The configuration.
    """
    del isolated_env  # only needed for the setup

    c = Config.from_env()
    init_vault(c)
    return c


@pytest.fixture(name="svc")
def fixture_svc(cfg):
    """Service for the initialized vault.

    Args:
        cfg: Configuration.

    Returns:
        The service.
    """
    return Service(cfg)


def write(env_or_cfg, rel: str, text: str) -> Path:
    """Write a file in the vault (folders are created).

    Args:
        env_or_cfg: Isolated environment or configuration.
        rel: Relative path.
        text: Inhalt (UTF-8).

    Returns:
        Path of the written file.
    """
    root = env_or_cfg["root"] if isinstance(env_or_cfg, dict) else env_or_cfg.root
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


def commit_doc(cfg: Config, rel: str, text: str, doc_id: str, version: int) -> str:
    """Write a document and commit it with PKM lines.

    Args:
        cfg: Configuration.
        rel: Relative path.
        text: Content.
        doc_id: Document ID for ``PKM-Id``.
        version: Version number for ``PKM-Version``.
        source: ``PKM-Source``.
        title: Title in the subject.

    Returns:
        Hash of the commit.
    """
    write(cfg, rel, text)
    message = build_message("T", f"v{version}", "", doc_id, version, "user")
    return Git(cfg.git_dir, cfg.root).commit_paths([rel], message)

def remove_tree(path: Path) -> None:
    """Delete a folder, also read-only files (Git objects on Windows).

    Args:
        path: Folder to delete.
    """
    def make_writable(func, target, _exc):  # pylint: disable=unused-argument
        """Remove the write protection and retry the deletion.

        Args:
            func: Failed function (e.g. ``os.unlink``).
            target: Affected path.
            _exc: Exception (unused).
        """
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable)  # pylint: disable=unexpected-keyword-arg
    else:
        shutil.rmtree(path, onerror=make_writable)  # pylint: disable=deprecated-argument


# Main ************************************************************************
