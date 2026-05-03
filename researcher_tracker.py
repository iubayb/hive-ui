#!/usr/bin/env python3
"""
researcher_tracker.py — Generic external researcher skill tracker.

Polls GitHub for new commits, READMEs, and releases from configured
researchers, extracts relevant technical findings with a single batched
LLM call per cycle, and injects them into hive_status.

All researcher identity (handle, platform, keywords, context, priority
repos) lives in hive_status.tracked_researchers[], set at runtime via
/api/tracker/add.  This file contains zero user-specific strings.

Public API
----------
  run_once()          → int   # new findings added this cycle
  run_loop()          → None  # blocking daemon loop; call in a thread
  get_status()        → dict  # last run summary for /api/tracker/status
"""

import base64, hashlib, http.client, json, os, random, ssl, sys, time, traceback

sys.path.insert(0, os.path.dirname(__file__))
import hive_status

# ── constants ─────────────────────────────────────────────────────────────────

STATE_DIR        = "/tmp"
TRACKER_INTERVAL = 7200     # 2 h base; actual sleep = base ± 5 min jitter
MAX_REPOS        = 10       # cap on auto-discovered repos per researcher
GH_API_HOST      = "api.github.com"
COMMITS_PER_REPO = 5
LLM_MAX_TOKENS   = 600
LLM_BATCH_CHARS  = 6000

_HIVE_UI_URL = os.environ.get("HIVE_UI_URL", "https://openrouter.ai")

# ── env fallback chain ────────────────────────────────────────────────────────

def _read_env_file() -> dict:
    candidates = [
        os.environ.get("HIVE_ENV_FILE", ""),
        os.path.expanduser("~/.config/hive-ui/env"),
        os.path.expanduser("~/.config/research-hive/env"),
    ]
    for path in candidates:
        if not path:
            continue
        try:
            pairs = {}
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, _, v = line.partition("=")
                        pairs[k.strip()] = v.strip()
            return pairs
        except OSError:
            continue
    return {}

# ── per-researcher state ───────────────────────────────────────────────────────

_state_lock = __import__("threading").Lock()

def _state_file(handle: str) -> str:
    safe = handle.lower().replace("/", "_").replace("\\", "_")
    return f"{STATE_DIR}/researcher-tracker-{safe}.json"

def _load_state(handle: str) -> dict:
    try:
        with open(_state_file(handle)) as f:
            return json.load(f)
    except Exception:
        return {
            "repo_shas":      {},
            "readme_hashes":  {},
            "findings_count": 0,
            "last_run":       None,
            "last_finding":   None,
            "errors":         0,
        }

def _save_state(handle: str, s: dict):
    try:
        with open(_state_file(handle), "w") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass

# ── runtime status (read by /api/tracker/status) ─────────────────────────────

_runtime_status = {
    "last_run":           None,
    "last_run_new":       0,
    "findings_count":     0,
    "researchers_active": 0,
    "last_finding":       None,
    "errors_consecutive": 0,
}

def get_status() -> dict:
    return dict(_runtime_status)

# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _gh_get(path: str) -> "dict | list | None":
    """Unauthenticated GitHub API GET. Returns parsed JSON or None on error."""
    try:
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection(GH_API_HOST, context=ctx, timeout=12)
        conn.request("GET", path, headers={
            "User-Agent": "hive-ui/1.0",
            "Accept":     "application/vnd.github.v3+json",
        })
        resp = conn.getresponse()
        raw  = resp.read().decode("utf-8", errors="replace")
        conn.close()
        if resp.status == 200:
            return json.loads(raw)
        if resp.status == 403:
            _runtime_status["errors_consecutive"] = (
                _runtime_status.get("errors_consecutive", 0) + 1
            )
        return None
    except Exception:
        return None


def _discover_repos(handle: str, keywords: list, priority_repos: list) -> list:
    """
    Return list of full_name strings for this user's public repos,
    filtered by the researcher's keyword list, capped at MAX_REPOS.
    """
    data = _gh_get(f"/users/{handle}/repos?sort=pushed&per_page=30")
    if not isinstance(data, list):
        return list(priority_repos)[:MAX_REPOS]

    kw_set = {k.lower() for k in keywords if k}
    found  = []
    for repo in data:
        name  = (repo.get("name") or "").lower()
        desc  = (repo.get("description") or "").lower()
        combo = f"{name} {desc}"
        if kw_set and any(kw in combo for kw in kw_set):
            found.append(repo["full_name"])

    # Priority repos come first, then discovered ones
    merged = list(priority_repos)
    for f in found:
        if f not in merged:
            merged.append(f)
    return merged[:MAX_REPOS]


