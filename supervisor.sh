#!/usr/bin/env bash
# supervisor.sh — Adaptive session supervisor + integrated watchdog.
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
#       by INTERVAL_STEP per calm sweep.
#
# Integrated watchdog (runs every sweep):
#   • WeGIA research-loop.service health check + auto-restart
#   • PS5 hive tmux session check + auto-restart
#   • Ollama API liveness + auto-restart
#   • hive-ui port 8888 + orchestrator idle detection → hive-status blocker
#   • GitHub Actions failure alert (every GH_CHECK_INTERVAL seconds)
#   • Heartbeat log (every 5 sweeps)
#
# Canonical source: /home/ayoub/hive-ui/supervisor.sh
# Run via:  systemctl --user start hive-supervisor   (authoritative)
#           supervisor tmux pane shows: tail -f /tmp/supervisor.log

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

# ── watchdog tunables ─────────────────────────────────────────────────────────
GH_CHECK_INTERVAL=300       # check GitHub Actions every 5 minutes
HIVE_IDLE_THRESHOLD=300     # orchestrator silent >5min → hive-status blocker
HEARTBEAT_EVERY=5           # print heartbeat every N sweeps
SELF_TEST_EVERY=10          # run system invariant tests every N sweeps (~25 min)

# ── watchdog paths ────────────────────────────────────────────────────────────
PS5_LOG=~/research/ps5-hive.log
TASK_INSTR=/tmp/ps5-task-instructions.txt
RESEARCH_LOOP=/home/ayoub/research_loop.py

# ── per-session state (survive across sweeps, reset on supervisor restart) ────
declare -A BACKOFF        # current backoff seconds
declare -A LAST_RESTART   # epoch of last restart attempt
declare -A RESTART_COUNT  # cumulative restart count
declare -A CONSEC_OK      # consecutive OK sweeps since last failure
declare -A HEALTHCHECK    # optional HTTP URL from conf
declare -A CMD            # restart commands from conf

current_interval=$INTERVAL_MIN
had_event=0   # flag: set to 1 if any DEAD/RESTART happened this sweep

# watchdog state
last_gh_check=0
sweep_count=0
mkdir -p ~/research

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
        # Alert when backoff is long (>=120s) — orchestrator may need to act
        if (( backoff >= 120 )); then
            python3 - <<PYEOF 2>/dev/null || true
import sys; sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status
s = hive_status.load()
already = any(
    b.get('status') == 'open'
    and 'backoff' in b.get('description','').lower()
    and '${session}' in b.get('description','')
    for b in s.get('blockers', [])
)
if not already:
    hive_status.add_blocker('desktop', 'supervisor',
        "Session '${session}' in long backoff (${backoff}s) — ${RESTART_COUNT[$session]:-0} restart(s), may need manual intervention",
        severity='high')
PYEOF
        fi
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

    local nb=$(( backoff * BACKOFF_MULT ))
    BACKOFF[$session]=$(( nb > BACKOFF_MAX ? BACKOFF_MAX : nb ))

    had_event=1
    http_check "$session"
}

# ── watchdog: WeGIA service ────────────────────────────────────────────────────
check_wegia() {
    if ! systemctl --user is-active --quiet research-loop.service; then
        log "WARN [watchdog] research-loop.service not active — restarting"
        systemctl --user restart research-loop.service && \
            log "INFO [watchdog] research-loop.service restarted" || \
            log "ERROR [watchdog] failed to restart research-loop.service"
    fi
}

