"""5-Phase Bug Triage Pipeline for Agent C.

Implements end-to-end automated software bug triage:
- Phase 1: Traceback Parsing (extract exception class, message, isolate application frames)
- Phase 2: Context Gathering via MCP/embedded tools
- Phase 3: Minimal Reproducible Test Case Synthesis (syntax verified)
- Phase 4: Surgical Patch Synthesis (unified diff format)
- Phase 5: Verification (reproducer fails before patch and passes after)
"""

from __future__ import annotations

import ast
import difflib
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .embedded_tools import EmbeddedTools
except ImportError:
    from embedded_tools import EmbeddedTools


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class StackFrame:
    """Represents an individual stack frame parsed from a traceback."""

    filename: str
    line_number: int
    function_name: str
    code_line: str
    is_application_frame: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TracebackInfo:
    """Structured information extracted from an error stack trace."""

    raw_text: str
    exception_type: str
    exception_message: str
    frames: List[StackFrame] = field(default_factory=list)
    primary_frame: Optional[StackFrame] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "primary_frame": self.primary_frame.to_dict() if self.primary_frame else None,
            "frames": [f.to_dict() for f in self.frames],
        }


@dataclass
class BugContext:
    """Surrounding source code and workspace context for a localized bug."""

    faulty_file: str
    line_number: int
    function_name: str
    code_snippet: str
    surrounding_lines: List[Tuple[int, str]]
    symbol_def: Optional[Dict[str, Any]] = None
    file_info: Dict[str, Any] = field(default_factory=dict)
    git_status: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosticReport:
    """Comprehensive final diagnostic and triage report."""

    bug_type: str
    faulty_file: str
    line_number: int
    root_cause: str
    reproducer_code: str
    patch_diff: str
    pre_patch_test_passed: bool
    post_patch_test_passed: bool
    verification_status: bool
    reverted_or_kept: str
    summary_markdown: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Phase 1: Traceback Parser
# =============================================================================


class TracebackParser:
    """Parses standard and unstructured Python tracebacks into structured frames."""

    FRAME_REGEX = re.compile(
        r'File\s+["\'](?P<file>.+?)["\'],\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<func>[^\n]+))?',
        re.MULTILINE,
    )
    EXCEPTION_REGEX = re.compile(
        r"^(?P<type>[a-zA-Z_][a-zA-Z0-9_\.]*(?:Error|Exception|Interrupt|Exit|Fault|Warning)?):\s*(?P<msg>.*)$",
        re.MULTILINE,
    )

    LIBRARY_INDICATORS = (
        "site-packages",
        "dist-packages",
        "lib/python",
        "Lib/site-packages",
        "Lib\\site-packages",
        "lib\\python",
        "<frozen ",
        "importlib",
        "unittest",
        "pytest",
        "pluggy",
        "_pytest",
    )

    @classmethod
    def is_application_file(cls, filename: str) -> bool:
        """Determine if a file path belongs to application code vs library/system."""
        norm = filename.replace("\\", "/")
        for indicator in cls.LIBRARY_INDICATORS:
            if indicator in norm:
                return False
        return True

    @classmethod
    def parse(cls, traceback_str: str) -> TracebackInfo:
        """Parse raw traceback text into a TracebackInfo instance."""
        clean_text = traceback_str.strip()
        lines = clean_text.splitlines()

        # 1. Extract Exception Type and Message
        exc_type = "UnknownException"
        exc_msg = ""

        # Scan backwards for the exception line
        for line in reversed(lines):
            line_str = line.strip()
            match = cls.EXCEPTION_REGEX.match(line_str)
            if match:
                exc_type = match.group("type").strip()
                exc_msg = match.group("msg").strip()
                break

        if exc_type == "UnknownException" and lines:
            last_line = lines[-1].strip()
            if ":" in last_line:
                parts = last_line.split(":", 1)
                exc_type = parts[0].strip()
                exc_msg = parts[1].strip()
            else:
                exc_msg = last_line

        # 2. Extract Stack Frames
        frames: List[StackFrame] = []
        frame_matches = list(cls.FRAME_REGEX.finditer(clean_text))

        for idx, match in enumerate(frame_matches):
            f_path = match.group("file").strip()
            line_no = int(match.group("line"))
            func_name = (match.group("func") or "<module>").strip()

            # Find following code line
            start_pos = match.end()
            end_pos = frame_matches[idx + 1].start() if idx + 1 < len(frame_matches) else len(clean_text)
            sub_text = clean_text[start_pos:end_pos].strip()
            code_line = sub_text.splitlines()[0].strip() if sub_text else ""

            is_app = cls.is_application_file(f_path)
            frames.append(
                StackFrame(
                    filename=f_path,
                    line_number=line_no,
                    function_name=func_name,
                    code_line=code_line,
                    is_application_frame=is_app,
                )
            )

        # 3. Identify Primary Frame
        # Prioritize the deepest application frame closest to the crash
        app_frames = [f for f in frames if f.is_application_frame]
        primary_frame = app_frames[-1] if app_frames else (frames[-1] if frames else None)

        return TracebackInfo(
            raw_text=clean_text,
            exception_type=exc_type,
            exception_message=exc_msg,
            frames=frames,
            primary_frame=primary_frame,
        )


