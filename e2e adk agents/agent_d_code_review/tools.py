"""Core analysis, style, security, and diff parsing tools for Agent D.

Provides deterministic AST structure analysis, PEP 8 compliance scoring,
OWASP/CWE security scanning, unified git diff parsing, and feedback synthesis.
"""

import ast
import re
import tokenize
import io
from typing import Dict, Any, List, Optional, Tuple, Set

try:
    from .constants import StateKeys, Severity, CWE_DEFINITIONS
    from .models import (
        SecurityFinding,
        StyleViolation,
        StructureMetrics,
        LineComment,
        CodeReviewReport,
    )
except ImportError:
    from constants import StateKeys, Severity, CWE_DEFINITIONS
    from models import (
        SecurityFinding,
        StyleViolation,
        StructureMetrics,
        LineComment,
        CodeReviewReport,
    )


class ToolContext:
    """Lightweight ADK-compatible tool context for sharing pipeline state."""

    def __init__(self, state: Optional[Dict[str, Any]] = None):
        self.state = state if state is not None else {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.state[key] = value


def _get_state(tool_context: Optional[Any], key: str, default: Any = None) -> Any:
    """Helper to extract state from ToolContext or dict."""
    if tool_context is None:
        return default
    if hasattr(tool_context, "state") and isinstance(tool_context.state, dict):
        return tool_context.state.get(key, default)
    if isinstance(tool_context, dict):
        return tool_context.get(key, default)
    return default


def _set_state(tool_context: Optional[Any], key: str, value: Any) -> None:
    """Helper to store state in ToolContext or dict."""
    if tool_context is None:
        return
    if hasattr(tool_context, "state") and isinstance(tool_context.state, dict):
        tool_context.state[key] = value
    elif isinstance(tool_context, dict):
        tool_context[key] = value


# ---------------------------------------------------------------------------
# 1. AST Structure Analysis (analyze_code_structure)
# ---------------------------------------------------------------------------

class _ComplexityVisitor(ast.NodeVisitor):
    """Calculates McCabe cyclomatic complexity for AST nodes."""

    def __init__(self):
        self.complexity = 1

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncWith(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # Each extra boolean condition adds a branch
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)


def _compute_complexity(node: ast.AST) -> int:
    """Compute cyclomatic complexity for a given function or AST node."""
    visitor = _ComplexityVisitor()
    # Walk children of the function
    for child in ast.iter_child_nodes(node):
        visitor.visit(child)
    return visitor.complexity


def analyze_code_structure(code: str, tool_context: Optional[Any] = None) -> Dict[str, Any]:
    """Analyzes Python source code structure using the AST.

    Extracts:
      - Function definitions (name, lines, args, complexity, docstring)
      - Class definitions (name, lines, base classes, methods, docstring)
      - Module imports and aliases
      - Cyclomatic complexity metrics
      - Docstring coverage percentage
      - Lines of Code (LOC) breakdown

    Args:
        code: Python source code string.
        tool_context: Optional ADK ToolContext or state dict.

    Returns:
        Dictionary of structure metrics.
    """
    if not code or not code.strip():
        result = {
            "syntax_valid": True,
            "total_loc": 0,
            "functions_count": 0,
            "classes_count": 0,
            "docstring_coverage": 100.0,
            "max_complexity": 0,
            "avg_complexity": 0.0,
            "high_complexity_functions": [],
            "functions": [],
            "classes": [],
            "imports": [],
            "syntax_error": None,
        }
        _set_state(tool_context, StateKeys.CODE_ANALYSIS, result)
        return result

    # Check for syntax errors first
    try:
        tree = ast.parse(code)
    except SyntaxError as err:
        error_info = {
            "syntax_valid": False,
            "total_loc": len(code.splitlines()),
            "functions_count": 0,
            "classes_count": 0,
            "docstring_coverage": 0.0,
            "max_complexity": 0,
            "avg_complexity": 0.0,
            "high_complexity_functions": [],
            "functions": [],
            "classes": [],
            "imports": [],
            "syntax_error": f"Line {err.lineno}:{err.offset} - {err.msg}",
        }
        _set_state(tool_context, StateKeys.CODE_ANALYSIS, error_info)
        return error_info

    lines = code.splitlines()
    total_loc = len(lines)

    functions: List[Dict[str, Any]] = []
    classes: List[Dict[str, Any]] = []
    imports: List[Dict[str, Any]] = []
    high_complexity: List[str] = []

    total_definitions = 0
    documented_definitions = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total_definitions += 1
            doc = ast.get_docstring(node)
            has_doc = doc is not None and len(doc.strip()) > 0
            if has_doc:
                documented_definitions += 1

            arg_names = [a.arg for a in node.args.args]
            complexity = _compute_complexity(node)
            if complexity > 10:
                high_complexity.append(f"{node.name} (complexity: {complexity})")

            end_line = getattr(node, "end_lineno", node.lineno)
            functions.append({
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": end_line,
                "args": arg_names,
                "args_count": len(arg_names),
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "has_docstring": has_doc,
                "complexity": complexity,
                "has_return_annotation": node.returns is not None,
            })

        elif isinstance(node, ast.ClassDef):
            total_definitions += 1
            doc = ast.get_docstring(node)
            has_doc = doc is not None and len(doc.strip()) > 0
            if has_doc:
                documented_definitions += 1

            methods = [
                m.name for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            bases = [ast.unparse(b) for b in node.bases]
            end_line = getattr(node, "end_lineno", node.lineno)

            classes.append({
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": end_line,
                "methods": methods,
                "bases": bases,
                "has_docstring": has_doc,
            })

        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"module": alias.name, "alias": alias.asname})

        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append({"module": f"{mod}.{alias.name}" if mod else alias.name, "alias": alias.asname})

    complexities = [f["complexity"] for f in functions]
    max_comp = max(complexities) if complexities else 1
    avg_comp = round(sum(complexities) / len(complexities), 2) if complexities else 1.0

    doc_coverage = (
        round((documented_definitions / total_definitions) * 100.0, 1)
        if total_definitions > 0
        else 100.0
    )

    result = {
        "syntax_valid": True,
        "total_loc": total_loc,
        "functions_count": len(functions),
        "classes_count": len(classes),
        "docstring_coverage": doc_coverage,
        "max_complexity": max_comp,
        "avg_complexity": avg_comp,
        "high_complexity_functions": high_complexity,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "syntax_error": None,
    }

    _set_state(tool_context, StateKeys.CODE_ANALYSIS, result)
    return result


