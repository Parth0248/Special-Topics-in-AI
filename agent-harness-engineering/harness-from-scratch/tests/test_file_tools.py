"""The starter tools, exercised through a host sandbox rooted at tmp_path."""

import pytest

from harness.sandbox import HostSandbox
from harness.tools import list_files, read_file, run_bash, write_file


@pytest.fixture
def box(tmp_path):
    return HostSandbox(tmp_path)


def test_read_file_returns_contents(box):
    (box.workspace / "notes.txt").write_text("alpha\nbeta\n", encoding="utf-8")

    assert read_file(box, "notes.txt") == "alpha\nbeta\n"


def test_read_missing_file_explains_itself(box):
    assert "does not exist" in read_file(box, "absent.txt")


def test_reading_a_directory_points_at_the_right_tool(box):
    (box.workspace / "sub").mkdir()

    assert "list_files" in read_file(box, "sub")


def test_write_creates_parent_directories(box):
    result = write_file(box, "nested/deep/out.txt", "content")

    assert (box.workspace / "nested" / "deep" / "out.txt").read_text() == "content"
    assert "Created" in result


def test_write_reports_overwriting_an_existing_file(box):
    write_file(box, "out.txt", "old")

    result = write_file(box, "out.txt", "new")

    assert (box.workspace / "out.txt").read_text() == "new"
    assert "Overwrote" in result


def test_list_files_marks_directories(box):
    (box.workspace / "file.txt").write_text("", encoding="utf-8")
    (box.workspace / "subdir").mkdir()

    listing = list_files(box, ".").splitlines()

    assert "subdir/" in listing
    assert "file.txt" in listing


def test_list_empty_directory(box):
    assert "empty" in list_files(box, ".")


def test_run_bash_captures_stdout(box):
    assert "hello" in run_bash(box, "echo hello")


def test_run_bash_reports_a_failing_exit_code(box):
    assert "exit code 3" in run_bash(box, "exit 3")
