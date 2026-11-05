from __future__ import annotations

import pytest

from jobwatch.config import Source
from jobwatch.sources import fetch_source, parse_ashby, parse_greenhouse, parse_lever
from jobwatch.transport import FetchError
from tests.helpers import FakeTransport

GH = Source("G", "greenhouse", "g")
AS = Source("A", "ashby", "a")
LV = Source("L", "lever", "l")


def test_greenhouse_keeps_only_remote() -> None:
    payload = {"jobs": [
        {"id": 1, "title": "T", "location": {"name": "Remote - EU"}, "absolute_url": "https://x.test/1"},
        {"id": 2, "title": "T", "location": {"name": "Madrid"}, "absolute_url": "https://x.test/2"},
    ]}  # fmt: skip
    jobs = parse_greenhouse(GH, payload)
    assert [j.id for j in jobs] == ["greenhouse:g:1"]


def test_ashby_requires_literal_true() -> None:
    payload = {"jobs": [
        {"id": "x", "title": "T", "isRemote": True, "jobUrl": "https://x.test/x"},
        {"id": "y", "title": "T", "isRemote": "true"},
        {"id": "z", "title": "T", "isRemote": False},
    ]}  # fmt: skip
    assert [j.id for j in parse_ashby(AS, payload)] == ["ashby:a:x"]


def test_lever_filters_on_workplace_type() -> None:
    payload = [
        {"id": "1", "text": "T", "workplaceType": "Remote", "hostedUrl": "https://x.test/1"},
        {"id": "2", "text": "T", "workplaceType": "onsite"},
    ]
    assert [j.id for j in parse_lever(LV, payload)] == ["lever:l:1"]


@pytest.mark.parametrize("payload", [None, 5, "x", [], {}, {"jobs": "x"}, {"jobs": [1, None, "a"]}])
def test_parsers_tolerate_hostile_shapes(payload: object) -> None:
    assert parse_greenhouse(GH, payload) == []
    assert parse_ashby(AS, payload) == []
    assert parse_lever(LV, payload) == []


def test_missing_or_odd_fields_are_handled() -> None:
    payload = {"jobs": [
        {"title": "no id", "location": {"name": "Remote"}},
        {"id": True, "title": "bool id", "location": {"name": "Remote"}},
        {"id": 5, "title": 9, "location": {"name": "Remote"}, "absolute_url": "ftp://x.test/f"},
    ]}  # fmt: skip
    jobs = parse_greenhouse(GH, payload)
    assert len(jobs) == 1 and jobs[0].title == "Untitled role" and jobs[0].url == ""


def test_fetch_source_builds_the_provider_url_and_parses() -> None:
    transport = FakeTransport({"boards-api.greenhouse.io/v1/boards/g/jobs": {"jobs": []}})
    assert fetch_source(GH, transport) == []
    assert transport.requested == ["https://boards-api.greenhouse.io/v1/boards/g/jobs"]


def test_fetch_source_rejects_non_json_without_echoing_it() -> None:
    transport = FakeTransport({"greenhouse": b"<html>SECRET-BODY</html>"})
    with pytest.raises(FetchError) as info:
        fetch_source(GH, transport)
    assert "SECRET" not in str(info.value)
