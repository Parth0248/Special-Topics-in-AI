"""Command Line Interface (CLI) for Agent D: Production-Quality Code Review Assistant.

Supports reviewing local files, git diffs, pull request descriptions, running the
automated iterative fix pipeline, and executing an end-to-end demo.
"""

import argparse
import json
import os
import sys

# Support running as both module and standalone script
try:
    from .agent import CodeReviewAssistantAgent, create_agent
    from .models import CodeReviewReport
except ImportError:
    from agent import CodeReviewAssistantAgent, create_agent
    from models import CodeReviewReport


DEMO_VULNERABLE_CODE = '''import os
import hashlib
import sqlite3

API_KEY = "AIzaSyD_SECRET_PROD_KEY_98765"

def loginUser(username, password, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Flawed SQL query with string formatting (CWE-89 SQL Injection)
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    user = cursor.fetchone()
    
    # Flawed None comparison (PEP 8 E711)
    if user == None:
        return None
        
    # Weak cryptographic hashing (CWE-327)
    hashed_input = hashlib.md5(password.encode()).hexdigest()
    
    if user[2] == hashed_input:
        return True
    return False

def ping_host(host):
    # Command Injection vulnerability (CWE-78)
    os.system("ping -c 1 " + host)

def process_data(data):
    try:
        val = int(data)
        if val == True:
            return 1
        return val
    except:
        # Bare except (PEP 8 E722 & CWE-703)
        pass
'''


def run_demo(agent: CodeReviewAssistantAgent) -> int:
    """Runs a complete end-to-end interactive demonstration."""
    print("=" * 70)
    print("🚀 Google ADK Agent D: Code Review Assistant — Interactive Demo")
    print("=" * 70)
    print("\n[Stage 1] Ingesting Sample Flawed Python Code...")
    print("-" * 50)
    print(DEMO_VULNERABLE_CODE.strip())
    print("-" * 50)

    print("\n[Stage 2] Running Sequential Review Pipeline (AST, PEP 8, Security)...")
    pr_desc = "Feature: Implement user authentication and diagnostic host ping."
    report = agent.review(code=DEMO_VULNERABLE_CODE, pr_description=pr_desc)

    print("\n" + report.markdown_summary)
    print("=" * 70)

    print("\n[Stage 3] Triggering Iterative Fix Pipeline (LoopAgent Pattern)...")
    fix_results = agent.auto_fix(DEMO_VULNERABLE_CODE, max_iterations=3)

    print(f"\n✅ LoopAgent Completed in {fix_results['iterations']} iteration(s).")
    print(f"Validation Gate Passed: {fix_results['validation_passed']}")
    print(f"Initial Style Score: {fix_results['initial_score']} -> Final Style Score: {fix_results['final_score']}")

    print("\n[Stage 4] Remediated Source Code:")
    print("-" * 50)
    print(fix_results["fixed_code"].strip())
    print("-" * 50)

    # Re-review remediated code
    print("\n[Stage 5] Post-Remediation Re-Audit:")
    post_report = agent.review(code=fix_results["fixed_code"])
    print(f"Post-Fix Status: {post_report.overall_status}")
    print(f"Post-Fix Health Score: {post_report.health_score}/100")
    print(f"Remaining Critical Issues: {post_report.critical_count}")
    print(f"Remaining High Issues: {post_report.high_count}")
    print("=" * 70)
    print("✨ Demo completed successfully!")
    return 0


def main(argv=None) -> int:
    """CLI Entry Point for Agent D."""
    parser = argparse.ArgumentParser(
        description="Google ADK Agent D: Production-Quality Automated Code Review Assistant"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="Path to Python source file to review.",
    )
    parser.add_argument(
        "--diff", "-d",
        type=str,
        help="Unified git diff text or path to diff file.",
    )
    parser.add_argument(
        "--pr-desc",
        type=str,
        default="",
        help="Pull request title and description for contextual review.",
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Run the iterative LoopAgent code fixer on the reviewed code.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Execute an automated end-to-end review and fix demo.",
    )
    parser.add_argument(
        "--output", "-o",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format: markdown (default) or json.",
    )
    parser.add_argument(
        "--save", "-s",
        type=str,
        help="Optional path to save review report.",
    )

    args = parser.parse_args(argv)

    agent = create_agent()

    if args.demo:
        return run_demo(agent)

    # Ingest code or diff
    source_code = None
    git_diff = None

    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            return 1
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            source_code = f.read()

    if args.diff:
        if os.path.exists(args.diff):
            with open(args.diff, "r", encoding="utf-8", errors="replace") as f:
                git_diff = f.read()
        else:
            git_diff = args.diff

    # If nothing provided and piped data present
    if not source_code and not git_diff and not sys.stdin.isatty():
        piped_input = sys.stdin.read()
        if "diff --git" in piped_input or "--- " in piped_input:
            git_diff = piped_input
        else:
            source_code = piped_input

    if not source_code and not git_diff:
        print("Error: Please provide --file, --diff, or --demo. Use --help for usage.", file=sys.stderr)
        return 1

    # Run review pipeline
    report = agent.review(
        code=source_code,
        git_diff=git_diff,
        pr_description=args.pr_desc,
        file_path=args.file,
    )

    # Output review report
    output_text = report.markdown_summary if args.output == "markdown" else json.dumps(report.to_dict(), indent=2)
    print(output_text)

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(output_text)
        print(f"\n[+] Report saved to {args.save}")

    # Handle auto-fix if requested
    if args.auto_fix and source_code:
        print("\n" + "=" * 50)
        print("🔧 Triggering LoopAgent Auto-Fix...")
        print("=" * 50)
        fix_result = agent.auto_fix(source_code)
        print(f"Validation Passed: {fix_result['validation_passed']}")
        print(f"Score: {fix_result['initial_score']} -> {fix_result['final_score']}")
        print("\nRemediated Code:\n")
        print(fix_result["fixed_code"])

        if args.file:
            fixed_file_path = f"{args.file}.fixed.py"
            with open(fixed_file_path, "w", encoding="utf-8") as f:
                f.write(fix_result["fixed_code"])
            print(f"\n[+] Remediated code written to {fixed_file_path}")

    # Return exit code based on severity
    return 1 if report.critical_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
