#!/usr/bin/env python3
"""
vercel_hive.py — Standalone public Hive dashboard with OpenRouter chat.

Deployed to Vercel as api/index.py (see vercel-deploy/).
Also runnable standalone for local testing:

    python3 vercel_hive.py                        # standalone mode (needs OPENROUTER_API_KEY)
    HIVE_BACKEND_URL=http://127.0.0.1:8889 python3 vercel_hive.py  # proxy mode

Modes
-----
  Standalone (HIVE_BACKEND_URL not set — default on Vercel):
    GET  /            → full dashboard + chat UI
    GET  /api/status  → minimal JSON status
    GET  /api/config  → model + favorites config
    POST /api/chat    → non-streaming OpenRouter fallback (for local dev only;
                        on Vercel the Edge Function api/chat.js handles this route)

  Proxy (HIVE_BACKEND_URL set — for internal/dev use):
    GET  /            → lightweight status dashboard (no chat)
    GET  /api/*       → whitelisted read-only proxy to backend
    POST/*            → 403

Env vars
--------
  OPENROUTER_API_KEY  — required for chat in standalone mode
  OPENROUTER_MODEL    — model to use (default: openai/gpt-oss-120b:free)
  HIVE_BACKEND_URL    — if set, enables proxy mode (no chat)
  PORT                — local dev port (default 8080)
"""

import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── config ────────────────────────────────────────────────────────────────────

HIVE_BACKEND_URL = os.environ.get("HIVE_BACKEND_URL", "").rstrip("/")
STANDALONE       = not bool(HIVE_BACKEND_URL)
OPENROUTER_KEY   = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")
PORT             = int(os.environ.get("PORT", 8080))

# Whitelist for proxy mode
_PROXY_PATHS = {
    "/api/status",
    "/api/status/questions",
    "/api/status/compact",
    "/api/arena/status",
    "/api/arena/results",
    "/api/doctor/status",
    "/api/config",
    "/api/queue",
}

DEFAULT_FAVORITES = [
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen3-coder:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]

# ── standalone dashboard HTML ─────────────────────────────────────────────────

_STANDALONE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Hive</title>
<style>
:root{--bg:#0d0d0d;--sur:#161616;--bdr:#2a2a2a;--txt:#e0e0e0;--mut:#666;--acc:#fff;
      --safe-b:env(safe-area-inset-bottom,0px)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font:14px/1.6 'Courier New',monospace;
     padding:16px 16px calc(var(--safe-b) + 80px)}
h1{font-size:1rem;font-weight:bold;letter-spacing:.1em;margin-bottom:16px;color:var(--acc)}
section{background:var(--sur);border:1px solid var(--bdr);border-radius:4px;
        margin-bottom:12px;padding:12px}
section h2{font-size:.8rem;color:var(--mut);text-transform:uppercase;letter-spacing:.12em;
           margin-bottom:8px}
.badge{display:inline-block;padding:2px 6px;border-radius:2px;font-size:.75rem;
       background:var(--bdr);color:var(--acc)}
.row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:6px}
.stat{flex:1;min-width:120px;background:var(--bg);border:1px solid var(--bdr);
      border-radius:3px;padding:8px 10px}
.stat-val{font-size:1.4rem;font-weight:bold}
.stat-label{font-size:.7rem;color:var(--mut);margin-top:2px}
#questions .q{padding:6px 0;border-bottom:1px solid var(--bdr)}
#questions .q:last-child{border:none}
.q-text{color:var(--acc)}
.q-meta{font-size:.75rem;color:var(--mut)}
.err{color:#888}

/* ── chat ── */
#chat-msgs{display:flex;flex-direction:column;gap:10px;margin-top:4px;
           min-height:40px;max-height:60vh;overflow-y:auto}
.msg{padding:8px 10px;border-radius:4px;white-space:pre-wrap;word-break:break-word;
     line-height:1.5;font-size:.875rem}
.msg.user{background:var(--bdr);align-self:flex-end;max-width:90%}
.msg.assistant{background:var(--bg);border:1px solid var(--bdr);align-self:flex-start;
               max-width:95%}
.msg.assistant.streaming::after{content:'▌';animation:blink .7s step-end infinite}
@keyframes blink{50%{opacity:0}}
.msg-err{color:#888;font-size:.8rem;padding:6px 0}

#chat-bar{position:fixed;bottom:0;left:0;right:0;
          padding:10px 12px calc(var(--safe-b) + 10px);
          background:var(--sur);border-top:1px solid var(--bdr);
          display:flex;gap:8px;align-items:flex-end;z-index:100}
