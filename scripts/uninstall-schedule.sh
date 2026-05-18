#!/usr/bin/env bash
set -euo pipefail

LABEL="com.pm-jobs-scraper"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null \
  || launchctl unload "$PLIST_DST" 2>/dev/null \
  || true

if [[ -f "$PLIST_DST" ]]; then
  rm "$PLIST_DST"
  echo "Removed $PLIST_DST"
else
  echo "Plist not found (already removed)."
fi

echo "Schedule uninstalled."
