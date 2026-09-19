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
    """Load the nearest .env, searching upward from this file.

    Walking up rather than indexing a fixed number of parents means the project
    can be moved or nested without breaking the lookup.
    """
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".env"
        if candidate.is_file():
            load_dotenv(candidate)
            return


def _show_tool(name: str, args: dict) -> None:
    """Print each tool call so the user can see what the agent is doing."""
    preview = ", ".join(f"{k}={_clip(str(v))}" for k, v in args.items())
    console.print(f"  [yellow]⚒ {name}[/yellow][dim]({preview})[/dim]")


def _clip(value: str, limit: int = 60) -> str:
    flat = value.replace("\n", "↵")
    return flat if len(flat) <= limit else flat[:limit] + "…"


def main() -> int:
    _load_env()

    try:
        agent = Agent(llm=LLM(), on_tool=_show_tool)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    tools = ", ".join(agent.registry.names())
    console.print(f"[dim]harness · {agent.llm.model} · type 'exit' to quit[/dim]")
    console.print(f"[dim]tools: {tools}[/dim]\n")

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
