"""Headless Gemini CLI Subprocess Executor with Resilient SDK & Mock Fallback.

Executes `gemini -p <prompt> -o json` in non-interactive mode.
Features:
- Timeout guardrails via `subprocess.TimeoutExpired` and `asyncio`.
- Non-zero returncode and stderr capture.
- Robust JSON response extraction with multi-pattern regex fallback.
- Auto-sensing PATH availability for `gemini` executable.
- Seamless fallback to `google.genai` SDK when `GOOGLE_API_KEY` is present.
- Deterministic mock emulator for fully offline testing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Union

from schemas import CliResult

logger = logging.getLogger(__name__)


class GeminiCliWrapper:
    """Wrapper for executing Gemini CLI commands in headless non-interactive mode."""

    def __init__(
        self,
        binary_name: str = "gemini",
        default_timeout: int = 120,
        force_fallback: bool = False,
    ) -> None:
        """Initialize the Gemini CLI executor.

        Args:
            binary_name: Name or absolute path of the Gemini CLI binary.
            default_timeout: Default execution timeout in seconds.
            force_fallback: If True, bypasses CLI binary and uses SDK or mock fallback.
        """
        self.binary_name = binary_name
        self.default_timeout = default_timeout
        self.force_fallback = (
            force_fallback
            or os.getenv("GEMINI_CLI_FALLBACK", "").strip().lower() in ("1", "true", "yes")
        )

    def is_cli_available(self) -> bool:
        """Check if the Gemini CLI binary is available on the system PATH."""
        if self.force_fallback:
            return False
        return shutil.which(self.binary_name) is not None

    def execute_prompt(
        self,
        prompt: str,
        output_format: str = "json",
        codebase_dir: str = ".",
        timeout: Optional[int] = None,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> CliResult:
        """Execute a prompt via Gemini CLI subprocess in synchronous mode.

        Args:
            prompt: Text prompt or instruction for Gemini CLI.
            output_format: Requested output format ('json' or 'text').
            codebase_dir: Working directory for CLI execution.
            timeout: Subprocess timeout in seconds (defaults to self.default_timeout).
            extra_env: Additional environment variables to merge into subprocess env.

        Returns:
            CliResult model with execution status, returncode, response, and telemetry stats.
        """
        timeout_val = timeout or self.default_timeout
        start_time = time.perf_counter()

        # Check if we must use the resilient fallback
        if not self.is_cli_available():
            logger.info("Gemini CLI binary not found or fallback forced; invoking fallback handler.")
            return self._fallback_execution(
                prompt=prompt,
                output_format=output_format,
                codebase_dir=codebase_dir,
                start_time=start_time,
            )

        cmd = [self.binary_name, "-p", prompt, "-o", output_format]
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_val,
                cwd=codebase_dir,
                env=env,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return self._parse_cli_result(result, elapsed_ms)

        except subprocess.TimeoutExpired as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error("Gemini CLI subprocess timed out after %d seconds.", timeout_val)
            raw_out = getattr(exc, "output", getattr(exc, "stdout", ""))
            return CliResult(
                success=False,
                returncode=-1,
                error=f"TimeoutExpired: Subprocess exceeded {timeout_val}s timeout limit",
                raw_output=raw_out.decode("utf-8", errors="replace") if isinstance(raw_out, bytes) else str(raw_out or ""),
                stats={"timed_out": True, "timeout_seconds": timeout_val},
                is_fallback=False,
                execution_time_ms=elapsed_ms,
            )
        except FileNotFoundError as exc:
            logger.warning("Gemini CLI binary '%s' not found: %s. Falling back.", self.binary_name, exc)
            return self._fallback_execution(
                prompt=prompt,
                output_format=output_format,
                codebase_dir=codebase_dir,
                start_time=start_time,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.exception("Unexpected error executing Gemini CLI subprocess: %s", exc)
            return CliResult(
                success=False,
                returncode=getattr(exc, "returncode", 1),
                error=str(exc),
                stats={"unexpected_error": True},
                is_fallback=False,
                execution_time_ms=elapsed_ms,
            )

    async def execute_prompt_async(
        self,
        prompt: str,
        output_format: str = "json",
        codebase_dir: str = ".",
        timeout: Optional[int] = None,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> CliResult:
        """Execute a prompt via Gemini CLI subprocess in asynchronous mode with asyncio guardrails."""
        timeout_val = timeout or self.default_timeout
        start_time = time.perf_counter()

        if not self.is_cli_available():
            # Run fallback in default executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._fallback_execution(prompt, output_format, codebase_dir, start_time),
            )

        cmd = [self.binary_name, "-p", prompt, "-o", output_format]
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=codebase_dir,
                env=env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_val,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            stdout_str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_str = stderr_bytes.decode("utf-8", errors="replace")

            fake_completed = subprocess.CompletedProcess(
                args=cmd,
                returncode=proc.returncode if proc.returncode is not None else 0,
                stdout=stdout_str,
                stderr=stderr_str,
            )
            return self._parse_cli_result(fake_completed, elapsed_ms)

        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error("Async Gemini CLI subprocess timed out after %d seconds.", timeout_val)
            try:
                proc.kill()
            except Exception:
                pass
            return CliResult(
                success=False,
                returncode=-1,
                error=f"TimeoutExpired: Async execution exceeded {timeout_val}s timeout limit",
                stats={"timed_out": True, "async": True},
                is_fallback=False,
                execution_time_ms=elapsed_ms,
            )
        except FileNotFoundError:
            return self._fallback_execution(
                prompt=prompt,
                output_format=output_format,
                codebase_dir=codebase_dir,
                start_time=start_time,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return CliResult(
                success=False,
                returncode=1,
                error=str(exc),
                stats={"async_error": True},
                is_fallback=False,
                execution_time_ms=elapsed_ms,
            )

    def _parse_cli_result(
        self,
        result: subprocess.CompletedProcess,
        elapsed_ms: float,
    ) -> CliResult:
        """Parse the CompletedProcess output, handling JSON envelopes and regex extraction."""
        if result.returncode != 0:
            err_msg = (result.stderr or "").strip() or f"CLI returned non-zero exit code {result.returncode}"
            return CliResult(
                success=False,
                returncode=result.returncode,
                error=err_msg,
                raw_output=result.stdout or "",
                stats={"returncode": result.returncode},
                is_fallback=False,
                execution_time_ms=elapsed_ms,
            )

        stdout_clean = (result.stdout or "").strip()
        parsed_payload: Optional[Union[Dict[str, Any], List[Any]]] = None
        stats: Dict[str, Any] = {"returncode": 0}

        # 1. Attempt standard JSON parsing
        try:
            parsed_payload = json.loads(stdout_clean)
        except (json.JSONDecodeError, TypeError):
            parsed_payload = None

        # 2. Multi-pattern regex extraction fallback
        if parsed_payload is None:
            parsed_payload = self._extract_json_via_regex(stdout_clean)

        if parsed_payload is not None:
            if isinstance(parsed_payload, dict):
                # Standard Gemini CLI JSON schema may wrap output in 'response' and 'stats'
                response_val = parsed_payload.get("response", parsed_payload)
                stats.update(parsed_payload.get("stats", {}))
                return CliResult(
                    success=True,
                    returncode=0,
                    response=response_val,
                    raw_output=stdout_clean,
                    stats=stats,
                    is_fallback=False,
                    execution_time_ms=elapsed_ms,
                )
            else:
                return CliResult(
                    success=True,
                    returncode=0,
                    response={"items": parsed_payload},
                    raw_output=stdout_clean,
                    stats=stats,
                    is_fallback=False,
                    execution_time_ms=elapsed_ms,
                )

        # 3. Fallback to raw text output if not JSON formatted
        stats["raw_text"] = True
        return CliResult(
            success=True,
            returncode=0,
            response=stdout_clean,
            raw_output=stdout_clean,
            stats=stats,
            is_fallback=False,
            execution_time_ms=elapsed_ms,
        )

    def _extract_json_via_regex(self, text: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """Extract JSON objects or arrays from arbitrary terminal or markdown text."""
        if not text:
            return None

        # Pattern A: Markdown code fence ```json ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # Pattern B: First outermost curly braces { ... }
        brace_match = re.search(r"(\{[\s\S]*\})", text)
        if brace_match:
            candidate = brace_match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # Pattern C: First outermost square brackets [ ... ]
        bracket_match = re.search(r"(\[[\s\S]*\])", text)
        if bracket_match:
            candidate = bracket_match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass

        return None

    def _fallback_execution(
        self,
        prompt: str,
        output_format: str,
        codebase_dir: str,
        start_time: float,
    ) -> CliResult:
        """Execute prompt via google.genai SDK or deterministic offline emulator."""
        api_key = os.getenv("GOOGLE_API_KEY", "").strip()

        # Step 1: Try live google.genai SDK if API key is present and not mock
        if api_key and not api_key.startswith("mock_"):
            try:
                from google import genai

                client = genai.Client(api_key=api_key)
                model_name = os.getenv("HARNESS_MODEL", "gemini-2.5-flash")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                resp_text = response.text or ""

                # Try parsing as JSON
                parsed_json = None
                if output_format.lower() == "json":
                    try:
                        parsed_json = json.loads(resp_text)
                    except Exception:
                        parsed_json = self._extract_json_via_regex(resp_text)

                return CliResult(
                    success=True,
                    returncode=0,
                    response=parsed_json if parsed_json is not None else resp_text,
                    raw_output=resp_text,
                    stats={
                        "fallback": "google-genai-sdk",
                        "model": model_name,
                        "sdk_version": getattr(genai, "__version__", "unknown"),
                    },
                    is_fallback=True,
                    execution_time_ms=elapsed_ms,
                )
            except Exception as exc:
                logger.warning(
                    "Fallback to google.genai SDK failed: %s. Using deterministic emulator.",
                    exc,
                )

        # Step 2: Deterministic Mock Emulator
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        mock_response = self._generate_mock_response(prompt, output_format)
        return CliResult(
            success=True,
            returncode=0,
            response=mock_response,
            raw_output=json.dumps(mock_response) if isinstance(mock_response, (dict, list)) else str(mock_response),
            stats={
                "fallback": "mock-emulator",
                "reason": "cli_absent_or_forced_fallback",
            },
            is_fallback=True,
            execution_time_ms=elapsed_ms,
        )

    def _generate_mock_response(
        self,
        prompt: str,
        output_format: str,
    ) -> Union[Dict[str, Any], str]:
        """Generate a realistic, deterministic response for offline execution."""
        prompt_lower = prompt.lower()

        # Specialized mock output for pipeline stages:
        if "decompose" in prompt_lower or "break down" in prompt_lower or "stages" in prompt_lower:
            return {
                "tasks": [
                    {
                        "step": 1,
                        "title": "Analyze Code Structure",
                        "instruction": "Inspect functions, classes, and logic flow.",
                    },
                    {
                        "step": 2,
                        "title": "Synthesize Improvements",
                        "instruction": "Generate refactored code and comprehensive docstrings.",
                    },
                    {
                        "step": 3,
                        "title": "Generate Verification Tests",
                        "instruction": "Produce automated pytest unit tests asserting expected behavior.",
                    },
                ],
                "explanation": "Decomposed user prompt into 3 structured execution steps.",
            }

        if "unit test" in prompt_lower or "test plan" in prompt_lower:
            code_sample = (
                "import pytest\n\n"
                "def test_generated_logic():\n"
                "    assert True\n"
            )
            if output_format.lower() == "json":
                return {
                    "test_code": code_sample,
                    "coverage_targets": ["happy_path", "edge_cases"],
                    "summary": "Generated unit tests for target code context.",
                }
            return f"```python\n{code_sample}\n```"

        if "refactor" in prompt_lower or "optimize" in prompt_lower or "transformation" in prompt_lower:
            refactored_code = (
                "def processed_solution(*args, **kwargs):\n"
                "    \"\"\"Optimized implementation synthesized via Gemini tool.\"\"\"\n"
                "    return {'status': 'processed', 'args': list(args)}\n"
            )
            if output_format.lower() == "json":
                return {
                    "refactored_code": refactored_code,
                    "language": "python",
                    "optimizations": ["AST validated", "PEP 8 compliant"],
                }
            return f"```python\n{refactored_code}\n```"

        # General response
        if output_format.lower() == "json":
            return {
                "status": "success",
                "response": f"[MOCK_GEMINI_CLI] Processed prompt: {prompt[:120]}...",
                "metadata": {"tokens": 42, "model": "mock-gemini-cli"},
            }

        return f"[MOCK_GEMINI_CLI] Processed prompt: {prompt[:120]}..."

    @staticmethod
    def extract_code_blocks(text: str, default_language: str = "python") -> List[Dict[str, str]]:
        """Extract fenced code blocks from markdown text.

        Args:
            text: Markdown or raw text containing optional ```lang code ``` blocks.
            default_language: Fallback language identifier if not specified in fence.

        Returns:
            List of dictionaries with 'language' and 'code' keys.
        """
        blocks = []
        pattern = re.compile(r"```([a-zA-Z0-9_\-+]*)\s*([\s\S]*?)\s*```")
        matches = pattern.findall(text)
        for lang, code in matches:
            clean_lang = lang.strip().lower() or default_language
            blocks.append({"language": clean_lang, "code": code.strip()})

        if not blocks and text.strip():
            # If no code fences were found, treat raw text as code
            blocks.append({"language": default_language, "code": text.strip()})

        return blocks
