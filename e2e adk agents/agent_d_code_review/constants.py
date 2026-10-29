"""Constants and Enumerations for Agent D: Code Review Assistant.

Defines StateKeys for ADK ToolContext, Severity tiers, and CWE definitions.
"""

from enum import Enum
from typing import Dict, Any


class StateKeys(str, Enum):
    """ADK State keys for sharing data between pipeline agents and tools."""
    CODE_TO_REVIEW = "code_to_review"
    CODE_ANALYSIS = "code_analysis"
    STYLE_SCORE = "style_score"
    STYLE_VIOLATIONS = "style_violations"
    SECURITY_FINDINGS = "security_findings"
    GIT_DIFF = "git_diff"
    PR_DESCRIPTION = "pr_description"
    TEST_RESULTS = "test_results"
    FEEDBACK_REPORT = "feedback_report"
    FIXED_CODE = "fixed_code"
    VALIDATION_PASSED = "validation_passed"
    FIX_ITERATIONS = "fix_iterations"
    FIX_HISTORY = "fix_history"


class Severity(str, Enum):
    """4-tier severity levels for code review findings."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Known Common Weakness Enumeration (CWE) definitions with metadata
CWE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "CWE-89": {
        "name": "SQL Injection (SQLi)",
        "default_severity": Severity.CRITICAL,
        "owasp": "A03:2021-Injection",
        "description": "Untrusted input directly concatenated into SQL queries.",
        "remediation": "Use parameterized queries or ORM query parameters instead of string formatting."
    },
    "CWE-78": {
        "name": "OS Command Injection",
        "default_severity": Severity.CRITICAL,
        "owasp": "A03:2021-Injection",
        "description": "Untrusted input executed via shell command.",
        "remediation": "Avoid shell=True in subprocess, use shlex.quote, or pass argument list directly."
    },
    "CWE-502": {
        "name": "Deserialization of Untrusted Data",
        "default_severity": Severity.CRITICAL,
        "owasp": "A08:2021-Software and Data Integrity Failures",
        "description": "Insecure deserialization via pickle, marshal, or unsafe yaml.",
        "remediation": "Use safe serialization formats like JSON, or yaml.safe_load."
    },
    "CWE-22": {
        "name": "Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')",
        "default_severity": Severity.HIGH,
        "owasp": "A01:2021-Broken Access Control",
        "description": "User input used in file path without canonicalization.",
        "remediation": "Validate input using os.path.basename or pathlib.Path.resolve() with boundary check."
    },
    "CWE-798": {
        "name": "Use of Hard-coded Credentials",
        "default_severity": Severity.HIGH,
        "owasp": "A07:2021-Identification and Authentication Failures",
        "description": "Hard-coded passwords, API keys, or tokens in source code.",
        "remediation": "Load credentials from environment variables or a secrets manager."
    },
    "CWE-327": {
        "name": "Use of a Broken or Risky Cryptographic Algorithm",
        "default_severity": Severity.HIGH,
        "owasp": "A02:2021-Cryptographic Failures",
        "description": "Use of obsolete or weak cryptographic hashes (MD5, SHA1) or ciphers.",
        "remediation": "Use SHA-256, SHA-3, or modern password hashing algorithms like bcrypt/argon2."
    },
    "CWE-95": {
        "name": "Improper Neutralization of Directives in Dynamically Evaluated Code ('Eval Injection')",
        "default_severity": Severity.CRITICAL,
        "owasp": "A03:2021-Injection",
        "description": "Use of eval() or exec() with dynamic untrusted input.",
        "remediation": "Use ast.literal_eval() for data parsing, or redesign without dynamic evaluation."
    },
    "CWE-703": {
        "name": "Improper Check or Handling of Exceptional Conditions",
        "default_severity": Severity.LOW,
        "owasp": "A04:2021-Insecure Design",
        "description": "Bare except clause catching and silencing all exceptions.",
        "remediation": "Catch specific exception types and log or re-raise."
    },
    "CWE-476": {
        "name": "NULL Pointer Dereference",
        "default_severity": Severity.MEDIUM,
        "owasp": "A04:2021-Insecure Design",
        "description": "Unchecked None value dereference.",
        "remediation": "Add explicit None checks before accessing attributes or subscripting."
    }
}
