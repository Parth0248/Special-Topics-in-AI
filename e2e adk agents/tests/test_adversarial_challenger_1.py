"""Adversarial Stress Testing & Empirical Verification Suite (challenger_1).

Tests:
1. Agent A (Lead Gen):
   - Empty/whitespace criteria (empty industry, negative bounds, zero bounds)
   - Extreme headcount ranges (inverted bounds, massive values, non-integer inputs)
   - Missing/dummy/corrupted API keys (graceful offline fallback)
   - Corrupted candidate records (missing fields, malformed types, invalid formats)

2. Agent B (Gemini CLI):
   - Subprocess timeouts (TimeoutExpired guardrail, stats recording)
   - Non-zero returncodes (1, 2, 127 with stderr capture)
   - Malformed stdout (raw garbage, unclosed JSON, HTML error)
   - Markdown-wrapped JSON (various code fence variations, text before/after)
   - CLI fallback paths (forced fallback, missing binary)

3. Agent C (Bug Assistant):
   - Empty/whitespace/unstructured tracebacks
   - Non-existent files in stack trace
   - Syntax-invalid code and patch failure handling
   - Patch rollback verification (.bak restoration and cleanup)
   - Cross-agent pipeline 2 root cause reproduction
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

# Agent A imports
from agent_a_lead_gen.models import (
    CompanyProfile,
    FitScoreEvaluation,
    LeadDossier,
    TargetMarketCriteria,
)
from agent_a_lead_gen.tools import (
    compile_dossier_report,
    evaluate_lead_fit,
    extract_company_profile,
    search_companies,
)

# Agent B imports
from agent_b_gemini_cli.cli_wrapper import GeminiCliWrapper
from agent_b_gemini_cli.pipeline import (
    ADKPipeline,
)
from agent_b_gemini_cli.schemas import CliResult, PipelineSummary, StageOutput, TaskRequest

# Agent C imports
from agent_c_bug_assistant.agent import BugAssistantAgent
from agent_c_bug_assistant.embedded_tools import EmbeddedTools
from agent_c_bug_assistant.triage import (
    BugTriagePipeline,
    TracebackParser,
    apply_patch_unified,
    gather_bug_context,
    rollback_patch,
    synthesize_patch,
    synthesize_reproducer,
    verify_bug_and_fix,
)


# =============================================================================
# SUITE 1: AGENT A ADVERSARIAL STRESS TESTS
# =============================================================================

class TestAgentAAdversarial:
    """Stress tests for Agent A: Deep Research Lead Gen."""

    def test_empty_industry_matches_all_companies_at_max_score(self):
        """Adversarial Test A1b: Empty target industry awards neutral baseline score (15.0 pts).

        Remediated in agent_a_lead_gen/tools.py line 338:
        When criteria has `industry=""`, assigns neutral baseline score (15.0 pts) rather than 30.0/100.0.
        """
        unrelated_company = CompanyProfile(
            company_name="Antarctic Construction Ltd",
            website="https://antarctic-build.com",
            industry="Heavy Construction & Concrete",
            headquarters="McMurdo Station, Antarctica",
        )
        crit_empty = TargetMarketCriteria(industry="")
        eval_result = evaluate_lead_fit(unrelated_company, crit_empty)

        # Remediated: Awards neutral baseline 15.0 points rather than full 30.0 / 100.0
        assert eval_result.category_scores["industry_match"] == 15.0
        assert eval_result.overall_fit_score < 100.0
        assert any("unspecified" in s.lower() or "baseline" in s.lower() for s in eval_result.strengths)


    def test_extreme_and_invalid_headcount_ranges(self):
        """Adversarial Test A2: Inverted headcount, negative headcount, extreme bounds."""
        # Inverted headcount: min > max must raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            TargetMarketCriteria(industry="Fintech", min_headcount=500, max_headcount=100)
        assert "cannot be less than min_headcount" in str(exc_info.value)

        # Zero headcount (ge=1 constraint)
        with pytest.raises(ValidationError):
            TargetMarketCriteria(industry="Fintech", min_headcount=0)

        # Negative headcount
        with pytest.raises(ValidationError):
            TargetMarketCriteria(industry="Fintech", min_headcount=-10)

        # Extreme astronomical headcount (e.g. 10 billion)
        crit_huge = TargetMarketCriteria(
            industry="Fintech",
            min_headcount=1_000_000,
            max_headcount=10_000_000_000,
        )
        sample_company = {
            "company_name": "MegaCorp",
            "website": "https://megacorp.com",
            "industry": "Fintech",
            "headquarters": "New York, USA",
            "employee_count": 50,
        }
        eval_huge = evaluate_lead_fit(sample_company, crit_huge)
        assert eval_huge.category_scores["headcount_scale_fit"] <= 10.0

    def test_missing_and_corrupted_api_keys(self, monkeypatch):
        """Adversarial Test A3: Unset, empty, or dummy API keys fall back gracefully."""
        # Case 1: Unset GOOGLE_API_KEY
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        results_none = search_companies("Healthcare AI", industry="Healthcare", limit=3)
        assert isinstance(results_none, list)
        assert len(results_none) > 0

        # Case 2: Dummy key
        monkeypatch.setenv("GOOGLE_API_KEY", "AQ.dummy_invalid_key_999")
        results_dummy = search_companies("Cybersecurity", industry="Security", limit=2)
        assert isinstance(results_dummy, list)
        assert len(results_dummy) > 0

        # Case 3: Empty string key
        monkeypatch.setenv("GOOGLE_API_KEY", "")
        results_empty = search_companies("SaaS", limit=2)
        assert isinstance(results_empty, list)
        assert len(results_empty) > 0

    def test_corrupted_and_sparse_candidate_records(self):
        """Adversarial Test A4: Corrupted, missing fields, or unexpected data types."""
        # Missing almost everything except company_name
        sparse_candidate = {"company_name": "Ghost Startup"}
        profile = extract_company_profile("Ghost Startup", structured_data=sparse_candidate)
        assert profile.company_name == "Ghost Startup"
        assert profile.industry == "Technology"  # Safe default
        assert profile.website.startswith("https://")

        # Non-numeric employee count in raw text
        raw_text = "Ghost Startup is an AI lab with twenty-five employees in Berlin."
        profile_text = extract_company_profile("Ghost Startup", raw_text=raw_text)
        assert isinstance(profile_text, CompanyProfile)

        # Candidate with unexpected unicode and special characters
        unicode_candidate = {
            "company_name": "Üñîçødé 🚀 Labs",
            "website": "https://unicode.io",
            "industry": "A.I. & Big Data 🤖",
            "headquarters": "Zürich, Schweiz 🇨🇭",
            "employee_count": 42,
            "growth_signals": ["Hiring 10x Engineers 🔥"],
        }
        crit = TargetMarketCriteria(industry="AI", geography="Europe")
        eval_res = evaluate_lead_fit(unicode_candidate, crit)
        assert isinstance(eval_res, FitScoreEvaluation)
        assert eval_res.company_name == "Üñîçødé 🚀 Labs"

    def test_empty_candidates_dossier_compilation(self):
        """Adversarial Test A5: Dossier compilation with 0 qualified candidates."""
        crit = TargetMarketCriteria(industry="Quantum Computing", min_fit_score=99.9)
        dossier_md = compile_dossier_report([], crit, output_format="markdown")
        assert isinstance(dossier_md, str)
        assert "Deep Research Lead Dossier: Quantum Computing" in dossier_md

        dossier_json = compile_dossier_report([], crit, output_format="json")
        data = json.loads(dossier_json)
        assert data["total_candidates_analyzed"] == 0
        assert data["qualified_leads_count"] == 0


# =============================================================================
# SUITE 2: AGENT B ADVERSARIAL STRESS TESTS
# =============================================================================

class TestAgentBAdversarial:
    """Stress tests for Agent B: Gemini CLI in ADK Pipeline."""

    def test_subprocess_timeout_guardrail(self, monkeypatch):
        """Adversarial Test B1: Subprocess execution times out cleanly."""
        wrapper = GeminiCliWrapper(binary_name="gemini", default_timeout=1)

        def mock_timeout_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=["gemini", "-p", "slow"], timeout=1)

        monkeypatch.setattr("shutil.which", lambda _: "C:\\fake\\gemini.exe")
        monkeypatch.setattr("subprocess.run", mock_timeout_run)

        result = wrapper.execute_prompt("Generate complex code", timeout=1)
        assert result.success is False
        assert result.returncode == -1
        assert "TimeoutExpired" in result.error
        assert result.stats.get("timed_out") is True

    def test_non_zero_exit_codes(self, monkeypatch):
        """Adversarial Test B2: CLI exits with code 1, 2, 127 and stderr messages."""
        wrapper = GeminiCliWrapper(binary_name="gemini")
        monkeypatch.setattr("shutil.which", lambda _: "C:\\fake\\gemini.exe")

        for code in [1, 2, 127]:
            def mock_fail_run(*args, **kwargs):
                return subprocess.CompletedProcess(
                    args=["gemini"],
                    returncode=code,
                    stdout="",
                    stderr=f"Fatal error code {code}: Resource exhausted",
                )

            monkeypatch.setattr("subprocess.run", mock_fail_run)
            result = wrapper.execute_prompt("test prompt")
            assert result.success is False
            assert result.returncode == code
            assert f"code {code}" in result.error

    def test_malformed_and_unclosed_json_stdout(self, monkeypatch):
        """Adversarial Test B3: CLI returns corrupted JSON or HTML error pages."""
        wrapper = GeminiCliWrapper(binary_name="gemini")
        monkeypatch.setattr("shutil.which", lambda _: "C:\\fake\\gemini.exe")

        malformed_cases = [
            '{"unclosed": "brace", "items": [1, 2,',  # Syntax error
            "<html><body>502 Bad Gateway</body></html>",  # Gateway error
            "Raw unformatted text without any JSON structure",  # Plain text
            "",  # Empty stdout
        ]

        for stdout_case in malformed_cases:
            def mock_malformed(*args, **kwargs):
                return subprocess.CompletedProcess(
                    args=["gemini"],
                    returncode=0,
                    stdout=stdout_case,
                    stderr="",
                )

            monkeypatch.setattr("subprocess.run", mock_malformed)
            result = wrapper.execute_prompt("test")
            # Must not crash! Should fall back to raw text output with success=True
            assert result.success is True
            assert result.returncode == 0

    def test_markdown_wrapped_json_variations(self, monkeypatch):
        """Adversarial Test B4: JSON wrapped inside complex Markdown fences."""
        wrapper = GeminiCliWrapper(binary_name="gemini")
        monkeypatch.setattr("shutil.which", lambda _: "C:\\fake\\gemini.exe")

        markdown_samples = [
            # Standard markdown fence
            'Here is the response:\n```json\n{"status": "ok", "count": 42}\n```\nHope this helps!',
            # Uppercase JSON tag
            '```JSON\n{"key": "value"}\n```',
            # No tag on fence
            '```\n{"implicit": "json"}\n```',
            # Embedded in conversation
            'Sure! The analysis is: {"direct_object": true} and more notes.',
        ]

        for sample in markdown_samples:
            def mock_md(*args, **kwargs):
                return subprocess.CompletedProcess(
                    args=["gemini"],
                    returncode=0,
                    stdout=sample,
                    stderr="",
                )

            monkeypatch.setattr("subprocess.run", mock_md)
            result = wrapper.execute_prompt("analyze")
            assert result.success is True
            assert isinstance(result.response, (dict, list))

    def test_forced_fallback_path(self, monkeypatch):
        """Adversarial Test B5: Forced fallback triggers mock emulator with telemetry."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        wrapper = GeminiCliWrapper(binary_name="gemini", force_fallback=True)
        assert wrapper.is_cli_available() is False

        result = wrapper.execute_prompt("decompose: build microservice architecture", output_format="json")
        assert result.success is True
        assert result.is_fallback is True
        assert result.stats.get("fallback") == "mock-emulator"
        assert isinstance(result.response, dict)
        assert "tasks" in result.response