#chat-input{flex:1;background:var(--bg);border:1px solid var(--bdr);border-radius:4px;
            color:var(--txt);font:14px/1.4 'Courier New',monospace;
            padding:10px 12px;resize:none;min-height:44px;max-height:160px;
            overflow-y:auto;outline:none}
#chat-input:focus{border-color:var(--acc)}
#chat-send{min-height:44px;min-width:44px;background:var(--acc);color:var(--bg);
           border:none;border-radius:4px;font:bold 14px 'Courier New',monospace;
           cursor:pointer;padding:0 14px;flex-shrink:0}
#chat-send:disabled{opacity:.35;cursor:default}
#chat-model{font-size:.7rem;color:var(--mut);padding:0 2px 4px;white-space:nowrap;
            overflow:hidden;text-overflow:ellipsis;max-width:180px}

footer{text-align:center;color:var(--mut);font-size:.7rem;margin-top:24px}
</style>
</head>
<body>
<h1>[ HIVE ]</h1>

<section>
  <h2>Overview</h2>
  <div class="row" id="stats"><span class="err">loading…</span></div>
</section>

<section>
  <h2>Open Questions</h2>
  <div id="questions"><span class="err">loading…</span></div>
</section>

<section>
  <h2>Chat</h2>
  <div id="chat-msgs"></div>
</section>

<footer>public view · auto-refreshes every 60 s</footer>

<div id="chat-bar">
  <div style="display:flex;flex-direction:column;flex:1;gap:0;min-width:0">
    <div id="chat-model">MODEL_PLACEHOLDER</div>
    <textarea id="chat-input" rows="1" placeholder="ask the hive…"
              aria-label="chat input"></textarea>
  </div>
  <button id="chat-send">send</button>
</div>

<script>
(function(){
'use strict';

/* ── status ── */
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

async function loadStatus(){
  try{
    const s=await fetch('/api/status').then(r=>r.json());
    const pairs=[
      ['achievements',(s.achievements||[]).length],
      ['blockers',(s.blockers||[]).filter(b=>b.status!=='resolved').length],
      ['questions',(s.questions||[]).filter(q=>!q.answered).length],
      ['next steps',(s.next_steps||[]).length],
    ];
    document.getElementById('stats').innerHTML=pairs.map(([l,v])=>
      `<div class="stat"><div class="stat-val">${v}</div><div class="stat-label">${esc(l)}</div></div>`
    ).join('');
  }catch{
    document.getElementById('stats').innerHTML='<span class="err">unavailable</span>';
  }
  try{
    const qs=await fetch('/api/status').then(r=>r.json()).then(s=>(s.questions||[]).filter(q=>!q.answered));
    const el=document.getElementById('questions');
    if(!qs.length){el.innerHTML='<span class="err">no open questions</span>';return;}
    el.innerHTML=qs.map(q=>
      `<div class="q"><div class="q-text">${esc(q.question||'')}</div>`+
      `<div class="q-meta">${esc(q.hive||'')} / ${esc(q.agent||'')} · ${esc(q.hint||'')}</div></div>`
    ).join('');
  }catch{}
}

loadStatus();
setInterval(loadStatus,60000);

/* ── chat ── */
const msgsEl  = document.getElementById('chat-msgs');
const inputEl = document.getElementById('chat-input');
const sendEl  = document.getElementById('chat-send');
const history = [];

function appendMsg(role, text, streaming){
  const d=document.createElement('div');
  d.className='msg '+role+(streaming?' streaming':'');
  d.textContent=text;
  msgsEl.appendChild(d);
  msgsEl.scrollTop=msgsEl.scrollHeight;
  return d;
}

function appendErr(text){
  const d=document.createElement('div');
  d.className='msg-err';
  d.textContent=text;
  msgsEl.appendChild(d);
  msgsEl.scrollTop=msgsEl.scrollHeight;
}

// auto-grow textarea
inputEl.addEventListener('input',()=>{
  inputEl.style.height='auto';
  inputEl.style.height=Math.min(inputEl.scrollHeight,160)+'px';
});
inputEl.addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg();}
});
sendEl.addEventListener('click',sendMsg);

