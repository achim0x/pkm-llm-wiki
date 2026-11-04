"""``pkm setup``: guided installation with and without Git (specification 15.1).

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
import zipfile

import pytest

from pkm import cli
from pkm.config import read_config_file
from pkm.setupwiz import NO_GIT_HINT, Setup, SetupOptions

from .conftest import git

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="paths")
def fixture_paths(isolated_env, tmp_path, monkeypatch):
    """Paths for a setup run; PKM_ROOT is not set (setup asks for it).

    Args:
        isolated_env: Isolated environment.
        tmp_path: Temporary folder of pytest.
        monkeypatch: pytest fixture.

    Returns:
        Vault, configuration file, Claude Desktop configuration and skills folder.
    """
    monkeypatch.delenv("PKM_ROOT")
    return {"root": isolated_env["root"], "config": tmp_path / "app" / "config.toml",
            "claude": tmp_path / "claude" / "claude_desktop_config.json", "skills": tmp_path / "skills",
            "env": isolated_env}


def _setup(paths, git_finder=None, ask=None, **kw):
    """Run the setup without questions.

    Args:
        paths: Paths of the fixture ``paths``.
        git_finder: Replacement for the Git search or ``None`` for the real one.
        ask: Function for questions or ``None`` (then ``yes``).
        **kw: Further options.

    Returns:
        Result of ``Setup.run`` and the output.
    """
    out: list[str] = []
    opts = SetupOptions(vault=str(paths["root"]), yes=ask is None, claude_config=str(paths["claude"]),
                        skills_dir=str(paths["skills"]), **kw)
    extra = {"git_finder": git_finder} if git_finder else {}
    res = Setup(opts, ask=ask or input, say=out.append, **extra).run()
    return res, "\n".join(out)


def test_setup_with_git(paths):
    """With Git: config.toml, vault with initial commit, Claude Desktop entries, skill ZIPs, doctor ok."""
    res, out = _setup(paths)
    assert res["status"] == "ok", out
    assert res["versioning"] is True and res["init"]["commit"]
    values = read_config_file(paths["config"])
    assert values["PKM_ROOT"] == str(paths["root"]) and values["PKM_VERSIONING"] == "true" and values["PKM_GIT"]
    assert git(paths["env"], "log", "-1", "--format=%s").strip() == "pkm: init"
    assert git(paths["env"], "config", "commit.gpgsign").strip() == "false"
    servers = json.loads(paths["claude"].read_text(encoding="utf-8"))["mcpServers"]
    assert set(servers) == {"pkm", "pkm-pflege"} and servers["pkm"]["command"].replace(".exe", "").endswith("pkm-mcp")
    assert servers["pkm"]["env"] == {"PKM_CONFIG": str(paths["config"])}  # not the default folder in the tests
    with zipfile.ZipFile(paths["skills"] / "pkm-access.zip") as zf:
        assert "pkm-access/SKILL.md" in zf.namelist()
    assert (paths["root"] / ".obsidian" / "app.json").is_file()
    assert "PKM-Pflege" in out


def test_setup_is_repeatable_and_keeps_other_servers(paths):
    """A second run changes nothing; other servers stay, differing entries are only replaced after confirmation."""
    paths["claude"].parent.mkdir(parents=True)
    paths["claude"].write_text(json.dumps({"mcpServers": {"other": {"command": "x"}, "pkm": {"command": "old"}},
                                           "theme": "dark"}), encoding="utf-8")
    res, _ = _setup(paths, ask=lambda q: "n" if "Replace" in q else "")
    assert res["claude"]["added"] == ["pkm-pflege"] and res["claude"]["kept"] == ["pkm"]
    data = json.loads(paths["claude"].read_text(encoding="utf-8"))
    assert data["theme"] == "dark" and data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"]["pkm"] == {"command": "old"}
    assert len(list(paths["claude"].parent.glob("*.bak"))) == 1
    res, _ = _setup(paths)
    assert res["claude"]["replaced"] == ["pkm"]
    res, _ = _setup(paths)
    assert res["claude"] == {"path": str(paths["claude"]), "added": [], "replaced": [], "kept": []}
    assert len(list(paths["claude"].parent.glob("*.bak"))) == 2


def test_setup_without_git_then_with_git(paths):
    """Without Git: hint, no Git directory, PKM works; after installing Git a new run turns version control on."""
    res, out = _setup(paths, git_finder=lambda: None)
    assert res["status"] == "ok" and res["versioning"] is False
    assert NO_GIT_HINT in res["warnings"] and "git-scm.com" in out
    assert read_config_file(paths["config"])["PKM_VERSIONING"] == "false"
    assert not paths["env"]["git_dir"].exists()
    res, _ = _setup(paths)
    assert res["versioning"] is True and res["init"]["repo_created"] is True and res["init"]["commit"]


def test_setup_asks_and_sets_git_identity(paths, monkeypatch, tmp_path):
    """Without a global Git identity the setup asks for it and sets it for the PKM repo only."""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    answers = {"Vault folder": str(paths["root"]), "user name": "Ada", "e-mail": "ada@example.org"}
    res, _ = _setup(paths, ask=lambda q: next((v for k, v in answers.items() if k in q), ""))
    assert res["status"] == "ok" and res["init"]["commit"]
    assert git(paths["env"], "config", "--local", "user.name").strip() == "Ada"


def test_setup_cli(paths, capsys):
    """pkm setup --yes --json runs without questions."""
    code = cli.main(["setup", "--yes", "--json", "--vault", str(paths["root"]), "--claude-config", str(paths["claude"]),
                     "--skills-dir", str(paths["skills"])])
    assert code == 0 and json.loads(capsys.readouterr().out)["status"] == "ok"
    code = cli.main(["setup", "--yes", "--vault", "relative/path", "--no-claude"])
    assert code == 1 and "absolute path" in capsys.readouterr().out

# Main ************************************************************************
