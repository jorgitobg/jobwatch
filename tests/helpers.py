from __future__ import annotations

import json

from jobwatch.transport import FetchError


class FakeTransport:
    """Maps a URL fragment to bytes, an object (JSON-encoded) or an exception."""

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.requested: list[str] = []

    def get(self, url: str) -> bytes:
        self.requested.append(url)
        for fragment, value in self.routes.items():
            if fragment in url:
                if isinstance(value, Exception):
                    raise value
                return value if isinstance(value, bytes) else json.dumps(value).encode()
        raise FetchError("http status 404")