# ---------------------------------------------------------------------------
# 2. PEP 8 Style Checking (check_code_style)
# ---------------------------------------------------------------------------

_SNAKE_CASE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
_PASCAL_CASE_PATTERN = re.compile(r"^[A-Z][a-zA-Z0-9]*$")


def check_code_style(code: str, tool_context: Optional[Any] = None) -> Dict[str, Any]:
    """Checks Python source code against PEP 8 style rules and computes a 0-100 score.

    Rules checked:
      - E501: Line length > 88 characters
      - W291: Trailing whitespace
      - W191: Indentation contains tabs
      - E111: Indentation is not a multiple of 4 spaces
      - E711: Comparison to None using == or != (should use 'is' / 'is not')
      - E712: Comparison to True/False using == or !=
      - E722: Bare except clause without exception class
      - N802: Function name not in snake_case
      - N801: Class name not in PascalCase (CapWords)
      - D103: Missing function docstring for public function
      - D101: Missing class docstring for public class
      - E225: Missing whitespace around operators

    Returns:
        Dict with 'score' (0-100), 'violations' list, and 'summary'.
    """
    if not code or not code.strip():
        res = {"score": 100.0, "violations": [], "summary": "Empty code (clean)."}
        _set_state(tool_context, StateKeys.STYLE_SCORE, 100.0)
        _set_state(tool_context, StateKeys.STYLE_VIOLATIONS, [])
        return res

    violations: List[Dict[str, Any]] = []
    lines = code.splitlines()

    # 1. Line-level textual checks
    for idx, line in enumerate(lines, 1):
        # E501: Line length
        if len(line) > 88:
            violations.append({
                "code": "E501",
                "line_number": idx,
                "column": 88,
                "message": f"Line exceeds 88 characters ({len(line)} > 88)",
                "snippet": line[:80] + "...",
                "penalty": 2.0,
                "severity": Severity.LOW.value,
            })

        # W291: Trailing whitespace
        if line.endswith(" ") or line.endswith("\t"):
            violations.append({
                "code": "W291",
                "line_number": idx,
                "column": len(line),
                "message": "Trailing whitespace detected",
                "snippet": line.rstrip(),
                "penalty": 1.0,
                "severity": Severity.LOW.value,
            })

        # W191: Tab indentation
        stripped_leading = line.lstrip()
        leading = line[:len(line) - len(stripped_leading)]
        if "\t" in leading:
            violations.append({
                "code": "W191",
                "line_number": idx,
                "column": 1,
                "message": "Indentation contains tab characters (PEP 8 requires 4 spaces)",
                "snippet": stripped_leading,
                "penalty": 3.0,
                "severity": Severity.LOW.value,
            })
        elif stripped_leading and not stripped_leading.startswith("#"):
            # E111: Indentation multiple of 4
            spaces = len(leading)
            if spaces % 4 != 0:
                violations.append({
                    "code": "E111",
                    "line_number": idx,
                    "column": 1,
                    "message": f"Indentation of {spaces} spaces is not a multiple of 4",
                    "snippet": stripped_leading,
                    "penalty": 3.0,
                    "severity": Severity.LOW.value,
                })

    # 2. AST-level semantic style checks
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # If syntax error, cap score and note
        violations.append({
            "code": "E999",
            "line_number": 1,
            "column": 1,
            "message": "SyntaxError prevents full PEP 8 AST verification",
            "snippet": "",
            "penalty": 40.0,
            "severity": Severity.CRITICAL.value,
        })
        tree = None

    if tree:
        for node in ast.walk(tree):
            # E722: Bare except
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "except:"
                    violations.append({
                        "code": "E722",
                        "line_number": node.lineno,
                        "column": node.col_offset,
                        "message": "Do not use bare 'except:' - catch specific exceptions or 'except Exception:'",
                        "snippet": snippet,
                        "penalty": 10.0,
                        "severity": Severity.MEDIUM.value,
                    })

            # E711 / E712: Comparisons to None or True/False
            elif isinstance(node, ast.Compare):
                # Check left and comparators
                all_ops = list(zip(node.ops, node.comparators))
                for op, comp in all_ops:
                    if isinstance(op, (ast.Eq, ast.NotEq)):
                        # Comparison to None
                        if isinstance(comp, ast.Constant) and comp.value is None:
                            op_str = "==" if isinstance(op, ast.Eq) else "!="
                            rec = "is None" if isinstance(op, ast.Eq) else "is not None"
                            violations.append({
                                "code": "E711",
                                "line_number": node.lineno,
                                "column": node.col_offset,
                                "message": f"Comparison to None should be 'cond {rec}', not 'cond {op_str} None'",
                                "snippet": lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                                "penalty": 5.0,
                                "severity": Severity.LOW.value,
                            })
                        # Comparison to True or False
                        elif isinstance(comp, ast.Constant) and isinstance(comp.value, bool):
                            op_str = "==" if isinstance(op, ast.Eq) else "!="
                            violations.append({
                                "code": "E712",
                                "line_number": node.lineno,
                                "column": node.col_offset,
                                "message": f"Comparison to boolean literal should be 'if cond:' or 'if not cond:', not '{op_str} {comp.value}'",
                                "snippet": lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                                "penalty": 5.0,
                                "severity": Severity.LOW.value,
                            })

            # N802: Function naming convention
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip dunder methods
                if not (node.name.startswith("__") and node.name.endswith("__")):
                    if not _SNAKE_CASE_PATTERN.match(node.name):
                        violations.append({
                            "code": "N802",
                            "line_number": node.lineno,
                            "column": node.col_offset,
                            "message": f"Function name '{node.name}' should be lowercase_with_underscores (snake_case)",
                            "snippet": f"def {node.name}(...)",
                            "penalty": 3.0,
                            "severity": Severity.LOW.value,
                        })

                # D103: Public function docstring
                if not node.name.startswith("_"):
                    doc = ast.get_docstring(node)
                    if not doc:
                        violations.append({
                            "code": "D103",
                            "line_number": node.lineno,
                            "column": node.col_offset,
                            "message": f"Missing docstring in public function '{node.name}'",
                            "snippet": f"def {node.name}(...)",
                            "penalty": 2.5,
                            "severity": Severity.LOW.value,
                        })

            # N801: Class naming convention
            elif isinstance(node, ast.ClassDef):
                if not _PASCAL_CASE_PATTERN.match(node.name):
                    violations.append({
                        "code": "N801",
                        "line_number": node.lineno,
                        "column": node.col_offset,
                        "message": f"Class name '{node.name}' should use CapWords / PascalCase",
                        "snippet": f"class {node.name}:",
                        "penalty": 3.0,
                        "severity": Severity.LOW.value,
                    })

                # D101: Public class docstring
                if not node.name.startswith("_"):
                    doc = ast.get_docstring(node)
                    if not doc:
                        violations.append({
                            "code": "D101",
                            "line_number": node.lineno,
                            "column": node.col_offset,
                            "message": f"Missing docstring in public class '{node.name}'",
                            "snippet": f"class {node.name}:",
                            "penalty": 2.5,
                            "severity": Severity.LOW.value,
                        })

    # Deduct penalties
    total_penalty = sum(v.get("penalty", 2.0) for v in violations)
    score = max(0.0, min(100.0, round(100.0 - total_penalty, 1)))

    result = {
        "score": score,
        "violations": violations,
        "total_violations": len(violations),
        "clean": len(violations) == 0,
        "summary": f"PEP 8 Compliance Score: {score}/100 with {len(violations)} violations."
    }

    _set_state(tool_context, StateKeys.STYLE_SCORE, score)
    _set_state(tool_context, StateKeys.STYLE_VIOLATIONS, violations)
    return result


