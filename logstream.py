#!/usr/bin/env python3
"""
Hive UI — live tmux log monitor + cloud chat + prompt queue + GitHub PR tracking
           + centralized knowledge base + live status SSE + model arena.

Endpoints:
  GET  /                        → dashboard HTML
  GET  /stream                  → SSE log stream
  GET  /status/stream           → SSE live status JSON (hive-knowledge broadcast)
  GET  /api/sessions            → discovered tmux sessions
  GET  /api/snapshot            → full buffer dump
  GET  /api/config              → current config
  POST /api/config              → save config
  POST /api/upload              → multipart file upload
  POST /api/prompt              → submit prompt → SSE LLM stream
  GET  /api/queue               → task queue JSON
  POST /api/queue/poll          → force-refresh PR statuses
  DELETE /api/chat              → clear chat history
  GET  /api/status              → full status JSON snapshot
  GET  /api/status/compact      → build_context_block() as plain text (for LLM injection)
  POST /api/status/achievement  → agent reports achievement
  POST /api/status/blocker      → agent reports blocker
  PATCH /api/status/blocker/<id>→ resolve blocker
  POST /api/status/capability   → agent reports learned capability
  POST /api/status/next-step    → add next step
  PATCH /api/status/next-step/<id> → update next step status
  POST /api/status/finding      → add knowledge finding
  GET  /api/groups              → named hive groups
  POST /api/groups              → save groups config
  POST /api/status/answer       → answer a pending question
  POST /api/status/compact      → store orchestrator compaction summary
  GET  /api/arena/status        → model arena champion + last run
  POST /api/arena/run           → trigger arena benchmark async
  GET  /api/arena/results       → full leaderboard JSON
  GET  /api/doctor/status       → last hive-doctor run summary
  GET  /api/uid/registry        → per-browser uid activity (orchestrator access)
   GET  /api/tracker/status      → researcher tracker status
   POST /api/tracker/add         → add/update tracked researcher
   DELETE /api/tracker/remove    → remove tracked researcher
"""
import email.message, email.policy, hashlib, http.client, io, json
import os, queue, re, subprocess, ssl, threading, time, traceback, uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import sys
sys.path.insert(0, os.path.dirname(__file__))
import hive_status
try:
    import model_arena
    _ARENA_AVAILABLE = True
except Exception:
    _ARENA_AVAILABLE = False

try:
    import researcher_tracker
    _TRACKER_AVAILABLE = True
except Exception:
    _TRACKER_AVAILABLE = False

# ── runtime config ────────────────────────────────────────────────────────────

def _read_hive_env():
    """Read env vars from config file. Tries HIVE_ENV_FILE → ~/.config/hive-ui/env → ~/.config/research-hive/env → {script_dir}/.env."""
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.environ.get("HIVE_ENV_FILE", ""),
        os.path.expanduser("~/.config/hive-ui/env"),
        os.path.expanduser("~/.config/research-hive/env"),
        os.path.join(_script_dir, ".env"),
    ]
    pairs = {}
    for env_file in candidates:
        if not env_file:
            continue
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, _, v = line.partition("=")
                        pairs[k.strip()] = v.strip()
            return pairs   # return on first successfully read file
        except OSError:
            continue
    return pairs

_hive_env = _read_hive_env()

PORT              = int(os.environ.get("PORT", "8888"))
OPENROUTER_KEY    = os.environ.get("OPENROUTER_API_KEY") or _hive_env.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL  = os.environ.get("OPENROUTER_MODEL") or _hive_env.get("OPENROUTER_MODEL", "inclusionai/ling-2.6-1t:free")
LLM_BASE_URL      = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
GITHUB_TASKS_REPO = os.environ.get("GITHUB_TASKS_REPO", "")
HIVE_NAME         = os.environ.get("HIVE_NAME", "default")

_HIVE_UI_URL = os.environ.get("HIVE_UI_URL", "https://openrouter.ai")

MAX_LINES        = 100
COMBINED_MAX     = 1000
POLL_INTERVAL    = 2
CAPTURE_LINES    = 200
UPLOAD_MAX_BYTES = 10 * 1024 * 1024
UPLOAD_KEEP      = 20
CHAT_HISTORY_MAX = 40
QUEUE_FILE       = "/tmp/hive-queue.json"
GROUPS_FILE      = "/tmp/hive-groups.json"
DOCTOR_INTERVAL  = 30 * 60    # 30 minutes
GITHUB_SYNC_INTERVAL = 5 * 60  # 5 minutes
SILENCE_THRESHOLD    = 30 * 60  # 30 min silence = stalled

DEFAULT_FAVORITES = [
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen3-coder:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md",
    ".txt", ".log", ".sh", ".bash", ".yml", ".yaml", ".toml", ".ini",
    ".env", ".conf", ".cfg", ".xml", ".sql", ".php", ".rb", ".go",
    ".rs", ".c", ".cpp", ".h", ".java", ".kt", ".swift", ".cs",
}

# ── shared state ──────────────────────────────────────────────────────────────

buffers  = {}
combined = deque(maxlen=COMBINED_MAX)
lock     = threading.Lock()

uploads       = {}
uploads_order = deque(maxlen=UPLOAD_KEEP)
uploads_lock  = threading.Lock()

task_queue = []
queue_lock = threading.Lock()

chat_history = []
chat_lock    = threading.Lock()

_server_config = {
    "model":        OPENROUTER_MODEL,
    "llm_base_url": LLM_BASE_URL,
    "api_key_set":  bool(OPENROUTER_KEY),
    "favorites":    DEFAULT_FAVORITES,
    "tasks_repo":   GITHUB_TASKS_REPO,
    "ai_auto_answer":             False,
    "ai_auto_answer_timeout_min": 30,
}
config_lock = threading.Lock()

# ── per-browser uid registry ──────────────────────────────────────────────────
# Key: uid str  Value: {"first_seen": iso, "last_seen": iso, "calls": int}
# Orchestrator (no uid or uid="orchestrator") has full unrestricted access.
_uid_registry: dict = {}
_uid_lock = threading.Lock()

def _register_uid(uid: str):
    """Record an activity hit for this uid."""
    if not uid:
        return
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with _uid_lock:
        if uid not in _uid_registry:
            _uid_registry[uid] = {"first_seen": now, "last_seen": now, "calls": 1}
        else:
            _uid_registry[uid]["last_seen"] = now
            _uid_registry[uid]["calls"]     += 1

_groups = {}           # {group_name: [session, ...]}
groups_lock = threading.Lock()

# last non-GET interaction time (POST/PATCH/DELETE) — used by question_timeout_loop
_last_ui_activity      = time.time()
_activity_lock         = threading.Lock()

_doctor_status = {
    "last_run": None,
    "last_findings": [],
    "runs_total": 0,
}
doctor_lock = threading.Lock()

# session last-seen timestamps for silence detection
_session_last_seen = {}   # {session: time.time()}
_session_lock = threading.Lock()

# arena job tracker
_arena_job = {"running": False, "last_run": None, "last_type": None}
_arena_lock = threading.Lock()

# ── session discovery ─────────────────────────────────────────────────────────

