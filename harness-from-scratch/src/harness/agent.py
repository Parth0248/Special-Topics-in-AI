"""The agent loop.

A harness is a loop with a stopping rule. The model proposes; the harness
decides whether to run what was proposed, runs it, feeds the result back, and
asks again. Stage 1 has no tools to run yet, so the loop stops on the first
reply — but the shape is already the one every later stage extends.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from google.genai import types

from .llm import LLM, Response

SYSTEM_PROMPT = """You are a coding assistant running inside a terminal harness.

Be direct. When you do not know something about the user's project, say so
rather than guessing at file contents or APIs.
"""

# A runaway loop burns tokens and money. Every harness needs this number.
MAX_STEPS = 25


@dataclass
class Agent:
    """Drives one conversation to completion."""

    llm: LLM
    system_prompt: str = SYSTEM_PROMPT
    max_steps: int = MAX_STEPS
    messages: list[types.Content] = field(default_factory=list)

    def send(self, user_input: str) -> str:
        """Run the loop until the model answers without asking for a tool."""
        self.messages.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        for _ in range(self.max_steps):
            response = self.llm.respond(self.messages, self.system_prompt)
            self._record(response)

            if not response.wants_tools:
                return response.text

            # Stage 1 has no tool registry. Later stages dispatch here.
            raise NotImplementedError(
                f"Model requested tool {response.tool_calls[0].name!r}, "
                "but no tools are registered yet."
            )

        return f"Stopped after {self.max_steps} steps without a final answer."

    def _record(self, response: Response) -> None:
        parts: list[types.Part] = []
        if response.text:
            parts.append(types.Part(text=response.text))
        if parts:
            self.messages.append(types.Content(role="model", parts=parts))