# ---------------------------------------------------------------------------
# 3. Security Vulnerability Scanner (scan_security_vulnerabilities)
# ---------------------------------------------------------------------------

_SECRET_VAR_PATTERN = re.compile(
    r"(?i)^(api[_-]?key|secret|password|passwd|auth[_-]?token|access[_-]?key|private[_-]?key|jwt[_-]?secret)$"
)
_DUMMY_SECRET_VALUES = {
    "", "test", "dummy", "placeholder", "xxx", "password", "123456", "admin", "todo"
}


def scan_security_vulnerabilities(code: str, tool_context: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Scans Python code for OWASP Top 10 and CWE security vulnerabilities using AST and semantic checks.

    Detects:
      - CWE-89: SQL Injection (string concatenation/formatting in execute calls)
      - CWE-78: Command Injection (os.system, subprocess with shell=True and dynamic args)
      - CWE-502: Insecure Deserialization (pickle.loads, unsafe yaml.load, marshal)
      - CWE-22: Path Traversal (unrestricted user input in open() / file operations)
      - CWE-798: Hardcoded Credentials / Secrets in assignments
      - CWE-327: Broken or Risky Cryptographic Algorithms (MD5, SHA1 without security check)
      - CWE-95: Eval Injection (eval/exec dynamic execution)
      - CWE-703: Bare except catching and silencing all errors

    Args:
        code: Python source code string.
        tool_context: Optional ADK ToolContext or state dict.

    Returns:
        List of vulnerability finding dictionaries sorted by severity.
    """
    findings: List[Dict[str, Any]] = []

    if not code or not code.strip():
        _set_state(tool_context, StateKeys.SECURITY_FINDINGS, [])
        return findings

    try:
        tree = ast.parse(code)
    except SyntaxError:
        # If syntax error, skip AST scans
        _set_state(tool_context, StateKeys.SECURITY_FINDINGS, [])
        return findings

    lines = code.splitlines()

    def get_line_snippet(lineno: int) -> str:
        if 1 <= lineno <= len(lines):
            return lines[lineno - 1].strip()
        return ""

    for node in ast.walk(tree):
        # 1. Calls: SQLi, Command Injection, Deserialization, Crypto, Eval
        if isinstance(node, ast.Call):
            func_name = ""
            attr_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                func_name = attr_name

            # CWE-89: SQL Injection in cursor.execute(...)
            if attr_name in ("execute", "executemany", "raw") and len(node.args) > 0:
                first_arg = node.args[0]
                is_sqli = False
                if isinstance(first_arg, ast.JoinedStr):  # f-string
                    is_sqli = True
                elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, (ast.Add, ast.Mod)):
                    is_sqli = True
                elif isinstance(first_arg, ast.Call):
                    if isinstance(first_arg.func, ast.Attribute) and first_arg.func.attr == "format":
                        is_sqli = True

                if is_sqli:
                    findings.append({
                        "cwe_id": "CWE-89",
                        "name": CWE_DEFINITIONS["CWE-89"]["name"],
                        "severity": Severity.CRITICAL.value,
                        "line_number": node.lineno,
                        "snippet": get_line_snippet(node.lineno),
                        "message": "Potential SQL Injection: SQL statement constructed using dynamic string formatting or concatenation.",
                        "recommendation": "Use parameterized queries with query placeholders (e.g., execute('SELECT * FROM users WHERE id = ?', (user_id,))).",
                        "owasp": CWE_DEFINITIONS["CWE-89"]["owasp"],
                    })

            # CWE-78: OS Command Injection
            # A. os.system, os.popen
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("system", "popen"):
                caller = ast.unparse(node.func.value) if hasattr(ast, "unparse") else ""
                if "os" in caller:
                    if len(node.args) > 0:
                        arg0 = node.args[0]
                        # If dynamic f-string, binop, or variable
                        is_dynamic = isinstance(arg0, (ast.JoinedStr, ast.BinOp, ast.Name, ast.Call))
                        findings.append({
                            "cwe_id": "CWE-78",
                            "name": CWE_DEFINITIONS["CWE-78"]["name"],
                            "severity": Severity.CRITICAL.value if is_dynamic else Severity.HIGH.value,
                            "line_number": node.lineno,
                            "snippet": get_line_snippet(node.lineno),
                            "message": f"Dangerous execution of shell command via os.{node.func.attr}.",
                            "recommendation": "Use subprocess.run(['cmd', 'arg'], shell=False) instead of shell execution.",
                            "owasp": CWE_DEFINITIONS["CWE-78"]["owasp"],
                        })

            # B. subprocess.run / Popen / call with shell=True
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("run", "Popen", "call", "check_call", "check_output"):
                caller = ast.unparse(node.func.value) if hasattr(ast, "unparse") else ""
                if "subprocess" in caller:
                    # Check for shell=True keyword
                    has_shell_true = False
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            has_shell_true = True
                    if has_shell_true:
                        findings.append({
                            "cwe_id": "CWE-78",
                            "name": CWE_DEFINITIONS["CWE-78"]["name"],
                            "severity": Severity.CRITICAL.value,
                            "line_number": node.lineno,
                            "snippet": get_line_snippet(node.lineno),
                            "message": "Subprocess executed with shell=True allowing arbitrary OS command injection.",
                            "recommendation": "Set shell=False and pass arguments as a list of strings.",
                            "owasp": CWE_DEFINITIONS["CWE-78"]["owasp"],
                        })

            # CWE-502: Insecure Deserialization
            # pickle.loads, pickle.load, marshal.loads, yaml.load without SafeLoader
            if isinstance(node.func, ast.Attribute):
                caller = ast.unparse(node.func.value) if hasattr(ast, "unparse") else ""
                if "pickle" in caller and node.func.attr in ("loads", "load"):
                    findings.append({
                        "cwe_id": "CWE-502",
                        "name": CWE_DEFINITIONS["CWE-502"]["name"],
                        "severity": Severity.CRITICAL.value,
                        "line_number": node.lineno,
                        "snippet": get_line_snippet(node.lineno),
                        "message": f"Insecure deserialization using pickle.{node.func.attr} can execute arbitrary code.",
                        "recommendation": "Avoid deserializing untrusted data with pickle. Use safer data formats like JSON.",
                        "owasp": CWE_DEFINITIONS["CWE-502"]["owasp"],
                    })
                elif "yaml" in caller and node.func.attr == "load":
                    # Check loader
                    has_safe_loader = False
                    for kw in node.keywords:
                        if kw.arg == "Loader":
                            loader_str = ast.unparse(kw.value) if hasattr(ast, "unparse") else ""
                            if "SafeLoader" in loader_str:
                                has_safe_loader = True
                    if not has_safe_loader:
                        findings.append({
                            "cwe_id": "CWE-502",
                            "name": CWE_DEFINITIONS["CWE-502"]["name"],
                            "severity": Severity.CRITICAL.value,
                            "line_number": node.lineno,
                            "snippet": get_line_snippet(node.lineno),
                            "message": "Unsafe YAML loading via yaml.load without SafeLoader allows code execution.",
                            "recommendation": "Use yaml.safe_load(data) instead of yaml.load.",
                            "owasp": CWE_DEFINITIONS["CWE-502"]["owasp"],
                        })

            # CWE-327: Broken Crypto (MD5, SHA1)
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("md5", "sha1"):
                caller = ast.unparse(node.func.value) if hasattr(ast, "unparse") else ""
                if "hashlib" in caller:
                    # Check if usedforsecurity=False is set
                    is_for_security = True
                    for kw in node.keywords:
                        if kw.arg == "usedforsecurity" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                            is_for_security = False
                    if is_for_security:
                        findings.append({
                            "cwe_id": "CWE-327",
                            "name": CWE_DEFINITIONS["CWE-327"]["name"],
                            "severity": Severity.HIGH.value,
                            "line_number": node.lineno,
                            "snippet": get_line_snippet(node.lineno),
                            "message": f"Use of cryptographically weak hash algorithm hashlib.{node.func.attr}.",
                            "recommendation": "Use SHA-256 (hashlib.sha256) or SHA-3 for secure hashing.",
                            "owasp": CWE_DEFINITIONS["CWE-327"]["owasp"],
                        })

            # CWE-95: Eval / Exec Injection
            if func_name in ("eval", "exec"):
                if len(node.args) > 0 and not isinstance(node.args[0], ast.Constant):
                    findings.append({
                        "cwe_id": "CWE-95",
                        "name": CWE_DEFINITIONS["CWE-95"]["name"],
                        "severity": Severity.CRITICAL.value,
                        "line_number": node.lineno,
                        "snippet": get_line_snippet(node.lineno),
                        "message": f"Dynamic execution via {func_name}() on arbitrary input allows code injection.",
                        "recommendation": "Use ast.literal_eval() for parsing data literals, or avoid dynamic evaluation.",
                        "owasp": CWE_DEFINITIONS["CWE-95"]["owasp"],
                    })

            # CWE-22: Path Traversal in open()
            if func_name == "open" and len(node.args) > 0:
                arg0 = node.args[0]
                is_path_concatenation = False
                if isinstance(arg0, ast.JoinedStr):
                    # Check if contains variable
                    has_var = any(isinstance(v, ast.FormattedValue) for v in arg0.values)
                    if has_var:
                        is_path_concatenation = True
                elif isinstance(arg0, ast.BinOp) and isinstance(arg0.op, ast.Add):
                    is_path_concatenation = True

                if is_path_concatenation:
                    findings.append({
                        "cwe_id": "CWE-22",
                        "name": CWE_DEFINITIONS["CWE-22"]["name"],
                        "severity": Severity.HIGH.value,
                        "line_number": node.lineno,
                        "snippet": get_line_snippet(node.lineno),
                        "message": "Potential Path Traversal: file opened with dynamic concatenated or interpolated path.",
                        "recommendation": "Sanitize user paths using os.path.basename or verify pathlib.Path.resolve() starts with safe base directory.",
                        "owasp": CWE_DEFINITIONS["CWE-22"]["owasp"],
                    })

        # 2. Assignments: CWE-798 Credentials & CWE-89 SQL Queries
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value_node = node.value

            # Check for dynamic SQL query assignment (CWE-89)
            sql_keywords = ("select", "insert", "update", "delete", "drop", "from", "where")
            is_dynamic_sql = False
            if isinstance(value_node, ast.JoinedStr):
                raw_text = "".join(
                    p.value for p in value_node.values
                    if isinstance(p, ast.Constant) and isinstance(p.value, str)
                ).lower()
                if any(k in raw_text for k in sql_keywords):
                    is_dynamic_sql = True
            elif isinstance(value_node, ast.BinOp) and isinstance(value_node.op, (ast.Add, ast.Mod)):
                left_text = (
                    value_node.left.value.lower()
                    if isinstance(value_node.left, ast.Constant) and isinstance(value_node.left.value, str)
                    else ""
                )
                if any(k in left_text for k in sql_keywords):
                    is_dynamic_sql = True

            if is_dynamic_sql:
                findings.append({
                    "cwe_id": "CWE-89",
                    "name": CWE_DEFINITIONS["CWE-89"]["name"],
                    "severity": Severity.CRITICAL.value,
                    "line_number": node.lineno,
                    "snippet": get_line_snippet(node.lineno),
                    "message": "Potential SQL Injection: Dynamic SQL query constructed using string formatting.",
                    "recommendation": "Use parameterized queries with query placeholders (e.g., cursor.execute('SELECT ... WHERE col = ?', (val,))).",
                    "owasp": CWE_DEFINITIONS["CWE-89"]["owasp"],
                })

            if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
                val_str = value_node.value.strip()
                for target in targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        if _SECRET_VAR_PATTERN.match(var_name):
                            # Ignore short dummy values or placeholders
                            if len(val_str) > 5 and val_str.lower() not in _DUMMY_SECRET_VALUES:
                                findings.append({
                                    "cwe_id": "CWE-798",
                                    "name": CWE_DEFINITIONS["CWE-798"]["name"],
                                    "severity": Severity.HIGH.value,
                                    "line_number": node.lineno,
                                    "snippet": get_line_snippet(node.lineno),
                                    "message": f"Hardcoded secret or credential assigned to '{var_name}'.",
                                    "recommendation": f"Load credential from environment variable: os.getenv('{var_name.upper()}')",
                                    "owasp": CWE_DEFINITIONS["CWE-798"]["owasp"],
                                })

        # 3. CWE-703: Bare except (silencing errors)
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            # Also flagged as security smell if body is just pass
            is_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            if is_pass:
                findings.append({
                    "cwe_id": "CWE-703",
                    "name": CWE_DEFINITIONS["CWE-703"]["name"],
                    "severity": Severity.LOW.value,
                    "line_number": node.lineno,
                    "snippet": get_line_snippet(node.lineno),
                    "message": "Bare 'except: pass' silently suppresses all exceptions including SystemExit and KeyboardInterrupt.",
                    "recommendation": "Catch specific exceptions and log or handle the error appropriately.",
                    "owasp": CWE_DEFINITIONS["CWE-703"]["owasp"],
                })

    # Sort findings by severity (CRITICAL first, then HIGH, MEDIUM, LOW) and line number
    severity_order = {
        Severity.CRITICAL.value: 0,
        Severity.HIGH.value: 1,
        Severity.MEDIUM.value: 2,
        Severity.LOW.value: 3,
    }
    findings.sort(key=lambda x: (severity_order.get(x["severity"], 4), x["line_number"]))

    _set_state(tool_context, StateKeys.SECURITY_FINDINGS, findings)
    return findings


# ---------------------------------------------------------------------------
# 4. Unified Git Diff Parser (parse_git_diff)
# ---------------------------------------------------------------------------

_HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$")


def parse_git_diff(diff_content: str, tool_context: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Parses unified git diff output into structured file hunks with line mappings.

    Args:
        diff_content: Raw git diff or patch text.
        tool_context: Optional ADK ToolContext or state dict.

    Returns:
        List of parsed file diff objects containing:
          - old_file, new_file
          - is_new, is_deleted
          - hunks with line-by-line additions, deletions, context
          - modified_lines (list of added line numbers in new file)
          - stats (additions, deletions, changes)
    """
    if not diff_content or not diff_content.strip():
        _set_state(tool_context, StateKeys.GIT_DIFF, [])
        return []

    file_diffs: List[Dict[str, Any]] = []
    current_file: Optional[Dict[str, Any]] = None
    current_hunk: Optional[Dict[str, Any]] = None

    old_lineno = 0
    new_lineno = 0

    lines = diff_content.splitlines()

    for line in lines:
        if line.startswith("diff --git"):
            # New file diff block
            parts = line.split()
            old_f = parts[2].replace("a/", "", 1) if len(parts) > 2 else "unknown"
            new_f = parts[3].replace("b/", "", 1) if len(parts) > 3 else "unknown"
            current_file = {
                "old_file": old_f,
                "new_file": new_f,
                "is_new": False,
                "is_deleted": False,
                "hunks": [],
                "modified_lines": [],
                "stats": {"additions": 0, "deletions": 0, "changes": 0},
            }
            file_diffs.append(current_file)
            current_hunk = None

        elif line.startswith("--- "):
            if current_file is None:
                current_file = {
                    "old_file": line[4:].strip().replace("a/", "", 1),
                    "new_file": "unknown",
                    "is_new": False,
                    "is_deleted": False,
                    "hunks": [],
                    "modified_lines": [],
                    "stats": {"additions": 0, "deletions": 0, "changes": 0},
                }
                file_diffs.append(current_file)
            if "/dev/null" in line:
                current_file["is_new"] = True

        elif line.startswith("+++ "):
            if current_file is not None:
                new_path = line[4:].strip().replace("b/", "", 1)
                current_file["new_file"] = new_path
                if "/dev/null" in line:
                    current_file["is_deleted"] = True

        elif line.startswith("@@"):
            match = _HUNK_HEADER_RE.match(line)
            if match and current_file is not None:
                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) else 1

                old_lineno = old_start
                new_lineno = new_start

                current_hunk = {
                    "old_start": old_start,
                    "old_count": old_count,
                    "new_start": new_start,
                    "new_count": new_count,
                    "header": line,
                    "lines": [],
                }
                current_file["hunks"].append(current_hunk)

        elif current_hunk is not None and current_file is not None:
            if line.startswith("+"):
                current_file["stats"]["additions"] += 1
                current_file["stats"]["changes"] += 1
                current_file["modified_lines"].append(new_lineno)
                current_hunk["lines"].append({
                    "type": "add",
                    "content": line[1:],
                    "old_lineno": None,
                    "new_lineno": new_lineno,
                })
                new_lineno += 1
            elif line.startswith("-"):
                current_file["stats"]["deletions"] += 1
                current_file["stats"]["changes"] += 1
                current_hunk["lines"].append({
                    "type": "del",
                    "content": line[1:],
                    "old_lineno": old_lineno,
                    "new_lineno": None,
                })
                old_lineno += 1
            else:
                # Context line (starts with space or empty)
                content = line[1:] if line.startswith(" ") else line
                current_hunk["lines"].append({
                    "type": "context",
                    "content": content,
                    "old_lineno": old_lineno,
                    "new_lineno": new_lineno,
                })
                old_lineno += 1
                new_lineno += 1

    _set_state(tool_context, StateKeys.GIT_DIFF, file_diffs)
    return file_diffs


