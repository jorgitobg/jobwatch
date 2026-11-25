from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from jobwatch.config import ConfigError, load_config
from jobwatch.radar import run_once
from jobwatch.render import render_json, render_markdown
from jobwatch.transport import (
    MAX_ATTEMPTS_LIMIT,
    MAX_BYTES,
    MAX_BYTES_LIMIT,
    HttpTransport,
    Transport,
)

DEFAULT_STATE = Path.home() / ".local" / "state" / "jobwatch" / "state.json"


def _byte_cap(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{raw!r} is not an integer") from None
    if not 1 <= value <= MAX_BYTES_LIMIT:
        raise argparse.ArgumentTypeError(f"must be between 1 and {MAX_BYTES_LIMIT}")
    return value


def main(argv: Sequence[str] | None = None, transport: Transport | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobwatch", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("sources.toml"))
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=1,
        choices=range(1, MAX_ATTEMPTS_LIMIT + 1),
        metavar=f"1..{MAX_ATTEMPTS_LIMIT}",
        help="attempts per source for transient failures (default 1 = no retries)",
    )
    parser.add_argument(
        "--max-bytes",
        type=_byte_cap,
        default=MAX_BYTES,
        metavar=f"1..{MAX_BYTES_LIMIT}",
        help=f"largest response accepted per source, in bytes (default {MAX_BYTES})",
    )
    args = parser.parse_args(argv)
    try:
        sources = load_config(args.config)
    except ConfigError as error:
        print(f"jobwatch: {error}", file=sys.stderr)
        return 2
    report = run_once(
        sources,
        transport or HttpTransport(max_attempts=args.max_attempts, max_bytes=args.max_bytes),
        args.state,
        date.today(),
    )
    output = render_json(report) if args.json else render_markdown(report)
    if output:
        print(output)
    return 0 if report.answered > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
