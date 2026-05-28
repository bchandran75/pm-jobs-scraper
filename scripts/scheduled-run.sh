#!/usr/bin/env bash
# Invoked by launchd every 24 hours. Logs to logs/scraper.log.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs output

if [[ -f "$PROJECT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >>"$PROJECT_DIR/logs/scraper.log"
}

log "=== PM jobs scraper started ==="

SCRAPE_OK=0
if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  if "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/run.py" -o "$PROJECT_DIR/output" >>"$PROJECT_DIR/logs/scraper.log" 2>&1; then
    log "Finished (Python)."
  else
    log "Python run finished with warnings or no matches (exit $?)."
    SCRAPE_OK=1
  fi
elif [[ -x "$PROJECT_DIR/scrape.sh" ]]; then
  if "$PROJECT_DIR/scrape.sh" >>"$PROJECT_DIR/logs/scraper.log" 2>&1; then
    log "Finished (Node)."
  else
    log "Node run finished with warnings or no matches (exit $?)."
    SCRAPE_OK=1
  fi
else
  log "ERROR: No .venv/bin/python or scrape.sh found."
  exit 1
fi

send_email() {
  local to="${EMAIL_TO:-balaji.chandran@yahoo.com}"
  if [[ -z "${SMTP_USER:-}" || -z "${SMTP_PASS:-}" ]]; then
    log "Email skipped — add SMTP_USER and SMTP_PASS to .env (see .env.example)."
    return 0
  fi

  if [[ -x "$PROJECT_DIR/scripts/send-results-email.sh" ]] && "$PROJECT_DIR/scripts/send-results-email.sh" >>"$PROJECT_DIR/logs/scraper.log" 2>&1; then
    log "Results emailed to $to (curl)."
    return 0
  fi

  NODE_BIN=node
  if ! command -v node >/dev/null 2>&1; then
    NODE_BIN="/Applications/Cursor.app/Contents/Resources/app/resources/helpers/node"
  fi

  if [[ -x "$PROJECT_DIR/.venv/bin/python" ]] && "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/send-results-email.py" >>"$PROJECT_DIR/logs/scraper.log" 2>&1; then
    log "Results emailed to $to (Python)."
    return 0
  fi

  if command -v python3 >/dev/null 2>&1 && python3 "$PROJECT_DIR/scripts/send-results-email.py" >>"$PROJECT_DIR/logs/scraper.log" 2>&1; then
    log "Results emailed to $to (Python)."
    return 0
  fi

  if "$NODE_BIN" "$PROJECT_DIR/scripts/send-results-email-smtp.mjs" >>"$PROJECT_DIR/logs/scraper.log" 2>&1; then
    log "Results emailed to $to (SMTP)."
    return 0
  fi

  if [[ -d "$PROJECT_DIR/node_modules/nodemailer" ]]; then
    if "$NODE_BIN" "$PROJECT_DIR/scripts/send-results-email.mjs" >>"$PROJECT_DIR/logs/scraper.log" 2>&1; then
      log "Results emailed to $to (nodemailer)."
      return 0
    fi
  fi

  log "Email failed — check .env credentials and logs/scraper.log."
}

send_email

log "=== PM jobs scraper done ==="
exit "$SCRAPE_OK"
