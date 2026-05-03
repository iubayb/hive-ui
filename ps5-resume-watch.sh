#!/usr/bin/env bash
# ps5-resume-watch.sh — waits for WeGIA synthesis to complete, then re-enables
# and starts the PS5 hive. Safe to run as a background daemon.
#
# Triggered by: nohup /home/ayoub/hive-ui/ps5-resume-watch.sh &

LOG=/home/ayoub/research/logs/research-loop.log
CONF=/home/ayoub/hive-ui/supervisor.conf
PS5_CMD="python3 /home/ayoub/research_loop.py \
  --mission 'PS5 Slim exploit chain research' \
  --target-dir /tmp/ps5-research \
  --report /home/ayoub/research/ps5-exploit.md \
  --db /home/ayoub/research/ps5-queue.db \
  --audit /home/ayoub/research/ps5-audit.jsonl \
  --task-instructions /home/ayoub/hive-ui/ps5-task-instructions.txt \
  --local-worker-model qwen3.6-abliterated-q3km \
  --worker-count 1 --max-hours 0 --max-tasks 0 \
  --batch-bytes 20000 --max-tokens 1024 \
  --num-ctx 16384 --synth-num-ctx 131072 \
  --log-level INFO 2>&1 | tee /home/ayoub/research/ps5-hive.log"

echo "[ps5-watch] Started. Waiting for WeGIA 'mission complete' in $LOG" >&2

# Record how many lines are currently in the log so we only watch NEW entries
BASELINE=$(wc -l < "$LOG" 2>/dev/null || echo 0)

while true; do
    if tail -n "+$((BASELINE+1))" "$LOG" 2>/dev/null | grep -q "mission complete"; then
        echo "[ps5-watch] WeGIA mission complete detected. Waiting 30s for cleanup..." >&2
        sleep 30

        # Re-enable PS5 in supervisor.conf by uncommenting the ps5-hive line
        sed -i 's/^#ps5-hive:/ps5-hive:/' "$CONF"
        echo "[ps5-watch] Uncommented ps5-hive in $CONF" >&2

        # Start ps5-hive tmux session
        if ! tmux has-session -t ps5-hive 2>/dev/null; then
            tmux new-session -d -s ps5-hive "eval $PS5_CMD"
            echo "[ps5-watch] ps5-hive tmux session started." >&2
        else
            echo "[ps5-watch] ps5-hive session already running." >&2
        fi

        echo "[ps5-watch] Done. Exiting." >&2
        exit 0
    fi
    sleep 60
done
