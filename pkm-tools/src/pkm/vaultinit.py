"""`pkm init`: Struktur anlegen und Git-Verzeichnis außerhalb des Vaults initialisieren."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from .config import Config
from .errors import PkmError
from .gitlayer import Git

DIRS = [
    "documents/_inbox",
    "documents/_attachments",
    "wiki/topics",
    "wiki/entities",
    "wiki/summaries",
    "wiki/syntheses",
    "wiki/_lint",
    ".pkm",
]

STATE_FORMAT = 1


def _template(name: str) -> str:
    return resources.files("pkm").joinpath("templates", name).read_text(encoding="utf-8")


def initial_files() -> dict[str, str]:
    return {
        "CLAUDE.md": _template("CLAUDE.md"),
        ".gitignore": _template("gitignore"),
        "wiki/index.md": "# Wiki-Index\n\n_Noch keine Seiten._\n",
        "wiki/log.md": "# Pflege-Log\n",
        "wiki/_status.md": "# Status\n\n## Noch nicht verarbeitet (0)\n",
        ".pkm/state.json": json.dumps({"version": STATE_FORMAT, "documents": {}}, indent=2) + "\n",
    }


def init_vault(cfg: Config) -> dict:
    """Idempotent. Gibt zurück, was angelegt wurde."""
    for problem in (cfg.git_dir_problem(), cfg.cache_dir_problem()):
        if problem:
            raise PkmError("config_error", problem)
    if (cfg.root / ".git").exists():
        raise PkmError("config_error", "Im Vault liegt ein `.git`. Git muss außerhalb liegen (5.5).")
    cfg.root.mkdir(parents=True, exist_ok=True)
    created_dirs: list[str] = []
    for d in DIRS:
        p = cfg.root / d
        if not p.is_dir():
            p.mkdir(parents=True)
            created_dirs.append(d)
    created_files: list[str] = []
    for rel, content in initial_files().items():
        p = cfg.root / rel
        if not p.exists():
            p.write_bytes(content.encode("utf-8"))
            created_files.append(rel)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)

    git = Git(cfg.git_dir, cfg.root)
    repo_created = git.init()
    commit = None
    warnings: list[str] = []
    if not git.has_head():
        if git.config_get("user.name") and git.config_get("user.email"):
            paths = [rel for rel in initial_files() if (cfg.root / rel).exists()]
            commit = git.commit_paths(paths, "pkm: init\n")
        else:
            warnings.append("Git-Identität fehlt (user.name/user.email); Initial-Commit übersprungen.")
    return {
        "status": "ok",
        "root": str(cfg.root),
        "git_dir": str(cfg.git_dir),
        "created_dirs": created_dirs,
        "created_files": created_files,
        "repo_created": repo_created,
        "commit": commit,
        "warnings": warnings,
    }


def vault_has_dotgit(root: Path) -> bool:
    return (root / ".git").exists()
