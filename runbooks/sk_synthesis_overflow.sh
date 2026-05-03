#!/usr/bin/env bash
# runbook_sk_synthesis_overflow.sh
# Capability: sk_synthesis_overflow
# Problem:    research_loop.py reads full report file into synthesis prompt with
#             no length cap → context overflow + HTTP 400 on large reports
# Fix:        Verify synth_max_chars param exists and run_research.sh pre-trims
# Idempotent: read-only check

set -euo pipefail
RLOOP="/home/ayoub/research_loop.py"
RUNSH="/home/ayoub/.local/bin/run_research.sh"

detect() {
    ok=1
    if ! grep -q "synth_max_chars" "$RLOOP" 2>/dev/null; then
        echo "DETECT: synth_max_chars missing from research_loop.py"; ok=0
    fi
    if ! grep -q "REPORT_MAX_CHARS\|synth.max.chars\|synth_max_chars" "$RUNSH" 2>/dev/null; then
        echo "DETECT: report trim missing from run_research.sh"; ok=0
    fi
    [ "$ok" -eq 1 ] && echo "DETECT: OK — synthesis overflow protections present" && return 0
    return 1
}

if detect; then
    echo "No action needed."
else
    echo "WARNING: synthesis overflow protection missing — large reports will crash synthesis"
    exit 1
fi
