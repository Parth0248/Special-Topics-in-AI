"""Terminal front end for the harness."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

from .agent import Agent
from .llm import LLM

console = Console()

EXIT_WORDS = {"exit", "quit", ":q"}


def _load_env() -> None:
    """Read .env from this project, then fall back to the repository root."""
    here = Path(__file__).resolve()
    project_root = here.parents[2]
    load_dotenv(project_root / ".env")
    load_dotenv(project_root.parent / ".env")


def main() -> int:
    _load_env()

    try:
        agent = Agent(llm=LLM())
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    console.print(f"[dim]harness · {agent.llm.model} · type 'exit' to quit[/dim]\n")

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

        with console.status("[dim]thinking…[/dim]"):
            reply = agent.send(user_input)

        console.print("\n[bold green]agent ›[/bold green]")
        console.print(Markdown(reply))
        console.print()


if __name__ == "__main__":
    sys.exit(main())
