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
    args = parser.parse_args()
    try:
        config = load_config(args.workspace)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    from termagent.tui import run_app

    run_app(config)


if __name__ == "__main__":
    main()
