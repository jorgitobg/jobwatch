from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from jobwatch.config import ConfigError, load_config
from jobwatch.radar import run_once
from jobwatch.render import render_json, render_markdown
from jobwatch.transport import HttpTransport, Transport

DEFAULT_STATE = Path.home() / ".local" / "state" / "jobwatch" / "state.json"


def main(argv: Sequence[str] | None = None, transport: Transport | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobwatch", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("sources.toml"))
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    try:
        sources = load_config(args.config)
    except ConfigError as error:
        print(f"jobwatch: {error}", file=sys.stderr)
        return 2
    report = run_once(sources, transport or HttpTransport(), args.state, date.today())
    output = render_json(report) if args.json else render_markdown(report)
    if output:
        print(output)
    return 0 if report.answered > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
