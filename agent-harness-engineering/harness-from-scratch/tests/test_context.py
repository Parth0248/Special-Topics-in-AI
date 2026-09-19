"""Compaction must shrink the transcript without breaking it.

The hazard is the cut landing between a tool call and its result. That leaves a
call with no response, which the provider rejects — so the split point matters
more than the summary does.
"""

from google.genai import types

from harness.context import (
    ContextManager,
    estimate_tokens,
    find_safe_split,
)


def user(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def model(text: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part(text=text)])


def model_calls(name: str) -> types.Content:
    return types.Content(
        role="model",
        parts=[types.Part(function_call=types.FunctionCall(name=name, args={}))],
    )


def tool_result(name: str, output: str) -> types.Content:
    return types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    name=name, response={"output": output}
                )
            )
        ],
    )


def test_estimate_counts_text_calls_and_results():
    assert estimate_tokens([user("x" * 400)]) == 100
    assert estimate_tokens([tool_result("read_file", "y" * 400)]) > 0
    assert estimate_tokens([]) == 0


def test_short_transcripts_are_never_split():
    assert find_safe_split([user("a"), model("b")], keep_recent=6) == 0


def test_split_keeps_the_requested_number_of_recent_turns():
    messages = [user(f"turn {i}") for i in range(10)]

    assert find_safe_split(messages, keep_recent=4) == 6


def test_split_never_separates_a_tool_call_from_its_result():
    # The natural cut at index 6 would orphan the call at index 5.
    messages = [
        user("do a thing"),
        model("sure"),
        user("another"),
        model("ok"),
        user("now use a tool"),
        model_calls("read_file"),
        tool_result("read_file", "contents"),
        model("done"),
    ]

    split = find_safe_split(messages, keep_recent=2)

    assert split <= 5, "the cut must not land between the call and its result"
    assert not any(
        part.function_call
        for part in (messages[split - 1].parts or [])
        if split > 0
    )


def test_under_budget_transcripts_are_returned_untouched():
    manager = ContextManager(llm=None, budget_tokens=1000)
    messages = [user("short")]

    assert manager.maybe_compact(messages) is messages
    assert manager.compactions == 0


def test_over_budget_without_a_model_drops_the_oldest_turns():
    manager = ContextManager(llm=None, budget_tokens=10, keep_recent=2)
    messages = [user("x" * 400) for _ in range(6)]

    compacted = manager.maybe_compact(messages)

    assert len(compacted) == 2
    assert manager.compactions == 1


def test_over_budget_with_a_model_keeps_a_summary_in_place_of_the_old_turns():
    class FakeLLM:
        def respond(self, messages, system_prompt, tools=None):
            from harness.llm import Response

            return Response(text="the user asked for X; file Y was written")

    manager = ContextManager(llm=FakeLLM(), budget_tokens=10, keep_recent=2)
    messages = [user(f"turn {i} " + "x" * 400) for i in range(6)]

    compacted = manager.maybe_compact(messages)

    assert len(compacted) == 3  # summary + 2 recent
    assert "Earlier in this session" in compacted[0].parts[0].text
    assert "file Y was written" in compacted[0].parts[0].text


def test_a_failing_summary_falls_back_to_dropping_rather_than_crashing():
    class BrokenLLM:
        def respond(self, *args, **kwargs):
            raise RuntimeError("provider is down")

    manager = ContextManager(llm=BrokenLLM(), budget_tokens=10, keep_recent=2)
    messages = [user("x" * 400) for _ in range(6)]

    compacted = manager.maybe_compact(messages)

    assert len(compacted) == 2
