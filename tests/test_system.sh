#!/usr/bin/env bash
# tests/test_system.sh — System invariant tests (TS1–TS21)
#
# Usage:
#   bash tests/test_system.sh          # run all tests
#   bash tests/test_system.sh --fix TS3  # apply fix for a specific failed test
#   bash tests/test_system.sh --fix-all  # auto-apply all fixes for failed tests
#
# Output format (one line per test):
#   PASS: TS1 description
#   FAIL: TS1 description — reason
#   FIX_CMD_TS1: <shell command to fix>    # emitted after each FAIL line
#
# Exit code: 0 if all pass, 1 if any fail.

set -euo pipefail

HIVE_DIR="/home/ayoub/hive-ui"
HIVE_USER="ayoub"

pass=0
fail=0
declare -a failed_ids=()

_pass() { echo "PASS: $1 $2"; (( pass++ )) || true; }
_fail() {
    local id="$1" desc="$2" reason="$3" fix="${4:-}"
    echo "FAIL: $id $desc — $reason"
    [[ -n "$fix" ]] && echo "FIX_CMD_${id}: $fix"
    (( fail++ )) || true
    failed_ids+=("$id")
}

# ── TS1: Ollama service drop-in directory exists ───────────────────────────
id=TS1
desc="Ollama systemd drop-in directory exists"
fix="sudo mkdir -p /etc/systemd/system/ollama.service.d"
if [[ -d /etc/systemd/system/ollama.service.d ]]; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "dir /etc/systemd/system/ollama.service.d missing" "$fix"
fi

# ── TS2: throttle.conf exists ─────────────────────────────────────────────
id=TS2
desc="Ollama throttle.conf drop-in exists"
THROTTLE_CONF=/etc/systemd/system/ollama.service.d/throttle.conf
fix="sudo bash -c 'mkdir -p /etc/systemd/system/ollama.service.d && cat > $THROTTLE_CONF <<EOF
[Service]
CPUQuota=1000%
Nice=15
IOWeight=50
Environment=OLLAMA_NUM_THREAD=10
Environment=OLLAMA_MAX_LOADED_MODELS=1
EOF
systemctl daemon-reload && systemctl restart ollama'"
if [[ -f "$THROTTLE_CONF" ]]; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "$THROTTLE_CONF not found" "$fix"
fi

# ── TS3: CPUQuota=1000% in throttle.conf ──────────────────────────────────
id=TS3
desc="Ollama CPUQuota=1000% present in throttle.conf"
fix="sudo sed -i 's/^CPUQuota=.*/CPUQuota=1000%/' $THROTTLE_CONF || sudo bash -c 'echo CPUQuota=1000% >> $THROTTLE_CONF'; sudo systemctl daemon-reload && sudo systemctl restart ollama"
if [[ -f "$THROTTLE_CONF" ]] && grep -q "CPUQuota=1000%" "$THROTTLE_CONF"; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "CPUQuota=1000% not found in $THROTTLE_CONF" "$fix"
fi

# ── TS4: systemd loaded the CPUQuota (CPUQuotaPerSecUSec present) ──────────
id=TS4
desc="systemd loaded Ollama CPUQuota (CPUQuotaPerSecUSec set)"
fix="sudo systemctl daemon-reload && sudo systemctl restart ollama"
if systemctl show ollama --property=CPUQuotaPerSecUSec 2>/dev/null | grep -q "=10s\|=[0-9]"; then
    _pass "$id" "$desc"
else
    # Fallback: check if unit is loaded at all with any non-infinity value
    val=$(systemctl show ollama --property=CPUQuotaPerSecUSec 2>/dev/null | cut -d= -f2 || echo "")
    if [[ "$val" == "infinity" || -z "$val" ]]; then
        _fail "$id" "$desc" "CPUQuotaPerSecUSec=$val (not throttled)" "$fix"
    else
        _pass "$id" "$desc"
    fi
fi

# ── TS5: Ollama process running at Nice >= 10 ──────────────────────────────
id=TS5
desc="Ollama process Nice >= 10"
fix="pgrep -x ollama | head -1 | xargs -r renice +15 -p"
ollama_pid=$(pgrep -x ollama 2>/dev/null | head -1 || true)
if [[ -n "$ollama_pid" ]]; then
    # Field 19 in /proc/pid/stat is the nice value
    nice_val=$(awk '{print $19}' /proc/"$ollama_pid"/stat 2>/dev/null || \
               ps -o nice= -p "$ollama_pid" 2>/dev/null | tr -d ' ' || echo "0")
    # ps nice is raw (-20..19); we want >= 10
    if [[ "$nice_val" -ge 10 ]] 2>/dev/null; then
        _pass "$id" "$desc (nice=$nice_val)"
    else
        _fail "$id" "$desc" "Ollama nice=$nice_val (want >=10)" "$fix"
    fi
