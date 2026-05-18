"""Orchestrates scraping across all target companies."""

from __future__ import annotations

import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from pm_jobs_scraper.companies import COMPANIES, Company
from pm_jobs_scraper.filters import JobMatch
from pm_jobs_scraper.scrapers import fetch_ashby_jobs, fetch_greenhouse_jobs, fetch_lever_jobs

console = Console()

FETCHERS = {
    "greenhouse": fetch_greenhouse_jobs,
    "lever": fetch_lever_jobs,
    "ashby": fetch_ashby_jobs,
}

USER_AGENT = "pm-jobs-scraper/0.1 (personal job search; +https://github.com/local)"


@dataclass
class ScrapeStats:
    companies_checked: int = 0
    companies_with_board: int = 0
    raw_jobs_seen: int = 0
    errors: int = 0


@dataclass
class ScrapeResult:
    matches: list[JobMatch]
    stats: ScrapeStats


def _fetch_company(
    client: httpx.Client, company: Company
) -> tuple[Company, list[JobMatch], int, str | None]:
    fetcher = FETCHERS[company.ats]
    try:
        jobs = fetcher(client, company)
        raw_count = len(jobs)  # matched only; boards without PM roles return 0
        return company, jobs, raw_count, None
    except Exception as exc:  # noqa: BLE001 — per-company isolation
        return company, [], 0, str(exc)


def run_scrape(
    *,
    categories: set[str] | None = None,
    max_workers: int = 12,
    request_delay_s: float = 0.05,
) -> ScrapeResult:
    targets = [c for c in COMPANIES if not categories or c.category in categories]
    all_matches: list[JobMatch] = []
    stats = ScrapeStats(companies_checked=len(targets))

    timeout = httpx.Timeout(30.0, connect=10.0)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Scraping {len(targets)} companies…", total=len(targets))

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_fetch_company, client, c): c for c in targets}
                for future in as_completed(futures):
                    company, jobs, raw_count, err = future.result()
                    if err:
                        stats.errors += 1
                    elif raw_count >= 0:
                        stats.companies_with_board += 1
                    all_matches.extend(jobs)
                    progress.advance(task)
                    if request_delay_s:
                        time.sleep(request_delay_s)

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[JobMatch] = []
    for m in sorted(all_matches, key=lambda x: (x.company, x.title)):
        if m.url in seen:
            continue
        seen.add(m.url)
        unique.append(m)

    return ScrapeResult(matches=unique, stats=stats)


def print_results(matches: list[JobMatch], stats: ScrapeStats | None = None) -> None:
    if stats:
        console.print(
            f"Checked [bold]{stats.companies_checked}[/bold] companies "
            f"({stats.errors} fetch errors).\n"
        )
    if not matches:
        console.print("[yellow]No matching roles found in this run.[/yellow]")
        console.print(
            "Tip: boards change slugs often — edit [bold]companies.py[/bold] "
            "or relax filters in [bold]filters.py[/bold]."
        )
        return

    table = Table(title="Director+ Product Management — India / TX / CA")
    table.add_column("Company", style="cyan")
    table.add_column("Category")
    table.add_column("Title")
    table.add_column("Location")
    table.add_column("Region")
    table.add_column("Link", overflow="fold")

    for m in matches:
        table.add_row(m.company, m.category, m.title, m.location, m.region, m.url)

    console.print(table)
    console.print(f"\n[green]{len(matches)}[/green] matching role(s).")


def save_results(matches: list[JobMatch], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"pm_jobs_{ts}.json"
    csv_path = output_dir / f"pm_jobs_{ts}.csv"

    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "count": len(matches),
        "filters": {
            "role": "product_management_above_director",
            "regions": ["india", "texas", "california"],
        },
        "jobs": [asdict(m) for m in matches],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["company", "category", "title", "location", "region", "url", "ats"],
        )
        writer.writeheader()
        for m in matches:
            writer.writerow(asdict(m))

    return json_path, csv_path
