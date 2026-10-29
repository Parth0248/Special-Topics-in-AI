"""Embedded In-Process Tool Provider for Agent C.

Provides in-process, zero-friction filesystem, search, git, and execution tools
mirroring the FastMCP toolset for direct local execution and testing.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class EmbeddedTools:
    """In-process tool provider for filesystem, code search, git, and test execution."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = (
            Path(workspace_root).resolve() if workspace_root else Path.cwd().resolve()
        )

    def _resolve_path(self, path: str) -> Path:
        """Resolve a relative or absolute path within the workspace root."""
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace_root / p
        return p.resolve()

    # -------------------------------------------------------------------------
    # Filesystem Tools
    # -------------------------------------------------------------------------

    def read_file(
        self,
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """Read the contents of a file, optionally within a 1-indexed line range.

        Args:
            path: Relative or absolute path to the file.
            start_line: Optional 1-indexed start line (inclusive).
            end_line: Optional 1-indexed end line (inclusive).

        Returns:
            The file content or sliced lines as a string.
        """
        file_path = self._resolve_path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise IsADirectoryError(f"Path is a directory, not a file: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="utf-8", errors="replace")

        lines = content.splitlines(keepends=True)
        if start_line is not None or end_line is not None:
            s = max(1, start_line) if start_line is not None else 1
            e = min(len(lines), end_line) if end_line is not None else len(lines)
            if s > len(lines):
                return ""
            sliced = lines[s - 1 : e]
            return "".join(sliced)

        return content

    def write_file(self, path: str, content: str) -> str:
        """Write content to a file, creating parent directories if necessary.

        Args:
            path: Relative or absolute path to the destination file.
            content: The text content to write.

        Returns:
            Confirmation message with path and written byte size.
        """
        file_path = self._resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        byte_count = len(content.encode("utf-8"))
        return f"Successfully wrote {byte_count} bytes to {file_path}"

    def list_directory(self, path: str = ".", recursive: bool = False) -> List[str]:
        """List files and directories in the target path.

        Args:
            path: Directory path to list.
            recursive: Whether to recursively traverse subdirectories.

        Returns:
            List of relative path strings.
        """
        target_dir = self._resolve_path(path)
        if not target_dir.exists():
            raise FileNotFoundError(f"Directory not found: {target_dir}")
        if not target_dir.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {target_dir}")

        ignored_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", ".pytest_tmp"}
        results: List[str] = []

        if not recursive:
            for item in sorted(target_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                rel = item.relative_to(target_dir).as_posix()
                if item.is_dir():
                    rel += "/"
                results.append(rel)
        else:
            for root, dirs, files in os.walk(target_dir):
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
                root_path = Path(root)
                for d in sorted(dirs):
                    rel = (root_path / d).relative_to(target_dir).as_posix() + "/"
                    results.append(rel)
                for f in sorted(files):
                    rel = (root_path / f).relative_to(target_dir).as_posix()
                    results.append(rel)

        return results

    def directory_tree(self, path: str = ".", max_depth: int = 3) -> str:
        """Generate a formatted ASCII directory tree structure.

        Args:
            path: Directory path to inspect.
            max_depth: Maximum recursion depth.

        Returns:
            Formatted ASCII tree string.
        """
        target_dir = self._resolve_path(path)
        if not target_dir.exists():
            raise FileNotFoundError(f"Directory not found: {target_dir}")
        if not target_dir.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {target_dir}")

        ignored_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", ".pytest_tmp"}
        lines: List[str] = [f"{target_dir.name}/"]

        def _build_tree(curr_dir: Path, prefix: str = "", current_depth: int = 1):
            if current_depth > max_depth:
                return
            try:
                entries = sorted(
                    [
                        e
                        for e in curr_dir.iterdir()
                        if e.name not in ignored_dirs and not (e.name.startswith(".") and e.is_dir())
                    ],
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except PermissionError:
                return

            total = len(entries)
            for idx, entry in enumerate(entries):
                is_last = idx == total - 1
                connector = "└── " if is_last else "├── "
                sub_prefix = "    " if is_last else "│   "

                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    _build_tree(entry, prefix + sub_prefix, current_depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")

        _build_tree(target_dir)
        return "\n".join(lines)

    def get_file_info(self, path: str) -> Dict[str, Any]:
        """Retrieve detailed metadata about a file or directory.

        Args:
            path: Relative or absolute path to inspect.

        Returns:
            Dictionary containing size, timestamps, line count, and types.
        """
        file_path = self._resolve_path(path)
        if not file_path.exists():
            return {
                "path": str(file_path),
                "exists": False,
                "is_file": False,
                "is_dir": False,
                "size_bytes": 0,
                "line_count": 0,
                "modified_time": None,
            }

        stat = file_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
        is_file = file_path.is_file()
        line_count = 0
        if is_file:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    line_count = sum(1 for _ in f)
            except Exception:
                line_count = 0

        return {
            "path": str(file_path),
            "exists": True,
            "is_file": is_file,
            "is_dir": file_path.is_dir(),
            "size_bytes": stat.st_size,
            "line_count": line_count,
            "modified_time": mtime,
        }

    # -------------------------------------------------------------------------
    # Code Search Tools
    # -------------------------------------------------------------------------

    def search_files(
        self,
        pattern: str,
        path: str = ".",
        extension: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for a regex or literal text pattern in files under a directory.

        Args:
            pattern: Search string or regex pattern.
            path: Directory or file to search in.
            extension: Optional extension filter (e.g. '.py' or 'py').

        Returns:
            List of matching records: [{file, line_number, line, match}].
        """
        target = self._resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Search target does not exist: {target}")

        if extension and not extension.startswith("."):
            extension = f".{extension}"

        try:
            regex = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern}': {e}") from e

        ignored_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", ".pytest_tmp"}
        matches: List[Dict[str, Any]] = []

        files_to_scan: List[Path] = []
        if target.is_file():
            files_to_scan.append(target)
        else:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
                for f in files:
                    if extension and not f.endswith(extension):
                        continue
                    files_to_scan.append(Path(root) / f)

        for file_path in files_to_scan:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for idx, line in enumerate(content.splitlines(), start=1):
                match = regex.search(line)
                if match:
                    rel = (
                        file_path.relative_to(self.workspace_root).as_posix()
                        if file_path.is_relative_to(self.workspace_root)
                        else file_path.as_posix()
                    )
                    matches.append(
                        {
                            "file": rel,
                            "line_number": idx,
                            "line": line.strip(),
                            "match": match.group(0),
                        }
                    )
                    if len(matches) >= 200:  # Safety cap
                        return matches

        return matches

    def find_symbol(self, symbol_name: str, path: str = ".") -> List[Dict[str, Any]]:
        """Locate function, class, or variable definitions in Python files using AST.

        Args:
            symbol_name: Exact or prefix name of function/class/variable.
            path: Directory or file to inspect.

        Returns:
            List of definitions: [{file, line_number, symbol_type, name}].
        """
        target = self._resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Symbol search path does not exist: {target}")

        ignored_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", ".pytest_tmp"}
        files_to_scan: List[Path] = []
        if target.is_file() and target.suffix == ".py":
            files_to_scan.append(target)
        elif target.is_dir():
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
                for f in files:
                    if f.endswith(".py"):
                        files_to_scan.append(Path(root) / f)

        definitions: List[Dict[str, Any]] = []

        for file_path in files_to_scan:
            try:
                tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"), filename=str(file_path))
            except SyntaxError:
                continue

            rel = (
                file_path.relative_to(self.workspace_root).as_posix()
                if file_path.is_relative_to(self.workspace_root)
                else file_path.as_posix()
            )

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == symbol_name:
                        definitions.append(
                            {
                                "file": rel,
                                "line_number": node.lineno,
                                "symbol_type": "function",
                                "name": node.name,
                            }
                        )
                elif isinstance(node, ast.ClassDef):
                    if node.name == symbol_name:
                        definitions.append(
                            {
                                "file": rel,
                                "line_number": node.lineno,
                                "symbol_type": "class",
                                "name": node.name,
                            }
                        )
                elif isinstance(node, ast.Assign):
                    for target_node in node.targets:
                        if isinstance(target_node, ast.Name) and target_node.id == symbol_name:
                            definitions.append(
                                {
                                "file": rel,
                                "line_number": target_node.lineno,
                                "symbol_type": "variable",
                                "name": target_node.id,
                            }
                        )

        return definitions

    # -------------------------------------------------------------------------
    # Git Tools
    # -------------------------------------------------------------------------

    def git_status(self, repo_path: Optional[str] = None) -> str:
        """Run `git status --porcelain` in the target repository.

        Args:
            repo_path: Optional path to repository. Defaults to workspace root.

        Returns:
            Porcelain status output or error string.
        """
        cwd = self._resolve_path(repo_path or ".")
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip() or "Clean working directory (no changes)"
            return f"Git error (code {res.returncode}): {res.stderr.strip()}"
        except Exception as e:
            return f"Failed to execute git status: {e}"

    def git_diff(self, repo_path: Optional[str] = None, target: Optional[str] = None) -> str:
        """Run `git diff` in the target repository.

        Args:
            repo_path: Optional path to repository.
            target: Optional commit, branch, or file target.

        Returns:
            Unified diff string or empty message.
        """
        cwd = self._resolve_path(repo_path or ".")
        cmd = ["git", "diff"]
        if target:
            cmd.append(target)
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip() or "No git diff found (working tree clean)"
            return f"Git diff error (code {res.returncode}): {res.stderr.strip()}"
        except Exception as e:
            return f"Failed to execute git diff: {e}"

    def git_log(self, repo_path: Optional[str] = None, max_count: int = 5) -> str:
        """Run `git log` with oneline summary.

        Args:
            repo_path: Path to repository.
            max_count: Number of recent commits to return.

        Returns:
            Formatted git log lines.
        """
        cwd = self._resolve_path(repo_path or ".")
        cmd = ["git", "log", f"-n{max_count}", "--oneline"]
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip() or "No commit history found"
            return f"Git log error (code {res.returncode}): {res.stderr.strip()}"
        except Exception as e:
            return f"Failed to execute git log: {e}"

    # -------------------------------------------------------------------------
    # Test Runner Tool
    # -------------------------------------------------------------------------

    def run_test_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Execute a test command in a subprocess with a timeout.

        Args:
            command: Shell command to execute (e.g. `pytest test_foo.py`).
            cwd: Working directory for command. Defaults to workspace root.
            timeout: Subprocess timeout in seconds.

        Returns:
            Dict containing exit_code, stdout, stderr, timed_out, duration_seconds.
        """
        exec_cwd = self._resolve_path(cwd or ".")
        start_time = time.time()
        try:
            res = subprocess.run(
                command,
                cwd=exec_cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = round(time.time() - start_time, 3)
            return {
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "timed_out": False,
                "duration_seconds": duration,
            }
        except subprocess.TimeoutExpired as e:
            duration = round(time.time() - start_time, 3)
            return {
                "exit_code": -1,
                "stdout": e.stdout or "",
                "stderr": f"Command timed out after {timeout} seconds",
                "timed_out": True,
                "duration_seconds": duration,
            }
        except Exception as e:
            duration = round(time.time() - start_time, 3)
            return {
                "exit_code": -2,
                "stdout": "",
                "stderr": f"Execution failed: {e}",
                "timed_out": False,
                "duration_seconds": duration,
            }

    # -------------------------------------------------------------------------
    # Tool Dispatch & Schema Map
    # -------------------------------------------------------------------------

    def get_tool_map(self) -> Dict[str, Any]:
        """Return mapping of tool name to callable method."""
        return {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "list_directory": self.list_directory,
            "directory_tree": self.directory_tree,
            "get_file_info": self.get_file_info,
            "search_files": self.search_files,
            "find_symbol": self.find_symbol,
            "git_status": self.git_status,
            "git_diff": self.git_diff,
            "git_log": self.git_log,
            "run_test_command": self.run_test_command,
        }

    def call_tool(self, name: str, **kwargs) -> Any:
        """Call an embedded tool by name with keyword arguments."""
        tool_map = self.get_tool_map()
        if name not in tool_map:
            raise ValueError(f"Unknown tool '{name}'. Available: {list(tool_map.keys())}")
        return tool_map[name](**kwargs)


# Module-level default instance
_default_tools = EmbeddedTools()

read_file = _default_tools.read_file
write_file = _default_tools.write_file
list_directory = _default_tools.list_directory
directory_tree = _default_tools.directory_tree
get_file_info = _default_tools.get_file_info
search_files = _default_tools.search_files
find_symbol = _default_tools.find_symbol
git_status = _default_tools.git_status
git_diff = _default_tools.git_diff
git_log = _default_tools.git_log
run_test_command = _default_tools.run_test_command
