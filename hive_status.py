#!/usr/bin/env python3
"""
hive_status.py — Centralized Knowledge Base for the Hive UI.

Manages /tmp/hive-status.json (local working copy).
Syncs to/from a configured GitHub repo via gh CLI.
Also writes /tmp/hive-status.md (human-readable summary) on every save.

Public API:
  load()                          → dict
  save(status)                    → None
  get_or_create()                 → dict
  add_achievement(hive, agent, description, evidence)
  add_blocker(hive, agent, description, severity)
  resolve_blocker(blocker_id, resolution)
  add_capability(source_hive, source_agent, skill, description, example, tags)
  add_next_step(description, assigned_to, priority, source)
  update_next_step(step_id, status)
  add_finding(hive, summary, source)
  add_solution(problem, solution, hive, verified)
  update_hive_health(hive_name, sessions, status, health_score, **kwargs)
  update_model_champions(text=None, vision=None)
  increment_metric(key, amount)
  merge_remote(remote_dict)       → merged dict
  build_capability_prompt()       → markdown string for system prompts
  build_context_block(max_chars)  → structured context string for LLM injection
  get_broadcast_payload()         → compact dict safe to SSE-broadcast
  push_to_github(repo)
  pull_from_github(repo)          → remote dict or None
  add_question(hive, agent, question, hint, type_, choices, required)  → id
  answer_question(question_id, answer, answered_by)
  get_pending_questions(unanswered_only)  → list
  update_orchestrator_session(summary, goal, progress, next_steps, decisions)
  update_deployment(vercel_url, vercel_project, status)
  add_researcher(handle, platform, keywords, context, priority_repos)
  get_tracked_researchers()       → list
  remove_researcher(handle)

CLI:
  python3 hive_status.py --summary    → concise orchestrator status view
  python3 hive_status.py --compact    → print build_context_block() output
"""

import json, os, subprocess, threading, time, uuid

STATUS_FILE   = "/tmp/hive-status.json"
_status_lock  = threading.Lock()
_sse_listeners: list = []          # list of queue.Queue objects
_sse_lock     = threading.Lock()

# ── GitHub Issues integration (single call site — never scattered) ────────────
_GITHUB_REPO = os.environ.get("HIVE_GITHUB_REPO", "iubayb/hive-ui")


