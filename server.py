#!/usr/bin/env python3
"""Local API for the PM Job Agent UI: scrape, RAG resume, match."""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pm_jobs_scraper.agent import run_match, run_scrape, save_results  # noqa: E402
from pm_jobs_scraper.companies import (  # noqa: E402
    _CONFIG_PATH,
    load_companies,
    reload_companies,
)
from pm_jobs_scraper.search_criteria import (  # noqa: E402
    criteria_from_request,
    load_search_criteria,
    set_search_criteria,
)

RESUME_PATH = ROOT / "resume" / "resume.txt"
AGENT_CONFIG_PATH = ROOT / "config" / "agent.json"
UI_INDEX = ROOT / "ui" / "index.html"
_resume_cache: str | None = None


def _load_resume() -> str:
    global _resume_cache
    if _resume_cache is not None:
        return _resume_cache
    if RESUME_PATH.exists():
        _resume_cache = RESUME_PATH.read_text(encoding="utf-8")
    else:
        _resume_cache = ""
    return _resume_cache


def _set_resume(text: str) -> None:
    global _resume_cache
    RESUME_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESUME_PATH.write_text(text, encoding="utf-8")
    _resume_cache = text


def _load_agent_config() -> dict:
    if AGENT_CONFIG_PATH.exists():
        return json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def _cors(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


class AgentHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: D401
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _json_response(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        _cors(self)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html_response(self, code: int, html: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        _cors(self)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            if UI_INDEX.exists():
                self._html_response(200, UI_INDEX.read_bytes())
            else:
                self._html_response(
                    200,
                    b"<h1>PM Job Agent</h1><p>Missing ui/index.html</p>",
                )
            return
        if path == "/api/health":
            self._json_response(200, {"ok": True, "version": 2})
            return
        if path == "/api/companies":
            rows = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            self._json_response(200, {"companies": rows, "count": len(rows)})
            return
        if path == "/api/config":
            cfg = _load_agent_config()
            crit = load_search_criteria()
            cfg["jobTitles"] = crit.job_titles
            cfg["regions"] = crit.regions
            cfg["requireSeniorPmRules"] = crit.require_senior_pm_rules
            cfg["fetchDescriptions"] = crit.fetch_descriptions
            self._json_response(200, cfg)
            return
        if path == "/api/resume":
            self._json_response(
                200,
                {"resume": _load_resume(), "path": str(RESUME_PATH), "ragReady": bool(_load_resume().strip())},
            )
            return
        self._json_response(404, {"error": "not found"})

    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/config":
            body = self._read_json()
            cfg = _load_agent_config()
            cfg.update(body)
            AGENT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            AGENT_CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            set_search_criteria(None)
            self._json_response(200, {"saved": True})
            return
        if path == "/api/companies":
            body = self._read_json()
            rows = body.get("companies")
            if not isinstance(rows, list):
                self._json_response(400, {"error": "companies array required"})
                return
            _CONFIG_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
            reload_companies()
            self._json_response(200, {"saved": True, "count": len(rows)})
            return
        if path == "/api/resume":
            body = self._read_json()
            text = body.get("resume", "")
            if not isinstance(text, str) or not text.strip():
                self._json_response(400, {"error": "resume text required"})
                return
            _set_resume(text)
            self._json_response(200, {"saved": True, "chars": len(text)})
            return
        self._json_response(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/run":
            self._json_response(404, {"error": "not found"})
            return

        try:
            body = self._read_json()
            category = body.get("category", "all")
            categories = None if category in ("all", None) else {category}
            resume = body.get("resume") or _load_resume()
            if body.get("resume"):
                _set_resume(resume)

            cfg = _load_agent_config()
            name = body.get("candidateName") or cfg.get("candidateName")
            if name:
                os.environ["CANDIDATE_NAME"] = str(name)

            use_llm = body.get("useLlm")
            if use_llm is None and cfg.get("useLlmMatch") is not None:
                use_llm = cfg.get("useLlmMatch")

            companies_path = body.get("companiesPath")
            if companies_path:
                companies = load_companies(Path(companies_path))
            else:
                reload_companies()
                companies = load_companies()

            criteria = criteria_from_request(body)
            set_search_criteria(criteria)
            fast = bool(body.get("fast", True))
            max_workers = int(body.get("workers", 20 if fast else 12))

            t0 = time.perf_counter()
            result = run_scrape(
                categories=categories,
                companies=companies,
                max_workers=max_workers,
                request_delay_s=0.0,
            )
            scrape_s = round(time.perf_counter() - t0, 1)

            t1 = time.perf_counter()
            scored = run_match(result.matches, resume, use_llm=use_llm)
            match_s = round(time.perf_counter() - t1, 1)
            scored.sort(key=lambda j: j.matchScore, reverse=True)

            out_dir = ROOT / "output"
            if scored and not body.get("skipSave"):
                save_results(scored, out_dir, resume_rag=True)

            total_s = round(time.perf_counter() - t0, 1)
            self._json_response(
                200,
                {
                    "stats": asdict(result.stats),
                    "jobs": [asdict(j) for j in scored],
                    "resumeRag": True,
                    "usedLlm": bool(use_llm) and bool(os.environ.get("ANTHROPIC_API_KEY")),
                    "timing": {
                        "scrapeSeconds": scrape_s,
                        "matchSeconds": match_s,
                        "totalSeconds": total_s,
                    },
                    "searchCriteria": {
                        "jobTitles": criteria.job_titles,
                        "regions": criteria.regions,
                        "requireSeniorPmRules": criteria.require_senior_pm_rules,
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"POST /api/run error: {exc}\n")
            self._json_response(500, {"error": str(exc)})


def main() -> None:
    port = int(os.environ.get("AGENT_PORT", "8765"))
    host = os.environ.get("AGENT_HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), AgentHandler)
    print(f"PM Job Agent listening on http://{host}:{port}/")
    print("  Browser UI:  http://127.0.0.1:{port}/".format(port=port))
    print("  GET  /api/companies  /api/resume  /api/config")
    print("  PUT  /api/companies  /api/resume")
    print("  POST /api/run")
    server.serve_forever()


if __name__ == "__main__":
    main()
