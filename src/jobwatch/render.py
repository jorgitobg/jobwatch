from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict
from urllib.parse import urlparse

from jobwatch.model import Job
from jobwatch.radar import Report

MAX_SHOWN = 12
_MARKDOWN = re.compile(r"([\\`*_{}\[\]()<>#+!|~&])")


def clean(text: str, limit: int = 120) -> str:
    """Strip control characters, collapse whitespace and cap the length of untrusted text."""
    visible = "".join(
        " " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in text
    )
    collapsed = " ".join(visible.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "\u2026"


def escape(text: str) -> str:
    """Make untrusted text inert in Markdown."""
    return _MARKDOWN.sub(r"\\\1", clean(text))


def safe_link(url: str) -> str | None:
    """Return a Markdown-safe https URL, or None if the URL is not a plain web link."""
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or any(c.isspace() or ord(c) < 32 for c in url)
    ):
        return None
    return url.replace("(", "%28").replace(")", "%29").replace("<", "%3C").replace(">", "%3E")


def _line(job: Job) -> str:
    link = safe_link(job.url)
    where = escape(job.location)
    tail = f"[Apply]({link})" if link else "no valid link"
    return f"- **{escape(job.company)}** \u2014 {escape(job.title)}\n  {where} \u00b7 {tail}"


def render_markdown(report: Report) -> str:
    lines: list[str] = []
    if report.baselined:
        names = ", ".join(escape(n) for n in report.baselined)
        lines.append(f"Baseline recorded for: {names}. Existing roles are not reported.")
    if report.new:
        lines.append(f"**New remote roles ({len(report.new)})**")
        lines += [_line(job) for job in report.new[:MAX_SHOWN]]
        if len(report.new) > MAX_SHOWN:
            lines.append(f"- \u2026 and {len(report.new) - MAX_SHOWN} more.")
    if report.errors:
        lines += ["", "**Partial coverage**"] + [f"- {escape(e)}" for e in report.errors]
    return "\n".join(lines).strip()


def render_json(report: Report) -> str:
    body = {
        "new": [asdict(j) for j in report.new],
        "total": report.total,
        "baselined": list(report.baselined),
        "errors": list(report.errors),
    }
    return json.dumps(body, indent=2, sort_keys=True)
