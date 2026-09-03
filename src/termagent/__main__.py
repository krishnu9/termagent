from __future__ import annotations

import argparse
from pathlib import Path

from termagent.config import ConfigError, load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="termagent")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (default: current directory)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-approve write_file and run_shell (skip confirmation prompts)",
    )
    args = parser.parse_args()
    try:
        config = load_config(args.workspace, auto_approve=args.yes)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    from termagent.tui import run_app

    run_app(config)


if __name__ == "__main__":
    main()
