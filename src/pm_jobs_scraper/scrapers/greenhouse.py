"""Greenhouse Job Board API."""

from __future__ import annotations

import httpx

from pm_jobs_scraper.companies import Company
from pm_jobs_scraper.filters import JobMatch, is_match

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs"


def fetch_greenhouse_jobs(client: httpx.Client, company: Company) -> list[JobMatch]:
    url = GREENHOUSE_URL.format(board_id=company.board_id)
    try:
        resp = client.get(url, params={"content": "false"})
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
    except httpx.HTTPError:
        return []

    matches: list[JobMatch] = []
    for job in resp.json().get("jobs", []):
        title = job.get("title") or ""
        loc_obj = job.get("location") or {}
        location = loc_obj.get("name") if isinstance(loc_obj, dict) else str(loc_obj)
        if not location:
            offices = job.get("offices") or []
            location = ", ".join(
                o.get("name", "") for o in offices if isinstance(o, dict)
            )
        url = job.get("absolute_url") or ""
        m = is_match(company.name, company.category, title, location, url, "greenhouse")
        if m:
            matches.append(m)
    return matches
