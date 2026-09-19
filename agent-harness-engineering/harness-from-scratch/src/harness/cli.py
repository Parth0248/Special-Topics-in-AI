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
from .sandbox import DockerSandbox, HostSandbox
from .subagents import delegation_tool
from .tools import default_registry

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
    parser.add_argument(
        "--workspace",
        default=".",
        help="The directory the agent may act in. It cannot read or write "
        "outside this. Default: the current directory.",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Run shell commands in a container instead of on this machine.",
    )
    return parser.parse_args(argv)


def _build_sandbox(options: argparse.Namespace):
    workspace = Path(options.workspace)
    if not options.docker:
        return HostSandbox(workspace)

    if not DockerSandbox.available():
        console.print(
            "[red]Docker is not available. Start it, or drop --docker to run "
            "on this machine.[/red]"
        )
        raise SystemExit(1)
    return DockerSandbox(workspace)


def main(argv: list[str] | None = None) -> int:
    options = _parse_args(argv)
    _load_env()

    sandbox = _build_sandbox(options)
    policy = Policy(mode=Decision(options.mode), confirm=_confirm)

    try:
        agent = Agent(
            llm=LLM(),
            registry=default_registry(sandbox),
            policy=policy,
            on_tool=_show_tool,
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    # Registered after construction because the tool closes over the agent that
    # owns it — that is what gives a subagent the parent's sandbox and policy.
    agent.registry.add(delegation_tool(agent))

    where = "docker" if options.docker else "host"
    tools = ", ".join(agent.registry.names())
    console.print(f"[dim]harness · {agent.llm.model} · type 'exit' to quit[/dim]")
    console.print(f"[dim]tools: {tools}[/dim]")
    console.print(f"[dim]permissions: {policy.mode.value} · sandbox: {where}[/dim]")
    console.print(f"[dim]workspace: {sandbox.workspace}[/dim]\n")

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
