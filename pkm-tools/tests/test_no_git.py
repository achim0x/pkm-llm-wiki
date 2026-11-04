"""Operation without Git: version control is optional (specification 0.26, 5.4, 15.1).

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

import pytest

from pkm import maintrun
from pkm.config import Config, find_git, read_config_file, write_config_file
from pkm.doctor import doctor
from pkm.errors import PkmError
from pkm.lint import lint
from pkm.maint import Maintenance
from pkm.service import Service
from pkm.vaultinit import init_vault

from .conftest import write

# Variables *******************************************************************

BODY = "## Result\nFloat switch.\n\n## Open points\n- Mounting\n"

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="nsvc")
def fixture_nsvc(isolated_env, monkeypatch):
    """Service for a vault initialized without version control.

    Args:
        isolated_env: Isolated environment.
        monkeypatch: pytest fixture.

    Returns:
        The service.
    """
    monkeypatch.setenv("PKM_VERSIONING", "off")
    cfg = Config.from_env()
    res = init_vault(cfg)
    assert res["versioning"] is False and res["commit"] is None and res["git_dir"] is None
    assert not isolated_env["git_dir"].exists()
    return Service(cfg)


def _page(svc, doc_id):
    """Wiki page with a citation of the section "Result".

    Args:
        svc: Service.
        doc_id: Document ID.

    Returns:
        Page content.
    """
    doc = svc.read(f"id:{doc_id}")
    sha = next(s["sha"] for s in doc["sections"] if s["key"] == "Result")
    link = doc["path"][:-3]
    return ("---\ntype: summary\ntitle: Sensor\nsources: []\nconfidence: high\n---\n\n"
            "> **Summary:** Sensor decision.\n\n## Content\nA float switch is used.[^b1]\n\n## Citations\n"
            f"[^b1]: [[{link}#Result]] · \"Float switch.\" · id:{doc_id} · v:{doc['version']} · sha:{sha}\n")


def test_write_tools_without_git(nsvc):
    """Creating and changing works without Git: versions count up, there is no commit."""
    created = nsvc.create_document(title="Sensor", content=BODY)
    assert created["status"] == "created" and created["version"] == 1 and created["commit"] is None
    doc = nsvc.read(created["path"])
    res = nsvc.append_to_document(target=created["path"], text="- Cable", expected_hash=doc["hash"],
                                  section="Open points")
    assert res["status"] == "changed" and res["version"] == 2 and res["commit"] is None
    assert "- Cable" in nsvc.read(created["path"])["content"]


def test_history_tools_report_not_versioned(nsvc):
    """history, read with version and restore_document return not_versioned with a hint."""
    created = nsvc.create_document(title="Sensor", content=BODY)
    for call in (lambda: nsvc.history(created["path"]), lambda: nsvc.read(created["path"], version=1),
                 lambda: nsvc.restore_document(created["path"], 1, created["new_hash"])):
        with pytest.raises(PkmError) as exc:
            call()
        assert exc.value.status == "not_versioned" and "pkm setup" in exc.value.message


def test_maintenance_without_git(nsvc):
    """versions, ids and commit-wiki do not need Git; a manual change is detected via the hashes."""
    m = Maintenance(nsvc)
    write(nsvc.cfg, "documents/note.md", "# Note\n\nText.\n")
    assert m.versions() == {"status": "ok", "versioning": False, "committed": [], "skipped": []}
    ids = m.ids()
    assert ids["assigned"][0]["path"] == "documents/note.md" and ids["assigned"][0]["commit"] is None
    doc_id = ids["assigned"][0]["id"]
    m.mark([doc_id])
    assert m.pending()["counts"]["new"] == 0
    write(nsvc.cfg, "documents/note.md", nsvc.vault.load("documents/note.md").text.replace("Text.", "Other."))
    assert [c["path"] for c in m.pending()["changed"]] == ["documents/note.md"]
    assert m.commit_wiki("ingest")["status"] == "unchanged"


def test_full_run_without_git(nsvc):
    """A maintenance run without Git: no errors in doctor and lint, a citation of an older version stays ok."""
    created = nsvc.create_document(title="Sensor", content=BODY)
    begin = maintrun.begin_maintenance(nsvc)
    assert begin["status"] == "ok", begin
    assert maintrun.write_wiki_page(nsvc, "wiki/summaries/sensor", _page(nsvc, created["id"]))["status"] == "created"
    fin = maintrun.finish_maintenance(nsvc, "- new: wiki/summaries/sensor", log_title="1 new",
                                      processed=[created["id"]])
    assert fin["lint"]["summary"]["error"] == 0, fin["lint"]["findings"]
    assert fin["commit"]["status"] == "unchanged" and fin["commit"]["versioning"] is False
    doc = nsvc.read(created["path"])
    nsvc.append_to_document(target=created["path"], text="- Cable", expected_hash=doc["hash"], section="Open points")
    report = lint(nsvc)
    assert report["summary"]["error"] == 0, report["findings"]
    checks = {c["check"]: c for c in doctor(nsvc)["checks"]}
    assert doctor(nsvc)["errors"] == 0 and "git_repo" not in checks and "pkm setup" in checks["versioning"]["message"]


def test_versioning_on_without_git_is_an_error(isolated_env, monkeypatch):
    """With version control on but no Git program, doctor names the fix and the write tools refuse."""
    del isolated_env  # only needed for the setup
    cfg = Config.from_env()
    init_vault(cfg)
    monkeypatch.setenv("PKM_GIT", "/nonexistent/git")
    svc = Service(Config.from_env())
    checks = {c["check"]: c for c in doctor(svc)["checks"]}
    assert checks["git_installed"]["severity"] == "error" and "pkm setup" in checks["git_installed"]["message"]
    with pytest.raises(PkmError) as exc:
        svc.create_document(title="X", content="Y")
    assert exc.value.status == "git_unavailable"


def test_config_file(isolated_env, monkeypatch, tmp_path):
    """config.toml provides the values; environment variables take precedence."""
    path = tmp_path / "pkm" / "config.toml"
    write_config_file(path, {"PKM_ROOT": str(isolated_env["root"]), "PKM_VAULT_NAME": 'My "Vault" \\ x',
                             "PKM_VERSIONING": False})
    assert read_config_file(path) == {"PKM_ROOT": str(isolated_env["root"]), "PKM_VAULT_NAME": 'My "Vault" \\ x',
                                      "PKM_VERSIONING": "false"}
    monkeypatch.setenv("PKM_CONFIG", str(path))
    monkeypatch.delenv("PKM_ROOT")
    cfg = Config.from_env()
    assert cfg.root == isolated_env["root"].resolve() and cfg.vault_name == 'My "Vault" \\ x'
    assert cfg.versioning is False and cfg.config_file == path
    monkeypatch.setenv("PKM_VERSIONING", "on")
    assert Config.from_env().versioning is True
    path.write_text("broken = [", encoding="utf-8")
    with pytest.raises(PkmError) as exc:
        Config.from_env()
    assert exc.value.status == "config_error"


def test_find_git():
    """Git is found in PATH (the test machines have Git)."""
    found = find_git()
    assert found is not None and Config.from_env({"PKM_ROOT": "/x" if found.startswith("/") else "C:\\x"}).git_exe

# Main ************************************************************************
