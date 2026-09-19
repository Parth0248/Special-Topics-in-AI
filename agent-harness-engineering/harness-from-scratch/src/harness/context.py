"""What happens when the conversation outgrows the window.

Every agent hits this. Tool results are large, the transcript only grows, and
eventually the next request does not fit. There are two honest answers:

- **Drop** the oldest turns. Cheap, and the agent forgets what it was doing.
- **Compact** them: ask the model to summarise the old turns, then keep the
  summary in their place. Costs one extra call, and the thread survives.

This implements compaction, with dropping as the fallback when no model is
available. The part that takes care is *where* the cut lands — a transcript
sliced between a tool call and its result is rejected by the provider, so the
boundary has to respect call/response pairs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from google.genai import types

from .llm import LLM

# Rough characters-per-token. Counting exactly needs a tokenizer call per turn,
# which costs more than the estimate is worth for a budget check.
CHARS_PER_TOKEN = 4

# Compact when the transcript passes this. Well under any real context window,
# because the summary call needs room too.
DEFAULT_BUDGET_TOKENS = 60_000

# Recent turns are kept verbatim — the agent needs its immediate working state,
# not a summary of what it did ten seconds ago.
DEFAULT_KEEP_RECENT = 6

SUMMARY_PROMPT = """Summarise this portion of a coding session transcript.

Record findings, not activity. "Read config.py" is worthless to your future
self; "config.py sets DEBUG=True and reads DATABASE_URL from the environment"
is the thing worth keeping. Every fact the session established by looking must
survive here, because the transcript it came from is about to be discarded and
these notes are all that remain.

Preserve, in this order:
1. What the user asked for, including anything still outstanding.
2. Facts discovered — file contents, values, versions, structures. Quote the
   specifics: names, numbers, paths, exact strings.
3. Decisions made and why.
4. Files written, with their paths and what was put in them.
5. Anything that failed, with the exact error text.

Write it as notes to your future self, not as prose for a reader. Omit
pleasantries entirely."""


def estimate_tokens(messages: list[types.Content]) -> int:
    """Approximate the size of a transcript without calling a tokenizer."""
    total = 0
    for message in messages:
        for part in message.parts or []:
            if part.text:
                total += len(part.text)
            if part.function_call:
                total += len(str(part.function_call.args or "")) + len(
                    part.function_call.name or ""
                )
            if part.function_response:
                total += len(str(part.function_response.response or ""))
    return total // CHARS_PER_TOKEN


def _opens_tool_calls(message: types.Content) -> bool:
    return any(part.function_call for part in message.parts or [])


def find_safe_split(messages: list[types.Content], keep_recent: int) -> int:
    """Pick an index to cut at that does not orphan a tool call.

    A model turn containing tool calls must stay with the turn carrying their
    results. Cutting between them leaves a call with no response, and the
    provider rejects the next request.
    """
    if len(messages) <= keep_recent:
        return 0

    split = len(messages) - keep_recent

    # Walk backwards off any turn that would be separated from its results.
    while split > 0 and _opens_tool_calls(messages[split - 1]):
        split -= 1

    return split


@dataclass
class ContextManager:
    """Keeps a transcript inside its budget."""

    llm: LLM | None = None
    budget_tokens: int = DEFAULT_BUDGET_TOKENS
    keep_recent: int = DEFAULT_KEEP_RECENT
    compactions: int = field(default=0, init=False)

    def maybe_compact(self, messages: list[types.Content]) -> list[types.Content]:
        """Return a transcript that fits, compacting only if it does not."""
        if estimate_tokens(messages) <= self.budget_tokens:
            return messages

        split = find_safe_split(messages, self.keep_recent)
        if split == 0:
            # Everything is recent or tool-bound; there is nothing safe to fold.
            return messages

        older, recent = messages[:split], messages[split:]
        summary = self._summarise(older)
        self.compactions += 1

        if summary is None:
            return recent

        return [
            types.Content(
                role="user",
                parts=[types.Part(text=f"[Earlier in this session]\n{summary}")],
            ),
            *recent,
        ]

    def _summarise(self, older: list[types.Content]) -> str | None:
        """Fold old turns into notes. Returns None if no model is available."""
        if self.llm is None:
            return None

        transcript = _render(older)
        try:
            response = self.llm.respond(
                [types.Content(role="user", parts=[types.Part(text=transcript)])],
                SUMMARY_PROMPT,
            )
        except Exception:  # noqa: BLE001 - losing the summary beats losing the session
            return None

        return response.text or None


def _render(messages: list[types.Content]) -> str:
    """Flatten a transcript into text a model can read in one pass."""
    lines: list[str] = []
    for message in messages:
        for part in message.parts or []:
            if part.text and not part.thought:
                lines.append(f"{message.role}: {part.text}")
            if part.function_call:
                lines.append(
                    f"{message.role}: called {part.function_call.name}"
                    f"({part.function_call.args})"
                )
            if part.function_response:
                output = (part.function_response.response or {}).get("output", "")
                lines.append(f"tool: {output}")
    return "\n".join(lines)
