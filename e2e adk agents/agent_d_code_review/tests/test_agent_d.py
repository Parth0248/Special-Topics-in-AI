"""Automated Pytest Suite for Agent D: Production-Quality Code Review Assistant.

Verifies:
  - StateKeys and Severity constants
  - AST structural analysis and McCabe cyclomatic complexity
  - PEP 8 compliance checking and weighted scoring (0-100)
  - OWASP Top 10 / CWE security vulnerability scanning (CWE-89, 78, 502, 22, 798, 327)
  - Unified git diff parsing and line mapping
  - Structured Markdown feedback synthesizer
  - Iterative fix loop (LoopAgent pattern) and validation gates
  - Top-level ADK Agent integration and CLI execution
"""

import os
import sys
import tempfile
import pytest

# Ensure parent package is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from agent_d_code_review.constants import StateKeys, Severity, CWE_DEFINITIONS
    from agent_d_code_review.models import (
        CodeReviewReport,
        CodeReviewRequest,
        SecurityFinding,
        StyleViolation,
        StructureMetrics,
        LineComment,
    )
    from agent_d_code_review.tools import (
        ToolContext,
        analyze_code_structure,
        check_code_style,
        scan_security_vulnerabilities,
        parse_git_diff,
        feedback_synthesizer,
    )
    from agent_d_code_review.reviewer import CodeReviewer
    from agent_d_code_review.fix_pipeline import code_fixer, fix_validator, CodeFixLoopAgent
    from agent_d_code_review.agent import CodeReviewAssistantAgent, create_agent
    from agent_d_code_review.main import main, DEMO_VULNERABLE_CODE
except ImportError:
    from constants import StateKeys, Severity, CWE_DEFINITIONS
    from models import (
        CodeReviewReport,
        CodeReviewRequest,
        SecurityFinding,
        StyleViolation,
        StructureMetrics,
        LineComment,
    )
    from tools import (
        ToolContext,
        analyze_code_structure,
        check_code_style,
        scan_security_vulnerabilities,
        parse_git_diff,
        feedback_synthesizer,
    )
    from reviewer import CodeReviewer
    from fix_pipeline import code_fixer, fix_validator, CodeFixLoopAgent
    from agent import CodeReviewAssistantAgent, create_agent
    from main import main, DEMO_VULNERABLE_CODE


# ---------------------------------------------------------------------------
# Test Fixtures & Sample Snippets
# ---------------------------------------------------------------------------

CLEAN_CODE_SAMPLE = '''"""Module containing clean math utility functions."""

def calculate_square(num: int) -> int:
    """Calculate the square of a given integer.

    Args:
        num: Input integer.

    Returns:
        Square of input.
    """
    return num * num


class Calculator:
    """Simple calculator class."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
'''

HIGH_COMPLEXITY_CODE = '''def complex_decision_tree(a, b, c, d, e):
    result = 0
    if a > 0:
        if b > 0:
            result += 1
        elif c > 0:
            result += 2
        else:
            result += 3
    elif a < 0:
        if d > 0:
            result += 4
        elif e > 0:
            result += 5
        else:
            result += 6
    while b > 0 and c > 0 and d > 0:
        b -= 1
        for i in range(10):
            if i % 2 == 0:
                result += i
    return result
'''

SYNTAX_ERROR_CODE = '''def broken_function(:
    print("Syntax error here"
'''


# ---------------------------------------------------------------------------
# 1. Constants & Model Tests
# ---------------------------------------------------------------------------

def test_constants_state_keys():
    """Verify all required StateKeys are present and properly typed."""
    assert StateKeys.CODE_TO_REVIEW == "code_to_review"
    assert StateKeys.CODE_ANALYSIS == "code_analysis"
    assert StateKeys.STYLE_SCORE == "style_score"
    assert StateKeys.STYLE_VIOLATIONS == "style_violations"
    assert StateKeys.SECURITY_FINDINGS == "security_findings"
    assert StateKeys.GIT_DIFF == "git_diff"
    assert StateKeys.PR_DESCRIPTION == "pr_description"
    assert StateKeys.FEEDBACK_REPORT == "feedback_report"
    assert StateKeys.FIXED_CODE == "fixed_code"
    assert StateKeys.VALIDATION_PASSED == "validation_passed"


