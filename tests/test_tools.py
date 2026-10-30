"""The MCP tool server, the agent's client for it, and the Docker sandbox."""

import pytest

from agent.config import Settings
from agent.mcp_server import build_server
from agent.sandbox import DockerSandbox, SandboxError, copy_repo, docker_available
from agent.tools import ToolClient, ToolError
from tests.conftest import LocalSandbox

settings = Settings()
STATS_FUNCTIONS = ("average", "median", "percent_change", "top_n")


@pytest.fixture
def tools() -> ToolClient:
    return ToolClient(build_server(settings.demo_repo, LocalSandbox(), settings))


def test_server_offers_the_agent_tools(tools):
    assert tools.list_tools() == ["list_files", "search_code", "read_source", "run_tests"]


def test_tools_return_python_values(tools):
    assert tools.call("search_code", query="median of even values")[0] == "shopkit/stats.py"
    assert "def median" in tools.call("read_source", path="shopkit/stats.py")
    assert "shopkit/cart.py" in tools.call("list_files")
    result = tools.call("run_tests", tests=["tests/test_shopkit.py"])
    assert result["passed"] is True and result["exit_code"] == 0


def test_tool_errors_reach_the_client(tools):
    with pytest.raises(ToolError, match="not a file in the repository"):
        tools.call("read_source", path="../agent/config.py")


def test_copy_repo_refuses_to_write_outside_the_copy(tmp_path):
    with pytest.raises(SandboxError):
        copy_repo(settings.demo_repo, tmp_path / "repo", {"../escape.py": "x"})


def test_sandbox_command_is_locked_down(tmp_path):
    command = DockerSandbox("img").command(tmp_path, "name", ["tests/t.py"])
    joined = " ".join(command)
    for flag in [
        "--network none", "--read-only", "--cap-drop ALL", "no-new-privileges",
        "--user 1000:1000", "--memory 512m", "--pids-limit 128", ":/work:ro",
    ]:  # fmt: skip
        assert flag in joined
    assert command[-1] == "tests/t.py"


docker = pytest.mark.skipif(not docker_available(), reason="Docker is not running")


@docker
def test_docker_runs_the_tests_with_changes_applied():
    sandbox = DockerSandbox(settings.sandbox_image)
    assert sandbox.run_tests(settings.demo_repo, {}).passed
    # Every function the repo's tests import, each returning a wrong answer.
    stub = "".join(f"def {name}(*args):\n    return 0\n\n" for name in STATS_FUNCTIONS)
    broken = {"shopkit/stats.py": stub}
    result = sandbox.run_tests(settings.demo_repo, broken)
    assert not result.passed and result.exit_code == 1


@docker
def test_docker_blocks_the_network():
    probe = (
        "import socket\n\n\ndef test_network():\n"
        "    socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
    )
    result = DockerSandbox(settings.sandbox_image).run_tests(
        settings.demo_repo, {"tests/test_probe.py": probe}, ["tests/test_probe.py"]
    )
    assert result.exit_code == 1
    assert "Network is unreachable" in result.output or "OSError" in result.output
