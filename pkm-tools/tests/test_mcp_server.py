"""MCP server: tool list, in-process call and smoke test via stdio.

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

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pkm import mcp_server
from pkm.service import Service

# Variables *******************************************************************

READ_TOOLS = {"search", "read", "history", "read_index", "list_unprocessed"}

# Classes *********************************************************************

# Functions *******************************************************************


@pytest.fixture(name="server")
def fixture_server(cfg):
    """MCP server with a fresh service.

    Args:
        cfg: Configuration (only for the setup).

    Yields:
        The server.
    """
    del cfg  # only needed for the setup
    mcp_server.reset_service()
    yield mcp_server.build_server()
    mcp_server.reset_service()


def tool_names(server) -> set[str]:
    """Names of all registered tools.

    Args:
        server: MCP-Server.

    Returns:
        Set of the tool names.
    """
    return {t.name for t in asyncio.run(server.list_tools())}


def test_read_tools_registered(server):
    """All reading tools are registered."""
    assert READ_TOOLS <= tool_names(server)


@pytest.mark.usefixtures("server")
def test_call_returns_status_on_error(cfg):
    """Domain errors come back as a status and are logged."""
    res = mcp_server.call("read", Service.read, target="gibtsnicht")
    assert res["status"] == "not_found"
    log = cfg.log_path.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(log[-1])["tool"] == "read"


def _send(proc: subprocess.Popen, msg: dict) -> None:
    """Send a message to the server.

    Args:
        proc: Running server process.
        msg: JSON-RPC message.
    """
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def _recv(proc: subprocess.Popen) -> dict:
    """Read the next response with ``id`` (notifications are skipped).

    Args:
        proc: Running server process.

    Returns:
        The JSON-RPC response.
    """
    data: dict = {}
    while "id" not in data:
        line = proc.stdout.readline()
        assert line, proc.stderr.read()
        data = json.loads(line)
    return data


@pytest.mark.usefixtures("cfg")
def test_stdio_smoke():
    """The server answers initialize and tools/list via stdio."""
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    with subprocess.Popen(
        [sys.executable, "-m", "pkm.mcp_server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, text=True,
    ) as proc:
        try:
            _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"}}})
            assert "result" in _recv(proc)
            _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            names = {t["name"] for t in _recv(proc)["result"]["tools"]}
            assert READ_TOOLS <= names
        finally:
            proc.kill()


# Main ************************************************************************
