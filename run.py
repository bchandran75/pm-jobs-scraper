#!/usr/bin/env python3
"""CLI entrypoint for the PM jobs scraping agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without install: python run.py
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pm_jobs_scraper.agent import (  # noqa: E402
    console,
    print_results,
    run_match,
    run_scrape,
    save_results,
)
from pm_jobs_scraper.companies import load_companies  # noqa: E402


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
    parser.add_argument(
        "--companies-file",
        type=Path,
        default=None,
        help="Alternate companies.json path (default: project companies.json)",
    )
    parser.add_argument(
        "--match",
        action="store_true",
        help="Score jobs against resume using RAG (+ LLM if ANTHROPIC_API_KEY set)",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=Path("resume/resume.txt"),
        help="Resume text file for --match (default: resume/resume.txt)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Force heuristic RAG scoring only (no Anthropic API)",
    )
    args = parser.parse_args()

    categories: set[str] | None = None
    if args.category != "all":
        categories = {args.category}

    console.print("[bold]PM Jobs Scraper Agent[/bold]")
    console.print("Targets: AI + leading tech | Role: PM above Director | Geo: IN, TX, CA\n")

    companies = load_companies(args.companies_file) if args.companies_file else None
    result = run_scrape(
        categories=categories,
        companies=companies,
        max_workers=args.workers,
    )

    to_save = result.matches
    resume_rag = False
    if args.match:
        if not args.resume.exists():
            console.print(f"[red]Resume not found:[/red] {args.resume}")
            return 1
        resume_text = args.resume.read_text(encoding="utf-8")
        use_llm = False if args.no_llm else None
        to_save = run_match(result.matches, resume_text, use_llm=use_llm)
        resume_rag = True
        if to_save:
            console.print("\n[bold]Top matches (RAG):[/bold]")
            for j in sorted(to_save, key=lambda x: x.matchScore, reverse=True)[:10]:
                console.print(f"  [{j.matchScore}%] {j.company} — {j.title}")

    if args.match and to_save:
        console.print(f"\n[green]{len(to_save)}[/green] role(s) scored with RAG.")
    elif not args.match:
        print_results(result.matches, result.stats)
    else:
        print_results([], result.stats)

    if not args.no_save and to_save:
        json_path, csv_path = save_results(to_save, args.output, resume_rag=resume_rag)
        console.print(f"\nSaved: [link={json_path}]{json_path}[/link]")
        console.print(f"Saved: [link={csv_path}]{csv_path}[/link]")

    return 0 if to_save else 1


if __name__ == "__main__":
    raise SystemExit(main())