# ── watchdog: restore PS5 task instructions if /tmp cleared ──────────────────
restore_task_instructions() {
    if [ ! -f "$TASK_INSTR" ]; then
        log "WARN [watchdog] $TASK_INSTR missing — recreating"
        cat > "$TASK_INSTR" << 'EOF'
You are a security researcher specializing in embedded systems, hypervisor exploitation, and game console hacking. Analyze the provided source file as part of a PS5 exploit chain research project.

Primary objective: discover a viable exploit chain to run arbitrary Linux on PS5 Slim (CFI-7000 series, Oberon Pro / "Morpheus" SoC, firmware 7.61+).

For each file, produce the following sections:

## Summary
One-paragraph description of what this file does and its role in the exploit chain or boot process.

## Exploit Primitives
List any exploit primitives present or implied: type confusion, heap overflow, use-after-free, OOB read/write, integer overflow, format string, race condition, TOCTOU, stack pivot, ROP gadgets, etc. Quote the relevant code.

## Firmware Version Constraints
Which PS5 firmware versions does this code target? Which offsets, symbols, or gadgets are hardcoded? Are there version checks or offset tables? Can they be generalized?

## PS5 Slim Portability Assessment
The PS5 Fat (CFI-1xxx) uses Oberon SoC (AMD custom). The PS5 Slim (CFI-7xxx) uses Oberon Pro / "Morpheus" — same ISA (x86-64 Jaguar-derived + security coprocessors), different firmware binary layout. Assess:
- Which parts of this code are SoC-agnostic (pure software bugs)?
- Which parts depend on Fat-specific memory maps, firmware offsets, or hardware registers?
- What would need re-derivation for Slim?

## Boot Chain Attack Surface
Does this file reveal anything about: BootROM, second-stage loader, hypervisor (HV), kernel, or userland attack surface? What trust boundaries are crossed?

## Hypervisor Bypass
Does this file implement or reference any hypervisor escape or defeat technique? Quote code. Does it work on Slim firmware?

## Key Offsets / Gadgets
List any hardcoded addresses, offsets, gadget addresses, or structure layouts. Note firmware version they apply to.

## Confidence
Rate your overall confidence that this file contributes a portable exploit primitive for PS5 Slim: HIGH / MEDIUM / LOW. One sentence justification.

## Follow-up
Up to 3 concrete follow-up research questions this file raises (one per line, starting with "- ").
EOF
    fi
}

# ── watchdog: ensure PS5 repos exist in /tmp ─────────────────────────────────
ensure_ps5_repos() {
    if [ ! -d /tmp/ps5-research/PPPwn ]; then
        log "WARN [watchdog] /tmp/ps5-research missing (likely reboot) — re-cloning"
        mkdir -p /tmp/ps5-research
        git clone --depth=1 https://github.com/TheOfficialFloW/PPPwn.git \
            /tmp/ps5-research/PPPwn 2>>"$LOG" &
        git clone --depth=1 https://github.com/ps5-linux/ps5-linux-loader.git \
            /tmp/ps5-research/ps5-linux-loader 2>>"$LOG" &
        git clone --depth=1 https://github.com/ps5-linux/ps5-linux-patches.git \
            /tmp/ps5-research/ps5-linux-patches 2>>"$LOG" &
        wait
        log "INFO [watchdog] re-clone complete: $(ls /tmp/ps5-research/)"
    fi
}

# ── watchdog: Ollama ──────────────────────────────────────────────────────────
check_ollama() {
    if ! curl -sf http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
        log "WARN [watchdog] Ollama not responding — attempting restart"
        systemctl restart ollama 2>/dev/null || true
        sleep 15  # give it time to load model
        if curl -sf http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
            log "INFO [watchdog] Ollama recovered"
            # Ensure throttle drop-in is applied
            pgrep -x ollama | xargs -r renice +15 2>/dev/null || true
        else
            log "ERROR [watchdog] Ollama still down after restart attempt"
        fi
    fi
}

# ── watchdog: hive-ui liveness + orchestrator idle detection ─────────────────
check_hive_ui() {
    local now; now=$(date +%s)

    # Port 8888 liveness
    if ! curl -sf --max-time 5 http://127.0.0.1:8888/ -o /dev/null 2>/dev/null; then
        log "WARN [watchdog] hive-ui port 8888 not responding — supervisor should restart it"
        had_event=1
    fi

    # Orchestrator freshness via hive-status mtime
    local status_file="/tmp/hive-status.json"
    if [ -f "$status_file" ]; then
        local last_mod idle_secs
        last_mod=$(stat -c %Y "$status_file" 2>/dev/null || echo 0)
        idle_secs=$(( now - last_mod ))
        if [ "$idle_secs" -gt "$HIVE_IDLE_THRESHOLD" ]; then
            log "WARN [watchdog] hive-status idle ${idle_secs}s (>${HIVE_IDLE_THRESHOLD}s) — orchestrator may be stuck"
            python3 - <<PYEOF 2>/dev/null || true
import sys; sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status
s = hive_status.load()
already = any(
    b.get('status') == 'open' and 'watchdog' in b.get('agent','') and 'idle' in b.get('description','').lower()
    for b in s.get('blockers', [])
)
if not already:
    hive_status.add_blocker('desktop', 'watchdog',
        f'Orchestrator/hive idle for ${idle_secs}s — check for stuck processes',
        severity='high')
PYEOF
        else
            # Healthy — resolve any open watchdog-idle blocker
            python3 - <<PYEOF 2>/dev/null || true
import sys; sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status
s = hive_status.load()
for b in s.get('blockers', []):
    if b.get('status') == 'open' and 'watchdog' in b.get('agent','') and 'idle' in b.get('description','').lower():
        hive_status.resolve_blocker(b['id'], 'watchdog: hive is active again')
PYEOF
        fi
    fi
}