def _fetch_commits(full_name: str, count: int = COMMITS_PER_REPO) -> list:
    data = _gh_get(f"/repos/{full_name}/commits?per_page={count}")
    if not isinstance(data, list):
        return []
    results = []
    for c in data:
        commit = c.get("commit", {})
        results.append({
            "sha":     c.get("sha", "")[:12],
            "message": commit.get("message", "").split("\n")[0][:200],
            "date":    commit.get("author", {}).get("date", "")[:10],
            "author":  commit.get("author", {}).get("name", ""),
        })
    return results


def _fetch_readme(full_name: str) -> str:
    data = _gh_get(f"/repos/{full_name}/readme")
    if not isinstance(data, dict):
        return ""
    try:
        raw = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        return raw[:3000]
    except Exception:
        return ""


def _fetch_repo_meta(full_name: str) -> dict:
    data = _gh_get(f"/repos/{full_name}")
    if not isinstance(data, dict):
        return {}
    return {
        "name":        data.get("name", ""),
        "description": (data.get("description") or "")[:200],
        "stars":       data.get("stargazers_count", 0),
        "language":    data.get("language", ""),
        "pushed_at":   (data.get("pushed_at") or "")[:10],
        "topics":      data.get("topics", []),
    }

# ── LLM extraction ─────────────────────────────────────────────────────────────

def _call_llm(content: str, api_key: str, model: str, system_prompt: str) -> list:
    """
    Single non-streaming OpenRouter call. Returns list of finding strings.
    Falls back to [] on any error — tracker never blocks on LLM.
    """
    if not api_key or not content.strip():
        return []
    body = json.dumps({
        "model":    model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": content[:LLM_BATCH_CHARS]},
        ],
        "stream":     False,
        "max_tokens": LLM_MAX_TOKENS,
    }).encode("utf-8")
    headers = {
        "Content-Type":   "application/json",
        "Authorization":  f"Bearer {api_key}",
        "HTTP-Referer":   _HIVE_UI_URL,
        "X-Title":        "Hive Researcher Tracker",
        "Content-Length": str(len(body)),
    }
    try:
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("openrouter.ai", context=ctx, timeout=45)
        conn.request("POST", "/api/v1/chat/completions", body=body, headers=headers)
        resp = conn.getresponse()
        raw  = resp.read().decode("utf-8", errors="replace")
        conn.close()
        if resp.status != 200:
            return []
        data = json.loads(raw)
        text = (data.get("choices", [{}])[0]
                    .get("message", {}).get("content", ""))
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        findings = json.loads(text)
        if isinstance(findings, list):
            return [str(f) for f in findings if str(f).strip()]
        return []
    except Exception:
        return []

# ── per-researcher cycle ───────────────────────────────────────────────────────

def _run_researcher(researcher: dict, api_key: str, model: str) -> int:
    """
    Run one tracker cycle for a single researcher config dict.
    Returns number of new findings added.

    researcher keys:
      handle        (str)  — GitHub username
      platform      (str)  — "github" (others reserved)
      keywords      (list) — repo/description filter terms
      context       (str)  — LLM system prompt; should describe what to extract
      priority_repos(list) — full_name strings to always watch
    """
    handle         = researcher.get("handle", "")
    keywords       = researcher.get("keywords", [])
    context        = researcher.get("context", (
        "You are a technical research assistant. Analyse the developer activity below. "
        "Extract ONLY concrete, actionable technical findings. "
        "Output a JSON array of finding strings. Each finding: ≤80 words, "
        "present-tense, technically precise. Return [] if nothing actionable found."
    ))
    priority_repos = researcher.get("priority_repos", [])
    hive_tag       = f"external/{handle.lower()}"

    if not handle:
        return 0

    with _state_lock:
        state = _load_state(handle)

    repos = _discover_repos(handle, keywords, priority_repos)

    batch_parts = []
    new_shas    = {}
    new_readmes = {}

    for full_name in repos:
        commits = _fetch_commits(full_name)
        if not commits:
            continue

        head_sha   = commits[0]["sha"]
        stored_sha = state["repo_shas"].get(full_name, "")

        if not stored_sha:
            meta   = _fetch_repo_meta(full_name)
            readme = _fetch_readme(full_name)
            rdmd5  = hashlib.md5(readme.encode()).hexdigest()
            new_shas[full_name]    = head_sha
            new_readmes[full_name] = rdmd5
            part = (
                f"=== REPO: {full_name} ===\n"
                f"Stars: {meta.get('stars')} | Lang: {meta.get('language')} | "
                f"Last pushed: {meta.get('pushed_at')}\n"
                f"Description: {meta.get('description')}\n"
                f"Topics: {', '.join(meta.get('topics', []))}\n\n"
                f"README (first 2000 chars):\n{readme[:2000]}\n\n"
                f"Recent commits:\n" +
                "\n".join(f"  [{c['date']}] {c['message']}" for c in commits[:5])
            )
            batch_parts.append(part)
        else:
            new_commits = []
            for c in commits:
                if c["sha"][:12] == stored_sha[:12]:
                    break
                new_commits.append(c)
            if new_commits:
                new_shas[full_name] = head_sha
                part = (
                    f"=== REPO: {full_name} — {len(new_commits)} new commit(s) ===\n" +
                    "\n".join(f"  [{c['date']}] {c['message']}" for c in new_commits)
                )
                batch_parts.append(part)

            stored_rdmd5 = state["readme_hashes"].get(full_name, "")
            if not stored_rdmd5:
                readme = _fetch_readme(full_name)
                rdmd5  = hashlib.md5(readme.encode()).hexdigest()
                if rdmd5 != stored_rdmd5:
                    new_readmes[full_name] = rdmd5
                    batch_parts.append(
                        f"=== README UPDATE: {full_name} ===\n{readme[:1500]}"
                    )

    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if not batch_parts:
        with _state_lock:
            state["last_run"] = now_str
            _save_state(handle, state)
        return 0

    batch_text = "\n\n".join(batch_parts)
    findings   = _call_llm(batch_text, api_key, model, context)

    # Fallback: store commit summaries as raw findings if LLM unavailable
    if not findings:
        for part in batch_parts[:3]:
            lines = [l for l in part.splitlines() if l.strip().startswith("[")][:3]
            if lines:
                findings.append(
                    f"{handle} recent activity: " +
                    " | ".join(l.strip() for l in lines)
                )

    added = 0
    for finding in findings:
        if len(finding.strip()) < 10:
            continue
        hive_status.add_finding(
            hive    = hive_tag,
            summary = finding,
            source  = f"{handle}-github",
        )
        added += 1
        _runtime_status["last_finding"] = finding[:120]

    with _state_lock:
        state["repo_shas"].update(new_shas)
        state["readme_hashes"].update(new_readmes)
        state["findings_count"] = state.get("findings_count", 0) + added
        state["last_run"]       = now_str
        state["errors"]         = 0
        _save_state(handle, state)

    return added


