#!/usr/bin/env bash
# status-push.sh — runs on Oracle ARM server every 60s via cron / systemd timer
# Pushes /tmp/hive-status.json + /home/ayoub/research/wegia-audit.md to status/ branch

set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/ayoub/hive-ui}"
STATUS_FILE="${STATUS_FILE:-/tmp/hive-status.json}"
REPORT_FILE="${REPORT_FILE:-/home/ayoub/research/wegia-audit.md}"
BRANCH="status"

cd "$REPO_DIR"

# Ensure we're on the status branch
git fetch origin "$BRANCH" --quiet 2>/dev/null || true
git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" origin/"$BRANCH"

# Copy latest files
[ -f "$STATUS_FILE" ] && cp "$STATUS_FILE" hive-status.json
[ -f "$REPORT_FILE" ] && { mkdir -p research; cp "$REPORT_FILE" research/latest.md; }

# Only commit if something changed
if git diff --quiet && git diff --cached --quiet; then
  echo "[status-push] no changes — skipping"
  git checkout develop 2>/dev/null || true
  exit 0
fi

git add hive-status.json logs.jsonl research/ 2>/dev/null || git add hive-status.json

GIT_AUTHOR_NAME=status-push \
GIT_AUTHOR_EMAIL=status@hive.local \
GIT_COMMITTER_NAME=status-push \
GIT_COMMITTER_EMAIL=status@hive.local \
git commit -m "chore: status sync $(date -u +%Y-%m-%dT%H:%M:%SZ)"

git push origin "$BRANCH"
echo "[status-push] pushed to $BRANCH OK"
git checkout develop 2>/dev/null || true
