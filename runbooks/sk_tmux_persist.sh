#!/usr/bin/env bash
# runbook_sk_tmux_persist.sh
# Capability: sk_tmux_persist (Run all long-running work inside persistent tmux sessions)
# Problem:    Long-running loops started outside tmux die when terminal closes
# Fix:        Ensure all critical sessions exist and are alive
# Idempotent: creates missing sessions, does not affect running ones

set -euo pipefail

CRITICAL_SESSIONS=("build_monitor" "hive-dev" "hive-watch" "orchestrator" "ps5-hive" "supervisor" "watchdog")

detect() {
    existing=$(tmux list-sessions -F "#{session_name}" 2>/dev/null || true)
    missing=()
    for sess in "${CRITICAL_SESSIONS[@]}"; do
        echo "$existing" | grep -qx "$sess" || missing+=("$sess")
    done
    if [ ${#missing[@]} -gt 0 ]; then
        echo "DETECT: missing tmux sessions: ${missing[*]}"; return 1
    fi
    echo "DETECT: OK — all ${#CRITICAL_SESSIONS[@]} critical sessions exist"; return 0
}

apply() {
    for sess in "${CRITICAL_SESSIONS[@]}"; do
        if ! tmux has-session -t "$sess" 2>/dev/null; then
            tmux new-session -d -s "$sess"
            echo "  Created session: $sess (supervisor will populate)"
        fi
    done
}

verify() {
    existing=$(tmux list-sessions -F "#{session_name}" 2>/dev/null || true)
    for sess in "${CRITICAL_SESSIONS[@]}"; do
        echo "$existing" | grep -qx "$sess" || { echo "VERIFY FAILED: $sess missing"; return 1; }
    done
    echo "VERIFY: OK — all sessions present"
}

if detect; then
    echo "No action needed."
else
    echo "Applying fix..."
    apply
    verify || exit 1
fi
