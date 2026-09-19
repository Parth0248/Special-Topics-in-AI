"""Who decides whether a proposed action is allowed to run.

The model proposes; this module decides. Stage 2 let every proposal through,
which is fine until the model proposes `rm -rf`. A policy answers one question —
allow, ask, or deny — and the loop obeys the answer.

The important design choice: policy is evaluated on the *proposal*, before the
tool runs. A check that happens inside the tool is not a permission system, it
is a tool that sometimes refuses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


# Commands that are destructive enough to be worth refusing outright, even when
# the user has opted into a permissive mode. These are patterns, not a sandbox:
# stage 4 adds the actual containment.
ALWAYS_DENY = [
    re.compile(r"\brm\s+(-\w*\s+)*-\w*[rf]", re.I),  # rm -rf and friends
    re.compile(r"\bmkfs\b", re.I),
    re.compile(r"\bdd\s+.*\bof=/dev/", re.I),
    re.compile(r":\(\)\{.*\};:"),  # fork bomb
    re.compile(r"\bshutdown\b|\breboot\b", re.I),
    re.compile(r"\bgit\s+push\b.*--force", re.I),
]

# Tools that only read. Nothing they do needs confirmation.
READ_ONLY_TOOLS = {"read_file", "list_files"}


@dataclass
class Verdict:
    """The answer to 'may this call run?', with a reason the model can read."""

    decision: Decision
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


# Asks the user to confirm one call. Returns True to proceed.
Confirmer = Callable[[str, dict, str], bool]


@dataclass
class Policy:
    """Decides what the agent may do without asking.

    `mode` sets the default for anything that writes or executes:
      - "allow": run it
      - "ask":   confirm with the user first
      - "deny":  refuse everything that is not read-only
    """

    mode: Decision = Decision.ASK
    confirm: Confirmer | None = None
    always_deny: list[re.Pattern[str]] = field(default_factory=lambda: list(ALWAYS_DENY))

    def check(self, tool: str, args: dict) -> Verdict:
        """Judge one proposed call without running it."""
        if tool in READ_ONLY_TOOLS:
            return Verdict(Decision.ALLOW, "read-only tool")

        if tool == "run_bash":
            command = str(args.get("command", ""))
            for pattern in self.always_deny:
                if pattern.search(command):
                    return Verdict(
                        Decision.DENY,
                        "This command matches a destructive pattern that is "
                        "refused regardless of permission mode.",
                    )

        if self.mode is Decision.DENY:
            return Verdict(Decision.DENY, "Permission mode is 'deny'.")

        if self.mode is Decision.ALLOW:
            return Verdict(Decision.ALLOW, "Permission mode is 'allow'.")

        return self._ask(tool, args)

    def _ask(self, tool: str, args: dict) -> Verdict:
        if self.confirm is None:
            return Verdict(
                Decision.DENY,
                "This call needs confirmation, but nothing is available to ask.",
            )

        summary = _describe(tool, args)
        if self.confirm(tool, args, summary):
            return Verdict(Decision.ALLOW, "Approved by the user.")
        return Verdict(Decision.DENY, "The user declined this action.")


def _describe(tool: str, args: dict) -> str:
    if tool == "run_bash":
        return f"run: {args.get('command', '')}"
    if tool == "write_file":
        return f"write {args.get('path', '')}"
    rendered = ", ".join(f"{k}={v}" for k, v in args.items())
    return f"{tool}({rendered})"