else
    _fail "$id" "$desc" "ollama process not running (skipping nice check)" "sudo systemctl start ollama"
fi

# ── TS6: sleep.target masked ──────────────────────────────────────────────
id=TS6
desc="sleep.target is masked"
fix="sudo systemctl mask sleep.target"
if [[ "$(readlink /etc/systemd/system/sleep.target 2>/dev/null)" == "/dev/null" ]]; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "sleep.target is NOT masked" "$fix"
fi

# ── TS7: suspend.target masked ────────────────────────────────────────────
id=TS7
desc="suspend.target is masked"
fix="sudo systemctl mask suspend.target"
if [[ "$(readlink /etc/systemd/system/suspend.target 2>/dev/null)" == "/dev/null" ]]; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "suspend.target is NOT masked" "$fix"
fi

# ── TS8: hibernate.target masked ─────────────────────────────────────────
id=TS8
desc="hibernate.target is masked"
fix="sudo systemctl mask hibernate.target"
if [[ "$(readlink /etc/systemd/system/hibernate.target 2>/dev/null)" == "/dev/null" ]]; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "hibernate.target is NOT masked" "$fix"
fi

# ── TS9: hybrid-sleep.target masked ──────────────────────────────────────
id=TS9
desc="hybrid-sleep.target is masked"
fix="sudo systemctl mask hybrid-sleep.target"
if [[ "$(readlink /etc/systemd/system/hybrid-sleep.target 2>/dev/null)" == "/dev/null" ]]; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "hybrid-sleep.target is NOT masked" "$fix"
fi

# ── TS10: loginctl Linger=yes for hive user ───────────────────────────────
id=TS10
desc="loginctl Linger=yes for $HIVE_USER"
fix="sudo loginctl enable-linger $HIVE_USER"
linger=$(loginctl show-user "$HIVE_USER" 2>/dev/null | grep '^Linger=' | cut -d= -f2 || echo "no")
if [[ "$linger" == "yes" ]]; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "Linger=$linger" "$fix"
fi

# ── TS11: hive-supervisor.service active ──────────────────────────────────
id=TS11
desc="hive-supervisor.service (user) is active"
fix="systemctl --user daemon-reload && systemctl --user restart hive-supervisor"
if systemctl --user is-active hive-supervisor &>/dev/null; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "hive-supervisor not active" "$fix"
fi

# ── TS12: research-loop.service active ────────────────────────────────────
id=TS12
desc="research-loop.service (user) is active"
fix="systemctl --user restart research-loop.service"
if systemctl --user is-active research-loop &>/dev/null; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "research-loop not active" "$fix"
fi

# ── TS13: nginx active ────────────────────────────────────────────────────
id=TS13
desc="nginx is active"
fix="sudo systemctl restart nginx"
if systemctl is-active nginx &>/dev/null; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "nginx not active" "$fix"
fi

# ── TS14: ollama service active ───────────────────────────────────────────
id=TS14
desc="ollama service is active"
fix="sudo systemctl restart ollama"
if systemctl is-active ollama &>/dev/null; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "ollama not active" "$fix"
fi

# ── TS15: cron renice job present ─────────────────────────────────────────
id=TS15
desc="cron renice job present for ollama/research_loop"
fix="(crontab -l 2>/dev/null; echo '* * * * * renice +15 -p \$(pgrep -x ollama 2>/dev/null | head -1) 2>/dev/null; pgrep -f research_loop.py 2>/dev/null | xargs -r renice +10 2>/dev/null; true') | crontab -"
if crontab -l 2>/dev/null | grep -q "renice.*ollama\|renice.*research_loop"; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "no renice cron job found" "$fix"
fi

# ── TS16: check_resource_guardian in supervisor.sh ───────────────────────
id=TS16
desc="check_resource_guardian() defined in supervisor.sh"
fix="# Manual: add check_resource_guardian() back to supervisor.sh"
if grep -q "check_resource_guardian" "$HIVE_DIR/supervisor.sh"; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "check_resource_guardian not found in supervisor.sh" "$fix"
fi

# ── TS17: port 8888 HTTP 200 (live server) ───────────────────────────────
id=TS17
desc="port 8888 (hive-live) returns HTTP 200"
fix="# Supervisor will restart hive-live automatically"
code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8888/ 2>/dev/null || echo "0")
if [[ "$code" == "200" ]]; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "HTTP $code (want 200)" "$fix"
fi

# ── TS18: port 8889 HTTP 200 (dev server) ────────────────────────────────
id=TS18
desc="port 8889 (hive-dev) returns HTTP 200"
fix="# Supervisor will restart hive-dev automatically"
code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8889/ 2>/dev/null || echo "0")
if [[ "$code" == "200" ]]; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "HTTP $code (want 200)" "$fix"
fi

