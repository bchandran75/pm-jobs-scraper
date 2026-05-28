"""Score scraped jobs against a resume using RAG + heuristics (+ optional LLM)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field

import httpx

from pm_jobs_scraper.filters import JobMatch
from pm_jobs_scraper.resume_rag import ResumeRAG

_LEADERSHIP_TERMS = re.compile(
    r"\b(vp|svp|evp|cpo|head of product|chief product|director|general manager|gm)\b",
    re.I,
)
_DOMAIN_TERMS = re.compile(
    r"\b(ai|ml|genai|e-?commerce|marketplace|crm|ad-?tech|pricing|inventory|forecast)\b",
    re.I,
)


@dataclass
class ScoredJob:
    company: str
    category: str
    title: str
    location: str
    url: str
    region: str
    ats: str
    description: str = ""
    matchScore: int = 0
    matchTier: str = "low"
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    summary: str = ""
    resumeEvidence: list[str] = field(default_factory=list)

    @classmethod
    def from_job(cls, job: JobMatch, **kwargs) -> ScoredJob:
        base = asdict(job)
        base.update(kwargs)
        return cls(**base)


def _tier(score: int) -> str:
    if score >= 80:
        return "strong"
    if score >= 60:
        return "good"
    return "low"


def _job_query(job: JobMatch) -> str:
    parts = [job.title, job.company, job.location, getattr(job, "description", "") or ""]
    return " ".join(p for p in parts if p)


def _heuristic_score(job: JobMatch, rag: ResumeRAG) -> ScoredJob:
    query = _job_query(job)
    retrieved = rag.retrieve(query, top_k=5)
    sim = max((c.score for c in retrieved), default=0.0)

    # 0–55 from semantic overlap with resume chunks
    semantic = int(min(sim * 55 / 0.35, 55)) if sim else 0

    # 0–25 leadership title alignment
    leadership = 25 if _LEADERSHIP_TERMS.search(job.title) else 10

    # 0–20 domain keyword overlap between job text and retrieved chunks
    job_terms = set(_DOMAIN_TERMS.findall(query))
    ctx = " ".join(c.text for c in retrieved)
    ctx_terms = set(_DOMAIN_TERMS.findall(ctx))
    domain = min(20, len(job_terms & ctx_terms) * 7) if job_terms else 5

    score = min(100, semantic + leadership + domain)
    evidence = [c.text[:180] + ("…" if len(c.text) > 180 else "") for c in retrieved[:3]]

    strengths: list[str] = []
    gaps: list[str] = []
    if retrieved:
        strengths.append(f"Resume overlap: {retrieved[0].text[:120].strip()}…")
    if _DOMAIN_TERMS.search(ctx):
        strengths.append("Domain experience (AI/e-commerce/CRM/ad-tech) appears in resume context.")
    if job.region == "india" and re.search(r"bangalore|bengaluru|india", ctx, re.I):
        strengths.append("India / Bangalore alignment with resume location.")
    if not strengths:
        gaps.append("Limited explicit overlap in retrieved resume sections.")
    if "remote" not in job.location.lower() and job.region in ("texas", "california"):
        gaps.append("US role — confirm relocation or remote eligibility.")

    name = _candidate_name_from_env()
    summary = (
        f"{name} shows {'strong' if score >= 80 else 'moderate' if score >= 60 else 'partial'} "
        f"fit for {job.title} at {job.company} based on retrieved resume evidence."
    )

    return ScoredJob.from_job(
        job,
        matchScore=score,
        matchTier=_tier(score),
        strengths=strengths[:3],
        gaps=gaps[:2],
        summary=summary,
        resumeEvidence=evidence,
    )


def _candidate_name_from_env() -> str:
    return os.environ.get("CANDIDATE_NAME", "Candidate")


def _llm_score_batch(jobs: list[JobMatch], rag: ResumeRAG, api_key: str) -> list[ScoredJob]:
    """Refine scores with Claude using RAG context only (not full resume)."""
    name = _candidate_name_from_env()
    payload_jobs = []
    for job in jobs:
        ctx = rag.context_block(_job_query(job), top_k=5)
        payload_jobs.append(
            {
                "id": job.url,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "region": job.region,
                "url": job.url,
                "resume_context": ctx,
            }
        )

    prompt = f"""You are a senior tech recruiter. Score job fit for {name} using ONLY the resume_context per job (RAG excerpts). Do not invent experience not in resume_context.

For each job return: matchScore (0-100), matchTier (strong|good|low), strengths (2-3 strings citing resume_context), gaps (1-2 honest gaps), summary (2 sentences naming {name}).

JOBS:
{json.dumps(payload_jobs, indent=2)}

Return ONLY a JSON array with one object per job, same order, including id (job url). No markdown."""

    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    data = resp.json()
    text = next((b["text"] for b in data.get("content", []) if b.get("type") == "text"), "")
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError("LLM response did not contain JSON array")
    scored_raw = json.loads(text[start : end + 1])

    by_url = {item.get("id"): item for item in scored_raw}
    out: list[ScoredJob] = []
    for job in jobs:
        row = by_url.get(job.url, {})
        base = _heuristic_score(job, rag)
        if row:
            score = int(row.get("matchScore", base.matchScore))
            out.append(
                ScoredJob.from_job(
                    job,
                    matchScore=score,
                    matchTier=row.get("matchTier") or _tier(score),
                    strengths=row.get("strengths") or base.strengths,
                    gaps=row.get("gaps") or base.gaps,
                    summary=row.get("summary") or base.summary,
                    resumeEvidence=base.resumeEvidence,
                )
            )
        else:
            out.append(base)
    return out


def match_jobs(
    jobs: list[JobMatch],
    resume_text: str,
    *,
    use_llm: bool | None = None,
    llm_batch_size: int = 8,
) -> list[ScoredJob]:
    if not jobs:
        return []
    rag = ResumeRAG(resume_text)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    should_llm = use_llm if use_llm is not None else bool(api_key)

    if not should_llm or not api_key:
        return [_heuristic_score(j, rag) for j in jobs]

    scored: list[ScoredJob] = []
    for i in range(0, len(jobs), llm_batch_size):
        batch = jobs[i : i + llm_batch_size]
        try:
            scored.extend(_llm_score_batch(batch, rag, api_key))
        except Exception:
            scored.extend([_heuristic_score(j, rag) for j in batch])
    return scored
