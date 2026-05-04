#!/usr/bin/env python3
"""
orchestrator.py — Autonomous hive orchestrator.

Runs permanently in the 'orchestrator' tmux session (managed by supervisor.sh).
Never exits on its own.

Responsibilities
----------------
1. Heartbeat every 2 min — keeps supervisor is_dead check happy, visible in UI
2. Compaction every 15 min — LLM reads full hive state, writes goal/summary/next-steps
   back into orchestrator_sessions ring via hive_status.update_orchestrator_session()
3. Health triage every sweep — detects dead sessions via tmux, pings watchdog,
   logs blockers (does NOT duplicate hive-doctor work — complementary layer)
4. Self-healing — if /api/status or /api/queue returns non-200, logs a blocker;
   if hive-dev (port 8889) is down, supervisor handles restart via supervisor.conf

All LLM calls use stdlib http.client (no pip).  Falls back gracefully if key absent.
"""

import json
import os
import sys
import time
import ssl
import http.client
import subprocess
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

# ── path bootstrap ────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import hive_status  # noqa: E402

# ── env / API key ─────────────────────────────────────────────────────────────
def _load_env() -> dict:
    """Load env vars from the first env file that exists."""
    candidates = [
        os.path.expanduser("~/.config/hive-ui/env"),
        os.path.expanduser("~/.config/research-hive/env"),
        os.path.join(SCRIPT_DIR, ".env"),
    ]
    env = {}
    for p in candidates:
        if os.path.isfile(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, _, v = line.partition("=")
                        env[k.strip()] = v.strip().strip('"').strip("'")
            break
    return env

_hive_env = _load_env()
OPENROUTER_KEY   = os.environ.get("OPENROUTER_API_KEY") or _hive_env.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = (os.environ.get("OPENROUTER_MODEL")
                    or _hive_env.get("OPENROUTER_MODEL", "inclusionai/ling-2.6-1t:free"))
LLM_BASE_URL     = "https://openrouter.ai/api/v1"
HIVE_NAME        = "default"

# ── timing ────────────────────────────────────────────────────────────────────
HEARTBEAT_INTERVAL  = 120    # 2 min — print a visible line
COMPACTION_INTERVAL = 900    # 15 min — LLM compaction call
TRIAGE_INTERVAL     = 60     # 1 min — check session liveness
SELF_TEST_INTERVAL  = 300    # 5 min — system invariant self-test
GITOPS_INTERVAL     = 300    # 5 min — PR status poll + auto-merge
PROMOTE_INTERVAL    = 3600   # 1 hr  — develop→main promotion check

# ── rate limiting ─────────────────────────────────────────────────────────────
_MAX_LLM_CALLS_HR = 8        # conservative — shares OpenRouter free quota
_llm_call_times   = []


def _llm_budget_ok() -> bool:
    now = time.time()
    _llm_call_times[:] = [t for t in _llm_call_times if now - t < 3600]
    return len(_llm_call_times) < _MAX_LLM_CALLS_HR


def _llm_budget_consume():
    _llm_call_times.append(time.time())


# ── LLM call ─────────────────────────────────────────────────────────────────
def call_llm(messages: list, max_tokens: int = 512, timeout: int = 60):
    """Non-streaming LLM call via stdlib http.client. Returns (text, err)."""
    if not OPENROUTER_KEY:
        return "", "no API key"
    if not _llm_budget_ok():
        return "", f"budget exceeded ({_MAX_LLM_CALLS_HR} calls/hr)"
    parsed = urlparse(LLM_BASE_URL)
    host   = parsed.netloc
    path   = parsed.path.rstrip("/") + "/chat/completions"
    body   = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
    }).encode()
    headers = {
        "Content-Type":   "application/json",
        "Authorization":  f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer":   "https://hive-ui.local",
        "X-Title":        "Hive Orchestrator",
        "Content-Length": str(len(body)),
    }
    try:
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection(host, context=ctx, timeout=timeout)
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        raw  = resp.read().decode("utf-8", errors="replace")
        conn.close()
        if resp.status != 200:
            return "", f"HTTP {resp.status}"
        data = json.loads(raw)
        # Handle reasoning models (delta.reasoning before delta.content)
        choice = data.get("choices", [{}])[0]
        text   = choice.get("message", {}).get("content", "")
        if not text:
            text = choice.get("message", {}).get("reasoning", "")
        _llm_budget_consume()
        hive_status.increment_metric("openrouter_calls_today", updated_by="orchestrator")
        return text, None
    except Exception as e:
        return "", str(e)


# ── helpers ───────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_hms() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _ts():
    return f"[{_now_hms()} UTC]"


# ── active task context manager ───────────────────────────────────────────────
import contextlib

@contextlib.contextmanager
def _doing(task: str):
    """
    Context manager: sets active_task at entry, clears at exit (even on error).
    Usage:
        with _doing("triage: checking sessions"):
            ...
    """
    hive_status.set_active_task("orchestrator", task)
    try:
        yield
    finally:
        hive_status.clear_active_task()


def _log(msg: str):
    print(f"{_ts()} [orchestrator] {msg}", flush=True)


def tmux_sessions() -> list:
    try:
        r = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5
        )
        return [s.strip() for s in r.stdout.strip().split("\n") if s.strip()]
    except Exception:
        return []


def session_is_alive(name: str) -> bool:
    """Return True if the named tmux session exists AND has a child process."""
    try:
        pane_pid = subprocess.run(
            ["tmux", "display", "-t", name, "-p", "#{pane_pid}"],
            capture_output=True, text=True, timeout=3
        ).stdout.strip()
        if not pane_pid:
            return False
        children = subprocess.run(
            ["pgrep", "-P", pane_pid],
            capture_output=True, text=True, timeout=3
        ).stdout.strip()
        return bool(children)
    except Exception:
        return False


def alert_watchdog(msg: str):
    """Send a visible alert message to the watchdog tmux session."""
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", "watchdog", msg, "Enter"],
            timeout=5, capture_output=True
        )
    except Exception:
        pass


# ── triage ────────────────────────────────────────────────────────────────────
# Sessions that are critical and must be alerted if dead.
# supervisor.conf handles restarts; we handle alerting.
CRITICAL_SESSIONS = {"hive-dev", "hive-live", "hive-watch"}

_alerted: dict = {}   # session -> last alert epoch (throttle: 10 min between alerts)


