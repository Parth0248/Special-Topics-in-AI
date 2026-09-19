"""Delegation: one agent spawning another to do bounded work.

The reason to delegate is not that the work is hard. It is that the work is
*noisy*: searching a repository reads twenty files to find one answer, and if
that happens in the main transcript, nineteen irrelevant files are now permanent
context. A subagent does the reading in its own transcript and returns only the
answer.

So the contract is deliberately narrow. A subagent receives one task string and
returns one string. It does not share the parent's transcript, cannot ask the
user anything, and inherits a policy no more permissive than its parent's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .permissions import Decision, Policy
from .tools import Registry, Tool

if TYPE_CHECKING:
    from .agent import Agent

# A subagent that delegates in turn is a way to spend a lot of money quickly.
MAX_DEPTH = 1

# Subagents run unattended, so they get a tighter ceiling than the parent.
SUBAGENT_MAX_STEPS = 15


@dataclass(frozen=True)
class Role:
    """A named specialist: a system prompt plus the tools it is allowed."""

    name: str
    purpose: str
    prompt: str
    tools: tuple[str, ...]


EXPLORER = Role(
    name="explorer",
    purpose="Search the workspace and report findings. Reads only; changes nothing.",
    prompt="""You explore a codebase and report what you find.

Read whatever you need. Follow imports, check neighbouring files, look at tests.
Then answer in a way that stands alone — the agent receiving your answer cannot
see any of the files you read.

Quote exact paths, exact names, exact line content. If you could not find
something, say so plainly rather than guessing at what it probably is.""",
    tools=("read_file", "list_files"),
)

REVIEWER = Role(
    name="reviewer",
    purpose="Review code for correctness problems. Reads only; changes nothing.",
    prompt="""You review code and report defects.

Read the code under review and anything it depends on. Report only problems you
can point at: the file, the line, what goes wrong, and the input or state that
makes it go wrong.

Rank by severity. Say "no defects found" when that is the honest answer — an
invented problem costs more than a missed one.""",
    tools=("read_file", "list_files"),
)

ROLES: dict[str, Role] = {role.name: role for role in (EXPLORER, REVIEWER)}


def _narrow(policy: Policy) -> Policy:
    """A subagent never gets more permission than its parent.

    Nothing can approve on its behalf, so `ask` becomes `deny` rather than
    silently hanging or silently allowing.
    """
    mode = Decision.DENY if policy.mode is Decision.ASK else policy.mode
    return Policy(mode=mode, confirm=None, always_deny=list(policy.always_deny))


def _subset(registry: Registry, allowed: tuple[str, ...]) -> Registry:
    return Registry([registry.get(name) for name in allowed if registry.get(name)])


def run_subagent(parent: Agent, role_name: str, task: str) -> str:
    """Run one task in a fresh transcript and return only its answer."""
    from .agent import Agent as _Agent  # imported late to avoid a cycle

    role = ROLES.get(role_name)
    if role is None:
        return f"Error: no role named {role_name!r}. Available: {', '.join(sorted(ROLES))}"

    if parent.depth >= MAX_DEPTH:
        return (
            "Error: subagents cannot themselves delegate. Do this work directly."
        )

    child = _Agent(
        llm=parent.llm,
        registry=_subset(parent.registry, role.tools),
        policy=_narrow(parent.policy),
        system_prompt=role.prompt,
        max_steps=SUBAGENT_MAX_STEPS,
        on_tool=parent.on_tool,
        depth=parent.depth + 1,
    )

    return child.send(task)


def delegation_tool(parent: Agent) -> Tool:
    """The `delegate` tool, bound to the agent that owns it."""
    catalogue = "\n".join(f"- {r.name}: {r.purpose}" for r in ROLES.values())

    def run(role: str, task: str) -> str:
        return run_subagent(parent, role, task)

    return Tool(
        name="delegate",
        description=(
            "Hand a self-contained task to a specialist agent and receive only "
            "its answer. Use this for work that would otherwise read many files "
            "into this conversation.\n\nAvailable roles:\n" + catalogue
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "role": {
                    "type": "STRING",
                    "enum": list(ROLES),
                    "description": "Which specialist to use.",
                },
                "task": {
                    "type": "STRING",
                    "description": "The complete task. The specialist cannot see "
                    "this conversation, so include every detail it needs.",
                },
            },
            "required": ["role", "task"],
        },
        run=run,
    )


def describe_roles() -> dict[str, Any]:
    return {name: role.purpose for name, role in ROLES.items()}
