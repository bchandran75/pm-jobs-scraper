#!/usr/bin/env python3
"""CLI entrypoint for the PM jobs scraping agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without install: python run.py
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pm_jobs_scraper.agent import console, print_results, run_scrape, save_results  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape director+ Product Management roles at AI and leading tech companies "
            "in India, Texas, or California."
        ),
    )
    parser.add_argument(
        "--category",
        choices=["ai", "tech", "all"],
        default="all",
        help="Limit to AI companies, tech companies, or both (default: all)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output"),
        help="Directory for JSON/CSV exports (default: ./output)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print results only; do not write files",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=12,
        help="Parallel company fetch workers (default: 12)",
    )
    args = parser.parse_args()

    categories: set[str] | None = None
    if args.category != "all":
        categories = {args.category}

    console.print("[bold]PM Jobs Scraper Agent[/bold]")
    console.print("Targets: AI + leading tech | Role: PM above Director | Geo: IN, TX, CA\n")

    result = run_scrape(categories=categories, max_workers=args.workers)
    print_results(result.matches, result.stats)

    if not args.no_save and result.matches:
        json_path, csv_path = save_results(result.matches, args.output)
        console.print(f"\nSaved: [link={json_path}]{json_path}[/link]")
        console.print(f"Saved: [link={csv_path}]{csv_path}[/link]")

    return 0 if result.matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
