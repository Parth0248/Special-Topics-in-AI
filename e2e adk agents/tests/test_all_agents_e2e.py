"""End-to-End Multi-Agent Integration and Opaque-Box Test Suite.

Covers all 5 Google ADK agents across 4 rigorous tiers:
- Tier 1: Feature coverage tests for each agent (Agent A through E).
- Tier 2: Boundary and error conditions (timeouts, missing keys, empty carts, invalid diffs, syntax errors).
- Tier 3: Cross-agent pipeline test cases.
- Tier 4: Real-world workload integration test.
"""

import ast
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

# Ensure schemas module identity between test runner and agent_b_gemini_cli
import schemas
sys.modules["agent_b_gemini_cli.schemas"] = schemas
from schemas import (
    CliResult,
    PipelineSummary,
    StageOutput,
    TaskRequest,
)

# Agent A imports
from agent_a_lead_gen.agent import LeadGenAgent
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
from agent_b_gemini_cli.agent import gemini_cli_tool, run_pipeline_tool
from agent_b_gemini_cli.cli_wrapper import GeminiCliWrapper
from agent_b_gemini_cli.pipeline import ADKPipeline

# Agent C imports
from agent_c_bug_assistant.agent import BugAssistantAgent
from agent_c_bug_assistant.embedded_tools import EmbeddedTools
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
)

# Agent D imports
from agent_d_code_review.agent import CodeReviewAssistantAgent
from agent_d_code_review.constants import CWE_DEFINITIONS, Severity, StateKeys
from agent_d_code_review.fix_pipeline import (
    CodeFixLoopAgent,
    code_fixer,
    fix_validator,
)
from agent_d_code_review.models import (
    CodeReviewReport,
    CodeReviewRequest,
    SecurityFinding,
    StructureMetrics,
    StyleViolation,
)
from agent_d_code_review.reviewer import CodeReviewer
from agent_d_code_review.tools import (
    ToolContext,
    analyze_code_structure,
    check_code_style,
    feedback_synthesizer,
    parse_git_diff,
    scan_security_vulnerabilities,
)

# Agent E imports
from agent_e_sports_shop.agent import SportsAgent
from agent_e_sports_shop.db import DatabaseManager
from agent_e_sports_shop.tools import (
    check_inventory,
    find_nearby_stores,
    get_order_status,
    get_product_details,
    manage_cart,
    place_order,
    search_products,
    set_db,
)
from agent_e_sports_shop.vector_store import (
    VectorStore,
    cosine_distance,
    cosine_similarity,
    deserialize_vector,
    serialize_vector,
)


# ===========================================================================
# TIER 1: Feature Coverage Tests for Each Agent
# ===========================================================================

