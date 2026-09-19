"""The registry's job is to make tool failure survivable.

A tool that raises, a tool that does not exist, and a call with the wrong
arguments all have to come back as text the model can read. If any of them
escapes as an exception, it kills the loop.
"""

from harness.tools import MAX_OUTPUT_CHARS, Registry, Tool, default_registry, truncate

NO_PARAMS = {"type": "OBJECT", "properties": {}}


def _tool(name: str, run) -> Tool:
    return Tool(name=name, description="test tool", parameters=NO_PARAMS, run=run)


def test_unknown_tool_reports_what_is_available():
    registry = Registry([_tool("real", lambda: "ok")])

    result = registry.invoke("imaginary", {})

    assert "no tool named" in result
    assert "real" in result


def test_raising_tool_becomes_readable_text():
    def explode() -> str:
        raise ValueError("disk on fire")

    registry = Registry([_tool("explode", explode)])

    result = registry.invoke("explode", {})

    assert "ValueError" in result
    assert "disk on fire" in result


def test_wrong_arguments_are_reported_not_raised():
    registry = Registry([_tool("greet", lambda: "hi")])

    result = registry.invoke("greet", {"unexpected": 1})

    assert "bad arguments" in result


def test_long_output_is_truncated():
    registry = Registry([_tool("flood", lambda: "x" * (MAX_OUTPUT_CHARS * 2))])

    result = registry.invoke("flood", {})

    assert len(result) < MAX_OUTPUT_CHARS * 2
    assert "truncated" in result


def test_short_output_is_untouched():
    assert truncate("hello") == "hello"


def test_default_registry_exposes_the_starter_tools():
    assert default_registry().names() == [
        "list_files",
        "read_file",
        "run_bash",
        "write_file",
    ]