# ── public run_once / run_loop ────────────────────────────────────────────────

def run_once(api_key: str = "", model: str = "") -> int:
    """
    Run one tracker cycle for all configured researchers.
    Returns total new findings added.
    """
    if not api_key:
        env = _read_env_file()
        api_key = os.environ.get("OPENROUTER_API_KEY") or env.get("OPENROUTER_API_KEY", "")
    if not model:
        status = hive_status.load()
        model  = (status.get("model_champions", {}).get("text")
                  or "nousresearch/hermes-3-llama-3.1-405b:free")

    researchers = hive_status.get_tracked_researchers()
    _runtime_status["researchers_active"] = len(researchers)

    if not researchers:
        _runtime_status["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return 0

    total = 0
    for researcher in researchers:
        try:
            n = _run_researcher(researcher, api_key, model)
            total += n
            _runtime_status["findings_count"] = (
                _runtime_status.get("findings_count", 0) + n
            )
        except Exception:
            _runtime_status["errors_consecutive"] = (
                _runtime_status.get("errors_consecutive", 0) + 1
            )

    _runtime_status["last_run"]     = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _runtime_status["last_run_new"] = total
    if total > 0:
        _runtime_status["errors_consecutive"] = 0
    return total


def run_loop():
    """
    Background daemon loop. Calls run_once() every TRACKER_INTERVAL ± jitter.
    Idles gracefully when no researchers are configured.
    Catches all exceptions — tracker must never bring down the server.
    """
    time.sleep(30)   # stagger: let server fully start first
    while True:
        try:
            added = run_once()
            researchers = hive_status.get_tracked_researchers()
            if researchers:
                tag = f"+{added} findings" if added else "no new findings"
                print(f"[researcher-tracker] cycle complete — {tag} "
                      f"({len(researchers)} researcher(s))", flush=True)
            else:
                print("[researcher-tracker] idle — no researchers configured", flush=True)
        except Exception:
            _runtime_status["errors_consecutive"] = (
                _runtime_status.get("errors_consecutive", 0) + 1
            )
            if _runtime_status["errors_consecutive"] >= 3:
                try:
                    hive_status.add_blocker(
                        hive="researcher-tracker",
                        agent="tracker",
                        description="Researcher tracker failing repeatedly — check network/API",
                        severity="low",
                    )
                except Exception:
                    pass

        jitter  = random.randint(-300, 300)
        sleep_s = max(600, TRACKER_INTERVAL + jitter)
        time.sleep(sleep_s)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys
    researchers = hive_status.get_tracked_researchers()
    print(f"[researcher-tracker] {len(researchers)} researcher(s) configured")
    n = run_once()
    print(f"[researcher-tracker] done — {n} new findings added to hive_status")
    if "--loop" in _sys.argv:
        print("[researcher-tracker] entering loop...")
        run_loop()