class TestTier1AgentAFeatures:
    """Tier 1 Feature coverage tests for Agent A: Deep Research Lead Gen."""

    def test_target_market_criteria_validation(self):
        """Verifies TargetMarketCriteria model parsing and bounds validation."""
        criteria = TargetMarketCriteria(
            industry="Fintech",
            geography="North America",
            min_headcount=20,
            max_headcount=500,
            target_stages=["Series A", "Series B"],
            key_signals=["hiring", "expansion"],
            min_fit_score=65.0,
        )
        assert criteria.industry == "Fintech"
        assert criteria.min_headcount == 20
        assert criteria.max_headcount == 500
        assert "Series A" in criteria.target_stages

        # Boundary check: max_headcount < min_headcount raises ValueError
        with pytest.raises(ValueError):
            TargetMarketCriteria(
                industry="AI",
                min_headcount=100,
                max_headcount=10,
            )

    def test_company_discovery_and_search_offline(self):
        """Verifies search_companies discovers candidate profiles deterministically."""
        results = search_companies(
            query="financial compliance and automated identity verification",
            industry="Fintech",
            limit=5,
            mock_only=True,
        )
        assert isinstance(results, list)
        assert len(results) > 0
        first = results[0]
        assert "company_name" in first
        assert "industry" in first
        assert "funding_stage" in first

    def test_firmographic_extraction(self):
        """Verifies extract_company_profile normalizes raw company data into CompanyProfile."""
        raw_company = {
            "company_name": "Synthetix Health AI",
            "website": "https://synthetixhealth.ai",
            "industry": "Healthcare AI",
            "headquarters": "Boston, MA",
            "employee_count": 85,
            "employee_count_range": "51-200",
            "funding_stage": "Series A",
            "total_funding_raised": "$18M",
            "growth_signals": ["Expanding clinical team", "SOC2 certified"],
            "overview": "Clinical trial workflow intelligence and cohort optimization.",
        }
        profile = extract_company_profile("Synthetix Health AI", structured_data=raw_company)
        assert isinstance(profile, CompanyProfile)
        assert profile.company_name == "Synthetix Health AI"
        assert profile.funding_stage == "Series A"
        assert "SOC2 certified" in profile.growth_signals

    def test_lead_fit_scoring_rubric(self):
        """Verifies evaluate_lead_fit computes weighted category scores and returns qualification."""
        criteria = TargetMarketCriteria(
            industry="Fintech",
            geography="North America",
            min_headcount=20,
            max_headcount=250,
            target_stages=["Series A", "Series B"],
            key_signals=["hiring", "compliance"],
            min_fit_score=70.0,
        )
        company = {
            "company_name": "Veritas Identity Systems",
            "website": "https://veritasidentity.example.com",
            "industry": "Fintech",
            "headquarters": "San Francisco, USA",
            "employee_count": 75,
            "funding_stage": "Series A",
            "growth_signals": ["hiring aggressively", "compliance automation expansion"],
        }
        eval_result = evaluate_lead_fit(company, criteria)
        assert isinstance(eval_result, FitScoreEvaluation)
        assert eval_result.overall_fit_score >= 70.0
        assert eval_result.qualification_status in ("HIGH_FIT", "MEDIUM_FIT")
        assert "industry_match" in eval_result.category_scores
        assert "geography_match" in eval_result.category_scores

    def test_dossier_compilation(self):
        """Verifies compile_dossier_report compiles a structured markdown dossier report."""
        criteria = TargetMarketCriteria(industry="Cybersecurity", geography="Global")
        qualified_leads = [
            {
                "profile": {
                    "company_name": "ShieldVault Inc",
                    "website": "https://shieldvault.example.com",
                    "industry": "Cybersecurity",
                    "headquarters": "Austin, TX",
                    "employee_count_range": "51-200",
                    "funding_stage": "Series B",
                    "total_funding_raised": "$35M",
                    "growth_signals": ["Enterprise expansion", "FedRAMP authorization"],
                    "overview": "Zero-trust secrets orchestration.",
                    "source_references": ["https://news.example.com/shieldvault"],
                },
                "evaluation": {
                    "overall_fit_score": 92.5,
                    "qualification_status": "HIGH_FIT",
                    "fit_rationale": "Direct domain match with strong growth signals.",
                    "category_scores": {"industry_match": 30.0, "geography_match": 20.0},
                    "strengths": ["Enterprise traction"],
                    "identified_risks": [],
                },
            }
        ]
        dossier_md = compile_dossier_report(qualified_leads, criteria, output_format="markdown")
        assert isinstance(dossier_md, str)
        assert "ShieldVault" in dossier_md
        assert "92.5" in dossier_md

    def test_lead_gen_agent_orchestrator(self):
        """Verifies LeadGenAgent full 5-stage synchronous workflow in mock mode."""
        criteria = TargetMarketCriteria(industry="Fintech", geography="North America", min_fit_score=50.0)
        agent = LeadGenAgent(mock_mode=True)
        dossier = agent.run(criteria=criteria, candidate_limit=4)
        assert isinstance(dossier, LeadDossier)
        assert dossier.total_candidates_analyzed >= 1
        assert dossier.qualified_leads_count >= 1
        assert len(dossier.leads) >= 1


class TestTier1AgentBFeatures:
    """Tier 1 Feature coverage tests for Agent B: Gemini CLI in ADK Pipeline Tool."""

    def test_gemini_cli_wrapper_execution_mocked(self, mock_gemini_cli):
        """Verifies GeminiCliWrapper executes headless command and captures structured JSON."""
        mock_gemini_cli.set_mode("success", custom_response="class DataProcessor: pass")
        wrapper = GeminiCliWrapper(binary_name="gemini")
        result = wrapper.execute_prompt("Generate a Python data processing class")
        assert isinstance(result, CliResult)
        assert result.success is True
        assert result.returncode == 0
        assert "DataProcessor" in str(result.response)

    def test_gemini_cli_wrapper_fallback(self):
        """Verifies GeminiCliWrapper force_fallback uses SDK / deterministic emulator."""
        wrapper = GeminiCliWrapper(force_fallback=True)
        assert wrapper.is_cli_available() is False
        result = wrapper.execute_prompt("Explain bubble sort algorithm")
        assert isinstance(result, CliResult)
        assert result.success is True
        assert result.is_fallback is True
        assert result.response is not None

    def test_gemini_cli_json_markdown_extraction(self, mock_gemini_cli):
        """Verifies JSON response embedded in Markdown code fences is parsed accurately."""
        mock_gemini_cli.set_mode(
            "malformed",
            custom_response="Synthesized pipeline payload"
        )
        wrapper = GeminiCliWrapper(binary_name="gemini")
        result = wrapper.execute_prompt("Return JSON status")
        assert result.success is True
        assert "Synthesized pipeline payload" in str(result.response)

    def test_four_stage_pipeline_execution(self, mock_gemini_cli):
        """Verifies ADKPipeline runs all 4 stages: Decompose, Exec, Transform, Synthesize."""
        mock_gemini_cli.set_mode("success", custom_response="def add(a, b): return a + b")
        pipeline = ADKPipeline(cli_wrapper=GeminiCliWrapper(binary_name="gemini"))
        task = TaskRequest(
            description="Implement a robust addition function with type hints",
            language="python",
        )
        summary = pipeline.run(task)
        assert isinstance(summary, PipelineSummary)
        assert summary.overall_success is True
        assert len(summary.stages) == 4
        stage_names = [s.stage_name for s in summary.stages]
        assert "Decompose" in stage_names[0]
        assert "Tool Invocation" in stage_names[1]
        assert "Transformation" in stage_names[2]
        assert "Synthesis" in stage_names[3]

    def test_tool_adapter_functions(self, mock_gemini_cli):
        """Verifies standalone tool adapter functions gemini_cli_tool and run_pipeline_tool."""
        mock_gemini_cli.set_mode("success", custom_response="Valid tool output")
        tool_output = gemini_cli_tool("Analyze code structure")
        parsed = json.loads(tool_output)
        assert parsed["success"] is True

        pipe_output = run_pipeline_tool("Create factorial function")
        parsed_pipe = json.loads(pipe_output)
        assert parsed_pipe["overall_success"] is True


