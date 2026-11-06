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
from pathlib import Path

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
    assert set(servers) == {"pkm", "pkm-maintenance"}
    assert servers["pkm"]["command"].replace(".exe", "").endswith("pkm-mcp")
    assert servers["pkm"]["env"] == {"PKM_CONFIG": str(paths["config"])}  # not the default folder in the tests
    with zipfile.ZipFile(paths["skills"] / "pkm-access.zip") as zf:
        assert "pkm-access/SKILL.md" in zf.namelist()
    assert (paths["root"] / ".obsidian" / "app.json").is_file()
    assert "PKM Maintenance" in out


def test_setup_asks_before_changing_claude_desktop(paths):
    """Missing or different entries are shown; without permission nothing changes and the entries are printed."""
    paths["claude"].parent.mkdir(parents=True)
    old = {"mcpServers": {"other": {"command": "x"}, "pkm": {"command": "old"}}, "theme": "dark"}
    paths["claude"].write_text(json.dumps(old), encoding="utf-8")
    questions: list[str] = []

    def no(question):
        """Answer no to the question about Claude Desktop.

        Args:
            question: Question.

        Returns:
            The answer.
        """
        questions.append(question)
        return "n" if "Claude Desktop configuration" in question else ""

    res, out = _setup(paths, ask=no)
    claude = res["claude"]
    assert claude["status"] == "declined" and claude["missing"] == ["pkm-maintenance"]
    assert claude["differing"] == ["pkm"]
    assert sum("Claude Desktop configuration" in q for q in questions) == 1
    assert json.loads(paths["claude"].read_text(encoding="utf-8")) == old
    assert not list(paths["claude"].parent.glob("*.bak"))
    manual = json.loads(claude["manual"])["mcpServers"]
    assert set(manual) == {"pkm", "pkm-maintenance"} and "Enter the following by hand" in out
    assert "pkm-maintenance-mcp" in out


def test_setup_changes_claude_desktop_with_permission_and_is_repeatable(paths):
    """With permission: entries added or replaced, other servers kept, backup; a second run asks nothing."""
    paths["claude"].parent.mkdir(parents=True)
    paths["claude"].write_text(json.dumps({"mcpServers": {"other": {"command": "x"}, "pkm": {"command": "old"}},
                                           "theme": "dark"}), encoding="utf-8")
    res, _ = _setup(paths, ask=lambda q: "")
    assert res["claude"]["status"] == "changed"
    data = json.loads(paths["claude"].read_text(encoding="utf-8"))
    assert data["theme"] == "dark" and data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"]["pkm"]["command"] != "old" and "pkm-maintenance" in data["mcpServers"]
    assert len(list(paths["claude"].parent.glob("*.bak"))) == 1

    def no_claude_question(question):
        """Fail if the setup asks about Claude Desktop again.

        Args:
            question: Question.

        Returns:
            An empty answer (default).
        """
        assert "Claude Desktop" not in question
        return ""

    res, out = _setup(paths, ask=no_claude_question)
    assert res["claude"]["status"] == "unchanged" and "already entered" in out
    assert len(list(paths["claude"].parent.glob("*.bak"))) == 1


def test_setup_replaces_old_maintenance_entry(paths):
    """The old entry pkm-pflege (name up to 0.2.0) is replaced by pkm-maintenance; other servers stay."""
    paths["claude"].parent.mkdir(parents=True)
    old = {"mcpServers": {"pkm-pflege": {"command": "/x/pkm-pflege-mcp"}, "other": {"command": "x"}}}
    paths["claude"].write_text(json.dumps(old), encoding="utf-8")
    res, out = _setup(paths)
    servers = json.loads(paths["claude"].read_text(encoding="utf-8"))["mcpServers"]
    assert set(servers) == {"pkm", "pkm-maintenance", "other"} and res["claude"]["obsolete"] == ["pkm-pflege"]
    assert "old name of pkm-maintenance" in out
    res, _ = _setup(paths)
    assert res["claude"]["status"] == "unchanged" and not res["claude"]["obsolete"]


