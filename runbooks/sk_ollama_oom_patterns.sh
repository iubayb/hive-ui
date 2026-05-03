#!/usr/bin/env bash
# runbook_sk_ollama_oom_patterns.sh
# Capability: sk_ollama_oom_patterns
# Problem:    Ollama returns HTTP 400 with context-overflow messages not in
#             OOM_PATTERNS → research_loop retries infinitely instead of halving ctx
# Fix:        Verify research_loop.py contains all required OOM pattern strings
# Idempotent: read-only check; only patches if missing

set -euo pipefail
RLOOP="/home/ayoub/research_loop.py"

REQUIRED_PATTERNS=(
    "input too large"
    "prompt eval requires"
    "prompt exceeds"
    "too many tokens"
    "tokens requested"
    "context length"
    "maximum context"
)

detect() {
    missing=()
    for pat in "${REQUIRED_PATTERNS[@]}"; do
        grep -q "$pat" "$RLOOP" 2>/dev/null || missing+=("$pat")
    done
    if [ ${#missing[@]} -gt 0 ]; then
        echo "DETECT: missing OOM patterns in $RLOOP: ${missing[*]}"; return 1
    fi
    echo "DETECT: OK — all OOM patterns present in research_loop.py"; return 0
}

verify() {
    detect
}

if detect; then
    echo "No action needed."
else
    echo "WARNING: OOM patterns missing. Manual edit of research_loop.py required."
    echo "Add missing strings to OOM_PATTERNS list in research_loop.py"
    exit 1
fi
