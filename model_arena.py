#!/usr/bin/env python3
"""
Model Arena — automatic free-tier model benchmarking and champion selection.

Two arenas:
  text   — chat / hive-doctor reasoning (no vision required)
  vision — UX screenshot analysis (image input required)

Top-5 per arena are selected by estimated parameter count, then benchmarked
in parallel threads.  Results + champion written to /tmp/.

Public API (used by logstream.py):
  run_arena(arena_type, api_key, force=False) → results dict
  get_champion(arena_type) → model_id str or None
  fetch_and_register_free_models(api_key) → (all_models, new_model_ids)
  get_arena_status() → dict
  get_arena_results() → dict
"""

import base64, http.client, io, json, os, queue, ssl, struct, threading
import time, traceback, urllib.parse, zlib
from concurrent.futures import ThreadPoolExecutor, as_completed

_HIVE_UI_URL = os.environ.get("HIVE_UI_URL", "https://openrouter.ai")

# ── file paths ────────────────────────────────────────────────────────────────
CHAMPION_FILE  = "/tmp/hive-model-champion.json"
RESULTS_FILE   = "/tmp/hive-model-benchmark.json"
REGISTRY_FILE  = "/tmp/hive-model-registry.json"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1"

# ── known param counts (billions total) for free-tier candidates ──────────────
# Higher = considered "larger". Used to pick top-5.
PARAM_BILLIONS = {
    # text arena
    "inclusionai/ling-2.6-1t:free":                    1000,
    "qwen/qwen3-coder:free":                            480,
    "nousresearch/hermes-3-llama-3.1-405b:free":        405,
    "openai/gpt-oss-120b:free":                         120,
    "nvidia/nemotron-3-super-120b-a12b:free":            120,
    "minimax/minimax-m2.5:free":                        100,
    "tencent/hy3-preview:free":                         100,
    "qwen/qwen3-next-80b-a3b-instruct:free":             80,
    "meta-llama/llama-3.3-70b-instruct:free":            70,
    "nvidia/nemotron-3-nano-30b-a3b:free":               30,
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free": 24,
    "openai/gpt-oss-20b:free":                           20,
    "z-ai/glm-4.5-air:free":                             10,
    # vision arena
    "google/gemma-4-31b-it:free":                        31,
    "google/gemma-4-26b-a4b-it:free":                    26,
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": 30,
    "google/gemma-3-27b-it:free":                        27,
    "nvidia/nemotron-nano-12b-v2-vl:free":               12,
    "google/gemma-3-12b-it:free":                        12,
    "google/gemma-3-4b-it:free":                          4,
}

TOP_N = 5          # candidates per arena
TASK_TIMEOUT = 30  # seconds per LLM call
MAX_WORKERS  = 5   # parallel model threads per arena

# ── minimal test PNG (100×80 px UI mockup) ────────────────────────────────────

def _make_test_png_b64() -> str:
    """Return a base64-encoded PNG with coloured UI mock-up rectangles."""
    W, H = 100, 80
    rows = []
    for y in range(H):
        row = [0]   # filter byte
        for x in range(W):
            # dark bg
            r, g, b = 13, 17, 23
            # blue "Send" button (5-45, 5-25)
            if 5 <= x <= 45 and 5 <= y <= 25:
                r, g, b = 31, 109, 255
            # green "OK" button (50-95, 5-25)
            elif 50 <= x <= 95 and 5 <= y <= 25:
                r, g, b = 63, 185, 80
            # input field (5-95, 35-55)
            elif 5 <= x <= 95 and 35 <= y <= 55:
                r, g, b = 22, 27, 34
            # sticky bottom bar (0-100, 65-80)
            elif y >= 65:
                r, g, b = 22, 27, 34
            row += [r, g, b]
        rows.append(bytes(row))

    raw = b"".join(rows)
    compressed = zlib.compress(raw)

    def _pack_chunk(tag: bytes, data: bytes) -> bytes:
        ln = struct.pack(">I", len(data))
        body = tag + data
        crc  = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return ln + body + crc

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png  = (b"\x89PNG\r\n\x1a\n"
            + _pack_chunk(b"IHDR", ihdr)
            + _pack_chunk(b"IDAT", compressed)
            + _pack_chunk(b"IEND", b""))
    return base64.b64encode(png).decode()

_TEST_PNG_B64 = _make_test_png_b64()

# ── OpenRouter model list ─────────────────────────────────────────────────────

