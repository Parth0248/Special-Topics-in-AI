"""Automated Test Suite for Agent C: MCP Tools-Based Bug Assistant.

Tests all components:
- Traceback parsing & application frame isolation
- Embedded tools (filesystem, AST symbol search, git, test runner)
- FastMCP server registration
- 5-Phase Bug Triage Pipeline (intake -> context -> reproducer -> patch -> verification)
- Patch application and backup rollback
- Google ADK Agent integration and demo runner
- CLI argument parsing and execution
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_c_bug_assistant.agent import BugAssistantAgent
from agent_c_bug_assistant.embedded_tools import EmbeddedTools
from agent_c_bug_assistant.mcp_server import create_mcp_server, get_mcp_server_command, mcp
from agent_c_bug_assistant.triage import (
    BugContext,
    BugTriagePipeline,
    DiagnosticReport,
    StackFrame,
    TracebackInfo,
    TracebackParser,
    apply_patch_unified,
    gather_bug_context,
    rollback_patch,
    synthesize_patch,
    synthesize_reproducer,
    verify_bug_and_fix,
)


# =============================================================================
# 1. Traceback Parsing Tests
# =============================================================================


def test_parse_standard_traceback():
    tb = """Traceback (most recent call last):
  File "app/services/calculator.py", line 45, in compute_ratio
    result = total / count
ZeroDivisionError: division by zero
"""
    info = TracebackParser.parse(tb)
    assert info.exception_type == "ZeroDivisionError"
    assert info.exception_message == "division by zero"
    assert len(info.frames) == 1
    assert info.primary_frame is not None
    assert info.primary_frame.filename == "app/services/calculator.py"
    assert info.primary_frame.line_number == 45
    assert info.primary_frame.function_name == "compute_ratio"
    assert info.primary_frame.code_line == "result = total / count"
    assert info.primary_frame.is_application_frame is True


def test_parse_application_vs_library_frames():
    tb = """Traceback (most recent call last):
  File "app/main.py", line 12, in handle_request
    data = fetch_upstream()
  File "C:\\Python313\\Lib\\site-packages\\requests\\api.py", line 59, in get
    return request('get', url)
  File "C:\\Python313\\Lib\\site-packages\\urllib3\\connectionpool.py", line 380, in urlopen
    raise MaxRetryError(self, url, e)
urllib3.exceptions.MaxRetryError: Max retries exceeded
"""
    info = TracebackParser.parse(tb)
    assert len(info.frames) == 3
    # Check library identification
    assert info.frames[0].is_application_frame is True
    assert info.frames[1].is_application_frame is False
    assert info.frames[2].is_application_frame is False

    # Primary frame should be the deepest application frame (app/main.py)
    assert info.primary_frame is not None
    assert info.primary_frame.filename == "app/main.py"
    assert info.primary_frame.line_number == 12


def test_parse_unstructured_traceback():
    raw = """Crash report at 2026-10-29 12:00:00
File "analytics/engine.py", line 88, in aggregate
  total = values[0]
