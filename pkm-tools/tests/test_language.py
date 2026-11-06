"""Document language of documents created in chat (``PKM_LANGUAGE``, specification 7.1, 15.1).

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

from pkm import cli
from pkm.config import Config, configured_language, parse_language, read_config_file
from pkm.errors import PkmError
from pkm.maintenance_server import build_server as build_maintenance_server
from pkm.maintenance_server import wiki_language_instructions
from pkm.mcp_server import build_server, language_instructions
from pkm.setupwiz import Setup, SetupOptions

# Variables *******************************************************************

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="paths")
def fixture_paths(isolated_env, tmp_path, monkeypatch):
    """Paths for a setup run; PKM_ROOT is not set.

    Args:
        isolated_env: Isolated environment.
        tmp_path: Temporary folder of pytest.
        monkeypatch: pytest fixture.

    Returns:
        Vault, configuration file, Claude Desktop configuration and skills folder.
    """
    monkeypatch.delenv("PKM_ROOT")
    return {"root": isolated_env["root"], "config": tmp_path / "app" / "config.toml",
            "claude": tmp_path / "claude" / "claude_desktop_config.json", "skills": tmp_path / "skills"}


def _run(paths, answers=None, **kw):
    """Run the setup; questions are answered from ``answers`` (otherwise ``yes``).

    Args:
        paths: Paths of the fixture ``paths``.
        answers: Part of the question → answer, or ``None`` for ``yes``.
        **kw: Further options.

    Returns:
        Result of ``Setup.run`` and the questions asked.
    """
    asked: list[str] = []

    def ask(question):
        """Answer a question from ``answers``.

        Args:
            question: Question.

        Returns:
            The answer.
        """
        asked.append(question)
        return next((v for k, v in (answers or {}).items() if k in question), "")

    opts = SetupOptions(vault=str(paths["root"]), yes=answers is None, claude_config=str(paths["claude"]),
                        skills_dir=str(paths["skills"]), **kw)
    res = Setup(opts, ask=ask, say=lambda text: None).run()
    return res, asked


def test_parse_language():
    """en/de and the names of the languages are accepted, empty gives English, others are refused."""
    assert parse_language(None) == "en" and parse_language("") == "en"
    assert parse_language("DE") == "de" and parse_language("Deutsch") == "de" and parse_language("german") == "de"
    assert parse_language("english") == "en" and parse_language(" en ") == "en"
    with pytest.raises(PkmError) as err:
        parse_language("fr")
    assert err.value.status == "config_error"


def test_config_language(isolated_env, monkeypatch, tmp_path):
    """Config reads PKM_LANGUAGE from the environment or config.toml; default English."""
    assert Config.from_env().language == "en"
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "app" / "config.toml").write_text('PKM_LANGUAGE = "de"\n', encoding="utf-8")
    assert Config.from_env().language == "de" and configured_language() == "de"
    monkeypatch.setenv("PKM_LANGUAGE", "en")
    assert Config.from_env().language == "en" and configured_language() == "en"
    monkeypatch.setenv("PKM_LANGUAGE", "fr")
    with pytest.raises(PkmError):
        Config.from_env()
    assert configured_language() == "en"  # the server still starts
    assert isolated_env["root"].is_dir()


def test_server_instructions_name_language_and_sections():
    """The instructions of the server pkm name the document language and its section names."""
    german = language_instructions("de")
    assert "German" in german and "## Ergebnis" in german and "## Kontext / Begründung" in german
    english = language_instructions("en")
    assert "English" in english and "## Open points" in english and "Ergebnis" not in english
    assert "## Offene Punkte" in build_server("de").instructions
    assert "## Open points" in build_server("en").instructions


def test_maintenance_instructions_name_wiki_language_and_sections(isolated_env, tmp_path):
    """The instructions of the server pkm-maintenance name the wiki language, sections and summary label."""
    german = wiki_language_instructions("de")
    assert "German" in german and "## Inhalt" in german and "## Belege" in german and "Kurzfassung" in german
    english = wiki_language_instructions("en")
    assert "## Content" in english and "**Summary:**" in english and "Inhalt" not in english
    assert "## Widersprüche / offene Fragen" in build_maintenance_server("de").instructions
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "app" / "config.toml").write_text('PKM_LANGUAGE = "de"\n', encoding="utf-8")
    assert "## Siehe auch" in build_maintenance_server().instructions  # from the configuration
    assert isolated_env["root"].is_dir()


def test_setup_asks_for_language_and_keeps_it(paths):
    """pkm setup asks for the language, writes it to config.toml and offers it as default next time."""
    res, asked = _run(paths, {"Main language": "de"})
    assert res["status"] == "ok" and res["language"] == "de"
    assert sum("Main language" in q for q in asked) == 1
    assert read_config_file(paths["config"])["PKM_LANGUAGE"] == "de"
    res, asked = _run(paths, {})
    assert res["language"] == "de" and any("Main language" in q and "[de]" in q for q in asked)
    res, _ = _run(paths)
    assert res["language"] == "de"


def test_setup_language_option_and_default(paths, capsys):
    """--language replaces the question; without an answer the language is English."""
    res, asked = _run(paths, {}, language="Deutsch")
    assert res["language"] == "de" and not any("Main language" in q for q in asked)
    paths["config"].unlink()
    res, _ = _run(paths)
    assert res["language"] == "en" and read_config_file(paths["config"])["PKM_LANGUAGE"] == "en"
    code = cli.main(["setup", "--yes", "--json", "--vault", str(paths["root"]), "--claude-config",
                     str(paths["claude"]), "--skills-dir", str(paths["skills"]), "--language", "de"])
    assert code == 0 and json.loads(capsys.readouterr().out)["language"] == "de"
    code = cli.main(["setup", "--yes", "--vault", str(paths["root"]), "--claude-config", str(paths["claude"]),
                     "--skills-dir", str(paths["skills"]), "--language", "fr"])
    assert code == 1 and "PKM_LANGUAGE" in capsys.readouterr().out

# Main ************************************************************************