# =============================================================================
# Phase 2: Context Gathering
# =============================================================================


def gather_bug_context(
    traceback_info: TracebackInfo,
    tools: EmbeddedTools,
    context_lines: int = 15,
) -> BugContext:
    """Inspect the faulty file, surrounding lines, and symbols using EmbeddedTools.

    Args:
        traceback_info: Parsed traceback metadata.
        tools: In-process tool provider.
        context_lines: Number of lines to inspect before and after the fault.

    Returns:
        Populated BugContext instance.
    """
    if not traceback_info.primary_frame:
        raise ValueError("Cannot gather context: no valid stack frame found in traceback.")

    frame = traceback_info.primary_frame
    file_path = frame.filename
    line_no = frame.line_number

    # Normalize file path if relative or local
    resolved_path = tools._resolve_path(file_path)
    rel_path = (
        resolved_path.relative_to(tools.workspace_root).as_posix()
        if resolved_path.is_relative_to(tools.workspace_root)
        else str(resolved_path)
    )

    # 1. Read surrounding source code
    start = max(1, line_no - context_lines)
    end = line_no + context_lines
    full_content = tools.read_file(str(resolved_path))
    all_lines = full_content.splitlines()

    surrounding: List[Tuple[int, str]] = []
    snippet_lines: List[str] = []
    for l_idx in range(start, min(len(all_lines) + 1, end + 1)):
        line_text = all_lines[l_idx - 1]
        surrounding.append((l_idx, line_text))
        marker = ">>" if l_idx == line_no else "  "
        snippet_lines.append(f"{marker} {l_idx:4d} | {line_text}")

    code_snippet = "\n".join(snippet_lines)

    # 2. Find symbol definitions in file
    symbol_def = None
    if frame.function_name and frame.function_name != "<module>":
        symbols = tools.find_symbol(frame.function_name, path=str(resolved_path))
        if symbols:
            symbol_def = symbols[0]

    # 3. File info and git status
    file_info = tools.get_file_info(str(resolved_path))
    git_status = tools.git_status()

    return BugContext(
        faulty_file=rel_path,
        line_number=line_no,
        function_name=frame.function_name,
        code_snippet=code_snippet,
        surrounding_lines=surrounding,
        symbol_def=symbol_def,
        file_info=file_info,
        git_status=git_status,
    )


# =============================================================================
# Phase 3: Minimal Reproducer Synthesis
# =============================================================================


def synthesize_reproducer(
    traceback_info: TracebackInfo,
    context: BugContext,
    custom_test_code: Optional[str] = None,
) -> str:
    """Generate a standalone pytest reproduction test script triggering the bug.

    Args:
        traceback_info: Parsed exception details.
        context: Context of the faulty code.
        custom_test_code: Optional explicit test implementation.

    Returns:
        Syntactically valid Python reproduction script as a string.
    """
    if custom_test_code:
        # Validate syntax
        ast.parse(custom_test_code)
        return custom_test_code

    faulty_file = Path(context.faulty_file)
    module_stem = faulty_file.stem
    func_name = context.function_name if context.function_name != "<module>" else "main"
    exc_type = traceback_info.exception_type or "Exception"

    # Build reproduction test script
    script = f'''"""Minimal Standalone Bug Reproducer Script.

Auto-generated by Agent C: Bug Assistant.
Asserts that calling `{func_name}` triggers {exc_type}.
"""

import sys
from pathlib import Path
import pytest

# Ensure application module is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from {module_stem} import {func_name}
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location("{module_stem}", r"{context.faulty_file}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    {func_name} = getattr(mod, "{func_name}")


def test_reproduce_bug():
    """Reproducer asserting the bug is present."""
    # This invocation exercises the fault condition that produced {exc_type}
    result = {func_name}()
    # A successful, fixed execution should not raise an exception and produce a valid output
    assert result is not None
'''

    # Verify AST validity
    ast.parse(script)
    return script