IndexError: list index out of range
"""
    info = TracebackParser.parse(raw)
    assert info.exception_type == "IndexError"
    assert info.exception_message == "list index out of range"
    assert len(info.frames) == 1
    assert info.primary_frame.filename == "analytics/engine.py"
    assert info.primary_frame.line_number == 88


# =============================================================================
# 2. Embedded Tools Tests
# =============================================================================


def test_embedded_filesystem_tools(tmp_path):
    tools = EmbeddedTools(workspace_root=str(tmp_path))

    # Test write_file & read_file
    res = tools.write_file("src/module.py", "line 1\nline 2\nline 3\nline 4\nline 5\n")
    assert "Successfully wrote" in res
    assert (tmp_path / "src" / "module.py").exists()

    content = tools.read_file("src/module.py")
    assert "line 1" in content

    # Test sliced read
    sliced = tools.read_file("src/module.py", start_line=2, end_line=4)
    assert sliced == "line 2\nline 3\nline 4\n"

    # Test list_directory and directory_tree
    tools.write_file("src/sub/nested.txt", "data")
    listing = tools.list_directory("src", recursive=True)
    assert any("nested.txt" in item for item in listing)

    tree = tools.directory_tree("src")
    assert "module.py" in tree
    assert "nested.txt" in tree

    # Test get_file_info
    info = tools.get_file_info("src/module.py")
    assert info["exists"] is True
    assert info["is_file"] is True
    assert info["line_count"] == 5
    assert info["size_bytes"] > 0


def test_embedded_search_and_symbol_tools(tmp_path):
    tools = EmbeddedTools(workspace_root=str(tmp_path))

    code = '''class PaymentGateway:
    def process_transaction(self, amount: float):
        status = "approved"
        return status

def trigger_billing():
    pass
'''
    tools.write_file("billing.py", code)

    # Search pattern
    matches = tools.search_files("approved", path="billing.py")
    assert len(matches) == 1
    assert matches[0]["line_number"] == 3
    assert matches[0]["match"] == "approved"

    # Find symbols via AST
    symbols_cls = tools.find_symbol("PaymentGateway", path="billing.py")
    assert len(symbols_cls) == 1
    assert symbols_cls[0]["symbol_type"] == "class"

    symbols_func = tools.find_symbol("process_transaction", path="billing.py")
    assert len(symbols_func) == 1
    assert symbols_func[0]["symbol_type"] == "function"
    assert symbols_func[0]["line_number"] == 2


def test_embedded_git_and_test_command(tmp_path):
    tools = EmbeddedTools(workspace_root=str(tmp_path))

    # Test command runner (echo command)
    res = tools.run_test_command('python -c "print(\'Agent C Test Runner OK\')"', timeout=10)
    assert res["exit_code"] == 0
    assert "Agent C Test Runner OK" in res["stdout"]
    assert res["timed_out"] is False

    # Test command failure
    res_fail = tools.run_test_command('python -c "import sys; sys.exit(42)"', timeout=10)
    assert res_fail["exit_code"] == 42

    # Git tools in current repo
    status = tools.git_status()
    assert isinstance(status, str)


# =============================================================================
# 3. FastMCP Server Registration Tests
# =============================================================================


def test_mcp_server_tools_registered():
    server = create_mcp_server(name="test-server")
    assert hasattr(server, "_tool_manager")

    tool_names = list(server._tool_manager._tools.keys())
    required_tools = [
        "read_file",
        "write_file",
        "list_directory",
        "directory_tree",
        "get_file_info",
        "search_files",
        "find_symbol",
        "git_status",
        "git_diff",
        "git_log",
        "run_test_command",
    ]
    for req in required_tools:
        assert req in tool_names, f"FastMCP server missing required tool: {req}"


def test_mcp_server_command_generator():
    cmd = get_mcp_server_command(module_mode=True)
    assert sys.executable in cmd[0]
    assert "agent_c_bug_assistant.mcp_server" in cmd


# =============================================================================
# 4. 5-Phase Triage Pipeline & Verification Tests
# =============================================================================


def test_reproducer_synthesis_syntax_check(tmp_path):
    context = BugContext(
        faulty_file="service.py",
        line_number=10,
        function_name="dispatch_job",
        code_snippet="result = queue.pop()",
        surrounding_lines=[(10, "result = queue.pop()")],
    )
    tb_info = TracebackInfo(
        raw_text="",
        exception_type="IndexError",
        exception_message="pop from empty list",
    )

    reproducer_script = synthesize_reproducer(tb_info, context)
    # Must be valid Python syntax
    parsed = ast.parse(reproducer_script)
    assert isinstance(parsed, ast.Module)
    assert "test_reproduce_bug" in reproducer_script


def test_unified_patch_synthesis_and_rollback(tmp_path):
    target = tmp_path / "calc.py"
    original = """def divide(a, b):
    return a / b
