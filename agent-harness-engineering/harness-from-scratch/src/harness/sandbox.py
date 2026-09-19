"""Where an action runs, and what it can reach from there.

Stage 3 decides *whether* a call may run. This decides *where*. The two are
independent and both are needed: a policy that refuses `rm -rf` still lets
`write_file` land anywhere on the disk, and a sandbox that confines writes still
runs whatever command it is handed.

Two sandboxes ship here:

- `HostSandbox` runs on the machine, confined to a workspace directory.
- `DockerSandbox` runs commands in a container with the workspace mounted.

Both satisfy the same protocol, so the tools do not know which one they have.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_IMAGE = "python:3.12-slim"


class SandboxViolation(Exception):
    """A path escaped the workspace."""


@dataclass
class CommandResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0

    def render(self) -> str:
        chunks = []
        if self.stdout.strip():
            chunks.append(self.stdout.rstrip())
        if self.stderr.strip():
            chunks.append(f"[stderr]\n{self.stderr.rstrip()}")
        if self.exit_code != 0:
            chunks.append(f"[exit code {self.exit_code}]")
        return "\n".join(chunks) if chunks else "(no output)"


class Sandbox(Protocol):
    """The execution environment the tools act through."""

    workspace: Path

    def resolve(self, path: str) -> Path: ...

    def run(self, command: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> CommandResult: ...


@dataclass
class HostSandbox:
    """Runs on this machine, with every path confined to the workspace."""

    workspace: Path = field(default_factory=Path.cwd)

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str) -> Path:
        """Turn a model-supplied path into a real one inside the workspace.

        Resolving before comparing is what makes this hold: `../../etc/passwd`
        and a symlink pointing outside both collapse to an absolute path that
        simply is not under the workspace.
        """
        candidate = (self.workspace / path).expanduser()
        resolved = candidate.resolve()

        if resolved != self.workspace and self.workspace not in resolved.parents:
            raise SandboxViolation(
                f"{path!r} resolves outside the workspace ({self.workspace})."
            )
        return resolved

    def run(self, command: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> CommandResult:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )


@dataclass
class DockerSandbox:
    """Runs commands in a container with the workspace mounted.

    Path confinement still happens on the host, because the tools read and write
    files directly; the container's job is to contain *execution*.
    """

    workspace: Path = field(default_factory=Path.cwd)
    image: str = DEFAULT_IMAGE
    network: bool = False

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._host = HostSandbox(self.workspace)

    @staticmethod
    def available() -> bool:
        if shutil.which("docker") is None:
            return False
        probe = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=20
        )
        return probe.returncode == 0

    def resolve(self, path: str) -> Path:
        return self._host.resolve(path)

    def run(self, command: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> CommandResult:
        argv = [
            "docker", "run", "--rm",
            "--volume", f"{self.workspace}:/workspace",
            "--workdir", "/workspace",
            # A container that can still reach the network and spawn unbounded
            # processes is only half a sandbox.
            "--network", "bridge" if self.network else "none",
            "--pids-limit", "256",
            "--memory", "512m",
            self.image,
            "sh", "-c", command,
        ]
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return CommandResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )
