"""Tools: the actions a model is allowed to propose.

A tool is a Python function plus a schema the model can read. The registry
owns both halves, so the loop can ask "what can be proposed?" and "run this
proposal" without knowing what any individual tool does.

Every tool returns a string. Tool output is model input, and the model reads
text — a tool that returns rich objects just forces someone else to stringify
them, usually worse.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from google.genai import types

# Tool output is fed straight back into the context window. Without a ceiling,
# one `cat` of a large file evicts the rest of the conversation.
MAX_OUTPUT_CHARS = 8000

BASH_TIMEOUT_SECONDS = 60


def truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return f"{text[:limit]}\n\n[... {dropped} more characters truncated ...]"


@dataclass
class Tool:
    """One callable action, with the schema the model sees."""

    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[..., str]

    def declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(**self.parameters),
        )


class Registry:
    """The set of tools available to one agent."""

    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.add(tool)

    def add(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def as_gemini_tools(self) -> list[types.Tool]:
        if not self._tools:
            return []
        return [
            types.Tool(
                function_declarations=[t.declaration() for t in self._tools.values()]
            )
        ]

    def invoke(self, name: str, args: dict[str, Any]) -> str:
        """Run a tool by name, converting failure into text the model can read."""
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: no tool named {name!r}. Available: {', '.join(self.names())}"
        try:
            return truncate(tool.run(**args))
        except TypeError as exc:
            return f"Error: bad arguments for {name!r}: {exc}"
        except Exception as exc:  # noqa: BLE001 - a crashed tool must not kill the loop
            return f"Error: {name!r} failed: {type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------
# The starter set: read, write, list, run.
# --------------------------------------------------------------------------


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def read_file(path: str) -> str:
    target = _resolve(path)
    if not target.exists():
        return f"Error: {path} does not exist."
    if target.is_dir():
        return f"Error: {path} is a directory. Use list_files."
    return target.read_text(encoding="utf-8", errors="replace")


def write_file(path: str, content: str) -> str:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    target.write_text(content, encoding="utf-8")
    verb = "Overwrote" if existed else "Created"
    return f"{verb} {target} ({len(content)} characters)."


def list_files(path: str = ".") -> str:
    target = _resolve(path)
    if not target.is_dir():
        return f"Error: {path} is not a directory."
    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    if not entries:
        return f"{target} is empty."
    lines = [f"{e.name}/" if e.is_dir() else e.name for e in entries]
    return "\n".join(lines)


def run_bash(command: str) -> str:
    """Run a shell command and return whatever it printed."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=BASH_TIMEOUT_SECONDS,
    )
    chunks = []
    if result.stdout.strip():
        chunks.append(result.stdout.rstrip())
    if result.stderr.strip():
        chunks.append(f"[stderr]\n{result.stderr.rstrip()}")
    if result.returncode != 0:
        chunks.append(f"[exit code {result.returncode}]")
    return "\n".join(chunks) if chunks else "(no output)"


def default_registry() -> Registry:
    return Registry(
        [
            Tool(
                name="read_file",
                description="Read a text file and return its contents.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "path": {"type": "STRING", "description": "Path to the file."}
                    },
                    "required": ["path"],
                },
                run=read_file,
            ),
            Tool(
                name="write_file",
                description="Write text to a file, creating parent directories and "
                "overwriting any existing file.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "path": {"type": "STRING", "description": "Path to write."},
                        "content": {"type": "STRING", "description": "Full file contents."},
                    },
                    "required": ["path", "content"],
                },
                run=write_file,
            ),
            Tool(
                name="list_files",
                description="List the entries of a directory.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "path": {
                            "type": "STRING",
                            "description": "Directory to list. Defaults to the "
                            "working directory.",
                        }
                    },
                },
                run=list_files,
            ),
            Tool(
                name="run_bash",
                description="Run a shell command and return its output.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "command": {"type": "STRING", "description": "The command to run."}
                    },
                    "required": ["command"],
                },
                run=run_bash,
            ),
        ]
    )
