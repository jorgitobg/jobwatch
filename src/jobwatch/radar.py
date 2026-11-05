from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jobwatch.config import Source
from jobwatch.model import Job
from jobwatch.sources import fetch_source
from jobwatch.state import State, load_state, save_state, today_iso
from jobwatch.transport import FetchError, Transport


@dataclass(frozen=True, slots=True)
class Report:
    new: tuple[Job, ...]
    total: int  # remote roles currently listed by the sources that answered
    baselined: tuple[str, ...]  # sources recorded silently for the first time this run
    errors: tuple[str, ...]  # "<source>: <reason>"; also warnings about state
    answered: int = 0  # how many sources answered this run


def scan(
    sources: tuple[Source, ...], transport: Transport
) -> tuple[dict[str, list[Job]], list[str]]:
    """Fetch every source independently: one failure never hides the others."""
    results: dict[str, list[Job]] = {}
    errors: list[str] = []
    for src in sources:
        try:
            results[src.name] = fetch_source(src, transport)
        except FetchError as error:
            errors.append(f"{src.name}: {error}")
    return results, errors


def update(state: State, results: dict[str, list[Job]], today: date) -> tuple[list[Job], list[str]]:
    """Apply one scan to the state. Returns (new jobs, sources baselined this run).

    A source is only allowed to report "new" roles after it has been scanned successfully once.
    Otherwise a source that was down during the first run would flood the next report.
    """
    stamp = today_iso(today)
    new: list[Job] = []
    baselined: list[str] = []
    for name, jobs in results.items():
        first_time = name not in state.baselined
        for job in jobs:
            if not first_time and job.id not in state.seen:
                new.append(job)
            state.seen[job.id] = stamp
        if first_time:
            state.baselined.add(name)
            baselined.append(name)
    state.prune()
    new.sort(key=lambda j: (j.company.lower(), j.title.lower(), j.id))
    return new, baselined


def run_once(
    sources: tuple[Source, ...], transport: Transport, state_path: Path, today: date
) -> Report:
    state, warning = load_state(state_path)
    results, errors = scan(sources, transport)
    if warning:
        errors.insert(0, warning)
    new, baselined = update(state, results, today)
    if results:
        save_state(state_path, state)
    total = sum(len(jobs) for jobs in results.values())
    return Report(tuple(new), total, tuple(baselined), tuple(errors), answered=len(results))