def triage():
    """Check critical sessions; alert watchdog if any are dead."""
    sessions = set(tmux_sessions())
    now = time.time()
    for sess in CRITICAL_SESSIONS:
        if sess not in sessions:
            # Session doesn't exist at all
            if now - _alerted.get(sess, 0) > 600:
                msg = f"[orchestrator] CRITICAL: tmux session '{sess}' does not exist!"
                _log(msg)
                alert_watchdog(msg)
                hive_status.add_blocker(
                    HIVE_NAME, "orchestrator",
                    f"tmux session '{sess}' missing entirely",
                    severity="critical",
                )
                _alerted[sess] = now
        elif not session_is_alive(sess):
            if now - _alerted.get(sess, 0) > 600:
                msg = f"[orchestrator] WARNING: '{sess}' session is dead (no child process)"
                _log(msg)
                alert_watchdog(msg)
                hive_status.add_blocker(
                    HIVE_NAME, "orchestrator",
                    f"Session '{sess}' dead — supervisor should restart it",
                    severity="high",
                )
                _alerted[sess] = now

    # Resolve stale orchestrator-raised blockers for sessions that are now healthy
    s = hive_status.load()
    for b in s.get("blockers", []):
        if b.get("status") != "open":
            continue
        if b.get("agent") != "orchestrator":
            continue
        for sess in CRITICAL_SESSIONS:
            if sess in b.get("description", "") and sess in sessions and session_is_alive(sess):
                hive_status.resolve_blocker(b["id"], f"Session '{sess}' is healthy again")
                _log(f"auto-resolved blocker for '{sess}' — now healthy")
                break

    # ── avahi mDNS watchdog (sk_avahi_mdns) ─────────────────────────────────
    # Check at most once every 10 minutes; auto-fix publish-workstation=no
    _AVAHI_CHECK_INTERVAL = 600
    _AVAHI_CONF = "/etc/avahi/avahi-daemon.conf"
    if now - _alerted.get("avahi_mdns_check", 0) > _AVAHI_CHECK_INTERVAL:
        _alerted["avahi_mdns_check"] = now
        try:
            r = subprocess.run(
                ["avahi-resolve", "--name", "desktop.local"],
                capture_output=True, timeout=5
            )
            avahi_ok = r.returncode == 0
        except Exception:
            avahi_ok = False

        if not avahi_ok:
            # Check if the config has the wrong value
            try:
                conf_txt = open(_AVAHI_CONF).read()
                needs_fix = "publish-workstation=no" in conf_txt
            except Exception:
                needs_fix = False

            if needs_fix:
                try:
                    subprocess.run(
                        ["sudo", "-S", "sed", "-i",
                         "s/^publish-workstation=no$/publish-workstation=yes/",
                         _AVAHI_CONF],
                        input=b"ayb\n", capture_output=True, timeout=10
                    )
                    subprocess.run(
                        ["sudo", "-S", "systemctl", "restart", "avahi-daemon"],
                        input=b"ayb\n", capture_output=True, timeout=10
                    )
                    _log("[orchestrator] avahi watchdog: fixed publish-workstation=yes, restarted avahi-daemon")
                    # Resolve any existing avahi blocker
                    s2 = hive_status.load()
                    for b in s2.get("blockers", []):
                        if b.get("status") == "open" and "avahi" in b.get("description", "").lower():
                            hive_status.resolve_blocker(b["id"], "avahi watchdog: auto-fixed publish-workstation=yes")
                except Exception as exc:
                    _log(f"[orchestrator] avahi watchdog fix failed: {exc}")
            else:
                # Resolve can fail for transient reasons; only raise blocker if rate-limited
                if now - _alerted.get("avahi_mdns", 0) > _AVAHI_CHECK_INTERVAL:
                    _log("[orchestrator] avahi watchdog: desktop.local not resolving (transient?)")
                    _alerted["avahi_mdns"] = now
        else:
            # mDNS healthy — resolve any existing avahi blocker silently
            s2 = hive_status.load()
            for b in s2.get("blockers", []):
                if b.get("status") == "open" and "avahi" in b.get("description", "").lower():
                    hive_status.resolve_blocker(b["id"], "avahi watchdog: desktop.local resolving normally")


# ── research-loop error watchdog ──────────────────────────────────────────────
# Detects when a research_loop.py session is stuck in a 400-error loop
# (e.g. model doesn't support thinking, incompatible payload) and auto-restarts
# it.  Checks at most once per triage interval.

_RLOOP_400_RESTART_COOLDOWN = 600   # minimum seconds between repeated alerts
MAX_SYNTH_RETRIES = 8               # mirrors research_loop.py — for log messages only
_rloop_last_restart: dict = {}       # session_name → timestamp of last restart
_rloop_400_counts: dict = {}         # session_name → consecutive 400 count seen

def _watch_research_loop_errors() -> None:
    """Scan research_loop tmux sessions for 400-loop patterns.

    ALERT-ONLY — never sends signals or restarts processes.
    The circuit breaker inside research_loop.py is the authoritative
    recovery mechanism; this function only adds visibility (log + blocker).

    Two consecutive triage calls must both observe the threshold before a
    blocker is raised, preventing false positives from a single pane-buffer
    snapshot that still contains historical error lines.
    """
    import re as _re
    _400_pat  = _re.compile(r"400 Bad Request")
    # Broader OOM filter — all patterns that have their own self-heal in chat()
    _skip_pat = _re.compile(
        r"(input too large|out of memory|kv cache|cuda error|context length"
        r"|failed to allocate|llama_kv_cache|ggml_|no space left"
        r"|prompt eval requires|too many tokens|does not support thinking)"
    )
    now = time.time()

    try:
        sessions_out = subprocess.check_output(
            ["tmux", "ls", "-F", "#{session_name}"], text=True, timeout=5
        ).splitlines()
    except Exception:
        return

    for sess in sessions_out:
        if sess not in ("ps5-hive", "wegia-hive"):
            continue

        # Capture last 80 lines of the pane
        try:
            pane = subprocess.check_output(
                ["tmux", "capture-pane", "-t", sess, "-p", "-S", "-80"],
                text=True, timeout=5
            )
        except Exception:
            continue

        lines = pane.splitlines()
        count_400 = sum(1 for ln in lines if _400_pat.search(ln))
        has_skip  = any(_skip_pat.search(ln) for ln in lines)

        # Threshold: 40/80 lines must be 400 errors, and none from the skip
        # list (those have their own self-heal paths).
        if count_400 < 40 or has_skip:
            _rloop_400_counts[sess] = 0
            continue

        # Require two consecutive observations before raising any alert
        prev_count = _rloop_400_counts.get(sess, 0)
        _rloop_400_counts[sess] = count_400
        if prev_count < 40:
            # First observation — wait for next triage cycle to confirm
            _log(
                f"[watchdog] {sess}: {count_400}/80 pane lines are '400 Bad Request' "
                f"— observing; will alert next cycle if still failing"
            )
            continue

        # Two consecutive observations above threshold → raise a blocker (alert only)
        # Check we haven't already raised one recently
        last_alerted = _rloop_last_restart.get(sess, 0)
        if now - last_alerted < _RLOOP_400_RESTART_COOLDOWN:
            continue

        _log(
            f"[watchdog] {sess}: confirmed 400-loop ({count_400}/80 lines, "
            f"2 consecutive observations) — raising blocker (no auto-action; "
            f"circuit breaker inside research_loop.py handles recovery)"
        )
        hive_status.add_blocker(
            sess, "orchestrator",
            f"research_loop sustained 400-loop on {sess} ({count_400}/80 pane lines) "
            f"— circuit breaker will switch models after {MAX_SYNTH_RETRIES} attempts",
            severity="high",
        )
        _rloop_last_restart[sess] = now  # reuse field as "last alerted" timestamp


