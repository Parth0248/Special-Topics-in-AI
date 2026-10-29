"""Command Line Interface (CLI) for Agent A: Deep Research Lead Generation.

Supports rich terminal output, demo walkthroughs, customizable search criteria,
offline mock execution, and dossier file generation.
"""

import argparse
import os
import sys
from typing import List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    from .agent import LeadGenAgent
    from .models import TargetMarketCriteria
except (ImportError, ValueError):
    from agent import LeadGenAgent
    from models import TargetMarketCriteria

console = Console()


def create_parser() -> argparse.ArgumentParser:
    """Builds the argument parser for Agent A CLI."""
    parser = argparse.ArgumentParser(
        prog="agent_a_lead_gen",
        description="Google ADK Agent A: Deep Research Lead Generation Agent",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run an automated end-to-end showcase with sample Fintech criteria.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force deterministic offline execution using curated mock dataset.",
    )
    parser.add_argument(
        "--industry",
        type=str,
        default="Fintech",
        help="Target industry sector (e.g., 'Fintech', 'Healthcare AI', 'Enterprise SaaS').",
    )
    parser.add_argument(
        "--geography",
        type=str,
        default="Global",
        help="Target geographic region (e.g., 'North America', 'Europe', 'Global').",
    )
    parser.add_argument(
        "--min-headcount",
        type=int,
        default=None,
        help="Minimum number of employees.",
    )
    parser.add_argument(
        "--max-headcount",
        type=int,
        default=None,
        help="Maximum number of employees.",
    )
    parser.add_argument(
        "--stages",
        type=str,
        default="",
        help="Comma-separated target funding stages (e.g., 'Series A,Series B').",
    )
    parser.add_argument(
        "--signals",
        type=str,
        default="",
        help="Comma-separated growth triggers (e.g., 'hiring,expansion,SOC2').",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default="",
        help="Comma-separated product keywords (e.g., 'payments,open banking,API').",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=60.0,
        help="Minimum overall fit score to qualify a lead (0.0 to 100.0).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Maximum candidate companies to search and evaluate (default: 8).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional file path to export the dossier (e.g., 'lead_dossier.md').",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output file format ('markdown' or 'json').",
    )
    return parser


