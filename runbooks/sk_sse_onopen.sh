#!/usr/bin/env bash
# runbook_sk_sse_onopen.sh
# Capability: sk_sse_onopen
# Problem:    Browser EventSource auto-reconnects but without onopen handler
#             the UI stays in a dead/stale state after a disconnect
# Fix:        Verify onopen handler exists in ui_shared.py
# Idempotent: read-only check

set -euo pipefail
UI="/home/ayoub/hive-ui/ui_shared.py"

detect() {
    if grep -q "logEs.onopen\|\.onopen" "$UI" 2>/dev/null; then
        echo "DETECT: OK — SSE onopen handler present in ui_shared.py"; return 0
    fi
    echo "DETECT: SSE onopen handler missing from ui_shared.py"; return 1
}

if detect; then
    echo "No action needed."
else
    echo "WARNING: Add logEs.onopen handler to ui_shared.py to clear dead SSE state"
    exit 1
fi
