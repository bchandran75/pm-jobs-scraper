"""Ashby Job Postings API."""

from __future__ import annotations

import httpx

from pm_jobs_scraper.companies import Company
from pm_jobs_scraper.filters import JobMatch, is_match

ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{board_id}"


def fetch_ashby_jobs(client: httpx.Client, company: Company) -> list[JobMatch]:
    url = ASHBY_URL.format(board_id=company.board_id)
    try:
        resp = client.get(url)
        if resp.status_code in (404, 403):
            return []
        resp.raise_for_status()
    except httpx.HTTPError:
        return []

    matches: list[JobMatch] = []
    for job in resp.json().get("jobs", []):
        title = job.get("title") or ""
        location = job.get("location") or ""
        if not location and job.get("isRemote"):
            location = "Remote"
        job_url = job.get("jobUrl") or job.get("applyUrl") or ""
        m = is_match(company.name, company.category, title, location, job_url, "ashby")
        if m:
            matches.append(m)
    return matches
