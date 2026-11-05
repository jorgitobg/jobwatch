from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast
from urllib.parse import urlparse

from jobwatch.config import Kind, Source
from jobwatch.model import Job
from jobwatch.transport import FetchError, Transport

URLS: dict[Kind, str] = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{token}",
    "lever": "https://api.lever.co/v0/postings/{token}?mode=json",
}


def _dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _text(value: object, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def _identifier(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, str | int):
        return ""
    return str(value).strip()


def _http_url(value: object) -> str:
    url = _text(value)
    parsed = urlparse(url)
    return url if parsed.scheme in ("http", "https") and parsed.netloc else ""


def _job(
    src: Source, prefix: str, ident: object, title: object, loc: str, url: object
) -> Job | None:
    job_id = _identifier(ident)
    if not job_id:
        return None
    return Job(
        id=f"{prefix}:{src.token}:{job_id}",
        source=src.name,
        company=src.name,
        title=_text(title, "Untitled role"),
        location=loc or "Remote",
        url=_http_url(url),
    )


def parse_greenhouse(src: Source, payload: object) -> list[Job]:
    jobs: list[Job] = []
    for item in _list(_dict(payload).get("jobs")):
        row = _dict(item)
        location = _text(_dict(row.get("location")).get("name"))
        if "remote" in location.lower():
            job = _job(src, "greenhouse", row.get("id"), row.get("title"), location,
                       row.get("absolute_url"))  # fmt: skip
            if job:
                jobs.append(job)
    return jobs


def parse_ashby(src: Source, payload: object) -> list[Job]:
    jobs: list[Job] = []
    for item in _list(_dict(payload).get("jobs")):
        row = _dict(item)
        if row.get("isRemote") is True:
            job = _job(src, "ashby", row.get("id"), row.get("title"), _text(row.get("location")),
                       row.get("jobUrl"))  # fmt: skip
            if job:
                jobs.append(job)
    return jobs


def parse_lever(src: Source, payload: object) -> list[Job]:
    jobs: list[Job] = []
    for item in _list(payload):
        row = _dict(item)
        if _text(row.get("workplaceType")).lower() == "remote":
            location = _text(_dict(row.get("categories")).get("location"))
            job = _job(src, "lever", row.get("id"), row.get("text"), location,
                       row.get("hostedUrl"))  # fmt: skip
            if job:
                jobs.append(job)
    return jobs


PARSERS: dict[Kind, Callable[[Source, object], list[Job]]] = {
    "greenhouse": parse_greenhouse,
    "ashby": parse_ashby,
    "lever": parse_lever,
}


def fetch_source(src: Source, transport: Transport) -> list[Job]:
    """Fetch and parse one source. Raises FetchError with a content-free message."""
    raw = transport.get(URLS[src.kind].format(token=src.token))
    try:
        payload: object = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise FetchError("response is not valid JSON") from error
    return PARSERS[src.kind](src, payload)
