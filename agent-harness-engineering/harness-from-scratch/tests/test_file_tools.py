"""The starter tools, exercised against a real temporary directory."""

from harness.tools import list_files, read_file, run_bash, write_file


def test_read_file_returns_contents(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")

    assert read_file(str(target)) == "alpha\nbeta\n"


def test_read_missing_file_explains_itself(tmp_path):
    result = read_file(str(tmp_path / "absent.txt"))

    assert "does not exist" in result


def test_reading_a_directory_points_at_the_right_tool(tmp_path):
    result = read_file(str(tmp_path))

    assert "list_files" in result


def test_write_creates_parent_directories(tmp_path):
    target = tmp_path / "nested" / "deep" / "out.txt"

    result = write_file(str(target), "content")

    assert target.read_text(encoding="utf-8") == "content"
    assert "Created" in result


def test_write_reports_overwriting_an_existing_file(tmp_path):
    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")

    result = write_file(str(target), "new")

    assert target.read_text(encoding="utf-8") == "new"
    assert "Overwrote" in result


def test_list_files_marks_directories(tmp_path):
    (tmp_path / "file.txt").write_text("", encoding="utf-8")
    (tmp_path / "subdir").mkdir()

    listing = list_files(str(tmp_path)).splitlines()

    assert "subdir/" in listing
    assert "file.txt" in listing


def test_list_empty_directory(tmp_path):
    assert "empty" in list_files(str(tmp_path))


def test_run_bash_captures_stdout():
    assert "hello" in run_bash("echo hello")


def test_run_bash_reports_a_failing_exit_code():
    result = run_bash("exit 3")

    assert "exit code 3" in result
