"""The model boundary.

Everything the harness knows about a language model lives behind `LLM.respond`.
The loop above it never sees a provider SDK, so swapping Gemini for another
backend is a change to this file alone.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-2.5-flash"


@dataclass
class ToolCall:
    """A request from the model to run one tool."""

    name: str
    args: dict[str, Any]
    call_id: str = ""


@dataclass
class Response:
    """One turn from the model: prose, tool calls, or both."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLM:
    """A thin, synchronous wrapper over the Gemini API."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError(
                "No API key. Set GOOGLE_API_KEY in your .env "
                "(get one free at https://aistudio.google.com/apikey)."
            )
        self.model = model or os.environ.get("HARNESS_MODEL") or DEFAULT_MODEL
        self._client = genai.Client(api_key=key)

    def respond(
        self,
        messages: list[types.Content],
        system_prompt: str,
        tools: list[types.Tool] | None = None,
    ) -> Response:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=tools or None,
            # The harness runs its own loop, so the SDK must not run one too.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        raw = self._client.models.generate_content(
            model=self.model, contents=messages, config=config
        )
        return self._parse(raw)

    @staticmethod
    def _parse(raw: types.GenerateContentResponse) -> Response:
        text_parts: list[str] = []
        calls: list[ToolCall] = []

        for candidate in raw.candidates or []:
            for part in (candidate.content.parts if candidate.content else None) or []:
                if part.text:
                    text_parts.append(part.text)
                if part.function_call:
                    fc = part.function_call
                    calls.append(
                        ToolCall(
                            name=fc.name or "",
                            args=dict(fc.args or {}),
                            call_id=fc.id or "",
                        )
                    )

        return Response(text="".join(text_parts).strip(), tool_calls=calls)