# ── watchdog: GitHub Actions failure alert ────────────────────────────────────
check_github_actions() {
    local now; now=$(date +%s)
    if (( now - last_gh_check < GH_CHECK_INTERVAL )); then
        return
    fi
    last_gh_check=$now

    local CUTOFF FAILED
    CUTOFF=$(date -u -d '2 hours ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || \
             date -u -v-2H '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo "")
    FAILED=$(gh run list --repo iubayb/ps5_bazzite --limit 20 \
        --json conclusion,name,headBranch,databaseId,createdAt \
        --jq --arg cutoff "$CUTOFF" \
        '[.[] | select(.conclusion=="failure"
               and .headBranch=="fix/caveats-env-generic"
               and .createdAt >= $cutoff)] | length' \
        2>/dev/null || echo "0")

    if [ "$FAILED" -gt 0 ]; then
        log "ALERT [watchdog] $FAILED recent failed GitHub Actions run(s) on fix/caveats-env-generic"
    else
        log "INFO [watchdog] GitHub Actions: no recent failures on fix/caveats-env-generic"
    fi
}

# ── resource guardian — CPU / memory / disk ───────────────────────────────────
# Runs every sweep. Never lets the machine become unresponsive.
# Levels:
#   NORMAL  — load/core < 0.70,  mem_avail > 8GB,  disk < 80%
#   WARN    — load/core < 0.85,  mem_avail > 4GB,  disk < 90%
#   CRIT    — otherwise → throttle heavy jobs; raise blocker
#   KILL    — load/core >= 1.5 OR mem_avail < 2GB → SIGSTOP research_loop

_NCPU=$(nproc 2>/dev/null || echo 4)
_RG_STATE="normal"   # normal | warn | crit | kill

_rg_add_blocker() {
    local msg="$1"
    python3 - <<PYEOF 2>/dev/null || true
import sys; sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status
s = hive_status.load()
already = any(b.get('status') == 'open' and 'resource' in b.get('description','').lower()
              for b in s.get('blockers', []))
if not already:
    hive_status.add_blocker('desktop', 'resource-guardian', '$msg', severity='high')
PYEOF
}

_rg_resolve_blocker() {
    python3 - <<PYEOF 2>/dev/null || true
import sys; sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status
s = hive_status.load()
for b in s.get('blockers', []):
    if b.get('status') == 'open' and 'resource' in b.get('description','').lower():
        hive_status.resolve_blocker(b['id'], 'resource-guardian: system healthy')
PYEOF
}

_rg_apply_nice() {
    local level="$1"   # normal | crit | kill
    case "$level" in
        normal)
            pgrep -x ollama      2>/dev/null | xargs -r renice +15 2>/dev/null || true
            pgrep -f "research_loop.py" 2>/dev/null | xargs -r renice +10 2>/dev/null || true
            # Resume SIGSTOP'd processes
            pgrep -f "research_loop.py" 2>/dev/null | xargs -r kill -CONT 2>/dev/null || true
            ;;
        crit)
            pgrep -x ollama      2>/dev/null | xargs -r renice +19 2>/dev/null || true
            pgrep -f "research_loop.py" 2>/dev/null | xargs -r renice +19 2>/dev/null || true
            # Resume any SIGSTOP — just slow, not stopped
            pgrep -f "research_loop.py" 2>/dev/null | xargs -r kill -CONT 2>/dev/null || true
            ;;
        kill)
            pgrep -x ollama      2>/dev/null | xargs -r renice +19 2>/dev/null || true
            # Pause (SIGSTOP) research_loop while system is critical
            pgrep -f "research_loop.py" 2>/dev/null | xargs -r kill -STOP 2>/dev/null || true
            ;;
    esac
}

