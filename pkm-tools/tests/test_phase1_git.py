"""Git-Schicht und `pkm init` (Spezifikation 5.4, 5.5, 8, 12).

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

import json

import pytest

from pkm.cli import main
from pkm.config import Config
from pkm.errors import PkmError
from pkm.gitlayer import Git, build_message, parse_message
from pkm.vaultinit import init_vault

from .conftest import git

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="cfg")
def fixture_cfg(isolated_env):  # ohne init (überschreibt die gemeinsame Fixture)
    """Konfiguration ohne ``pkm init`` (überschreibt die gemeinsame Fixture).

    Args:
        isolated_env: Isolierte Umgebung (nur für die Vorbereitung).

    Returns:
        Die Konfiguration.
    """
    del isolated_env  # nur für die Vorbereitung benötigt
    return Config.from_env()


def test_init_creates_structure_without_dotgit(cfg, isolated_env):
    """pkm init legt Struktur, Dateien, Repo und Initial-Commit an, ohne .git im Vault."""
    res = init_vault(cfg)
    root = isolated_env["root"]
    for d in ("documents/_inbox", "documents/_attachments", "wiki/topics", "wiki/_lint", ".pkm"):
        assert (root / d).is_dir()
    for f in ("CLAUDE.md", "wiki/index.md", "wiki/log.md", "wiki/_status.md", ".pkm/state.json", ".gitignore"):
        assert (root / f).is_file()
    assert json.loads((root / ".pkm/state.json").read_text()) == {"version": 1, "documents": {}}
    assert not (root / ".git").exists()
    assert res["repo_created"] and res["commit"]
    assert ".pkm/mcp.log" in (root / ".gitignore").read_text()
    assert git(isolated_env, "log", "--format=%s").strip() == "pkm: init"


def test_init_idempotent(cfg, isolated_env):
    """Ein zweites pkm init ändert nichts."""
    init_vault(cfg)
    before = git(isolated_env, "rev-parse", "HEAD")
    res = init_vault(cfg)
    assert res["created_dirs"] == [] and res["created_files"] == [] and not res["repo_created"]
    assert res["commit"] is None
    assert git(isolated_env, "rev-parse", "HEAD") == before


def test_init_rejects_git_dir_in_vault(isolated_env, monkeypatch):
    """Ein Git-Verzeichnis im Vault wird abgelehnt."""
    monkeypatch.setenv("PKM_GIT_DIR", str(isolated_env["root"] / "git"))
    with pytest.raises(PkmError):
        init_vault(Config.from_env())


def test_init_rejects_cache_in_vault(isolated_env, monkeypatch):
    """Ein Suchindex im Vault wird abgelehnt."""
    monkeypatch.setenv("PKM_CACHE_DIR", str(isolated_env["root"] / ".pkm"))
    with pytest.raises(PkmError):
        init_vault(Config.from_env())


def test_init_without_identity(isolated_env):
    """Ohne Git-Identität gibt es eine Warnung statt eines Commits."""
    isolated_env["gitconfig"].write_text("")
    res = init_vault(Config.from_env())
    assert res["commit"] is None and res["warnings"]


@pytest.mark.usefixtures("isolated_env")
def test_cli_init(capsys):
    """pkm init über die CLI meldet ok."""
    assert main(["init"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_message_roundtrip():
    """Commit-Nachrichten lassen sich in Betreff, Notiz und PKM-Zeilen zerlegen."""
    msg = build_message("Zisterne – Sensor", "v3", "Sensor: Schwimmer", "d-20261031-2340-k7q2", 3, "chat")
    subject, note, tr = parse_message(msg)
    assert subject == "doc: Zisterne – Sensor v3"
    assert note == "Sensor: Schwimmer"
    assert tr == {"PKM-Id": "d-20261031-2340-k7q2", "PKM-Version": "3", "PKM-Source": "chat"}


def test_commit_only_given_file(cfg, isolated_env):
    """commit_paths committet nur die angegebene Datei mit PKM_GIT_AUTHOR."""
    init_vault(cfg)
    root = isolated_env["root"]
    g = Git(cfg.git_dir, cfg.root, cfg.git_author)
    (root / "documents/a.md").write_text("a\n")
    (root / "documents/b.md").write_text("b\n")
    msg = build_message("A", "v1", "", "d-20261031-2340-k7q2", 1, "chat")
    sha = g.commit_paths(["documents/a.md"], msg)
    assert g.commit_files(sha) == [("A", "documents/a.md")]
    assert g.is_dirty("documents/b.md") and not g.is_dirty("documents/a.md")
    assert git(isolated_env, "log", "-1", "--format=%an <%ae>").strip() == "pkm-mcp <pkm@localhost>"
    assert not (root / ".git").exists()


def test_commit_only_keeps_other_staged_changes(cfg, isolated_env):
    """Andere offene Änderungen bleiben beim Commit unberührt."""
    init_vault(cfg)
    root = isolated_env["root"]
    g = Git(cfg.git_dir, cfg.root)
    (root / "CLAUDE.md").write_text("geändert\n")
    (root / "documents/a.md").write_text("a\n")
    sha = g.commit_paths(["documents/a.md"], "x\n")
    assert [p for _, p in g.commit_files(sha)] == ["documents/a.md"]
    assert g.is_dirty("CLAUDE.md")


def test_log_for_id_after_move(cfg, isolated_env):
    """Der Verlauf nach ID ist auch nach dem Verschieben vollständig."""
    init_vault(cfg)
    root = isolated_env["root"]
    g = Git(cfg.git_dir, cfg.root)
    did = "d-20261031-2340-k7q2"
    (root / "documents/_inbox/x.md").write_text("v1\n")
    g.commit_paths(["documents/_inbox/x.md"], build_message("X", "v1", "neu", did, 1, "chat"))
    (root / "documents/haus").mkdir()
    (root / "documents/_inbox/x.md").rename(root / "documents/haus/y.md")
    (root / "documents/haus/y.md").write_text("v2\n")
    g.commit_paths(["documents/_inbox/x.md", "documents/haus/y.md"], build_message("X", "v2", "", did, 2, "user"))
    other = "d-20261031-2340-abcd"
    (root / "documents/z.md").write_text("z\n")
    g.commit_paths(["documents/z.md"], build_message("Z", "v1", "", other, 1, "chat"))
    log = g.log_for_id(did)
    assert [c.version for c in log] == [1, 2]
    assert [c.path for c in log] == ["documents/_inbox/x.md", "documents/haus/y.md"]
    assert log[0].source == "chat" and log[1].source == "user" and log[0].note == "neu"
    assert g.show_file(log[0].sha, log[0].path) == b"v1\n"


def test_log_for_id_rejects_bad_id(cfg):
    """Ungültige IDs werden nicht an git log weitergereicht."""
    g = Git(cfg.git_dir, cfg.root)
    with pytest.raises(PkmError):
        g.log_for_id("--all")


def test_commit_failure_unstages(cfg, isolated_env):
    """Ein fehlgeschlagener Commit hinterlässt keinen Index-Eintrag."""
    init_vault(cfg)
    root = isolated_env["root"]
    hook = cfg.git_dir / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    g = Git(cfg.git_dir, cfg.root)
    (root / "documents/a.md").write_text("a\n")
    with pytest.raises(PkmError):
        g.commit_paths(["documents/a.md"], "x\n")
    assert git(isolated_env, "diff", "--cached", "--name-only").strip() == ""


def test_problem_reports(cfg, isolated_env):
    """problem() nennt fehlendes Repo und fehlende Identität."""
    g = Git(cfg.git_dir, cfg.root)
    assert "pkm init" in g.problem()
    init_vault(cfg)
    assert g.problem() is None
    isolated_env["gitconfig"].write_text("")
    assert "Identität" in g.problem()


def test_cli_without_pkm_root_uses_cwd(cfg, isolated_env, monkeypatch, capsys):
    """Die CLI findet den Vault ohne PKM_ROOT vom aktuellen Ordner aus."""
    init_vault(cfg)
    monkeypatch.delenv("PKM_ROOT")
    monkeypatch.chdir(isolated_env["root"] / "documents")
    assert main(["pending"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"

# Main ************************************************************************
