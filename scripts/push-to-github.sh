#!/usr/bin/env bash
# Push pm-jobs-scraper to github.com/bchandran75 (no system git required).
set -euo pipefail

OWNER="bchandran75"
REPO="pm-jobs-scraper"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$PROJECT_DIR/.tools"
install_gh() {
  mkdir -p "$TOOLS_DIR"
  for candidate in "$TOOLS_DIR/gh-bin/gh" "$TOOLS_DIR/gh/gh" "$TOOLS_DIR/gh/bin/gh"; do
    if [[ -x "$candidate" ]]; then
      GH_BIN="$candidate"
      return 0
    fi
  done
  local arch zip dir
  arch="$(uname -m)"
  if [[ "$arch" == "arm64" ]]; then
    zip="gh_2.69.0_macOS_arm64.zip"
  else
    zip="gh_2.69.0_macOS_amd64.zip"
  fi
  echo "Downloading GitHub CLI…"
  curl -fsSL -o "$TOOLS_DIR/gh.zip" "https://github.com/cli/cli/releases/download/v2.69.0/${zip}"
  unzip -qo "$TOOLS_DIR/gh.zip" -d "$TOOLS_DIR"
  dir="$(find "$TOOLS_DIR" -maxdepth 1 -type d -name 'gh_*' | head -1)"
  GH_BIN="$TOOLS_DIR/gh-bin/gh"
  rm -rf "$TOOLS_DIR/gh-bin"
  mkdir -p "$TOOLS_DIR/gh-bin"
  mv "${dir}/bin/gh" "$GH_BIN"
  chmod +x "$GH_BIN"
  rm -rf "$dir" "$TOOLS_DIR/gh.zip"
}

load_token() {
  if [[ -f "$PROJECT_DIR/.env" ]]; then
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
  fi
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    export GH_TOKEN="$GITHUB_TOKEN"
  fi
}

ensure_auth() {
  if "$GH_BIN" auth status >/dev/null 2>&1; then
    return 0
  fi
  if [[ -z "${GH_TOKEN:-}" ]]; then
    echo "ERROR: Not logged in. Either:" >&2
    echo "  1. Add GITHUB_TOKEN=ghp_... to .env (repo scope), or" >&2
    echo "  2. Run: ./.tools/gh/gh auth login --hostname github.com --device" >&2
    exit 1
  fi
}

create_repo() {
  if "$GH_BIN" repo view "${OWNER}/${REPO}" >/dev/null 2>&1; then
    echo "Repository ${OWNER}/${REPO} already exists."
    return 0
  fi
  "$GH_BIN" repo create "${OWNER}/${REPO}" --public \
    --description "PM jobs scraper — director+ roles at AI/tech companies (IN, TX, CA)"
  echo "Created https://github.com/${OWNER}/${REPO}"
}

should_skip() {
  local rel="$1"
  case "$rel" in
    .env|.env.*) return 0 ;;
    .git/*|.tools/*|output/*|logs/*|node_modules/*|.venv/*|__pycache__/*) return 0 ;;
    *.pyc) return 0 ;;
  esac
  return 1
}

upload_file() {
  local rel="$1"
  local file="$PROJECT_DIR/$rel"
  local sha="" b64

  b64="$(base64 <"$file" | tr -d '\n')"
  sha="$("$GH_BIN" api "repos/${OWNER}/${REPO}/contents/${rel}" --jq .sha 2>/dev/null || true)"

  if [[ -n "$sha" ]]; then
    "$GH_BIN" api "repos/${OWNER}/${REPO}/contents/${rel}" -X PUT \
      -f message="Update ${rel}" \
      -f content="$b64" \
      -f sha="$sha" >/dev/null
  else
    "$GH_BIN" api "repos/${OWNER}/${REPO}/contents/${rel}" -X PUT \
      -f message="Add ${rel}" \
      -f content="$b64" >/dev/null
  fi
}

upload_files() {
  local count=0 rel
  while IFS= read -r -d '' file; do
    rel="${file#"$PROJECT_DIR"/}"
    should_skip "$rel" && continue
    echo "  ↑ $rel"
    upload_file "$rel"
    count=$((count + 1))
  done < <(find "$PROJECT_DIR" -type f \
    ! -path '*/.git/*' \
    ! -path '*/.tools/*' \
    ! -path '*/output/*' \
    ! -path '*/logs/*' \
    ! -path '*/node_modules/*' \
    ! -path '*/.venv/*' \
    ! -path '*/__pycache__/*' \
    -print0)
  echo "Uploaded ${count} file(s)."
}

cd "$PROJECT_DIR"
install_gh
load_token
ensure_auth

login_user="$("$GH_BIN" api user --jq .login 2>/dev/null || true)"
echo "Authenticated as: ${login_user:-unknown}"
if [[ -n "$login_user" && "$login_user" != "$OWNER" ]]; then
  echo "Warning: expected GitHub user ${OWNER}, got ${login_user}."
fi

create_repo
echo "Uploading to ${OWNER}/${REPO}…"
upload_files
echo ""
echo "Done: https://github.com/${OWNER}/${REPO}"
