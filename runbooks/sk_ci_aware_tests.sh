#!/usr/bin/env bash
# runbook_sk_ci_aware_tests.sh
# Capability: sk_ci_aware_tests (Tests must not require local files absent in CI)
# Problem:    Tests that fatal/exit on missing .env.local or similar local-only
#             files break CI while passing locally
# Fix:        Auto-create stub for missing env files in test setup
# Idempotent: only creates stub if file is absent

set -euo pipefail
HIVE_UI="/home/ayoub/hive-ui"

detect() {
    # Check if any test files have hard exits on missing .env files
    if grep -rn "exit 1\|sys.exit" "$HIVE_UI"/*.py 2>/dev/null | grep -q "env\|\.env\|config"; then
        echo "DETECT: potential hard exit on missing env in test files"; return 1
    fi
    echo "DETECT: OK — no hard exits on missing env files found"; return 0
}

apply_stub() {
    local target="${1:-.env.local}"
    if [ ! -f "$target" ]; then
        echo "# Auto-generated stub for CI — replace with real values locally" > "$target"
        echo "OPENROUTER_API_KEY=stub" >> "$target"
        echo "Created stub: $target"
    fi
}

detect || {
    echo "WARNING: Consider adding env file stubs for CI compatibility"
    echo "Run: apply_stub .env.local  (defined in this script)"
}
echo "CI test compatibility check complete."