async function sendMsg(){
  const text=inputEl.value.trim();
  if(!text)return;
  inputEl.value='';
  inputEl.style.height='auto';
  sendEl.disabled=true;

  appendMsg('user',text,false);
  history.push({role:'user',content:text});

  const assistantEl=appendMsg('assistant','',true);

  try{
    const resp=await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text,history:history.slice(0,-1)}),
    });

    if(!resp.ok){
      const err=await resp.json().catch(()=>({error:'server error '+resp.status}));
      assistantEl.classList.remove('streaming');
      assistantEl.textContent='';
      appendErr('error: '+(err.error||resp.status));
      history.pop();
      sendEl.disabled=false;
      return;
    }

    const ct=resp.headers.get('content-type')||'';

    if(ct.includes('text/event-stream')){
      // Streaming (Edge Function on Vercel)
      const reader=resp.body.getReader();
      const dec=new TextDecoder();
      let buf='',reply='';
      while(true){
        const {done,value}=await reader.read();
        if(done)break;
        buf+=dec.decode(value,{stream:true});
        const lines=buf.split('\\n');
        buf=lines.pop();
        for(const line of lines){
          if(!line.startsWith('data:'))continue;
          const raw=line.slice(5).trim();
          if(raw==='[DONE]')continue;
          try{
            const chunk=JSON.parse(raw);
            const delta=chunk.choices?.[0]?.delta?.content||'';
            if(delta){reply+=delta;assistantEl.textContent=reply;}
          }catch{}
        }
      }
      assistantEl.classList.remove('streaming');
      if(!reply)assistantEl.textContent='(empty response)';
      history.push({role:'assistant',content:reply});
    } else {
      // Non-streaming fallback (local dev Python handler)
      const data=await resp.json();
      const reply=data.content||data.choices?.[0]?.message?.content||'(no content)';
      assistantEl.classList.remove('streaming');
      assistantEl.textContent=reply;
      history.push({role:'assistant',content:reply});
    }
  }catch(e){
    assistantEl.classList.remove('streaming');
    assistantEl.textContent='';
    appendErr('network error: '+e.message);
    history.pop();
  }finally{
    sendEl.disabled=false;
    inputEl.focus();
  }
}
})();
</script>
</body>
</html>
"""

# ── proxy dashboard HTML (no chat) ────────────────────────────────────────────

_PROXY_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Hive Status</title>
<style>
:root{--bg:#0d0d0d;--sur:#161616;--bdr:#2a2a2a;--txt:#e0e0e0;--mut:#666;--acc:#fff}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font:14px/1.6 'Courier New',monospace;padding:16px}
h1{font-size:1rem;font-weight:bold;letter-spacing:.1em;margin-bottom:16px;color:var(--acc)}
section{background:var(--sur);border:1px solid var(--bdr);border-radius:4px;
        margin-bottom:12px;padding:12px}
section h2{font-size:.8rem;color:var(--mut);text-transform:uppercase;letter-spacing:.12em;
           margin-bottom:8px}
.badge{display:inline-block;padding:2px 6px;border-radius:2px;font-size:.75rem;
       background:var(--bdr);color:var(--acc)}
.row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:6px}
.stat{flex:1;min-width:120px;background:var(--bg);border:1px solid var(--bdr);
      border-radius:3px;padding:8px 10px}
.stat-val{font-size:1.4rem;font-weight:bold}
.stat-label{font-size:.7rem;color:var(--mut);margin-top:2px}
.err{color:#888}
footer{text-align:center;color:var(--mut);font-size:.7rem;margin-top:24px}
</style>
</head>
<body>
<h1>[ HIVE STATUS ]</h1>
<section>
  <h2>Overview</h2>
  <div class="row" id="stats"><span class="err">loading…</span></div>
</section>
<section>
  <h2>Open Questions</h2>
  <div id="questions"><span class="err">loading…</span></div>
</section>
<section>
  <h2>Arena Champion</h2>
  <div id="arena"><span class="err">loading…</span></div>
</section>
<footer>read-only public view · auto-refreshes every 30 s</footer>
<script>
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function load(){
  try{
    const s=await fetch('/api/status').then(r=>r.json());
    const pairs=[['achievements',(s.achievements||[]).length],['blockers',(s.blockers||[]).filter(b=>b.status!=='resolved').length],['questions',(s.questions||[]).filter(q=>!q.answered).length],['next steps',(s.next_steps||[]).length]];
    document.getElementById('stats').innerHTML=pairs.map(([l,v])=>`<div class="stat"><div class="stat-val">${v}</div><div class="stat-label">${esc(l)}</div></div>`).join('');
  }catch{}
  try{
    const qs=await fetch('/api/status/questions?unanswered').then(r=>r.json());
    const el=document.getElementById('questions');
    if(!Array.isArray(qs)||!qs.length){el.innerHTML='<span class="err">no open questions</span>';}
    else el.innerHTML=qs.map(q=>`<div style="padding:6px 0;border-bottom:1px solid #2a2a2a"><div style="color:#fff">${esc(q.question||'')}</div><div style="font-size:.75rem;color:#666">${esc(q.hive||'')} / ${esc(q.agent||'')} · ${esc(q.hint||'')}</div></div>`).join('');
  }catch{}
  try{
    const a=await fetch('/api/arena/status').then(r=>r.json());
    document.getElementById('arena').innerHTML=`<span class="badge">text</span> ${esc(a.text_champion||'—')}&nbsp;&nbsp;<span class="badge">vision</span> ${esc(a.vision_champion||'—')}`;
  }catch{}
}
load();setInterval(load,30000);
</script>
</body>
</html>
"""

