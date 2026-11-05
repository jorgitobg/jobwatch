from __future__ import annotations

import json

import pytest

from jobwatch.model import Job
from jobwatch.radar import Report
from jobwatch.render import clean, escape, render_json, render_markdown, safe_link


def job(**kw: str) -> Job:
    base = {"id": "i", "source": "S", "company": "Co", "title": "T", "location": "Remote",
            "url": "https://x.test/1"}  # fmt: skip
    return Job(**{**base, **kw})


def report(*jobs: Job, **kw: object) -> Report:
    return Report(new=jobs, total=len(jobs), baselined=(), errors=(), **kw)  # type: ignore[arg-type]


def test_markdown_in_titles_is_inert() -> None:
    text = render_markdown(report(job(title="**bold** [x](https://evil.test) <b>")))
    assert "[x](https://evil.test)" not in text and "\\[x\\]" in text and "<b>" not in text


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,x",
        "http://x.test/",
        "https://",
        "",
        "https://x.test/a b",
        "https://x.test/\n",
    ],
)
def test_unsafe_links_are_dropped(url: str) -> None:
    assert safe_link(url) is None
    assert "no valid link" in render_markdown(report(job(url=url)))


def test_link_parentheses_cannot_break_out() -> None:
    link = safe_link("https://x.test/a)(https://evil.test")
    assert link is not None and ")(" not in link


def test_clean_strips_controls_and_caps_length() -> None:
    assert clean("a\x00b\u202ec\nd") == "a b c d"
    assert len(clean("x" * 500)) == 120 and clean("x" * 500).endswith("\u2026")


def test_escape_special_characters() -> None:
    assert escape("a_b*c") == "a\\_b\\*c"


def test_long_lists_are_truncated_deterministically() -> None:
    text = render_markdown(report(*[job(id=str(i), title=f"T{i}") for i in range(15)]))
    assert text.count("- **") == 12 and "and 3 more" in text and "T12" not in text


def test_errors_and_baseline_are_shown() -> None:
    r = Report(new=(), total=0, baselined=("A",), errors=("B: http status 503",))
    text = render_markdown(r)
    assert "Baseline recorded for: A" in text and "Partial coverage" in text and "503" in text
    assert render_markdown(Report((), 0, (), ())) == ""


def test_json_output_is_stable() -> None:
    body = json.loads(render_json(report(job())))
    assert body["total"] == 1 and body["new"][0]["id"] == "i" and body["errors"] == []