def _gh_issue_create(title: str, body: str, labels: list[str]) -> int | None:
    """Fire-and-forget: open a GitHub Issue. Returns issue number or None."""
    try:
        label_args = []
        for lb in labels:
            label_args += ["--label", lb]
        r = subprocess.run(
            ["gh", "issue", "create",
             "--repo", _GITHUB_REPO,
             "--title", title[:255],
             "--body", body[:65535]] + label_args,
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            # Output is the issue URL; parse number from it
            url = r.stdout.strip()
            try:
                return int(url.rstrip("/").split("/")[-1])
            except (ValueError, IndexError):
                return None
    except Exception:
        pass
    return None


def _gh_issue_close(issue_number: int, comment: str) -> None:
    """Fire-and-forget: close a GitHub Issue with a closing comment."""
    try:
        subprocess.run(
            ["gh", "issue", "close", str(issue_number),
             "--repo", _GITHUB_REPO,
             "--comment", comment[:65535]],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        pass

# ── schema factory ────────────────────────────────────────────────────────────

def _empty_status() -> dict:
    return {
        "schema_version":  "1.0",
        "last_updated":    _now(),
        "updated_by":      "system",
        "hives":           {},
        "achievements":    [],
        "blockers":        [],
        "next_steps":      [],
        "capabilities":    {"learned": []},
        "knowledge":       {"findings": [], "patterns": [], "solutions": []},
        "metrics": {
            "tasks_completed_total": 0,
            "tasks_failed_total":    0,
            "avg_task_duration_s":   0,
            "model_usage":           {},
            "error_rate_24h":        0.0,
            "openrouter_calls_today": 0,
        },
        "model_champions":    {"text": None, "vision": None, "updated": None},
        "pending_questions":  [],
        "orchestrator_sessions": [],   # FIFO ring of last 10 compaction summaries
        "tracked_researchers":   [],   # config-driven external researcher monitors
        "deployment": {
            "vercel_url":    None,
            "vercel_project": None,
            "deployed_at":   None,
            "status":        "pending",
        },
        "active_task": None,   # {agent, task, started_at} — what's running RIGHT NOW
    }

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# ── load / save ───────────────────────────────────────────────────────────────

def load() -> dict:
    try:
        with open(STATUS_FILE) as f:
            data = json.load(f)
        # Migrate missing keys
        empty = _empty_status()
        for k, v in empty.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return _empty_status()

def save(status: dict, updated_by: str = "system"):
    status["last_updated"] = _now()
    status["updated_by"]   = updated_by
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)
    except Exception:
        pass
    _write_readme(status)
    _broadcast(status)

def get_or_create() -> dict:
    with _status_lock:
        s = load()
        if s.get("schema_version") != "1.0":
            s = _empty_status()
            save(s)
        return s

# ── README sync ───────────────────────────────────────────────────────────────

README_FILE = "/tmp/hive-status.md"

def _write_readme(status: dict):
    """Write a human-readable markdown summary of the current status."""
    try:
        lines = [
            f"# Hive Status",
            f"_Updated: {status.get('last_updated', '?')} by {status.get('updated_by', '?')}_",
            "",
        ]

        # Hives
        hives = status.get("hives", {})
        if hives:
            lines.append("## Hives")
            for name, d in hives.items():
                score = d.get("health_score", "?")
                stat  = d.get("status", "?")
                lines.append(f"- **{name}**: {stat} (health {score})")
            lines.append("")

        # Model champions
        ch = status.get("model_champions", {})
        if ch.get("text") or ch.get("vision"):
            lines.append("## Model Champions")
            if ch.get("text"):
                lines.append(f"- text: `{ch['text']}`")
            if ch.get("vision"):
                lines.append(f"- vision: `{ch['vision']}`")
            lines.append("")

        # Active blockers
        open_b = [b for b in status.get("blockers", []) if b.get("status") == "open"]
        if open_b:
            lines.append("## Active Blockers")
            for b in open_b[:10]:
                lines.append(f"- [{b.get('severity','?')}] {b['description'][:100]}")
            lines.append("")

        # Pending next steps
        pending = [ns for ns in status.get("next_steps", []) if ns.get("status") == "pending"]
        if pending:
            lines.append("## Pending Next Steps")
            for ns in pending[:10]:
                lines.append(f"- P{ns.get('priority',5)} {ns['description'][:90]}")
            lines.append("")

        # Unanswered questions
        unanswered = [q for q in status.get("pending_questions", []) if not q.get("answered")]
        if unanswered:
            lines.append("## Unanswered Questions")
            for q in unanswered[:5]:
                lines.append(f"- [{q['id']}] {q['question'][:90]}")
            lines.append("")

        # Tracked researchers
        researchers = status.get("tracked_researchers", [])
        if researchers:
            lines.append("## Tracked Researchers")
            for r in researchers:
                lines.append(f"- {r.get('handle')} ({r.get('platform','github')})")
            lines.append("")

        # Deployment
        dep = status.get("deployment", {})
        if dep.get("vercel_url"):
            lines.append("## Deployment")
            lines.append(f"- URL: {dep['vercel_url']} [{dep.get('status','?')}]")
            lines.append("")

        # Metrics
        m = status.get("metrics", {})
        lines.append("## Metrics")
        lines.append(f"- Tasks completed: {m.get('tasks_completed_total', 0)}")
        lines.append(f"- OpenRouter calls today: {m.get('openrouter_calls_today', 0)}")
        lines.append("")

        with open(README_FILE, "w") as f:
            f.write("\n".join(lines))
    except Exception:
        pass

# ── SSE broadcast ─────────────────────────────────────────────────────────────

def register_sse_listener(q):
    with _sse_lock:
        _sse_listeners.append(q)

def unregister_sse_listener(q):
    with _sse_lock:
        try:
            _sse_listeners.remove(q)
        except ValueError:
            pass

def _broadcast(status: dict):
    payload = get_broadcast_payload(status)
    msg = json.dumps(payload)
    with _sse_lock:
        dead = []
        for q in _sse_listeners:
            try:
                q.put_nowait(msg)
            except Exception:
                dead.append(q)
        for q in dead:
            try:
                _sse_listeners.remove(q)
            except ValueError:
                pass

def broadcast_current():
    """Broadcast current saved status to all SSE listeners."""
    with _status_lock:
        _broadcast(load())

# ── writers ───────────────────────────────────────────────────────────────────

def add_achievement(hive: str, agent: str, description: str,
                    evidence: str = "", updated_by: str = "agent"):
    with _status_lock:
        s = load()
        s["achievements"].insert(0, {
            "id":          _uid("a"),
            "ts":          _now(),
            "hive":        hive,
            "agent":       agent,
            "description": description,
            "evidence":    evidence,
        })
        s["achievements"] = s["achievements"][:50]   # cap at 50
        save(s, updated_by)


def add_blocker(hive: str, agent: str, description: str,
                severity: str = "medium", updated_by: str = "agent") -> str:
    bid = _uid("b")
    blocker = {
        "id":           bid,
        "ts":           _now(),
        "hive":         hive,
        "agent":        agent,
        "description":  description,
        "severity":     severity,
        "status":       "open",
        "resolved_at":  None,
        "resolution":   None,
        "github_issue": None,   # filled in by background thread on success
    }
    with _status_lock:
        s = load()
        s["blockers"].insert(0, blocker)
        s["blockers"] = s["blockers"][:100]
        save(s, updated_by)

    # Mirror to GitHub Issues asynchronously — never blocks the caller
    def _open_issue():
        num = _gh_issue_create(
            title=f"[{severity.upper()}] {description[:120]}",
            body=(
                f"**Hive:** {hive}  \n"
                f"**Agent:** {agent}  \n"
                f"**Severity:** {severity}  \n"
                f"**Description:** {description}\n\n"
                f"_Auto-created by hive_status.add_blocker · id={bid}_"
            ),
            labels=["blocker", severity],
        )
        if num:
            # Patch the issue number back into the saved status
            with _status_lock:
                s2 = load()
                for b in s2["blockers"]:
                    if b["id"] == bid:
                        b["github_issue"] = num
                        break
                save(s2, "hive_status")

    t = threading.Thread(target=_open_issue, daemon=True)
    t.start()
    return bid


def resolve_blocker(blocker_id: str, resolution: str = "",
                    updated_by: str = "agent"):
    github_issue = None
    with _status_lock:
        s = load()
        for b in s["blockers"]:
            if b["id"] == blocker_id:
                b["status"]      = "resolved"
                b["resolved_at"] = _now()
                b["resolution"]  = resolution
                github_issue     = b.get("github_issue")
                break
        save(s, updated_by)

    # Mirror to GitHub Issues asynchronously
    if github_issue:
        comment = f"Resolved: {resolution}" if resolution else "Resolved automatically by hive."
        t = threading.Thread(
            target=_gh_issue_close, args=(github_issue, comment), daemon=True
        )
        t.start()


# ── active task tracking (real-time "what is running right NOW") ──────────────

def set_active_task(agent: str, task: str, updated_by: str = "agent") -> None:
    """
    Record what the orchestrator is executing at this instant.
    Writes to hive-status.json and broadcasts via SSE immediately.
    Call at the START of every significant work unit.
    """
    with _status_lock:
        s = load()
        s["active_task"] = {
            "agent":      agent,
            "task":       task,
            "status":     "running",
            "started_at": _now(),
            "completed_at": None,
        }
        save(s, updated_by)


def clear_active_task(updated_by: str = "agent") -> None:
    """Call at the END (or on error) of every work unit."""
    with _status_lock:
        s = load()
        prev = s.get("active_task") or {}
        s["active_task"] = {
            "agent":        prev.get("agent", ""),
            "task":         prev.get("task", ""),
            "status":       "completed",
            "started_at":   prev.get("started_at", ""),
            "completed_at": _now(),
        }
        save(s, updated_by)


def add_capability(source_hive: str, source_agent: str, skill: str,
                   description: str, example: str = "",
                   tags: list = None, applicable_to: str = "all",
                   updated_by: str = "agent"):
    with _status_lock:
        s = load()
        # Deduplicate by skill slug
        existing_skills = {c.get("skill", c.get("title", "")) for c in s["capabilities"]["learned"]}
        if skill in existing_skills:
            # Update existing entry
            for c in s["capabilities"]["learned"]:
                if c.get("skill", c.get("title", "")) == skill:
                    c["description"]   = description
                    c["example"]       = example
                    c["tags"]          = tags or []
                    c["last_updated"]  = _now()
            save(s, updated_by)
            return
        s["capabilities"]["learned"].insert(0, {
            "id":            _uid("cap"),
            "ts":            _now(),
            "source_hive":   source_hive,
            "source_agent":  source_agent,
            "skill":         skill,
            "description":   description,
            "example":       example,
            "tags":          tags or [],
            "applicable_to": applicable_to,
        })
        s["capabilities"]["learned"] = s["capabilities"]["learned"][:200]
        save(s, updated_by)


def add_next_step(description: str, assigned_to: str = "hive-doctor",
                  priority: int = 5, source: str = "manual",
                  updated_by: str = "agent") -> str:
    nsid = _uid("ns")
    with _status_lock:
        s = load()
        s["next_steps"].append({
            "id":          nsid,
            "priority":    priority,
            "description": description,
            "assigned_to": assigned_to,
            "status":      "pending",
            "source":      source,
            "ts":          _now(),
        })
        s["next_steps"].sort(key=lambda x: x["priority"])
        s["next_steps"] = s["next_steps"][:50]
        save(s, updated_by)
    return nsid


def update_next_step(step_id: str, status: str,
                     updated_by: str = "agent"):
    with _status_lock:
        s = load()
        for ns in s["next_steps"]:
            if ns["id"] == step_id:
                ns["status"] = status
                break
        save(s, updated_by)


def add_finding(hive: str, summary: str, source: str = "observation",
                updated_by: str = "agent"):
    with _status_lock:
        s = load()
        s["knowledge"]["findings"].insert(0, {
            "id":      _uid("f"),
            "ts":      _now(),
            "hive":    hive,
            "summary": summary,
            "source":  source,
        })
        s["knowledge"]["findings"] = s["knowledge"]["findings"][:100]
        save(s, updated_by)


def add_solution(problem: str, solution: str, hive: str = "unknown",
                 verified: bool = False, updated_by: str = "agent"):
    with _status_lock:
        s = load()
        s["knowledge"]["solutions"].insert(0, {
            "id":       _uid("sol"),
            "ts":       _now(),
            "problem":  problem,
            "solution": solution,
            "hive":     hive,
            "verified": verified,
        })
        s["knowledge"]["solutions"] = s["knowledge"]["solutions"][:100]
        save(s, updated_by)


def update_hive_health(hive_name: str, sessions: list = None,
                       status: str = "unknown", health_score: float = 1.0,
                       current_goal: str = "", active_model: str = "",
                       errors_last_hour: int = 0,
                       tasks_completed_today: int = 0,
                       silent_minutes: int = 0,
                       updated_by: str = "hive-doctor"):
    with _status_lock:
        s = load()
        s["hives"][hive_name] = {
            "status":               status,
            "health_score":         round(health_score, 3),
            "last_seen":            _now(),
            "sessions":             sessions or [],
            "current_goal":         current_goal,
            "active_model":         active_model,
            "errors_last_hour":     errors_last_hour,
            "tasks_completed_today": tasks_completed_today,
            "silent_minutes":       silent_minutes,
        }
        save(s, updated_by)


def update_model_champions(text: str = None, vision: str = None,
                           updated_by: str = "model-arena"):
    with _status_lock:
        s = load()
        if text:
            s["model_champions"]["text"]    = text
        if vision:
            s["model_champions"]["vision"]  = vision
        s["model_champions"]["updated"]     = _now()
        save(s, updated_by)


def increment_metric(key: str, amount: int = 1,
                     updated_by: str = "system"):
    with _status_lock:
        s = load()
        m = s.setdefault("metrics", {})
        if key == "model_usage":
            raise ValueError("use increment_model_usage()")
        m[key] = m.get(key, 0) + amount
        save(s, updated_by)


def increment_model_usage(model_id: str, updated_by: str = "system"):
    with _status_lock:
        s = load()
        usage = s.setdefault("metrics", {}).setdefault("model_usage", {})
        usage[model_id] = usage.get(model_id, 0) + 1
        save(s, updated_by)

# ── merge (cross-hive) ────────────────────────────────────────────────────────

def merge_remote(remote: dict) -> dict:
    """
    Merge a remote status dict into local, combining all list fields.
    Local wins on scalar fields; lists are union-merged by id.
    Returns merged dict (does NOT save — caller decides).
    """
    if not isinstance(remote, dict):
        return load()
    local = load()

    def _merge_list(local_list: list, remote_list: list) -> list:
        seen = {item["id"] for item in local_list if "id" in item}
        merged = list(local_list)
        for item in remote_list:
            if item.get("id") not in seen:
                merged.append(item)
                seen.add(item.get("id"))
        return merged

    # Merge hives (remote fills gaps, local wins on existing keys)
    for hname, hdata in remote.get("hives", {}).items():
        if hname not in local["hives"]:
            local["hives"][hname] = hdata

    # Merge list fields
    for key in ("achievements", "blockers", "next_steps"):
        local[key] = _merge_list(local.get(key, []), remote.get(key, []))

    # Merge capabilities
    local_caps = local.setdefault("capabilities", {"learned": []})
    remote_caps = remote.get("capabilities", {}).get("learned", [])
    local_caps["learned"] = _merge_list(local_caps["learned"], remote_caps)

    # Merge knowledge sub-lists
    for sub in ("findings", "patterns", "solutions"):
        local["knowledge"][sub] = _merge_list(
            local["knowledge"].get(sub, []),
            remote.get("knowledge", {}).get(sub, [])
        )

    # Merge model champions (take whichever is more recent)
    remote_champs = remote.get("model_champions", {})
    local_champs  = local.setdefault("model_champions", {})
    rc_time = remote_champs.get("updated", "")
    lc_time = local_champs.get("updated", "")
    if rc_time > lc_time:
        local["model_champions"] = remote_champs

    # Merge pending_questions
    local["pending_questions"] = _merge_list(
        local.get("pending_questions", []),
        remote.get("pending_questions", [])
    )

    # Merge orchestrator_sessions (keep most recent 10)
    local["orchestrator_sessions"] = _merge_list(
        local.get("orchestrator_sessions", []),
        remote.get("orchestrator_sessions", [])
    )[-10:]

    # Merge tracked_researchers (deduplicate by handle)
    local_researchers  = local.get("tracked_researchers", [])
    remote_researchers = remote.get("tracked_researchers", [])
    existing_handles   = {r["handle"].lower() for r in local_researchers if r.get("handle")}
    for r in remote_researchers:
        if r.get("handle", "").lower() not in existing_handles:
            local_researchers.append(r)
            existing_handles.add(r.get("handle", "").lower())
    local["tracked_researchers"] = local_researchers

    return local

# ── capability prompt builder ─────────────────────────────────────────────────

def build_capability_prompt() -> str:
    """Return markdown block of all learned capabilities for injection into system prompts."""
    s = load()
    caps = s.get("capabilities", {}).get("learned", [])
    if not caps:
        return ""
    lines = ["## Learned Capabilities (inherited from all hives)\n"]
    for cap in caps[:30]:   # limit to 30 most recent
        lines.append(f"### [{cap['skill']}] {cap['description']}")
        if cap.get("example"):
            lines.append(f"  Example: `{cap['example']}`")
        if cap.get("tags"):
            lines.append(f"  Tags: {', '.join(cap['tags'])}")
        lines.append("")
    return "\n".join(lines)

# ── broadcast payload (compact) ───────────────────────────────────────────────

def get_broadcast_payload(status: dict = None) -> dict:
    """Return a compact version safe to SSE-broadcast (no huge blobs)."""
    if status is None:
        status = load()
    return {
        "last_updated":   status.get("last_updated"),
        "updated_by":     status.get("updated_by"),
        "hives":          status.get("hives", {}),
        "achievements":       status.get("achievements", [])[:10],
        "achievements_total": len(status.get("achievements", [])),
        "blockers":       [b for b in status.get("blockers", [])
                           if b.get("status") == "open"][:20],
        "next_steps":     status.get("next_steps", [])[:10],
        "capabilities":   {
            "count":   len(status.get("capabilities", {}).get("learned", [])),
            "recent":  status.get("capabilities", {}).get("learned", [])[:5],
        },
        "metrics":        status.get("metrics", {}),
        "model_champions": status.get("model_champions", {}),
        "knowledge": {
            "findings_count":  len(status.get("knowledge", {}).get("findings", [])),
            "solutions_count": len(status.get("knowledge", {}).get("solutions", [])),
        },
        "pending_questions": status.get("pending_questions", []),
        "deployment":        status.get("deployment", {}),
        "orchestrator_sessions": status.get("orchestrator_sessions", [])[-1:],  # last entry only
        "active_task":       status.get("active_task"),
    }

# ── GitHub sync ───────────────────────────────────────────────────────────────

REMOTE_PATH = "status/hive-knowledge.json"

def _gh(*args, input_data=None):
    r = subprocess.run(["gh"] + list(args), capture_output=True,
                       text=True, input=input_data, timeout=30)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def push_to_github(repo: str):
    """Push current local status JSON + README to GitHub repo."""
    try:
        with _status_lock:
            s = load()
        import base64 as _b64

        # ── push JSON ────────────────────────────────────────────────────────
        content = json.dumps(s, indent=2)
        b64_content = _b64.b64encode(content.encode()).decode()
        out, _, rc = _gh("api", f"repos/{repo}/contents/{REMOTE_PATH}")
        sha_arg = []
        if rc == 0:
            try:
                sha = json.loads(out)["sha"]
                sha_arg = ["--field", f"sha={sha}"]
            except Exception:
                pass
        _gh("api", f"repos/{repo}/contents/{REMOTE_PATH}",
            "--method", "PUT",
            "--field", f"message=hive-status: {_now()}",
            "--field", f"content={b64_content}",
            *sha_arg)

        # ── push README ───────────────────────────────────────────────────────
        readme_remote = "status/README.md"
        try:
            with open(README_FILE) as f:
                readme_content = f.read()
        except OSError:
            _write_readme(s)
            try:
                with open(README_FILE) as f:
                    readme_content = f.read()
            except OSError:
                readme_content = ""
        if readme_content:
            b64_readme = _b64.b64encode(readme_content.encode()).decode()
            out2, _, rc2 = _gh("api", f"repos/{repo}/contents/{readme_remote}")
            sha_arg2 = []
            if rc2 == 0:
                try:
                    sha2 = json.loads(out2)["sha"]
                    sha_arg2 = ["--field", f"sha={sha2}"]
                except Exception:
                    pass
            _gh("api", f"repos/{repo}/contents/{readme_remote}",
                "--method", "PUT",
                "--field", f"message=hive-status readme: {_now()}",
                "--field", f"content={b64_readme}",
                *sha_arg2)
    except Exception:
        pass


def pull_from_github(repo: str) -> dict | None:
    """Pull remote status from GitHub. Returns parsed dict or None."""
    try:
        out, _, rc = _gh("api", f"repos/{repo}/contents/{REMOTE_PATH}")
        if rc != 0:
            return None
        import base64 as _b64
        data = json.loads(out)
        content = _b64.b64decode(data["content"]).decode()
        return json.loads(content)
    except Exception:
        return None


def sync_with_github(repo: str):
    """Pull remote, merge, push merged result. Call from background thread."""
    remote = pull_from_github(repo)
    if remote:
        with _status_lock:
            merged = merge_remote(remote)
            save(merged, "github-sync")
    push_to_github(repo)

# ── pending questions ─────────────────────────────────────────────────────────

def add_question(hive: str, agent: str, question: str,
                 hint: str = "", type_: str = "text",
                 choices: list = None, required: bool = True,
                 updated_by: str = "agent") -> str:
    """Post a pending question that needs a human or AI answer."""
    qid = _uid("q")
    with _status_lock:
        s = load()
        s.setdefault("pending_questions", []).append({
            "id":          qid,
            "ts":          _now(),
            "hive":        hive,
            "agent":       agent,
            "question":    question,
            "hint":        hint,
            "type":        type_,        # text | choice | confirm
            "choices":     choices or [],
            "required":    required,
            "answered":    False,
            "answer":      None,
            "answered_by": None,         # "human" | "ai"
            "answered_at": None,
        })
        s["pending_questions"] = s["pending_questions"][-100:]  # cap at 100
        save(s, updated_by)
    return qid


def answer_question(question_id: str, answer: str,
                    answered_by: str = "human",
                    updated_by: str = "agent"):
    """Mark a pending question as answered."""
    with _status_lock:
        s = load()
        for q in s.get("pending_questions", []):
            if q["id"] == question_id:
                q["answered"]    = True
                q["answer"]      = answer
                q["answered_by"] = answered_by
                q["answered_at"] = _now()
                break
        save(s, updated_by)


def get_pending_questions(unanswered_only: bool = False) -> list:
    """Return pending questions, optionally filtering to unanswered only."""
    s = load()
    pqs = s.get("pending_questions", [])
    if unanswered_only:
        return [q for q in pqs if not q.get("answered")]
    return list(pqs)


def update_deployment(vercel_url: str = None, vercel_project: str = None,
                      status: str = None, updated_by: str = "vercel-hive"):
    """Update Vercel deployment info."""
    with _status_lock:
        s = load()
        d = s.setdefault("deployment", {})
        if vercel_url:    d["vercel_url"]     = vercel_url
        if vercel_project: d["vercel_project"] = vercel_project
        if status:        d["status"]          = status
        if vercel_url:    d["deployed_at"]     = _now()
        save(s, updated_by)


def update_orchestrator_session(
        summary: str,
        goal: str = "",
        progress: str = "",
        next_steps: list = None,
        decisions: list = None,
        updated_by: str = "opencode") -> str:
    """
    Append a compaction summary to the orchestrator_sessions ring (max 10).
    Returns the entry id.
    """
    sid = _uid("sess")
    entry = {
        "id":         sid,
        "ts":         _now(),
        "updated_by": updated_by,
        "goal":       goal,
        "summary":    summary,
        "progress":   progress,
        "next_steps": next_steps or [],
        "decisions":  decisions or [],
    }
    with _status_lock:
        s = load()
        ring = s.setdefault("orchestrator_sessions", [])
        ring.append(entry)
        # keep most recent 10 only
        s["orchestrator_sessions"] = ring[-10:]
        save(s, updated_by)
    return sid


# ── tracked researchers ───────────────────────────────────────────────────────

def add_researcher(handle: str, platform: str = "github",
                   keywords: list = None, context: str = "",
                   priority_repos: list = None,
                   updated_by: str = "user") -> str:
    """
    Add or update a researcher to track.
    Returns the handle (lowercased).

    handle        — GitHub username (or other platform handle)
    platform      — "github" (others reserved for future)
    keywords      — repo/description filter terms for repo discovery
    context       — LLM system prompt prefix describing what to extract
    priority_repos— list of full_name strings (e.g. "user/repo") to always watch
    """
    handle = handle.strip()
    if not handle:
        raise ValueError("handle is required")
    with _status_lock:
        s = load()
        researchers = s.setdefault("tracked_researchers", [])
        # Update existing or append new
        for r in researchers:
            if r.get("handle", "").lower() == handle.lower():
                r["platform"]       = platform
                r["keywords"]       = keywords or r.get("keywords", [])
                r["context"]        = context or r.get("context", "")
                r["priority_repos"] = priority_repos or r.get("priority_repos", [])
                r["updated_at"]     = _now()
                save(s, updated_by)
                return handle.lower()
        researchers.append({
            "handle":        handle,
            "platform":      platform,
            "keywords":      keywords or [],
            "context":       context,
            "priority_repos": priority_repos or [],
            "added_at":      _now(),
            "updated_at":    _now(),
        })
        save(s, updated_by)
    return handle.lower()


def get_tracked_researchers() -> list:
    """Return list of tracked researcher config dicts."""
    return load().get("tracked_researchers", [])


def remove_researcher(handle: str, updated_by: str = "user"):
    """Remove a researcher from tracking by handle."""
    handle = handle.strip().lower()
    with _status_lock:
        s = load()
        before = s.get("tracked_researchers", [])
        s["tracked_researchers"] = [
            r for r in before
            if r.get("handle", "").lower() != handle
        ]
        save(s, updated_by)


def build_context_block(max_chars: int = 1500) -> str:
    """
    Build a structured context string safe to inject as an LLM system message.
    Pulls from: orchestrator_sessions (most recent), next_steps, blockers,
    model_champions, deployment.  Truncates to max_chars.
    """
    s = load()

    parts = []

    # ── last orchestrator session summary ────────────────────────────────────
    # Guard: orchestrator_sessions must be a list of dicts; skip string entries
    # that may exist from a previous startup-cleanup bug.
    sessions = [e for e in s.get("orchestrator_sessions", []) if isinstance(e, dict)]
    if sessions:
        last = sessions[-1]
        parts.append("## Last Session")
        if last.get("goal"):
            parts.append(f"Goal: {last['goal']}")
        if last.get("summary"):
            parts.append(last["summary"][:600])
        if last.get("progress"):
            parts.append(f"Progress: {last['progress'][:300]}")
        if last.get("next_steps"):
            ns_lines = "\n".join(f"  - {n}" for n in last["next_steps"][:5])
            parts.append(f"Next steps:\n{ns_lines}")
        if last.get("decisions"):
            dec_lines = "\n".join(f"  - {d}" for d in last["decisions"][:5])
            parts.append(f"Key decisions:\n{dec_lines}")
        parts.append(f"(recorded {last.get('ts','?')[:16]})")

    # ── active blockers ───────────────────────────────────────────────────────
    open_blockers = [b for b in s.get("blockers", []) if b.get("status") == "open"]
    if open_blockers:
        parts.append("\n## Active Blockers")
        for b in open_blockers[:3]:
            parts.append(f"  [{b.get('severity','?')}] {b['description'][:80]}")

    # ── pending next steps ────────────────────────────────────────────────────
    pending = [ns for ns in s.get("next_steps", []) if ns.get("status") == "pending"]
    if pending:
        parts.append("\n## Pending Next Steps")
        for ns in pending[:5]:
            parts.append(f"  P{ns.get('priority',5)} {ns['description'][:70]}")

    # ── model champions ───────────────────────────────────────────────────────
    champs = s.get("model_champions", {})
    if champs.get("text") or champs.get("vision"):
        parts.append("\n## Model Champions")
        if champs.get("text"):
            parts.append(f"  text:   {champs['text']}")
        if champs.get("vision"):
            parts.append(f"  vision: {champs['vision']}")

    # ── deployment ────────────────────────────────────────────────────────────
    dep = s.get("deployment", {})
    if dep.get("vercel_url"):
        parts.append(f"\n## Deployment\n  {dep['vercel_url']} [{dep.get('status','?')}]")

    block = "\n".join(parts)
    if len(block) > max_chars:
        block = block[:max_chars - 3] + "..."
    return block

# ── CLI summary mode ──────────────────────────────────────────────────────────

def _print_summary():
    """Print a concise orchestrator-readable status summary."""
    s = load()
    print(f"=== HIVE STATUS {s.get('last_updated','?')} ===")

    # Hives
    hives = s.get("hives", {})
    if hives:
        hive_strs = "  ".join(f"{n}({d.get('status','?')})" for n, d in hives.items())
        print(f"Hives:    {hive_strs}")
    else:
        print("Hives:    (none registered)")

    # Champions
    ch = s.get("model_champions", {})
    print(f"Champion: text={ch.get('text') or 'none'}  vision={ch.get('vision') or 'none'}")

    # Blockers
    open_blockers = [b for b in s.get("blockers", []) if b.get("status") == "open"]
    print(f"Blockers: {len(open_blockers)} active", end="")
    if open_blockers:
        first = open_blockers[0]
        print(f"  →  [{first['id']}] {first['description'][:60]} ({first.get('severity','?')})")
    else:
        print()

    # Next steps
    pending_steps = [ns for ns in s.get("next_steps", []) if ns.get("status") == "pending"]
    print(f"Next:     {len(pending_steps)} pending", end="")
    for i, ns in enumerate(pending_steps[:3]):
        prefix = "  →  " if i == 0 else "           "
        print(f"{prefix}[{ns['id']}] {ns['description'][:55]}")
    if not pending_steps:
        print()

    # Pending questions
    unanswered = [q for q in s.get("pending_questions", []) if not q.get("answered")]
    print(f"Pending Q: {len(unanswered)} unanswered", end="")
    for i, q in enumerate(unanswered[:3]):
        prefix = "  →  " if i == 0 else "           "
        print(f"{prefix}[{q['id']}] {q['question'][:55]} ({q.get('hive','?')})")
    if not unanswered:
        print()

    # Achievements
    achs = s.get("achievements", [])
    print(f"Achievements: {len(achs)} total", end="")
    if achs:
        print(f", last: \"{achs[0]['description'][:60]}\"")
    else:
        print()

    # Deployment
    dep = s.get("deployment", {})
    if dep.get("vercel_url"):
        print(f"Vercel:   {dep['vercel_url']}  [{dep.get('status','?')}]")

    # Capabilities
    caps = s.get("capabilities", {}).get("learned", [])
    print(f"Caps:     {len(caps)} learned")


if __name__ == "__main__":
    import sys
    if "--summary" in sys.argv:
        _print_summary()
    elif "--compact" in sys.argv:
        print(build_context_block(max_chars=3000))
    else:
        print("Usage: python3 hive_status.py --summary")
        print("       python3 hive_status.py --compact")
        print("       Import as module for full API access.")
