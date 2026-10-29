"""Top-level Google ADK Agent for Agent D: Production-Quality Code Review Assistant.

Wires the SequentialAgent review pipeline and the LoopAgent fix pipeline.
Supports both live Gemini-powered contextual explanations and fully deterministic
local execution for offline pipelines and automated test harnesses.
"""

import os
from typing import Dict, Any, List, Optional, Tuple

try:
    from .constants import StateKeys, Severity
    from .models import CodeReviewReport, CodeReviewRequest
    from .tools import ToolContext
    from .reviewer import CodeReviewer
    from .fix_pipeline import CodeFixLoopAgent, code_fixer, fix_validator
except ImportError:
    from constants import StateKeys, Severity
    from models import CodeReviewReport, CodeReviewRequest
    from tools import ToolContext
    from reviewer import CodeReviewer
    from fix_pipeline import CodeFixLoopAgent, code_fixer, fix_validator


class CodeReviewAssistantAgent:
    """Agent D: Production-Quality Code Review Assistant.

    Orchestrates:
      1. Sequential Review Pipeline (AST, PEP 8, OWASP/CWE Security, Diff, Synthesis)
      2. Iterative Fix Loop (LoopAgent: Code Fixer -> Fix Validator)
      3. Optional Gemini GenAI SDK integration for generative insights.
    """

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
        max_fix_iterations: int = 3,
    ):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.max_fix_iterations = max_fix_iterations
        self.reviewer = CodeReviewer()
        self.loop_agent = CodeFixLoopAgent(max_iterations=max_fix_iterations)

        # Initialize optional Gemini client if api_key is present
        self._genai_client = None
        if self.api_key:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self.api_key)
            except Exception:
                self._genai_client = None

    def review(
        self,
        code: Optional[str] = None,
        git_diff: Optional[str] = None,
        pr_description: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> CodeReviewReport:
        """Runs the Sequential Review Pipeline on code, diff, or file.

        Args:
            code: Source code string to evaluate.
            git_diff: Git diff / patch string to evaluate.
            pr_description: Optional PR description for context.
            file_path: Optional file path to inspect.

        Returns:
            CodeReviewReport containing scores, findings, and Markdown review.
        """
        report = self.reviewer.review(
            code=code,
            git_diff=git_diff,
            pr_description=pr_description,
            file_path=file_path,
        )

        # If Gemini is configured and code is present, optionally append AI commentary
        if self._genai_client and code and len(code.strip()) > 0:
            try:
                prompt = (
                    f"You are a senior Google code review assistant. Review this Python code:\n"
                    f"```python\n{code[:2000]}\n```\n"
                    f"Findings from static analysis:\n"
                    f"- Style score: {report.style_score}\n"
                    f"- Critical security issues: {report.critical_count}\n"
                    f"Provide a 2-sentence executive recommendation."
                )
                response = self._genai_client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
                if response and hasattr(response, "text") and response.text:
                    ai_commentary = f"\n\n### 🤖 AI Senior Reviewer Commentary\n{response.text.strip()}"
                    report.markdown_summary += ai_commentary
            except Exception:
                # Silently retain deterministic report on network/API failure
                pass

        return report

    def auto_fix(self, code: str, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """Runs the LoopAgent fix pipeline on the provided source code.

        Args:
            code: Source code string to remediate.
            max_iterations: Optional loop iteration limit override.

        Returns:
            Dictionary containing fixed_code, validation_passed, iterations, scores.
        """
        iterations = max_iterations or self.max_fix_iterations
        loop = CodeFixLoopAgent(max_iterations=iterations)
        return loop.run(code)

    def review_and_fix(
        self,
        code: str,
        pr_description: Optional[str] = None,
    ) -> Tuple[CodeReviewReport, Dict[str, Any]]:
        """Executes both the review pipeline and iterative remediation.

        Returns:
            Tuple of (initial_report, fix_results).
        """
        initial_report = self.review(code=code, pr_description=pr_description)
        fix_results = self.auto_fix(code)
        return initial_report, fix_results


def create_agent(
    model_name: str = "gemini-2.5-flash",
    api_key: Optional[str] = None,
    max_fix_iterations: int = 3,
) -> CodeReviewAssistantAgent:
    """Factory function for instantiating Agent D."""
    return CodeReviewAssistantAgent(
        model_name=model_name,
        api_key=api_key,
        max_fix_iterations=max_fix_iterations,
    )


__all__ = [
    "CodeReviewAssistantAgent",
    "create_agent",
]
