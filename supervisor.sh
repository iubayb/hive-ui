#!/usr/bin/env bash
# supervisor.sh — Adaptive session supervisor with exponential backoff.
#
# Behaviour:
#   • Discovers all tmux sessions via `tmux ls` each sweep — no hardcoded list.
#   • Restart commands and optional HTTP health-check URLs come from CONF
#     (reloaded every sweep — edit without restarting the supervisor).
#   • Conf format:
#       session:command
#       session:command|||http://health-check-url/
#   • Per-session exponential backoff on restarts:
#       first retry after BACKOFF_INIT s, doubles each failure, cap BACKOFF_MAX s.
#       After CONSEC_OK_RESET consecutive clean sweeps the backoff resets.
#   • Adaptive sweep interval:
#       Snaps to INTERVAL_MIN on any DEAD event; backs off toward INTERVAL_MAX
#       by INTERVAL_STEP per calm sweep — so the supervisor is aggressive when
#       things are broken and nearly silent when everything is healthy.
#
# Canonical source: /home/ayoub/hive-ui/supervisor.sh
# Run via:  systemctl --user start hive-supervisor   (authoritative)
#           tmux supervisor pane shows: tail -f /tmp/supervisor.log

set -uo pipefail

CONF="${CONF:-/home/ayoub/hive-ui/supervisor.conf}"
LOG=/tmp/supervisor.log
SELF="supervisor"   # never manage our own session

# ── backoff tunables ──────────────────────────────────────────────────────────
BACKOFF_INIT=5       # seconds before first restart attempt
BACKOFF_MAX=300      # cap at 5 minutes
BACKOFF_MULT=2       # multiplier per consecutive failure
CONSEC_OK_RESET=3    # consecutive clean sweeps to reset backoff to BACKOFF_INIT

# ── adaptive interval tunables ────────────────────────────────────────────────
INTERVAL_MIN=10      # sweep this fast when something is wrong
INTERVAL_MAX=300     # back off to this when everything is calm
INTERVAL_STEP=20     # add this many seconds per fully-clean sweep

# ── per-session state (survive across sweeps, reset on supervisor restart) ────
declare -A BACKOFF        # current backoff seconds
declare -A LAST_RESTART   # epoch of last restart attempt
declare -A RESTART_COUNT  # cumulative restart count
declare -A CONSEC_OK      # consecutive OK sweeps since last failure
declare -A HEALTHCHECK    # optional HTTP URL from conf

current_interval=$INTERVAL_MIN
had_event=0   # flag: set to 1 if any DEAD/RESTART happened this sweep

# ── helpers ───────────────────────────────────────────────────────────────────

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

load_conf() {
    unset CMD HEALTHCHECK
    declare -gA CMD
    declare -gA HEALTHCHECK
    [[ -f "$CONF" ]] || { log "WARN: $CONF not found — no restarts configured"; return; }
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ "$line" =~ ^[[:space:]]*$ ]] && continue
        [[ "$line" != *:* ]]            && continue
        local session="${line%%:*}"
        local rest="${line#*:}"
        # Split on optional ||| separator to extract health-check URL
        local cmd url=""
        if [[ "$rest" == *'|||'* ]]; then
            cmd="${rest%%'|||'*}"
            url="${rest##*'|||'}"
        else
            cmd="$rest"
        fi
        CMD["$session"]="$cmd"
        [[ -n "$url" ]] && HEALTHCHECK["$session"]="$url"
    done < "$CONF"
}

is_dead() {
    local session="$1" pane_pid
    pane_pid=$(tmux display -t "$session" -p "#{pane_pid}" 2>/dev/null) || return 1
    [[ -z "$pane_pid" ]] && return 1
    [[ $(pgrep -P "$pane_pid" 2>/dev/null | wc -l) -eq 0 ]]
}