def fetch_free_models(api_key: str) -> dict:
    """
    Return {model_id: {ctx, inputs, name}} for all free models on OpenRouter
    with ctx >= 32k, excluding tiny/audio/OCR/routing models.
    """
    SKIP = {"lyria", "safeguard", "owl-alpha", "openrouter/free",
            "3n-e2b", "3n-e4b", "1.2b", "baidu"}
    try:
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection("openrouter.ai", context=ctx, timeout=20)
        conn.request("GET", "/api/v1/models",
                     headers={"Authorization": f"Bearer {api_key}"})
        resp = conn.getresponse()
        raw  = resp.read().decode("utf-8", errors="replace")
        conn.close()
        data = json.loads(raw).get("data", [])
    except Exception as e:
        return {}

    result = {}
    for m in data:
        mid = m.get("id", "")
        if any(s in mid for s in SKIP):
            continue
        pricing = m.get("pricing", {})
        cost    = float(pricing.get("prompt", "0") or "0")
        if cost != 0:
            continue
        ctx_len = m.get("context_length", 0) or 0
        if ctx_len < 32768:
            continue
        arch   = m.get("architecture", {})
        inputs = arch.get("input_modalities", ["text"])
        result[mid] = {
            "ctx":    ctx_len,
            "inputs": inputs,
            "name":   m.get("name", mid),
        }
    return result


def fetch_and_register_free_models(api_key: str):
    """
    Fetch current free models, compare against registry, return (all_models, new_ids).
    Updates REGISTRY_FILE.
    """
    models   = fetch_free_models(api_key)
    registry = _load_registry()
    new_ids  = [mid for mid in models if mid not in registry]
    now      = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for mid in new_ids:
        registry[mid] = {"first_seen": now}
    _save_registry(registry)
    return models, new_ids


def _load_registry() -> dict:
    try:
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_registry(reg: dict):
    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump(reg, f, indent=2)
    except Exception:
        pass

# ── parameter count estimation ────────────────────────────────────────────────

def _estimate_params(model_id: str) -> float:
    """Return estimated billions of total params for a model id."""
    if model_id in PARAM_BILLIONS:
        return float(PARAM_BILLIONS[model_id])
    # Try to parse from name: e.g. "120b", "1t", "405b", "a3b" (active, less weight)
    import re
    parts = re.findall(r"(\d+(?:\.\d+)?)(t|b)(?!\w)", model_id.lower())
    best = 0.0
    for num, unit in parts:
        val = float(num) * (1000 if unit == "t" else 1)
        if val > best:
            best = val
    return best if best > 0 else 1.0


def select_top_n(models: dict, arena_type: str, n: int = TOP_N) -> list:
    """
    Filter models for the arena type and return top-n by param count.
    arena_type: 'text' or 'vision'
    """
    filtered = []
    for mid, info in models.items():
        inputs = info.get("inputs", ["text"])
        if arena_type == "vision":
            if "image" not in inputs:
                continue
            # Exclude pure-audio omni models from vision arena if they have audio issues
        else:
            # text arena: skip models that require image input only
            if inputs == ["image"]:
                continue
        filtered.append((mid, _estimate_params(mid)))
    filtered.sort(key=lambda x: x[1], reverse=True)
    return [mid for mid, _ in filtered[:n]]


# ── LLM call helper (blocking, no streaming) ─────────────────────────────────

def _call_llm(model_id: str, messages: list, api_key: str,
              timeout: int = TASK_TIMEOUT) -> tuple:
    """
    Call OpenRouter non-streaming.
    Returns (response_text, elapsed_ms, error_str_or_None).
    """
    body = json.dumps({
        "model":      model_id,
        "messages":   messages,
        "stream":     False,
        "max_tokens": 512,
    }).encode("utf-8")

    headers = {
        "Content-Type":   "application/json",
        "Authorization":  f"Bearer {api_key}",
        "HTTP-Referer":   _HIVE_UI_URL,
        "X-Title":        "Hive UI Arena",
        "Content-Length": str(len(body)),
    }
    t0 = time.time()
    try:
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("openrouter.ai", context=ctx,
                                           timeout=timeout)
        conn.request("POST", "/api/v1/chat/completions",
                     body=body, headers=headers)
        resp     = conn.getresponse()
        raw      = resp.read().decode("utf-8", errors="replace")
        conn.close()
        elapsed  = int((time.time() - t0) * 1000)
        if resp.status != 200:
            return "", elapsed, f"HTTP {resp.status}: {raw[:200]}"
        data     = json.loads(raw)
        text     = (data.get("choices", [{}])[0]
                        .get("message", {}).get("content", ""))
        return text, elapsed, None
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        return "", elapsed, str(e)