check_resource_guardian() {
    # Gather metrics
    local load1 load_per_core mem_avail_gb disk_pct
    load1=$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo 0)
    load_per_core=$(awk "BEGIN{printf \"%.2f\", $load1 / $_NCPU}")
    mem_avail_gb=$(awk '/MemAvailable/{printf "%.1f", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 99)
    disk_pct=$(df / --output=pcent 2>/dev/null | tail -1 | tr -d ' %' || echo 0)

    local new_state="normal"

    # Determine new state (worst wins)
    local is_kill is_crit is_warn
    is_kill=$(awk "BEGIN{print ($load_per_core >= 1.5 || $mem_avail_gb < 2.0) ? 1 : 0}")
    is_crit=$(awk "BEGIN{print ($load_per_core >= 0.85 || $mem_avail_gb < 4.0 || $disk_pct >= 90) ? 1 : 0}")
    is_warn=$(awk "BEGIN{print ($load_per_core >= 0.70 || $mem_avail_gb < 8.0 || $disk_pct >= 80) ? 1 : 0}")

    if   [ "$is_kill" = "1" ]; then new_state="kill"
    elif [ "$is_crit" = "1" ]; then new_state="crit"
    elif [ "$is_warn" = "1" ]; then new_state="warn"
    fi

    # Act on state transitions
    if [ "$new_state" != "$_RG_STATE" ]; then
        log "RESOURCE-GUARDIAN state: $_RG_STATE → $new_state | load/core=${load_per_core} mem_avail=${mem_avail_gb}GB disk=${disk_pct}%"
    fi

    case "$new_state" in
        kill)
            log "CRITICAL [resource-guardian] load/core=${load_per_core} mem=${mem_avail_gb}GB — PAUSING heavy jobs (SIGSTOP)"
            _rg_apply_nice kill
            _rg_add_blocker "CRITICAL: load/core=${load_per_core} mem=${mem_avail_gb}GB disk=${disk_pct}% — research_loop PAUSED"
            had_event=1
            ;;
        crit)
            _rg_apply_nice crit
            if [ "$_RG_STATE" = "normal" ] || [ "$_RG_STATE" = "warn" ]; then
                log "WARN [resource-guardian] load/core=${load_per_core} mem=${mem_avail_gb}GB disk=${disk_pct}% — throttling"
                _rg_add_blocker "HIGH load/core=${load_per_core} mem=${mem_avail_gb}GB disk=${disk_pct}% — jobs reniced"
                had_event=1
            fi
            ;;
        warn)
            # Only restore if we were worse
            if [ "$_RG_STATE" = "kill" ] || [ "$_RG_STATE" = "crit" ]; then
                log "INFO [resource-guardian] load/core=${load_per_core} mem=${mem_avail_gb}GB — recovering, restoring priorities"
                _rg_apply_nice normal
                _rg_resolve_blocker
            fi
            ;;
        normal)
            if [ "$_RG_STATE" != "normal" ]; then
                log "INFO [resource-guardian] system healthy (load/core=${load_per_core} mem=${mem_avail_gb}GB disk=${disk_pct}%) — restoring"
                _rg_apply_nice normal
                _rg_resolve_blocker
            fi
            ;;
    esac

    _RG_STATE="$new_state"
}


watchdog_heartbeat() {
    local WEGIA_STATUS PS5_DONE PS5_PENDING PS5_RUNNING
    WEGIA_STATUS=$(systemctl --user is-active research-loop.service 2>/dev/null || echo "unknown")
    PS5_DONE=$(sqlite3 ~/research/ps5-queue.db \
        "SELECT COUNT(*) FROM tasks WHERE status='done';" 2>/dev/null || echo "?")
    PS5_PENDING=$(sqlite3 ~/research/ps5-queue.db \
        "SELECT COUNT(*) FROM tasks WHERE status='pending';" 2>/dev/null || echo "?")
    PS5_RUNNING=$(sqlite3 ~/research/ps5-queue.db \
        "SELECT COUNT(*) FROM tasks WHERE status='running';" 2>/dev/null || echo "?")
    log "HEARTBEAT | WeGIA=$WEGIA_STATUS | PS5: done=$PS5_DONE pending=$PS5_PENDING running=$PS5_RUNNING"
}

