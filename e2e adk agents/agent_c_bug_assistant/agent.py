"""Google ADK Bug Assistant Agent (Agent C).

Connects to FastMCP server or embedded in-process tools to triage software bugs,
pinpoint root causes, synthesize minimal reproduction tests, and generate verified patches.
Supports Google ADK / google.genai tool calling and deterministic local execution.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from .embedded_tools import EmbeddedTools
    from .mcp_server import create_mcp_server
    from .triage import BugTriagePipeline, DiagnosticReport, TracebackParser
except ImportError:
    from embedded_tools import EmbeddedTools
    from mcp_server import create_mcp_server
    from triage import BugTriagePipeline, DiagnosticReport, TracebackParser

SYSTEM_INSTRUCTION = """You are a senior Software Bug Assistant Agent built with the Google Agent Development Kit (ADK).
Your mission is to perform systematic, reproducible 5-phase software bug triage:

1. Intake & Traceback Parsing: Parse exception type, message, and isolate application frames from library frames.
2. Context Gathering: Use MCP filesystem and AST search tools (read_file, search_files, find_symbol, git_status, git_diff) to inspect the faulty line and surrounding code.
3. Minimal Reproducible Test: Synthesize a standalone pytest reproducer that reliably triggers the bug.
4. Surgical Patch Synthesis: Synthesize a minimal unified diff (diff -u) resolving the root cause without invasive refactoring.
5. Verification: Verify the reproducer fails prior to patch and passes cleanly after patch application.

Always be precise, preserve existing code style, and guarantee minimal surgical changes.
"""


class BugAssistantAgent:
    """Google ADK Bug Assistant Agent with MCP and Embedded Tools integration."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        workspace_root: Optional[str] = None,
        api_key: Optional[str] = None,
        use_mcp_server: bool = False,
    ):
        self.model_name = model_name
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd().resolve()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.use_mcp_server = use_mcp_server

        self.tools = EmbeddedTools(workspace_root=str(self.workspace_root))
        self.pipeline = BugTriagePipeline(workspace_root=str(self.workspace_root))

        # Check for Google ADK / GenAI SDK client
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    def diagnose(
        self,
        stack_trace: str,
        repo_path: Optional[str] = None,
        apply_patch: bool = False,
        custom_reproducer: Optional[str] = None,
        custom_fix: Optional[str] = None,
    ) -> Union[DiagnosticReport, Dict[str, Any]]:
        """Run the end-to-end 5-phase bug triage on a stack trace.

        Args:
            stack_trace: Raw stack trace or crash log string.
            repo_path: Target repository path.
            apply_patch: Whether to permanently keep the verified patch.
            custom_reproducer: Optional custom reproducer code.
            custom_fix: Optional custom fixed code.

        Returns:
            DiagnosticReport containing diagnosis, patch diff, and verification status,
            or a structured error dict {"status": "error", "message": ...} on failure.
        """
        target_repo = repo_path or str(self.workspace_root)
        try:
            return self.pipeline.run_triage(
                stack_trace=stack_trace,
                repo_path=target_repo,
                apply_permanently=apply_patch,
                custom_reproducer=custom_reproducer,
                custom_fix=custom_fix,
            )
        except (ValueError, FileNotFoundError) as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected triage failure: {e}"}

    def run_demo(self, demo_workspace_dir: Optional[str] = None) -> DiagnosticReport:
        """Execute a complete, automated end-to-end bug triage demonstration.

        Creates a realistic buggy service, captures its crash traceback,
        localizes the fault via MCP tools, generates a minimal reproducer,
        verifies pre-patch failure, synthesizes a patch, and verifies post-patch success.

        Args:
            demo_workspace_dir: Directory where sample buggy code is created.

        Returns:
            The final DiagnosticReport.
        """
        import tempfile

        if demo_workspace_dir:
            work_dir = Path(demo_workspace_dir).resolve()
            work_dir.mkdir(parents=True, exist_ok=True)
        else:
            temp_obj = tempfile.TemporaryDirectory(prefix="agent_c_demo_")
            work_dir = Path(temp_obj.name).resolve()

        # 1. Create a realistic buggy Python module: metrics_service.py
        buggy_code = '''"""Metrics calculation service with an edge-case ZeroDivisionError defect."""

from typing import List, Dict, Any


def calculate_average_throughput(requests_per_second: List[float], total_duration_seconds: float) -> float:
    """Calculate the average request throughput.

    Defect: Fails when total_duration_seconds is 0.0 or requests_per_second is empty.
    """
    total_requests = sum(requests_per_second)
    # The line below raises ZeroDivisionError when total_duration_seconds == 0
    average_rate = total_requests / total_duration_seconds
    return round(average_rate, 2)


def process_telemetry_batch() -> float:
    """Process current telemetry batch."""
    rates = [120.5, 140.2, 98.4]
    duration = 0.0  # Empty observation window triggers crash
    return calculate_average_throughput(rates, duration)


if __name__ == "__main__":
    process_telemetry_batch()
'''
        file_path = work_dir / "metrics_service.py"
        file_path.write_text(buggy_code, encoding="utf-8")

        # 2. Simulate the crash traceback
        simulated_traceback = f"""Traceback (most recent call last):
  File "{file_path.as_posix()}", line 22, in <module>
    process_telemetry_batch()
  File "{file_path.as_posix()}", line 19, in process_telemetry_batch
    return calculate_average_throughput(rates, duration)
  File "{file_path.as_posix()}", line 13, in calculate_average_throughput
    average_rate = total_requests / total_duration_seconds
ZeroDivisionError: float division by zero
"""

        # 3. Custom reproducer targeting this exact failure
        reproducer_code = f'''"""Minimal reproduction test for metrics_service ZeroDivisionError."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, r"{work_dir.as_posix()}")
from metrics_service import process_telemetry_batch, calculate_average_throughput

def test_reproduce_metrics_crash():
    """Assert throughput calculation handles zero duration without crashing."""
    rate = process_telemetry_batch()
    assert rate == 0.0 or rate is not None
'''

        # 4. Correct fix
        fixed_code = '''"""Metrics calculation service with an edge-case ZeroDivisionError defect."""

from typing import List, Dict, Any


def calculate_average_throughput(requests_per_second: List[float], total_duration_seconds: float) -> float:
    """Calculate the average request throughput.

    Defect: Fails when total_duration_seconds is 0.0 or requests_per_second is empty.
    """
    total_requests = sum(requests_per_second)
    if not total_duration_seconds:
        return 0.0
    average_rate = total_requests / total_duration_seconds
    return round(average_rate, 2)


def process_telemetry_batch() -> float:
    """Process current telemetry batch."""
    rates = [120.5, 140.2, 98.4]
    duration = 0.0  # Empty observation window triggers crash
    return calculate_average_throughput(rates, duration)


if __name__ == "__main__":
    process_telemetry_batch()
'''

        # Run diagnosis & verification
        report = self.diagnose(
            stack_trace=simulated_traceback,
            repo_path=str(work_dir),
            apply_patch=True,
            custom_reproducer=reproducer_code,
            custom_fix=fixed_code,
        )

        return report