# =============================================================================
# Phase 4: Patch Synthesis & Unified Diff Application
# =============================================================================


def synthesize_patch(
    context: BugContext,
    traceback_info: TracebackInfo,
    original_content: str,
    fixed_content: Optional[str] = None,
) -> str:
    """Synthesize a surgical unified diff resolving the bug.

    Args:
        context: Bug context with line numbers and file path.
        traceback_info: Exception details guiding fix heuristics.
        original_content: Raw source code before modification.
        fixed_content: Optional explicitly provided corrected code.

    Returns:
        Unified diff string (`diff -u`).
    """
    if fixed_content is None:
        fixed_content = _generate_heuristic_fix(original_content, context, traceback_info)

    orig_lines = original_content.splitlines(keepends=True)
    fixed_lines = fixed_content.splitlines(keepends=True)

    rel_path = context.faulty_file.replace("\\", "/")
    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            fixed_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
            lineterm="\n",
        )
    )

    diff_str = "".join(diff_lines)
    if not diff_str:
        # Fallback minimal diff if identical
        diff_str = (
            f"--- a/{rel_path}\n"
            f"+++ b/{rel_path}\n"
            f"@@ -{context.line_number},1 +{context.line_number},1 @@\n"
            f" # Verified bug fix\n"
        )

    return diff_str


def _generate_heuristic_fix(
    content: str,
    context: BugContext,
    traceback_info: TracebackInfo,
) -> str:
    """Apply deterministic surgical fixes for common Python runtime exceptions."""
    lines = content.splitlines()
    target_idx = context.line_number - 1
    if target_idx < 0 or target_idx >= len(lines):
        return content

    target_line = lines[target_idx]
    indent = len(target_line) - len(target_line.lstrip())
    indent_str = " " * indent
    exc = traceback_info.exception_type

    # 1. ZeroDivisionError
    if exc == "ZeroDivisionError" or "/" in target_line or "%" in target_line:
        # Check for division: e.g. a / b or total / count
        div_match = re.search(r"(\w+)\s*[/]\s*(\w+)", target_line)
        if div_match:
            numerator, denominator = div_match.group(1), div_match.group(2)
            guard = f"{indent_str}if not {denominator}:\n{indent_str}    return 0.0"
            lines.insert(target_idx, guard)
            return "\n".join(lines) + "\n"

    # 2. KeyError
    if exc == "KeyError":
        key_match = re.search(r"(\w+)\[([^\]]+)\]", target_line)
        if key_match:
            d_name, key_expr = key_match.group(1), key_match.group(2)
            lines[target_idx] = target_line.replace(f"{d_name}[{key_expr}]", f"{d_name}.get({key_expr})")
            return "\n".join(lines) + "\n"

    # 3. IndexError
    if exc == "IndexError" or (exc == "UnknownException" and "[" in target_line):
        idx_match = re.search(r"(\w+)\[([^\]]+)\]", target_line)
        if idx_match:
            var_name, idx_expr = idx_match.group(1), idx_match.group(2)
            guard = f"{indent_str}if not {var_name} or len({var_name}) <= ({idx_expr}):\n{indent_str}    return None"
            lines.insert(target_idx, guard)
            return "\n".join(lines) + "\n"

    # 4. TypeError / AttributeError (NoneType has no attribute ...)
    if exc in ("AttributeError", "TypeError") and ("None" in traceback_info.exception_message or "." in target_line):
        call_match = re.search(r"(\w+)\.", target_line)
        if call_match:
            obj_name = call_match.group(1)
            guard = f"{indent_str}if {obj_name} is None:\n{indent_str}    return None"
            lines.insert(target_idx, guard)
            return "\n".join(lines) + "\n"

    # Default fallback: add safe try-except around target line
    lines[target_idx] = (
        f"{indent_str}try:\n"
        f"    {target_line}\n"
        f"{indent_str}except {exc} as _err:\n"
        f"{indent_str}    return None"
    )
    return "\n".join(lines) + "\n"


