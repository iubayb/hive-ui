#!/usr/bin/env bash
# runbook_sk_tmux_capture_wrap.sh
# Capability: sk_tmux_capture_wrap
# Problem:    tmux capture-pane without -J wraps long lines at pane terminal
#             width, splitting logical log lines into fragments
# Fix:        Verify logstream.py uses -J flag in capture-pane calls
# Idempotent: read-only check

set -euo pipefail
LS="/home/ayoub/hive-ui/logstream.py"
LS_LIVE="/tmp/logstream.py"

detect() {
    ok=1
    for f in "$LS" "$LS_LIVE"; do
        [ -f "$f" ] || continue
        if ! grep -q "capture-pane.*-J\|-J.*capture-pane" "$f" 2>/dev/null; then
            echo "DETECT: -J flag missing from tmux capture-pane in $f"; ok=0
        fi
    done
    [ "$ok" -eq 1 ] && echo "DETECT: OK — -J flag present in capture-pane calls" && return 0
    return 1
}

if detect; then
    echo "No action needed."
else
    echo "WARNING: tmux capture-pane calls in logstream.py missing -J flag"
    echo "Add -J to all 'tmux capture-pane' calls to join wrapped lines"
    exit 1
fi
