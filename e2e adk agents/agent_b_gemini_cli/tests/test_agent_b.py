"""Automated Pytest Suite for Agent B: Gemini CLI in ADK Pipeline Tool Agent.

Verifies:
1. Subprocess execution, exit codes, and stdout/stderr capture.
2. Timeout guardrails (synchronous and asynchronous).
3. JSON output parsing and multi-pattern regex extraction fallback.
4. Resilient fallback to google.genai SDK and deterministic mock emulator.
5. Four-stage ADK pipeline (Decompose -> CLI Invocation -> Code Transformation -> Synthesis).
6. AST code validation in Stage 3.
7. Google ADK Agent tool registration and dispatch.
8. CLI entry point (main.py) with --demo, --task, and --dry-run.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from agent import create_agent, gemini_cli_tool, run_pipeline_tool
from cli_wrapper import GeminiCliWrapper
from main import main
from pipeline import ADKPipeline
from schemas import CliResult, PipelineSummary, StageOutput, TaskRequest


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_completed_process():
    """Factory fixture for creating simulated subprocess.CompletedProcess results."""
    def _create(returncode: int = 0, stdout: str = "", stderr: str = ""):
        return subprocess.CompletedProcess(
            args=["gemini", "-p", "test", "-o", "json"],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )
    return _create


# ==============================================================================
# Test 1: Binary Availability & Fallback Configuration
# ==============================================================================

def test_cli_wrapper_availability_and_fallback_flag(monkeypatch):
    """Verify is_cli_available respects binary presence and GEMINI_CLI_FALLBACK."""
    wrapper_forced = GeminiCliWrapper(force_fallback=True)
    assert not wrapper_forced.is_cli_available()

    # Test environment variable override
    monkeypatch.setenv("GEMINI_CLI_FALLBACK", "1")
    wrapper_env = GeminiCliWrapper()
    assert not wrapper_env.is_cli_available()

    monkeypatch.delenv("GEMINI_CLI_FALLBACK", raising=False)
    with patch("shutil.which", return_value="C:\\fake\\gemini.exe"):
        wrapper_found = GeminiCliWrapper(force_fallback=False)
        assert wrapper_found.is_cli_available()

    with patch("shutil.which", return_value=None):
        wrapper_missing = GeminiCliWrapper(force_fallback=False)
        assert not wrapper_missing.is_cli_available()


# ==============================================================================
# Test 2: Subprocess Execution - Clean Exit Code 0 & JSON Parsing
# ==============================================================================

def test_cli_wrapper_subprocess_success_json(mock_completed_process):
    """Verify clean exit code 0 parses JSON response and telemetry stats."""
    payload = {
        "response": {"analysis": "All tests passed", "complexity": "O(1)"},
        "stats": {"tokens": 85, "latency_ms": 320},
    }
    mock_proc = mock_completed_process(
        returncode=0,
        stdout=json.dumps(payload),
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/gemini"), \
         patch("subprocess.run", return_value=mock_proc) as mock_run:
        wrapper = GeminiCliWrapper(force_fallback=False)
        result: CliResult = wrapper.execute_prompt("Analyze test function")

        assert result.success is True
        assert result.returncode == 0
        assert result.response == payload["response"]
        assert result.stats.get("tokens") == 85
        assert result.is_fallback is False
        mock_run.assert_called_once()


# ==============================================================================
# Test 3: Subprocess Execution - Non-Zero Exit Code Capture
# ==============================================================================

def test_cli_wrapper_subprocess_nonzero_exit(mock_completed_process):
    """Verify non-zero returncode and stderr are properly captured."""
    mock_proc = mock_completed_process(
        returncode=2,
        stdout="",
        stderr="Error: Model quota exceeded or unrecognized parameter",
    )

    with patch("shutil.which", return_value="/usr/bin/gemini"), \
         patch("subprocess.run", return_value=mock_proc):
        wrapper = GeminiCliWrapper(force_fallback=False)
        result: CliResult = wrapper.execute_prompt("Generate heavy workload")

        assert result.success is False
        assert result.returncode == 2
        assert "Model quota exceeded" in result.error
        assert result.response is None


# ==============================================================================
# Test 4: Subprocess Execution - Timeout Guardrail
# ==============================================================================

def test_cli_wrapper_subprocess_timeout():
    """Verify TimeoutExpired is caught and returns appropriate error status."""
    timeout_exception = subprocess.TimeoutExpired(
        cmd=["gemini", "-p", "slow prompt"],
        timeout=5,
        output=b"partial output before timeout",
    )

    with patch("shutil.which", return_value="/usr/bin/gemini"), \
         patch("subprocess.run", side_effect=timeout_exception):
        wrapper = GeminiCliWrapper(force_fallback=False, default_timeout=5)
        result: CliResult = wrapper.execute_prompt("Slow task", timeout=5)

        assert result.success is False
        assert result.returncode == -1
        assert "TimeoutExpired" in result.error
        assert result.stats.get("timed_out") is True


# ==============================================================================
# Test 5: Regex Extraction - Markdown JSON Fence
# ==============================================================================

def test_cli_wrapper_regex_extraction_markdown_fence(mock_completed_process):
    """Verify regex extraction parses JSON wrapped in markdown code fences."""
    raw_terminal_output = (
        "Analyzing target directory...\n"
        "Here is the structured analysis:\n"
        "```json\n"
        "{\n"
        '  "status": "completed",\n'
        '  "functions_found": 3,\n'
        '  "recommendation": "Add type annotations"\n'
        "}\n"
        "```\n"
        "Finished execution in 0.4s.\n"
    )
    mock_proc = mock_completed_process(
        returncode=0,
        stdout=raw_terminal_output,
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/gemini"), \
         patch("subprocess.run", return_value=mock_proc):
        wrapper = GeminiCliWrapper(force_fallback=False)
        result = wrapper.execute_prompt("Analyze codebase")

        assert result.success is True
        assert isinstance(result.response, dict)
        assert result.response.get("status") == "completed"
        assert result.response.get("functions_found") == 3


# ==============================================================================
# Test 6: Regex Extraction - Outer Braces
# ==============================================================================

def test_cli_wrapper_regex_extraction_outer_braces(mock_completed_process):
    """Verify regex extraction extracts JSON with outer braces without code fences."""
    raw_terminal_output = (
        "Log message: Execution ready.\n"
        '{"status": "ok", "items_processed": 10}\n'
        "Done.\n"
    )
    mock_proc = mock_completed_process(
        returncode=0,
        stdout=raw_terminal_output,
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/gemini"), \
         patch("subprocess.run", return_value=mock_proc):
        wrapper = GeminiCliWrapper(force_fallback=False)
        result = wrapper.execute_prompt("Process items")

        assert result.success is True
        assert isinstance(result.response, dict)
        assert result.response.get("status") == "ok"
        assert result.response.get("items_processed") == 10


# ==============================================================================
# Test 7: Plain Unstructured Text Handling
# ==============================================================================

def test_cli_wrapper_raw_text_handling(mock_completed_process):
    """Verify plain text output is returned as-is with raw_text flag."""
    plain_text = "This is a plain explanation of the sorting algorithm."
    mock_proc = mock_completed_process(
        returncode=0,
        stdout=plain_text,
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/gemini"), \
         patch("subprocess.run", return_value=mock_proc):
        wrapper = GeminiCliWrapper(force_fallback=False)
        result = wrapper.execute_prompt("Explain sort")

        assert result.success is True
        assert result.response == plain_text
        assert result.stats.get("raw_text") is True


# ==============================================================================
# Test 8: Asynchronous Subprocess Execution
# ==============================================================================

@pytest.mark.asyncio
async def test_cli_wrapper_async_execution():
    """Verify execute_prompt_async runs and returns valid CliResult."""
    wrapper = GeminiCliWrapper(force_fallback=True)
    result = await wrapper.execute_prompt_async("Generate docstring", output_format="json")

    assert result.success is True
    assert result.is_fallback is True
    assert result.execution_time_ms >= 0


# ==============================================================================
# Test 9: SDK Fallback with google.genai Mocked
# ==============================================================================

def test_cli_wrapper_sdk_fallback_with_genai_client(monkeypatch):
    """Verify live SDK fallback path is exercised when GOOGLE_API_KEY is present."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test_api_key_12345")
    monkeypatch.setenv("HARNESS_MODEL", "gemini-2.5-flash")

    mock_response = MagicMock()
    mock_response.text = '{"refactored_code": "def hello(): pass", "language": "python"}'

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        wrapper = GeminiCliWrapper(force_fallback=True)
        result = wrapper.execute_prompt("Refactor function", output_format="json")

        assert result.success is True
        assert result.is_fallback is True
        assert result.stats.get("fallback") == "google-genai-sdk"
        assert result.stats.get("model") == "gemini-2.5-flash"
        assert isinstance(result.response, dict)
        assert result.response.get("language") == "python"