def _strip_json(text: str) -> str:
    """Strip markdown code fences and whitespace around JSON."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        # drop first and last fence lines
        inner = []
        for line in lines[1:]:
            if line.strip().startswith("```"):
                break
            inner.append(line)
        t = "\n".join(inner).strip()
    return t


def _try_parse_json(text: str):
    """Return parsed dict/list or None."""
    try:
        return json.loads(_strip_json(text))
    except Exception:
        return None


# ── benchmark tasks ───────────────────────────────────────────────────────────

def _task_json_tool_call(model_id: str, api_key: str) -> dict:
    """Score 0-3: model correctly invokes a tool schema as JSON."""
    tool_schema = json.dumps({
        "name": "check_session",
        "description": "Check if a tmux session is healthy",
        "parameters": {
            "type": "object",
            "properties": {
                "session_name":     {"type": "string"},
                "timeout_seconds":  {"type": "integer"}
            },
            "required": ["session_name"]
        }
    })
    prompt = (
        f"Tool schema:\n{tool_schema}\n\n"
        "User: Check if the session-a session is healthy with a 30 second timeout.\n\n"
        'Return ONLY a JSON object with keys "tool" and "arguments". No explanation.'
    )
    text, ms, err = _call_llm(model_id,
                               [{"role": "user", "content": prompt}], api_key)
    score = 0
    detail = ""
    if err:
        detail = f"error: {err[:80]}"
    else:
        obj = _try_parse_json(text)
        if obj and isinstance(obj, dict):
            score += 1  # valid JSON
            tool_val = str(obj.get("tool", "")).lower()
            if "check" in tool_val or "session" in tool_val:
                score += 1  # correct tool name
            args = obj.get("arguments", obj.get("parameters", {}))
            if isinstance(args, dict) and "session_name" in args:
                score += 1  # correct args
            detail = f"tool={obj.get('tool')} args={list(args.keys()) if isinstance(args,dict) else '?'}"
        else:
            detail = f"not JSON: {text[:60]}"
    return {"score": score, "max": 3, "ms": ms, "detail": detail}


def _task_hive_diagnosis(model_id: str, api_key: str) -> dict:
    """Score 0-3: diagnose log error and return structured JSON."""
    logs = (
        "[session-a] 14:22:15 Starting build...\n"
        "[session-a] 14:22:16 Compiling src/main.c\n"
        "[session-a] 14:22:17 ERROR: Segmentation fault (core dumped)\n"
        "[session-a] 14:22:17 Build failed with exit code 139\n"
        "[session-a] 14:22:48 ERROR: Segmentation fault (core dumped)\n"
        "[session-a] 14:22:48 Retrying in 30s..."
    )
    prompt = (
        f"Analyze these tmux session logs:\n{logs}\n\n"
        'Return ONLY JSON: {"diagnosis":"one sentence","fix_command":"shell command","severity":"low|medium|high|critical"}'
    )
    text, ms, err = _call_llm(model_id,
                               [{"role": "user", "content": prompt}], api_key)
    score = 0
    detail = ""
    if err:
        detail = f"error: {err[:80]}"
    else:
        obj = _try_parse_json(text)
        if obj and isinstance(obj, dict):
            score += 1  # valid JSON
            if all(k in obj for k in ("diagnosis", "fix_command", "severity")):
                score += 1  # all keys present
            fc = str(obj.get("fix_command", ""))
            if len(fc) > 3 and (" " in fc or fc.startswith("/")):
                score += 1  # looks like a shell command
            detail = f"severity={obj.get('severity')} fix_len={len(fc)}"
        else:
            detail = f"not JSON: {text[:60]}"
    return {"score": score, "max": 3, "ms": ms, "detail": detail}


def _task_strict_format(model_id: str, api_key: str) -> dict:
    """Score 0-3: exact JSON output compliance."""
    TARGET = '{"status": "operational", "sessions": 4, "health": "good"}'
    prompt = (
        f"Return ONLY this exact JSON object — no explanation, no markdown, no code block:\n{TARGET}"
    )
    text, ms, err = _call_llm(model_id,
                               [{"role": "user", "content": prompt}], api_key)
    score = 0
    detail = ""
    if err:
        detail = f"error: {err[:80]}"
    else:
        stripped = _strip_json(text)
        obj = _try_parse_json(stripped)
        if stripped == TARGET:
            score = 3  # exact match
            detail = "exact"
        elif obj and isinstance(obj, dict) and all(
                obj.get(k) == v for k, v in
                [("status","operational"), ("sessions", 4), ("health","good")]):
            score = 2  # correct values
            detail = "correct values"
        elif obj and isinstance(obj, dict):
            score = 1  # valid JSON at least
            detail = f"wrong values: {list(obj.items())[:3]}"
        else:
            detail = f"not JSON: {text[:60]}"
    return {"score": score, "max": 3, "ms": ms, "detail": detail}


def _task_agentic_plan(model_id: str, api_key: str) -> dict:
    """Score 0-3: return agentic action plan as JSON."""
    prompt = (
        'Session "session-b" has been silent for 45 minutes (last output: 14:10:23). '
        "Current time: 14:55:41. It should emit a heartbeat every 5 minutes.\n\n"
        'Return ONLY JSON: {"action":"string","reason":"string","session":"session-b","priority":"low|medium|high|critical"}'
    )
    text, ms, err = _call_llm(model_id,
                               [{"role": "user", "content": prompt}], api_key)
    score = 0
    detail = ""
    PRIORITIES = {"low", "medium", "high", "critical"}
    if err:
        detail = f"error: {err[:80]}"
    else:
        obj = _try_parse_json(text)
        if obj and isinstance(obj, dict):
            score += 1  # valid JSON
            if all(k in obj for k in ("action", "reason", "session", "priority")):
                score += 1  # all keys
            if (obj.get("priority", "").lower() in PRIORITIES
                    and len(str(obj.get("action", ""))) > 3):
                score += 1  # valid enum + non-trivial action
            detail = f"priority={obj.get('priority')} action_len={len(str(obj.get('action','')))}"
        else:
            detail = f"not JSON: {text[:60]}"
    return {"score": score, "max": 3, "ms": ms, "detail": detail}


def _task_latency(model_id: str, api_key: str) -> dict:
    """Score 0-3: 3 simple pings, scored on average latency."""
    prompt = 'Reply with exactly: {"ok": true}'
    times = []
    errors = 0
    for _ in range(3):
        _, ms, err = _call_llm(model_id,
                                [{"role": "user", "content": prompt}], api_key,
                                timeout=TASK_TIMEOUT)
        if err:
            errors += 1
            times.append(TASK_TIMEOUT * 1000)
        else:
            times.append(ms)
    avg = sum(times) / len(times)
    score = 3 if avg < 2000 else (2 if avg < 5000 else (1 if avg < 10000 else 0))
    return {"score": score, "max": 3, "ms": int(avg),
            "detail": f"avg={avg:.0f}ms errors={errors}"}


# ── vision tasks ──────────────────────────────────────────────────────────────

def _vision_message(text_prompt: str) -> list:
    """Build a messages list with the test PNG attached."""
    return [{
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{_TEST_PNG_B64}"}
            },
            {"type": "text", "text": text_prompt}
        ]
    }]


def _task_vision_ui_elements(model_id: str, api_key: str) -> dict:
    """Score 0-3: identify UI elements in screenshot as JSON array."""
    prompt = (
        "This is a UI screenshot. Return ONLY a JSON array of UI elements you can see. "
        'Each: {"type":"button|input|bar|other","position":"top|middle|bottom"}'
    )
    text, ms, err = _call_llm(model_id, _vision_message(prompt), api_key)
    score = 0
    detail = ""
    if err:
        detail = f"error: {err[:80]}"
    else:
        obj = _try_parse_json(text)
        if obj is not None:
            score += 1  # valid JSON
            if isinstance(obj, list):
                score += 1  # is array
                if len(obj) >= 2:
                    score += 1  # found multiple elements
                detail = f"len={len(obj)}"
            else:
                detail = f"not array: {type(obj).__name__}"
        else:
            detail = f"not JSON: {text[:60]}"
    return {"score": score, "max": 3, "ms": ms, "detail": detail}


def _task_vision_layout_check(model_id: str, api_key: str) -> dict:
    """Score 0-3: detect overflow and fixed bottom bar."""
    prompt = (
        "Look at this mobile UI screenshot. Return ONLY JSON:\n"
        '{"has_horizontal_overflow":false,"bottom_bar_fixed":true,"explanation":"brief"}'
    )
    text, ms, err = _call_llm(model_id, _vision_message(prompt), api_key)
    score = 0
    detail = ""
    if err:
        detail = f"error: {err[:80]}"
    else:
        obj = _try_parse_json(text)
        if obj and isinstance(obj, dict):
            score += 1  # valid JSON dict
            if isinstance(obj.get("has_horizontal_overflow"), bool):
                score += 1  # correct bool type
            if isinstance(obj.get("bottom_bar_fixed"), bool):
                score += 1  # correct bool type
            detail = (f"overflow={obj.get('has_horizontal_overflow')} "
                      f"fixed={obj.get('bottom_bar_fixed')}")
        else:
            detail = f"not JSON dict: {text[:60]}"
    return {"score": score, "max": 3, "ms": ms, "detail": detail}


def _task_vision_tap_targets(model_id: str, api_key: str) -> dict:
    """Score 0-3: assess tap target sizes."""
    prompt = (
        "Analyze mobile accessibility of this UI screenshot. Return ONLY JSON:\n"
        '{"min_tap_height_px":44,"all_44px_compliant":true,"issues":[]}'
    )
    text, ms, err = _call_llm(model_id, _vision_message(prompt), api_key)
    score = 0
    detail = ""
    if err:
        detail = f"error: {err[:80]}"
    else:
        obj = _try_parse_json(text)
        if obj and isinstance(obj, dict):
            score += 1  # valid JSON dict
            val = obj.get("min_tap_height_px")
            if isinstance(val, (int, float)):
                score += 1  # numeric value
            comp = obj.get("all_44px_compliant")
            if isinstance(comp, bool):
                score += 1  # boolean
            detail = f"min_tap={val} compliant={comp}"
        else:
            detail = f"not JSON dict: {text[:60]}"
    return {"score": score, "max": 3, "ms": ms, "detail": detail}


# ── per-model benchmark ───────────────────────────────────────────────────────

TEXT_TASKS = [
    ("json_tool_call", _task_json_tool_call),
    ("hive_diagnosis",  _task_hive_diagnosis),
    ("strict_format",   _task_strict_format),
    ("agentic_plan",    _task_agentic_plan),
    ("latency",         _task_latency),
]

VISION_TASKS = [
    ("ui_elements",  _task_vision_ui_elements),
    ("layout_check", _task_vision_layout_check),
    ("tap_targets",  _task_vision_tap_targets),
]

MAX_FAILS_BEFORE_SKIP = 2  # skip remaining tasks if model fails this many


def benchmark_model(model_id: str, arena_type: str, api_key: str) -> dict:
    """
    Run all tasks for one model.
    Returns {"model": id, "arena": type, "tasks": {...}, "total": n, "max": n, "dnf": bool}
    """
    tasks   = TEXT_TASKS if arena_type == "text" else VISION_TASKS
    results = {}
    total   = 0
    max_pts = 0
    fails   = 0
    dnf     = False

    for task_name, task_fn in tasks:
        if fails >= MAX_FAILS_BEFORE_SKIP:
            results[task_name] = {"score": 0, "max": 3, "ms": 0,
                                  "detail": "skipped (too many failures)"}
            max_pts += 3
            continue
        try:
            r = task_fn(model_id, api_key)
        except Exception as e:
            r = {"score": 0, "max": 3, "ms": 0, "detail": f"exception: {e}"}
        results[task_name] = r
        total   += r["score"]
        max_pts += r["max"]
        if r["score"] == 0:
            fails += 1

    if fails >= MAX_FAILS_BEFORE_SKIP:
        dnf = True

    return {
        "model":  model_id,
        "arena":  arena_type,
        "tasks":  results,
        "total":  total,
        "max":    max_pts,
        "dnf":    dnf,
        "ts":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ── full arena run ────────────────────────────────────────────────────────────

def run_arena(arena_type: str, api_key: str, force: bool = False,
              model_list: list = None) -> dict:
    """
    Fetch free models, pick top-N, benchmark in parallel.
    Returns full results dict and updates champion + results files.

    arena_type: 'text' | 'vision'
    model_list: if provided, use this list instead of fetching (for testing)
    """
    if model_list is None:
        all_models, _ = fetch_and_register_free_models(api_key)
        candidates    = select_top_n(all_models, arena_type, TOP_N)
    else:
        candidates = model_list

    if not candidates:
        return {"error": "no candidates found", "arena": arena_type}

    model_results = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(candidates))) as pool:
        futures = {
            pool.submit(benchmark_model, mid, arena_type, api_key): mid
            for mid in candidates
        }
        for future in as_completed(futures):
            try:
                model_results.append(future.result())
            except Exception as e:
                mid = futures[future]
                model_results.append({
                    "model": mid, "arena": arena_type,
                    "tasks": {}, "total": 0, "max": 15 if arena_type=="text" else 9,
                    "dnf": True, "detail": str(e),
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })

    # Sort by total score desc
    model_results.sort(key=lambda x: x["total"], reverse=True)

    winner = None
    for r in model_results:
        if not r.get("dnf"):
            winner = r["model"]
            break
    if winner is None and model_results:
        winner = model_results[0]["model"]  # take best even if DNF

    arena_result = {
        "arena":     arena_type,
        "winner":    winner,
        "candidates": candidates,
        "results":   model_results,
        "run_at":    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Update persistent files
    _update_champion(arena_type, winner)
    _update_results(arena_type, arena_result)

    return arena_result


def _update_champion(arena_type: str, winner: str):
    champ = _load_champion()
    champ[arena_type]  = winner
    champ["updated"]   = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        with open(CHAMPION_FILE, "w") as f:
            json.dump(champ, f, indent=2)
    except Exception:
        pass


def _load_champion() -> dict:
    try:
        with open(CHAMPION_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def get_champion(arena_type: str) -> str | None:
    return _load_champion().get(arena_type)


def _update_results(arena_type: str, result: dict):
    try:
        with open(RESULTS_FILE) as f:
            data = json.load(f)
    except Exception:
        data = {}
    data[arena_type] = result
    try:
        with open(RESULTS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def get_arena_results() -> dict:
    try:
        with open(RESULTS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def get_arena_status() -> dict:
    champ   = _load_champion()
    results = get_arena_results()
    status  = {
        "text_champion":   champ.get("text"),
        "vision_champion": champ.get("vision"),
        "last_updated":    champ.get("updated"),
        "last_run": {}
    }
    for atype in ("text", "vision"):
        if atype in results:
            r = results[atype]
            status["last_run"][atype] = {
                "run_at":     r.get("run_at"),
                "winner":     r.get("winner"),
                "candidates": r.get("candidates", []),
                "top_scores": [
                    {"model": m["model"], "score": m["total"], "max": m["max"]}
                    for m in r.get("results", [])[:3]
                ]
            }
    return status


# ── background watcher ────────────────────────────────────────────────────────

def start_model_watcher(api_key: str, interval_hours: float = 6.0):
    """
    Background daemon thread: every `interval_hours` hours, fetch free models.
    If any new models are found, queue a full arena re-run.
    If no champion is set yet, run immediately.
    """
    def _loop():
        # Run immediately if no champion set
        if not get_champion("text"):
            try:
                run_arena("text",   api_key)
            except Exception:
                pass
        if not get_champion("vision"):
            try:
                run_arena("vision", api_key)
            except Exception:
                pass

        while True:
            time.sleep(interval_hours * 3600)
            try:
                _, new_ids = fetch_and_register_free_models(api_key)
                if new_ids:
                    # New models detected — re-run both arenas
                    for atype in ("text", "vision"):
                        try:
                            run_arena(atype, api_key)
                        except Exception:
                            pass
            except Exception:
                pass

    t = threading.Thread(target=_loop, daemon=True, name="model-watcher")
    t.start()
    return t


# ── CLI (standalone run) ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    api_key = ""
    for _env_path in [
        os.environ.get("HIVE_ENV_FILE", ""),
        os.path.expanduser("~/.config/hive-ui/env"),
        os.path.expanduser("~/.config/research-hive/env"),
    ]:
        if not _env_path:
            continue
        try:
            for line in open(_env_path):
                if line.startswith("OPENROUTER_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
            if api_key:
                break
        except Exception:
            continue
    api_key = os.environ.get("OPENROUTER_API_KEY", api_key)
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    arena_type = sys.argv[1] if len(sys.argv) > 1 else "text"
    print(f"Running {arena_type} arena benchmark (top-{TOP_N} by param count)...")
    result = run_arena(arena_type, api_key)
    print(f"\nWinner: {result.get('winner')}")
    print(f"Candidates: {result.get('candidates')}")
    for r in result.get("results", []):
        flag = " [DNF]" if r.get("dnf") else ""
        print(f"  {r['total']:2d}/{r['max']:2d}  {r['model']}{flag}")
