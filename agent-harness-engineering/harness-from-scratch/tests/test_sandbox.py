"""The sandbox's one job: a path the model supplies cannot leave the workspace."""

import pytest

from harness.sandbox import CommandResult, HostSandbox, SandboxViolation
from harness.tools import Registry, Tool, read_file


@pytest.fixture
def box(tmp_path):
    return HostSandbox(tmp_path / "workspace")


def test_relative_paths_resolve_inside_the_workspace(box):
    assert box.resolve("notes.txt").parent == box.workspace


def test_the_workspace_itself_is_allowed(box):
    assert box.resolve(".") == box.workspace


def test_nested_paths_are_allowed(box):
    assert box.resolve("a/b/c.txt").parent.parent.parent == box.workspace


@pytest.mark.parametrize(
    "escape",
    [
        "../outside.txt",
        "../../outside.txt",
        "a/../../outside.txt",
        "./../../etc/passwd",
    ],
)
def test_traversal_is_refused(box, escape):
    with pytest.raises(SandboxViolation):
        box.resolve(escape)


def test_absolute_paths_outside_are_refused(box, tmp_path):
    outsider = tmp_path / "elsewhere.txt"
    outsider.write_text("secret", encoding="utf-8")

    with pytest.raises(SandboxViolation):
        box.resolve(str(outsider))


def test_a_violation_reaches_the_model_as_text_not_an_exception(box):
    registry = Registry(
        [
            Tool(
                name="read_file",
                description="read",
                parameters={"type": "OBJECT", "properties": {}},
                run=lambda **kw: read_file(box, **kw),
            )
        ]
    )

    result = registry.invoke("read_file", {"path": "../../etc/passwd"})

    assert "outside the workspace" in result


def test_commands_run_with_the_workspace_as_their_directory(box):
    (box.workspace / "marker.txt").write_text("", encoding="utf-8")

    result = box.run("ls")

    assert "marker.txt" in result.stdout


def test_command_result_renders_stderr_and_exit_code():
    rendered = CommandResult(stdout="out", stderr="bad", exit_code=2).render()

    assert "out" in rendered
    assert "bad" in rendered
    assert "exit code 2" in rendered


def test_command_result_renders_silence():
    assert CommandResult().render() == "(no output)"
