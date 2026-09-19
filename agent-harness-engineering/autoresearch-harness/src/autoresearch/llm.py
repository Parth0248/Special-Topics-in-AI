"""The model boundary.

Same shape as the one in `harness-from-scratch`: everything the loop knows
about a language model is behind `LLM.respond`, so swapping the backend is a
change to this file alone.

This project keeps its own copy rather than importing the other one. They are
separate projects that happen to talk to the same API, and a shared dependency
between them would be a worse story than sixty duplicated lines.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-3.8-flash"


@dataclass
class Response:
    text: str = ""
    parts: list[types.Part] = field(default_factory=list)


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

    def respond(self, messages: list[types.Content], system_prompt: str) -> Response:
        config = types.GenerateContentConfig(system_instruction=system_prompt)
        raw = self._client.models.generate_content(
            model=self.model, contents=messages, config=config
        )

        text_parts: list[str] = []
        parts: list[types.Part] = []

        for candidate in raw.candidates or []:
            for part in (candidate.content.parts if candidate.content else None) or []:
                parts.append(part)
                # Thinking traces are not part of the answer.
                if part.text and not part.thought:
                    text_parts.append(part.text)

        return Response(text="".join(text_parts).strip(), parts=parts)