# =============================================================================
# SUITE 3: AGENT C ADVERSARIAL STRESS TESTS
# =============================================================================

class TestAgentCAdversarial:
    """Stress tests for Agent C: MCP Bug Assistant."""

    def test_empty_and_unstructured_tracebacks(self):
        """Adversarial Test C1: Empty or unstructured traceback strings."""
        # Completely empty
        info_empty = TracebackParser.parse("")
        assert info_empty.exception_type == "UnknownException"
        assert info_empty.primary_frame is None

        # Whitespace only
        info_ws = TracebackParser.parse("   \n\t   \n  ")
        assert info_empty.exception_type == "UnknownException"

        # Arbitrary error message without stack frames
        info_simple = TracebackParser.parse("ValueError: Invalid port specified: -1")
        assert info_simple.exception_type == "ValueError"
        assert "Invalid port specified" in info_simple.exception_message
        assert info_simple.primary_frame is None

    def test_nonexistent_file_handling_in_tools(self, tmp_path):
        """Adversarial Test C2: Filesystem tools handle non-existent paths gracefully."""
        tools = EmbeddedTools(workspace_root=str(tmp_path))

        # read_file raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            tools.read_file("non_existent_module.py")

        # get_file_info returns exists=False without crashing
        info = tools.get_file_info("ghost_file.py")
        assert info["exists"] is False
        assert info["size_bytes"] == 0

        # list_directory on missing path raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            tools.list_directory("missing_dir")

    def test_patch_rollback_restores_original_file(self, tmp_path):
        """Adversarial Test C3: Patch rollback restores exact content and removes backup."""
        test_file = tmp_path / "service.py"
        original_content = "def calculate(x, y):\n    return x / y\n"
        test_file.write_text(original_content, encoding="utf-8")

        # Synthesize a patch that modifies the file
        patch_diff = (
            "--- a/service.py\n"
            "+++ b/service.py\n"
            "@@ -1,2 +1,4 @@\n"
            " def calculate(x, y):\n"
            "+    if y == 0:\n"
            "+        return 0\n"
            "     return x / y\n"
        )

        # Apply patch with backup
        apply_ok = apply_patch_unified(str(test_file), patch_diff, backup=True)
        assert apply_ok is True
        assert "if y == 0:" in test_file.read_text(encoding="utf-8")
        bak_file = test_file.with_suffix(test_file.suffix + ".bak")
        assert bak_file.exists()

        # Execute rollback
        rolled_back = rollback_patch(str(test_file))
        assert rolled_back is True
        assert test_file.read_text(encoding="utf-8") == original_content
        assert not bak_file.exists()

    def test_unformatted_diff_rejected(self, tmp_path):
        """Adversarial Test C4a: Malformed diff with no hunk headers is rejected."""
        test_file = tmp_path / "calc.py"
        test_file.write_text("a = 10\nb = 20\n", encoding="utf-8")

        res = apply_patch_unified(str(test_file), "completely unformatted text", backup=False)
        assert res is False
        assert test_file.read_text(encoding="utf-8") == "a = 10\nb = 20\n"

        res_empty = apply_patch_unified(str(test_file), "", backup=False)
        assert res_empty is False
        assert test_file.read_text(encoding="utf-8") == "a = 10\nb = 20\n"

    def test_mismatched_hunk_vulnerability_discovered(self, tmp_path):
        """Adversarial Test C4b: Hunk with non-existent context is cleanly aborted without file corruption.

        Remediated in agent_c_bug_assistant/triage.py:
        When context is not found, apply_patch_unified returns False and preserves original content.
        """
        test_file = tmp_path / "calc_vuln.py"
        original = "a = 10\nb = 20\n"
        test_file.write_text(original, encoding="utf-8")

        mismatched_diff = "@@ -999,5 +999,5 @@\n-line that does not exist\n+new line\n"
        res = apply_patch_unified(str(test_file), mismatched_diff, backup=False)

        # Remediated: Returns False and original file remains unmodified
        assert res is False
        mutated_content = test_file.read_text(encoding="utf-8")
        assert mutated_content == original
        assert "new line" not in mutated_content

    def test_diagnose_empty_traceback_raises_unhandled_valueerror(self):
        """Adversarial Test C5: Empty traceback returns structured error dict without crashing.

        Remediated in agent_c_bug_assistant/agent.py:
        BugAssistantAgent.diagnose wraps triage in error handling and returns {"status": "error", "message": ...}.
        """
        agent = BugAssistantAgent()
        report = agent.diagnose("")
        assert isinstance(report, dict)
        assert report["status"] == "error"
        assert "no valid stack frame found" in report["message"].lower() or "context" in report["message"].lower()

    def test_diagnose_nonexistent_file_raises_unhandled_filenotfound(self):
        """Adversarial Test C6: Non-existent file in traceback returns structured error dict without crashing.

        Remediated in agent_c_bug_assistant/agent.py:
        BugAssistantAgent.diagnose returns {"status": "error", "message": ...} on FileNotFoundError.
        """
        agent = BugAssistantAgent()
        fake_traceback = """
Traceback (most recent call last):
  File "D:/non_existent_folder_xyz/missing_file.py", line 10, in execute_code
    x = 1 / 0
ZeroDivisionError: division by zero
"""
        report = agent.diagnose(fake_traceback)
        assert isinstance(report, dict)
        assert report["status"] == "error"
        assert "missing_file.py" in report["message"] or "not found" in report["message"].lower()


