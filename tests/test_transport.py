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
