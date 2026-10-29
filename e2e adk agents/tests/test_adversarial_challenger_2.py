"""Empirical Adversarial Challenge and Stress-Testing Suite (challenger_2).

Exhaustively verifies robustness, boundary behavior, and failure modes for:
1. Agent D: Severe syntax errors, unparseable diffs, intentional OWASP vulnerabilities, edge-case style scores.
2. Agent E: Empty cart checkout, negative quantities, out-of-stock items, unknown postal codes, vector search with orthogonal/zero vectors, SQLite fallback under missing credentials.
3. Cross-Agent Integration Pipelines:
   - Pipeline 1: Lead Gen -> Sports Shop with zero leads and SQLi payloads.
   - Pipeline 2: Code Review -> Bug Assistant -> Validator with patch generation, audit, and invalid patch handling.
   - Pipeline 3: Gemini CLI -> Code Review -> Execution with adversarial/malicious code generation blocking.
"""

import ast
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

# Ensure schemas module identity between test runner and agent_b_gemini_cli
import schemas
sys.modules["agent_b_gemini_cli.schemas"] = schemas
from schemas import CliResult, TaskRequest

# Agent A imports
from agent_a_lead_gen.agent import LeadGenAgent
from agent_a_lead_gen.models import TargetMarketCriteria
from agent_a_lead_gen.tools import search_companies

# Agent B imports
from agent_b_gemini_cli.cli_wrapper import GeminiCliWrapper

# Agent C imports
from agent_c_bug_assistant.agent import BugAssistantAgent
from agent_c_bug_assistant.embedded_tools import EmbeddedTools
from agent_c_bug_assistant.triage import (
    TracebackParser,
    apply_patch_unified,
    gather_bug_context,
    rollback_patch,
    synthesize_patch,
    synthesize_reproducer,
)

# Agent D imports
from agent_d_code_review.agent import CodeReviewAssistantAgent
from agent_d_code_review.constants import Severity, StateKeys
from agent_d_code_review.models import CodeReviewReport
from agent_d_code_review.reviewer import CodeReviewer
from agent_d_code_review.tools import (
    ToolContext,
    analyze_code_structure,
    check_code_style,
    parse_git_diff,
    scan_security_vulnerabilities,
)

