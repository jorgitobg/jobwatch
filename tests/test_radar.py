from __future__ import annotations

from datetime import date
from pathlib import Path

from jobwatch.config import Source
from jobwatch.radar import run_once
from jobwatch.transport import FetchError
from tests.helpers import FakeTransport

A = Source("A", "greenhouse", "a")
B = Source("B", "lever", "b")


def gh(*ids: int) -> dict[str, object]:
    return {"jobs": [{"id": i, "title": f"T{i}", "location": {"name": "Remote"},
                      "absolute_url": f"https://x.test/{i}"} for i in ids]}  # fmt: skip


def lv(*ids: str) -> list[dict[str, object]]:
    return [{"id": i, "text": f"T{i}", "workplaceType": "remote",
             "hostedUrl": f"https://x.test/{i}"} for i in ids]  # fmt: skip


def test_first_run_reports_nothing_and_baselines(tmp_path: Path) -> None:
    report = run_once(
        (A,), FakeTransport({"greenhouse": gh(1, 2)}), tmp_path / "s.json", date(2026, 11, 1)
    )
    assert report.new == () and report.baselined == ("A",) and report.total == 2


def test_second_run_reports_only_new_roles(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    run_once((A,), FakeTransport({"greenhouse": gh(1)}), path, date(2026, 11, 1))
    report = run_once((A,), FakeTransport({"greenhouse": gh(1, 2)}), path, date(2026, 11, 2))
    assert [j.id for j in report.new] == ["greenhouse:a:2"] and report.baselined == ()
    again = run_once((A,), FakeTransport({"greenhouse": gh(1, 2)}), path, date(2026, 11, 3))
    assert again.new == ()


def test_a_source_down_on_first_run_is_baselined_later_not_flooded(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    down = FakeTransport({"greenhouse": gh(1), "lever": FetchError("http status 503")})
    first = run_once((A, B), down, path, date(2026, 11, 1))
    assert first.errors == ("B: http status 503",) and first.answered == 1
    up = FakeTransport({"greenhouse": gh(1), "lever": lv("x", "y")})
    second = run_once((A, B), up, path, date(2026, 11, 2))
    assert second.new == () and second.baselined == ("B",)


def test_partial_failure_does_not_forget_a_sources_roles(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    run_once((A,), FakeTransport({"greenhouse": gh(1)}), path, date(2026, 11, 1))
    run_once(
        (A,), FakeTransport({"greenhouse": FetchError("http status 500")}), path, date(2026, 11, 2)
    )
    back = run_once((A,), FakeTransport({"greenhouse": gh(1)}), path, date(2026, 11, 3))
    assert back.new == () and back.errors == ()


def test_total_outage_does_not_write_state(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    report = run_once(
        (A,), FakeTransport({"greenhouse": FetchError("http status 500")}), path, date(2026, 11, 1)
    )
    assert report.answered == 0 and not path.exists()


def test_corrupt_state_is_reported_and_kept(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text("garbage", encoding="utf-8")
    report = run_once((A,), FakeTransport({"greenhouse": gh(1)}), path, date(2026, 11, 1))
    assert "unreadable" in report.errors[0] and (tmp_path / "s.json.corrupt").exists()
    assert report.new == ()
