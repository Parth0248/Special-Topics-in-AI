"""Delegation has three guarantees worth pinning down.

A subagent cannot delegate in turn, cannot hold more permission than its parent,
and cannot reach tools its role does not name.
"""

from harness.agent import Agent
from harness.llm import LLM
from harness.permissions import Decision, Policy
from harness.subagents import (
    EXPLORER,
    ROLES,
    _narrow,
    _subset,
    delegation_tool,
    run_subagent,
)
from harness.tools import Registry, Tool

NO_PARAMS = {"type": "OBJECT", "properties": {}}


def _tool(name: str) -> Tool:
    return Tool(name=name, description="d", parameters=NO_PARAMS, run=lambda: "ok")


def _parent(depth: int = 0, mode: Decision = Decision.ALLOW) -> Agent:
    return Agent(
        llm=object.__new__(LLM),
        registry=Registry([_tool(n) for n in ("read_file", "list_files", "run_bash")]),
        policy=Policy(mode=mode),
        depth=depth,
    )


def test_a_subagent_cannot_delegate_again():
    result = run_subagent(_parent(depth=1), "explorer", "look at something")

    assert "cannot themselves delegate" in result


def test_an_unknown_role_lists_what_exists():
    result = run_subagent(_parent(), "archaeologist", "dig")

    assert "no role named" in result
    assert "explorer" in result


def test_ask_becomes_deny_because_nothing_can_approve_for_a_subagent():
    narrowed = _narrow(Policy(mode=Decision.ASK, confirm=lambda *_: True))

    assert narrowed.mode is Decision.DENY
    assert narrowed.confirm is None


def test_deny_stays_deny():
    assert _narrow(Policy(mode=Decision.DENY)).mode is Decision.DENY


def test_allow_is_inherited_not_escalated():
    assert _narrow(Policy(mode=Decision.ALLOW)).mode is Decision.ALLOW


def test_the_destructive_deny_list_is_inherited():
    parent = Policy(mode=Decision.ALLOW)

    narrowed = _narrow(parent)

    assert not narrowed.check("run_bash", {"command": "rm -rf /"}).allowed


def test_a_role_only_receives_the_tools_it_names():
    full = Registry([_tool(n) for n in ("read_file", "list_files", "run_bash")])

    narrowed = _subset(full, EXPLORER.tools)

    assert narrowed.names() == ["list_files", "read_file"]
    assert narrowed.get("run_bash") is None


def test_a_missing_tool_is_skipped_rather_than_crashing():
    narrowed = _subset(Registry([_tool("read_file")]), ("read_file", "absent"))

    assert narrowed.names() == ["read_file"]


def test_the_delegate_tool_advertises_every_role():
    tool = delegation_tool(_parent())

    assert tool.name == "delegate"
    for role in ROLES:
        assert role in tool.description
    assert tool.parameters["properties"]["role"]["enum"] == list(ROLES)
