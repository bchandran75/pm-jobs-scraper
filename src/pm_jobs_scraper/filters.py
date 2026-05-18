"""Role and location filters for director+ product management."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Product management in title (exclude pure engineering / design unless PM clear).
PM_TITLE_RE = re.compile(
    r"\b("
    r"product\s+manag|"
    r"product\s+lead|"
    r"head\s+of\s+product|"
    r"chief\s+product|"
    r"\bcpo\b|"
    r"vp[,/\s]+product|"
    r"svp[,/\s]+product|"
    r"evp[,/\s]+product|"
    r"product\s+director|"
    r"director[,/\s]+product|"
    r"gm[,/\s]+product|"
    r"general\s+manager[,/\s]+product"
    r")\b",
    re.IGNORECASE,
)

# Above director: VP+, C-level, Head of Product, Senior Director+.
# Excludes plain "Director" and IC titles (Principal PM, Group PM, Sr PM).
ABOVE_DIRECTOR_RE = re.compile(
    r"\b("
    r"chief\s+product|"
    r"\bcpo\b|"
    r"head\s+of\s+product|"
    r"\b(?:evp|svp|vp)\b|"
    r"vice\s+president|"
    r"senior\s+director|"
    r"sr\.?\s+director|"
    r"executive\s+director|"
    r"president[,/\s]+product|"
    r"gm[,/\s]+product|"
    r"general\s+manager"
    r")\b",
    re.IGNORECASE,
)

# Down-level titles to reject even if they mention product.
EXCLUDE_TITLE_RE = re.compile(
    r"\b("
    r"principal\s+product|"
    r"group\s+product\s+manag|"
    r"senior\s+product\s+manag|"
    r"staff\s+product|"
    r"associate\s+product|"
    r"product\s+manag(?:er)?\s*(?:i{1,3}|[12])\b|"
    r"intern|"
    r"coordinator|"
    r"analyst|"
    r"associate\s+director"
    r")\b",
    re.IGNORECASE,
)

# Plain "Director" without Senior/Executive — below VP threshold.
PLAIN_DIRECTOR_RE = re.compile(
    r"\bdirector\b",
    re.IGNORECASE,
)
SENIOR_DIRECTOR_RE = re.compile(
    r"\b(senior|sr\.?|executive)\s+director\b",
    re.IGNORECASE,
)

INDIA_RE = re.compile(
    r"\b("
    r"india|"
    r"bangalore|bengaluru|"
    r"hyderabad|"
    r"mumbai|bombay|"
    r"delhi|ncr|gurgaon|gurugram|"
    r"noida|"
    r"pune|"
    r"chennai|"
    r"kolkata|"
    r"ahmedabad|"
    r"remote\s*[-–]?\s*india"
    r")\b",
    re.IGNORECASE,
)

TEXAS_RE = re.compile(
    r"\b("
    r"texas|\btx\b|"
    r"austin|"
    r"dallas|fort\s+worth|"
    r"houston|"
    r"san\s+antonio|"
    r"plano|irving|"
    r"remote\s*[-–]?\s*(?:texas|tx)"
    r")\b",
    re.IGNORECASE,
)

CALIFORNIA_RE = re.compile(
    r"\b("
    r"california|\bca\b|"
    r"san\s+francisco|\bsf\b|"
    r"bay\s+area|silicon\s+valley|"
    r"los\s+angeles|\bla\b|"
    r"san\s+diego|"
    r"san\s+jose|"
    r"mountain\s+view|"
    r"palo\s+alto|"
    r"sunnyvale|"
    r"santa\s+clara|"
    r"menlo\s+park|"
    r"cupertino|"
    r"redwood\s+city|"
    r"irvine|"
    r"sacramento|"
    r"oakland|"
    r"berkeley|"
    r"remote\s*[-–]?\s*(?:california|ca)"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class JobMatch:
    company: str
    category: str
    title: str
    location: str
    url: str
    region: str  # india | texas | california
    ats: str


def _normalize(text: str) -> str:
    return " ".join(text.split())


def matches_pm_senior(title: str) -> bool:
    t = _normalize(title)
    if EXCLUDE_TITLE_RE.search(t):
        return False
    if not PM_TITLE_RE.search(t):
        return False
    if ABOVE_DIRECTOR_RE.search(t):
        # Reject non-senior Director titles (user asked above director level).
        if PLAIN_DIRECTOR_RE.search(t) and not SENIOR_DIRECTOR_RE.search(t):
            if re.search(r"\bvp\b|vice\s+president|chief|cpo|head\s+of\s+product", t, re.I):
                return True
            return False
        return True
    return False


def detect_region(location: str) -> str | None:
    loc = _normalize(location)
    if INDIA_RE.search(loc):
        return "india"
    if TEXAS_RE.search(loc):
        return "texas"
    if CALIFORNIA_RE.search(loc):
        return "california"
    return None


def is_match(company: str, category: str, title: str, location: str, url: str, ats: str) -> JobMatch | None:
    if not matches_pm_senior(title):
        return None
    region = detect_region(f"{location} {title}")
    if not region:
        return None
    return JobMatch(
        company=company,
        category=category,
        title=title,
        location=location,
        url=url,
        region=region,
        ats=ats,
    )
