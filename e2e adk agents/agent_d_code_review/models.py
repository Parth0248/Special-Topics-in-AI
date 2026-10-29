"""Data models for Agent D: Code Review Assistant.

Defines Pydantic/dataclass models for code review requests, findings, metrics, and reports.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
try:
    from .constants import Severity
except ImportError:
    from constants import Severity


@dataclass
class SecurityFinding:
    """Represents a detected security vulnerability (OWASP / CWE)."""
    cwe_id: str
    name: str
    severity: Severity
    line_number: int
    snippet: str
    message: str
    recommendation: str
    owasp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert finding to dictionary representation."""
        res = asdict(self)
        res["severity"] = self.severity.value
        return res


@dataclass
class StyleViolation:
    """Represents a PEP 8 or code style violation."""
    code: str
    line_number: int
    column: int
    message: str
    snippet: str
    severity: Severity = Severity.LOW

    def to_dict(self) -> Dict[str, Any]:
        """Convert violation to dictionary representation."""
        res = asdict(self)
        res["severity"] = self.severity.value
        return res


@dataclass
class LineComment:
    """Represents an actionable line-by-line review comment."""
    file_path: str
    line_number: int
    severity: Severity
    comment: str
    suggested_replacement: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert comment to dictionary representation."""
        res = asdict(self)
        res["severity"] = self.severity.value
        return res


@dataclass
class StructureMetrics:
    """AST metrics detailing code structure, complexity, and coverage."""
    syntax_valid: bool
    total_loc: int
    functions_count: int
    classes_count: int
    docstring_coverage: float
    max_complexity: int
    avg_complexity: float
    high_complexity_functions: List[str] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    classes: List[Dict[str, Any]] = field(default_factory=list)
    syntax_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary representation."""
        return asdict(self)


@dataclass
class CodeReviewRequest:
    """Input payload for Code Review Assistant."""
    code: Optional[str] = None
    git_diff: Optional[str] = None
    file_path: Optional[str] = None
    pr_description: Optional[str] = None


@dataclass
class CodeReviewReport:
    """Comprehensive output report from Code Review Assistant."""
    overall_status: str
    health_score: float
    style_score: float
    security_findings: List[SecurityFinding] = field(default_factory=list)
    style_violations: List[StyleViolation] = field(default_factory=list)
    structure_metrics: Dict[str, Any] = field(default_factory=dict)
    line_comments: List[LineComment] = field(default_factory=list)
    markdown_summary: str = ""
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary representation."""
        return {
            "overall_status": self.overall_status,
            "health_score": self.health_score,
            "style_score": self.style_score,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "security_findings": [f.to_dict() for f in self.security_findings],
            "style_violations": [v.to_dict() for v in self.style_violations],
            "structure_metrics": self.structure_metrics,
            "line_comments": [c.to_dict() for c in self.line_comments],
            "markdown_summary": self.markdown_summary,
        }