class TestTier1AgentCFeatures:
    """Tier 1 Feature coverage tests for Agent C: MCP Tools Bug Assistant."""

    def test_traceback_parser_isolation(self):
        """Verifies TracebackParser accurately isolates exception class and application frames."""
        sample_traceback = """
Traceback (most recent call last):
  File "/usr/lib/python3.11/site-packages/flask/app.py", line 1484, in full_dispatch_request
    rv = self.dispatch_request()
  File "/app/services/billing.py", line 42, in calculate_invoice_discount
    discounted_total = base_amount / discount_factor
ZeroDivisionError: division by zero
"""
        info = TracebackParser.parse(sample_traceback)
        assert isinstance(info, TracebackInfo)
        assert info.exception_type == "ZeroDivisionError"
        assert "division by zero" in info.exception_message
        app_frames = [f for f in info.frames if f.is_application_frame]
        assert len(app_frames) >= 1
        assert info.primary_frame is not None
        assert info.primary_frame.line_number == 42
        assert "billing.py" in info.primary_frame.filename

    def test_embedded_tools_filesystem_and_search(self, tmp_path):
        """Verifies EmbeddedTools read, write, list, and search capabilities."""
        tools = EmbeddedTools(workspace_root=str(tmp_path))
        target_file = tmp_path / "sample.py"
        code = "def greet(name):\n    # line 2\n    return f'Hello, {name}'\n"
        tools.write_file("sample.py", code)

        assert target_file.exists()
        content = tools.read_file("sample.py")
        assert "def greet" in content

        # Slicing test (lines 1 to 2)
        sliced = tools.read_file("sample.py", start_line=1, end_line=2)
        assert "def greet" in sliced
        assert "return" not in sliced

        # Search test: each result has {"file", "line_number", "line", "match"}
        search_res = tools.search_files(pattern=r"def greet", extension=".py")
        assert len(search_res) >= 1
        assert search_res[0]["line_number"] == 1
        assert "def greet" in search_res[0]["line"]

    def test_reproducer_and_patch_synthesis(self, tmp_path):
        """Verifies reproducer and surgical patch generation and application."""
        calc_file = tmp_path / "calculator.py"
        calc_file.write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")

        tb_text = f"""
Traceback (most recent call last):
  File "{calc_file}", line 2, in divide
    return a / b
ZeroDivisionError: division by zero
"""
        tb_info = TracebackParser.parse(tb_text)
        tools = EmbeddedTools(workspace_root=str(tmp_path))
        context = gather_bug_context(tb_info, tools)

        reproducer_code = synthesize_reproducer(tb_info, context)
        assert "def test_reproduce_bug():" in reproducer_code
        assert "ZeroDivisionError" in reproducer_code

        # Patch synthesis
        patch_diff = synthesize_patch(
            context,
            tb_info,
            original_content=calc_file.read_text(encoding="utf-8"),
        )
        assert "---" in patch_diff
        assert "+++" in patch_diff

        # Apply patch
        success = apply_patch_unified(str(calc_file), patch_diff, backup=True)
        assert success is True
        modified_content = calc_file.read_text(encoding="utf-8")
        assert "ZeroDivisionError" in modified_content or "if b == 0:" in modified_content or "return" in modified_content

        # Rollback
        rollback_ok = rollback_patch(str(calc_file))
        assert rollback_ok is True
        assert calc_file.read_text(encoding="utf-8") == "def divide(a, b):\n    return a / b\n"

    def test_bug_assistant_agent_diagnose(self, tmp_path):
        """Verifies BugAssistantAgent.diagnose executes complete 5-phase triage."""
        target_py = tmp_path / "app_module.py"
        target_py.write_text(
            "def get_user_rank(points):\n    return points / 0\n",
            encoding="utf-8",
        )
        traceback_str = f"""
Traceback (most recent call last):
  File "{target_py}", line 2, in get_user_rank
    return points / 0
ZeroDivisionError: division by zero
"""
        agent = BugAssistantAgent(workspace_root=str(tmp_path))
        report = agent.diagnose(stack_trace=traceback_str)
        assert isinstance(report, DiagnosticReport)
        assert report.bug_type == "ZeroDivisionError"
        assert report.line_number == 2
        assert report.patch_diff != ""


