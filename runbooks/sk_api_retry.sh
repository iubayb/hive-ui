#!/usr/bin/env bash
# runbook_sk_api_retry.sh
# Capability: sk_api_retry (Wrap all GitHub API calls in retry loops)
# Problem:    GitHub API times out intermittently — single-shot curl fails
# Fix:        Always use --retry 2 --retry-delay 3 and check HTTP status
# Idempotent: read-only function library — source this in other scripts

# ── library (source me) ───────────────────────────────────────────────────────
gh_api() {
    # Usage: gh_api <endpoint> [extra curl args...]
    local endpoint="$1"; shift
    local KEYFILE="${HOME}/.config/research-hive/env"
    local TOKEN=$(grep "GITHUB_TOKEN\|GH_TOKEN" "$KEYFILE" 2>/dev/null | cut -d= -f2 | tr -d '"'"'" | head -1)
    curl -s --retry 2 --retry-delay 3 --max-time 30 \
        -H "Authorization: Bearer $TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/$endpoint" "$@"
}

gh_api_check() {
    # Returns 0 if endpoint returns 200, 1 otherwise
    local endpoint="$1"
    local status
    status=$(gh_api "$endpoint" -o /dev/null -w "%{http_code}")
    [ "$status" = "200" ] && return 0
    echo "gh_api_check: HTTP $status for $endpoint"; return 1
}

# ── self-test ─────────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Testing GitHub API retry wrapper..."
    if gh_api_check "repos/ryzensekai/ps5_bazzite/actions/runs?per_page=1"; then
        echo "VERIFY: OK — GitHub API reachable with retry"
    else
        echo "VERIFY: GitHub API not reachable (may be rate-limited or offline)"
    fi
fi