def discover_sessions():
    try:
        r = subprocess.run(
            ["tmux", "ls", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5)
        return [s.strip() for s in r.stdout.strip().splitlines() if s.strip()]
    except Exception:
        return []

# ── tmux capture ──────────────────────────────────────────────────────────────

def capture(session):
    try:
        r = subprocess.run(
            ["tmux", "capture-pane", "-t", session, "-p", "-J", "-S", f"-{CAPTURE_LINES}"],
            capture_output=True, text=True, timeout=5)
        return r.stdout.strip().splitlines()
    except Exception:
        return []

# ── diff / dedup ──────────────────────────────────────────────────────────────

def find_new_lines(old, curr):
    if not old:
        return curr
    if not curr:
        return []
    max_k = min(len(old), len(curr))
    for k in range(max_k, 0, -1):
        if old[-k:] == curr[:k]:
            return curr[k:]
    old_tail = set(old[-20:])
    for i, line in enumerate(curr):
        if line not in old_tail:
            return curr[i:]
    return []

# ── poll loop ─────────────────────────────────────────────────────────────────

def poll_loop():
    prev = {}
    while True:
        sessions = discover_sessions()
        with lock:
            for s in sessions:
                if s not in buffers:
                    buffers[s] = deque(maxlen=MAX_LINES)
        for s in sessions:
            lines = [l.rstrip() for l in capture(s) if l.strip()]
            if not lines:
                continue
            with lock:
                new_lines = find_new_lines(prev.get(s, []), lines)
                for line in new_lines:
                    buffers[s].append(line)
                    combined.append({
                        "session": s, "line": line,
                        "ts": time.strftime("%H:%M:%S"),
                    })
                prev[s] = lines
            if lines:
                with _session_lock:
                    _session_last_seen[s] = time.time()
        time.sleep(POLL_INTERVAL)

# ── groups persistence ────────────────────────────────────────────────────────

def _load_groups():
    global _groups
    try:
        with open(GROUPS_FILE) as f:
            data = json.load(f)
        with groups_lock:
            _groups = data.get("groups", {})
    except Exception:
        pass

def _save_groups():
    with groups_lock:
        data = {"groups": dict(_groups)}
    try:
        with open(GROUPS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass

# ── queue persistence ─────────────────────────────────────────────────────────

def _load_queue():
    try:
        with open(QUEUE_FILE) as f:
            items = json.load(f)
        with queue_lock:
            task_queue.extend(items)
    except (OSError, json.JSONDecodeError):
        pass

def _save_queue():
    try:
        with queue_lock:
            data = list(task_queue)
        with open(QUEUE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass

# ── GitHub helpers ────────────────────────────────────────────────────────────

def _gh(*args, input_data=None):
    cmd = ["gh"] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True,
                       input=input_data, timeout=30)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def ensure_tasks_repo(repo):
    _, _, rc = _gh("repo", "view", repo)
    if rc != 0:
        _gh("repo", "create", repo, "--private",
            "--description", "Hive UI task queue — one PR per prompt")
        readme = "# Hive Tasks\n\nOne PR per prompt. Merge = accepted.\n"
        _gh("api", f"repos/{repo}/contents/README.md",
            "--method", "PUT",
            "--field", "message=init",
            "--field", f"content={__import__('base64').b64encode(readme.encode()).decode()}")

def create_task_pr(repo, item_id, summary, thread_md):
    branch   = f"task/{item_id}"
    filename = f"tasks/{item_id}.md"
    content_b64 = __import__("base64").b64encode(thread_md.encode()).decode()
    out, _, rc = _gh("api", f"repos/{repo}/git/ref/heads/main")
    if rc != 0:
        out, _, rc = _gh("api", f"repos/{repo}/git/ref/heads/master")
    if rc != 0:
        return None, None
    try:
        sha = json.loads(out)["object"]["sha"]
    except Exception:
        return None, None
    _gh("api", f"repos/{repo}/git/refs", "--method", "POST",
        "--field", f"ref=refs/heads/{branch}", "--field", f"sha={sha}")
    _gh("api", f"repos/{repo}/contents/{filename}", "--method", "PUT",
        "--field", f"message=task: {summary[:72]}",
        "--field", f"content={content_b64}", "--field", f"branch={branch}")
    title = summary[:72] + ("…" if len(summary) > 72 else "")
    for base in ("main", "master"):
        out, _, rc = _gh("pr", "create", "--repo", repo,
                         "--head", branch, "--base", base,
                         "--title", title, "--body", thread_md, "--draft")
        if rc == 0:
            break
    if rc != 0:
        return None, None
    pr_url = out.strip()
    try:
        pr_number = int(pr_url.rstrip("/").split("/")[-1])
    except Exception:
        pr_number = None
    return pr_number, pr_url

def poll_pr_statuses():
    with queue_lock:
        items = [i for i in task_queue if i.get("status") == "pr_open"]
    for item in items:
        repo = item.get("task_dest", "").strip()
        pr_number = item.get("pr_number")
        if not repo or not pr_number:
            continue
        out, _, rc = _gh("api", f"repos/{repo}/pulls/{pr_number}")
        if rc != 0:
            continue
        try:
            data   = json.loads(out)
            merged = data.get("merged", False)
            state  = data.get("state", "open")
            with queue_lock:
                for i in task_queue:
                    if i["id"] == item["id"]:
                        if merged:
                            i["status"] = "merged"
                        elif state == "closed":
                            i["status"] = "closed"
                        break
        except Exception:
            pass
    _save_queue()

def _background_pr(item, repo):
    try:
        ensure_tasks_repo(repo)
        thread_md = _build_thread_md(item)
        pr_number, pr_url = create_task_pr(repo, item["id"],
                                            item["summary"], thread_md)
        with queue_lock:
            for i in task_queue:
                if i["id"] == item["id"]:
                    if pr_number:
                        i["pr_number"] = pr_number
                        i["pr_url"]    = pr_url
                        i["status"]    = "pr_open"
                    else:
                        i["status"]    = "local"
                    break
        _save_queue()
    except Exception:
        with queue_lock:
            for i in task_queue:
                if i["id"] == item["id"]:
                    i["status"] = "local"
                    break
        _save_queue()

def _build_thread_md(item):
    lines = [f"# {item['summary'][:72]}\n",
             f"**Submitted:** {item['created_at']}  ",
             f"**Model:** {item.get('model','?')}  ",
             f"**Status:** {item.get('status','?')}\n", "---\n"]
    for msg in item.get("thread", []):
        role = msg["role"].upper()
        lines.append(f"**{role}:**\n\n{msg['content']}\n\n---\n")
    return "\n".join(lines)

def pr_poll_loop():
    while True:
        time.sleep(60)
        try:
            poll_pr_statuses()
        except Exception:
            pass

# ── file upload helpers ───────────────────────────────────────────────────────

def _detect_attachment(filename, mime, data_bytes):
    ext      = os.path.splitext(filename)[1].lower()
    is_image = mime.startswith("image/")
    is_text  = mime.startswith("text/") or ext in TEXT_EXTENSIONS
    if is_image:
        import base64
        b64 = base64.b64encode(data_bytes).decode()
        return {"type": "image", "mime": mime, "b64": b64,
                "filename": filename, "size": len(data_bytes)}
    elif is_text:
        try:
            text = data_bytes.decode("utf-8", errors="replace")
        except Exception:
            text = data_bytes.decode("latin-1", errors="replace")
        return {"type": "text", "mime": mime, "text": text,
                "filename": filename, "size": len(data_bytes)}
    else:
        return {"type": "binary", "mime": mime,
                "filename": filename, "size": len(data_bytes)}

def _build_messages(prompt, attachment_ids, history, system_instructions):
    messages = []
    if system_instructions:
        messages.append({"role": "system", "content": system_instructions})
    messages.extend(history)
    content_parts = []
    with uploads_lock:
        for aid in attachment_ids:
            att = uploads.get(aid)
            if not att:
                continue
            if att["type"] == "image":
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{att['mime']};base64,{att['b64']}"}
                })
            elif att["type"] == "text":
                ext = os.path.splitext(att["filename"])[1].lstrip(".")
                content_parts.append({
                    "type": "text",
                    "text": f"**File: {att['filename']}**\n```{ext}\n{att['text']}\n```"
                })
            else:
                content_parts.append({
                    "type": "text",
                    "text": f"[Attached: {att['filename']} ({att['size']:,} bytes)]"
                })
    content_parts.append({"type": "text", "text": prompt})
    if all(p["type"] == "text" for p in content_parts):
        combined_text = "\n\n".join(p["text"] for p in content_parts)
        messages.append({"role": "user", "content": combined_text})
    else:
        messages.append({"role": "user", "content": content_parts})
    return messages

