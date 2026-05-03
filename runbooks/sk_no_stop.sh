#!/usr/bin/env bash
# runbook_sk_no_stop.sh
# Capability: sk_no_stop (Never stop to ask — apply sk_no_stop always)
# Problem:    Agent pauses for clarification mid-task when it could make a
#             reasonable assumption and proceed, increasing time-to-resolution
# Principle:  Every human correction → permanent skill in capabilities.learned
#             Apply always, verify by checking that capabilities.learned grows
# Idempotent: read-only check

set -euo pipefail

detect() {
    count=$(python3 -c "
import sys, json
sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status
s = hive_status.load()
print(len(s.get('capabilities', {}).get('learned', [])))
" 2>/dev/null)
    if [ "${count:-0}" -ge 8 ]; then
        echo "DETECT: OK — $count learned capabilities in hive-status"; return 0
    fi
    echo "DETECT: Only $count capabilities — hive may not be learning from corrections"; return 1
}

detect || exit 1
echo "Knowledge base healthy."
