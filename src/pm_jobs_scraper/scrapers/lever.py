"""Lever Postings API."""

from __future__ import annotations

import httpx

from pm_jobs_scraper.companies import Company
from pm_jobs_scraper.filters import JobMatch, is_match
from pm_jobs_scraper.scrape_utils import strip_html

LEVER_URL = "https://api.lever.co/v0/postings/{board_id}"


def fetch_lever_jobs(client: httpx.Client, company: Company) -> list[JobMatch]:
    url = LEVER_URL.format(board_id=company.board_id)
    try:
        resp = client.get(url, params={"mode": "json"})
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
    except httpx.HTTPError:
        return []

    matches: list[JobMatch] = []
    for job in resp.json():
        title = job.get("text") or ""
        categories = job.get("categories") or {}
        location = categories.get("location") or ""
        if not location:
            all_locs = job.get("allLocations") or []
            location = ", ".join(str(x) for x in all_locs)
        job_url = job.get("hostedUrl") or job.get("applyUrl") or ""
        raw_desc = job.get("descriptionPlain") or job.get("description") or ""
        lists = job.get("lists")
        if not raw_desc and isinstance(lists, list) and lists:
            raw_desc = lists[0].get("content", "") if isinstance(lists[0], dict) else ""
        desc = strip_html(str(raw_desc))
        m = is_match(company.name, company.category, title, location, job_url, "lever")
        if m:
            matches.append(
                JobMatch(
                    company=m.company,
                    category=m.category,
                    title=m.title,
                    location=m.location,
                    url=m.url,
                    region=m.region,
                    ats=m.ats,
                    description=desc,
                )
            )
    return matches