# ── handler ───────────────────────────────────────────────────────────────────

class PublicHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silence access log

    def _send(self, status, content_type, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type",   content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, status=200):
        self._send(status, "application/json", json.dumps(obj).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── GET ───────────────────────────────────────────────────────────────────

    def do_GET(self):
        path  = self.path.split("?")[0]
        query = self.path[len(path):]

        # Dashboard root
        if path == "/":
            if STANDALONE:
                html = _STANDALONE_HTML.replace(
                    "MODEL_PLACEHOLDER",
                    OPENROUTER_MODEL,
                )
                self._send(200, "text/html; charset=utf-8", html.encode())
            else:
                self._send(200, "text/html; charset=utf-8", _PROXY_HTML.encode())
            return

        # Standalone API endpoints
        if STANDALONE:
            if path == "/api/status":
                self._send_json({
                    "hive": "public",
                    "mode": "standalone",
                    "model": OPENROUTER_MODEL,
                    "achievements": [],
                    "blockers": [],
                    "questions": [],
                    "next_steps": [],
                })
                return
            if path == "/api/config":
                self._send_json({
                    "model":       OPENROUTER_MODEL,
                    "favorites":   DEFAULT_FAVORITES,
                    "api_key_set": bool(OPENROUTER_KEY),
                })
                return
            self._send_json({"error": "not found"}, 404)
            return

        # Proxy mode — whitelist check
        if path not in _PROXY_PATHS:
            self._send_json({"error": "not found"}, 404)
            return

        backend_url = HIVE_BACKEND_URL + path + query
        try:
            req = urllib.request.Request(
                backend_url,
                headers={"User-Agent": "hive-public-proxy/2"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                content_type = resp.headers.get("Content-Type", "application/json")
                body = resp.read()
            self._send(200, content_type, body)
        except urllib.error.HTTPError as e:
            self._send_json({"error": f"backend error {e.code}"}, 502)
        except Exception as e:
            self._send_json({"error": "backend unavailable", "detail": str(e)}, 502)

    # ── POST ──────────────────────────────────────────────────────────────────

    def do_POST(self):
        path = self.path.split("?")[0]

        if not STANDALONE:
            self._send_json({"error": "read-only proxy — writes not allowed"}, 403)
            return

        # /api/chat — non-streaming fallback (for local dev; Vercel routes to Edge Function)
        if path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            try:
                raw = json.loads(self.rfile.read(length) if length else b"{}")
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON"}, 400)
                return

            message = (raw.get("message") or "").strip()
            if not message:
                self._send_json({"error": "message required"}, 400)
                return
            if not OPENROUTER_KEY:
                self._send_json({"error": "OPENROUTER_API_KEY not set"}, 500)
                return

            history  = raw.get("history", [])
            model    = (raw.get("model") or OPENROUTER_MODEL).strip()
            messages = [*history, {"role": "user", "content": message}]

            payload = json.dumps({
                "model":    model,
                "messages": messages,
                "stream":   False,
            }).encode()
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "http://localhost",
                    "X-Title":       "Hive Dev",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=55) as resp:
                    data = json.loads(resp.read())
                content = data["choices"][0]["message"]["content"]
                self._send_json({"content": content, "model": model})
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")
                self._send_json({"error": f"upstream {e.code}", "detail": body}, 502)
            except Exception as e:
                self._send_json({"error": str(e)}, 502)
            return

        self._send_json({"error": "not found"}, 404)

    def do_PATCH(self):
        self._send_json({"error": "not allowed"}, 403)

    def do_DELETE(self):
        self._send_json({"error": "not allowed"}, 403)


# ── Vercel entry point ────────────────────────────────────────────────────────
# Vercel Python runtime expects a module-level `handler` that is a subclass of
# BaseHTTPRequestHandler.

handler = PublicHandler


# ── standalone dev entry point ────────────────────────────────────────────────
if __name__ == "__main__":
    mode = "standalone" if STANDALONE else f"proxy → {HIVE_BACKEND_URL}"
    server = HTTPServer(("0.0.0.0", PORT), PublicHandler)
    print(f"Hive public server on http://0.0.0.0:{PORT}  [{mode}]")
    if STANDALONE and not OPENROUTER_KEY:
        print("  WARNING: OPENROUTER_API_KEY not set — chat will return 500")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
