from __future__ import annotations

import io
import urllib.error
import urllib.request
from typing import Any

import pytest

from jobwatch.transport import FetchError, HttpTransport


class Response(io.BytesIO):
    def __enter__(self) -> Response:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def patch(monkeypatch: pytest.MonkeyPatch, result: object) -> None:
    def fake(request: urllib.request.Request, timeout: float) -> Response:
        assert timeout == 15.0 and request.headers["User-agent"].startswith("jobwatch/")
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, bytes)
        return Response(result)

    monkeypatch.setattr(urllib.request, "urlopen", fake)


def test_success(monkeypatch: pytest.MonkeyPatch) -> None:
    patch(monkeypatch, b"{}")
    assert HttpTransport().get("https://x.test/") == b"{}"


def test_refuses_non_https() -> None:
    with pytest.raises(FetchError):
        HttpTransport().get("http://x.test/")
    with pytest.raises(FetchError):
        HttpTransport().get("file:///etc/passwd")


def test_response_size_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    patch(monkeypatch, b"x" * 11)
    with pytest.raises(FetchError, match="too large"):
        HttpTransport(max_bytes=10).get("https://x.test/")


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (urllib.error.HTTPError("https://x.test/", 503, "SECRET", None, None), "503"),  # type: ignore[arg-type]
        (urllib.error.URLError("SECRET-DETAIL"), "network error"),
        (TimeoutError("SECRET-DETAIL"), "network error"),
    ],
)
def test_errors_are_content_free(
    monkeypatch: pytest.MonkeyPatch, error: Exception, text: str
) -> None:
    patch(monkeypatch, error)
    with pytest.raises(FetchError) as info:
        HttpTransport().get("https://x.test/")
    assert text in str(info.value) and "SECRET" not in str(info.value)


class Script:
    """Scripted urlopen: each call pops the next outcome (bytes or exception)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0
        self.timeouts: list[float] = []

        def fake(request: urllib.request.Request, timeout: float) -> Response:
            assert request.get_method() == "GET"
            self.calls += 1
            self.timeouts.append(timeout)
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            assert isinstance(outcome, bytes)
            return Response(outcome)

        monkeypatch.setattr(urllib.request, "urlopen", fake)


class Clock:
    """Fake clock: sleeping advances time, nothing really waits."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return urllib.error.HTTPError("https://x.test/", code, "SECRET", headers, None)  # type: ignore[arg-type]


def retrying(clock: Clock, **kwargs: Any) -> HttpTransport:
    return HttpTransport(clock=clock.time, sleep=clock.sleep, **kwargs)


def test_default_is_single_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    script = Script(monkeypatch, [http_error(503), b"{}"])
    clock = Clock()
    with pytest.raises(FetchError, match="503"):
        retrying(clock).get("https://x.test/")
    assert script.calls == 1 and clock.sleeps == []


def test_transient_failures_recover(monkeypatch: pytest.MonkeyPatch) -> None:
    script = Script(
        monkeypatch, [http_error(503), urllib.error.URLError("SECRET"), TimeoutError(), b"ok"]
    )
    clock = Clock()
    assert retrying(clock, max_attempts=4).get("https://x.test/") == b"ok"
    assert script.calls == 4
    assert clock.sleeps == [1.0, 2.0, 4.0]  # exponential backoff


def test_attempts_are_exhausted_with_the_last_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    script = Script(monkeypatch, [http_error(502), http_error(503), http_error(504)])
    clock = Clock()
    with pytest.raises(FetchError, match="504") as info:
        retrying(clock, max_attempts=3).get("https://x.test/")
    assert script.calls == 3 and "SECRET" not in str(info.value)
    assert len(clock.sleeps) == 2


def test_deadline_stops_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    script = Script(monkeypatch, [http_error(503)] * 5)
    clock = Clock()
    with pytest.raises(FetchError, match="503"):
        retrying(clock, max_attempts=5, deadline_s=2.5).get("https://x.test/")
    # sleeps 1.0 (t=1.0), then 2.0 would pass the 2.5 s deadline: no more attempts
    assert script.calls == 2 and clock.sleeps == [1.0]


def test_retry_after_is_honoured_and_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    Script(monkeypatch, [http_error(429, "3"), http_error(429, "9999"), b"ok"])
    clock = Clock()
    transport = retrying(clock, max_attempts=3, max_delay_s=10.0)
    assert transport.get("https://x.test/") == b"ok"
    assert clock.sleeps == [3.0, 10.0]


@pytest.mark.parametrize("value", ["soon", "-5", "nan", "inf", "", "Wed, 21 Oct 2026 07:28:00 GMT"])
def test_invalid_retry_after_falls_back_to_backoff(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    Script(monkeypatch, [http_error(503, value), b"ok"])
    clock = Clock()
    assert retrying(clock, max_attempts=2).get("https://x.test/") == b"ok"
    assert clock.sleeps == [1.0]


@pytest.mark.parametrize("code", [400, 401, 403, 404, 410])
def test_permanent_http_errors_are_not_retried(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    script = Script(monkeypatch, [http_error(code), b"ok"])
    clock = Clock()
    with pytest.raises(FetchError, match=str(code)):
        retrying(clock, max_attempts=3).get("https://x.test/")
    assert script.calls == 1 and clock.sleeps == []


def test_oversize_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    script = Script(monkeypatch, [b"x" * 11, b"ok"])
    clock = Clock()
    with pytest.raises(FetchError, match="too large"):
        retrying(clock, max_attempts=3, max_bytes=10).get("https://x.test/")
    assert script.calls == 1


def test_non_https_is_refused_before_any_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    script = Script(monkeypatch, [b"ok"])
    clock = Clock()
    with pytest.raises(FetchError, match="https"):
        retrying(clock, max_attempts=3).get("http://x.test/")
    assert script.calls == 0 and clock.sleeps == []


@pytest.mark.parametrize("kwargs", [{"max_attempts": 0}, {"max_attempts": 11}, {"deadline_s": 0}])
def test_invalid_policy_is_rejected(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        HttpTransport(**kwargs)


def test_request_timeout_never_exceeds_the_time_left(monkeypatch: pytest.MonkeyPatch) -> None:
    script = Script(monkeypatch, [http_error(503), http_error(503), http_error(503)])
    clock = Clock()
    with pytest.raises(FetchError):
        retrying(clock, max_attempts=3, deadline_s=10.0, timeout_s=8.0).get("https://x.test/")
    # t=0: min(8, 10); t=1: min(8, 9); t=3: min(8, 7)
    assert script.timeouts == [8.0, 8.0, 7.0]