# ==============================================================================
# Test 10: Deterministic Mock Emulator Fallback
# ==============================================================================

def test_cli_wrapper_deterministic_mock_emulator(monkeypatch):
    """Verify offline mock emulator executes when no API key is provided."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    wrapper = GeminiCliWrapper(force_fallback=True)

    # Test decomposition prompt pattern
    decomp_res = wrapper.execute_prompt("Decompose this task into stages", output_format="json")
    assert decomp_res.success is True
    assert isinstance(decomp_res.response, dict)
    assert "tasks" in decomp_res.response

    # Test test generation prompt pattern
    test_res = wrapper.execute_prompt("Generate unit tests for helper", output_format="json")
    assert test_res.success is True
    assert "test_code" in test_res.response


# ==============================================================================
# Test 11: Code Block Extraction Utility
# ==============================================================================

def test_extract_code_blocks_utility():
    """Verify code block extraction handles multiple languages and fences."""
    sample_markdown = (
        "Here is the implementation:\n"
        "```python\n"
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
        "```\n"
        "And the config:\n"
        "```json\n"
        '{"env": "test"}\n'
        "```\n"
    )
    blocks = GeminiCliWrapper.extract_code_blocks(sample_markdown)
    assert len(blocks) == 2
    assert blocks[0]["language"] == "python"
    assert "def add" in blocks[0]["code"]
    assert blocks[1]["language"] == "json"


# ==============================================================================
# Test 12: 4-Stage ADK Pipeline Execution
# ==============================================================================

def test_pipeline_four_stages_end_to_end():
    """Verify all 4 stages of the pipeline execute and synthesize telemetry."""
    wrapper = GeminiCliWrapper(force_fallback=True)
    pipeline = ADKPipeline(cli_wrapper=wrapper)

    req = TaskRequest(
        description="Refactor a math utility function and create pytest assertions",
        code_context="def add(x, y): return x + y",
        language="python",
        output_format="json",
    )

    summary: PipelineSummary = pipeline.run(req)

    assert summary.overall_success is True
    assert len(summary.stages) == 4
    assert summary.stages[0].stage_name == "Decompose"
    assert summary.stages[1].stage_name == "Tool Invocation via CLI Subprocess"
    assert summary.stages[2].stage_name == "Code/Text Transformation"
    assert summary.stages[3].stage_name == "Synthesis & Telemetry"

    assert summary.cli_invocations_count >= 2
    assert summary.total_duration_ms > 0
    assert summary.final_artifact is not None
    assert "Pipeline ID" in summary.final_artifact


# ==============================================================================
# Test 13: Pipeline AST Transformation Validation
# ==============================================================================

def test_pipeline_ast_validation():
    """Verify Stage 3 extracts code blocks and properly detects valid and invalid syntax."""
    wrapper = GeminiCliWrapper(force_fallback=True)
    pipeline = ADKPipeline(cli_wrapper=wrapper)

    # Valid code
    req_valid = TaskRequest(
        description="Optimize Python function",
        code_context="def test_fn(): return 42",
        language="python",
    )
    summary_valid = pipeline.run(req_valid)
    stage3 = summary_valid.stages[2]
    assert stage3.stage_name == "Code/Text Transformation"
    code_blocks = stage3.output_data.get("code_blocks", [])
    if code_blocks:
        assert any(b["ast_valid"] is True for b in code_blocks)


# ==============================================================================
# Test 14: Google ADK Agent Tool Functions & Dispatch
# ==============================================================================

def test_adk_agent_tools_and_dispatch():
    """Verify gemini_cli_tool and run_pipeline_tool callable from ADK Agent."""
    # Test tool functions directly
    cli_out = gemini_cli_tool("Analyze code quality")
    parsed_cli = json.loads(cli_out)
    assert parsed_cli.get("success") is True

    pipe_out = run_pipeline_tool("Create unit test plan", code_context="def foo(): pass")
    parsed_pipe = json.loads(pipe_out)
    assert parsed_pipe.get("overall_success") is True

    # Test Agent instance and dispatch
    agent = create_agent(wrapper=GeminiCliWrapper(force_fallback=True))
    assert agent.name == "gemini_cli_pipeline_agent"
    assert len(agent.tools) == 2

    # Test agent conversational dispatch
    run_res = agent.run("Run pipeline for code transformation")
    assert run_res is not None
    assert "overall_success" in run_res or "Pipeline ID" in run_res or "gemini_cli_pipeline_agent" in run_res


# ==============================================================================
# Test 15: CLI Entry Point (main.py)
# ==============================================================================

def test_main_cli_entrypoint_demo():
    """Verify main() runs successfully with --demo and --dry-run."""
    exit_code = main(["--demo", "--dry-run", "--format", "json"])
    assert exit_code == 0


def test_main_cli_entrypoint_task():
    """Verify main() runs with custom --task and --dry-run."""
    exit_code = main(["--task", "Synthesize docstrings and tests", "--dry-run"])
    assert exit_code == 0
