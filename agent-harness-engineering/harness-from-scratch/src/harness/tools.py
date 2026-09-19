"""Tools: the actions a model is allowed to propose.

A tool is a Python function plus a schema the model can read. The registry
owns both halves, so the loop can ask "what can be proposed?" and "run this
proposal" without knowing what any individual tool does.

Every tool returns a string. Tool output is model input, and the model reads
text — a tool that returns rich objects just forces someone else to stringify
them, usually worse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from google.genai import types

from .sandbox import DEFAULT_TIMEOUT_SECONDS, HostSandbox, Sandbox, SandboxViolation

# Tool output is fed straight back into the context window. Without a ceiling,
# one `cat` of a large file evicts the rest of the conversation.
MAX_OUTPUT_CHARS = 8000


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

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

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
        except SandboxViolation as exc:
            return f"Error: {exc}"
        except TypeError as exc:
            return f"Error: bad arguments for {name!r}: {exc}"
        except Exception as exc:  # noqa: BLE001 - a crashed tool must not kill the loop
            return f"Error: {name!r} failed: {type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------
# The starter set: read, write, list, run.
#
# Each takes the sandbox it acts through, so the same tool body works on the
# host or in a container. `default_registry` binds one in.
# --------------------------------------------------------------------------


def read_file(sandbox: Sandbox, path: str) -> str:
    target = sandbox.resolve(path)
    if not target.exists():
        return f"Error: {path} does not exist."
    if target.is_dir():
        return f"Error: {path} is a directory. Use list_files."
    return target.read_text(encoding="utf-8", errors="replace")


def write_file(sandbox: Sandbox, path: str, content: str) -> str:
    target = sandbox.resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    target.write_text(content, encoding="utf-8")
    verb = "Overwrote" if existed else "Created"
    relative = target.relative_to(sandbox.workspace) if target != sandbox.workspace else "."
    return f"{verb} {relative} ({len(content)} characters)."


def list_files(sandbox: Sandbox, path: str = ".") -> str:
    target = sandbox.resolve(path)
    if not target.is_dir():
        return f"Error: {path} is not a directory."
    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    if not entries:
        return f"{path} is empty."
    return "\n".join(f"{e.name}/" if e.is_dir() else e.name for e in entries)


def run_bash(sandbox: Sandbox, command: str) -> str:
    """Run a shell command inside the sandbox and return whatever it printed."""
    return sandbox.run(command, timeout=DEFAULT_TIMEOUT_SECONDS).render()


def default_registry(sandbox: Sandbox | None = None) -> Registry:
    """Build the starter registry, bound to a sandbox."""
    box = sandbox if sandbox is not None else HostSandbox()

    def bind(fn: Callable[..., str]) -> Callable[..., str]:
        def bound(**kwargs: Any) -> str:
            return fn(box, **kwargs)

        return bound

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
                run=bind(read_file),
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
                run=bind(write_file),
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
                run=bind(list_files),
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
                run=bind(run_bash),
            ),
        ]
    )