# ── stale blocker / next-step pruner ─────────────────────────────────────────
# The orchestrator sometimes raises blockers or next-steps for conditions that
# were fixed but never explicitly resolved (e.g. sessions that now exist).
# This runs every triage cycle and cleans up anything stale.

def _prune_stale_status_entries() -> None:
    """Resolve open blockers and cancel pending next-steps that no longer apply."""
    s = hive_status.load()
    sessions = set(tmux_sessions())
    now_sessions_alive = {sess for sess in sessions if session_is_alive(sess)}

    # Patterns that become stale once the session is alive
    _SESSION_PATTERNS = ["hive-watch", "hive-live", "hive-dev", "build_monitor",
                         "orchestrator", "ps5-hive", "opencode"]

    for b in s.get("blockers", []):
        if b.get("status") != "open":
            continue
        desc = b.get("description", "")
        # Resolve "missing session" / "dead session" blockers if session is now alive
        for sess in _SESSION_PATTERNS:
            if sess in desc and sess in now_sessions_alive:
                hive_status.resolve_blocker(b["id"], f"auto-pruned: {sess} is now alive")
                _log(f"pruned stale blocker {b['id']}: {desc[:80]}")
                break
        # Resolve "long backoff" blocker if session is now stable (has a child process)
        if "long backoff" in desc or "restart(s)" in desc:
            for sess in _SESSION_PATTERNS:
                if sess in desc and sess in now_sessions_alive:
                    hive_status.resolve_blocker(b["id"], f"auto-pruned: {sess} recovered from backoff")
                    break

    # Cancel pending next-steps for sessions that already exist
    for ns in s.get("next_steps", []):
        if ns.get("status") != "pending":
            continue
        desc = ns.get("description", "")
        for sess in _SESSION_PATTERNS:
            if ("Create missing" in desc or "Restart dead" in desc) and sess in desc:
                if sess in now_sessions_alive:
                    hive_status.update_next_step(ns["id"], "cancelled")
                    _log(f"pruned stale next-step {ns['id']}: {desc[:80]}")
                    break



# Maps test IDs → shell fix commands (run as the ayoub user).
# Sudo commands use -S to read password from stdin.
_AUTO_FIX_REGISTRY: dict = {
    "TS1":  "mkdir -p /etc/systemd/system/ollama.service.d",
    "TS2":  (
        "bash -c 'mkdir -p /etc/systemd/system/ollama.service.d && "
        "printf \"[Service]\\nCPUQuota=1000%%\\nNice=15\\nIOWeight=50\\n"
        "Environment=OLLAMA_NUM_THREAD=10\\nEnvironment=OLLAMA_MAX_LOADED_MODELS=1\\n\" "
        "> /etc/systemd/system/ollama.service.d/throttle.conf'"
    ),
    "TS3":  (
        "bash -c 'grep -q CPUQuota=1000%% /etc/systemd/system/ollama.service.d/throttle.conf "
        "|| echo CPUQuota=1000%% >> /etc/systemd/system/ollama.service.d/throttle.conf'"
    ),
    "TS4":  "systemctl daemon-reload && systemctl restart ollama",
    "TS5":  "pgrep -x ollama | head -1 | xargs -r renice +15 -p",
    "TS6":  "ln -sf /dev/null /etc/systemd/system/sleep.target",
    "TS7":  "ln -sf /dev/null /etc/systemd/system/suspend.target",
    "TS8":  "ln -sf /dev/null /etc/systemd/system/hibernate.target",
    "TS9":  "ln -sf /dev/null /etc/systemd/system/hybrid-sleep.target",
    "TS10": f"loginctl enable-linger {os.environ.get('USER', 'ayoub')}",
    "TS11": "systemctl --user daemon-reload && systemctl --user restart hive-supervisor",
    "TS12": "systemctl --user restart research-loop.service",
    "TS13": "systemctl restart nginx",
    "TS14": "systemctl restart ollama",
    "TS15": (
        "(crontab -l 2>/dev/null; echo '* * * * * "
        "renice +15 -p $(pgrep -x ollama 2>/dev/null | head -1) 2>/dev/null; "
        "pgrep -f research_loop.py 2>/dev/null | xargs -r renice +10 2>/dev/null; true') "
        "| crontab -"
    ),
    "TS19": "",   # handled per-session in the script itself
    "TS20": "pgrep -f research_loop.py | head -5 | xargs -r kill -STOP",
    "TS21": "find /tmp -mtime +1 -delete 2>/dev/null; journalctl --vacuum-size=500M 2>/dev/null; true",
}

# Track last self-test result to avoid flooding blockers
_last_self_test_failures: set = set()
_self_test_auto_fixed_total: int = 0


