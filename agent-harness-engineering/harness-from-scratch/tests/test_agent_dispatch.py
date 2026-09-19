"""Dispatch has one hard requirement: every call gets answered.

A tool call left without a matching response desyncs the transcript, and the
next request to the provider is rejected. A denial is not an exception to that —
it is a result the model has to receive.
"""

from harness.agent import Agent
from harness.llm import LLM, ToolCall
from harness.permissions import Decision, Policy
from harness.tools import Registry, Tool


def _agent(mode: Decision, runs: list[str]) -> Agent:
    registry = Registry(
        [
            Tool(
                name="write_file",
                description="test double",
                parameters={"type": "OBJECT", "properties": {}},
                run=lambda **kwargs: runs.append("ran") or "wrote it",
            )
        ]
    )
    return Agent(
        llm=object.__new__(LLM),  # never called; dispatch is what is under test
        registry=registry,
        policy=Policy(mode=mode),
    )


def test_denied_call_still_returns_a_function_response():
    runs: list[str] = []
    agent = _agent(Decision.DENY, runs)

    part = agent._dispatch(ToolCall(name="write_file", args={}))

    assert part.function_response is not None
    assert part.function_response.name == "write_file"
    assert "Denied" in part.function_response.response["output"]
    assert runs == [], "a denied tool must not have run"


def test_allowed_call_runs_and_returns_its_output():
    runs: list[str] = []
    agent = _agent(Decision.ALLOW, runs)

    part = agent._dispatch(ToolCall(name="write_file", args={}))

    assert runs == ["ran"]
    assert part.function_response.response["output"] == "wrote it"


def test_the_observer_sees_the_decision():
    seen: list[tuple[str, bool]] = []
    agent = _agent(Decision.DENY, [])
    agent.on_tool = lambda name, args, allowed: seen.append((name, allowed))

    agent._dispatch(ToolCall(name="write_file", args={}))

    assert seen == [("write_file", False)]
