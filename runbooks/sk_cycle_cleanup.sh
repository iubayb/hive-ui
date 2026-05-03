#!/usr/bin/env bash
# runbook_sk_cycle_cleanup.sh
# Capability: sk_cycle_cleanup (Always run cycle cleanup before starting new work)
# Problem:    Stale KB entries, open blockers, and orphaned next_steps accumulate
#             across cycles — each new cycle must start clean
# Fix:        Run this at the start of each major work cycle
# Idempotent: resolves stale data, does not destroy anything

set -euo pipefail

cd /home/ayoub/hive-ui

python3 - <<'PYEOF'
import sys, json
sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status

s = hive_status.load()
resolved_b = 0
cancelled_s = 0

# Resolve stale low-severity blockers older than 24h
import datetime
now = datetime.datetime.now(datetime.timezone.utc)
for b in s.get('blockers', []):
    if b.get('status') != 'open':
        continue
    if b.get('severity') not in ('low', 'medium'):
        continue
    try:
        ts = datetime.datetime.fromisoformat(b['ts'].replace('Z', '+00:00'))
        age_h = (now - ts).total_seconds() / 3600
        if age_h > 24:
            hive_status.resolve_blocker(b['id'], 'Auto-resolved: stale >24h', updated_by='cycle-cleanup')
            resolved_b += 1
    except Exception:
        pass

# Cancel done/stale next_steps from orchestrator that are >48h old
s = hive_status.load()
for n in s.get('next_steps', []):
    if n.get('status') != 'pending':
        continue
    if n.get('source') != 'orchestrator':
        continue
    try:
        ts = datetime.datetime.fromisoformat(n['ts'].replace('Z', '+00:00'))
        age_h = (now - ts).total_seconds() / 3600
        if age_h > 48:
            hive_status.update_next_step(n['id'], 'done', updated_by='cycle-cleanup')
            cancelled_s += 1
    except Exception:
        pass

print(f'Cycle cleanup: resolved {resolved_b} stale blockers, cancelled {cancelled_s} old steps')
PYEOF