def _run_self_test_script() -> tuple[bool, list[str], list[str]]:
    """Run tests/test_system.sh, return (all_passed, fail_ids, output_lines)."""
    script = os.path.join(SCRIPT_DIR, "tests", "test_system.sh")
    if not os.path.isfile(script):
        return False, ["SCRIPT_MISSING"], [f"test_system.sh not found at {script}"]
    try:
        r = subprocess.run(
            ["bash", script],
            capture_output=True, text=True, timeout=60,
        )
        lines = r.stdout.splitlines() + r.stderr.splitlines()
        fail_ids = [
            ln.split(":")[1].split()[0].strip()
            for ln in lines
            if ln.startswith("FAIL:") and len(ln.split(":")) >= 2
        ]
        return r.returncode == 0, fail_ids, lines
    except subprocess.TimeoutExpired:
        return False, ["TIMEOUT"], ["test_system.sh timed out after 60s"]
    except Exception as e:
        return False, ["ERROR"], [f"test_system.sh error: {e}"]


def _apply_fix(test_id: str) -> bool:
    """Apply the auto-fix for a test ID. Returns True if command ran without error."""
    cmd = _AUTO_FIX_REGISTRY.get(test_id, "")
    if not cmd:
        _log(f"[self-test] no auto-fix for {test_id}")
        return False
    _log(f"[self-test] applying fix for {test_id}: {cmd[:80]}")
    try:
        # Some fixes need sudo - they use ln -sf or systemctl as root
        # Try as user first; sudo commands will silently fail if no NOPASSWD
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=30, env={**os.environ, "HOME": os.path.expanduser("~")},
        )
        if r.returncode == 0:
            _log(f"[self-test] fix applied OK for {test_id}")
            return True
        # If it needs sudo, retry with sudo -S ayb
        if "sudo" in cmd or any(
            tok in cmd for tok in ["systemctl restart", "systemctl mask",
                                    "ln -sf /dev/null /etc/", "loginctl enable-linger"]
        ):
            r2 = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30,
                input="ayb\n",
                env={**os.environ, "HOME": os.path.expanduser("~")},
            )
            if r2.returncode == 0:
                _log(f"[self-test] fix applied OK (sudo) for {test_id}")
                return True
        _log(f"[self-test] fix failed for {test_id}: {r.stderr[:80]}")
        return False
    except Exception as e:
        _log(f"[self-test] fix exception for {test_id}: {e}")
        return False


def self_test():
    """Run test_system.sh, auto-fix failures, raise/resolve blockers, log achievements."""
    global _last_self_test_failures, _self_test_auto_fixed_total

    _log("[self-test] running system invariant checks...")
    passed, fail_ids, lines = _run_self_test_script()

    if passed:
        _log("[self-test] all system invariants PASS")
        # Resolve any open self-test blockers
        s = hive_status.load()
        for b in s.get("blockers", []):
            if (b.get("status") == "open"
                    and b.get("agent") == "orchestrator"
                    and "self-test" in b.get("description", "").lower()):
                hive_status.resolve_blocker(b["id"], "self-test: all invariants passing")
                _log(f"[self-test] resolved blocker {b['id']}")
        _last_self_test_failures = set()
        return

    _log(f"[self-test] {len(fail_ids)} invariant(s) failed: {fail_ids}")

    new_failures   = set(fail_ids) - _last_self_test_failures
    fixed_this_run = []

    for tid in fail_ids:
        if tid in ("TIMEOUT", "ERROR", "SCRIPT_MISSING"):
            hive_status.add_blocker(
                HIVE_NAME, "orchestrator",
                f"self-test: {tid} — could not run test_system.sh",
                severity="high",
            )
            continue

        # Try auto-fix
        fix_ok = _apply_fix(tid)
        if fix_ok:
            # Re-verify: re-run full script and check this ID passed
            _, recheck_ids, _ = _run_self_test_script()
            if tid not in recheck_ids:
                fixed_this_run.append(tid)
                _self_test_auto_fixed_total += 1
                _log(f"[self-test] {tid} auto-fixed and verified ✓")
                # Resolve any open blocker for this test
                s = hive_status.load()
                resolve_bid = next(
                    (b["id"] for b in s.get("blockers", [])
                     if b.get("status") == "open"
                     and b.get("agent") == "orchestrator"
                     and tid in b.get("description", "")),
                    None,
                )
                _record_improvement(
                    skill=f"auto_fix_{tid}",
                    description=f"Automatically detects and repairs {tid} system invariant failures",
                    example=f"Applied fix for {tid}: {_AUTO_FIX_REGISTRY.get(tid,'')[:60]}",
                    tags=["self-healing", "system-invariant", "auto-fix"],
                    achievement=f"Auto-fixed system invariant {tid}",
                    evidence=f"test_system.sh {tid} now passes after auto-fix",
                    resolve_blocker_id=resolve_bid,
                    resolve_msg=f"self-test: {tid} auto-fixed",
                )
            else:
                _log(f"[self-test] {tid} fix ran but test still failing")
                if tid in new_failures:
                    hive_status.add_blocker(
                        HIVE_NAME, "orchestrator",
                        f"self-test: {tid} failing — auto-fix attempted but not sufficient",
                        severity="high",
                    )
        else:
            # No fix or fix failed — raise blocker only if new
            if tid in new_failures:
                hive_status.add_blocker(
                    HIVE_NAME, "orchestrator",
                    f"self-test: {tid} failing — no auto-fix available or fix failed",
                    severity="high",
                )

    _last_self_test_failures = set(fail_ids) - set(fixed_this_run)

    if fixed_this_run:
        _log(f"[self-test] auto-fixed {len(fixed_this_run)} invariant(s): {fixed_this_run} "
             f"(total auto-fixes all time: {_self_test_auto_fixed_total})")


# ── issue → test pipeline ─────────────────────────────────────────────────────
# When a new failure type arrives that isn't in test_system.sh, generate a
# minimal test stub and commit it — the suite grows permanently.

