"""CLI entry: python run_cli.py <subcommand> ..."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mechanical_control.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
