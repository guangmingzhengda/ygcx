from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawJob:
    title: str
    company: str = ""
    city: str = ""
    job_type: str = "校招"
    source: str = "official"
    apply_url: str = ""
    official_url: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    company_info: str = ""