def test_constants_severity_and_cwe():
    """Verify 4-tier severity levels and CWE metadata mappings."""
    assert Severity.CRITICAL.value == "CRITICAL"
    assert Severity.HIGH.value == "HIGH"
    assert Severity.MEDIUM.value == "MEDIUM"
    assert Severity.LOW.value == "LOW"

    # Check key CWE entries
    assert "CWE-89" in CWE_DEFINITIONS
    assert CWE_DEFINITIONS["CWE-89"]["default_severity"] == Severity.CRITICAL
    assert "CWE-78" in CWE_DEFINITIONS
    assert CWE_DEFINITIONS["CWE-78"]["default_severity"] == Severity.CRITICAL
    assert "CWE-502" in CWE_DEFINITIONS
    assert CWE_DEFINITIONS["CWE-502"]["default_severity"] == Severity.CRITICAL
    assert "CWE-22" in CWE_DEFINITIONS
    assert CWE_DEFINITIONS["CWE-22"]["default_severity"] == Severity.HIGH
    assert "CWE-798" in CWE_DEFINITIONS
    assert CWE_DEFINITIONS["CWE-798"]["default_severity"] == Severity.HIGH
    assert "CWE-327" in CWE_DEFINITIONS
    assert CWE_DEFINITIONS["CWE-327"]["default_severity"] == Severity.HIGH


def test_models_to_dict():
    """Verify data model serialization to dict."""
    finding = SecurityFinding(
        cwe_id="CWE-89",
        name="SQLi",
        severity=Severity.CRITICAL,
        line_number=12,
        snippet="cursor.execute(f'...{x}')",
        message="SQL Injection detected",
        recommendation="Use parameterized queries",
        owasp="A03:2021",
    )
    d = finding.to_dict()
    assert d["cwe_id"] == "CWE-89"
    assert d["severity"] == "CRITICAL"
    assert d["line_number"] == 12


# ---------------------------------------------------------------------------
# 2. AST Structure Analysis Tests
# ---------------------------------------------------------------------------

def test_analyze_code_structure_clean():
    """Verify AST parsing extracts functions, classes, complexity, and docstrings."""
    context = ToolContext()
    result = analyze_code_structure(CLEAN_CODE_SAMPLE, context)

    assert result["syntax_valid"] is True
    assert result["functions_count"] == 2  # calculate_square and Calculator.add
    assert result["classes_count"] == 1
    assert result["docstring_coverage"] == 100.0
    assert result["max_complexity"] >= 1
    assert context.get(StateKeys.CODE_ANALYSIS) == result


def test_analyze_code_structure_high_complexity():
    """Verify McCabe cyclomatic complexity flags functions > 10."""
    result = analyze_code_structure(HIGH_COMPLEXITY_CODE)
    assert result["syntax_valid"] is True
    assert result["max_complexity"] > 10
    assert len(result["high_complexity_functions"]) > 0
    assert "complex_decision_tree" in result["high_complexity_functions"][0]


def test_analyze_code_structure_syntax_error():
    """Verify graceful handling of Python syntax errors."""
    result = analyze_code_structure(SYNTAX_ERROR_CODE)
    assert result["syntax_valid"] is False
    assert result["syntax_error"] is not None
    assert "Line" in result["syntax_error"]


def test_analyze_code_structure_empty():
    """Verify empty input handling."""
    result = analyze_code_structure("")
    assert result["syntax_valid"] is True
    assert result["functions_count"] == 0
    assert result["total_loc"] == 0


# ---------------------------------------------------------------------------
# 3. PEP 8 Code Style Checking Tests
# ---------------------------------------------------------------------------

def test_check_code_style_clean():
    """Verify clean code receives a high PEP 8 score."""
    res = check_code_style(CLEAN_CODE_SAMPLE)
    assert res["score"] >= 95.0
    assert len(res["violations"]) == 0


def test_check_code_style_violations():
    """Verify detection of PEP 8 violations (None/Bool compare, bare except, naming)."""
    bad_style_code = '''def BadFunctionName(a, b):
    if a == None:
        return None
    if b == True:
        return 1
    try:
        x = 1 / 0
    except:
        pass
'''
    res = check_code_style(bad_style_code)
    codes = [v["code"] for v in res["violations"]]
    assert "E711" in codes  # comparison to None
    assert "E712" in codes  # comparison to True
    assert "E722" in codes  # bare except
    assert "N802" in codes  # bad function name (camelCase)
    assert res["score"] < 80.0


def test_check_code_style_line_length_and_tabs():
    """Verify detection of line length (E501) and tabs (W191)."""
    long_line_code = "x = '" + "A" * 100 + "'\n\tprint(x)\n"
    res = check_code_style(long_line_code)
    codes = [v["code"] for v in res["violations"]]
    assert "E501" in codes
    assert "W191" in codes


# ---------------------------------------------------------------------------
# 4. Security Vulnerability Scanner Tests
# ---------------------------------------------------------------------------

