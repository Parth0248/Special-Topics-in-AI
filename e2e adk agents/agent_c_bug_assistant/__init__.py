"""Agent C: MCP Tools-Based Bug Assistant Agent.

A production-grade Google ADK agent for automated software bug triage,
root cause localization, minimal reproducer synthesis, and verified patch generation
powered by FastMCP and in-process embedded tools.
"""

from .embedded_tools import EmbeddedTools
from .mcp_server import mcp, create_mcp_server
from .triage import (
    TracebackParser,
    TracebackInfo,
    StackFrame,
    BugContext,
    DiagnosticReport,
    BugTriagePipeline,
)
from .agent import BugAssistantAgent

__all__ = [
    "EmbeddedTools",
    "mcp",
    "create_mcp_server",
    "TracebackParser",
    "TracebackInfo",
    "StackFrame",
    "BugContext",
    "DiagnosticReport",
    "BugTriagePipeline",
    "BugAssistantAgent",
]
