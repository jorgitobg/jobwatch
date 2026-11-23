from __future__ import annotations

import math
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol

USER_AGENT = "jobwatch/0.1 (+https://github.com/jorgitobg/jobwatch)"
MAX_BYTES = 5_000_000
MAX_ATTEMPTS_LIMIT = 10
TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})
BACKOFF_BASE_S = 1.0


class FetchError(Exception):
    """A fetch failed. Messages carry a short reason only, never a response body."""


class Transport(Protocol):
    def get(self, url: str) -> bytes: ...


class _Transient(Exception):
    """Internal: a failure worth another attempt. Carries the public reason."""

    def __init__(self, reason: str, retry_after_s: float | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_after_s = retry_after_s


def _parse_retry_after(value: str | None) -> float | None:
    """Delta-seconds only. HTTP-dates, negatives and non-finite values are ignored."""
    if value is None:
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


class HttpTransport:
    """HTTPS GET with a timeout, a hard cap on response size and opt-in bounded retries.

    By default there is exactly one attempt. With ``max_attempts > 1`` only GET requests that
    failed transiently (HTTP 429/500/502/503/504, network error, timeout) are retried, with
    exponential backoff (or a capped ``Retry-After`` in seconds) and never past ``deadline_s``
    in total. Permanent errors, oversized responses and non-HTTPS URLs fail immediately.
    """

    def __init__(
        self,
        timeout_s: float = 15.0,
        max_bytes: int = MAX_BYTES,
        *,
        max_attempts: int = 1,
        deadline_s: float = 60.0,
        max_delay_s: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 1 <= max_attempts <= MAX_ATTEMPTS_LIMIT:
            raise ValueError(f"max_attempts must be between 1 and {MAX_ATTEMPTS_LIMIT}")
        if deadline_s <= 0 or max_delay_s < 0:
            raise ValueError("deadline_s must be positive and max_delay_s not negative")
        self._timeout_s = timeout_s
        self._max_bytes = max_bytes
        self._max_attempts = max_attempts
        self._deadline_s = deadline_s
        self._max_delay_s = max_delay_s
        self._sleep = sleep
        self._clock = clock

    def get(self, url: str) -> bytes:
        if not url.startswith("https://"):
            raise FetchError("only https URLs are fetched")
        started = self._clock()
        attempt = 1
        while True:
            try:
                return self._once(url)
            except _Transient as failure:
                delay = self._delay(attempt, failure.retry_after_s)
                if attempt >= self._max_attempts or (
                    self._clock() - started + delay > self._deadline_s
                ):
                    raise FetchError(failure.reason) from failure
                self._sleep(delay)
                attempt += 1

    def _delay(self, attempt: int, retry_after_s: float | None) -> float:
        wanted = BACKOFF_BASE_S * 2 ** (attempt - 1) if retry_after_s is None else retry_after_s
        return min(wanted, self._max_delay_s)

    def _once(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:  # noqa: S310
                data: bytes = response.read(self._max_bytes + 1)
        except urllib.error.HTTPError as error:
            reason = f"http status {error.code}"
            if error.code in TRANSIENT_STATUSES:
                headers = error.headers
                after = _parse_retry_after(headers.get("Retry-After") if headers else None)
                raise _Transient(reason, after) from error
            raise FetchError(reason) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise _Transient(f"network error ({type(error).__name__})") from error
        if len(data) > self._max_bytes:
            raise FetchError("response too large")
        return data
