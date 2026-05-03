#!/usr/bin/env bash
# runbook_sk_stream_reasoning.sh
# Capability: sk_stream_reasoning
# Problem:    Reasoning models emit delta.reasoning tokens before delta.content.
#             Without handling reasoning tokens, streamed responses appear empty
# Fix:        Verify logstream.py reads both delta.content and delta.reasoning
# Idempotent: read-only check

set -euo pipefail
LS="/home/ayoub/hive-ui/logstream.py"

detect() {
    if grep -q 'delta.get.*reasoning\|\.get.*"reasoning"' "$LS" 2>/dev/null; then
        echo "DETECT: OK — delta.reasoning handled in logstream.py"; return 0
    fi
    echo "DETECT: delta.reasoning not handled in logstream.py"; return 1
}

if detect; then
    echo "No action needed."
else
    echo "WARNING: Add delta.reasoning fallback to _stream_llm() in logstream.py"
    exit 1
fi