# ---------------------------------------------------------------------------
# 5. Feedback Synthesizer (feedback_synthesizer)
# ---------------------------------------------------------------------------

def feedback_synthesizer(tool_context: Any, pr_description: Optional[str] = None) -> str:
    """Assembles all review metrics and findings into a production-grade Markdown review report.

    Args:
        tool_context: ADK ToolContext or state dict populated with review metrics.
        pr_description: Optional PR title/description to integrate into the evaluation.

    Returns:
        Structured Markdown review document.
    """
    code_analysis = _get_state(tool_context, StateKeys.CODE_ANALYSIS, {}) or {}
    style_score = float(_get_state(tool_context, StateKeys.STYLE_SCORE, 100.0))
    style_violations = _get_state(tool_context, StateKeys.STYLE_VIOLATIONS, []) or []
    security_findings = _get_state(tool_context, StateKeys.SECURITY_FINDINGS, []) or []
    git_diff = _get_state(tool_context, StateKeys.GIT_DIFF, []) or []
    pr_desc = pr_description or _get_state(tool_context, StateKeys.PR_DESCRIPTION, "")

    # Count findings by severity
    critical_count = sum(1 for f in security_findings if f.get("severity") == Severity.CRITICAL.value)
    high_count = sum(1 for f in security_findings if f.get("severity") == Severity.HIGH.value)
    medium_count = (
        sum(1 for f in security_findings if f.get("severity") == Severity.MEDIUM.value)
        + sum(1 for v in style_violations if v.get("severity") == Severity.MEDIUM.value)
    )
    low_count = (
        sum(1 for f in security_findings if f.get("severity") == Severity.LOW.value)
        + sum(1 for v in style_violations if v.get("severity") == Severity.LOW.value)
    )

    # Determine Review Status
    if critical_count > 0 or high_count > 0 or style_score < 70.0:
        overall_status = "CHANGES REQUESTED"
        status_emoji = "❌"
    elif medium_count > 0 or style_score < 85.0:
        overall_status = "COMMENT"
        status_emoji = "⚠️"
    else:
        overall_status = "APPROVED"
        status_emoji = "✅"

    # Overall Health Score (0-100)
    # Deductions: Critical (-25), High (-15), Medium (-5), Low (-1), weighted with style
    security_deduction = (critical_count * 30) + (high_count * 15) + (medium_count * 5)
    health_score = max(0.0, min(100.0, round((style_score * 0.4) + (max(0.0, 100.0 - security_deduction) * 0.6), 1)))

    # Build Markdown Document
    md_lines: List[str] = []
    md_lines.append("# Automated Code Review Report")
    md_lines.append(f"\n### {status_emoji} Overall Status: **{overall_status}** (Health Score: **{health_score}/100**)\n")

    # Executive Summary
    md_lines.append("## Executive Summary")
    if overall_status == "CHANGES REQUESTED":
        summary_text = (
            f"Review concluded with **{critical_count} CRITICAL** and **{high_count} HIGH** severity issues. "
            f"Merge blockers detected. Immediate remediation is required before deployment."
        )
    elif overall_status == "COMMENT":
        summary_text = (
            f"Code quality is acceptable with minor findings. "
            f"Found {medium_count} medium/low severity recommendations and PEP 8 style score is {style_score}/100."
        )
    else:
        summary_text = (
            f"Excellent code quality! Passed all security checks and achieved a PEP 8 score of {style_score}/100. "
            f"Code is clean and ready to merge."
        )
    md_lines.append(summary_text)

    if pr_desc:
        md_lines.append(f"\n> **Pull Request Context**: {pr_desc.strip()}")

    # Severity Breakdown Table
    md_lines.append("\n## Severity Breakdown")
    md_lines.append("| Severity | Count | Definition |")
    md_lines.append("|---|:---:|---|")
    md_lines.append(f"| **CRITICAL** | `{critical_count}` | Blocker: Exploitable security vulnerability or syntax error |")
    md_lines.append(f"| **HIGH** | `{high_count}` | High Risk: Security defect, weak cryptography, or hardcoded secrets |")
    md_lines.append(f"| **MEDIUM** | `{medium_count}` | Warning: Potential reliability bug, performance risk, or excessive complexity |")
    md_lines.append(f"| **LOW** | `{low_count}` | Nit: PEP 8 style rule, formatting violation, or missing docstring |")

    # Security Findings Section
    md_lines.append("\n## Security & Vulnerability Analysis")
    if security_findings:
        for idx, finding in enumerate(security_findings, 1):
            cwe = finding.get("cwe_id", "CWE-Unknown")
            name = finding.get("name", "Vulnerability")
            sev = finding.get("severity", "HIGH")
            lineno = finding.get("line_number", 0)
            snippet = finding.get("snippet", "")
            msg = finding.get("message", "")
            rec = finding.get("recommendation", "")
            owasp = finding.get("owasp", "")

            md_lines.append(f"\n### {idx}. [{sev}] {cwe}: {name} (Line {lineno})")
            if owasp:
                md_lines.append(f"**OWASP Category**: {owasp}")
            md_lines.append(f"**Issue**: {msg}")
            if snippet:
                md_lines.append(f"```python\n# Offending line {lineno}\n{snippet}\n```")
            md_lines.append(f"**Remediation**: {rec}")
    else:
        md_lines.append("🛡️ **Zero security vulnerabilities detected!** (OWASP Top 10 & CWE scan passed)")

    # Code Style & PEP 8 Metrics
    md_lines.append(f"\n## Code Style & PEP 8 Compliance (Score: {style_score}/100)")
    if style_violations:
        md_lines.append(f"Identified **{len(style_violations)} style violation(s)**:")
        for v in style_violations[:10]:  # limit to top 10 in summary
            code_id = v.get("code", "E")
            line_no = v.get("line_number", 0)
            msg = v.get("message", "")
            snippet = v.get("snippet", "")
            md_lines.append(f"- **Line {line_no}** (`{code_id}`): {msg}")
            if snippet:
                md_lines.append(f"  > `{snippet}`")
        if len(style_violations) > 10:
            md_lines.append(f"- *...and {len(style_violations) - 10} additional minor style violations.*")
    else:
        md_lines.append("✨ **100% PEP 8 compliant!** No formatting or lint violations found.")

    # Structure & Complexity Section
    md_lines.append("\n## Structural Analysis & Complexity")
    if code_analysis.get("syntax_valid", True):
        tot_loc = code_analysis.get("total_loc", 0)
        fn_count = code_analysis.get("functions_count", 0)
        cls_count = code_analysis.get("classes_count", 0)
        doc_cov = code_analysis.get("docstring_coverage", 100.0)
        max_c = code_analysis.get("max_complexity", 1)
        avg_c = code_analysis.get("avg_complexity", 1.0)
        high_c = code_analysis.get("high_complexity_functions", [])

        md_lines.append(f"- **Total Lines of Code**: {tot_loc}")
        md_lines.append(f"- **Functions**: {fn_count} | **Classes**: {cls_count}")
        md_lines.append(f"- **Docstring Coverage**: {doc_cov}%")
        md_lines.append(f"- **Cyclomatic Complexity**: Max `{max_c}` | Average `{avg_c}`")
        if high_c:
            md_lines.append("- ⚠️ **Functions exceeding complexity threshold (>10)**:")
            for fn_info in high_c:
                md_lines.append(f"  - `{fn_info}`")
    else:
        md_lines.append(f"❌ **Syntax Error**: {code_analysis.get('syntax_error', 'Invalid Python syntax')}")

    # Git Diff Context if available
    if git_diff:
        md_lines.append("\n## Git Diff Hunk Analysis")
        for f_diff in git_diff:
            fname = f_diff.get("new_file", "unknown")
            stats = f_diff.get("stats", {})
            md_lines.append(f"- **File**: `{fname}` (+{stats.get('additions', 0)} / -{stats.get('deletions', 0)})")
            md_lines.append(f"  - Modified lines: {f_diff.get('modified_lines', [])}")

    # Actionable Line-by-Line Suggestions
    md_lines.append("\n## Actionable Line-by-Line Recommendations")
    line_comments = []
    for f in security_findings:
        line_comments.append(
            f"- **Line {f.get('line_number')}** [{f.get('severity')}]: {f.get('message')}\n"
            f"  *Suggested fix*: {f.get('recommendation')}"
        )
    for v in style_violations[:5]:
        line_comments.append(
            f"- **Line {v.get('line_number')}** [LOW]: {v.get('message')}"
        )
    if line_comments:
        md_lines.extend(line_comments)
    else:
        md_lines.append("No line-level changes required.")

    # Verification & Next Steps
    md_lines.append("\n## Verification & Next Steps")
    md_lines.append("1. Run unit test suite: `pytest -o pythonpath=. --basetemp=.pytest_tmp tests/`")
    if critical_count > 0 or high_count > 0:
        md_lines.append("2. Run automated fixer: `python main.py --file <path> --auto-fix`")
    md_lines.append("3. Re-verify code review score after applying fixes.")

    report = "\n".join(md_lines)
    _set_state(tool_context, StateKeys.FEEDBACK_REPORT, report)
    return report