def test_security_sqli_detection():
    """Verify CWE-89 SQL Injection detection via f-strings and string formatting."""
    sqli_code = '''def get_user(cursor, username):
    cursor.execute(f"SELECT * FROM users WHERE user = '{username}'")
'''
    findings = scan_security_vulnerabilities(sqli_code)
    cwe_ids = [f["cwe_id"] for f in findings]
    assert "CWE-89" in cwe_ids
    sqli = next(f for f in findings if f["cwe_id"] == "CWE-89")
    assert sqli["severity"] == Severity.CRITICAL.value
    assert "SQL" in sqli["message"]


def test_security_command_injection_detection():
    """Verify CWE-78 Command Injection detection in subprocess with shell=True and os.system."""
    cmd_code = '''import subprocess
import os

def ping(host):
    os.system("ping " + host)
    subprocess.run(f"echo {host}", shell=True)
'''
    findings = scan_security_vulnerabilities(cmd_code)
    cwe_ids = [f["cwe_id"] for f in findings]
    assert "CWE-78" in cwe_ids
    cmd_findings = [f for f in findings if f["cwe_id"] == "CWE-78"]
    assert len(cmd_findings) >= 2


def test_security_deserialization_detection():
    """Verify CWE-502 Insecure Deserialization detection in pickle and unsafe yaml."""
    deser_code = '''import pickle
import yaml

def load_payload(raw_data):
    data = pickle.loads(raw_data)
    cfg = yaml.load(raw_data)
'''
    findings = scan_security_vulnerabilities(deser_code)
    cwe_ids = [f["cwe_id"] for f in findings]
    assert "CWE-502" in cwe_ids
    deser_findings = [f for f in findings if f["cwe_id"] == "CWE-502"]
    assert len(deser_findings) >= 2
    assert all(f["severity"] == Severity.CRITICAL.value for f in deser_findings)


def test_security_hardcoded_secrets_detection():
    """Verify CWE-798 Hardcoded Credentials detection."""
    secret_code = '''API_KEY = "AIzaSyD_SECRET_PROD_KEY_12345678"
password = "SuperSecretPassword123!"
'''
    findings = scan_security_vulnerabilities(secret_code)
    cwe_ids = [f["cwe_id"] for f in findings]
    assert "CWE-798" in cwe_ids
    assert all(f["severity"] == Severity.HIGH.value for f in findings if f["cwe_id"] == "CWE-798")


def test_security_weak_crypto_detection():
    """Verify CWE-327 Weak Cryptographic Algorithm detection (MD5, SHA1)."""
    crypto_code = '''import hashlib

def hash_pw(pw):
    return hashlib.md5(pw.encode()).hexdigest()
'''
    findings = scan_security_vulnerabilities(crypto_code)
    cwe_ids = [f["cwe_id"] for f in findings]
    assert "CWE-327" in cwe_ids
    crypto_finding = next(f for f in findings if f["cwe_id"] == "CWE-327")
    assert crypto_finding["severity"] == Severity.HIGH.value


def test_security_path_traversal_detection():
    """Verify CWE-22 Path Traversal detection."""
    path_code = '''def read_user_file(base_dir, user_file):
    with open(f"{base_dir}/{user_file}", "r") as f:
        return f.read()
'''
    findings = scan_security_vulnerabilities(path_code)
    cwe_ids = [f["cwe_id"] for f in findings]
    assert "CWE-22" in cwe_ids


def test_security_clean_code():
    """Verify clean code produces no security findings."""
    findings = scan_security_vulnerabilities(CLEAN_CODE_SAMPLE)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# 5. Git Diff Parser Tests
# ---------------------------------------------------------------------------

SAMPLE_GIT_DIFF = """diff --git a/auth.py b/auth.py
index e69de29..d95f3ad 100644
--- a/auth.py
+++ b/auth.py
@@ -1,5 +1,7 @@
 import os
+import hashlib
 
 def authenticate(user, password):
-    return user == "admin"
+    hashed = hashlib.sha256(password.encode()).hexdigest()
+    return hashed == "target"
"""


def test_parse_git_diff_hunks_and_lines():
    """Verify unified git diff parser extracts file paths, hunks, and line mappings."""
    context = ToolContext()
    diffs = parse_git_diff(SAMPLE_GIT_DIFF, context)

    assert len(diffs) == 1
    file_diff = diffs[0]
    assert file_diff["old_file"] == "auth.py"
    assert file_diff["new_file"] == "auth.py"
    assert file_diff["stats"]["additions"] == 3
    assert file_diff["stats"]["deletions"] == 1
    assert 2 in file_diff["modified_lines"]  # import hashlib line
    assert len(file_diff["hunks"]) == 1
    assert context.get(StateKeys.GIT_DIFF) == diffs