def test_setup_claude_md_current_after_init(paths):
    """A CLAUDE.md written by pkm init is current; nothing is asked or changed."""
    res, _ = _setup(paths)
    assert res["claude_md"]["status"] == "current"
    assert not (paths["root"] / "CLAUDE.md.new").exists()


def test_setup_replaces_outdated_claude_md_with_backup_and_commit(paths):
    """Outdated CLAUDE.md: after yes it is backed up outside the vault, replaced and committed."""
    _setup(paths)
    schema = paths["root"] / "CLAUDE.md"
    template = schema.read_text(encoding="utf-8")
    schema.write_text("# Old schema\nmy own rule\n", encoding="utf-8")
    git(paths["env"], "add", "CLAUDE.md")
    git(paths["env"], "commit", "-q", "-m", "old schema")
    res, out = _setup(paths)
    info = res["claude_md"]
    assert info["status"] == "replaced" and schema.read_text(encoding="utf-8") == template
    backup = Path(info["backup"])
    assert backup.read_text(encoding="utf-8") == "# Old schema\nmy own rule\n"
    assert paths["root"] not in backup.parents and backup.parent.name == "backups"
    assert info["commit"] and "updated to the current template" in git(paths["env"], "log", "-1", "--format=%s")
    assert "differs from the template" in out


def test_setup_keeps_claude_md_and_writes_new_on_no(paths):
    """Declined: CLAUDE.md stays, the template is written next to it as CLAUDE.md.new."""
    _setup(paths)
    schema = paths["root"] / "CLAUDE.md"
    template = schema.read_text(encoding="utf-8")
    schema.write_text("# Mine\n", encoding="utf-8")
    res, _ = _setup(paths, ask=lambda q: "n" if "Replace CLAUDE.md" in q else "")
    assert res["claude_md"]["status"] == "kept" and schema.read_text(encoding="utf-8") == "# Mine\n"
    assert (paths["root"] / "CLAUDE.md.new").read_text(encoding="utf-8") == template


def test_setup_replaces_claude_md_without_git(paths):
    """Without version control the file is replaced and backed up, without a commit."""
    _setup(paths, git_finder=lambda: None)
    schema = paths["root"] / "CLAUDE.md"
    schema.write_text("# Old\n", encoding="utf-8")
    res, _ = _setup(paths, git_finder=lambda: None)
    assert res["versioning"] is False and res["claude_md"]["status"] == "replaced"
    assert res["claude_md"]["commit"] is None and Path(res["claude_md"]["backup"]).is_file()


def test_setup_with_unreadable_claude_config(paths):
    """A broken Claude Desktop configuration is left alone; the entries are shown for entering by hand."""
    paths["claude"].parent.mkdir(parents=True)
    paths["claude"].write_text("{broken", encoding="utf-8")
    res, _ = _setup(paths)
    assert res["claude"]["status"] == "unreadable" and res["claude"]["manual"]
    assert paths["claude"].read_text(encoding="utf-8") == "{broken"


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
    answers = {"Vault folder": "must not be asked", "user name": "Ada", "e-mail": "ada@example.org"}
    res, _ = _setup(paths, ask=lambda q: next((v for k, v in answers.items() if k in q), ""))
    assert res["status"] == "ok" and res["init"]["commit"]
    assert git(paths["env"], "config", "--local", "user.name").strip() == "Ada"


def test_setup_cli(paths, capsys):
    """pkm setup --yes --json runs without questions."""
    code = cli.main(["setup", "--yes", "--json", "--vault", str(paths["root"]), "--claude-config", str(paths["claude"]),
                     "--skills-dir", str(paths["skills"])])
    assert code == 0 and json.loads(capsys.readouterr().out)["status"] == "ok"
    code = cli.main(["setup", "--yes", "--vault", "relative/path"])
    assert code == 1 and "absolute path" in capsys.readouterr().out

# Main ************************************************************************
