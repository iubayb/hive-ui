#!/usr/bin/env bash
# status-push.sh — push hive-status.json (and optional report) to status/ branch
# Uses GitHub Contents API via a temp JSON payload file to avoid ARG_MAX limits
# Safe to call from any working directory; never touches git working tree
set -euo pipefail

STATUS_FILE="${STATUS_FILE:-/tmp/hive-status.json}"
REPORT_FILE="${REPORT_FILE:-/home/ayoub/research/wegia-audit.md}"
REPO="iubayb/hive-ui"
BRANCH="status"

push_file() {
  local local_path="$1"
  local remote_path="$2"
  local msg="$3"
  [ -f "$local_path" ] || { echo "[status-push] skip $remote_path (not found)"; return 0; }

  python3 - "$local_path" "$remote_path" "$msg" "$REPO" "$BRANCH" << 'PYEOF'
import sys, json, base64, subprocess, os, tempfile
local_path, remote_path, msg, repo, branch = sys.argv[1:]

# Get current SHA
r = subprocess.run(
    ["gh", "api", f"repos/{repo}/contents/{remote_path}?ref={branch}", "--jq", ".sha"],
    capture_output=True, text=True
)
sha = r.stdout.strip()

# Build payload and write to temp file (avoids ARG_MAX / Argument list too long)
payload = {
    "message": msg,
    "content": base64.b64encode(open(local_path, "rb").read()).decode(),
    "branch": branch,
}
if sha:
    payload["sha"] = sha

with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    json.dump(payload, f)
    tmp = f.name

try:
    r2 = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{remote_path}",
         "--method", "PUT", "--input", tmp],
        capture_output=True, text=True
    )
    if r2.returncode != 0:
        print(f"[status-push] ERROR {remote_path}: {r2.stderr[:200]}", file=sys.stderr)
        sys.exit(1)
    print(f"[status-push] pushed {remote_path}")
finally:
    os.unlink(tmp)
PYEOF
}

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
push_file "$STATUS_FILE" "hive-status.json" "chore: status sync $TS"
push_file "$REPORT_FILE" "research/latest.md" "chore: report sync $TS"
echo "[status-push] done at $TS"
