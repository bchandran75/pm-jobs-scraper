"""Shared helpers for scrapers."""

from __future__ import annotations

import re

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(html: str, *, max_len: int = 1200) -> str:
    text = _TAG_RE.sub(" ", html or "")
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text