_ISSUE_TEST_PATTERNS: dict = {
    # Maps regex pattern → (test_id_prefix, test_body_template)
    # These are match patterns for blocker descriptions.
    r"ollama.*cpu|cpu.*ollama|933%|ollama.*throttl": (
        "ollama_cpu",
        """# Auto-generated: Ollama CPU throttle check
id=TSauto_ollama_cpu
desc="Ollama CPUQuota=1000% in throttle.conf (auto-generated)"
fix="echo 'CPUQuota=1000%' | sudo tee -a /etc/systemd/system/ollama.service.d/throttle.conf"
if grep -q 'CPUQuota=1000%' /etc/systemd/system/ollama.service.d/throttle.conf 2>/dev/null; then
    _pass "$id" "$desc"
else
    _fail "$id" "$desc" "CPUQuota=1000% not set" "$fix"
fi
""",
    ),
    r"sleep.*target|suspend.*target|hibernate": (
        "sleep_targets",
        """# Auto-generated: Sleep targets masked check
id=TSauto_sleep_targets
desc="Sleep/suspend targets masked (auto-generated)"
fix="sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target"
all_masked=1
for t in sleep.target suspend.target hibernate.target; do
    [[ "$(readlink /etc/systemd/system/$t 2>/dev/null)" == "/dev/null" ]] || all_masked=0
done
if [[ $all_masked -eq 1 ]]; then _pass "$id" "$desc"
else _fail "$id" "$desc" "one or more targets not masked" "$fix"; fi
""",
    ),
    r"disk.*full|disk.*90|no space": (
        "disk_space",
        """# Auto-generated: Disk space check
id=TSauto_disk_space
desc="Disk / usage < 90% (auto-generated)"
fix="find /tmp -mtime +1 -delete 2>/dev/null; journalctl --vacuum-size=200M 2>/dev/null"
pct=$(df / | awk 'NR==2{gsub(/%/,""); print $5}')
if [[ "$pct" -lt 90 ]]; then _pass "$id" "$desc (${pct}%)"
else _fail "$id" "$desc" "${pct}% >= 90%" "$fix"; fi
""",
    ),
    r"oom|out of memory|killed|ram.*low": (
        "oom",
        """# Auto-generated: Available RAM check
id=TSauto_oom
desc="Available RAM > 500MB (auto-generated)"
fix="pgrep -f research_loop.py | head -5 | xargs -r kill -STOP"
avail=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
if [[ "$avail" -gt 512000 ]]; then _pass "$id" "$desc (${avail}kB)"
else _fail "$id" "$desc" "only ${avail}kB available" "$fix"; fi
""",
    ),
}

_issue_test_committed: set = set()   # patterns already turned into tests


def _issue_to_test(blocker_description: str) -> None:
    """If blocker matches a known pattern and no test exists yet, generate + commit a test."""
    learned_dir = os.path.join(SCRIPT_DIR, "tests", "learned")
    os.makedirs(learned_dir, exist_ok=True)

    for pattern, (name, body_template) in _ISSUE_TEST_PATTERNS.items():
        if name in _issue_test_committed:
            continue
        if not re.search(pattern, blocker_description, re.IGNORECASE):
            continue

        # Check if already on disk
        dest = os.path.join(learned_dir, f"test_{name}.sh")
        if os.path.isfile(dest):
            _issue_test_committed.add(name)
            continue

        # Write the test stub
        header = f"""#!/usr/bin/env bash
# AUTO-GENERATED by orchestrator issue→test pipeline
# Source blocker: {blocker_description[:80]}
# Generated at: {_now_iso()}
set -euo pipefail
pass=0; fail=0
_pass(){{ echo "PASS: $1 $2"; (( pass++ )) || true; }}
_fail(){{ echo "FAIL: $1 $2 — $3"; [[ -n "${{4:-}}" ]] && echo "FIX_CMD_$1: $4"; (( fail++ )) || true; }}

"""
        footer = """
echo ""
echo "SYSTEM_TEST_RESULT: pass=$pass fail=$fail total=$((pass+fail))"
[[ "$fail" -eq 0 ]]
"""
        try:
            with open(dest, "w") as f:
                f.write(header + body_template + footer)
            os.chmod(dest, 0o755)
            _log(f"[issue→test] generated test: {dest}")

            # Auto-commit + open PR via unified gitops path
            commit_msg = (
                f"auto: add learned test test_{name}.sh\n\n"
                f"Generated by orchestrator issue→test pipeline.\n"
                f"Source incident: {blocker_description[:120]}\n"
                f"Generated: {_now_iso()}"
            )
            _git_branch_pr(
                filepath=dest,
                slug=name,
                commit_msg=commit_msg,
                pr_title=f"auto: add learned test for '{name}'",
                pr_body=(
                    f"## Auto-generated test\n\n"
                    f"Source incident: {blocker_description[:200]}\n\n"
                    f"Test file: `tests/learned/test_{name}.sh`\n\n"
                    f"_Generated automatically by orchestrator issue→test pipeline._"
                ),
            )
            _issue_test_committed.add(name)

            _record_improvement(
                skill=f"auto_test_{name}",
                description=f"Auto-generated test for '{name}' from incident: {blocker_description[:60]}",
                example=f"tests/learned/test_{name}.sh",
                tags=["self-improving", "auto-generated", "issue-to-test"],
            )
        except Exception as e:
            _log(f"[issue→test] failed to write test for {name}: {e}")


# ── git / gh helpers (single source of truth for all git operations) ──────────
_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME":    "orchestrator",
    "GIT_AUTHOR_EMAIL":   "orchestrator@hive.local",
    "GIT_COMMITTER_NAME": "orchestrator",
    "GIT_COMMITTER_EMAIL":"orchestrator@hive.local",
}

_GITHUB_REPO = "iubayb/hive-ui"