# ── LLM streaming ─────────────────────────────────────────────────────────────

def _stream_llm(messages, model, api_key, base_url, out_queue):
    parsed  = urlparse(base_url)
    host    = parsed.netloc
    path    = parsed.path.rstrip("/") + "/chat/completions"
    use_ssl = parsed.scheme == "https"
    body    = json.dumps({
        "model": model, "messages": messages, "stream": True,
    }).encode("utf-8")
    headers = {
        "Content-Type":   "application/json",
        "Authorization":  f"Bearer {api_key}",
        "HTTP-Referer":   _HIVE_UI_URL,
        "X-Title":        "Hive UI",
        "Content-Length": str(len(body)),
    }
    try:
        if use_ssl:
            ctx  = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, context=ctx, timeout=60)
        else:
            conn = http.client.HTTPConnection(host, timeout=60)
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        if resp.status != 200:
            err_body = resp.read().decode("utf-8", errors="replace")
            out_queue.put({"error": f"HTTP {resp.status}: {err_body[:300]}"})
            return
        full_text = []
        buf = b""
        while True:
            chunk = resp.read(256)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                if line == b"data: [DONE]":
                    out_queue.put({"done": True, "full": "".join(full_text)})
                    return
                if line.startswith(b"data: "):
                    try:
                        obj   = json.loads(line[6:])
                        d     = obj.get("choices", [{}])[0].get("delta", {})
                        # Include reasoning tokens (o1/o3/gpt-oss-120b style) so the
                        # stream is visibly active from the first chunk, not just after
                        # the model switches from reasoning to content phase.
                        delta = d.get("content") or d.get("reasoning") or ""
                        if delta:
                            full_text.append(delta)
                            out_queue.put({"delta": delta})
                    except Exception:
                        pass
        out_queue.put({"done": True, "full": "".join(full_text)})
    except Exception as e:
        out_queue.put({"error": str(e)})
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ── multipart parser ──────────────────────────────────────────────────────────

def _parse_multipart(content_type_header, body_bytes):
    msg_bytes = f"Content-Type: {content_type_header}\r\n\r\n".encode() + body_bytes
    msg = email.message_from_bytes(msg_bytes, policy=email.policy.compat32)
    fields = {}
    for part in msg.get_payload():
        if isinstance(part, str):
            continue
        disposition = part.get("Content-Disposition", "")
        params = {}
        for seg in disposition.split(";"):
            seg = seg.strip()
            if "=" in seg:
                k, _, v = seg.partition("=")
                params[k.strip()] = v.strip().strip('"')
        name     = params.get("name", "")
        filename = params.get("filename", "")
        payload  = part.get_payload(decode=True)
        if payload is None:
            continue
        if filename:
            mime = part.get_content_type() or "application/octet-stream"
            fields[name] = (filename, mime, payload)
        else:
            fields[name] = payload.decode("utf-8", errors="replace")
    return fields

# ── background LLM budget ─────────────────────────────────────────────────────
# Prevents runaway API spend from background tasks (doctor, tracker, arena).

_BG_MAX_TOKENS    = 512     # hard cap per background call
_BG_MAX_CALLS_HR  = 20      # max background LLM calls per hour
_bg_budget_lock   = threading.Lock()
_bg_calls_this_hr: list = []   # timestamps of recent calls

def _bg_budget_ok() -> bool:
    """Return True if we are within the per-hour budget."""
    now = time.time()
    with _bg_budget_lock:
        # Evict calls older than 1 hour
        cutoff = now - 3600
        while _bg_calls_this_hr and _bg_calls_this_hr[0] < cutoff:
            _bg_calls_this_hr.pop(0)
        return len(_bg_calls_this_hr) < _BG_MAX_CALLS_HR

def _bg_budget_consume():
    """Record a background LLM call against the budget."""
    with _bg_budget_lock:
        _bg_calls_this_hr.append(time.time())

# Privacy boundary prefix injected into every background LLM system message.
# The LLM must not reveal user-specific operational data in responses.
_PRIVACY_BOUNDARY = (
    "[PRIVACY BOUNDARY] You are operating inside a multi-user hive system. "
    "Do not reveal user handles, session names, file paths, or any personally "
    "identifying information in your response. Refer to sessions generically "
    "(e.g. 'the monitored session') unless the session name is required for a "
    "shell command. Keep responses concise and technically focused.\n\n"
)

