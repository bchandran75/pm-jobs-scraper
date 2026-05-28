"""Configurable job title and region search criteria (config/agent.json)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pm_jobs_scraper.filters import (
    CALIFORNIA_RE,
    EXCLUDE_TITLE_RE,
    INDIA_RE,
    TEXAS_RE,
    _normalize,
    matches_pm_senior,
)

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "agent.json"

DEFAULT_JOB_TITLES = [
    "VP of Product",
    "VP Product",
    "SVP Product",
    "EVP Product",
    "Director of Product",
    "Senior Director of Product",
    "Head of Product",
    "Chief Product Officer",
    "CPO",
    "General Manager, Product",
]


@dataclass
class SearchCriteria:
    """User-tunable filters applied during scrape."""

    job_titles: list[str] = field(default_factory=lambda: list(DEFAULT_JOB_TITLES))
    regions: list[str] = field(default_factory=lambda: ["india", "texas", "california"])
    # When True, title must match a jobTitles phrase AND built-in senior-PM rules.
    # When False, matching any jobTitles phrase is enough (still applies exclusions).
    require_senior_pm_rules: bool = True
    fetch_descriptions: bool = False

    def title_matches(self, title: str) -> bool:
        t = _normalize(title)
        if EXCLUDE_TITLE_RE.search(t):
            return False

        keyword_ok = True
        if self.job_titles:
            keyword_ok = any(kw.lower() in t.lower() for kw in self.job_titles if kw.strip())

        if self.require_senior_pm_rules:
            return keyword_ok and matches_pm_senior(title)
        return keyword_ok

    def region_matches(self, location: str, title: str = "") -> str | None:
        text = _normalize(f"{location} {title}")
        checks = [
            ("india", INDIA_RE),
            ("texas", TEXAS_RE),
            ("california", CALIFORNIA_RE),
        ]
        for name, pattern in checks:
            if name in self.regions and pattern.search(text):
                return name
        return None


_active: SearchCriteria | None = None


def load_search_criteria(path: Path | None = None) -> SearchCriteria:
    config_path = path or _CONFIG_PATH
    if not config_path.exists():
        return SearchCriteria()

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    titles = raw.get("jobTitles") or raw.get("job_titles") or DEFAULT_JOB_TITLES
    if isinstance(titles, str):
        titles = [t.strip() for t in re.split(r"[,;\n]", titles) if t.strip()]

    regions = raw.get("regions") or ["india", "texas", "california"]
    return SearchCriteria(
        job_titles=list(titles),
        regions=list(regions),
        require_senior_pm_rules=raw.get("requireSeniorPmRules", True),
        fetch_descriptions=raw.get("fetchDescriptions", False),
    )


def get_search_criteria() -> SearchCriteria:
    global _active
    if _active is None:
        _active = load_search_criteria()
    return _active


def set_search_criteria(criteria: SearchCriteria | None) -> None:
    global _active
    _active = criteria


def criteria_from_request(body: dict) -> SearchCriteria:
    base = load_search_criteria()
    titles = body.get("jobTitles")
    if titles is None:
        titles = body.get("job_titles")
    if isinstance(titles, str):
        titles = [t.strip() for t in re.split(r"[,;\n]", titles) if t.strip()]
    regions = body.get("regions") or base.regions
    return SearchCriteria(
        job_titles=list(titles) if titles is not None else base.job_titles,
        regions=list(regions),
        require_senior_pm_rules=body.get(
            "requireSeniorPmRules", base.require_senior_pm_rules
        ),
        fetch_descriptions=body.get("fetchDescriptions", base.fetch_descriptions),
    )