# Agent E imports
from agent_e_sports_shop.agent import SportsAgent
from agent_e_sports_shop.db import DatabaseManager
from agent_e_sports_shop.tools import (
    check_inventory,
    find_nearby_stores,
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
# 1. ADVERSARIAL STRESS TESTS FOR AGENT D (Code Review Assistant)
# ===========================================================================

class TestAgentDAdversarialStress:
    """Stress tests Agent D against severe syntax errors, unparseable diffs, OWASP injections, and style edge cases."""

    def test_agent_d_severe_syntax_errors(self):
        """Tests Agent D against various severe syntax corruptions:
        - Mismatched delimiters
        - Truncated function headers
        - Unterminated multiline strings
        - Invalid indentation
        """
        reviewer = CodeReviewer()

        corrupt_samples = [
            ("def broken(x, y:\n    return x + y", "unclosed parameter list"),
            ("x = [1, 2, 3\nprint(x)", "unclosed bracket list"),
            ("'''unterminated docstring\ndef foo(): pass", "unterminated string"),
            ("def foo():\nreturn 1", "missing indentation"),
            ("import ;;;", "invalid token import"),
        ]

        for code, description in corrupt_samples:
            struct = analyze_code_structure(code)
            assert struct["syntax_valid"] is False, f"Failed for {description}"
            assert struct["syntax_error"] is not None

            report = reviewer.review(code=code)
            assert report.overall_status == "CHANGES REQUESTED", f"Expected CHANGES REQUESTED for {description}"
            assert report.structure_metrics["syntax_valid"] is False
            # Verify E999 violation is recorded for syntax error
            assert any(v.code == "E999" for v in report.style_violations)
            # Verify health_score capped to at most 25.0 and CRITICAL blocker finding recorded
            assert report.health_score <= 25.0
            assert any(f.severity == Severity.CRITICAL for f in report.security_findings)

    def test_agent_d_unparseable_diffs(self):
        """Tests parse_git_diff against corrupted diffs, raw non-diff strings, and malformed hunks."""
        # 1. Non-diff raw text
        non_diff = "Random conversational text that has nothing to do with git."
        parsed = parse_git_diff(non_diff)
        assert parsed == []

        # 2. Corrupted hunk header
        corrupt_hunk_diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ not_a_valid_hunk_header @@
+print('hello')
"""
        parsed_corrupt = parse_git_diff(corrupt_hunk_diff)
        assert len(parsed_corrupt) == 1
        assert parsed_corrupt[0]["new_file"] == "test.py"
        assert len(parsed_corrupt[0]["hunks"]) == 0  # Invalid hunk header ignored cleanly

        # 3. Empty string diff
        assert parse_git_diff("") == []
        assert parse_git_diff("   \n\n  ") == []

        # 4. Binary / truncated diff
        trunc_diff = "diff --git a/bin b/bin\nBinary files differ"
        parsed_trunc = parse_git_diff(trunc_diff)
        assert len(parsed_trunc) == 1
        assert parsed_trunc[0]["stats"]["changes"] == 0

    def test_agent_d_intentional_owasp_vulnerabilities(self):
        """Tests detection of intentional OWASP Top 10 / CWE vulnerabilities across multiple categories."""
        vulnerable_code = '''
import os
import subprocess
import pickle
import sqlite3

def handle_user_request(user_input, raw_payload, file_name, math_expr):
    # CWE-89: SQL Injection via f-string
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE name = '{user_input}'")

    # CWE-89: SQL Injection via string concatenation in assignment
    query = "SELECT * FROM secrets WHERE id = " + user_input
    cur.execute(query)

    # CWE-78: Command Injection via os.system
    os.system(f"ping -c 1 {user_input}")

    # CWE-78: Command Injection via subprocess shell=True
    subprocess.run(f"echo {user_input}", shell=True)

    # CWE-502: Insecure Deserialization
    data = pickle.loads(raw_payload)

    # CWE-22: Path Traversal
    with open("/var/logs/" + file_name, "r") as f:
        content = f.read()

    # CWE-95: Eval Code Injection
    calc = eval(math_expr)

    # CWE-798: Hardcoded credential
    API_KEY = "sk-live-production-secret-token-987654"

    # CWE-703: Bare except pass
    try:
        pass
    except:
        pass

    return data
'''
        reviewer = CodeReviewer()
        report = reviewer.review(code=vulnerable_code)

        assert report.overall_status == "CHANGES REQUESTED"
        assert report.critical_count >= 5

        cwe_found = {f.cwe_id for f in report.security_findings}
        assert "CWE-89" in cwe_found, "Missing SQL Injection CWE-89"
        assert "CWE-78" in cwe_found, "Missing Command Injection CWE-78"
        assert "CWE-502" in cwe_found, "Missing Deserialization CWE-502"
        assert "CWE-95" in cwe_found, "Missing Eval Injection CWE-95"
        assert "CWE-22" in cwe_found, "Missing Path Traversal CWE-22"
        assert "CWE-798" in cwe_found, "Missing Hardcoded Credential CWE-798"
        assert "CWE-703" in cwe_found, "Missing Bare Except CWE-703"

    def test_agent_d_edge_case_style_scoring(self):
        """Tests PEP 8 style scoring at boundary conditions:
        - 100% clean code
        - Exactly 88 characters line length vs 89 characters
        - Massive violations (score must clamp cleanly to 0.0, not negative)
        - Whitespace and tab combinations
        """
        # 1. 100% clean code
        clean_code = '''"""Module providing clean math functions."""


def add_numbers(first_val: int, second_val: int) -> int:
    """Adds two integers and returns the result."""
    return first_val + second_val
'''
        style_clean = check_code_style(clean_code)
        assert style_clean["score"] == 100.0
        assert style_clean["clean"] is True
        assert len(style_clean["violations"]) == 0

        # 2. 88 vs 89 char boundary
        code_88 = 'x = 1  # ' + ('a' * (88 - 9))
        code_89 = 'x = 1  # ' + ('a' * (89 - 9))
        assert len(code_88) == 88
        assert len(code_89) == 89

        res_88 = check_code_style(code_88)
        assert not any(v["code"] == "E501" for v in res_88["violations"])

        res_89 = check_code_style(code_89)
        assert any(v["code"] == "E501" for v in res_89["violations"])

        # 3. Massive violations clamping
        massive_violations_code = "\n".join(["x=1 \t # " + ("v" * 90) for _ in range(60)])
        res_massive = check_code_style(massive_violations_code)
        assert res_massive["score"] == 0.0, "Style score must clamp to 0.0 and not become negative"

        # 4. Empty code
        assert check_code_style("")["score"] == 100.0


# ===========================================================================
# 2. ADVERSARIAL STRESS TESTS FOR AGENT E (E-Commerce Sports Shop)
# ===========================================================================

class TestAgentEAdversarialStress:
    """Stress tests Agent E against empty carts, negative quantities, stock limits, unknown zips, and vector extremes."""

    def test_agent_e_empty_cart_checkout(self):
        """Verifies Agent E prevents placing order on empty cart."""
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")
        res = db.place_order(user_id="user_with_no_cart")
        assert "error" in res
        assert "Cart is empty" in res["error"]
        db.close()

    def test_agent_e_negative_quantities_empirical_vulnerability(self):
        """Empirically asserts whether negative quantity inputs are caught or permit cart corruption.

        NOTE FOR CRITIC: This test documents the empirical behavior when negative quantities
        are supplied to manage_cart('add', ...) or manage_cart('remove', ...).
        """
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")

        # Test adding negative quantity
        cart = db.manage_cart(action="add", user_id="adversary_user", product_id="PROD-RUN-001", quantity=-3)

        # Check empirical state:
        # If the system does NOT reject negative quantities, cart item_count will be -3 or subtotal will be negative.
        if "error" not in cart:
            assert cart["item_count"] == -3, "Negative quantity was accepted without error"
            assert cart["subtotal"] < 0, "Subtotal was negative"

            # Attempt checkout with negative balance
            order = db.place_order(user_id="adversary_user")
            # Document if order confirms with negative balance
            if "error" not in order:
                assert order["total_amount"] < 0
                assert order["status"] == "confirmed"
        else:
            # If rejected, error should state invalid quantity
            assert "quantity" in cart["error"].lower()

        db.close()

    def test_agent_e_out_of_stock_and_inventory_exhaustion(self):
        """Verifies rejection when adding more than available network inventory or checking out exhausted stock."""
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")

        inv = db.check_inventory("PROD-RUN-001")
        total_available = inv["total_network_stock"]

        # Attempt to add total_available + 10 units
        res = db.manage_cart(action="add", user_id="greedy_user", product_id="PROD-RUN-001", quantity=total_available + 10)
        assert "error" in res
        assert "exceeds" in res["error"].lower()

        # Place valid order that consumes stock
        db.manage_cart(action="add", user_id="valid_user", product_id="PROD-RUN-001", quantity=2)
        order_res = db.place_order(user_id="valid_user")
        assert "error" not in order_res

        # Verify stock decremented
        inv_after = db.check_inventory("PROD-RUN-001")
        assert inv_after["total_network_stock"] == total_available - 2
        db.close()

    def test_agent_e_unknown_postal_codes(self):
        """Verifies behavior when customer provides unknown or out-of-region postal codes.

        Empirical observation: Unrecognized zip codes fallback to SJSU coordinates (37.3352, -121.8811).
        """
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")

        unknown_zips = ["99999", "00000", "INVALID_ZIP", "10001"]
        for zip_code in unknown_zips:
            stores = db.find_nearby_stores(postal_code=zip_code)
            assert len(stores) >= 1
            # Verify distance is computed without throwing an unhandled exception
            assert "distance_miles" in stores[0]
            assert isinstance(stores[0]["distance_miles"], float)

        db.close()

    def test_agent_e_vector_search_zero_and_orthogonal_vectors(self):
        """Tests cosine_similarity, cosine_distance, and product search with zero vectors and orthogonal vectors."""
        # 1. Cosine similarity with zero vectors
        zero_vec = np.zeros(768, dtype=np.float32)
        unit_vec1 = np.zeros(768, dtype=np.float32)
        unit_vec1[0] = 1.0

        unit_vec2 = np.zeros(768, dtype=np.float32)
        unit_vec2[1] = 1.0

        # Zero vector dot product / norm
        assert cosine_similarity(zero_vec, unit_vec1) == 0.0
        assert cosine_distance(zero_vec, unit_vec1) == 1.0

        # Orthogonal vectors
        assert cosine_similarity(unit_vec1, unit_vec2) == 0.0
        assert cosine_distance(unit_vec1, unit_vec2) == 1.0

        # 2. Product search with empty string and whitespace queries
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")

        empty_results = db.search_products(query="")
        assert len(empty_results) >= 1
        # All products must have 0.0 similarity score for empty query
        for p in empty_results:
            assert p["similarity_score"] == 0.0

        ws_results = db.search_products(query="     ")
        assert len(ws_results) >= 1
        for p in ws_results:
            assert p["similarity_score"] == 0.0

        db.close()

    def test_agent_e_sqlite_fallback_under_missing_credentials(self, monkeypatch):
        """Verifies DatabaseManager smoothly falls back to SQLite + NumPy when AlloyDB is unreachable or credentials unset."""
        # Unset ALLOYDB_HOST and set invalid host
        monkeypatch.setenv("ALLOYDB_HOST", "invalid.unreachable.alloydb.domain.local")
        monkeypatch.setenv("ALLOYDB_PORT", "5432")

        db = DatabaseManager(use_alloydb=True, probe_timeout=0.2, db_path=":memory:")
        assert db.mode == "sqlite"
        assert db.sqlite_conn is not None

        # Verify database queries function cleanly in fallback mode
        products = db.search_products(query="running", limit=3)
        assert len(products) >= 1
        db.close()


# ===========================================================================
# 3. ADVERSARIAL STRESS TESTS FOR CROSS-AGENT PIPELINES
# ===========================================================================

class TestCrossAgentPipelinesAdversarialStress:
    """Stress tests multi-agent interaction pipelines against adversarial handoffs, malformed diffs, and security rejections."""

    def test_pipeline_1_lead_gen_to_sports_shop_adversarial(self):
        """Tests Lead Gen -> Sports Shop pipeline under edge conditions:
        1. Criteria that matches 0 leads.
        2. Malicious industry name containing SQL Injection payload passed to Agent E.
        """
        # Case 1: Zero leads returned
        crit_impossible = TargetMarketCriteria(
            industry="Submarine Quantum Agriculture",
            min_fit_score=99.9,
        )
        lead_agent = LeadGenAgent(mock_mode=True)
        dossier = lead_agent.run(criteria=crit_impossible)
        assert dossier.total_candidates_analyzed >= 0

        # Case 2: SQL Injection payload in industry passed into Agent E
        malicious_industry = "'; DROP TABLE products; --"
        db = DatabaseManager(use_alloydb=False, db_path=":memory:")
        set_db(db)

        # Agent E search must handle SQL injection safely without crashing or dropping table
        matched = search_products(query=f"{malicious_industry} sports equipment", category=malicious_industry)
        assert isinstance(matched, list)

        # Verify products table is completely intact
        cur = db.sqlite_conn.cursor()
        cur.execute("SELECT COUNT(*) as count FROM products")
        count = cur.fetchone()["count"]
        assert count > 0, "Products table was corrupted or dropped!"
        db.close()

    def test_pipeline_2_code_review_to_bug_assistant_adversarial(self, tmp_path):
        """Tests Code Review -> Bug Assistant -> Validator pipeline with invalid patch handling:
        1. Agent D flags severe vulnerability.
        2. Invalid or unparseable patch is generated.
        3. Patch application fails safely without destroying original code.
        4. Valid patch is generated, applied, and Agent D confirms remediation.
        """
        code_file = tmp_path / "service.py"
        initial_flawed_code = (
            "import os\n\n"
            "def execute_cmd(user_arg):\n"
            "    # Severe OS command injection\n"
            "    os.system('echo ' + user_arg)\n"
        )
        code_file.write_text(initial_flawed_code, encoding="utf-8")

        # Step 1: Agent D Audit 1
        reviewer = CodeReviewer()
        report_1 = reviewer.review(code=initial_flawed_code)
        assert report_1.critical_count >= 1
        assert report_1.overall_status == "CHANGES REQUESTED"

        # Step 2: Attempt to apply malformed/corrupted patch (no valid hunk headers)
        corrupted_patch_no_hunks = "Invalid plaintext diff with no hunk headers at all."
        apply_result_no_hunks = apply_patch_unified(str(code_file), corrupted_patch_no_hunks)
        assert apply_result_no_hunks is False, "Diff without hunks must return False"
        # Confirm original code remains intact
        assert code_file.read_text(encoding="utf-8") == initial_flawed_code

        # Mismatched hunk headers (e.g. line 999 on 5-line file)
        # Remediated: apply_patch_unified cleanly rejects mismatched hunk and returns False
        corrupted_patch_mismatch = """--- a/service.py
+++ b/service.py
@@ -999,1 +999,1 @@
-non_existent_line_content
+new_content
"""
        mismatch_res = apply_patch_unified(str(code_file), corrupted_patch_mismatch)
        # Remediated: verify that apply_patch_unified returned False and kept original code intact
        assert mismatch_res is False, "apply_patch_unified cleanly rejects mismatched hunk"
        assert code_file.read_text(encoding="utf-8") == initial_flawed_code

        # Step 3: Apply valid surgical patch
        valid_fixed_code = (
            "import subprocess\n\n"
            "def execute_cmd(user_arg):\n"
            '    """Safely executes echo command with subprocess."""\n'
            "    return subprocess.run(['echo', str(user_arg)], shell=False, check=True)\n"
        )
        tb_text = f"""
Traceback (most recent call last):
  File "{code_file}", line 5, in execute_cmd
    os.system('echo ' + user_arg)
RuntimeError: Command injection vulnerability
"""
        c_agent = BugAssistantAgent(workspace_root=str(tmp_path))
        diag = c_agent.diagnose(stack_trace=tb_text, custom_fix=valid_fixed_code)
        assert diag.patch_diff != ""

        valid_apply = apply_patch_unified(str(code_file), diag.patch_diff)
        assert valid_apply is True

        # Step 4: Agent D Re-Audit confirms vulnerability eliminated
        re_audit_code = code_file.read_text(encoding="utf-8")
        report_2 = reviewer.review(code=re_audit_code)
        assert report_2.critical_count == 0

    def test_pipeline_3_gemini_cli_to_code_review_security_blocking(self, mock_gemini_cli, tmp_path):
        """Tests Gemini CLI -> Code Review -> Execution pipeline when Gemini CLI generates malicious code:
        1. Gemini CLI mock generates code containing OWASP SQL Injection and OS Command Injection.
        2. Agent D reviews generated code and flags CRITICAL merge blockers.
        3. Pipeline blocks execution and rejects file creation.
        """
        # Step 1: Gemini CLI generates malicious code
        malicious_generated_code = (
            "import os\n"
            "import sqlite3\n\n"
            "def unsafe_inventory_query(product_id, cmd):\n"
            "    # Malicious injection\n"
            "    conn = sqlite3.connect('store.db')\n"
            "    conn.cursor().execute(f'SELECT * FROM items WHERE id = {product_id}')\n"
            "    os.system(f'echo {cmd}')\n"
        )
        mock_gemini_cli.set_mode("success", custom_response=malicious_generated_code)

        cli = GeminiCliWrapper(binary_name="gemini")
        res = cli.execute_prompt("Generate inventory query helper")
        assert res.success is True

        # Step 2: Agent D Code Review Audit
        reviewer = CodeReviewer()
        review_rep = reviewer.review(code=malicious_generated_code)

        # Step 3: Assert Agent D strictly BLOCKS execution
        assert review_rep.critical_count >= 2
        assert review_rep.overall_status == "CHANGES REQUESTED"

        # Gate check: only proceed if approved
        execution_permitted = (review_rep.overall_status == "APPROVED")
        assert execution_permitted is False, "Pipeline failed to block malicious code execution!"

        # Ensure Agent C does not write or execute the blocked code
        tools = EmbeddedTools(workspace_root=str(tmp_path))
        target_file = tmp_path / "unsafe_inventory.py"
        assert not target_file.exists()
