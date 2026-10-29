"""ADK 4-Stage Execution Pipeline for Agent B.

Pipeline Stages:
1. Stage 1: Decompose - Analyze task request and break into atomic execution steps.
2. Stage 2: Tool Invocation via CLI Subprocess - Invoke Gemini CLI tool across steps.
3. Stage 3: Code/Text Transformation - Extract code blocks, validate AST, and structure output.
4. Stage 4: Synthesis & Telemetry - Compile final artifacts and aggregate execution telemetry.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from cli_wrapper import GeminiCliWrapper
from schemas import CliResult, PipelineSummary, StageOutput, TaskRequest

logger = logging.getLogger(__name__)


class ADKPipeline:
    """Four-stage execution pipeline coordinating Gemini CLI tool invocations."""

    def __init__(
        self,
        cli_wrapper: Optional[GeminiCliWrapper] = None,
        default_timeout: int = 120,
    ) -> None:
        """Initialize the pipeline with a Gemini CLI wrapper instance.

        Args:
            cli_wrapper: Optional pre-configured GeminiCliWrapper.
            default_timeout: Timeout limit for each CLI invocation.
        """
        self.cli_wrapper = cli_wrapper or GeminiCliWrapper(default_timeout=default_timeout)

    def run(self, task_request: TaskRequest) -> PipelineSummary:
        """Execute the complete 4-stage pipeline synchronously."""
        pipeline_id = f"pipe_{uuid.uuid4().hex[:8]}"
        overall_start = time.perf_counter()
        stages: List[StageOutput] = []
        cli_invocations = 0

        # ======================================================================
        # STAGE 1: Decompose
        # ======================================================================
        stage1_start = time.perf_counter()
        decomp_prompt = (
            f"Analyze and decompose the following development task into atomic steps.\n"
            f"Task: {task_request.description}\n"
            f"Language: {task_request.language}\n"
            f"Output must be a JSON object with a 'tasks' list, each containing 'step', 'title', and 'instruction'."
        )
        if task_request.code_context:
            decomp_prompt += f"\nCode Context:\n```\n{task_request.code_context[:500]}\n```"

        stage1_cli_res = self.cli_wrapper.execute_prompt(
            prompt=decomp_prompt,
            output_format="json",
            timeout=task_request.max_timeout_seconds,
        )
        cli_invocations += 1

        subtasks: List[Dict[str, Any]] = []
        if stage1_cli_res.success and isinstance(stage1_cli_res.response, dict):
            subtasks = stage1_cli_res.response.get("tasks", [])

        if not subtasks:
            # Fallback decomposition if response didn't contain structured subtasks
            subtasks = [
                {
                    "step": 1,
                    "title": "Analyze and Refactor Code",
                    "instruction": f"Implement or optimize: {task_request.description}",
                },
                {
                    "step": 2,
                    "title": "Generate Automated Verification Tests",
                    "instruction": f"Create pytest unit tests verifying: {task_request.description}",
                },
            ]

        stage1_ms = (time.perf_counter() - stage1_start) * 1000
        stages.append(
            StageOutput(
                stage_id=1,
                stage_name="Decompose",
                status="success" if stage1_cli_res.success else "failed",
                input_data={"description": task_request.description},
                output_data={"subtasks": subtasks, "cli_result": stage1_cli_res.model_dump()},
                duration_ms=stage1_ms,
                notes=f"Decomposed into {len(subtasks)} modular execution subtasks.",
            )
        )

        # ======================================================================
        # STAGE 2: Tool Invocation via CLI Subprocess
        # ======================================================================
        stage2_start = time.perf_counter()
        execution_results: List[Dict[str, Any]] = []

        for subtask in subtasks:
            step_num = subtask.get("step", len(execution_results) + 1)
            step_title = subtask.get("title", f"Step {step_num}")
            step_inst = subtask.get("instruction", "")

            step_prompt = (
                f"Execute the following task:\n"
                f"Title: {step_title}\n"
                f"Instruction: {step_inst}\n"
                f"Language: {task_request.language}\n"
            )
            if task_request.code_context:
                step_prompt += f"\nRelevant Code Context:\n```\n{task_request.code_context}\n```"
            if task_request.extra_instructions:
                step_prompt += f"\nAdditional Guidelines: {task_request.extra_instructions}"

            step_cli_res = self.cli_wrapper.execute_prompt(
                prompt=step_prompt,
                output_format=task_request.output_format,
                timeout=task_request.max_timeout_seconds,
            )
            cli_invocations += 1

            execution_results.append({
                "step": step_num,
                "title": step_title,
                "success": step_cli_res.success,
                "returncode": step_cli_res.returncode,
                "response": step_cli_res.response,
                "stats": step_cli_res.stats,
                "is_fallback": step_cli_res.is_fallback,
                "execution_time_ms": step_cli_res.execution_time_ms,
            })

        stage2_success = all(r["success"] for r in execution_results) if execution_results else False
        stage2_ms = (time.perf_counter() - stage2_start) * 1000
        stages.append(
            StageOutput(
                stage_id=2,
                stage_name="Tool Invocation via CLI Subprocess",
                status="success" if stage2_success else "failed",
                input_data={"subtasks_count": len(subtasks)},
                output_data={"results": execution_results},
                duration_ms=stage2_ms,
                notes=f"Executed {len(execution_results)} CLI subprocess invocations.",
            )
        )

        # ======================================================================
        # STAGE 3: Code/Text Transformation
        # ======================================================================
        stage3_start = time.perf_counter()
        extracted_code_blocks: List[Dict[str, Any]] = []
        ast_validation_results: List[Dict[str, Any]] = []

        for item in execution_results:
            resp = item.get("response")
            raw_text = ""
            if isinstance(resp, dict):
                # Search for known code fields
                for k in ("refactored_code", "test_code", "code", "implementation", "solution"):
                    if k in resp and isinstance(resp[k], str):
                        raw_text += f"\n{resp[k]}"
                if not raw_text:
                    raw_text = json.dumps(resp, indent=2)
            elif isinstance(resp, str):
                raw_text = resp

            blocks = self.cli_wrapper.extract_code_blocks(raw_text, default_language=task_request.language)
            for block in blocks:
                lang = block.get("language", task_request.language).lower()
                code_content = block.get("code", "")
                is_valid_syntax = True
                syntax_error = None

                # Perform Python AST validation if applicable
                if lang in ("python", "py") and code_content:
                    try:
                        ast.parse(code_content)
                    except SyntaxError as err:
                        is_valid_syntax = False
                        syntax_error = f"Line {err.lineno}: {err.msg}"

                extracted_code_blocks.append({
                    "step": item.get("step"),
                    "language": lang,
                    "code": code_content,
                    "ast_valid": is_valid_syntax,
                    "syntax_error": syntax_error,
                })

        stage3_ms = (time.perf_counter() - stage3_start) * 1000
        stages.append(
            StageOutput(
                stage_id=3,
                stage_name="Code/Text Transformation",
                status="success",
                input_data={"invocations_processed": len(execution_results)},
                output_data={
                    "total_code_blocks": len(extracted_code_blocks),
                    "code_blocks": extracted_code_blocks,
                },
                duration_ms=stage3_ms,
                notes=f"Extracted and validated {len(extracted_code_blocks)} code blocks via AST parser.",
            )
        )

        # ======================================================================
        # STAGE 4: Synthesis & Telemetry
        # ======================================================================
        stage4_start = time.perf_counter()

        final_artifact_lines = [
            f"# Pipeline Execution Artifact: {task_request.description}",
            f"**Pipeline ID**: `{pipeline_id}`",
            f"**Language**: `{task_request.language}`",
            "",
            "## Decomposed Execution Steps",
        ]
        for task in subtasks:
            final_artifact_lines.append(f"- **Step {task.get('step')}**: {task.get('title')} — {task.get('instruction')}")

        final_artifact_lines.extend(["", "## Transformed Artifacts & Code"])
        if extracted_code_blocks:
            for idx, b in enumerate(extracted_code_blocks, start=1):
                status_badge = "✅ Valid AST" if b["ast_valid"] else f"⚠️ Syntax Warning: {b['syntax_error']}"
                final_artifact_lines.extend([
                    f"### Artifact {idx} ({b['language'].upper()}) - {status_badge}",
                    f"```{b['language']}",
                    b["code"],
                    "```",
                    "",
                ])
        else:
            final_artifact_lines.append("*(No code blocks extracted; raw responses recorded in telemetry)*")

        final_artifact_str = "\n".join(final_artifact_lines)
        total_pipeline_ms = (time.perf_counter() - overall_start) * 1000
        stage4_ms = (time.perf_counter() - stage4_start) * 1000

        stages.append(
            StageOutput(
                stage_id=4,
                stage_name="Synthesis & Telemetry",
                status="success",
                input_data={"total_stages_run": 3},
                output_data={"artifact_length": len(final_artifact_str)},
                duration_ms=stage4_ms,
                notes="Synthesized multi-stage artifacts and compiled performance telemetry.",
            )
        )

        overall_success = all(s.status == "success" for s in stages)

        return PipelineSummary(
            pipeline_id=pipeline_id,
            task_request=task_request,
            stages=stages,
            overall_success=overall_success,
            final_artifact=final_artifact_str,
            total_duration_ms=total_pipeline_ms,
            cli_invocations_count=cli_invocations,
            telemetry={
                "total_duration_ms": total_pipeline_ms,
                "stage_breakdown_ms": {s.stage_name: s.duration_ms for s in stages},
                "cli_invocations": cli_invocations,
                "code_blocks_generated": len(extracted_code_blocks),
                "is_fallback_mode": self.cli_wrapper.force_fallback or not self.cli_wrapper.is_cli_available(),
            },
        )

    async def run_async(self, task_request: TaskRequest) -> PipelineSummary:
        """Execute the 4-stage pipeline asynchronously in an event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, task_request)