def test_parse_git_diff_empty():
    """Verify empty diff produces empty list."""
    assert parse_git_diff("") == []


# ---------------------------------------------------------------------------
# 6. Feedback Synthesizer Tests
# ---------------------------------------------------------------------------

def test_feedback_synthesizer_generation():
    """Verify feedback synthesizer generates a complete Markdown report with severity counts."""
    context = ToolContext()
    analyze_code_structure(DEMO_VULNERABLE_CODE, context)
    check_code_style(DEMO_VULNERABLE_CODE, context)
    scan_security_vulnerabilities(DEMO_VULNERABLE_CODE, context)

    report_md = feedback_synthesizer(context, pr_description="Add user authentication")

    assert "# Automated Code Review Report" in report_md
    assert "CHANGES REQUESTED" in report_md
    assert "## Executive Summary" in report_md
    assert "## Severity Breakdown" in report_md
    assert "CWE-89" in report_md
    assert "CWE-78" in report_md
    assert "Score:" in report_md
    assert context.get(StateKeys.FEEDBACK_REPORT) == report_md


# ---------------------------------------------------------------------------
# 7. Fix Pipeline and LoopAgent Tests
# ---------------------------------------------------------------------------

def test_code_fixer_remediations():
    """Verify code_fixer applies surgical fixes to style and security flaws."""
    fixed = code_fixer(DEMO_VULNERABLE_CODE)

    # 1. Bare except fixed
    assert "except:" not in fixed
    assert "except Exception as err:" in fixed

    # 2. == None fixed
    assert "== None" not in fixed
    assert "is None" in fixed

    # 3. == True fixed
    assert "== True" not in fixed

    # 4. Weak crypto upgraded to sha256
    assert "hashlib.md5" not in fixed
    assert "hashlib.sha256" in fixed

    # 5. Secret extracted to os.getenv
    assert "os.getenv(\"API_KEY" in fixed

    # 6. Valid syntax maintained
    compile(fixed, "<string>", "exec")


def test_fix_validator_gate():
    """Verify fix_validator checks syntax, vulnerability reduction, and style improvements."""
    fixed = code_fixer(DEMO_VULNERABLE_CODE)
    val = fix_validator(DEMO_VULNERABLE_CODE, fixed)

    assert val["syntax_valid"] is True
    assert val["validation_passed"] is True
    assert val["critical_remaining"] == 0
    assert val["style_score_after"] > val["style_score_before"]


def test_code_fix_loop_agent_execution():
    """Verify CodeFixLoopAgent executes up to max_iterations and terminates upon passing."""
    loop_agent = CodeFixLoopAgent(max_iterations=3)
    results = loop_agent.run(DEMO_VULNERABLE_CODE)

    assert results["validation_passed"] is True
    assert results["iterations"] >= 1
    assert results["iterations"] <= 3
    assert results["final_score"] >= results["initial_score"]
    assert "fixed_code" in results
    compile(results["fixed_code"], "<string>", "exec")


# ---------------------------------------------------------------------------
# 8. Top-Level Agent D Integration & CLI Tests
# ---------------------------------------------------------------------------

def test_code_review_assistant_agent_end_to_end():
    """Verify CodeReviewAssistantAgent review and auto-fix capabilities."""
    agent = create_agent(max_fix_iterations=2)

    # Review flawed sample
    report = agent.review(code=DEMO_VULNERABLE_CODE)
    assert isinstance(report, CodeReviewReport)
    assert report.overall_status == "CHANGES REQUESTED"
    assert report.critical_count >= 1
    assert report.health_score < 70.0

    # Auto fix flawed sample
    fix_res = agent.auto_fix(DEMO_VULNERABLE_CODE)
    assert fix_res["validation_passed"] is True

    # Review clean sample
    clean_report = agent.review(code=CLEAN_CODE_SAMPLE)
    assert clean_report.overall_status == "APPROVED"
    assert clean_report.critical_count == 0
    assert clean_report.health_score >= 90.0


def test_main_cli_demo_mode():
    """Verify CLI --demo flag executes cleanly with exit code 0."""
    exit_code = main(["--demo"])
    assert exit_code == 0


def test_main_cli_file_review(tmp_path):
    """Verify CLI --file review and --output json."""
    sample_file = tmp_path / "test_sample.py"
    sample_file.write_text(CLEAN_CODE_SAMPLE, encoding="utf-8")

    exit_code = main(["--file", str(sample_file), "--output", "json"])
    assert exit_code == 0


def test_main_cli_diff_review():
    """Verify CLI --diff review."""
    exit_code = main(["--diff", SAMPLE_GIT_DIFF])
    assert exit_code == 0