http_check() {
    local session="$1" url="${HEALTHCHECK[$1]:-}"
    [[ -z "$url" ]] && return 0
    sleep 5
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        log "HEALTH OK  [$session] $url"
        return 0
    else
        log "HEALTH FAIL[$session] $url — doubling backoff"
        local b=${BACKOFF[$session]:-$BACKOFF_INIT}
        local nb=$(( b * BACKOFF_MULT ))
        BACKOFF[$session]=$(( nb > BACKOFF_MAX ? BACKOFF_MAX : nb ))
        return 1
    fi
}

try_restart() {
    local session="$1"
    local now; now=$(date +%s)
    local backoff=${BACKOFF[$session]:-$BACKOFF_INIT}
    local last=${LAST_RESTART[$session]:-0}
    local since=$(( now - last ))

    if (( since < backoff )); then
        local remaining=$(( backoff - since ))
        log "BACKOFF    [$session] ${remaining}s remaining (backoff=${backoff}s, restarts=${RESTART_COUNT[$session]:-0})"
        return
    fi

    local count=$(( ${RESTART_COUNT[$session]:-0} + 1 ))
    log "RESTART    [$session] attempt=$count backoff=${backoff}s → ${CMD[$session]:0:80}..."

    tmux send-keys -t "$session" "" Enter 2>/dev/null
    sleep 0.3
    tmux send-keys -t "$session" "${CMD[$session]}" Enter

    LAST_RESTART[$session]=$now
    RESTART_COUNT[$session]=$count
    CONSEC_OK[$session]=0

    # Double backoff for next failure, cap at max
    local nb=$(( backoff * BACKOFF_MULT ))
    BACKOFF[$session]=$(( nb > BACKOFF_MAX ? BACKOFF_MAX : nb ))

    had_event=1

    http_check "$session"
}

# ── main loop ─────────────────────────────────────────────────────────────────

log "=== Supervisor started (adaptive interval ${INTERVAL_MIN}–${INTERVAL_MAX}s, backoff ${BACKOFF_INIT}–${BACKOFF_MAX}s, conf: $CONF) ==="

while true; do
    load_conf
    had_event=0

    mapfile -t sessions < <(tmux ls -F "#{session_name}" 2>/dev/null || true)

    for session in "${sessions[@]}"; do
        [[ "$session" == "$SELF" ]] && continue

        if is_dead "$session"; then
            sleep 2  # brief grace — avoid false positive on slow start
            if is_dead "$session"; then
                if [[ -n "${CMD[$session]+_}" ]]; then
                    log "DEAD       [$session] — scheduling restart"
                    try_restart "$session"
                else
                    log "DEAD       [$session] — no restart command in $CONF"
                    had_event=1
                fi
            else
                log "RECOVERED  [$session] — briefly idle, no action"
            fi
        else
            local_pid=$(tmux display -t "$session" -p "#{pane_pid}" 2>/dev/null)
            n=$(pgrep -P "$local_pid" 2>/dev/null | wc -l)
            # Reset backoff after CONSEC_OK_RESET consecutive clean sweeps
            CONSEC_OK[$session]=$(( ${CONSEC_OK[$session]:-0} + 1 ))
            if (( ${CONSEC_OK[$session]} >= CONSEC_OK_RESET )); then
                if (( ${BACKOFF[$session]:-BACKOFF_INIT} > BACKOFF_INIT )); then
                    log "BACKOFF RESET [$session] — ${CONSEC_OK[$session]} clean sweeps"
                fi
                BACKOFF[$session]=$BACKOFF_INIT
                CONSEC_OK[$session]=0
            fi
            log "OK         [$session] children=$n interval=${current_interval}s backoff=${BACKOFF[$session]:-$BACKOFF_INIT}s"
        fi
    done

    # ── adaptive interval ────────────────────────────────────────────────────
    if (( had_event )); then
        current_interval=$INTERVAL_MIN
    else
        current_interval=$(( current_interval + INTERVAL_STEP ))
        (( current_interval > INTERVAL_MAX )) && current_interval=$INTERVAL_MAX
    fi

    log "--- sweep done (${#sessions[@]} sessions), next in ${current_interval}s ---"
    sleep "$current_interval"
done