"""
    target.write_text(original, encoding="utf-8")

    context = BugContext(
        faulty_file="calc.py",
        line_number=2,
        function_name="divide",
        code_snippet="return a / b",
        surrounding_lines=[(1, "def divide(a, b):"), (2, "    return a / b")],
    )
    tb_info = TracebackInfo(
        raw_text="",
        exception_type="ZeroDivisionError",
        exception_message="division by zero",
    )

    diff = synthesize_patch(context, tb_info, original_content=original)
    assert "--- a/calc.py" in diff
    assert "+++ b/calc.py" in diff

    # Apply patch
    success = apply_patch_unified(str(target), diff, backup=True)
    assert success is True
    patched_content = target.read_text(encoding="utf-8")
    assert "if not b:" in patched_content or "return 0.0" in patched_content

    # Rollback
    reverted = rollback_patch(str(target))
    assert reverted is True
    assert target.read_text(encoding="utf-8") == original


def test_end_to_end_triage_pipeline_zero_division(tmp_path):
    """Test full 5-phase bug triage:
    1. Parse traceback
    2. Context gathering
    3. Reproducer synthesis
    4. Patch synthesis
    5. Two-stage verification (fails before patch, passes after patch)
    """
    tools = EmbeddedTools(workspace_root=str(tmp_path))

    # Setup buggy service in tmp_path
    buggy_service = '''def compute_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator

def run_calculation():
    return compute_ratio(10.0, 0.0)
'''
    tools.write_file("ratio_service.py", buggy_service)

    simulated_tb = f"""Traceback (most recent call last):
  File "{(tmp_path / 'ratio_service.py').as_posix()}", line 5, in run_calculation
    return compute_ratio(10.0, 0.0)
  File "{(tmp_path / 'ratio_service.py').as_posix()}", line 2, in compute_ratio
    return numerator / denominator