# ── TS19: all expected tmux sessions exist ───────────────────────────────
id=TS19
desc="all 8 expected tmux sessions exist"
expected_sessions=(build_monitor hive-dev hive-live hive-watch opencode orchestrator ps5-hive supervisor)
missing=()
existing_sessions=$(tmux ls -F "#{session_name}" 2>/dev/null || true)
for s in "${expected_sessions[@]}"; do
    echo "$existing_sessions" | grep -qx "$s" || missing+=("$s")
done
if [[ ${#missing[@]} -eq 0 ]]; then
    _pass "$id" "$desc"
else
    # Fix: try to restart missing sessions that are in supervisor.conf
    fix_cmds=()
    for m in "${missing[@]}"; do
        case "$m" in
            hive-dev)   fix_cmds+=("tmux new-session -d -s hive-dev 'cd $HIVE_DIR && PORT=8889 python3 logstream.py'") ;;
            hive-live)  fix_cmds+=("tmux new-session -d -s hive-live 'cd $HIVE_DIR && PORT=8888 python3 logstream.py'") ;;
            orchestrator) fix_cmds+=("tmux new-session -d -s orchestrator 'cd $HIVE_DIR && python3 orchestrator.py'") ;;
            supervisor) fix_cmds+=("# supervisor manages itself — if missing, run: bash $HIVE_DIR/supervisor.sh") ;;
            *) fix_cmds+=("# $m: check supervisor.conf for restart command") ;;
        esac
    done
    fix=$(IFS='; '; echo "${fix_cmds[*]}")
    _fail "$id" "$desc" "missing: ${missing[*]}" "$fix"
fi

# ── TS20: CPU load/core < 2.0 ────────────────────────────────────────────
id=TS20
desc="CPU load/core < 2.0"
fix="pgrep -f research_loop.py | xargs -r kill -STOP; sleep 30; pgrep -f research_loop.py | xargs -r kill -CONT"
cores=$(nproc 2>/dev/null || echo "1")
load=$(awk '{printf "%.2f", $1}' /proc/loadavg)
# Use awk for float comparison
load_ok=$(awk -v l="$load" -v c="$cores" 'BEGIN{print (l/c < 2.0) ? "yes" : "no"}')
if [[ "$load_ok" == "yes" ]]; then
    _pass "$id" "$desc (load=$load cores=$cores)"
else
    _fail "$id" "$desc" "load=$load cores=$cores ratio=$(awk -v l="$load" -v c="$cores" 'BEGIN{printf "%.2f", l/c}')" "$fix"
fi

# ── TS21: disk / < 90% ───────────────────────────────────────────────────
id=TS21
desc="disk / usage < 90%"
fix="find /tmp -mtime +1 -delete 2>/dev/null; journalctl --vacuum-size=500M 2>/dev/null; true"
pct=$(df / | awk 'NR==2{gsub(/%/,""); print $5}')
if [[ "$pct" -lt 90 ]]; then
    _pass "$id" "$desc (${pct}% used)"
else
    _fail "$id" "$desc" "disk ${pct}% >= 90%" "$fix"
fi

# ── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "SYSTEM_TEST_RESULT: pass=$pass fail=$fail total=$((pass+fail))"
if [[ ${#failed_ids[@]} -gt 0 ]]; then
    echo "FAILED_IDS: ${failed_ids[*]}"
fi

# ── --fix / --fix-all mode ────────────────────────────────────────────────
if [[ "${1:-}" == "--fix" && -n "${2:-}" ]]; then
    TARGET="$2"
    echo ""
    echo "Attempting auto-fix for $TARGET..."
    # Re-run script capturing output, extract FIX_CMD_$TARGET line, execute
    fix_line=$(bash "$0" 2>/dev/null | grep "^FIX_CMD_${TARGET}:" | head -1 || true)
    if [[ -n "$fix_line" ]]; then
        fix_cmd="${fix_line#FIX_CMD_${TARGET}: }"
        echo "Running: $fix_cmd"
        eval "$fix_cmd" && echo "Fix applied for $TARGET" || echo "Fix command failed for $TARGET"
    else
        echo "No auto-fix defined for $TARGET (may have passed or fix is manual)"
    fi
fi

if [[ "${1:-}" == "--fix-all" ]]; then
    echo ""
    echo "Attempting auto-fix for all failed tests: ${failed_ids[*]}"
    for tid in "${failed_ids[@]}"; do
        fix_line=$(grep "^FIX_CMD_${tid}:" <<< "$(bash "$0" 2>/dev/null)" | head -1 || true)
        if [[ -n "$fix_line" ]]; then
            fix_cmd="${fix_line#FIX_CMD_${tid}: }"
            echo "[$tid] Running: ${fix_cmd:0:80}..."
            eval "$fix_cmd" 2>/dev/null && echo "[$tid] fixed" || echo "[$tid] fix failed"
        fi
    done
fi

[[ "$fail" -eq 0 ]]
