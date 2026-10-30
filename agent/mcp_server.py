"""The agent's tools as an MCP server.

The agent calls every tool through this server (see agent/tools.py), and the same server
can be plugged into any MCP client, such as Claude Desktop or Claude Code:

    python -m agent.mcp_server --repo path/to/repo

Each server is bound to one repository at startup, so a client cannot point a tool at
other files on the machine.
"""

import argparse
from dataclasses import asdict
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from agent.config import Settings, get_settings
from agent.sandbox import DockerSandbox, Sandbox, SandboxError
from agent.workspace import WorkspaceError, list_source_files, rank_files, read_file


def build_server(root: Path, sandbox: Sandbox, settings: Settings) -> MCPServer:
    server = MCPServer(
        "issue-agent-tools",
        instructions=f"Read, search and test the repository checked out at {root.name}.",
    )

    @server.tool()
    def list_files() -> list[str]:
        """All source files in the repository, as paths relative to its root."""
        return list_source_files(root)

    @server.tool()
    def search_code(query: str) -> list[str]:
        """Source files (tests excluded) ranked by how many words of the query they contain."""
        return rank_files(root, query, settings.candidate_files)

    @server.tool()
    def read_source(path: str) -> str:
        """The content of one file, cut to a size that fits a model's prompt."""
        try:
            return read_file(root, path)[: settings.max_file_chars]
        except WorkspaceError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool()
    def run_tests(changes: dict[str, str] | None = None, tests: list[str] | None = None) -> dict:
        """Runs pytest in an isolated container on a copy of the repository.

        changes maps file paths to their new content and is applied to the copy only.
        tests limits the run to these test files; by default every test runs.
        """
        try:
            return asdict(sandbox.run_tests(root, changes or {}, tests))
        except SandboxError as exc:
            raise ToolError(str(exc)) from exc

    return server


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m agent.mcp_server")
    parser.add_argument("--repo", type=Path, required=True, help="Repository to serve")
    args = parser.parse_args()
    settings = get_settings()
    sandbox = DockerSandbox(
        settings.sandbox_image,
        settings.sandbox_timeout_s,
        settings.sandbox_memory,
        settings.sandbox_cpus,
    )
    build_server(args.repo.resolve(), sandbox, settings).run("stdio")


if __name__ == "__main__":
    main()
