"""Google Agent Development Kit (ADK) Agent with Gemini CLI Subprocess Tool.

Integrates Gemini CLI as a headless external tool inside a Google ADK Agent.
Supports official `google.adk.agents.Agent` when installed, with an
in-process ADK-compliant adapter when running in standalone mode.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Union

from cli_wrapper import GeminiCliWrapper
from pipeline import ADKPipeline
from schemas import TaskRequest

logger = logging.getLogger(__name__)

# Default shared wrapper and pipeline instances
_default_wrapper = GeminiCliWrapper()
_default_pipeline = ADKPipeline(cli_wrapper=_default_wrapper)


def gemini_cli_tool(
    task: str,
    output_format: str = "json",
    codebase_dir: str = ".",
) -> str:
    """Executes the Gemini CLI in headless non-interactive mode.

    Args:
        task: The task or prompt to pass to Gemini CLI, e.g. explain codebase, generate tests.
        output_format: Output format for response ('json' or 'text').
        codebase_dir: Directory context for CLI execution.

    Returns:
        JSON string containing success status, parsed response, and execution stats.
    """
    result = _default_wrapper.execute_prompt(
        prompt=task,
        output_format=output_format,
        codebase_dir=codebase_dir,
    )
    return json.dumps(result.model_dump(), indent=2)


def run_pipeline_tool(
    task_description: str,
    code_context: str = "",
    language: str = "python",
) -> str:
    """Executes the 4-stage ADK pipeline (Decompose, Exec, Transform, Synthesize).

    Args:
        task_description: High-level development task to execute through the pipeline.
        code_context: Optional source code or file content to analyze or transform.
        language: Programming language for AST parsing and validation (default: python).

    Returns:
        JSON string containing the PipelineSummary, final artifact, and stage telemetry.
    """
    req = TaskRequest(
        description=task_description,
        code_context=code_context if code_context else None,
        language=language,
    )
    summary = _default_pipeline.run(req)
    return json.dumps(summary.model_dump(), indent=2)


# ==============================================================================
# Google ADK Agent Definition
# ==============================================================================

ADK_INSTRUCTION = """You are a world-class Software Development Life Cycle (SDLC) AI Assistant powered by Google ADK.
You have direct access to Gemini CLI tools:
1. `gemini_cli_tool`: Directly executes commands, code analysis, and refactoring via Gemini CLI in headless mode.
2. `run_pipeline_tool`: Runs complex multi-stage tasks through the 4-stage ADK pipeline (Decomposition, CLI Execution, AST Code Transformation, and Telemetry Synthesis).

Always leverage these tools to fulfill software engineering, testing, and code generation requests with verified syntax and rigorous telemetry.
"""

# Attempt to import Google ADK Agent; fallback to compliant in-process implementation
try:
    from google.adk.agents import Agent as BaseADKAgent
    HAS_NATIVE_ADK = True
except ImportError:
    HAS_NATIVE_ADK = False

    class BaseADKAgent:  # type: ignore
        """ADK-compliant Agent interface adhering to Google ADK specification."""

        def __init__(
            self,
            name: str,
            model: str = "gemini-2.5-pro",
            instruction: str = "",
            description: str = "",
            tools: Optional[List[Callable[..., Any]]] = None,
        ) -> None:
            self.name = name
            self.model = model
            self.instruction = instruction
            self.description = description or instruction
            self.tools = tools or []
            self._tools_by_name = {t.__name__: t for t in self.tools if hasattr(t, "__name__")}

        def run(self, prompt: str, **kwargs: Any) -> str:
            """Execute agent prompt, dispatching tools when appropriate."""
            prompt_lower = prompt.lower()

            # Automatic tool selection based on task intent
            if "pipeline" in prompt_lower or "decompose" in prompt_lower or "multi-stage" in prompt_lower:
                if "run_pipeline_tool" in self._tools_by_name:
                    logger.info("Agent dispatching to run_pipeline_tool.")
                    return self._tools_by_name["run_pipeline_tool"](task_description=prompt)

            if "run_gemini_cli_tool" in self._tools_by_name or "gemini_cli_tool" in self._tools_by_name:
                tool_fn = self._tools_by_name.get("gemini_cli_tool") or self._tools_by_name.get("run_gemini_cli_tool")
                if tool_fn:
                    logger.info("Agent dispatching to gemini_cli_tool.")
                    return tool_fn(task=prompt)

            # Default conversational response
            return (
                f"[{self.name} | Model: {self.model}]\n"
                f"Successfully processed request: '{prompt[:100]}...'\n"
                f"Available tools registered: {list(self._tools_by_name.keys())}"
            )

        def chat(self, message: str) -> str:
            return self.run(message)


def create_agent(
    model: Optional[str] = None,
    custom_instruction: Optional[str] = None,
    wrapper: Optional[GeminiCliWrapper] = None,
) -> BaseADKAgent:
    """Factory creating an instance of the Gemini CLI ADK Pipeline Agent."""
    active_model = model or os.getenv("HARNESS_MODEL", "gemini-2.5-pro")
    instruction = custom_instruction or ADK_INSTRUCTION

    # If a custom wrapper is passed, wrap tool functions to use it
    if wrapper is not None:
        def custom_cli_tool(task: str, output_format: str = "json", codebase_dir: str = ".") -> str:
            res = wrapper.execute_prompt(prompt=task, output_format=output_format, codebase_dir=codebase_dir)
            return json.dumps(res.model_dump(), indent=2)

        pipeline = ADKPipeline(cli_wrapper=wrapper)
        def custom_pipeline_tool(task_description: str, code_context: str = "", language: str = "python") -> str:
            req = TaskRequest(description=task_description, code_context=code_context or None, language=language)
            return json.dumps(pipeline.run(req).model_dump(), indent=2)

        tools = [custom_cli_tool, custom_pipeline_tool]
    else:
        tools = [gemini_cli_tool, run_pipeline_tool]

    return BaseADKAgent(
        name="gemini_cli_pipeline_agent",
        model=active_model,
        instruction=instruction,
        description="Google ADK Agent coordinating Gemini CLI tools and 4-stage pipeline execution.",
        tools=tools,
    )


# Root agent singleton export matching ADK convention
root_agent = create_agent()
