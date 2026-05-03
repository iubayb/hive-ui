#!/usr/bin/env bash
# Self-healing build monitor.
# Loops forever: idles between builds, auto-monitors each new PS5 Kernel Build
# end-to-end (kernel → image → release). Crashes are caught by the tmux wrapper.

# GH_TOKEN loaded from env or gh CLI — never hardcode
REPO=iubayb/ps5_bazzite
LOG=/tmp/build_monitor.log
STATE_FILE=/tmp/build_monitor_last_run   # persists last-seen run ID across restarts

POLL_IDLE=60     # seconds between idle polls
POLL_BUILD=60    # seconds between kernel-build status checks
POLL_IMAGE=30    # seconds between image-build status checks

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# ── helpers ───────────────────────────────────────────────────────────────────

latest_kernel_run() {
  gh run list --repo "$REPO" --workflow "PS5 Kernel Build" --limit 1 \
    --json databaseId,status,conclusion \
    -q '.[0] | "\(.databaseId)|\(.status)|\(.conclusion)"' 2>/dev/null || echo ""
}

run_status() {
  local run_id="$1"
  gh run view "$run_id" --repo "$REPO" --json status,conclusion \
    -q '[.status,.conclusion] | join("|")' 2>/dev/null || echo "unknown|"
}

# ── phase 1: watch kernel ─────────────────────────────────────────────────────

watch_kernel() {
  local run_id="$1"
  log "PHASE 1: Watching kernel build $run_id ..."
  while true; do
    local result status conclusion
    result=$(run_status "$run_id")
    status="${result%%|*}"; conclusion="${result##*|}"
    log "  kernel[$run_id] status=$status conclusion=$conclusion"
    if [[ "$status" == "completed" ]]; then
      if [[ "$conclusion" == "success" ]]; then
        log "KERNEL BUILD SUCCEEDED"; return 0
      else
        log "KERNEL BUILD FAILED (conclusion=$conclusion)"
        gh run view "$run_id" --repo "$REPO" --log-failed 2>&1 \
          | tail -40 | tee -a "$LOG" || true
        return 1
      fi
    fi
    sleep "$POLL_BUILD"
  done
}

# ── phase 2+3: find & watch image ────────────────────────────────────────────

watch_image() {
  log "PHASE 2: Looking for image build ..."
  local image_run=""
  for attempt in $(seq 1 20); do
    image_run=$(gh run list --repo "$REPO" --workflow "PS5 Bazzite Image Build" --limit 5 \
      --json databaseId,createdAt \
      -q 'sort_by(.createdAt) | reverse | .[0].databaseId | tostring' 2>/dev/null || echo "")
    if [[ -n "$image_run" && "$image_run" != "null" ]]; then
      log "  Found image run: $image_run"; break
    fi
    log "  Waiting for image run (attempt $attempt/20) ..."
    sleep 30
  done

  if [[ -z "$image_run" || "$image_run" == "null" ]]; then
    log "ERROR: image build never appeared"; return 1
  fi

  log "PHASE 3: Watching image build $image_run ..."
  while true; do
    local result status conclusion
    result=$(run_status "$image_run")
    status="${result%%|*}"; conclusion="${result##*|}"
    log "  image[$image_run] status=$status conclusion=$conclusion"
    if [[ "$status" == "completed" ]]; then
      if [[ "$conclusion" == "success" ]]; then
        log "IMAGE BUILD SUCCEEDED"; return 0
      else
        log "IMAGE BUILD FAILED (conclusion=$conclusion)"
        gh run view "$image_run" --repo "$REPO" --log-failed 2>&1 \
          | tail -40 | tee -a "$LOG" || true
        return 1
      fi
    fi
    sleep "$POLL_IMAGE"
  done
}

# ── phase 4: verify release ───────────────────────────────────────────────────

verify_release() {
  log "PHASE 4: Verifying GitHub Release ..."
  sleep 30   # allow release action to create the tag
  local tag
  tag=$(gh release list --repo "$REPO" --limit 1 --json tagName \
    -q '.[0].tagName' 2>/dev/null || echo "")
  log "  Latest release tag: $tag"
  if [[ "$tag" == kernel-v* ]]; then
    local assets
    assets=$(gh release view "$tag" --repo "$REPO" --json assets \
      -q '.assets[].name' 2>/dev/null || echo "")
    log "  Release assets:"
    while IFS= read -r a; do [[ -n "$a" ]] && log "    - $a"; done <<< "$assets"
    log "=== PIPELINE FULLY SUCCESSFUL === tag=$tag"
  else
    log "WARNING: unexpected release tag: ${tag:-(none)}"
  fi
}

# ── main idle/watch loop ──────────────────────────────────────────────────────

LAST_SEEN_RUN=""
[[ -f "$STATE_FILE" ]] && LAST_SEEN_RUN=$(cat "$STATE_FILE" 2>/dev/null || echo "")

log "=== Build Monitor (self-healing) started. Last seen: ${LAST_SEEN_RUN:-none} ==="

while true; do
  raw=$(latest_kernel_run)
  if [[ -z "$raw" ]]; then
    log "[idle] Could not fetch workflow list — retrying in ${POLL_IDLE}s ..."
    sleep "$POLL_IDLE"; continue
  fi

  run_id="${raw%%|*}"
  rest="${raw#*|}"; status="${rest%%|*}"; conclusion="${rest##*|}"

  if [[ "$run_id" == "$LAST_SEEN_RUN" ]]; then
    log "[idle] No new kernel run (last=$run_id status=$status). Next poll in ${POLL_IDLE}s ..."
    sleep "$POLL_IDLE"; continue
  fi

  # New run detected
  log ""
  log "=== NEW KERNEL RUN: $run_id (status=$status conclusion=$conclusion) ==="
  echo "$run_id" > "$STATE_FILE"
  LAST_SEEN_RUN="$run_id"

  if [[ "$status" == "completed" ]]; then
    if [[ "$conclusion" == "success" ]]; then
      log "Kernel already succeeded — jumping to image watch ..."
      watch_image && verify_release || log "PIPELINE INCOMPLETE"
    else
      log "Kernel already finished with conclusion=$conclusion — skipping ..."
    fi
  else
    watch_kernel "$run_id" && watch_image && verify_release || log "PIPELINE INCOMPLETE"
  fi

  log "=== Cycle done. Polling for next build in ${POLL_IDLE}s ... ==="
  log ""
  sleep "$POLL_IDLE"
done
