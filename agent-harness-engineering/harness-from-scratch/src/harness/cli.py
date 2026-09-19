"""Terminal front end for the harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

from .agent import Agent
from .llm import LLM
from .permissions import Decision, Policy

console = Console()

EXIT_WORDS = {"exit", "quit", ":q"}


def _load_env() -> None:
    """Load the nearest .env, searching upward from this file.

    Walking up rather than indexing a fixed number of parents means the project
    can be moved or nested without breaking the lookup.
    """
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".env"
        if candidate.is_file():
            load_dotenv(candidate)
            return


def _clip(value: str, limit: int = 60) -> str:
    flat = value.replace("\n", "↵")
    return flat if len(flat) <= limit else flat[:limit] + "…"


def _show_tool(name: str, args: dict, allowed: bool) -> None:
    """Print each decision so the user sees what ran and what was stopped."""
    preview = ", ".join(f"{k}={_clip(str(v))}" for k, v in args.items())
    mark, color = ("⚒", "yellow") if allowed else ("✗", "red")
    console.print(f"  [{color}]{mark} {name}[/{color}][dim]({preview})[/dim]")


def _confirm(_tool: str, _args: dict, summary: str) -> bool:
    """Ask the user to approve one action."""
    console.print(f"\n  [bold yellow]permission needed[/bold yellow] · {summary}")
    answer = console.input("  [bold]allow? [y/N][/bold] ").strip().lower()
    return answer in {"y", "yes"}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="harness", description="A coding agent built from scratch."
    )
    parser.add_argument(
        "--mode",
        choices=[d.value for d in Decision],
        default=Decision.ASK.value,
        help="What to do with actions that write or execute: run them (allow), "
        "confirm each one (ask), or refuse them (deny). Default: ask.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = _parse_args(argv)
    _load_env()

    policy = Policy(mode=Decision(options.mode), confirm=_confirm)

    try:
        agent = Agent(llm=LLM(), policy=policy, on_tool=_show_tool)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    tools = ", ".join(agent.registry.names())
    console.print(f"[dim]harness · {agent.llm.model} · type 'exit' to quit[/dim]")
    console.print(f"[dim]tools: {tools}[/dim]")
    console.print(f"[dim]permissions: {policy.mode.value}[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold cyan]you ›[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/dim]")
            return 0

        if not user_input:
            continue
        if user_input.lower() in EXIT_WORDS:
            console.print("[dim]bye[/dim]")
            return 0

        reply = agent.send(user_input)

        console.print("\n[bold green]agent ›[/bold green]")
        console.print(Markdown(reply))
        console.print()


if __name__ == "__main__":
    sys.exit(main())
