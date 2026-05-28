#!/usr/bin/env bash
# Install macOS LaunchAgent: run PM jobs scraper every 24 hours.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.pm-jobs-scraper"
PLIST_SRC="$PROJECT_DIR/launchd/com.pm-jobs-scraper.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
RUN_SCRIPT="$PROJECT_DIR/scripts/scheduled-run.sh"

chmod +x "$RUN_SCRIPT" "$PROJECT_DIR/scrape.sh" "$PROJECT_DIR/scripts/send-results-email.mjs"

mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/output" "$HOME/Library/LaunchAgents"

if command -v npm >/dev/null 2>&1; then
  (cd "$PROJECT_DIR" && npm install --silent) || echo "Warning: npm install failed — email may not work until you run: npm install"
fi

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  echo ""
  echo "Created .env from .env.example — add your Yahoo app password before email will send."
fi

sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PLIST_SRC" >"$PLIST_DST"

# Unload if already loaded (ignore errors on first install).
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || launchctl unload "$PLIST_DST" 2>/dev/null || true

launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>/dev/null \
  || launchctl load "$PLIST_DST"

echo "Installed LaunchAgent: $PLIST_DST"
echo "  Label:        $LABEL"
echo "  Interval:     every 24 hours (86400s)"
echo "  Run at load:  yes (runs once now, then every 24h)"
echo "  Project:      $PROJECT_DIR"
echo "  Scraper log:  $PROJECT_DIR/logs/scraper.log"
echo ""
echo "Commands:"
echo "  launchctl print gui/$(id -u)/$LABEL    # status"
echo "  $PROJECT_DIR/scripts/uninstall-schedule.sh"
