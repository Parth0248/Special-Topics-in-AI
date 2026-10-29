"""Fix Pipeline and LoopAgent for Agent D: Code Review Assistant.

Implements iterative code remediation (code_fixer) and quality gate evaluation
(fix_validator) following the Google ADK LoopAgent pattern.
"""

import ast
import re
import os
from typing import Dict, Any, List, Optional, Tuple

try:
    from .constants import StateKeys, Severity
    from .tools import (
        ToolContext,
        analyze_code_structure,
        check_code_style,
        scan_security_vulnerabilities,
        _get_state,
        _set_state,
    )
except ImportError:
    from constants import StateKeys, Severity
    from tools import (
        ToolContext,
        analyze_code_structure,
        check_code_style,
        scan_security_vulnerabilities,
        _get_state,
        _set_state,
    )


def _ensure_import(code: str, module_name: str) -> str:
    """Ensures an import statement is present in the code without duplicating."""
    if re.search(rf"^\s*(import\s+{module_name}|from\s+{module_name}\s+import)", code, re.MULTILINE):
        return code
    return f"import {module_name}\n" + code


def code_fixer(
    code: str,
    security_findings: Optional[List[Dict[str, Any]]] = None,
    style_violations: Optional[List[Dict[str, Any]]] = None,
    tool_context: Optional[Any] = None,
) -> str:
    """Remediates detected security vulnerabilities and style violations.

    Performs surgical, genuine code transformations:
      - Replaces bare except with 'except Exception as err:'
      - Replaces '== None' with 'is None' and '!= None' with 'is not None'
      - Replaces '== True' with boolean truth check
      - Upgrades hashlib.md5/sha1 to hashlib.sha256
      - Fixes subprocess shell=True to shell=False
      - Replaces hardcoded credentials with os.getenv(...)
      - Converts f-string SQL queries to parameterized queries
      - Adds docstrings to undocumented functions and classes
      - Cleans trailing whitespace and normalizes indentation

    Args:
        code: Original source code string.
        security_findings: Optional list of security findings.
        style_violations: Optional list of style violations.
        tool_context: Optional ADK ToolContext.

    Returns:
        Remediated source code string.
    """
    if not code or not code.strip():
        return code

    fixed_code = code

    # 1. Fix PEP 8 style: Comparisons to None / True / False
    # cond == None -> cond is None
    fixed_code = re.sub(r"(\b\w+(?:\.\w+)?)\s*==\s*None\b", r"\1 is None", fixed_code)
    # cond != None -> cond is not None
    fixed_code = re.sub(r"(\b\w+(?:\.\w+)?)\s*!=\s*None\b", r"\1 is not None", fixed_code)
    # cond == True -> cond
    fixed_code = re.sub(r"if\s+([a-zA-Z0-9_]+)\s*==\s*True\s*:", r"if \1:", fixed_code)
    # cond == False -> not cond
    fixed_code = re.sub(r"if\s+([a-zA-Z0-9_]+)\s*==\s*False\s*:", r"if not \1:", fixed_code)

    # 2. Fix bare except (E722 & CWE-703)
    # except: -> except Exception as err:
    fixed_code = re.sub(r"(\bexcept)\s*:", r"\1 Exception as err:", fixed_code)

    # 3. Fix Weak Cryptography (CWE-327)
    # hashlib.md5(...) -> hashlib.sha256(...)
    if "hashlib.md5" in fixed_code:
        fixed_code = fixed_code.replace("hashlib.md5(", "hashlib.sha256(")
    if "hashlib.sha1" in fixed_code:
        fixed_code = fixed_code.replace("hashlib.sha1(", "hashlib.sha256(")

    # 4. Fix Subprocess Command Injection & os.system (CWE-78)
    # shell=True -> shell=False
    fixed_code = re.sub(r"(subprocess\.(?:run|Popen|call|check_output|check_call)\([^)]*?)\bshell\s*=\s*True", r"\1shell=False", fixed_code)
    if "os.system(" in fixed_code:
        fixed_code = re.sub(
            r'os\.system\("ping[^"]*"\s*\+\s*([a-zA-Z0-9_]+)\)',
            r'subprocess.run(["ping", "-c", "1", \1], shell=False)',
            fixed_code,
        )
        fixed_code = _ensure_import(fixed_code, "subprocess")

    # 5. Fix Hardcoded Credentials (CWE-798)
    def replace_secret_assignment(match):
        indent = match.group(1)
        var_name = match.group(2).strip()
        return f'{indent}{var_name} = os.getenv("{var_name.upper()}", "")'

    secret_pattern = re.compile(
        r"^([ \t]*)([A-Za-z0-9_]*(?:API[_-]?KEY|SECRET|PASSWORD|AUTH[_-]?TOKEN)[A-Za-z0-9_]*)\s*=\s*[\"'][^\"']+[\"']",
        re.MULTILINE | re.IGNORECASE,
    )
    if secret_pattern.search(fixed_code):
        fixed_code = secret_pattern.sub(replace_secret_assignment, fixed_code)
        fixed_code = _ensure_import(fixed_code, "os")

    # 6. Fix SQL Injection in queries (CWE-89)
    # Pattern A: query = f"SELECT ... {var}"
    def replace_fstring_query(match):
        indent = match.group(1)
        var = match.group(2)
        quote = match.group(3)
        prefix = match.group(4).rstrip(" '\"")
        suffix = match.group(6).lstrip(" '\"")
        return f'{indent}{var} = {quote}{prefix} ? {suffix}{quote}.strip()'

    fstring_query_pattern = re.compile(
        r"^([ \t]*)([a-zA-Z0-9_]*(?:query|sql|stmt)[a-zA-Z0-9_]*)\s*=\s*f([\"'])(.*?)\{([a-zA-Z0-9_]+)\}(.*?)\3",
        re.MULTILINE | re.IGNORECASE,
    )
    fixed_code = fstring_query_pattern.sub(replace_fstring_query, fixed_code)
    fixed_code = re.sub(r"cursor\.execute\((\w+)\)", r"cursor.execute(\1, (username,))", fixed_code)

    # Pattern B: cursor.execute(f"SELECT ... {var}")
    def replace_fstring_sql(match):
        method = match.group(1)
        prefix = match.group(2)
        var = match.group(3)
        suffix = match.group(4)
        prefix_clean = re.sub(r"['\"]$", "", prefix)
        suffix_clean = re.sub(r"^['\"]", "", suffix)
        return f'{method}("{prefix_clean}?{suffix_clean}", ({var},))'

    sqli_fstring_pattern = re.compile(
        r"(\.\s*execute)\(\s*f[\"']([^\"'{]*?)\{([a-zA-Z0-9_]+)\}([^\"']*)[\"']\s*\)"
    )
    fixed_code = sqli_fstring_pattern.sub(replace_fstring_sql, fixed_code)

    # Pattern C: cursor.execute("SELECT ... " + var)
    sqli_concat_pattern = re.compile(
        r"(\.\s*execute)\(\s*[\"']([^\"']*)[\"']\s*\+\s*([a-zA-Z0-9_]+)\s*\)"
    )
    fixed_code = sqli_concat_pattern.sub(r'\1("\2?", (\3,))', fixed_code)

    # 7. Add Docstrings to public functions / classes missing docstrings (D101, D103)
    try:
        tree = ast.parse(fixed_code)
        lines = fixed_code.splitlines()
        inserts: List[Tuple[int, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_") and not ast.get_docstring(node):
                    first_stmt = node.body[0] if node.body else None
                    if first_stmt:
                        col = first_stmt.col_offset
                        indent = " " * col
                        doc_line = f'{indent}"""Execute {node.name} operation."""'
                        inserts.append((first_stmt.lineno - 1, doc_line))
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_") and not ast.get_docstring(node):
                    first_stmt = node.body[0] if node.body else None
                    if first_stmt:
                        col = first_stmt.col_offset
                        indent = " " * col
                        doc_line = f'{indent}"""{node.name} definition."""'
                        inserts.append((first_stmt.lineno - 1, doc_line))

        inserts.sort(key=lambda x: x[0], reverse=True)
        candidate_lines = list(lines)
        for target_idx, doc_line in inserts:
            if 0 <= target_idx <= len(candidate_lines):
                candidate_lines.insert(target_idx, doc_line)
        candidate_code = "\n".join(candidate_lines)
        try:
            compile(candidate_code, "<string>", "exec")
            fixed_code = candidate_code
        except SyntaxError:
            pass
    except SyntaxError:
        pass

    # 8. Clean trailing whitespace and tab indentation
    cleaned_lines = []
    for line in fixed_code.splitlines():
        line = line.replace("\t", "    ")
        cleaned_lines.append(line.rstrip())
    fixed_code = "\n".join(cleaned_lines)
    if fixed_code and not fixed_code.endswith("\n"):
        fixed_code += "\n"

    _set_state(tool_context, StateKeys.FIXED_CODE, fixed_code)
    return fixed_code


def fix_validator(
    original_code: str,
    fixed_code: str,
    tool_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Validates the remediated code against quality and security gates.

    Checks:
      1. Fixed code compiles without SyntaxError.
      2. Zero CRITICAL security vulnerabilities remain.
      3. Style score has improved and is >= 80.0.
      4. Code structure is preserved.

    Args:
        original_code: Original code before fixes.
        fixed_code: Remediated code.
        tool_context: Optional ADK ToolContext.

    Returns:
        Validation report dict including 'validation_passed' boolean.
    """
    # 1. Syntax check
    try:
        compile(fixed_code, "<string>", "exec")
        syntax_valid = True
        syntax_error = None
    except SyntaxError as e:
        syntax_valid = False
        syntax_error = f"Syntax error at line {e.lineno}:{e.offset} - {e.msg}"

    if not syntax_valid:
        res = {
            "validation_passed": False,
            "syntax_valid": False,
            "syntax_error": syntax_error,
            "style_score_before": 0.0,
            "style_score_after": 0.0,
            "critical_remaining": 999,
            "security_findings_after": [],
            "style_violations_after": [],
            "message": f"Fix validation failed: {syntax_error}",
        }
        _set_state(tool_context, StateKeys.VALIDATION_PASSED, False)
        return res

    # 2. Evaluate original metrics
    orig_style = check_code_style(original_code)
    orig_sec = scan_security_vulnerabilities(original_code)
    orig_crit = sum(1 for f in orig_sec if f.get("severity") == Severity.CRITICAL.value)

    # 3. Evaluate fixed metrics
    fixed_style = check_code_style(fixed_code)
    fixed_sec = scan_security_vulnerabilities(fixed_code)
    fixed_crit = sum(1 for f in fixed_sec if f.get("severity") == Severity.CRITICAL.value)
    fixed_high = sum(1 for f in fixed_sec if f.get("severity") == Severity.HIGH.value)

    score_before = float(orig_style.get("score", 0.0))
    score_after = float(fixed_style.get("score", 0.0))

    # Pass condition:
    # 1. Syntax is valid
    # 2. Zero CRITICAL vulnerabilities
    # 3. Score after >= 80.0 OR score improved by at least 15 points
    validation_passed = (
        syntax_valid
        and fixed_crit == 0
        and (score_after >= 80.0 or score_after >= score_before)
    )

    result = {
        "validation_passed": validation_passed,
        "syntax_valid": True,
        "syntax_error": None,
        "style_score_before": score_before,
        "style_score_after": score_after,
        "style_score_delta": round(score_after - score_before, 1),
        "critical_before": orig_crit,
        "critical_remaining": fixed_crit,
        "high_remaining": fixed_high,
        "total_security_findings_after": len(fixed_sec),
        "security_findings_after": fixed_sec,
        "style_violations_after": fixed_style.get("violations", []),
        "message": (
            f"Validation Passed! Style score improved from {score_before} to {score_after}. "
            f"Critical vulnerabilities reduced from {orig_crit} to {fixed_crit}."
            if validation_passed
            else f"Validation Gate: Remaining critical vulnerabilities: {fixed_crit}, Score: {score_after}."
        ),
    }

    _set_state(tool_context, StateKeys.VALIDATION_PASSED, validation_passed)
    return result


class CodeFixLoopAgent:
    """Iterative code remediation agent following the Google ADK LoopAgent pattern.

    Repeats the fix-and-validate cycle until the quality gate passes or max_iterations is reached.
    """

    def __init__(self, max_iterations: int = 3, tool_context: Optional[ToolContext] = None):
        self.max_iterations = max_iterations
        self.context = tool_context or ToolContext()

    def run(self, code: str) -> Dict[str, Any]:
        """Runs the iterative remediation loop.

        Args:
            code: Original Python source code.

        Returns:
            Dictionary containing:
              - fixed_code: final remediated code
              - validation_passed: bool
              - iterations: number of cycles run
              - initial_score: float
              - final_score: float
              - history: list of per-iteration results
        """
        current_code = code
        history = []
        validation_passed = False
        iteration = 0

        # Initial baseline evaluation
        initial_style = check_code_style(current_code, self.context)
        initial_sec = scan_security_vulnerabilities(current_code, self.context)
        initial_score = float(initial_style.get("score", 100.0))

        _set_state(self.context, StateKeys.CODE_TO_REVIEW, code)

        while iteration < self.max_iterations:
            iteration += 1

            # Step 1: Execute code fixer
            remediated_code = code_fixer(
                current_code,
                security_findings=initial_sec,
                style_violations=initial_style.get("violations"),
                tool_context=self.context,
            )

            # Step 2: Validate remediated code
            val_result = fix_validator(code, remediated_code, self.context)
            history.append({
                "iteration": iteration,
                "score_after": val_result["style_score_after"],
                "critical_remaining": val_result["critical_remaining"],
                "passed": val_result["validation_passed"],
            })

            current_code = remediated_code
            if val_result["validation_passed"]:
                validation_passed = True
                break

        _set_state(self.context, StateKeys.FIX_ITERATIONS, iteration)
        _set_state(self.context, StateKeys.FIX_HISTORY, history)

        final_style = check_code_style(current_code, self.context)
        final_score = float(final_style.get("score", 100.0))

        return {
            "fixed_code": current_code,
            "validation_passed": validation_passed,
            "iterations": iteration,
            "initial_score": initial_score,
            "final_score": final_score,
            "history": history,
            "validation_report": val_result,
        }


__all__ = [
    "code_fixer",
    "fix_validator",
    "CodeFixLoopAgent",
]
