from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import cast

VERSION = 1
MAX_SEEN = 5000


@dataclass(slots=True)
class State:
    """seen maps job id -> ISO date it was last present; baselined are sources scanned once."""

    seen: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    baselined: set[str] = field(default_factory=lambda: set[str]())

    def prune(self, limit: int = MAX_SEEN) -> None:
        """Keep the most recently seen ids (ties broken by id so the result is deterministic)."""
        if len(self.seen) <= limit:
            return
        keep = sorted(self.seen.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)[:limit]
        self.seen = dict(keep)


def _decode(raw: object) -> State | None:
    if not isinstance(raw, dict):
        return None
    data = cast(dict[str, object], raw)
    seen, baselined = data.get("seen"), data.get("baselined")
    if (
        data.get("version") != VERSION
        or not isinstance(seen, dict)
        or not isinstance(baselined, list)
    ):
        return None
    pairs = cast(dict[object, object], seen)
    names = cast(list[object], baselined)
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in pairs.items()):
        return None
    if not all(isinstance(n, str) for n in names):
        return None
    return State(cast(dict[str, str], dict(pairs)), {cast(str, n) for n in names})


def load_state(path: Path) -> tuple[State, str | None]:
    """Load state. A missing file is a clean start. An unreadable or invalid file is moved aside
    (never silently overwritten) and reported, then the run starts from a fresh baseline."""
    if not path.exists():
        return State(), None
    try:
        state = _decode(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        state = None
    if state is not None:
        return state, None
    aside = path.with_name(path.name + ".corrupt")
    os.replace(path, aside)
    return State(), f"state file was unreadable; moved to {aside.name} and baseline re-recorded"


def save_state(path: Path, state: State) -> None:
    """Write atomically: a crash leaves either the old file or the new one, never half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": VERSION, "baselined": sorted(state.baselined),
               "seen": dict(sorted(state.seen.items()))}  # fmt: skip
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def today_iso(today: date) -> str:
    return today.isoformat()
