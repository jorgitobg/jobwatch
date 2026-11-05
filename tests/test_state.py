from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from jobwatch.state import State, load_state, save_state


def test_missing_file_is_a_clean_start(tmp_path: Path) -> None:
    state, warning = load_state(tmp_path / "s.json")
    assert state.seen == {} and warning is None


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "s.json"
    save_state(path, State({"a": "2026-11-01"}, {"src"}))
    state, warning = load_state(path)
    assert state.seen == {"a": "2026-11-01"} and state.baselined == {"src"} and warning is None


@pytest.mark.parametrize(
    "content",
    [
        "{ not json",
        "[]",
        json.dumps({"version": 99, "seen": {}, "baselined": []}),
        json.dumps({"version": 1, "seen": [], "baselined": []}),
        json.dumps({"version": 1, "seen": {"a": 1}, "baselined": []}),
        json.dumps({"version": 1, "seen": {}, "baselined": [1]}),
    ],
)
def test_invalid_state_is_moved_aside_not_overwritten(tmp_path: Path, content: str) -> None:
    path = tmp_path / "s.json"
    path.write_text(content, encoding="utf-8")
    state, warning = load_state(path)
    assert state.seen == {} and warning is not None
    assert (tmp_path / "s.json.corrupt").read_text(encoding="utf-8") == content
    assert not path.exists()


def test_retention_keeps_the_most_recent_not_the_lexically_last() -> None:
    state = State({"zzz-old": "2026-01-01", "aaa-new": "2026-11-01", "mmm-new": "2026-11-02"})
    state.prune(limit=2)
    assert set(state.seen) == {"aaa-new", "mmm-new"}


def test_prune_is_a_noop_under_the_limit() -> None:
    state = State({"a": "2026-01-01"})
    state.prune()
    assert state.seen == {"a": "2026-01-01"}


def test_failed_write_leaves_the_old_file_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "s.json"
    save_state(path, State({"keep": "2026-11-01"}))

    def boom(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        save_state(path, State({"new": "2026-11-02"}))
    monkeypatch.undo()
    assert load_state(path)[0].seen == {"keep": "2026-11-01"}
    assert [p.name for p in tmp_path.iterdir()] == ["s.json"]
