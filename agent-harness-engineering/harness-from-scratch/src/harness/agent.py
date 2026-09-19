"""The agent loop.

A harness is a loop with a stopping rule. The model proposes; the harness
decides whether to run what was proposed, runs it, feeds the result back, and
asks again. The loop ends when the model answers without asking to act.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from google.genai import types

from .llm import LLM, Response, ToolCall
from .permissions import Policy
from .tools import Registry, default_registry

SYSTEM_PROMPT = """You are a coding assistant running inside a terminal harness.

You have tools for reading, writing, and listing files, and for running shell
commands. Use them instead of guessing: if a question is about the user's
project, read the project.

Some actions require the user's permission. If a call is refused, do not retry
it or work around it — tell the user what you wanted to do and why.

Work in small steps. Run one tool, look at what came back, then decide the next
one. When the task is done, say so plainly and stop calling tools.
"""

# A runaway loop burns tokens and money. Every harness needs this number.
MAX_STEPS = 25

# Called with (tool_name, args, was_allowed) after each decision, so a front end
# can show the user what the agent did and what it was stopped from doing.
ToolObserver = Callable[[str, dict, bool], None]


@dataclass
class Agent:
    """Drives one conversation to completion."""

    llm: LLM
    registry: Registry = field(default_factory=default_registry)
    policy: Policy = field(default_factory=Policy)
    system_prompt: str = SYSTEM_PROMPT
    max_steps: int = MAX_STEPS
    on_tool: ToolObserver | None = None
    messages: list[types.Content] = field(default_factory=list)

    def send(self, user_input: str) -> str:
        """Run the loop until the model answers without asking for a tool."""
        self.messages.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        for _ in range(self.max_steps):
            response = self.llm.respond(
                self.messages,
                self.system_prompt,
                tools=self.registry.as_gemini_tools(),
            )
            self._record_model_turn(response)

            if not response.wants_tools:
                return response.text

            results = [self._dispatch(call) for call in response.tool_calls]
            self.messages.append(types.Content(role="user", parts=results))

        return (
            f"Stopped after {self.max_steps} steps without a final answer. "
            "The task may need to be broken into smaller pieces."
        )

    def _dispatch(self, call: ToolCall) -> types.Part:
        """Judge one proposed call, run it if allowed, and answer the model.

        A refusal still returns a response. Leaving a call unanswered desyncs
        the transcript and the next request is rejected — so 'denied' has to be
        a result the model receives, not a result it never gets.
        """
        verdict = self.policy.check(call.name, call.args)

        if self.on_tool:
            self.on_tool(call.name, call.args, verdict.allowed)

        if verdict.allowed:
            output = self.registry.invoke(call.name, call.args)
        else:
            output = f"Denied: {verdict.reason}"

        return types.Part(
            function_response=types.FunctionResponse(
                name=call.name,
                response={"output": output},
            )
        )

    def _record_model_turn(self, response: Response) -> None:
        """Append the model's turn to the transcript exactly as it arrived.

        The tool calls must go back in — a provider that sees a tool result with
        no matching call rejects the request — and they must go back *unmodified*,
        because thinking models sign each call and check the signature on the
        next request.
        """
        if response.parts:
            self.messages.append(types.Content(role="model", parts=response.parts))
