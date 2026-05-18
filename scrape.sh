#!/usr/bin/env bash
# Run the PM jobs scraper (Node — no Python/Xcode required).
set -euo pipefail
cd "$(dirname "$0")"

if command -v node >/dev/null 2>&1; then
  NODE=node
elif [[ -x "/Applications/Cursor.app/Contents/Resources/app/resources/helpers/node" ]]; then
  NODE="/Applications/Cursor.app/Contents/Resources/app/resources/helpers/node"
else
  echo "Node.js not found. Install Node or Xcode CLI tools for Python run.py." >&2
  exit 1
fi

exec "$NODE" run.mjs "$@"