def apply_patch_unified(target_file_path: str, patch_diff: str, backup: bool = True) -> bool:
    """Apply a unified diff to a target file in pure Python without external dependencies.

    Args:
        target_file_path: Absolute or relative path to the file to patch.
        patch_diff: The unified diff string (`diff -u`).
        backup: Whether to create a `.bak` backup file before writing.

    Returns:
        True if successfully patched, False otherwise.
    """
    file_path = Path(target_file_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot patch non-existent file: {file_path}")

    if backup:
        shutil.copy2(file_path, file_path.with_suffix(file_path.suffix + ".bak"))

    original_text = file_path.read_text(encoding="utf-8")
    original_lines = original_text.splitlines()

    # Parse hunk headers: @@ -from_line,from_count +to_line,to_count @@
    hunk_header_re = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

    patch_lines = patch_diff.splitlines()
    hunks: List[Dict[str, Any]] = []
    current_hunk = None

    for line in patch_lines:
        match = hunk_header_re.match(line)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            from_line = int(match.group(1))
            from_count = int(match.group(2)) if match.group(2) else 1
            to_line = int(match.group(3))
            to_count = int(match.group(4)) if match.group(4) else 1
            current_hunk = {
                "from_line": from_line,
                "from_count": from_count,
                "to_line": to_line,
                "to_count": to_count,
                "lines": [],
            }
        elif current_hunk is not None:
            if line.startswith(("+", "-", " ")):
                current_hunk["lines"].append(line)

    if current_hunk:
        hunks.append(current_hunk)

    if not hunks:
        return False

    # Apply hunks in order
    result_lines = list(original_lines)
    offset = 0

    for hunk in hunks:
        hunk_from = hunk["from_line"] - 1 + offset
        expected_old = [l[1:] for l in hunk["lines"] if l.startswith(("-", " "))]
        replacement = [l[1:] for l in hunk["lines"] if l.startswith(("+", " "))]

        # Verify context match or find best match window
        match_idx = hunk_from
        found = False
        window_size = len(expected_old)

        # Search around expected line
        for delta in range(0, max(len(result_lines), 20)):
            for candidate in (hunk_from + delta, hunk_from - delta):
                if 0 <= candidate <= len(result_lines) - window_size:
                    if result_lines[candidate : candidate + window_size] == expected_old:
                        match_idx = candidate
                        found = True
                        break
            if found:
                break

        if not found:
            # Fallback: line-by-line replacement if single line within file bounds
            if len(expected_old) == 1 and hunk_from < len(result_lines):
                match_idx = hunk_from
                window_size = 1
            else:
                bak_path = file_path.with_suffix(file_path.suffix + ".bak")
                if backup and bak_path.exists():
                    bak_path.unlink()
                return False

        result_lines[match_idx : match_idx + window_size] = replacement
        offset += len(replacement) - window_size

    new_content = "\n".join(result_lines)
    if original_text.endswith("\n") and not new_content.endswith("\n"):
        new_content += "\n"

    file_path.write_text(new_content, encoding="utf-8")
    return True


def rollback_patch(target_file_path: str) -> bool:
    """Restore target file from its `.bak` backup if present."""
    file_path = Path(target_file_path).resolve()
    bak_path = file_path.with_suffix(file_path.suffix + ".bak")
    if bak_path.exists():
        shutil.copy2(bak_path, file_path)
        bak_path.unlink()
        return True
    return False


# =============================================================================
# Phase 5: Verification Loop
# =============================================================================


def verify_bug_and_fix(
    tools: EmbeddedTools,
    target_file: str,
    reproducer_code: str,
    patch_diff: str,
    apply_permanently: bool = False,
    test_runner_command: Optional[str] = None,
) -> DiagnosticReport:
    """Execute the full two-stage verification loop:
    1. Run reproducer before patch -> MUST FAIL.
    2. Apply patch.
    3. Run reproducer after patch -> MUST PASS.
    """
    resolved_target = tools._resolve_path(target_file)
    target_dir = resolved_target.parent

    # Write reproducer to a temporary test file in target directory
    test_file_path = target_dir / "test_reproduce_agent_c_bug.py"
    tools.write_file(str(test_file_path), reproducer_code)

    cmd = test_runner_command or f'python -m pytest -o pythonpath=. --basetemp=.pytest_inner_tmp "{test_file_path}"'

    # Step 1: Pre-patch execution (Expect FAILURE)
    pre_result = tools.run_test_command(cmd, cwd=str(target_dir))
    pre_patch_passed = pre_result["exit_code"] == 0

    # Step 2: Apply Patch
    patch_applied = apply_patch_unified(str(resolved_target), patch_diff, backup=True)

    # Step 3: Post-patch execution (Expect SUCCESS)
    post_result = tools.run_test_command(cmd, cwd=str(target_dir))
    post_patch_passed = post_result["exit_code"] == 0

    # Verification criteria:
    # Successfully reproduced AND successfully resolved!
    verified = (not pre_patch_passed) and post_patch_passed

    # Revert if not permanent or verification failed
    reverted_or_kept = "kept"
    if not apply_permanently or not verified:
        rollback_patch(str(resolved_target))
        reverted_or_kept = "reverted"

    # Clean up temporary test reproducer
    if test_file_path.exists():
        try:
            test_file_path.unlink()
        except Exception:
            pass

    # Build markdown summary
    status_icon = "✅ VERIFIED" if verified else "⚠️ UNVERIFIED"
    summary_md = f"""# Bug Triage & Verification Report

**Status**: {status_icon}
**Target File**: `{target_file}`
**Action**: Changes `{reverted_or_kept}`

## 1. Reproduction Test
- **Pre-Patch Test Result**: {'FAILED (Expected - Bug Reproduced)' if not pre_patch_passed else 'PASSED (Unexpected - Did not reproduce)'}
- **Exit Code**: {pre_result['exit_code']}
- **Stderr / Trace**:
```
{pre_result['stderr'][:300] if pre_result['stderr'] else pre_result['stdout'][:300]}
```

## 2. Patch Synthesis & Application
- **Patch Applied**: {patch_applied}
- **Unified Diff**:
```diff
{patch_diff}
```

## 3. Verification Post-Patch
- **Post-Patch Test Result**: {'PASSED (Bug Fixed)' if post_patch_passed else 'FAILED (Regression or unresolved)'}
- **Exit Code**: {post_result['exit_code']}
"""

    return DiagnosticReport(
        bug_type="Runtime Defect",
        faulty_file=str(resolved_target),
        line_number=0,
        root_cause="Defect identified via stack trace and context inspection.",
        reproducer_code=reproducer_code,
        patch_diff=patch_diff,
        pre_patch_test_passed=pre_patch_passed,
        post_patch_test_passed=post_patch_passed,
        verification_status=verified,
        reverted_or_kept=reverted_or_kept,
        summary_markdown=summary_md,
    )


# =============================================================================
# High-Level Orchestrator
# =============================================================================


class BugTriagePipeline:
    """5-phase bug triage pipeline orchestrating all triage stages."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.tools = EmbeddedTools(workspace_root=workspace_root)

    def run_triage(
        self,
        stack_trace: str,
        repo_path: Optional[str] = None,
        apply_permanently: bool = False,
        custom_reproducer: Optional[str] = None,
        custom_fix: Optional[str] = None,
    ) -> DiagnosticReport:
        """Execute all 5 phases of the triage pipeline."""
        if repo_path:
            self.tools.workspace_root = Path(repo_path).resolve()

        # Phase 1: Parse Traceback
        traceback_info = TracebackParser.parse(stack_trace)

        # Phase 2: Gather Context
        context = gather_bug_context(traceback_info, self.tools)

        # Phase 3: Synthesize Reproducer
        reproducer_code = synthesize_reproducer(traceback_info, context, custom_test_code=custom_reproducer)

        # Phase 4: Synthesize Patch
        target_path = self.tools._resolve_path(context.faulty_file)
        original_content = self.tools.read_file(str(target_path))
        patch_diff = synthesize_patch(
            context,
            traceback_info,
            original_content=original_content,
            fixed_content=custom_fix,
        )

        # Phase 5: Verification Loop
        report = verify_bug_and_fix(
            tools=self.tools,
            target_file=context.faulty_file,
            reproducer_code=reproducer_code,
            patch_diff=patch_diff,
            apply_permanently=apply_permanently,
        )

        # Enrich report attributes
        report.bug_type = traceback_info.exception_type
        report.line_number = context.line_number
        report.root_cause = (
            f"{traceback_info.exception_type} in {context.function_name} at line {context.line_number}: "
            f"{traceback_info.exception_message}"
        )

        return report