def _call_bg_llm(messages: list, model: str = None,
                 timeout: int = 45) -> tuple:
    """
    Budget-aware background LLM call (doctor, arena, tracker).
    Returns (text, error_str_or_None).

    Automatically:
      - enforces per-hour call budget (_BG_MAX_CALLS_HR)
      - caps max_tokens at _BG_MAX_TOKENS
      - prepends _PRIVACY_BOUNDARY to the first system message
    """
    if not OPENROUTER_KEY:
        return "", "no API key"
    if not _bg_budget_ok():
        return "", f"budget exceeded ({_BG_MAX_CALLS_HR} calls/hr)"

    model = model or OPENROUTER_MODEL

    # Inject privacy boundary into first system message
    msgs = list(messages)
    injected = False
    for i, m in enumerate(msgs):
        if m.get("role") == "system":
            msgs[i] = {**m, "content": _PRIVACY_BOUNDARY + m["content"]}
            injected = True
            break
    if not injected:
        msgs.insert(0, {"role": "system", "content": _PRIVACY_BOUNDARY.strip()})

    parsed  = urlparse(LLM_BASE_URL)
    host    = parsed.netloc
    path    = parsed.path.rstrip("/") + "/chat/completions"
    body    = json.dumps({
        "model": model, "messages": msgs,
        "stream": False, "max_tokens": _BG_MAX_TOKENS,
    }).encode()
    headers = {
        "Content-Type":   "application/json",
        "Authorization":  f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer":   _HIVE_UI_URL,
        "X-Title":        "Hive UI Background",
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
        text = (data.get("choices", [{}])[0]
                    .get("message", {}).get("content", ""))
        _bg_budget_consume()
        hive_status.increment_metric("openrouter_calls_today", updated_by="system")
        return text, None
    except Exception as e:
        return "", str(e)



def _call_llm_sync(messages, model=None, timeout=60):
    """Non-streaming LLM call. Delegates to _call_bg_llm (budget-aware)."""
    return _call_bg_llm(messages, model=model, timeout=timeout)


def _doctor_check_sessions():
    """Return list of session health dicts."""
    sessions = discover_sessions()
    results  = []
    now      = time.time()
    for s in sessions:
        with _session_lock:
            last = _session_last_seen.get(s, now)
        silent_s = int(now - last)
        with lock:
            buf = list(buffers.get(s, []))
        last_lines  = buf[-10:] if buf else []
        error_count = sum(1 for l in last_lines
                         if re.search(r"error|kill|sigkill|failed|exception",
                                      l, re.I))
        status = "running"
        if silent_s > SILENCE_THRESHOLD:
            status = "stalled"
        elif error_count >= 3:
            status = "error"
        elif not buf:
            status = "idle"
        results.append({
            "session":      s,
            "status":       status,
            "silent_s":     silent_s,
            "error_count":  error_count,
            "last_lines":   last_lines,
        })
    return results


def _parse_capability_blocks(text):
    """Extract CAPABILITY: {...} JSON blocks from doctor response."""
    caps = []
    for m in re.finditer(r"CAPABILITY:\s*(\{[^}]+\})", text, re.DOTALL):
        try:
            caps.append(json.loads(m.group(1)))
        except Exception:
            pass
    return caps


def doctor_loop():
    """Background thread: runs every DOCTOR_INTERVAL seconds."""
    time.sleep(30)  # initial delay
    while True:
        try:
            _run_doctor()
        except Exception as e:
            pass
        time.sleep(DOCTOR_INTERVAL)


def _run_doctor():
    session_health = _doctor_check_sessions()
    problems       = [s for s in session_health
                      if s["status"] in ("stalled", "error")]

    # Update hive health in status JSON
    all_sessions = [s["session"] for s in session_health]
    healthy      = len([s for s in session_health if s["status"] == "running"])
    total        = len(session_health) or 1
    score        = healthy / total

    with config_lock:
        goal = _server_config.get("goal", "")

    hive_status.update_hive_health(
        hive_name=HIVE_NAME,
        sessions=all_sessions,
        status="running" if score > 0.7 else ("error" if score < 0.4 else "stalled"),
        health_score=score,
        current_goal=goal,
        active_model=OPENROUTER_MODEL,
        errors_last_hour=sum(s["error_count"] for s in session_health),
        silent_minutes=0,
        updated_by="hive-doctor",
    )

    with doctor_lock:
        _doctor_status["runs_total"] += 1
        _doctor_status["last_run"]    = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if not problems:
        # All healthy — log achievement if first clean run in a while
        return

    # ── LLM-independent watchdog: alert watchdog session if orchestrator is dead ──
    # This fires before the LLM call so it never depends on LLM availability.
    _CRITICAL_SESSION = "orchestrator"
    _dead_orchestrator = next(
        (p for p in problems
         if p["session"] == _CRITICAL_SESSION
         and p["status"] in ("stalled", "idle", "error")
         and not p["last_lines"]),   # blank — no output ever captured
        None
    )
    if _dead_orchestrator:
        _alert_msg = (
            f"[hive-doctor] WARNING: '{_CRITICAL_SESSION}' session is dead "
            f"(silent {_dead_orchestrator['silent_s']}s, no output). "
            "Please inspect and restart the orchestrator process."
        )
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", "watchdog", _alert_msg, "Enter"],
                timeout=5, capture_output=True
            )
        except Exception:
            pass
        hive_status.add_blocker(
            HIVE_NAME, "hive-doctor",
            f"Orchestrator session dead — watchdog alerted (silent {_dead_orchestrator['silent_s']}s)",
            severity="high",
        )

    # Build context for LLM diagnosis
    caps_prompt = hive_status.build_capability_prompt()
    problem_text = "\n".join(
        f"Session '{p['session']}': status={p['status']}, "
        f"silent={p['silent_s']}s, errors={p['error_count']}, "
        f"last_lines={p['last_lines'][-3:]}"
        for p in problems
    )

    system_msg = f"""You are hive-doctor, a self-healing orchestrator for tmux-based AI research hives.

{caps_prompt}

Analyze the session problems and produce:
1. A diagnosis for each problem
2. A shell command to attempt a fix (safe, non-destructive)
3. Any new capability you are applying that others should know about

For each new technique discovered, end with:
CAPABILITY: {{"skill": "slug", "description": "one sentence", "example": "code or command"}}

Return JSON:
{{
  "diagnoses": [{{"session": "...", "problem": "...", "fix_command": "...", "severity": "low|medium|high|critical"}}],
  "summary": "one sentence overall"
}}"""

    text, err = _call_llm_sync([
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": f"Problems detected:\n{problem_text}"}
    ])

    with doctor_lock:
        _doctor_status["last_findings"] = []

    if err or not text:
        hive_status.add_blocker(
            HIVE_NAME, "hive-doctor",
            f"LLM diagnosis call failed: {err or 'empty response'}",
            severity="medium"
        )
        return

    # Parse response
    try:
        # Strip markdown fences
        clean = text.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            inner = []
            for line in lines[1:]:
                if line.strip().startswith("```"):
                    break
                inner.append(line)
            clean = "\n".join(inner)
        # Extract JSON before any CAPABILITY: blocks
        json_part = clean.split("CAPABILITY:")[0].strip()
        result    = json.loads(json_part)
    except Exception:
        result = {"diagnoses": [], "summary": text[:200]}

    diagnoses = result.get("diagnoses", [])
    summary   = result.get("summary", "")

    with doctor_lock:
        _doctor_status["last_findings"] = diagnoses

    for diag in diagnoses:
        severity = diag.get("severity", "medium")
        bid = hive_status.add_blocker(
            HIVE_NAME, "hive-doctor",
            f"[{diag.get('session','')}] {diag.get('problem','')}",
            severity=severity,
        )
        fix_cmd = diag.get("fix_command", "").strip()
        if fix_cmd and severity in ("critical", "high"):
            # Auto-apply safe fix commands (whitelist approach)
            _safe_apply(fix_cmd, bid,
                        session = diag.get("session", ""),
                        problem = diag.get("problem", ""))

    if summary:
        hive_status.add_finding(HIVE_NAME, summary, source="doctor")

    # Extract and store new capabilities
    for cap in _parse_capability_blocks(text):
        hive_status.add_capability(
            source_hive=HIVE_NAME,
            source_agent="hive-doctor",
            skill=cap.get("skill", "unknown"),
            description=cap.get("description", ""),
            example=cap.get("example", ""),
            updated_by="hive-doctor",
        )


def _safe_apply(cmd: str, blocker_id: str, session: str = "",
                problem: str = ""):
    """
    Apply a fix command if it passes the safety whitelist.
    Records outcome in hive_status: successful fixes become solutions;
    failures are noted so the doctor doesn't retry the same approach.

    Returns True on success, False on failure or unsafe command.
    """
    SAFE_PATTERNS = [
        r"^tmux send-keys",
        r"^pkill\s+-f\s+",
        r"^kill\s+\d+",
        r"^touch\s+",
        r"^mkdir\s+-p\s+",
        r"^echo\s+",
    ]
    cmd_stripped = cmd.strip()
    if not any(re.match(p, cmd_stripped) for p in SAFE_PATTERNS):
        return False
    try:
        result = subprocess.run(
            cmd_stripped, shell=True, timeout=10,
            capture_output=True, text=True
        )
        if result.returncode == 0:
            hive_status.resolve_blocker(blocker_id, f"Auto-applied: {cmd_stripped}")
            # Store as a solution so the doctor (and other hives) learn from it
            if problem:
                hive_status.add_solution(
                    problem  = problem,
                    solution = cmd_stripped,
                    hive     = HIVE_NAME,
                    verified = True,
                )
            return True
        else:
            # Failed — record the failure so we don't retry blindly
            hive_status.add_finding(
                hive    = HIVE_NAME,
                summary = (f"Auto-fix failed (exit {result.returncode}): "
                           f"`{cmd_stripped[:80]}`"),
                source  = "hive-doctor-rollback",
            )
            return False
    except Exception as e:
        hive_status.add_finding(
            hive    = HIVE_NAME,
            summary = f"Auto-fix exception: {str(e)[:80]} cmd=`{cmd_stripped[:60]}`",
            source  = "hive-doctor-rollback",
        )
        return False


# ── GitHub sync loop ──────────────────────────────────────────────────────────

def github_sync_loop():
    time.sleep(60)  # initial delay
    while True:
        try:
            hive_status.sync_with_github(GITHUB_TASKS_REPO)
        except Exception:
            pass
        time.sleep(GITHUB_SYNC_INTERVAL)


# ── AI auto-answer ────────────────────────────────────────────────────────────

def _ai_answer_question(q: dict):
    """Answer a pending question using the LLM with full hive context."""
    if not OPENROUTER_KEY:
        return
    try:
        capability_ctx  = hive_status.build_capability_prompt()
        s               = hive_status.load()
        recent_ach      = [a["description"] for a in s.get("achievements", [])[-8:]]
        active_blockers = [b["description"] for b in s.get("blockers", [])
                           if b.get("status") == "open"][:5]
        champions       = s.get("model_champions", {})
        hives_summary   = {n: d.get("status") for n, d in s.get("hives", {}).items()}

        system = (
            "You are an autonomous hive orchestration AI with full context of the current hive state.\n\n"
            + (capability_ctx + "\n\n" if capability_ctx else "")
            + f"Recent achievements: {recent_ach}\n"
            + f"Active blockers: {active_blockers}\n"
            + f"Model champions: {champions}\n"
            + f"Active hives: {hives_summary}\n\n"
            "Answer the following configuration question on behalf of the operator. "
            "Be concise, practical, and consistent with the hive's current state. "
            "Return ONLY the answer value — no preamble, no explanation."
        )
        choices_hint = ""
        if q.get("choices"):
            choices_hint = f"\nValid choices: {q['choices']}"
        user_msg = (
            f"Question: {q['question']}\n"
            f"Hint: {q.get('hint', '')}{choices_hint}\n"
            f"Type: {q.get('type', 'text')}"
        )
        answer = _call_llm_sync(
            [{"role": "system", "content": system},
             {"role": "user",   "content": user_msg}],
            timeout=30,
        )
        if answer and answer.strip():
            hive_status.answer_question(q["id"], answer.strip(), answered_by="ai")
    except Exception:
        pass