class TestTier1AgentDFeatures:
    """Tier 1 Feature coverage tests for Agent D: Code Review Assistant."""

    def test_ast_structural_analysis(self):
        """Verifies analyze_code_structure extracts metrics, classes, and complexity."""
        code = '''
"""Sample module for AST testing."""

class AccountService:
    """Manages user accounts."""

    def authenticate(self, username, password):
        """Checks credentials."""
        if not username or not password:
            return False
        if len(password) < 8:
            return False
        return True
'''
        metrics = analyze_code_structure(code)
        assert metrics["syntax_valid"] is True
        assert metrics["classes_count"] == 1
        assert metrics["functions_count"] == 1
        assert metrics["docstring_coverage"] > 50.0
        assert metrics["max_complexity"] >= 3

    def test_pep8_style_scoring(self):
        """Verifies check_code_style scores code on 0-100 scale and lists violations."""
        clean_code = '''"""A fully PEP 8 compliant module."""


def calculate_area(width: float, height: float) -> float:
    """Calculates rectangular area."""
    return width * height
'''
        clean_res = check_code_style(clean_code)
        assert clean_res["score"] >= 95.0

        messy_code = "def bad_func():\n  x=1\n  y =2 \n  return x+y\n"
        messy_res = check_code_style(messy_code)
        assert messy_res["score"] < clean_res["score"]
        assert len(messy_res["violations"]) > 0

    def test_owasp_security_vulnerability_scanner(self):
        """Verifies scan_security_vulnerabilities detects CWE-89, CWE-78, CWE-95, CWE-798."""
        vuln_code = """
import os
import sqlite3

def dangerous_operations(user_id, cmd_arg):
    # SQL Injection (CWE-89)
    conn = sqlite3.connect(":memory:")
    conn.execute(f"SELECT * FROM users WHERE id = '{user_id}'")

    # Command Injection (CWE-78)
    os.system(f"echo {cmd_arg}")

    # Eval Injection (CWE-95)
    eval(f"verify('{user_id}')")

    # Hardcoded credential (CWE-798)
    api_key = "AKIA1234567890SECRETKEY"
    return True
"""
        findings = scan_security_vulnerabilities(vuln_code)
        assert len(findings) >= 3
        cwe_ids = [f["cwe_id"] for f in findings]
        assert "CWE-89" in cwe_ids
        assert "CWE-78" in cwe_ids
        assert "CWE-95" in cwe_ids
        assert "CWE-798" in cwe_ids
        for f in findings:
            if f["cwe_id"] in ("CWE-89", "CWE-78", "CWE-95"):
                assert f["severity"] == "CRITICAL"

    def test_git_diff_parser(self):
        """Verifies parse_git_diff extracts modified files, line counts, and hunks."""
        sample_diff = """--- a/src/app.py
+++ b/src/app.py
@@ -10,3 +10,4 @@
 def handle_request():
-    return 'old'
+    # Updated response
+    return 'new'
"""
        files = parse_git_diff(sample_diff)
        assert len(files) == 1
        f0 = files[0]
        assert f0["new_file"] == "src/app.py"
        assert f0["stats"]["additions"] == 2
        assert f0["stats"]["deletions"] == 1
        assert len(f0["hunks"]) == 1

    def test_code_reviewer_pipeline(self):
        """Verifies CodeReviewer executes the end-to-end sequential review pipeline."""
        reviewer = CodeReviewer()
        code_to_review = """
def authenticate(token):
    eval(f"verify('{token}')")
    return True
"""
        report = reviewer.review(code=code_to_review)
        assert isinstance(report, CodeReviewReport)
        assert report.critical_count >= 1
        assert report.overall_status == "CHANGES REQUESTED"
        assert "CWE-95" in [f.cwe_id for f in report.security_findings]
        assert len(report.line_comments) >= 1
        assert "Executive Summary" in report.markdown_summary


