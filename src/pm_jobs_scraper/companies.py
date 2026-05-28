"""Load target companies from companies.json at project root."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ATSType = Literal["greenhouse", "lever", "ashby"]

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "companies.json"


@dataclass(frozen=True)
class Company:
    name: str
    ats: ATSType
    board_id: str
    category: Literal["ai", "tech"]


def load_companies(path: Path | None = None) -> list[Company]:
    config = path or _CONFIG_PATH
    rows = json.loads(config.read_text(encoding="utf-8"))
    companies: list[Company] = []
    for row in rows:
        if row.get("enabled") is False:
            continue
        companies.append(
            Company(
                name=row["name"],
                ats=row["ats"],
                board_id=row["board_id"],
                category=row["category"],
            )
        )
    return companies


def reload_companies(path: Path | None = None) -> list[Company]:
    """Reload companies from disk (used after config edits)."""
    global COMPANIES
    COMPANIES = load_companies(path)
    return COMPANIES


COMPANIES: list[Company] = load_companies()
