"""MCP-Server: Tool-Liste, Aufruf in-process und Rauchtest über stdio."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pkm import mcp_server

READ_TOOLS = {"search", "read", "history", "read_index", "list_unprocessed"}


@pytest.fixture
def server(cfg):
    mcp_server.reset_service()
    yield mcp_server.build_server()
    mcp_server.reset_service()


def tool_names(server) -> set[str]:
    return {t.name for t in asyncio.run(server.list_tools())}


def test_read_tools_registered(server):
    assert READ_TOOLS <= tool_names(server)


def test_call_returns_status_on_error(server, cfg):
    res = mcp_server.call("read", mcp_server.t_read, target="gibtsnicht")
    assert res["status"] == "not_found"
    log = cfg.log_path.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(log[-1])["tool"] == "read"


def test_stdio_smoke(cfg):
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, "-m", "pkm.mcp_server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, text=True,
    )
    try:
        def send(msg):
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()

        def recv():
            while True:
                line = proc.stdout.readline()
                assert line, proc.stderr.read()
                data = json.loads(line)
                if "id" in data:
                    return data

        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"}}})
        assert "result" in recv()
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in recv()["result"]["tools"]}
        assert READ_TOOLS <= names
    finally:
        proc.kill()
        proc.wait()
