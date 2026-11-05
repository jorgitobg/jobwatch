"""Offline demo: python -m jobwatch.demo (synthetic data, no network, deterministic)."""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

from jobwatch.config import Source
from jobwatch.radar import Report, run_once
from jobwatch.render import render_markdown
from jobwatch.transport import FetchError

SOURCES = (
    Source("Example Co", "greenhouse", "example-co"),
    Source("Sample Labs", "ashby", "sample-labs"),
    Source("Demo Works", "lever", "demo-works"),
)

GREENHOUSE_DAY1 = {
    "jobs": [
        {
            "id": 101,
            "title": "Platform Engineer",
            "location": {"name": "Remote - Europe"},
            "absolute_url": "https://boards.example.test/example-co/101",
        },
        {
            "id": 102,
            "title": "Office Manager",
            "location": {"name": "Berlin"},
            "absolute_url": "https://boards.example.test/example-co/102",
        },
    ]
}
GREENHOUSE_DAY2 = {
    "jobs": GREENHOUSE_DAY1["jobs"]
    + [
        {
            "id": 103,
            "title": "Staff **Backend** Engineer [apply here](https://evil.example.test)",
            "location": {"name": "Remote (EU)"},
            "absolute_url": "https://boards.example.test/example-co/103",
        },
        {
            "id": 104,
            "title": "Data Engineer",
            "location": {"name": "Remote"},
            "absolute_url": "javascript:alert(1)",
        },
    ]
}
ASHBY = {
    "jobs": [
        {
            "id": "a-1",
            "title": "ML Engineer",
            "isRemote": True,
            "location": "Spain",
            "jobUrl": "https://jobs.example.test/sample-labs/a-1",
        },
    ]
}
LEVER = [
    {"id": "l-1", "text": "Solutions Architect", "workplaceType": "remote",
     "categories": {"location": "Europe"}, "hostedUrl": "https://lever.example.test/demo-works/l-1"},
]  # fmt: skip


class ScriptedTransport:
    """Serves fixed JSON per provider host; can simulate one provider being down."""

    def __init__(self) -> None:
        self.greenhouse: object = GREENHOUSE_DAY1
        self.ashby_down = False

    def get(self, url: str) -> bytes:
        if "greenhouse" in url:
            return json.dumps(self.greenhouse).encode()
        if "ashby" in url:
            if self.ashby_down:
                raise FetchError("http status 503")
            return json.dumps(ASHBY).encode()
        return json.dumps(LEVER).encode()


def _show(title: str, report: Report) -> None:
    print(f"\n## {title}")
    print(render_markdown(report) or "(nothing to report)")
    print(
        f"[sources answered: {report.answered}/{len(SOURCES)}, remote roles listed: {report.total}]"
    )


def run() -> None:
    transport = ScriptedTransport()
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "state.json"
        transport.ashby_down = True
        _show(
            "Run 1 (2026-11-01): first scan; one provider is down",
            run_once(SOURCES, transport, state, date(2026, 11, 1)),
        )
        transport.ashby_down = False
        _show(
            "Run 2 (2026-11-02): the provider is back; it is baselined now, not reported",
            run_once(SOURCES, transport, state, date(2026, 11, 2)),
        )
        transport.greenhouse = GREENHOUSE_DAY2
        _show(
            "Run 3 (2026-11-03): two new roles; hostile title and link are neutralised",
            run_once(SOURCES, transport, state, date(2026, 11, 3)),
        )
        _show(
            "Run 4 (2026-11-04): nothing changed",
            run_once(SOURCES, transport, state, date(2026, 11, 4)),
        )
        state.write_text("{ not json", encoding="utf-8")
        _show(
            "Run 5 (2026-11-05): state file is corrupt; kept aside, never silently reset",
            run_once(SOURCES, transport, state, date(2026, 11, 5)),
        )
        print(f"\ncorrupt copy kept: {(state.with_name('state.json.corrupt')).exists()}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
