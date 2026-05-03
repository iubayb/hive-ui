#!/usr/bin/env bash
# tests/run_all.sh — Single entry point for entire test suite
#
# Runs all suites in order:
#   1. test_system.sh      — TS1-TS21  (bash, system invariants, ~5s)
#   2. test_all.js         — T1-T44    (Playwright, core API + UI)
#   3. test_extended.js    — T41-T70   (Playwright, extended checks)
#   4. test_ui_inheritance.js — TUI1-TUI20 (Playwright, UI inheritance)
#   5. test_new_features.js — T71-T94  (Playwright, new features)
#   6. tests/learned/*.sh  — auto-generated from incidents (if any)
#
# Usage:
#   bash tests/run_all.sh [--port 8889] [--no-system] [--system-only]
#
# Exit code: 0 if ALL suites pass, 1 if any fail.
# Output: prints each suite's results; summary at end.

set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8889}"
RUN_SYSTEM=1
RUN_JS=1

# ── arg parsing ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)         PORT="$2"; shift 2 ;;
        --no-system)    RUN_SYSTEM=0; shift ;;
        --system-only)  RUN_JS=0; shift ;;
        --port=*)       PORT="${1#--port=}"; shift ;;
        *) shift ;;
    esac
done

export PORT

log()  { echo "[run_all] $*"; }
pass() { echo "  [SUITE PASS] $*"; }
fail() { echo "  [SUITE FAIL] $*"; }

total_suites=0
failed_suites=0
declare -a failed_suite_names=()

run_suite() {
    local name="$1"; shift
    total_suites=$(( total_suites + 1 ))
    echo ""
    echo "══════════════════════════════════════════════════════════"
    echo " Suite: $name"
    echo "══════════════════════════════════════════════════════════"
    if "$@"; then
        pass "$name"
    else
        fail "$name"
        failed_suites=$(( failed_suites + 1 ))
        failed_suite_names+=("$name")
    fi
}

cd "$HIVE_DIR"

# ── 1. System invariants (bash) ───────────────────────────────────────────────
if [[ "$RUN_SYSTEM" -eq 1 ]]; then
    run_suite "test_system.sh (TS1-TS21)" \
        bash tests/test_system.sh
fi

# ── 2–5. Playwright suites ────────────────────────────────────────────────────
if [[ "$RUN_JS" -eq 1 ]]; then
    # Verify server is up before running JS suites
    if ! curl -sf --max-time 5 "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
        log "ERROR: dev server not responding on port $PORT — start hive-dev first"
        log "  tmux send-keys -t hive-dev 'cd $HIVE_DIR && PORT=$PORT python3 logstream.py' ENTER"
        exit 1
    fi

    run_suite "test_all.js (T1-T44)" \
        node tests/test_all.js

    run_suite "test_extended.js (T41-T70)" \
        node tests/test_extended.js

    run_suite "test_ui_inheritance.js (TUI1-TUI20)" \
        node tests/test_ui_inheritance.js

    run_suite "test_new_features.js (T71-T94)" \
        node tests/test_new_features.js

    # ── 6. Auto-generated tests from incidents ────────────────────────────────
    LEARNED_DIR="$HIVE_DIR/tests/learned"
    if [[ -d "$LEARNED_DIR" ]]; then
        shopt -s nullglob
        learned_tests=("$LEARNED_DIR"/*.sh)
        shopt -u nullglob
        for t in "${learned_tests[@]}"; do
            run_suite "learned/$(basename "$t")" bash "$t"
        done
    fi
fi

# ── Final summary ─────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════"
echo " TOTAL: $((total_suites - failed_suites))/$total_suites suites passed"
if [[ ${#failed_suite_names[@]} -gt 0 ]]; then
    echo " FAILED: ${failed_suite_names[*]}"
fi
echo "══════════════════════════════════════════════════════════"

[[ "$failed_suites" -eq 0 ]]
