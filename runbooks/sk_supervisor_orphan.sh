#!/usr/bin/env bash
# runbook_sk_supervisor_orphan.sh
# Capability: sk_supervisor_orphan
# Problem:    If logstream.py (port 8889) was started outside supervisor
#             (nohup/manual), it becomes PPID=1. supervisor.sh then can't
#             kill it on restart → EADDRINUSE loop.
# Fix:        pkill the orphaned instance before supervisor relaunches
# Idempotent: safe to run multiple times

set -euo pipefail

PORT="${1:-8889}"

detect() {
    orphans=$(pgrep -f "PORT=$PORT python3.*logstream.py" 2>/dev/null | while read pid; do
        ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        [ "$ppid" = "1" ] && echo "$pid"
    done)
    if [ -n "$orphans" ]; then
        echo "DETECT: orphaned logstream.py PIDs (PPID=1): $orphans"; return 1
    fi
    echo "DETECT: OK — no orphaned logstream.py on port $PORT"; return 0
}

apply() {
    pkill -f "PORT=$PORT python3.*logstream.py" 2>/dev/null || true
    sleep 1
}

verify() {
    remaining=$(pgrep -f "PORT=$PORT python3.*logstream.py" 2>/dev/null | while read pid; do
        ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        [ "$ppid" = "1" ] && echo "$pid"
    done)
    [ -z "$remaining" ] && echo "VERIFY: OK — no orphaned logstream.py" && return 0
    echo "VERIFY FAILED — orphan still running: $remaining"; return 1
}

if detect; then
    echo "No action needed."
else
    echo "Applying fix..."
    apply
    verify || { echo "VERIFY FAILED"; exit 1; }
fi
