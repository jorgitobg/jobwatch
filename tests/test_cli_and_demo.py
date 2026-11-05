from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobwatch import demo
from jobwatch.cli import main
from tests.helpers import FakeTransport

TOML = '[[source]]\nname = "A"\nkind = "greenhouse"\ntoken = "a"\n'
JOBS = {
    "jobs": [
        {"id": 1, "title": "T", "location": {"name": "Remote"}, "absolute_url": "https://x.test/1"}
    ]
}


def setup(tmp_path: Path) -> list[str]:
    (tmp_path / "s.toml").write_text(TOML, encoding="utf-8")
    return ["--config", str(tmp_path / "s.toml"), "--state", str(tmp_path / "state.json")]


def test_first_run_then_new_role(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = setup(tmp_path)
    assert main(args, FakeTransport({"greenhouse": {"jobs": []}})) == 0
    assert "Baseline recorded" in capsys.readouterr().out
    assert main(args, FakeTransport({"greenhouse": JOBS})) == 0
    assert "New remote roles (1)" in capsys.readouterr().out


def test_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([*setup(tmp_path), "--json"], FakeTransport({"greenhouse": JOBS})) == 0
    assert json.loads(capsys.readouterr().out)["total"] == 1


def test_bad_config_exits_2_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "s.toml").write_text("nope = [", encoding="utf-8")
    assert main(["--config", str(tmp_path / "s.toml")]) == 2
    err = capsys.readouterr().err
    assert "not valid TOML" in err and "Traceback" not in err


def test_all_sources_down_exits_3(tmp_path: Path) -> None:
    assert main(setup(tmp_path), FakeTransport({})) == 3


def test_demo_runs_and_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    demo.run()
    first = capsys.readouterr().out
    demo.run()
    assert first == capsys.readouterr().out
    assert "no valid link" in first and "corrupt copy kept: True" in first
    assert "[x](https://evil" not in first and "javascript:" not in first
