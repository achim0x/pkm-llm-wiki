"""Gemeinsame Fixtures: temporärer Vault mit getrenntem Git-Verzeichnis.

Die Umgebung wird vollständig isoliert (eigenes HOME, eigene globale Git-Konfiguration),
damit Einstellungen des Rechners (z. B. Commit-Signierung) die Tests nicht beeinflussen.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    home = tmp_path / "home"
    home.mkdir()
    gitconfig = home / ".gitconfig"
    gitconfig.write_text("[user]\n\tname = Test User\n\temail = test@example.org\n", encoding="utf-8")
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
    for var in ("PKM_MAX_KB", "PKM_VAULT_NAME", "PKM_GIT_AUTHOR"):
        monkeypatch.delenv(var, raising=False)
    return {"root": root, "git_dir": app / "git", "cache_dir": app, "home": home, "gitconfig": gitconfig}


def git(env: dict[str, Path], *args: str) -> str:
    """Git im Testvault mit getrenntem Git-Verzeichnis aufrufen."""
    out = subprocess.run(
        ["git", f"--git-dir={env['git_dir']}", f"--work-tree={env['root']}", *args],
        check=True,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    return out.stdout
