"""Pydantic data models and schemas for Agent B: Gemini CLI in ADK Pipeline Tool Agent.

Defines schemas for task requests, subprocess execution results, pipeline stage outputs,
and comprehensive telemetry summaries.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """Input specification for an agent task to be executed through the ADK pipeline."""

    task_id: str = Field(
        default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}",
        description="Unique identifier for the task request.",
    )
    description: str = Field(
        ...,
        description="High-level task description or prompt to execute.",
    )
    code_context: Optional[str] = Field(
        default=None,
        description="Optional source code snippet or file content provided as context.",
    )
    language: str = Field(
        default="python",
        description="Target programming language (default: python).",
    )
    output_format: str = Field(
        default="json",
        description="Requested output format from the CLI tool ('json' or 'text').",
    )
    max_timeout_seconds: int = Field(
        default=120,
        ge=1,
        le=600,
        description="Maximum execution timeout in seconds.",
    )
    extra_instructions: Optional[str] = Field(
        default=None,
        description="Optional additional guidelines or constraints for the model.",
    )


class CliResult(BaseModel):
    """Encapsulates the execution result of the Gemini CLI subprocess invocation."""

    success: bool = Field(
        ...,
        description="True if the CLI command exited cleanly (code 0) and parsed.",
    )
    returncode: int = Field(
        default=0,
        description="Subprocess return code (0 for success, non-zero for error, -1 for timeout).",
    )
    response: Union[Dict[str, Any], str, None] = Field(
        default=None,
        description="Parsed JSON payload or extracted text response from the model.",
    )
    raw_output: str = Field(
        default="",
        description="Raw standard output captured from the subprocess.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message or standard error captured if execution failed.",
    )
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Execution metadata including token usage, latency, or fallback details.",
    )
    is_fallback: bool = Field(
        default=False,
        description="True if execution fell back to google.genai SDK or mock emulator.",
    )
    execution_time_ms: float = Field(
        default=0.0,
        description="Duration of the subprocess or fallback call in milliseconds.",
    )


class StageOutput(BaseModel):
    """Telemetry and data output for an individual pipeline execution stage."""

    stage_id: int = Field(
        ...,
        ge=1,
        le=4,
        description="Stage numeric index (1 to 4).",
    )
    stage_name: str = Field(
        ...,
        description="Descriptive name of the pipeline stage.",
    )
    status: str = Field(
        default="success",
        description="Execution status of this stage ('success', 'failed', 'skipped').",
    )
    input_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data and parameters passed into this stage.",
    )
    output_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Results, artifacts, or transformations generated in this stage.",
    )
    duration_ms: float = Field(
        default=0.0,
        description="Execution duration for this stage in milliseconds.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional diagnostic notes or observations.",
    )


class PipelineSummary(BaseModel):
    """Comprehensive summary of all 4 stages of the ADK execution pipeline."""

    pipeline_id: str = Field(
        default_factory=lambda: f"pipe_{uuid.uuid4().hex[:8]}",
        description="Unique identifier for this pipeline execution run.",
    )
    task_request: TaskRequest = Field(
        ...,
        description="Original task request that initiated the pipeline.",
    )
    stages: List[StageOutput] = Field(
        default_factory=list,
        description="Ordered list of stage execution records.",
    )
    overall_success: bool = Field(
        ...,
        description="Whether the entire pipeline completed successfully without critical errors.",
    )
    final_artifact: Union[str, Dict[str, Any], None] = Field(
        default=None,
        description="Synthesized final artifact (code, test suite, or documentation).",
    )
    total_duration_ms: float = Field(
        default=0.0,
        description="Total end-to-end execution time across all stages in milliseconds.",
    )
    cli_invocations_count: int = Field(
        default=0,
        description="Total number of external CLI or fallback tool invocations executed.",
    )
    telemetry: Dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated performance telemetry and resource usage statistics.",
    )