run_self_test() {
    local script="/home/ayoub/hive-ui/tests/test_system.sh"
    [[ -f "$script" ]] || { log "SELF-TEST: test_system.sh not found — skipping"; return; }
    log "SELF-TEST: running system invariants..."
    local result
    result=$(timeout 60 bash "$script" 2>&1 || true)
    local failed_count
    failed_count=$(echo "$result" | grep -c "^FAIL:" || true)
    if [[ "$failed_count" -gt 0 ]]; then
        log "SELF-TEST: $failed_count invariant(s) FAILED"
        echo "$result" | grep "^FAIL:" | while IFS= read -r line; do
            log "  $line"
            # Raise hive-status blocker for each failure
            python3 - <<PYEOF 2>/dev/null || true
import sys, re
sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status
line = """$line"""
hive_status.add_blocker('default', 'supervisor', 'self-test: ' + line.strip(), severity='high')
PYEOF
        done
        # Attempt auto-fixes via the orchestrator's registry (fire-and-forget)
        echo "$result" | grep "^FIX_CMD_" | while IFS= read -r fixline; do
            local fix_cmd="${fixline#FIX_CMD_*: }"
            log "SELF-TEST: applying fix: ${fix_cmd:0:80}"
            eval "$fix_cmd" 2>/dev/null || true
        done
    else
        log "SELF-TEST: all system invariants PASS"
        # Resolve any open self-test blockers
        python3 - <<PYEOF 2>/dev/null || true
import sys
sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status
s = hive_status.load()
for b in s.get('blockers', []):
    if b.get('status') == 'open' and 'self-test' in b.get('description', '').lower():
        hive_status.resolve_blocker(b['id'], 'supervisor self-test: all invariants passing')
PYEOF
    fi
}

# ── main loop ─────────────────────────────────────────────────────────────────

log "=== Supervisor+Watchdog started (adaptive interval ${INTERVAL_MIN}–${INTERVAL_MAX}s, backoff ${BACKOFF_INIT}–${BACKOFF_MAX}s, conf: $CONF) ==="

# ── startup: protect critical processes from OOM + enforce initial nice levels ─
_apply_oom_scores() {
    # Protect: logstream (hive UI), orchestrator, supervisor itself
    for proc in "logstream.py" "orchestrator.py"; do
        pgrep -f "$proc" 2>/dev/null | while read -r pid; do
            echo -500 > /proc/$pid/oom_score_adj 2>/dev/null || true
        done
    done
    echo -500 > /proc/$$/oom_score_adj 2>/dev/null || true

    # Deprioritize: Ollama (heavy inference), research_loop (background batch)
    pgrep -x ollama 2>/dev/null | while read -r pid; do
        echo 500 > /proc/$pid/oom_score_adj 2>/dev/null || true
    done
    pgrep -f "research_loop.py" 2>/dev/null | while read -r pid; do
        echo 400 > /proc/$pid/oom_score_adj 2>/dev/null || true
    done

    # Enforce nice levels
    pgrep -x ollama      2>/dev/null | xargs -r renice +15 2>/dev/null || true
    pgrep -f "research_loop.py" 2>/dev/null | xargs -r renice +10 2>/dev/null || true
}
_apply_oom_scores
log "INFO startup: OOM scores and nice levels applied"

while true; do
    load_conf
    had_event=0
    sweep_count=$(( sweep_count + 1 ))

    # ── session process supervision ──────────────────────────────────────────
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
            CONSEC_OK[$session]=$(( ${CONSEC_OK[$session]:-0} + 1 ))
            if (( ${CONSEC_OK[$session]} >= CONSEC_OK_RESET )); then
                if (( ${BACKOFF[$session]:-BACKOFF_INIT} > BACKOFF_INIT )); then
                    log "BACKOFF RESET [$session] — ${CONSEC_OK[$session]} clean sweeps"
                    # Resolve any open backoff blocker for this session
                    python3 - <<PYEOF 2>/dev/null || true
import sys; sys.path.insert(0, '/home/ayoub/hive-ui')
import hive_status
s = hive_status.load()
for b in s.get('blockers', []):
    if (b.get('status') == 'open'
            and 'backoff' in b.get('description','').lower()
            and '${session}' in b.get('description','')):
        hive_status.resolve_blocker(b['id'], 'supervisor: session recovered cleanly')
PYEOF
                fi
                BACKOFF[$session]=$BACKOFF_INIT
                CONSEC_OK[$session]=0
            fi
            log "OK         [$session] children=$n interval=${current_interval}s backoff=${BACKOFF[$session]:-$BACKOFF_INIT}s"
        fi
    done

    # ── integrated watchdog checks ───────────────────────────────────────────
    check_resource_guardian   # first — throttle before any other action
    check_ollama
    check_wegia
    check_hive_ui
    check_github_actions
    restore_task_instructions

    # Heartbeat every N sweeps
    if (( sweep_count % HEARTBEAT_EVERY == 0 )); then
        watchdog_heartbeat
    fi

    # Self-test every N sweeps
    if (( sweep_count % SELF_TEST_EVERY == 0 )); then
        run_self_test &   # run in background — non-blocking
    fi

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
