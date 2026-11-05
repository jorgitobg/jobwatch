from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    source: str  # configured source name
    company: str
    title: str
    location: str
    url: str
