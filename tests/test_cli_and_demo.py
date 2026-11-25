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


def test_max_attempts_flag_is_validated(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as info:
        main([*setup(tmp_path), "--max-attempts", "0"], FakeTransport({}))
    assert info.value.code == 2


def test_max_attempts_flag_builds_a_retrying_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    import urllib.error
    import urllib.request

    import jobwatch.transport as transport_module

    def no_sleep(seconds: float) -> None:
        return None

    calls: list[int] = []
    body = json.dumps(JOBS).encode()

    def flaky(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(request.full_url, 503, "x", None, None)  # type: ignore[arg-type]
        return _Body(body)

    class _Body(io.BytesIO):
        def __enter__(self) -> _Body:
            return self

        def __exit__(self, *exc: object) -> None:
            self.close()

    monkeypatch.setattr(urllib.request, "urlopen", flaky)
    monkeypatch.setattr(transport_module.time, "sleep", no_sleep)
    assert main([*setup(tmp_path), "--max-attempts", "3"]) == 0
    assert len(calls) == 3
    calls.clear()
    assert main(setup(tmp_path)) == 3  # default: a single attempt, source down
    assert len(calls) == 1


class _Resp:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, n: int = -1) -> bytes:
        return self._data if n < 0 else self._data[:n]


def _capture_transport(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    import jobwatch.cli as cli_module

    seen: list[dict[str, object]] = []

    class Spy:
        def __init__(self, **kwargs: object) -> None:
            seen.append(kwargs)

        def get(self, url: str) -> bytes:
            return json.dumps(JOBS).encode()

    monkeypatch.setattr(cli_module, "HttpTransport", Spy)
    return seen


def test_max_bytes_default_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from jobwatch.transport import MAX_BYTES

    seen = _capture_transport(monkeypatch)
    assert main(setup(tmp_path)) == 0
    assert seen == [{"max_attempts": 1, "max_bytes": MAX_BYTES}]


def test_max_bytes_flag_is_passed_to_the_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _capture_transport(monkeypatch)
    assert main([*setup(tmp_path), "--max-bytes", "12000000"]) == 0
    assert seen[0]["max_bytes"] == 12_000_000


@pytest.mark.parametrize("value", ["0", "-5", "abc", "1.5", "100000001"])
def test_max_bytes_flag_is_validated(tmp_path: Path, value: str) -> None:
    with pytest.raises(SystemExit) as info:
        main([*setup(tmp_path), "--max-bytes", value], FakeTransport({}))
    assert info.value.code == 2


def test_over_cap_response_fails_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import urllib.request

    calls: list[int] = []

    def big(request: urllib.request.Request, timeout: float) -> _Resp:
        calls.append(1)
        return _Resp(b"x" * 11)

    monkeypatch.setattr(urllib.request, "urlopen", big)
    args = [*setup(tmp_path), "--max-bytes", "10", "--max-attempts", "3"]
    assert main(args) == 3
    assert len(calls) == 1
    assert "response too large" in capsys.readouterr().out
    calls.clear()
    capsys.readouterr()
    assert main([*setup(tmp_path), "--max-bytes", "11", "--max-attempts", "3"]) == 3
    assert len(calls) == 1  # exactly at the cap is accepted; the body is not a board, so no answer
    assert "response too large" not in capsys.readouterr().out
