"""Pure-Python FastMCP Server for Agent C: Bug Assistant.

Exposes filesystem, code search, git operations, and test runner tools
over the Model Context Protocol (MCP) using stdio transport with ZERO Node.js dependency.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

try:
    from .embedded_tools import EmbeddedTools
except ImportError:
    from embedded_tools import EmbeddedTools


def create_mcp_server(
    name: str = "agent-c-bug-assistant",
    workspace_root: Optional[str] = None,
) -> FastMCP:
    """Create and configure a FastMCP server instance with bug assistant tools.

    Args:
        name: Name of the MCP server.
        workspace_root: Optional root directory for tool sandboxing/path resolution.

    Returns:
        Configured FastMCP instance ready to serve via stdio or SSE.
    """
    server = FastMCP(name)
    tools = EmbeddedTools(workspace_root=workspace_root)

    # -------------------------------------------------------------------------
    # Filesystem Tools
    # -------------------------------------------------------------------------

    @server.tool(name="read_file", description="Read file contents with optional line slice [start_line, end_line]")
    def read_file(
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """Read the contents of a file, optionally within a 1-indexed line range."""
        return tools.read_file(path=path, start_line=start_line, end_line=end_line)

    @server.tool(name="write_file", description="Write content to a file, creating parent directories if needed")
    def write_file(path: str, content: str) -> str:
        """Write content to a file, creating parent directories if necessary."""
        return tools.write_file(path=path, content=content)

    @server.tool(name="list_directory", description="List entries in a directory, optionally recursive")
    def list_directory(path: str = ".", recursive: bool = False) -> List[str]:
        """List files and directories in the target path."""
        return tools.list_directory(path=path, recursive=recursive)

    @server.tool(name="directory_tree", description="Generate a formatted ASCII directory tree structure")
    def directory_tree(path: str = ".", max_depth: int = 3) -> str:
        """Generate a formatted ASCII directory tree structure."""
        return tools.directory_tree(path=path, max_depth=max_depth)

    @server.tool(name="get_file_info", description="Retrieve file metadata (size, lines, timestamps)")
    def get_file_info(path: str) -> Dict[str, Any]:
        """Retrieve detailed metadata about a file or directory."""
        return tools.get_file_info(path=path)

    # -------------------------------------------------------------------------
    # Code Search & AST Inspection Tools
    # -------------------------------------------------------------------------

    @server.tool(name="search_files", description="Search for regex or literal pattern across workspace files")
    def search_files(
        pattern: str,
        path: str = ".",
        extension: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for a regex or literal text pattern in files under a directory."""
        return tools.search_files(pattern=pattern, path=path, extension=extension)

    @server.tool(name="find_symbol", description="Locate function, class, or variable definitions via AST")
    def find_symbol(symbol_name: str, path: str = ".") -> List[Dict[str, Any]]:
        """Locate function, class, or variable definitions in Python files using AST."""
        return tools.find_symbol(symbol_name=symbol_name, path=path)

    # -------------------------------------------------------------------------
    # Git Tools
    # -------------------------------------------------------------------------

    @server.tool(name="git_status", description="Get git status porcelain output for workspace")
    def git_status(repo_path: Optional[str] = None) -> str:
        """Run `git status --porcelain` in the target repository."""
        return tools.git_status(repo_path=repo_path)

    @server.tool(name="git_diff", description="Get git unified diff of working tree or target commit")
    def git_diff(repo_path: Optional[str] = None, target: Optional[str] = None) -> str:
        """Run `git diff` in the target repository."""
        return tools.git_diff(repo_path=repo_path, target=target)

    @server.tool(name="git_log", description="Get recent git commit log (oneline format)")
    def git_log(repo_path: Optional[str] = None, max_count: int = 5) -> str:
        """Run `git log` with oneline summary."""
        return tools.git_log(repo_path=repo_path, max_count=max_count)

    # -------------------------------------------------------------------------
    # Test Runner Tool
    # -------------------------------------------------------------------------

    @server.tool(name="run_test_command", description="Run a test command in a subprocess with timeout")
    def run_test_command(
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Execute a test command in a subprocess with a timeout."""
        return tools.run_test_command(command=command, cwd=cwd, timeout=timeout)

    return server


# Default server instance
mcp = create_mcp_server()


def get_mcp_server_command(module_mode: bool = True) -> List[str]:
    """Get the command line invocation to launch this MCP server via stdio.

    Args:
        module_mode: Whether to launch via `python -m agent_c_bug_assistant.mcp_server`
                     or directly with file path.

    Returns:
        List of command strings suitable for subprocess or ADK McpToolset.
    """
    if module_mode:
        return [sys.executable, "-m", "agent_c_bug_assistant.mcp_server"]
    server_path = str(Path(__file__).resolve())
    return [sys.executable, server_path]


if __name__ == "__main__":
    # Start FastMCP server on stdio transport
    mcp.run(transport="stdio")