def _git(args: list, check: bool = False, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a git command in SCRIPT_DIR with the canonical git env."""
    return subprocess.run(
        ["git"] + args,
        cwd=SCRIPT_DIR, capture_output=True, text=True,
        env=_GIT_ENV, timeout=timeout, check=check,
    )


def _gh(args: list, timeout: int = 20) -> subprocess.CompletedProcess:
    """Run a gh CLI command in SCRIPT_DIR. Never raises — callers check returncode."""
    return subprocess.run(
        ["gh"] + args,
        cwd=SCRIPT_DIR, capture_output=True, text=True, timeout=timeout,
    )


def _git_in_repo() -> bool:
    """Return True if SCRIPT_DIR is inside a git repository."""
    return _git(["rev-parse", "--git-dir"]).returncode == 0


def _current_branch() -> str:
    r = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def _git_branch_pr(
    filepath: str,
    slug: str,
    commit_msg: str,
    pr_title: str,
    pr_body: str,
    base: str = "develop",
    prefix: str = "feat/auto-",
) -> str | None:
    """
    Full GitOps path for one auto-generated artifact:
      1. checkout (or create) branch  <prefix><slug>
      2. git add <filepath>
      3. git commit
      4. git push origin <branch>
      5. gh pr create --base <base>  (skips if PR already open)
    Returns the PR URL on success, None on any failure.
    Single source of truth — no other function does git operations.
    """
    if not _git_in_repo():
        _log("[gitops] not a git repo — skipping branch/PR creation")
        return None

    branch = f"{prefix}{slug}"
    try:
        # Create or switch to the auto branch
        existing = _git(["branch", "--list", branch]).stdout.strip()
        if existing:
            _git(["checkout", branch], check=True)
        else:
            _git(["checkout", "-b", branch], check=True)

        _git(["add", filepath], check=True)

        # Commit (ignore "nothing to commit")
        r = _git(["commit", "-m", commit_msg])
        if r.returncode not in (0, 1):   # 1 = nothing to commit
            _log(f"[gitops] commit failed for {slug}: {r.stderr.strip()}")
            _git(["checkout", "develop"])
            return None

        # Push
        push_r = _git(["push", "-u", "origin", branch], timeout=30)
        if push_r.returncode != 0:
            _log(f"[gitops] push failed for {branch}: {push_r.stderr.strip()[:120]}")
            _git(["checkout", "develop"])
            return None

        # Create PR (idempotent — gh skips if already open)
        pr_r = _gh([
            "pr", "create",
            "--repo", _GITHUB_REPO,
            "--base", base,
            "--head", branch,
            "--title", pr_title,
            "--body", pr_body,
        ])
        _git(["checkout", "develop"])
        if pr_r.returncode == 0:
            url = pr_r.stdout.strip()
            _log(f"[gitops] PR created: {url}")
            return url
        # "already exists" is not an error
        if "already exists" in pr_r.stderr:
            _log(f"[gitops] PR for {branch} already open — skipping")
            return None
        _log(f"[gitops] gh pr create failed: {pr_r.stderr.strip()[:120]}")
        return None

    except Exception as e:
        _log(f"[gitops] _git_branch_pr error (non-fatal): {e}")
        try:
            _git(["checkout", "develop"])
        except Exception:
            pass
        return None


def _record_improvement(
    skill: str,
    description: str,
    example: str = "",
    tags: list | None = None,
    achievement: str | None = None,
    evidence: str = "",
    resolve_blocker_id: str | None = None,
    resolve_msg: str = "",
) -> None:
    """
    Single call that atomically:
      • registers a capability (deduped by skill slug)
      • optionally records an achievement
      • optionally resolves an open blocker
    DRY mandate: no caller should call add_capability directly — use this instead.
    """
    hive_status.add_capability(
        HIVE_NAME, "orchestrator",
        skill=skill,
        description=description,
        example=example,
        tags=tags or [],
    )
    if achievement:
        hive_status.add_achievement(
            HIVE_NAME, "orchestrator",
            achievement,
            evidence=evidence or description,
        )
    if resolve_blocker_id:
        hive_status.resolve_blocker(resolve_blocker_id, resolve_msg or description)


# ── GitOps triage: poll open PRs and auto-merge when CI is green ──────────────
GITOPS_INTERVAL = 300    # 5 min — check PR statuses


def _poll_open_prs() -> None:
    """
    Fetch all open PRs on iubayb/hive-ui with base=develop.
    Auto-merge any whose CI checks have all passed.
    Logs a blocker for any that are failing.
    Idempotent — safe to call every GITOPS_INTERVAL.
    """
    if not _gh(["auth", "status"]).returncode == 0:
        return   # gh not authenticated — skip silently

    r = _gh([
        "pr", "list",
        "--repo", _GITHUB_REPO,
        "--base", "develop",
        "--state", "open",
        "--json", "number,title,headRefName,statusCheckRollup",
        "--limit", "20",
    ])
    if r.returncode != 0:
        return

    try:
        prs = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return

    for pr in prs:
        num    = pr.get("number")
        title  = pr.get("title", "")
        branch = pr.get("headRefName", "")
        checks = pr.get("statusCheckRollup") or []

        if not (branch.startswith("feat/auto-") or branch.startswith("fix/auto-")):
            continue   # only auto-branches get auto-merged

        if not checks:
            continue   # CI not yet run

        states = {c.get("conclusion") or c.get("status", "PENDING") for c in checks}

        if states <= {"SUCCESS", "SKIPPED", "NEUTRAL"}:
            # All checks green — auto-merge
            merge_r = _gh([
                "pr", "merge", str(num),
                "--repo", _GITHUB_REPO,
                "--squash", "--auto",
                "--delete-branch",
            ])
            if merge_r.returncode == 0:
                _log(f"[gitops] auto-merged PR #{num} ({title})")
                _record_improvement(
                    skill=f"gitops_merge_pr_{num}",
                    description=f"Auto-merged PR #{num}: {title}",
                    tags=["gitops", "auto-merge", "ci-green"],
                    achievement=f"CI green → auto-merged PR #{num}: {title}",
                    evidence=f"Branch {branch} merged to develop",
                )
            else:
                _log(f"[gitops] auto-merge failed for PR #{num}: {merge_r.stderr.strip()[:80]}")

        elif "FAILURE" in states or "ERROR" in states:
            _log(f"[gitops] PR #{num} ({branch}) has CI failures")
            # Add blocker only if not already open for this PR
            s = hive_status.load()
            already = any(
                b.get("status") == "open" and f"PR #{num}" in b.get("description", "")
                for b in s.get("blockers", [])
            )
            if not already:
                hive_status.add_blocker(
                    HIVE_NAME, "orchestrator",
                    f"CI failure on PR #{num} ({branch}): {title}",
                    severity="high",
                )


def _develop_to_main_pr() -> None:
    """
    Once a week (or when ≥5 auto-PRs have been merged to develop since last
    promote), open a develop → main PR and tag a GitHub Release.
    Idempotent — skips if a promote PR is already open.
    """
    # Check for existing open develop→main PR
    r = _gh([
        "pr", "list",
        "--repo", _GITHUB_REPO,
        "--base", "main",
        "--head", "develop",
        "--state", "open",
        "--json", "number",
    ])
    try:
        existing = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return
    if existing:
        return   # already open

    # Count merged auto-PRs since last main update
    log_r = _git(["log", "origin/main..origin/develop", "--oneline"])
    commits = [l for l in (log_r.stdout or "").splitlines() if l.strip()]
    if len(commits) < 5:
        return   # not enough accumulated yet

    tag = f"v{datetime.now(timezone.utc).strftime('%Y.%m.%d')}"
    pr_r = _gh([
        "pr", "create",
        "--repo", _GITHUB_REPO,
        "--base", "main",
        "--head", "develop",
        "--title", f"chore: promote develop → main ({tag})",
        "--body", (
            f"## Auto-promotion\n\n"
            f"Accumulated {len(commits)} commit(s) on `develop` since last `main` update.\n\n"
            f"Merging to trigger Vercel production deploy and create release `{tag}`.\n\n"
            f"_Generated automatically by orchestrator._"
        ),
    ])
    if pr_r.returncode == 0:
        _log(f"[gitops] opened develop→main PR: {pr_r.stdout.strip()}")
        # Create a GitHub Release draft (best-effort)
        _gh([
            "release", "create", tag,
            "--repo", _GITHUB_REPO,
            "--title", f"Hive UI {tag}",
            "--generate-notes",
            "--draft",
            "--target", "develop",
        ])


# ── compaction ────────────────────────────────────────────────────────────────
# Patterns that indicate a hallucinating model invented tasks rather than
# observing real hive state.  Used in compaction() and _startup_cleanup().
_HALLUCINATION_SIGNALS = (
    "champion", "integration test", "documentation",
    "compute resource", "allocate", "provision",
)


def compaction():
    """LLM reads full hive state, writes goal/summary/next-steps to orchestrator_sessions ring."""
    s = hive_status.load()

    # Build a concise context snapshot
    open_blockers  = [b for b in s.get("blockers", []) if b.get("status") == "open"]
    pending_steps  = [n for n in s.get("next_steps", []) if n.get("status") == "pending"]
    caps           = [c.get("title") or c.get("skill", "?") for c in
                      s.get("capabilities", {}).get("learned", [])[:8]]
    hives_summary  = {n: f"{d.get('status')} h={d.get('health_score',0):.0%}"
                      for n, d in s.get("hives", {}).items()}
    sessions       = tmux_sessions()
    achievements   = [a.get("description", "") for a in s.get("achievements", [])[-5:]]

    context = f"""## Hive State Snapshot — {_now_iso()}

Active sessions: {sessions}
Hive health: {hives_summary}
Model: {OPENROUTER_MODEL}

Open blockers ({len(open_blockers)}):
{chr(10).join(f'  [{b["severity"]}] {b["description"][:80]}' for b in open_blockers[:5]) or "  none"}

Pending next steps ({len(pending_steps)}):
{chr(10).join(f'  P{n.get("priority",5)} {n["description"][:70]}' for n in pending_steps[:5]) or "  none"}

Recent achievements:
{chr(10).join(f'  - {a[:70]}' for a in achievements) or "  none"}

Learned capabilities: {caps}

Knowledge findings: {s.get("knowledge", {}).get("findings_count", len(s.get("knowledge",{}).get("findings",[])))}
"""

    system = (
        "You are an autonomous hive orchestrator. Given the current hive state, produce a JSON "
        "compaction summary with exactly these fields:\n"
        '  "goal": current one-line objective,\n'
        '  "summary": 2-3 sentence status,\n'
        '  "progress": what was completed recently (1 sentence),\n'
        '  "next_steps": list of up to 5 concrete action strings,\n'
        '  "decisions": list of up to 3 key decision strings.\n'
        "Return ONLY valid JSON. No markdown fences. No preamble."
    )

    _log("running compaction (LLM)...")
    text, err = call_llm(
        [{"role": "system", "content": system},
         {"role": "user",   "content": context}],
        max_tokens=600,
        timeout=30,
    )

    if err:
        _log(f"compaction LLM error: {err}")
        # Deduplicate: only add a new blocker if no open compaction-failure blocker exists
        _es = hive_status.load()
        _has_open_fail = any(
            b.get("status") == "open"
            and b.get("agent") == "orchestrator"
            and b.get("description", "").startswith("Compaction LLM failed")
            for b in _es.get("blockers", [])
        )
        if not _has_open_fail:
            hive_status.add_blocker(
                HIVE_NAME, "orchestrator",
                f"Compaction LLM failed: {err}",
                severity="low",
            )
        # Still store a minimal no-LLM compaction so the ring isn't empty
        hive_status.update_orchestrator_session(
            summary  = f"Compaction skipped — LLM unavailable: {err}",
            goal     = s.get("hives", {}).get("default", {}).get("current_goal", ""),
            progress = "",
            next_steps = [n["description"] for n in pending_steps[:5]],
            decisions  = [],
            updated_by = "orchestrator",
        )
        return

    # Parse JSON from LLM response
    try:
        # Strip any accidental markdown fences
        clean = text.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            inner = [l for l in lines[1:] if not l.strip().startswith("```")]
            clean = "\n".join(inner)
        result = json.loads(clean)
    except Exception:
        # Fallback: extract what we can
        _log(f"compaction parse failed, raw: {text[:120]}")
        result = {
            "goal":       s.get("hives", {}).get("default", {}).get("current_goal", ""),
            "summary":    text[:300],
            "progress":   "",
            "next_steps": [n["description"] for n in pending_steps[:5]],
            "decisions":  [],
        }

    hive_status.update_orchestrator_session(
        summary    = result.get("summary", ""),
        goal       = result.get("goal", ""),
        progress   = result.get("progress", ""),
        next_steps = result.get("next_steps", [])[:5],
        decisions  = result.get("decisions", [])[:3],
        updated_by = "orchestrator",
    )

    # Auto-resolve all open compaction-failure blockers — LLM is healthy again
    _rs = hive_status.load()
    for _rb in _rs.get("blockers", []):
        if (
            _rb.get("status") == "open"
            and _rb.get("agent") == "orchestrator"
            and _rb.get("description", "").startswith("Compaction LLM failed")
        ):
            hive_status.resolve_blocker(
                _rb["id"], "Compaction succeeded", updated_by="orchestrator"
            )
            _log(f"auto-resolved stale blocker {_rb['id']}")

    # Only write LLM-suggested steps when pending queue is empty AND
    # none of the steps match known hallucination patterns from broken models
    if not pending_steps and result.get("next_steps"):
        clean_steps = [
            d for d in result["next_steps"][:3]
            if not any(sig in d.lower() for sig in _HALLUCINATION_SIGNALS)
        ]
        for i, desc in enumerate(clean_steps):
            hive_status.add_next_step(
                description = desc,
                priority    = i + 1,
                assigned_to = HIVE_NAME,
                source      = "orchestrator",
                updated_by  = "orchestrator",
            )

    _log(f"compaction stored — goal: {result.get('goal','')[:60]}")


# ── startup cleanup ───────────────────────────────────────────────────────────
def _startup_cleanup():
    """
    Called once at startup.
    1. Resolves all open compaction-failure blockers (model is being switched/restarted).
    2. Cancels hallucinated pending next_steps injected by a broken orchestrator model.
    This ensures every restart leaves the hive in a cleaner state than before.
    """
    s = hive_status.load()

    # Resolve stale compaction-failure blockers
    resolved = 0
    for b in s.get("blockers", []):
        if (
            b.get("status") == "open"
            and b.get("agent") == "orchestrator"
            and b.get("description", "").startswith("Compaction LLM failed")
        ):
            hive_status.resolve_blocker(
                b["id"],
                "Resolved at startup — orchestrator restarted with new model",
                updated_by="orchestrator",
            )
            _log(f"startup: resolved stale blocker {b['id']}")
            resolved += 1

    # Cancel hallucinated next_steps from orchestrator source
    s = hive_status.load()  # reload after blocker changes
    cancelled = 0
    for n in s.get("next_steps", []):
        if (
            n.get("status") == "pending"
            and n.get("source") == "orchestrator"
            and any(sig in n.get("description", "").lower() for sig in _HALLUCINATION_SIGNALS)
        ):
            hive_status.update_next_step(n["id"], "done", updated_by="orchestrator")
            _log(f"startup: cancelled hallucinated step {n['id']}: "
                 f"{n.get('description','')[:60]}")
            cancelled += 1

    if resolved or cancelled:
        _log(f"startup cleanup: {resolved} blockers resolved, {cancelled} steps cancelled")


# ── main loop ─────────────────────────────────────────────────────────────────
def main():
    _log(f"starting — model={OPENROUTER_MODEL} key={'set' if OPENROUTER_KEY else 'MISSING'}")
    _log("hive is live · running autonomously · never stopping")
    _startup_cleanup()

    last_heartbeat  = 0.0
    last_compaction = 0.0
    last_triage     = 0.0
    last_self_test  = 0.0
    last_gitops     = 0.0
    last_promote    = 0.0

    while True:
        now = time.time()

        # ── heartbeat ─────────────────────────────────────────────────────────
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            s = hive_status.load()
            h = s.get("hives", {}).get("default", {})
            open_b  = sum(1 for b in s.get("blockers", []) if b.get("status") == "open")
            pending = sum(1 for n in s.get("next_steps", []) if n.get("status") == "pending")
            sessions_alive = tmux_sessions()

            # Compute real health score from live session state
            # = fraction of CRITICAL_SESSIONS that exist AND have a child process
            alive_count = sum(
                1 for sess in CRITICAL_SESSIONS
                if sess in sessions_alive and session_is_alive(sess)
            )
            live_health = alive_count / max(len(CRITICAL_SESSIONS), 1)
            # Apply open-blocker penalty: each critical blocker shaves 5%
            critical_blockers = sum(
                1 for b in s.get("blockers", [])
                if b.get("status") == "open" and b.get("severity") in ("critical", "high")
            )
            live_health = max(0.0, live_health - critical_blockers * 0.05)

            _log(
                f"HEARTBEAT | sessions={len(sessions_alive)} "
                f"| health={live_health:.0%} "
                f"| blockers={open_b} | next_steps={pending} "
                f"| model={OPENROUTER_MODEL.split('/')[-1]}"
            )
            # Sync active model, sessions, and live health into hive-status
            hive_status.update_hive_health(
                hive_name   = HIVE_NAME,
                sessions    = sessions_alive,
                status      = h.get("status", "running"),
                health_score= live_health,
                current_goal= h.get("current_goal", ""),
                active_model= OPENROUTER_MODEL,
                errors_last_hour = h.get("errors_last_hour", 0),
                silent_minutes   = 0,
                updated_by  = "orchestrator",
            )
            # Show heartbeat in the active-task bar so it's never permanently IDLE
            hive_status.set_active_task(
                "orchestrator",
                f"heartbeat · sessions={len(sessions_alive)} health={live_health:.0%}"
                f" blockers={open_b}",
            )
            hive_status.clear_active_task()
            last_heartbeat = now

        # ── triage ────────────────────────────────────────────────────────────
        if now - last_triage >= TRIAGE_INTERVAL:
            with _doing("triage: checking sessions + service health"):
                try:
                    triage()
                    _watch_research_loop_errors()
                    _prune_stale_status_entries()
                except Exception as e:
                    _log(f"triage error (non-fatal): {e}")
            last_triage = now

        # ── compaction ────────────────────────────────────────────────────────
        if now - last_compaction >= COMPACTION_INTERVAL:
            with _doing("compaction: LLM summarising hive state"):
                try:
                    compaction()
                except Exception as e:
                    _log(f"compaction error (non-fatal): {e}")
            last_compaction = now

        # ── self-test ─────────────────────────────────────────────────────────
        if now - last_self_test >= SELF_TEST_INTERVAL:
            with _doing("self-test: running test_system.sh + auto-fix"):
                try:
                    self_test()
                except Exception as e:
                    _log(f"self-test error (non-fatal): {e}")

                # Issue→test pipeline: scan recent blockers for novel patterns
                try:
                    hive_status.set_active_task("orchestrator", "issue→test: scanning blockers for new test patterns")
                    s = hive_status.load()
                    for b in s.get("blockers", [])[-20:]:
                        if b.get("status") == "open":
                            _issue_to_test(b.get("description", ""))
                except Exception as e:
                    _log(f"issue→test error (non-fatal): {e}")
            last_self_test = now

        # ── GitOps: PR status poll + auto-merge ───────────────────────────────
        if now - last_gitops >= GITOPS_INTERVAL:
            with _doing("gitops: polling open PRs — auto-merge if CI green"):
                try:
                    _poll_open_prs()
                except Exception as e:
                    _log(f"gitops poll error (non-fatal): {e}")
            last_gitops = now

        # ── develop → main promotion check ────────────────────────────────────
        if now - last_promote >= PROMOTE_INTERVAL:
            with _doing("gitops: develop→main promotion check + release draft"):
                try:
                    _develop_to_main_pr()
                except Exception as e:
                    _log(f"promote error (non-fatal): {e}")
            last_promote = now

        # ── watchdog file — written every tick so supervisor can detect hangs ──
        # If THIS line stops updating, the main loop itself is stuck.
        try:
            with open("/tmp/orchestrator.watchdog", "w") as _wf:
                _wf.write(f"{now:.0f}\n")
        except Exception:
            pass

        time.sleep(10)   # base tick — tight loop would waste CPU


if __name__ == "__main__":
    main()