ZeroDivisionError: float division by zero
"""

    reproducer = f'''import sys
from pathlib import Path
import pytest
sys.path.insert(0, r"{tmp_path.as_posix()}")
from ratio_service import run_calculation

def test_reproduce_zero_division():
    res = run_calculation()
    assert res == 0.0 or res is not None
'''

    fixed_code = '''def compute_ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator

def run_calculation():
    return compute_ratio(10.0, 0.0)
'''

    pipeline = BugTriagePipeline(workspace_root=str(tmp_path))
    report = pipeline.run_triage(
        stack_trace=simulated_tb,
        repo_path=str(tmp_path),
        apply_permanently=True,
        custom_reproducer=reproducer,
        custom_fix=fixed_code,
    )

    assert report.bug_type == "ZeroDivisionError"
    assert report.pre_patch_test_passed is False  # Must have failed before patch!
    assert report.post_patch_test_passed is True   # Must pass after patch!
    assert report.verification_status is True      # Verified!
    assert report.reverted_or_kept == "kept"

    # Verify file now contains fix
    content = (tmp_path / "ratio_service.py").read_text(encoding="utf-8")
    assert "if not denominator:" in content


# =============================================================================
# 5. Agent & CLI Tests
# =============================================================================


def test_agent_diagnose_and_demo(tmp_path):
    agent = BugAssistantAgent(workspace_root=str(tmp_path))
    assert agent.workspace_root == tmp_path.resolve()

    # Test run_demo
    report = agent.run_demo(demo_workspace_dir=str(tmp_path / "demo_space"))
    assert report.verification_status is True
    assert report.bug_type == "ZeroDivisionError"
    assert "Bug Triage & Verification Report" in report.summary_markdown


def test_cli_demo_invocation():
    # Invoke main.py --demo via subprocess
    pkg_dir = Path(__file__).parent.parent
    cmd = [sys.executable, str(pkg_dir / "main.py"), "--demo"]
    res = subprocess.run(
        cmd,
        cwd=str(pkg_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 0
    assert "AGENT C: MCP TOOLS-BASED BUG ASSISTANT" in res.stdout
    assert "Verification Result: PASSED" in res.stdout


def test_error_handling_invalid_inputs(tmp_path):
    tools = EmbeddedTools(workspace_root=str(tmp_path))

    # Read non-existent file
    with pytest.raises(FileNotFoundError):
        tools.read_file("nonexistent.py")

    # Invalid regex in search
    with pytest.raises(ValueError):
        tools.search_files("[invalid regex", path=str(tmp_path))

    # Call unknown tool
    with pytest.raises(ValueError):
        tools.call_tool("unknown_tool_xyz")

    # Read directory as file
    with pytest.raises(IsADirectoryError):
        tools.read_file(".")


def test_traceback_parser_no_frames():
    raw = "ValueError: unexpected empty payload"
    info = TracebackParser.parse(raw)
    assert info.exception_type == "ValueError"
    assert info.exception_message == "unexpected empty payload"
    assert len(info.frames) == 0
    assert info.primary_frame is None


def test_reproducer_custom_test_code_syntax_error():
    context = BugContext(
        faulty_file="test.py",
        line_number=1,
        function_name="bad",
        code_snippet="bad",
        surrounding_lines=[],
    )
    tb_info = TracebackInfo(raw_text="", exception_type="Error", exception_message="")
    with pytest.raises(SyntaxError):
        synthesize_reproducer(tb_info, context, custom_test_code="def broken_func(:\n pass")


def test_patch_synthesis_key_error_and_index_error():
    # Test KeyError heuristic
    context_key = BugContext(
        faulty_file="store.py",
        line_number=2,
        function_name="lookup",
        code_snippet="return cache[key]",
        surrounding_lines=[(1, "def lookup(cache, key):"), (2, "    return cache[key]")],
    )
    tb_key = TracebackInfo(raw_text="", exception_type="KeyError", exception_message="'user_id'")
    orig_key = "def lookup(cache, key):\n    return cache[key]\n"
    diff_key = synthesize_patch(context_key, tb_key, original_content=orig_key)
    assert "cache.get(key)" in diff_key

    # Test IndexError heuristic
    context_idx = BugContext(
        faulty_file="queue.py",
        line_number=2,
        function_name="get_first",
        code_snippet="return items[0]",
        surrounding_lines=[(1, "def get_first(items):"), (2, "    return items[0]")],
    )
    tb_idx = TracebackInfo(raw_text="", exception_type="IndexError", exception_message="index out of range")
    orig_idx = "def get_first(items):\n    return items[0]\n"
    diff_idx = synthesize_patch(context_idx, tb_idx, original_content=orig_idx)
    assert "len(items)" in diff_idx


def test_cli_stack_trace_from_file_and_json_output(tmp_path):
    pkg_dir = Path(__file__).parent.parent
    trace_file = tmp_path / "crash.txt"
    demo_file = tmp_path / "service.py"
    demo_file.write_text("def run():\n    return 10 / 0\n", encoding="utf-8")

    trace_file.write_text(f"""Traceback (most recent call last):
  File "{demo_file.as_posix()}", line 2, in run
    return 10 / 0
ZeroDivisionError: division by zero
""", encoding="utf-8")

    out_json = tmp_path / "report.json"
    cmd = [
        sys.executable,
        str(pkg_dir / "main.py"),
        "--stack-trace",
        str(trace_file),
        "--repo",
        str(tmp_path),
        "--output",
        str(out_json),
    ]
    res = subprocess.run(cmd, cwd=str(pkg_dir), capture_output=True, text=True, timeout=30)
    assert res.returncode in (0, 1)  # Triage executed and completed
    assert out_json.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["bug_type"] == "ZeroDivisionError"

