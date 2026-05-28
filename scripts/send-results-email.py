#!/usr/bin/env python3
"""Email latest scrape results via SMTP (stdlib only — no npm)."""

from __future__ import annotations

import json
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "output"
DEFAULT_TO = "balaji.chandran@yahoo.com"


def load_env() -> None:
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip("'\"")
        os.environ.setdefault(key, val)


def latest_json() -> Path | None:
    if not OUTPUT_DIR.is_dir():
        return None
    files = sorted(OUTPUT_DIR.glob("pm_jobs_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def build_bodies(payload: dict, scraped_at: str) -> tuple[str, str]:
    jobs = payload.get("jobs") or []
    count = payload.get("count", len(jobs))
    text = [
        f"PM Jobs Scraper — {scraped_at}",
        "Director+ Product roles | India, Texas, California",
        "",
    ]
    html = [
        "<h2>PM Jobs Scraper</h2>",
        f"<p><strong>{scraped_at}</strong><br>Director+ PM · India / TX / CA</p>",
    ]
    if not count:
        text.append("No matching roles in this run.")
        html.append("<p><em>No matching roles in this run.</em></p>")
    else:
        text.append(f"{count} matching role(s):\n")
        html.append("<ul>")
        for j in jobs:
            text += f"\n{j['company']} | {j.get('region', '').upper()}\n  {j['title']}\n  {j['location']}\n  {j['url']}\n"
            html.append(
                f"<li><b>{j['company']}</b> ({j.get('region', '')}) — "
                f"<a href=\"{j['url']}\">{j['title']}</a><br>{j['location']}</li>"
            )
        html.append("</ul>")
    text.append("\nFull JSON attached.")
    html.append("<p><small>Full JSON attached.</small></p>")
    return "\n".join(text), "".join(html)


def main() -> int:
    load_env()
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    host = os.environ.get("SMTP_HOST", "smtp.mail.yahoo.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    from_addr = os.environ.get("EMAIL_FROM") or user
    to_addr = os.environ.get("EMAIL_TO", DEFAULT_TO)

    if not user or not password:
        print("Email skipped: set SMTP_USER and SMTP_PASS in .env")
        return 1

    path = latest_json()
    payload: dict = {"count": 0, "jobs": []}
    scraped_at = datetime.now(timezone.utc).isoformat()
    if path:
        payload = json.loads(path.read_text(encoding="utf-8"))
        scraped_at = payload.get("scraped_at", scraped_at)

    text, html = build_bodies(payload, scraped_at)
    subject = f"[PM Jobs] {payload.get('count', 0)} director+ role(s) — {scraped_at[:10]}"

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_addr or user
    msg["To"] = to_addr

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text, "plain", "utf-8"))
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)

    if path:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(path.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
        msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls(context=context)
        server.login(user, password)
        server.sendmail(msg["From"], [to_addr], msg.as_string())

    print(f"Email sent to {to_addr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
