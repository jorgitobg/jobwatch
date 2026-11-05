from __future__ import annotations

import urllib.error
import urllib.request
from typing import Protocol

USER_AGENT = "jobwatch/0.1 (+https://github.com/jorgitobg/jobwatch)"
MAX_BYTES = 5_000_000


class FetchError(Exception):
    """A fetch failed. Messages carry a short reason only, never a response body."""


class Transport(Protocol):
    def get(self, url: str) -> bytes: ...


class HttpTransport:
    """HTTPS GET with a timeout and a hard cap on response size."""

    def __init__(self, timeout_s: float = 15.0, max_bytes: int = MAX_BYTES) -> None:
        self._timeout_s = timeout_s
        self._max_bytes = max_bytes

    def get(self, url: str) -> bytes:
        if not url.startswith("https://"):
            raise FetchError("only https URLs are fetched")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:  # noqa: S310
                data: bytes = response.read(self._max_bytes + 1)
        except urllib.error.HTTPError as error:
            raise FetchError(f"http status {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise FetchError(f"network error ({type(error).__name__})") from error
        if len(data) > self._max_bytes:
            raise FetchError("response too large")
        return data