def run_cli(args: Optional[List[str]] = None) -> int:
    """Entry point for executing the CLI."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    console.print(
        Panel.fit(
            Text.assemble(
                ("Google Agent Development Kit (ADK)\n", "bold cyan"),
                ("Agent A: Deep Research Lead Generation Agent\n", "bold green"),
                ("Multi-hop research, firmographic extraction, and weighted lead fit scoring", "italic white"),
            ),
            box=box.DOUBLE,
            border_style="cyan",
        )
    )

    # Demo Mode overrides
    if parsed_args.demo:
        console.print("[bold yellow]🎬 Running in DEMO mode with curated sample criteria...[/bold yellow]\n")
        industry = "Fintech"
        geography = "North America"
        min_headcount = 20
        max_headcount = 250
        stages = ["Series A", "Series B"]
        signals = ["hiring", "Series B", "SOC 2", "compliance"]
        keywords = ["payments", "treasury", "open banking", "underwriting"]
        min_score = 65.0
        mock_mode = True
        output_file = parsed_args.output or "demo_lead_dossier.md"
    else:
        industry = parsed_args.industry
        geography = parsed_args.geography
        min_headcount = parsed_args.min_headcount
        max_headcount = parsed_args.max_headcount
        stages = [s.strip() for s in parsed_args.stages.split(",") if s.strip()]
        signals = [s.strip() for s in parsed_args.signals.split(",") if s.strip()]
        keywords = [k.strip() for k in parsed_args.keywords.split(",") if k.strip()]
        min_score = parsed_args.min_score
        mock_mode = parsed_args.mock or bool(os.environ.get("MOCK_MODE", False))
        output_file = parsed_args.output

    criteria = TargetMarketCriteria(
        industry=industry,
        geography=geography,
        min_headcount=min_headcount,
        max_headcount=max_headcount,
        target_stages=stages,
        key_signals=signals,
        keywords=keywords,
        min_fit_score=min_score,
    )

    # Display criteria panel
    crit_table = Table(show_header=False, box=box.SIMPLE)
    crit_table.add_column("Property", style="bold cyan")
    crit_table.add_column("Value", style="white")
    crit_table.add_row("Target Industry", criteria.industry)
    crit_table.add_row("Geography", criteria.geography)
    crit_table.add_row("Headcount Bounds", f"[{criteria.min_headcount or 'Any'} - {criteria.max_headcount or 'Any'}]")
    crit_table.add_row("Target Stages", ", ".join(criteria.target_stages) if criteria.target_stages else "Any")
    crit_table.add_row("Priority Signals", ", ".join(criteria.key_signals) if criteria.key_signals else "None specified")
    crit_table.add_row("Minimum Fit Score", f"{criteria.min_fit_score}/100")
    crit_table.add_row("Execution Mode", "Offline Mock (Zero-Network)" if mock_mode else "Live Search Grounding")
    console.print(Panel(crit_table, title="Target Market Criteria", border_style="blue"))

    def progress_callback(stage_name: str, step: int, total_steps: int) -> None:
        console.print(f"[bold cyan]▶ Step {step}/{total_steps}:[/bold cyan] [white]{stage_name}[/white]")

    agent = LeadGenAgent(
        mock_mode=mock_mode,
        progress_callback=progress_callback,
    )

    console.print("\n[bold magenta]Starting Deep Research Pipeline...[/bold magenta]")
    dossier = agent.run(criteria=criteria, candidate_limit=parsed_args.limit)

    console.print(f"\n[bold green]✔ Research Complete in {agent.session_state['telemetry'].get('elapsed_seconds', 0)}s![/bold green]")
    console.print(
        f"Analyzed [bold]{dossier.total_candidates_analyzed}[/bold] candidates. "
        f"Qualified: [bold green]{dossier.qualified_leads_count}[/bold green] leads meeting >={criteria.min_fit_score} score.\n"
    )

    # Render Leaderboard Table
    lead_table = Table(
        title=f"Qualified Lead Leaderboard — {criteria.industry}",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    lead_table.add_column("Rank", justify="center", style="dim")
    lead_table.add_column("Company", style="bold white")
    lead_table.add_column("Score", justify="right")
    lead_table.add_column("Tier", justify="center")
    lead_table.add_column("Stage", style="cyan")
    lead_table.add_column("Employees", justify="right")
    lead_table.add_column("Headquarters")

    for rank, item in enumerate(dossier.leads, start=1):
        prof = item.get("profile", {})
        eval_data = item.get("evaluation", {})
        score = eval_data.get("overall_fit_score", 0.0)
        status = eval_data.get("qualification_status", "")

        status_style = "green" if status == "HIGH_FIT" else "cyan" if status == "MEDIUM_FIT" else "yellow"
        lead_table.add_row(
            str(rank),
            prof.get("company_name", ""),
            f"{score:.1f}",
            f"[{status_style}]{status}[/{status_style}]",
            prof.get("funding_stage", "Unknown"),
            str(prof.get("employee_count", prof.get("employee_count_range", "Unknown"))),
            prof.get("headquarters", ""),
        )

    console.print(lead_table)

    # Print Top Candidate Deep-Dive
    if dossier.leads:
        top_lead = dossier.leads[0]
        top_prof = top_lead.get("profile", {})
        top_eval = top_lead.get("evaluation", {})
        console.print(
            Panel(
                f"[bold cyan]{top_prof.get('company_name')} ({top_prof.get('funding_stage')})[/bold cyan]\n"
                f"[italic white]{top_prof.get('overview')}[/italic white]\n\n"
                f"[bold yellow]Rationale:[/bold yellow] {top_eval.get('fit_rationale')}\n\n"
                f"[bold green]Top Growth Signals:[/bold green]\n" +
                "\n".join(f"  • {s}" for s in top_prof.get("growth_signals", [])[:3]),
                title="🏆 Top Ranked Qualified Lead",
                border_style="gold1",
            )
        )

    # Save output if requested
    if output_file:
        content_to_write = (
            dossier.model_dump_json(indent=2)
            if parsed_args.format == "json"
            else dossier.markdown_report or ""
        )
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content_to_write)
        console.print(f"\n[bold green]📄 Dossier successfully saved to:[/bold green] [underline]{os.path.abspath(output_file)}[/underline]")

    return 0


def main() -> None:
    """Direct entry point for command-line execution."""
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
