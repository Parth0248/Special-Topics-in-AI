"""CLI Entry Point for Agent C: MCP Tools-Based Bug Assistant Agent.

Usage:
  python main.py --demo
  python main.py --stack-trace "path/to/traceback.txt" --repo "." --apply-patch
  python main.py --stack-trace "Traceback..." --output report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .agent import BugAssistantAgent
except ImportError:
    from agent import BugAssistantAgent


def print_banner():
    banner = r"""
======================================================================
     AGENT C: MCP TOOLS-BASED BUG ASSISTANT (Google ADK)
     Autonomous 5-Phase Bug Triage, Localization & Patch Verification
======================================================================
"""
    print(banner)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Agent C: Software Bug Assistant using FastMCP & Google ADK",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--stack-trace",
        type=str,
        default=None,
        help="Path to file containing stack trace, or raw stack trace string",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=".",
        help="Target repository or workspace directory",
    )
    parser.add_argument(
        "--apply-patch",
        action="store_true",
        help="Permanently apply the synthesized patch if verified",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run end-to-end automated demo on a simulated bug",
    )
    parser.add_argument(
        "--mode",
        choices=["embedded", "mcp"],
        default="embedded",
        help="Tool execution mode (embedded in-process or FastMCP stdio server)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write JSON or Markdown report",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print_banner()

    agent = BugAssistantAgent(
        workspace_root=args.repo,
        use_mcp_server=(args.mode == "mcp"),
    )

    if args.demo:
        print("[*] Running Autonomous Bug Triage Demo...")
        print("    [Phase 1] Intake & Traceback Parsing")
        print("    [Phase 2] Context Gathering via MCP Tools")
        print("    [Phase 3] Minimal Reproducible Test Case Synthesis")
        print("    [Phase 4] Surgical Patch Synthesis (diff -u)")
        print("    [Phase 5] Verification Loop (pre-patch fail -> post-patch pass)")
        print("-" * 70)

        report = agent.run_demo()

        print("\n" + report.summary_markdown)
        print(f"Verification Result: {'PASSED' if report.verification_status else 'FAILED'}")

        if args.output:
            out_path = Path(args.output)
            if out_path.suffix == ".json":
                out_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
            else:
                out_path.write_text(report.summary_markdown, encoding="utf-8")
            print(f"Report saved to: {out_path.resolve()}")

        sys.exit(0 if report.verification_status else 1)

    if not args.stack_trace:
        print("Error: Either --demo or --stack-trace must be provided.")
        print("Run `python main.py --help` for usage.")
        sys.exit(1)

    # Read stack trace from file or raw string
    trace_path = Path(args.stack_trace)
    if trace_path.exists() and trace_path.is_file():
        stack_trace_content = trace_path.read_text(encoding="utf-8")
    else:
        stack_trace_content = args.stack_trace

    print(f"[*] Analyzing stack trace in repository: {Path(args.repo).resolve()}")
    report = agent.diagnose(
        stack_trace=stack_trace_content,
        repo_path=args.repo,
        apply_patch=args.apply_patch,
    )

    if isinstance(report, dict):
        print(f"\n[Error] Bug Assistant diagnosis failed: {report.get('message')}")
        sys.exit(1)

    print("\n" + report.summary_markdown)

    if args.output:
        out_path = Path(args.output)
        if out_path.suffix == ".json":
            out_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        else:
            out_path.write_text(report.summary_markdown, encoding="utf-8")
        print(f"Report saved to: {out_path.resolve()}")

    sys.exit(0 if report.verification_status else 1)


if __name__ == "__main__":
    main()