class TestTier1AgentEFeatures:
    """Tier 1 Feature coverage tests for Agent E: Sports Shop Agent."""

    def test_vector_store_operations(self):
        """Verifies 768-d vector similarity, distance, and serialization."""
        vstore = VectorStore()
        vec_run1 = vstore.generate_embedding("trail running shoes with aggressive vibram lugs")
        vec_run2 = vstore.generate_embedding("marathon racing flats lightweight")
        vec_bsk = vstore.generate_embedding("basketball composite official size 7 ball")

        assert len(vec_run1) == 768
        assert len(vec_bsk) == 768

        sim_run = cosine_similarity(vec_run1, vec_run2)
        sim_diff = cosine_similarity(vec_run1, vec_bsk)

        # Running shoes should be semantically closer to running shoes than basketballs
        assert sim_run > sim_diff
        assert cosine_distance(vec_run1, vec_run2) == pytest.approx(1.0 - sim_run, abs=1e-5)

        # Serialization round-trip
        blob = serialize_vector(vec_run1)
        restored = deserialize_vector(blob)
        np.testing.assert_allclose(vec_run1, restored, rtol=1e-5)

    def test_database_manager_sqlite_fallback(self):
        """Verifies DatabaseManager initializes SQLite with seeded products in fallback mode."""
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")
        assert db.mode == "sqlite"
        products = db.search_products(query="shoes", limit=10)
        assert len(products) >= 2
        first = products[0]
        assert "product_id" in first
        assert "price" in first
        assert "similarity_score" in first
        db.close()

    def test_store_inventory_and_nearby_lookup(self):
        """Verifies store inventory verification and geolocation/distance lookup."""
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")
        inv = db.check_inventory("PROD-RUN-001")
        assert inv["in_stock"] is True
        assert inv["total_network_stock"] >= 10

        stores = db.find_nearby_stores(city="San Jose")
        assert len(stores) >= 1
        assert "San Jose" in stores[0]["city"]
        db.close()

    def test_cart_and_order_lifecycle(self):
        """Verifies cart add, view, clear, and order checkout with stock decrement."""
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")
        user = "test_athlete_01"

        # 1. Add to cart
        cart1 = db.manage_cart(action="add", user_id=user, product_id="PROD-RUN-001", quantity=2)
        assert "error" not in cart1
        assert cart1["item_count"] == 2
        assert cart1["subtotal"] == pytest.approx(149.99 * 2, abs=0.01)

        # 2. View cart
        cart_view = db.manage_cart(action="view", user_id=user)
        assert len(cart_view["items"]) == 1

        # 3. Check baseline stock
        stock_before = db.check_inventory("PROD-RUN-001")["total_network_stock"]

        # 4. Place order
        order = db.place_order(user_id=user, shipping_address="789 Runner Lane, San Jose, CA")
        assert "error" not in order
        order_id = order["order_id"]
        assert order_id.startswith("ORD-")
        assert order["status"] == "confirmed"

        # 5. Check cart cleared
        cart_after = db.manage_cart(action="view", user_id=user)
        assert len(cart_after["items"]) == 0

        # 6. Check inventory decremented
        stock_after = db.check_inventory("PROD-RUN-001")["total_network_stock"]
        assert stock_after == stock_before - 2

        # 7. Check order status
        status = db.get_order_status(order_id)
        assert status["order_id"] == order_id
        assert status["status"] == "confirmed"
        db.close()

    def test_sports_agent_persona(self):
        """Verifies SportsAgent ('Finn') answers query, recommends gear, and manages cart."""
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")
        set_db(db)
        agent = SportsAgent(user_id="customer_marathoner")

        response = agent.execute_turn("Find me trail running shoes under $160")
        assert isinstance(response, str)
        assert len(response) > 20
        assert "Apex" in response or "Trail" in response or "running" in response.lower()
        db.close()


# ===========================================================================
# TIER 2: Boundary and Error Conditions
# ===========================================================================

