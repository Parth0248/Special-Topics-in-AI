"""Command Line Interface (CLI) for Agent B: Gemini CLI in ADK Pipeline Tool Agent.

Supports:
  --demo       Run comprehensive end-to-end multi-stage pipeline demonstration
  --task       Execute a specific user task through the pipeline
  --code-file  Provide a source code file as context for analysis/transformation
  --dry-run    Force local offline mock execution without external CLI or network calls
  --format     Output format ('json' or 'text')
  --output     Save the generated final artifact to a file
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from cli_wrapper import GeminiCliWrapper
from pipeline import ADKPipeline
from schemas import PipelineSummary, TaskRequest


def print_banner() -> None:
    banner = """
================================================================================
  Agent B: Gemini CLI in ADK Pipeline Tool Agent
  Google Agent Development Kit (ADK) + Subprocess Execution Architecture
================================================================================
"""
    if HAS_RICH:
        console = Console()
        console.print(Panel.fit(
            "[bold cyan]Agent B: Gemini CLI in ADK Pipeline Tool Agent[/bold cyan]\n"
            "[dim]Google Agent Development Kit (ADK) + Subprocess Execution Architecture[/dim]",
            border_style="cyan",
        ))
    else:
        print(banner)


def render_summary(summary: PipelineSummary, output_format: str = "text") -> None:
    """Render the pipeline summary in rich terminal format or JSON."""
    if output_format == "json":
        print(json.dumps(summary.model_dump(), indent=2))
        return

    if HAS_RICH:
        console = Console()
        # Stage summary table
        table = Table(title="Pipeline Execution Telemetry", show_header=True, header_style="bold magenta")
        table.add_column("Stage #", justify="center", style="cyan", width=8)
        table.add_column("Stage Name", style="bold green", width=36)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Duration (ms)", justify="right", style="yellow", width=14)

        for stage in summary.stages:
            status_style = "[green]SUCCESS[/green]" if stage.status == "success" else "[red]FAILED[/red]"
            table.add_row(
                str(stage.stage_id),
                stage.stage_name,
                status_style,
                f"{stage.duration_ms:.2f}",
            )
        console.print(table)

        # Overview metadata
        console.print(f"\n[bold]Total End-to-End Latency:[/bold] [yellow]{summary.total_duration_ms:.2f} ms[/yellow]")
        console.print(f"[bold]CLI Invocations Executed:[/bold] [cyan]{summary.cli_invocations_count}[/cyan]")
        console.print(f"[bold]Overall Status:[/bold] {'[green]PASSED[/green]' if summary.overall_success else '[red]FAILED[/red]'}")

        # Render Final Artifact
        if summary.final_artifact:
            console.print("\n[bold cyan]Synthesized Final Artifact:[/bold cyan]")
            console.print(Panel(str(summary.final_artifact), title="Synthesized Output", border_style="green"))
    else:
        print("\n--- Pipeline Execution Summary ---")
        print(f"Pipeline ID: {summary.pipeline_id}")
        print(f"Overall Success: {summary.overall_success}")
        print(f"Total Duration: {summary.total_duration_ms:.2f} ms")
        print(f"CLI Tool Calls: {summary.cli_invocations_count}")
        print("\nStage Breakdown:")
        for s in summary.stages:
            print(f"  Stage {s.stage_id} [{s.stage_name}]: {s.status.upper()} ({s.duration_ms:.2f} ms)")
        print("\n--- Final Artifact ---")
        print(summary.final_artifact)


def run_demo(dry_run: bool = False, output_format: str = "text") -> int:
    """Execute the end-to-end demo scenario."""
    print_banner()
    print("\n[DEMO MODE] Running 4-stage SDLC code transformation and unit-test synthesis...\n")

    sample_code = (
        "def compute_discounted_price(price: float, discount_percent: float) -> float:\n"
        "    if discount_percent < 0 or discount_percent > 100:\n"
        "        raise ValueError('Invalid discount')\n"
        "    discount = price * (discount_percent / 100.0)\n"
        "    return round(price - discount, 2)\n"
    )

    req = TaskRequest(
        description="Refactor compute_discounted_price with docstrings, type validation, and produce comprehensive pytest unit tests.",
        code_context=sample_code,
        language="python",
        output_format="json",
        max_timeout_seconds=60,
    )

    wrapper = GeminiCliWrapper(force_fallback=dry_run)
    pipeline = ADKPipeline(cli_wrapper=wrapper)

    start = time.perf_counter()
    summary = pipeline.run(req)
    render_summary(summary, output_format=output_format)
    return 0 if summary.overall_success else 1


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent B: Gemini CLI in ADK Pipeline Tool Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run comprehensive end-to-end pipeline demonstration",
    )
    parser.add_argument(
        "--task",
        type=str,
        help="Task description or prompt to execute through the pipeline",
    )
    parser.add_argument(
        "--code-file",
        type=str,
        help="Path to an existing code file to analyze or transform",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force offline mock fallback without calling external CLI or network APIs",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output display format ('text' or 'json', default: 'text')",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional file path to write final artifact",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="python",
        help="Target language for code analysis and AST checks (default: python)",
    )

    args = parser.parse_args(argv)

    # If demo or no explicit task given, run demo
    if args.demo or not args.task:
        return run_demo(dry_run=args.dry_run, output_format=args.format)

    code_context = None
    if args.code_file:
        file_path = Path(args.code_file)
        if not file_path.exists():
            print(f"Error: Specified code file does not exist: {args.code_file}", file=sys.stderr)
            return 1
        code_context = file_path.read_text(encoding="utf-8")

    req = TaskRequest(
        description=args.task,
        code_context=code_context,
        language=args.language,
        output_format="json" if args.format == "json" else "text",
    )

    wrapper = GeminiCliWrapper(force_fallback=args.dry_run)
    pipeline = ADKPipeline(cli_wrapper=wrapper)

    summary = pipeline.run(req)
    render_summary(summary, output_format=args.format)

    if args.output and summary.final_artifact:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(str(summary.final_artifact), encoding="utf-8")
        print(f"\nFinal artifact successfully saved to: {args.output}")

    return 0 if summary.overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
