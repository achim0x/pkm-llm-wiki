"""``pkm setup``: show an existing configuration and take it over (specification 15.1).

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

from pkm.config import read_config_file
from pkm.setupwiz import Setup, SetupOptions

# Variables *******************************************************************

QUESTION = "Take over this configuration?"

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="paths")
def fixture_paths(isolated_env, tmp_path, monkeypatch):
    """Paths for a setup run without any settings in the environment.

    Args:
        isolated_env: Isolated environment.
        tmp_path: Temporary folder of pytest.
        monkeypatch: pytest fixture.

    Returns:
        Vault, configuration file, Claude Desktop configuration, skills folder and a folder for
        an existing Git directory.
    """
    for var in ("PKM_ROOT", "PKM_GIT_DIR", "PKM_CACHE_DIR", "PKM_TZ"):
        monkeypatch.delenv(var)
    return {"root": isolated_env["root"], "config": tmp_path / "app" / "config.toml",
            "claude": tmp_path / "claude" / "claude_desktop_config.json", "skills": tmp_path / "skills",
            "old_git": tmp_path / "old-git", "home": isolated_env["home"]}


def _run(paths, answers=None, **kw):
    """Run the setup; questions are answered from ``answers`` (otherwise ``yes``).

    Args:
        paths: Paths of the fixture ``paths``.
        answers: Part of the question → answer, or ``None`` for ``yes``.
        **kw: Further options.

    Returns:
        Result of ``Setup.run``, the questions asked and the output.
    """
    asked: list[str] = []
    out: list[str] = []

    def ask(question):
        """Answer a question from ``answers``.

        Args:
            question: Question.

        Returns:
            The answer.
        """
        asked.append(question)
        return next((v for k, v in (answers or {}).items() if k in question), "")

    opts = SetupOptions(yes=answers is None, claude_config=str(paths["claude"]), skills_dir=str(paths["skills"]),
                        **kw)
    res = Setup(opts, ask=ask, say=out.append).run()
    return res, asked, "\n".join(out)


def _old_claude(paths):
    """Write Claude Desktop entries of an installation from before ``pkm setup`` (settings in ``env``).

    Args:
        paths: Paths of the fixture ``paths``.
    """
    env = {"PKM_ROOT": str(paths["root"]), "PKM_VAULT_NAME": "MyVault", "PKM_GIT_DIR": str(paths["old_git"])}
    paths["claude"].parent.mkdir(parents=True)
    data = {"mcpServers": {"pkm": {"command": "pkm-mcp", "env": env},
                           "pkm-maintenance": {"command": "pkm-maintenance-mcp", "env": env},
                           "other": {"command": "x"}}}
    paths["claude"].write_text(json.dumps(data), encoding="utf-8")


def test_no_existing_configuration_no_question(paths):
    """Without any existing settings the setup does not ask about taking over."""
    res, asked, out = _run(paths, {}, vault=str(paths["root"]))
    assert res["status"] == "ok" and not any(QUESTION in q for q in asked)
    assert "Existing configuration found" not in out


def test_takes_over_settings_from_old_claude_desktop_entries(paths):
    """Settings in the env blocks of old Claude Desktop entries are shown and taken over."""
    _old_claude(paths)
    res, asked, out = _run(paths, {"Vault folder": ""})
    assert sum(QUESTION in q for q in asked) == 1
    assert f"PKM_GIT_DIR = {paths['old_git']}   [Claude Desktop (pkm)]" in out
    values = read_config_file(paths["config"])
    assert values["PKM_GIT_DIR"] == str(paths["old_git"]) and values["PKM_VAULT_NAME"] == "MyVault"
    assert values["PKM_ROOT"] == str(paths["root"])  # default of the vault question
    assert res["root"] == str(paths["root"]) and (paths["old_git"] / "HEAD").is_file()
    servers = json.loads(paths["claude"].read_text(encoding="utf-8"))["mcpServers"]
    assert "PKM_GIT_DIR" not in json.dumps(servers["pkm"]) and servers["other"] == {"command": "x"}


def test_takes_over_config_toml_and_environment_wins(paths, monkeypatch):
    """Keys of config.toml are kept; a value from the environment overrides the file and is marked."""
    paths["config"].parent.mkdir(parents=True, exist_ok=True)
    paths["config"].write_text(f'PKM_ROOT = "{paths["root"].as_posix()}"\nPKM_MAX_KB = "300"\n'
                               'PKM_TZ = "Europe/Vienna"\n', encoding="utf-8")
    monkeypatch.setenv("PKM_TZ", "UTC")
    res, _, out = _run(paths)
    values = read_config_file(paths["config"])
    assert values["PKM_MAX_KB"] == "300" and values["PKM_TZ"] == "UTC"
    assert "PKM_TZ = UTC   [environment]" in out and "Europe/Vienna" in out and "not used" in out
    assert res["root"] == str(paths["root"])


def test_declined_starts_new_configuration_with_backup(paths):
    """Declined: the old file is backed up, its keys are not taken over and the vault is asked again."""
    paths["config"].parent.mkdir(parents=True, exist_ok=True)
    paths["config"].write_text(f'PKM_ROOT = "{paths["root"].as_posix()}"\nPKM_MAX_KB = "300"\n',
                               encoding="utf-8")
    res, asked, out = _run(paths, {QUESTION: "n", "Vault folder": str(paths["root"])})
    assert res["root"] == str(paths["root"]) and any("Vault folder" in q and "[" not in q for q in asked)
    assert "PKM_MAX_KB" not in read_config_file(paths["config"])
    backups = list(paths["config"].parent.glob("config.toml.*.bak"))
    assert len(backups) == 1 and "PKM_MAX_KB" in backups[0].read_text(encoding="utf-8")
    assert "new configuration" in out

def test_closed_input_counts_as_empty_answer(paths):
    """End of input (e.g. answers piped in and used up) takes the defaults instead of failing."""
    _old_claude(paths)

    def closed(question):
        """Simulate closed input.

        Args:
            question: Question.

        Raises:
            EOFError: Always.
        """
        raise EOFError(question)

    opts = SetupOptions(claude_config=str(paths["claude"]), skills_dir=str(paths["skills"]))
    res = Setup(opts, ask=closed, say=lambda text: None).run()
    assert res["root"] == str(paths["root"])
    assert read_config_file(paths["config"])["PKM_GIT_DIR"] == str(paths["old_git"])

def test_finds_pkm_entries_by_program_name(paths):
    """Entries under another name are recognized by their program; unrelated servers are ignored."""
    paths["claude"].parent.mkdir(parents=True)
    data = {"mcpServers": {
        "knowledge": {"command": "C:\\Users\\me\\.local\\bin\\pkm-mcp.exe",
                      "env": {"PKM_ROOT": str(paths["root"]), "PKM_GIT_DIR": str(paths["old_git"])}},
        "other": {"command": "x", "env": {"PKM_TZ": "UTC"}}}}
    paths["claude"].write_text(json.dumps(data), encoding="utf-8")
    res, _, out = _run(paths)
    assert "[Claude Desktop (knowledge)]" in out and "PKM_TZ" not in out
    assert res["root"] == str(paths["root"]) and (paths["old_git"] / "HEAD").is_file()


def test_vault_from_git_directory(paths):
    """Without PKM_ROOT anywhere, the vault comes from core.worktree of the default Git directory."""
    setup = Setup(SetupOptions(yes=True))
    git_dir = setup._app_dir() / "git"  # pylint: disable=protected-access
    git_dir.mkdir(parents=True)
    (git_dir / "config").write_text(f"[core]\n\tbare = false\n\tworktree = {paths['root'].as_posix()}\n",
                                    encoding="utf-8")
    (paths["root"] / ".pkm").mkdir(exist_ok=True)
    (paths["root"] / ".pkm" / "state.json").write_text("{}", encoding="utf-8")
    res, asked, out = _run(paths, {"Vault folder": ""})
    assert f"[Git directory {git_dir}]" in out and any(QUESTION in q for q in asked)
    assert res["root"] == str(paths["root"])

# Main ************************************************************************
