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


@pytest.fixture
def cfg(isolated_env):
    from pkm.config import Config
    from pkm.vaultinit import init_vault

    c = Config.from_env()
    init_vault(c)
    return c


@pytest.fixture
def svc(cfg):
    from pkm.service import Service

    return Service(cfg)


def write(env_or_cfg, rel: str, text: str) -> Path:
    root = env_or_cfg["root"] if isinstance(env_or_cfg, dict) else env_or_cfg.root
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


def commit_doc(cfg, rel: str, text: str, doc_id: str, version: int, source: str = "user", title: str = "T") -> str:
    from pkm.gitlayer import Git, build_message

    write(cfg, rel, text)
    return Git(cfg.git_dir, cfg.root).commit_paths([rel], build_message(title, f"v{version}", "", doc_id, version, source))