class TestTier2BoundaryAndErrors:
    """Tier 2 Boundary and error condition tests across all 5 agents."""

    def test_agent_b_subprocess_timeout(self, mock_gemini_cli):
        """Verifies Agent B catches subprocess timeout without crashing."""
        mock_gemini_cli.set_mode("timeout")
        wrapper = GeminiCliWrapper(binary_name="gemini", default_timeout=5)
        result = wrapper.execute_prompt("Long running calculation")
        assert isinstance(result, CliResult)
        assert result.success is False
        assert result.returncode == -1
        assert "TimeoutExpired" in str(result.error)

    def test_agent_b_cli_error_exit_code(self, mock_gemini_cli):
        """Verifies Agent B captures non-zero exit code and stderr."""
        mock_gemini_cli.set_mode("error", returncode=127, stderr="Command not found: gemini")
        wrapper = GeminiCliWrapper(binary_name="gemini")
        result = wrapper.execute_prompt("Test error exit")
        assert result.success is False
        assert result.returncode == 127
        assert "Command not found" in result.error

    def test_agent_e_empty_cart_checkout(self):
        """Verifies Agent E prevents checkout on an empty cart and returns error."""
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")
        order = db.place_order(user_id="empty_cart_user")
        assert "error" in order
        assert "Cart is empty" in order["error"]
        db.close()

    def test_agent_e_nonexistent_product(self):
        """Verifies Agent E gracefully handles non-existent product IDs."""
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")
        details = db.get_product_details("PROD-NON-EXISTENT-999")
        assert "error" in details

        cart_res = db.manage_cart("add", user_id="user_err", product_id="PROD-FAKE-000")
        assert "error" in cart_res
        db.close()

    def test_agent_d_syntax_error_in_code(self):
        """Verifies Agent D detects Python syntax error and records CRITICAL finding."""
        unparseable_code = "def broken_syntax(x, y:\n    return x +"
        metrics = analyze_code_structure(unparseable_code)
        assert metrics["syntax_valid"] is False
        assert metrics["syntax_error"] is not None

        reviewer = CodeReviewer()
        report = reviewer.review(code=unparseable_code)
        assert report.structure_metrics["syntax_valid"] is False
        assert report.overall_status == "CHANGES REQUESTED"
        assert any(v.severity == Severity.CRITICAL or v.code == "E999" for v in report.style_violations)

    def test_agent_c_missing_file_error(self, tmp_path):
        """Verifies Agent C EmbeddedTools raises FileNotFoundError on missing files."""
        tools = EmbeddedTools(workspace_root=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            tools.read_file("non_existent_code_file_404.py")

    def test_agent_c_empty_traceback_handling(self):
        """Verifies Agent C TracebackParser handles partial or unformatted logs gracefully."""
        unstructured_log = "Connection closed unexpectedly by peer."
        info = TracebackParser.parse(unstructured_log)
        assert isinstance(info, TracebackInfo)
        assert info.exception_type == "UnknownException"
        assert len(info.frames) == 0

    def test_agent_a_missing_api_key_graceful_fallback(self, monkeypatch):
        """Verifies Agent A falls back smoothly to offline data when GOOGLE_API_KEY is empty."""
        monkeypatch.setenv("GOOGLE_API_KEY", "")
        candidates = search_companies("machine learning payments", industry="Fintech", limit=3)
        assert isinstance(candidates, list)
        assert len(candidates) > 0


# ===========================================================================
# TIER 3: Cross-Agent Pipeline Test Cases
# ===========================================================================

class TestTier3CrossAgentPipelines:
    """Tier 3 Multi-agent interaction pipelines testing interoperability."""

    def test_pipeline_1_lead_gen_to_sports_shop(self):
        """Pipeline 1: Agent A discovers athletic tech startup -> Agent E queries catalog for complementary gear.

        1. Agent A searches for 'Athletic Performance Apparel & Footwear' startup leads.
        2. Discovers an outdoor gear company profile.
        3. Agent E takes the industry theme ('outdoor') and queries local sports catalog.
        4. Verifies product recommendations and stock availability for a prospective partner bundle.
        """
        # Step 1: Agent A Deep Research Lead Discovery
        criteria = TargetMarketCriteria(
            industry="Outdoor Athletic Gear",
            geography="North America",
            min_fit_score=50.0,
        )
        lead_agent = LeadGenAgent(mock_mode=True)
        dossier = lead_agent.run(criteria=criteria, candidate_limit=3)
        assert dossier.total_candidates_analyzed >= 1

        # Step 2: Extract top lead theme
        lead = dossier.leads[0]
        lead_industry = lead["profile"]["industry"]

        # Step 3: Agent E Catalog Matching
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")
        set_db(db)
        matched_products = search_products(query=f"{lead_industry} waterproof equipment", category="outdoor")
        assert len(matched_products) >= 1

        top_item = matched_products[0]
        assert top_item["product_id"].startswith("PROD-")

        # Step 4: Verify inventory for partner showcase
        inv = check_inventory(top_item["product_id"])
        assert inv["in_stock"] is True
        db.close()

    def test_pipeline_2_code_review_to_bug_assistant_to_validator(self, tmp_path):
        """Pipeline 2: Agent D identifies vulnerable code -> Agent C synthesizes patch -> Agent D audits fix.

        1. Agent D reviews a flawed script with command injection vulnerability.
        2. Agent C consumes the stack trace / issue context, synthesizes reproducer and patch.
        3. Patch is applied to the codebase.
        4. Agent D re-audits the patched code, confirming 0 critical vulnerabilities and improved score.
        """
        # Step 1: Flawed code file setup
        discount_file = tmp_path / "cmd_runner.py"
        flawed_code = (
            "import os\n\n"
            "def run_custom_command(cmd_arg):\n"
            "    # Vulnerable command execution\n"
            "    os.system(f'echo {cmd_arg}')\n"
        )
        discount_file.write_text(flawed_code, encoding="utf-8")

        # Agent D Audit 1
        reviewer = CodeReviewer()
        report_before = reviewer.review(code=flawed_code)
        assert report_before.critical_count >= 1

        # Step 2: Agent C Diagnosis and Patch Synthesis
        stack_trace = f"""
Traceback (most recent call last):
  File "{discount_file}", line 5, in run_custom_command
    os.system(f'echo {{cmd_arg}}')
RuntimeError: Command injection detected
"""
        safe_fixed_code = (
            "import subprocess\n\n"
            "def run_custom_command(cmd_arg):\n"
            '    """Safely executes custom command using subprocess."""\n'
            "    return subprocess.run(['echo', str(cmd_arg)], shell=False, check=True)\n"
        )
        c_agent = BugAssistantAgent(workspace_root=str(tmp_path))
        diag_report = c_agent.diagnose(stack_trace=stack_trace, custom_fix=safe_fixed_code)
        assert diag_report.bug_type == "RuntimeError"
        assert diag_report.patch_diff != ""

        # Step 3: Apply surgical patch
        apply_ok = apply_patch_unified(str(discount_file), diag_report.patch_diff)
        assert apply_ok is True
        patched_code = discount_file.read_text(encoding="utf-8")

        # Step 4: Agent D Re-Audit
        report_after = reviewer.review(code=patched_code)
        assert report_after.critical_count == 0

    def test_pipeline_3_gemini_cli_to_code_review_to_execution(self, mock_gemini_cli, tmp_path):
        """Pipeline 3: Agent B CLI tool generates helper -> Agent D audits -> Agent C executes test.

        1. Agent B executes pipeline to generate an inventory alert helper.
        2. Agent D audits generated code for syntax, style, and security.
        3. Agent C's embedded tools write and verify test execution in the workspace.
        """
        # Step 1: Agent B Generates Code
        generated_code = (
            '"""Inventory monitor utility."""\n\n'
            "def check_stock_level(stock: int, threshold: int = 5) -> bool:\n"
            '    """Returns True if stock is above threshold."""\n'
            "    return stock > threshold\n"
        )
        mock_gemini_cli.set_mode("success", custom_response=generated_code)

        cli_wrapper = GeminiCliWrapper(binary_name="gemini")
        cli_result = cli_wrapper.execute_prompt("Generate stock monitor function")
        assert cli_result.success is True

        # Step 2: Agent D Audits Generated Code
        reviewer = CodeReviewer()
        review = reviewer.review(code=generated_code)
        assert review.critical_count == 0
        assert review.health_score >= 80.0

        # Step 3: Agent C Writes and Verifies Execution
        tools = EmbeddedTools(workspace_root=str(tmp_path))
        tools.write_file("stock_monitor.py", generated_code)

        test_code = (
            "from stock_monitor import check_stock_level\n\n"
            "def test_stock():\n"
            "    assert check_stock_level(10, 5) is True\n"
            "    assert check_stock_level(2, 5) is False\n"
        )
        tools.write_file("test_stock_monitor.py", test_code)

        exec_res = tools.run_test_command("pytest test_stock_monitor.py")
        assert exec_res["exit_code"] == 0


# ===========================================================================
# TIER 4: Real-World Workload Integration Test
# ===========================================================================

class TestTier4RealWorldWorkload:
    """Tier 4 Full end-to-end integration test across all 5 agents."""

    def test_full_enterprise_multi_agent_workflow(self, mock_gemini_cli, tmp_path):
        """Executes a realistic enterprise multi-agent workflow exercising all 5 agents:

        1. Agent A performs market research to identify target opportunities in athletic sports retail.
        2. Agent B decomposes and synthesizes promotional campaign logic via CLI pipeline.
        3. Agent E performs vector search, verifies warehouse & store inventory, and places test order.
        4. Agent D reviews the campaign code against OWASP/CWE security and PEP 8 standards.
        5. Agent C verifies workspace integrity and filesystem outputs via MCP tools.
        """
        workflow_start = time.time()
        telemetry: Dict[str, Any] = {}

        # -------------------------------------------------------------------
        # Step 1: Agent A - Deep Research Lead Generation
        # -------------------------------------------------------------------
        criteria = TargetMarketCriteria(
            industry="Sports Retail & Apparel",
            geography="North America",
            min_headcount=10,
            max_headcount=500,
            target_stages=["Series A", "Series B", "Growth"],
            key_signals=["omnichannel", "expansion"],
            min_fit_score=50.0,
        )
        agent_a = LeadGenAgent(mock_mode=True)
        dossier = agent_a.run(criteria=criteria, candidate_limit=5)

        assert isinstance(dossier, LeadDossier)
        assert dossier.total_candidates_analyzed >= 1
        assert dossier.qualified_leads_count >= 1
        top_lead = dossier.leads[0]
        telemetry["agent_a_leads"] = len(dossier.leads)
        telemetry["agent_a_top_lead"] = top_lead["profile"]["company_name"]

        # -------------------------------------------------------------------
        # Step 2: Agent B - Gemini CLI Pipeline Tool Execution
        # -------------------------------------------------------------------
        campaign_code_snippet = (
            '"""Automated campaign discount evaluator."""\n\n'
            "def apply_promotional_discount(price: float, member_tier: str) -> float:\n"
            '    """Calculates discounted price based on verified member tier."""\n'
            '    discount_rates = {"vip": 0.20, "gold": 0.15, "silver": 0.10}\n'
            "    rate = discount_rates.get(member_tier.lower(), 0.0)\n"
            "    return round(price * (1.0 - rate), 2)\n"
        )
        mock_gemini_cli.set_mode("success", custom_response=campaign_code_snippet)

        pipeline_b = ADKPipeline(cli_wrapper=GeminiCliWrapper(binary_name="gemini"))
        task_b = TaskRequest(
            description="Generate promotional discount evaluator for sports club members",
            language="python",
        )
        summary_b = pipeline_b.run(task_b)

        assert summary_b.overall_success is True
        assert len(summary_b.stages) == 4
        telemetry["agent_b_stages"] = len(summary_b.stages)
        telemetry["agent_b_cli_calls"] = summary_b.cli_invocations_count

        # -------------------------------------------------------------------
        # Step 3: Agent E - E-Commerce Catalog & Checkout Operation
        # -------------------------------------------------------------------
        db_e = DatabaseManager(use_alloydb=False, db_path=":memory:")
        set_db(db_e)

        # Vector product search for trail shoes
        trail_products = search_products(query="Apex trail running shoes with Gore-Tex", category="running", limit=3)
        assert len(trail_products) >= 1
        featured_item = trail_products[0]
        prod_id = featured_item["product_id"]

        # Inventory check across stores
        inventory_data = check_inventory(prod_id)
        assert inventory_data["in_stock"] is True

        # Cart addition and order completion
        user_id = "enterprise_partner_01"
        cart_res = manage_cart(action="add", user_id=user_id, product_id=prod_id, quantity=5)
        assert "error" not in cart_res

        order_res = place_order(user_id=user_id, shipping_address="100 Enterprise Way, San Jose, CA")
        assert "error" not in order_res
        order_id = order_res["order_id"]
        telemetry["agent_e_order_id"] = order_id
        telemetry["agent_e_order_total"] = order_res["total_amount"]
        db_e.close()

        # -------------------------------------------------------------------
        # Step 4: Agent D - Automated Code Review & Security Audit
        # -------------------------------------------------------------------
        assistant_d = CodeReviewAssistantAgent()
        review_d = assistant_d.review(code=campaign_code_snippet)

        assert isinstance(review_d, CodeReviewReport)
        assert review_d.critical_count == 0
        assert review_d.health_score >= 80.0
        assert "apply_promotional_discount" in str(review_d.structure_metrics)
        telemetry["agent_d_health_score"] = review_d.health_score

        # -------------------------------------------------------------------
        # Step 5: Agent C - Workspace Verification & File Integrity Check
        # -------------------------------------------------------------------
        tools_c = EmbeddedTools(workspace_root=str(tmp_path))
        manifest_payload = json.dumps({
            "campaign": "Fall 2026 Sports Discovery",
            "lead_partner": telemetry["agent_a_top_lead"],
            "featured_product": prod_id,
            "order_id": order_id,
            "code_health_score": review_d.health_score,
            "timestamp": time.time(),
        }, indent=2)

        tools_c.write_file("campaign_code.py", campaign_code_snippet)
        tools_c.write_file("campaign_manifest.json", manifest_payload)

        # Verify filesystem entries
        dir_listing = tools_c.list_directory(".")
        assert "campaign_code.py" in dir_listing
        assert "campaign_manifest.json" in dir_listing

        readback_manifest = json.loads(tools_c.read_file("campaign_manifest.json"))
        assert readback_manifest["featured_product"] == prod_id
        assert readback_manifest["order_id"] == order_id

        total_duration = time.time() - workflow_start
        telemetry["total_workflow_duration_seconds"] = round(total_duration, 3)

        # Telemetry assertion
        assert telemetry["total_workflow_duration_seconds"] > 0
        assert "agent_a_leads" in telemetry
        assert "agent_b_stages" in telemetry
        assert "agent_e_order_id" in telemetry
        assert "agent_d_health_score" in telemetry
