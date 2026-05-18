#!/usr/bin/env bash
# Send latest scrape results via Yahoo SMTP (uses curl — no npm/python).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/output"
DEFAULT_TO="balaji.chandran@yahoo.com"

if [[ -f "$PROJECT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

: "${SMTP_USER:?SMTP_USER not set in .env}"
: "${SMTP_PASS:?SMTP_PASS not set in .env}"
SMTP_HOST="${SMTP_HOST:-smtp.mail.yahoo.com}"
SMTP_PORT="${SMTP_PORT:-587}"
EMAIL_FROM="${EMAIL_FROM:-$SMTP_USER}"
EMAIL_TO="${EMAIL_TO:-$DEFAULT_TO}"

latest="$(ls -t "$OUTPUT_DIR"/pm_jobs_*.json 2>/dev/null | head -1 || true)"
if [[ -z "$latest" ]]; then
  echo "No results file in output/"
  exit 1
fi

NODE=node
if ! command -v node >/dev/null 2>&1; then
  NODE="/Applications/Cursor.app/Contents/Resources/app/resources/helpers/node"
fi

read -r count scraped_at body_text < <("$NODE" - "$latest" <<'NODE'
const fs = require("fs");
const p = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const jobs = p.jobs || [];
const count = p.count ?? jobs.length;
const scraped = p.scraped_at || new Date().toISOString();
let text = "";
if (!jobs.length) text = "No matching roles in this run.\n";
else {
  for (const j of jobs) {
    text += `${j.company} | ${(j.region || "").toUpperCase()}\n  ${j.title}\n  ${j.location}\n  ${j.url}\n\n`;
  }
}
process.stdout.write(`${count}\t${scraped}\t${text.replace(/\t/g, " ")}`);
NODE
)

subject="[PM Jobs] ${count} director+ role(s) — $(date -u '+%Y-%m-%d')"

tmp="$(mktemp)"
{
  echo "From: ${EMAIL_FROM}"
  echo "To: ${EMAIL_TO}"
  echo "Subject: ${subject}"
  echo "MIME-Version: 1.0"
  echo "Content-Type: multipart/mixed; boundary=pmjobsboundary"
  echo ""
  echo "--pmjobsboundary"
  echo "Content-Type: text/plain; charset=utf-8"
  echo ""
  echo "PM Jobs Scraper — ${scraped_at}"
  echo "Director+ Product Management · India / TX / CA"
  echo ""
  printf '%s' "$body_text"
  echo ""
  echo "JSON results attached."
  echo "--pmjobsboundary"
  echo "Content-Type: application/json"
  echo "Content-Disposition: attachment; filename=$(basename "$latest")"
  echo ""
  cat "$latest"
  echo "--pmjobsboundary--"
} >"$tmp"

if ! curl --version >/dev/null 2>&1; then
  echo "curl required for SMTP"
  rm -f "$tmp"
  exit 1
fi

curl --silent --show-error \
  --url "smtp://${SMTP_HOST}:${SMTP_PORT}" \
  --ssl-reqd \
  --mail-from "$EMAIL_FROM" \
  --mail-rcpt "$EMAIL_TO" \
  --user "${SMTP_USER}:${SMTP_PASS}" \
  --upload-file "$tmp"

rm -f "$tmp"
echo "Email sent to ${EMAIL_TO}"
