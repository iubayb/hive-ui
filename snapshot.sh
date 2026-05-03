#!/usr/bin/env bash
# snapshot.sh — Persist current hive state to /home/ayoub/hive-snapshots/
# Idempotent. Safe to run any time. Keeps last 48 hourly snapshots.
# Called by cron every hour and by orchestrator on demand.

set -euo pipefail

SNAP_ROOT="/home/ayoub/hive-snapshots"
TS=$(date -u +"%Y%m%dT%H%M%SZ")
DEST="$SNAP_ROOT/$TS"
mkdir -p "$DEST"

# ── 1. hive-status JSON (full state) ──────────────────────────────────────────
cp /tmp/hive-status.json "$DEST/hive-status.json" 2>/dev/null || true

# ── 2. arena + benchmark results ──────────────────────────────────────────────
cp /tmp/hive-model-champion.json  "$DEST/" 2>/dev/null || true
cp /tmp/hive-model-benchmark.json "$DEST/" 2>/dev/null || true
cp /tmp/hive-model-registry.json  "$DEST/" 2>/dev/null || true

# ── 3. critical config files ───────────────────────────────────────────────────
mkdir -p "$DEST/conf"
cp /home/ayoub/hive-ui/supervisor.conf      "$DEST/conf/" 2>/dev/null || true
cp /home/ayoub/hive-ui/orchestrator.py      "$DEST/conf/" 2>/dev/null || true
cp /etc/avahi/avahi-daemon.conf             "$DEST/conf/" 2>/dev/null || true
cp ~/.config/research-hive/env             "$DEST/conf/env.redacted" 2>/dev/null || \
    echo "(env not readable)" > "$DEST/conf/env.redacted" || true
# Redact API key from copy
sed -i 's/\(OPENROUTER_API_KEY=\).*/\1<REDACTED>/' "$DEST/conf/env.redacted" 2>/dev/null || true

# ── 4. tmux session tail (last 50 lines each) ─────────────────────────────────
mkdir -p "$DEST/sessions"
for sess in build_monitor hive-dev hive-watch orchestrator ps5-hive watchdog; do
    tmux capture-pane -t "$sess" -p -S -50 2>/dev/null \
        > "$DEST/sessions/${sess}.log" || true
done

# ── 5. research artifacts (sizes only — don't copy multi-MB files) ────────────
{
    echo "=== Research artifacts ==="
    ls -lh /home/ayoub/research/ 2>/dev/null || echo "(no research dir)"
    echo ""
    echo "=== WeGIA audit lines ==="
    wc -l /home/ayoub/research/wegia-audit.md 2>/dev/null || echo "0"
    echo ""
    echo "=== PS5 exploit lines ==="
    wc -l /home/ayoub/research/ps5-exploit.md 2>/dev/null || echo "0"
} > "$DEST/research-sizes.txt"

# ── 6. systemd service states ─────────────────────────────────────────────────
{
    systemctl --user is-active research-loop.service 2>/dev/null || echo "unknown"
    systemctl is-active ssh 2>/dev/null || echo "unknown"
    systemctl is-active avahi-daemon 2>/dev/null || echo "unknown"
} > "$DEST/service-states.txt"

# ── 7. Prune: keep last 48 snapshots ──────────────────────────────────────────
ls -1d "$SNAP_ROOT"/[0-9]* 2>/dev/null | sort | head -n -48 | xargs -r rm -rf

echo "[snapshot] saved to $DEST"