def question_timeout_loop():
    """Background thread: AI auto-answers all unanswered questions when UI is idle."""
    time.sleep(30)  # initial delay
    while True:
        time.sleep(60)  # check every minute
        try:
            with config_lock:
                enabled     = _server_config.get("ai_auto_answer", False)
                timeout_min = _server_config.get("ai_auto_answer_timeout_min", 30)
            if not enabled:
                continue
            with _activity_lock:
                idle_min = (time.time() - _last_ui_activity) / 60.0
            if idle_min < timeout_min:
                continue
            unanswered = hive_status.get_pending_questions(unanswered_only=True)
            for q in unanswered:
                _ai_answer_question(q)
        except Exception:
            pass


# ── model arena ───────────────────────────────────────────────────────────────

def _run_arena_async(arena_type: str):
    if not _ARENA_AVAILABLE or not OPENROUTER_KEY:
        return
    with _arena_lock:
        if _arena_job["running"]:
            return
        _arena_job["running"]  = True
        _arena_job["last_type"] = arena_type

    def _do():
        try:
            result = model_arena.run_arena(arena_type, OPENROUTER_KEY)
            winner = result.get("winner")
            if winner:
                if arena_type == "text":
                    hive_status.update_model_champions(text=winner)
                else:
                    hive_status.update_model_champions(vision=winner)
                hive_status.add_achievement(
                    HIVE_NAME, "model-arena",
                    f"New {arena_type} champion: {winner}",
                    evidence=f"Score: {result.get('results', [{}])[0].get('total','?')}"
                             f"/{result.get('results', [{}])[0].get('max','?')}",
                )
        except Exception:
            pass
        finally:
            with _arena_lock:
                _arena_job["running"]  = False
                _arena_job["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    threading.Thread(target=_do, daemon=True).start()


# ── dashboard HTML ────────────────────────────────────────────────────────────
# CSS and JS injected from ui_shared.py — single source, no duplication.

from ui_shared import SHARED_CSS, LOCAL_CSS, SHARED_RENDER_JS, LOCAL_STATUS_JS  # noqa

_DASHBOARD_TMPL = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>Hive Monitor</title>
<style>
/*__SHARED_CSS__*//*__LOCAL_CSS__*/
</style>
</head>
<body>
<!-- header -->
<div id="header">
  <h1><span class="dot" id="dot"></span>Hive Monitor</h1>
  <div id="header-btns">
    <button id="menu-btn" class="hdr-btn" onclick="openSettings()">⚙ Config</button>
  </div>
</div>
<div class="status-bar" id="status-bar">Connecting...</div>
<div id="active-task-bar" class="active-task-bar at-ok">
  <span class="at-dot"></span>
  <span class="at-label">OK</span>
  <span class="at-detail"> connecting&hellip;</span>
</div>

<!-- group tabs -->
<div id="group-tabs">
  <div class="gtab active" data-group="__all__" onclick="switchGroup('__all__',this)">All</div>
</div>

<div id="main">

<!-- onboarding (hidden — auto-skipped on load) -->
<div id="onboarding" style="display:none">
  <h2>Welcome to Hive UI — quick setup</h2>
  <div class="ob-q">
    <label>1. What is the mission for this session?</label>
    <textarea id="ob-goal" rows="3" placeholder="e.g. Audit WeGIA PHP app for OWASP Top 10 vulnerabilities"></textarea>
  </div>
  <div class="ob-q">
    <label>2. Define hive groups (optional)</label>
    <textarea id="ob-groups" rows="2" placeholder='{"Research": ["ps5-hive","hive-watch"], "Build": ["build_monitor"]}'></textarea>
    <div style="font-size:10px;color:var(--muted);margin-top:3px">
      JSON map of group name → session list. Leave blank for no grouping.
    </div>
  </div>
  <div class="ob-q">
    <label>3. Where should tasks be tracked?</label>
    <input id="ob-dest" type="text" placeholder="owner/repo or leave blank">
  </div>
  <div class="ob-q">
    <label>4. Which model?</label>
    <div class="model-row">
      <input id="ob-model" type="text" placeholder="model name">
    </div>
    <div class="favorites" id="ob-favorites"></div>
  </div>
  <div class="ob-q">
    <label>5. Standing instructions</label>
    <textarea id="ob-instructions" rows="2" placeholder="Always cite line numbers. Keep answers concise."></textarea>
  </div>
  <button id="ob-submit" onclick="submitOnboarding()">Begin →</button>
</div>

<!-- STATUS PANEL — unified feed: health + blockers + next steps + achievements + capabilities -->
<details class="section" id="status-panel">
  <summary>
    <span><span class="status-dot dead" id="status-dot"></span>Hive Status</span>
    <span id="status-updated" class="count">—</span>
  </summary>

  <!-- health cards + metrics inline -->
  <div id="hive-health-grid"></div>
  <div id="metrics-row"></div>

  <!-- unified activity feed — blockers, next_steps, achievements merged, no nested details -->
  <div id="hive-feed" style="padding:4px 8px 8px"></div>

  <!-- hidden anchors kept for JS compatibility -->
  <span id="blockers-count" style="display:none">0 open</span>
  <span id="ach-count" style="display:none">0</span>
  <span id="ns-count" style="display:none">0</span>
  <span id="caps-count" style="display:none">0</span>
  <div id="blockers-list" style="display:none"></div>
  <div id="achievements-list" style="display:none"></div>
  <div id="nextsteps-list" style="display:none"></div>
  <div id="caps-list" style="display:none"></div>
</details>

<!-- logs — primary landing view (top) -->
<details class="section" id="logs-section" open>
  <summary>
    <span>Logs</span>
    <span class="count" id="combined-count">0 lines</span>
  </summary>
  <div class="log-box combined" id="combined"></div>
</details>

<!-- chat -->
<details class="section" open id="chat-section">
  <summary>
    <span>Chat</span>
    <button id="clear-chat" onclick="clearChat(event)">Clear</button>
  </summary>
  <div id="chat-thread">
    <div class="chat-empty" id="chat-empty">Start a conversation below.</div>
  </div>
</details>

<!-- task queue -->
<details class="section" open id="queue-section">
  <summary>
    <span>Task Queue</span>
    <span class="count" id="queue-count">0 tasks</span>
    <button id="clear-done-btn" onclick="clearDoneItems(event)" title="Remove all done/merged/closed items">clear done</button>
  </summary>
  <div id="queue-list">
    <div id="queue-empty" style="display:none">No tasks yet. Submit a prompt below.</div>
  </div>
</details>

</div><!-- /main -->

<!-- sticky input bar -->
<div id="input-bar">
  <div id="attach-chips"></div>
  <div id="input-row">
    <button id="attach-btn" onclick="triggerAttach()" title="Attach file">📎</button>
    <textarea id="prompt-input" rows="1" placeholder="Ask the hive anything…"
              oninput="autoGrow(this)" onkeydown="handleKey(event)"></textarea>
    <button id="priority-btn" onclick="sendPrompt(true)" title="Force-prioritize this prompt — added to front of queue">⚡</button>
    <button id="send-btn" onclick="sendPrompt()">▶</button>
  </div>
  <input id="file-input" type="file" multiple accept="*/*" onchange="handleFiles(event)">
</div>

<!-- settings modal -->
<div id="settings-modal">
  <div id="settings-inner">
    <h2>Configuration <button id="close-settings" onclick="closeSettings()">✕</button></h2>
    <div class="setting-row">
      <label>Session goal</label>
      <textarea id="s-goal" rows="2"></textarea>
    </div>
    <div class="setting-row">
      <label>Hive groups (JSON)</label>
      <textarea id="s-groups" rows="2" placeholder='{"Research":["ps5-hive"]}'></textarea>
    </div>
    <div class="setting-row">
      <label>Task destination (owner/repo or blank)</label>
      <input id="s-dest" type="text">
    </div>
    <div class="setting-row">
      <label>Model</label>
      <input id="s-model" type="text">
      <div id="s-favorites" style="margin-top:6px;display:flex;flex-wrap:wrap;gap:4px"></div>
    </div>
    <div class="setting-row">
      <label>Standing instructions</label>
      <textarea id="s-instructions" rows="3"></textarea>
    </div>
    <button id="save-settings" onclick="saveSettings()">Save</button>

    <!-- question handling -->
    <div class="arena-section" id="q-handle-panel">
      <h3>Question Handling</h3>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <label style="color:var(--muted);font-size:11px;flex:1;min-width:160px">
          AI decides if unanswered after
        </label>
        <input id="s-ai-timeout" type="number" min="1" max="1440"
               style="width:56px;background:var(--input-bg);border:1px solid var(--border);
                      color:var(--text);padding:6px 8px;border-radius:4px;font-size:12px">
        <span style="color:var(--muted);font-size:11px">min</span>
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;min-height:44px">
          <input type="checkbox" id="s-ai-auto" style="width:16px;height:16px;cursor:pointer">
          <span style="color:var(--text);font-size:12px">Enabled</span>
        </label>
      </div>
      <div id="s-ai-status" style="font-size:10px;color:var(--muted);margin-top:6px"></div>
    </div>

    <!-- arena panel -->
    <div class="arena-section" id="arena-panel">
      <h3>⚡ Model Arena</h3>
      <div class="champ-row">
        <span class="champ-label">Text champion</span>
        <span class="champ-val" id="arena-text-champ">—</span>
      </div>
      <div class="champ-row">
        <span class="champ-label">Vision champion</span>
        <span class="champ-val" id="arena-vision-champ">—</span>
      </div>
      <div class="champ-row">
        <span class="champ-label">Last run</span>
        <span class="champ-val" id="arena-last-run">—</span>
      </div>
      <button id="run-arena-btn" onclick="runArena()">Run Arena Benchmark</button>
      <div id="arena-status-msg"></div>
      <div id="arena-leaderboard" style="margin-top:10px"></div>
    </div>
  </div>
</div>

<script>
/*__SHARED_RENDER_JS__*/
/*__LOCAL_STATUS_JS__*/
</script>
</body>
</html>
"""

DASHBOARD_HTML = (
    _DASHBOARD_TMPL
    .replace('/*__SHARED_CSS__*/', SHARED_CSS)
    .replace('/*__LOCAL_CSS__*/', LOCAL_CSS)
    .replace('/*__SHARED_RENDER_JS__*/', SHARED_RENDER_JS)
    .replace('/*__LOCAL_STATUS_JS__*/', LOCAL_STATUS_JS)
)


# ── HTTP handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _get_uid(self) -> str:
        """Extract X-Hive-UID header from request (empty string if absent)."""
        uid = (self.headers.get("X-Hive-UID") or "").strip()
        if uid:
            _register_uid(uid)
        return uid

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-Hive-UID")
        self.end_headers()

    def do_DELETE(self):
        self._get_uid()
        with _activity_lock:
            global _last_ui_activity
            _last_ui_activity = time.time()
        if self.path == "/api/chat":
            with chat_lock:
                chat_history.clear()
            self._send_json({"ok": True})
        elif self.path == "/api/tracker/remove":
            try:
                body = json.loads(self._read_body())
                handle = body.get("handle", "").strip()
                if not handle:
                    self._send_json({"error": "handle required"}, 400)
                    return
                hive_status.remove_researcher(handle, updated_by="ui")
                self._send_json({"ok": True, "handle": handle})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
        elif self.path == "/api/queue":
            # DELETE /api/queue — remove all terminal-state items (local, merged, closed)
            _TERMINAL = {"local", "merged", "closed"}
            with queue_lock:
                before = len(task_queue)
                task_queue[:] = [i for i in task_queue if i.get("status") not in _TERMINAL]
                removed = before - len(task_queue)
            _save_queue()
            self._send_json({"ok": True, "removed": removed})
        else:
            # DELETE /api/queue/<id>
            m = re.match(r"^/api/queue/([^/?]+)$", self.path)
            if m:
                qid = m.group(1)
                with queue_lock:
                    before = len(task_queue)
                    task_queue[:] = [i for i in task_queue if i.get("id") != qid]
                    removed = before - len(task_queue)
                _save_queue()
                self._send_json({"ok": True, "removed": removed})
            else:
                self.send_response(404); self.end_headers()

    def do_PATCH(self):
        with _activity_lock:
            global _last_ui_activity
            _last_ui_activity = time.time()
        # PATCH /api/status/blocker/<id>
        m = re.match(r"^/api/status/blocker/([^/?]+)$", self.path)
        if m:
            bid = m.group(1)
            try:
                body = json.loads(self._read_body())
                resolution = body.get("resolution", "")
                hive_status.resolve_blocker(bid, resolution, updated_by="ui")
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return
        # PATCH /api/status/next-step/<id>
        m = re.match(r"^/api/status/next-step/([^/?]+)$", self.path)
        if m:
            nsid = m.group(1)
            try:
                body = json.loads(self._read_body())
                hive_status.update_next_step(nsid, body.get("status","done"),
                                             updated_by="ui")
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return
        self.send_response(404); self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        self._get_uid()   # register uid on every GET (no-op if header absent)

        if p == "/":
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type",   "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif p == "/api/sessions":
            self._send_json(discover_sessions())

        elif p == "/api/snapshot":
            with lock:
                snap = {
                    "combined": list(combined),
                    "sessions": {s: list(buf) for s, buf in buffers.items()},
                }
            self._send_json(snap)

        elif p == "/api/config":
            with config_lock:
                self._send_json(dict(_server_config))

        elif p == "/api/queue":
            with queue_lock:
                self._send_json(list(task_queue))

        elif p == "/api/groups":
            with groups_lock:
                self._send_json({"groups": dict(_groups)})

        elif p == "/api/status":
            self._send_json(hive_status.load())

        elif p == "/api/status/compact":
            # GET — return build_context_block() as plain text for LLM injection
            text = hive_status.build_context_block(max_chars=3000)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(text.encode("utf-8"))

        elif p == "/api/status/questions":
            unanswered_only = "unanswered" in self.path
            self._send_json(hive_status.get_pending_questions(unanswered_only))

        elif p == "/api/doctor/status":
            with doctor_lock:
                self._send_json(dict(_doctor_status))

        elif p == "/api/uid/registry":
            # Orchestrator-accessible view of registered browser uids
            with _uid_lock:
                self._send_json(dict(_uid_registry))

        elif p == "/api/tracker/status":
            if _TRACKER_AVAILABLE:
                self._send_json(researcher_tracker.get_status())
            else:
                self._send_json({"error": "researcher_tracker not available"})

        elif p == "/api/arena/status":
            if _ARENA_AVAILABLE:
                self._send_json(model_arena.get_arena_status())
            else:
                self._send_json({"error": "model_arena not available"})

        elif p == "/api/arena/results":
            if _ARENA_AVAILABLE:
                self._send_json(model_arena.get_arena_results())
            else:
                self._send_json({})

        elif p == "/stream":
            self._handle_log_stream()

        elif p == "/status/stream":
            self._handle_status_stream()

        else:
            self.send_response(404); self.end_headers()

    def _handle_log_stream(self):
        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        last_combined_len  = 0
        try:
            while True:
                with lock:
                    clist        = list(combined)
                    new_combined = clist[last_combined_len:]
                    last_combined_len = len(clist)
                # Only send combined — per-session panels removed, no redundant data
                if new_combined:
                    payload = json.dumps({"combined": new_combined})
                    self.wfile.write(f"data: {payload}\n\n".encode())
                    self.wfile.flush()
                time.sleep(POLL_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _handle_status_stream(self):
        import queue as _queue
        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q = _queue.Queue(maxsize=20)
        hive_status.register_sse_listener(q)

        # Send current status immediately on connect
        try:
            initial = json.dumps(hive_status.get_broadcast_payload())
            self.wfile.write(f"data: {initial}\n\n".encode())
            self.wfile.flush()
        except Exception:
            hive_status.unregister_sse_listener(q)
            return

        try:
            while True:
                try:
                    msg = q.get(timeout=10)  # 10s heartbeat
                    self.wfile.write(f"data: {msg}\n\n".encode())
                except _queue.Empty:
                    # Heartbeat ping
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            hive_status.unregister_sse_listener(q)

    def do_POST(self):
        self._get_uid()
        with _activity_lock:
            global _last_ui_activity
            _last_ui_activity = time.time()
        p = self.path.split("?")[0]

        if p == "/api/config":
            try:
                body = json.loads(self._read_body())
                with config_lock:
                    _server_config.update(
                        {k: v for k, v in body.items() if k in _server_config})
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/upload":
            self._handle_upload()

        elif p == "/api/prompt":
            self._handle_prompt()

        elif p == "/api/queue/poll":
            threading.Thread(target=poll_pr_statuses, daemon=True).start()
            self._send_json({"ok": True})

        elif p == "/api/groups":
            try:
                body = json.loads(self._read_body())
                with groups_lock:
                    _groups.update(body.get("groups", {}))
                _save_groups()
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/status/achievement":
            try:
                body = json.loads(self._read_body())
                hive_status.add_achievement(
                    body.get("hive", HIVE_NAME),
                    body.get("agent", "unknown"),
                    body.get("description", ""),
                    body.get("evidence", ""),
                )
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/status/blocker":
            try:
                body = json.loads(self._read_body())
                bid = hive_status.add_blocker(
                    body.get("hive", HIVE_NAME),
                    body.get("agent", "unknown"),
                    body.get("description", ""),
                    body.get("severity", "medium"),
                )
                self._send_json({"ok": True, "id": bid})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/status/capability":
            try:
                body = json.loads(self._read_body())
                hive_status.add_capability(
                    body.get("source_hive", HIVE_NAME),
                    body.get("source_agent", "unknown"),
                    body.get("skill", ""),
                    body.get("description", ""),
                    body.get("example", ""),
                    body.get("tags", []),
                )
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/status/next-step":
            try:
                body = json.loads(self._read_body())
                nsid = hive_status.add_next_step(
                    body.get("description", ""),
                    body.get("assigned_to", "hive-doctor"),
                    body.get("priority", 5),
                    body.get("source", "manual"),
                )
                self._send_json({"ok": True, "id": nsid})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/status/finding":
            try:
                body = json.loads(self._read_body())
                hive_status.add_finding(
                    body.get("hive", HIVE_NAME),
                    body.get("summary", ""),
                    body.get("source", "observation"),
                )
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/status/question":
            try:
                body = json.loads(self._read_body())
                qid = hive_status.add_question(
                    body.get("hive", HIVE_NAME),
                    body.get("agent", "unknown"),
                    body.get("question", ""),
                    body.get("hint", ""),
                    body.get("type", "text"),
                    body.get("choices"),
                    body.get("required", True),
                )
                self._send_json({"ok": True, "id": qid})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/status/answer":
            try:
                body = json.loads(self._read_body())
                hive_status.answer_question(
                    body.get("id", ""),
                    body.get("answer", ""),
                    body.get("answered_by", "human"),
                )
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/status/compact":
            # POST — store orchestrator compaction summary
            try:
                body = json.loads(self._read_body())
                sid = hive_status.update_orchestrator_session(
                    summary    = body.get("summary", ""),
                    goal       = body.get("goal", ""),
                    progress   = body.get("progress", ""),
                    next_steps = body.get("next_steps", []),
                    decisions  = body.get("decisions", []),
                    updated_by = "opencode",
                )
                self._send_json({"ok": True, "id": sid})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/tracker/add":
            # POST — add or update a tracked researcher
            try:
                body = json.loads(self._read_body())
                handle = body.get("handle", "").strip()
                if not handle:
                    self._send_json({"error": "handle required"}, 400)
                    return
                hive_status.add_researcher(
                    handle        = handle,
                    platform      = body.get("platform", "github"),
                    keywords      = body.get("keywords", []),
                    context       = body.get("context", ""),
                    priority_repos= body.get("priority_repos", []),
                    updated_by    = "ui",
                )
                self._send_json({"ok": True, "handle": handle})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        elif p == "/api/arena/run":
            try:
                _raw = self._read_body()
                body = json.loads(_raw) if _raw else {}
                arena_type = body.get("arena_type", "text") if isinstance(body, dict) else "text"
                with _arena_lock:
                    running = _arena_job["running"]
                if running:
                    self._send_json({"message": "Arena already running", "running": True})
                elif not _ARENA_AVAILABLE:
                    self._send_json({"error": "model_arena module not available"})
                elif not OPENROUTER_KEY:
                    self._send_json({"error": "OPENROUTER_API_KEY not set"})
                else:
                    _run_arena_async(arena_type)
                    self._send_json({"message": f"Arena ({arena_type}) started", "running": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)

        else:
            self.send_response(404); self.end_headers()

    # ── upload ────────────────────────────────────────────────────────────────

    def _handle_upload(self):
        ct = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ct:
            self._send_json({"error": "expected multipart/form-data"}, 400)
            return
        length = int(self.headers.get("Content-Length", 0))
        if length > UPLOAD_MAX_BYTES:
            # Drain the request body in chunks before responding so the
            # client can read the 413 without getting EPIPE / connection reset.
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            self._send_json({"error": "file too large (max 10 MB)"}, 413)
            return
        body = self._read_body()
        try:
            fields = _parse_multipart(ct, body)
        except Exception as e:
            self._send_json({"error": f"parse error: {e}"}, 400)
            return
        file_field = fields.get("file")
        if not file_field or not isinstance(file_field, tuple):
            self._send_json({"error": "no file field"}, 400)
            return
        filename, mime, data_bytes = file_field
        att = _detect_attachment(filename, mime, data_bytes)
        aid = uuid.uuid4().hex[:12]
        with uploads_lock:
            if len(uploads_order) >= UPLOAD_KEEP:
                old_id = uploads_order[0]
                uploads.pop(old_id, None)
            uploads[aid] = att
            uploads_order.append(aid)
        self._send_json({
            "id":       aid,
            "filename": filename,
            "mime":     mime,
            "type":     att["type"],
            "is_image": att["type"] == "image",
            "size":     att["size"],
        })

    # ── prompt ────────────────────────────────────────────────────────────────

    def _handle_prompt(self):
        try:
            body = json.loads(self._read_body())
        except Exception:
            self._send_json({"error": "invalid JSON"}, 400)
            return
        prompt         = body.get("prompt", "").strip()
        attachment_ids = body.get("attachment_ids", [])
        model          = body.get("model") or OPENROUTER_MODEL
        task_dest      = body.get("task_dest", "").strip()
        instructions   = body.get("instructions", "").strip()
        is_priority    = bool(body.get("priority", False))

        if not prompt:
            self._send_json({"error": "empty prompt"}, 400)
            return

        with chat_lock:
            history = list(chat_history)

        messages = _build_messages(prompt, attachment_ids, history, instructions)
        api_key  = OPENROUTER_KEY

        item_id  = uuid.uuid4().hex[:8]
        summary  = prompt[:120] + ("…" if len(prompt) > 120 else "")
        item = {
            "id":         item_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "summary":    summary,
            "status":     "queued",
            "priority":   is_priority,
            "pr_number":  None,
            "pr_url":     None,
            "model":      model,
            "task_dest":  task_dest,
            "thread":     [{"role": "user", "content": prompt}],
        }
        with queue_lock:
            if is_priority:
                task_queue.insert(0, item)  # front of queue
            else:
                task_queue.append(item)
        _save_queue()

        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def _emit(obj):
            try:
                self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        _emit({"queue_item": item})

        q = queue.Queue()
        t = threading.Thread(target=_stream_llm,
                             args=(messages, model, api_key, LLM_BASE_URL, q),
                             daemon=True)
        t.start()
        full_text = []
        try:
            while True:
                chunk = q.get(timeout=90)
                if "delta" in chunk:
                    full_text.append(chunk["delta"])
                    _emit({"delta": chunk["delta"]})
                elif "done" in chunk:
                    _emit({"done": True})
                    break
                elif "error" in chunk:
                    _emit({"error": chunk["error"]})
                    break
        except queue.Empty:
            _emit({"error": "LLM timeout after 90s"})

        self.wfile.write(b"data: [DONE]\n\n")
        try:
            self.wfile.flush()
        except Exception:
            pass

        assistant_reply = "".join(full_text)
        with chat_lock:
            chat_history.append({"role": "user",      "content": prompt})
            chat_history.append({"role": "assistant", "content": assistant_reply})
            while len(chat_history) > CHAT_HISTORY_MAX:
                chat_history.pop(0)

        with queue_lock:
            for i in task_queue:
                if i["id"] == item_id:
                    i["thread"].append({"role": "assistant",
                                        "content": assistant_reply})
                    break
        _save_queue()
        hive_status.increment_metric("openrouter_calls_today", updated_by="system")

        if task_dest:
            threading.Thread(target=_background_pr, args=(item, task_dest),
                             daemon=True).start()
        else:
            with queue_lock:
                for i in task_queue:
                    if i["id"] == item_id:
                        i["status"] = "local"
                        break
            _save_queue()


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _load_queue()
    _load_groups()
    hive_status.get_or_create()   # ensure status file exists

    # ── Startup cleanup (sk_cycle_cleanup / sk_no_stop) ───────────────────
    # Applied at every server start so stale state never accumulates across
    # cycles. Each rule here corresponds to a learned skill in capabilities.
    try:
        import subprocess as _sp
        _s = hive_status.load()
        _now_ts = __import__('datetime').datetime.now(
            __import__('datetime').timezone.utc
        ).isoformat(timespec='seconds').replace('+00:00', 'Z')

        # 1. Correct active_model (sk_model_verify)
        _s.setdefault('hives', {}).setdefault('default', {})['active_model'] = OPENROUTER_MODEL

        # 2. Sync live tmux sessions into hives.default.sessions (sk_cycle_cleanup)
        # NOTE: orchestrator_sessions is a FIFO ring of compaction summary DICTS
        # (written by update_orchestrator_session). Do NOT overwrite it with a
        # flat string list — that crashes build_context_block() with AttributeError.
        # Also repair any existing corruption: strip out string entries from the ring.
        _tmux = _sp.run(['tmux', 'list-sessions', '-F', '#{session_name}'],
                        capture_output=True, text=True)
        _sessions = [x.strip() for x in _tmux.stdout.strip().split('\n') if x.strip()]
        _s['hives']['default']['sessions'] = _sessions
        # Sanitize orchestrator_sessions: keep only dict entries, discard strings
        _s['orchestrator_sessions'] = [
            e for e in _s.get('orchestrator_sessions', []) if isinstance(e, dict)
        ]

        # 3. Resolve stale 404/429/test blockers (sk_cycle_cleanup)
        for _b in _s.get('blockers', []):
            if _b.get('status') == 'open':
                _desc = _b.get('description', '')
                if any(x in _desc for x in ('HTTP 404', 'HTTP 429', 'test blocker', 'Test blocker')):
                    _b['status']      = 'resolved'
                    _b['resolved_at'] = _now_ts
                    _b['resolution']  = 'Auto-resolved at startup: transient/stale blocker.'

        # 4. Purge test-scaffold junk from KB (sk_cycle_cleanup)
        _TEST_HIVES = ('test-hive', 'test')
        _TEST_TOKENS = ('T60 test', 'T61 test', 'T62 test', 'What is 2+2?',
                        'T59 test', 'hello hive world', 'Reply with exactly')
        def _is_test_entry(e):
            if e.get('hive', '') in _TEST_HIVES:
                return True
            blob = (e.get('description', '') + e.get('summary', '') +
                    e.get('question', '') + e.get('rule', ''))
            return any(t in blob for t in _TEST_TOKENS)

        _s['blockers']    = [b for b in _s.get('blockers', [])    if not _is_test_entry(b)]
        _s['next_steps']  = [n for n in _s.get('next_steps', [])  if not _is_test_entry(n)]
        _s['knowledge']['findings'] = [
            f for f in _s['knowledge'].get('findings', []) if not _is_test_entry(f)]
        _s['pending_questions'] = [
            q for q in _s.get('pending_questions', []) if not _is_test_entry(q)]

        # 5. Deduplicate achievements — keep newest per (hive, description) pair;
        #    also drop test-hive entries (sk_cycle_cleanup)
        _seen_ach = set()
        _deduped_ach = []
        for _a in reversed(_s.get('achievements', [])):   # newest-first after reverse
            _key = (_a.get('hive', ''), _a.get('description', ''))
            if _key in _seen_ach or _a.get('hive', '') in _TEST_HIVES:
                continue
            _seen_ach.add(_key)
            _deduped_ach.append(_a)
        _s['achievements'] = list(reversed(_deduped_ach))  # restore chronological order

        # 6. Purge stale test items from the task queue file (sk_cycle_cleanup)
        try:
            with open(QUEUE_FILE) as _qf:
                _queue_items = __import__('json').load(_qf)
            _queue_items = [
                _qi for _qi in _queue_items
                if not any(t in _qi.get('summary', '') for t in _TEST_TOKENS)
            ]
            with open(QUEUE_FILE, 'w') as _qf:
                __import__('json').dump(_queue_items, _qf)
        except Exception:
            pass  # queue file may not exist yet — fine

        _s['last_updated'] = _now_ts
        _s['updated_by']   = 'startup-cleanup'
        hive_status.save(_s)
        print(f"[hive-ui] startup cleanup done — model={OPENROUTER_MODEL} sessions={_sessions}")
    except Exception as _e:
        print(f"[hive-ui] startup cleanup error (non-fatal): {_e}")
    # ── end startup cleanup ───────────────────────────────────────────────

    threading.Thread(target=poll_loop,              daemon=True).start()
    threading.Thread(target=pr_poll_loop,           daemon=True).start()
    threading.Thread(target=doctor_loop,            daemon=True).start()
    threading.Thread(target=github_sync_loop,       daemon=True).start()
    threading.Thread(target=question_timeout_loop,  daemon=True).start()

    if _TRACKER_AVAILABLE:
        threading.Thread(target=researcher_tracker.run_loop, daemon=True).start()

    if _ARENA_AVAILABLE and OPENROUTER_KEY:
        model_arena.start_model_watcher(OPENROUTER_KEY, interval_hours=6.0)

    print(f"[hive-ui] port={PORT}")
    print(f"[hive-ui] model={OPENROUTER_MODEL}")
    print(f"[hive-ui] tasks_repo={GITHUB_TASKS_REPO}")
    print(f"[hive-ui] arena={'enabled' if _ARENA_AVAILABLE else 'disabled'}")
    print(f"[hive-ui] tracker={'enabled' if _TRACKER_AVAILABLE else 'disabled'}")

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
