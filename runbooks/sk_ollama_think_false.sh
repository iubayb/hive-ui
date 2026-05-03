#!/usr/bin/env bash
# runbook_sk_ollama_think_false.sh
# Capability: sk_ollama_think_false
# Problem:    On Ollama <=0.21, options.think=False triggers model reload when
#             reasoning_effort != "none" → HTTP 400 for ~60s on ALL requests
# Fix:        Verify research_loop.py gates think:False behind reasoning_effort=="none"
# Idempotent: read-only check

set -euo pipefail
RLOOP="/home/ayoub/research_loop.py"

detect() {
    # The guard pattern: think=False only when reasoning_effort == "none"
    if grep -q 'options\["think"\] = False' "$RLOOP" 2>/dev/null; then
        # Check it's guarded
        if grep -B3 'options\["think"\] = False' "$RLOOP" | grep -q 'reasoning_effort.*none\|none.*reasoning_effort'; then
            echo "DETECT: OK — think=False is properly gated behind reasoning_effort==none"
            return 0
        else
            echo "DETECT: WARNING — think=False may not be gated"; return 1
        fi
    fi
    echo "DETECT: OK — think=False not present (no issue)"; return 0
}

if detect; then
    echo "No action needed."
else
    echo "WARNING: research_loop.py think=False guard may be missing."
    echo "Verify: options['think'] = False is only set when reasoning_effort == 'none'"
    exit 1
fi
