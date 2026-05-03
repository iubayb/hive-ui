#!/usr/bin/env bash
# runbook_sk_full_log.sh
# Capability: sk_full_log (Always fetch complete failure log before diagnosing)
# Problem:    Diagnosing from truncated CI logs misses the actual error line
# Fix:        Always use --retry 2 curl + filter noise for full job logs
# Usage:      sk_full_log.sh <github_run_id> <job_id>
# Idempotent: read-only

set -euo pipefail

RUN_ID="${1:-}"
JOB_ID="${2:-}"
REPO="ryzensekai/ps5_bazzite"
KEYFILE="${HOME}/.config/research-hive/env"
GH_TOKEN=$(grep "GITHUB_TOKEN\|GH_TOKEN" "$KEYFILE" 2>/dev/null | cut -d= -f2 | tr -d '"'"'" | head -1)

if [ -z "$RUN_ID" ] || [ -z "$JOB_ID" ]; then
    echo "Usage: $0 <run_id> <job_id>"
    echo "Example: $0 25277136141 <job_id>"
    echo "To list jobs: gh run view <run_id> --repo $REPO"
    exit 0
fi

if [ -z "$GH_TOKEN" ]; then
    echo "Fetching via gh CLI..."
    gh run view "$RUN_ID" --repo "$REPO" --log 2>/dev/null | \
        grep -v "^$\|^\s*$\|100%\|depmod\|\[  OK  \]" | tail -200
else
    echo "Fetching via API..."
    curl -s --retry 2 --retry-delay 3 \
        -H "Authorization: Bearer $GH_TOKEN" \
        "https://api.github.com/repos/$REPO/actions/jobs/$JOB_ID/logs" | \
        grep -v "^$\|100%\|depmod\|\[  OK  \]" | tail -200
fi
