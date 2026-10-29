"""Main entry point for Agent A: Deep Research Lead Generation Agent.

Usage:
    python main.py --demo
    python main.py --mock --industry "Fintech" --min-score 70 --output dossier.md
"""

import sys

try:
    from .cli import main, run_cli
except (ImportError, ValueError):
    from cli import main, run_cli

if __name__ == "__main__":
    main()
