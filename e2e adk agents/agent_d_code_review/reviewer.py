"""Reviewer module for Agent D: Production-Quality Code Review Assistant.

Exports the core review tools and the CodeReviewer pipeline orchestrator.
"""

from typing import Dict, Any, List, Optional
import os

try:
    from .constants import StateKeys, Severity, CWE_DEFINITIONS
    from .models import (
        CodeReviewRequest,
        CodeReviewReport,
        SecurityFinding,
        StyleViolation,
        LineComment,
        StructureMetrics,
    )
    from .tools import (
        ToolContext,
        analyze_code_structure,
        check_code_style,
        scan_security_vulnerabilities,
        parse_git_diff,
        feedback_synthesizer,
        _get_state,
        _set_state,
    )
except ImportError:
    from constants import StateKeys, Severity, CWE_DEFINITIONS
    from models import (
        CodeReviewRequest,
        CodeReviewReport,
        SecurityFinding,
        StyleViolation,
        LineComment,
        StructureMetrics,
    )
    from tools import (
        ToolContext,
        analyze_code_structure,
        check_code_style,
        scan_security_vulnerabilities,
        parse_git_diff,
        feedback_synthesizer,
        _get_state,
        _set_state,
    )


class CodeReviewer:
    """Sequential review pipeline executing structural analysis, style checking,
    security scanning, diff parsing, and structured feedback synthesis.
    """

    def __init__(self, tool_context: Optional[ToolContext] = None):
        self.context = tool_context or ToolContext()

    def review(
        self,
        code: Optional[str] = None,
        git_diff: Optional[str] = None,
        pr_description: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> CodeReviewReport:
        """Executes the full code review pipeline.

        Args:
            code: Python source code string.
            git_diff: Optional git diff string.
            pr_description: Optional PR description.
            file_path: Optional file path to read code from.

        Returns:
            Structured CodeReviewReport dataclass.
        """
        # Resolve code content
        source_code = code or ""
        if not source_code and file_path and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                source_code = f.read()

        _set_state(self.context, StateKeys.CODE_TO_REVIEW, source_code)
        if pr_description:
            _set_state(self.context, StateKeys.PR_DESCRIPTION, pr_description)

        # 1. Parse Git Diff if present
        diff_info = []
        if git_diff:
            diff_info = parse_git_diff(git_diff, self.context)

        # 2. Analyze Code Structure via AST
        struct_info = analyze_code_structure(source_code, self.context)

        # 3. Check PEP 8 Code Style & Compute Score
        style_info = check_code_style(source_code, self.context)

        # 4. Scan Security Vulnerabilities (OWASP Top 10 & CWE)
        sec_findings_raw = scan_security_vulnerabilities(source_code, self.context)

        # 5. Synthesize Markdown Review Report
        markdown_summary = feedback_synthesizer(self.context, pr_description)

        # Build dataclass report
        sec_findings = [
            SecurityFinding(
                cwe_id=f.get("cwe_id", "CWE-Unknown"),
                name=f.get("name", "Vulnerability"),
                severity=Severity(f.get("severity", Severity.HIGH.value)),
                line_number=f.get("line_number", 0),
                snippet=f.get("snippet", ""),
                message=f.get("message", ""),
                recommendation=f.get("recommendation", ""),
                owasp=f.get("owasp"),
            )
            for f in sec_findings_raw
        ]

        # Check for syntax errors preventing AST analysis and execution
        if struct_info.get("syntax_valid") is False:
            syntax_err_msg = struct_info.get("syntax_error", "Syntax error in source code")
            sec_findings.append(
                SecurityFinding(
                    cwe_id="CWE-SyntaxError",
                    name="Critical Syntax Blocker",
                    severity=Severity.CRITICAL,
                    line_number=1,
                    snippet="",
                    message=f"Critical Syntax Blocker: {syntax_err_msg}. Code cannot be compiled or statically verified.",
                    recommendation="Fix Python syntax error so that code compiles and can be safely evaluated.",
                    owasp="A04:2021-Insecure Design",
                )
            )

        style_violations = [
            StyleViolation(
                code=v.get("code", "E"),
                line_number=v.get("line_number", 0),
                column=v.get("column", 0),
                message=v.get("message", ""),
                snippet=v.get("snippet", ""),
                severity=Severity(v.get("severity", Severity.LOW.value)),
            )
            for v in style_info.get("violations", [])
        ]

        # Assemble line comments
        line_comments: List[LineComment] = []
        target_file = file_path or (diff_info[0]["new_file"] if diff_info else "source.py")

        for f in sec_findings:
            line_comments.append(
                LineComment(
                    file_path=target_file,
                    line_number=f.line_number,
                    severity=f.severity,
                    comment=f"[{f.cwe_id}] {f.message}",
                    suggested_replacement=f.recommendation,
                )
            )

        for v in style_violations[:10]:
            line_comments.append(
                LineComment(
                    file_path=target_file,
                    line_number=v.line_number,
                    severity=v.severity,
                    comment=f"[{v.code}] {v.message}",
                )
            )

        critical_count = sum(1 for f in sec_findings if f.severity == Severity.CRITICAL)
        high_count = sum(1 for f in sec_findings if f.severity == Severity.HIGH)
        medium_count = (
            sum(1 for f in sec_findings if f.severity == Severity.MEDIUM)
            + sum(1 for v in style_violations if v.severity == Severity.MEDIUM)
        )
        low_count = (
            sum(1 for f in sec_findings if f.severity == Severity.LOW)
            + sum(1 for v in style_violations if v.severity == Severity.LOW)
        )

        style_score = float(style_info.get("score", 100.0))
        sec_penalty = (critical_count * 30) + (high_count * 15) + (medium_count * 5)
        health_score = max(0.0, min(100.0, round((style_score * 0.4) + (max(0.0, 100.0 - sec_penalty) * 0.6), 1)))

        if struct_info.get("syntax_valid") is False:
            health_score = min(health_score, 25.0)

        if critical_count > 0 or high_count > 0 or style_score < 70.0:
            overall_status = "CHANGES REQUESTED"
        elif medium_count > 0 or style_score < 85.0:
            overall_status = "COMMENT"
        else:
            overall_status = "APPROVED"

        return CodeReviewReport(
            overall_status=overall_status,
            health_score=health_score,
            style_score=style_score,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            security_findings=sec_findings,
            style_violations=style_violations,
            structure_metrics=struct_info,
            line_comments=line_comments,
            markdown_summary=markdown_summary,
        )


__all__ = [
    "CodeReviewer",
    "ToolContext",
    "analyze_code_structure",
    "check_code_style",
    "scan_security_vulnerabilities",
    "parse_git_diff",
    "feedback_synthesizer",
]
