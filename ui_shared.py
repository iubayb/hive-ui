"""
ui_shared.py — Shared UI constants for all Hive UI server deployments.

Single responsibility: own every byte of portable CSS and JS render logic.
Imported by logstream.py (local server) and vercel_hive.py (Vercel deploy).

Exports
-------
SHARED_CSS        portable CSS: design tokens, components, animations
LOCAL_CSS         local-server chrome: input bar, settings modal, arena panel
SHARED_RENDER_JS  status panel render functions — framework-agnostic, no DOM
                  globals other than the element IDs defined in the HTML template
LOCAL_STATUS_JS   SSE connection + log stream wiring — local server only
"""

# ── shared CSS ────────────────────────────────────────────────────────────────
# Everything portable: design tokens, layout primitives, all status components.
# Monochrome dark: brightness = urgency, no hue.

SHARED_CSS = r"""
  :root{
    --bg:#0a0a0a;--panel:#131313;--border:#272727;--text:#e8e8e8;--muted:#808080;
    --err:#f0f0f0;--warn:#9c9c9c;--ok:#b0b0b0;--info:#d0d0d0;--purple:#8c8c8c;
    --input-bg:#0a0a0a;--bubble-user:#1a1a1a;--bubble-ai:#131313;
    --safe-bottom:env(safe-area-inset-bottom,0px);
    --crit:#f0f0f0;--high:#c4c4c4;--medium:#909090;--low:#585858;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%;background:var(--bg);color:var(--text);
            font-family:'Courier New',monospace;font-size:13px;line-height:1.5;
            overflow-x:hidden}

  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

  /* layout */
  #main{padding-bottom:calc(70px + var(--safe-bottom));padding-top:36px}
  /* 36px = height of the fixed active-task-bar so content isn't hidden under it */

  /* log boxes */
  .log-box{height:260px;overflow-y:auto;padding:4px 0;background:var(--bg)}
  .log-box.combined{height:300px}
  .ts{color:var(--muted);margin-right:5px;font-size:11px}
  .badge{display:inline-block;padding:1px 5px;border-radius:3px;
         font-size:10px;margin-right:5px;font-weight:bold;white-space:nowrap}
  .logline{padding:2px 8px;border-left:2px solid transparent;word-break:break-all}
  .logline.err{color:var(--err);border-color:var(--err)}
  .logline.warn{color:var(--warn);border-color:var(--warn)}
  .logline.ok{color:var(--ok);border-color:var(--ok)}

  /* status panel */
  #status-panel{margin:8px;border:1px solid var(--border);border-radius:6px;overflow:hidden}
  #status-panel summary{padding:9px 12px;background:var(--panel);font-weight:bold;cursor:pointer;
    display:flex;justify-content:space-between;align-items:center;list-style:none;
    -webkit-tap-highlight-color:transparent;min-height:44px;user-select:none}
  #status-panel summary::-webkit-details-marker{display:none}
  #status-panel summary:active{background:var(--border)}
  .status-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}
  .status-dot.live{background:var(--ok);animation:pulse 2s infinite}
  .status-dot.dead{background:var(--err)}
  #status-updated{font-size:10px;color:var(--muted)}

  /* hive health cards */
  #hive-health-grid{display:flex;flex-wrap:wrap;gap:8px;padding:10px 12px}
  .hive-card{flex:1;min-width:140px;background:var(--bg);border:1px solid var(--border);
             border-radius:6px;padding:10px 12px}
  .hive-card .hc-name{font-size:12px;font-weight:bold;color:var(--info);margin-bottom:6px}
  .hive-card .hc-status{font-size:11px;margin-bottom:4px}
  .hive-card .hc-bar-wrap{height:4px;background:var(--border);border-radius:2px;margin-bottom:4px}
  .hive-card .hc-bar{height:4px;border-radius:2px;background:var(--ok);transition:width .4s}
  .hive-card .hc-bar.warn{background:var(--warn)}
  .hive-card .hc-bar.err{background:var(--err)}
  .hive-card .hc-meta{font-size:10px;color:var(--muted)}

  /* blockers */
  .blocker-item{padding:9px 12px;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:flex-start}
  .blocker-item:last-child{border-bottom:none}
  .sev-badge{padding:2px 7px;border-radius:10px;font-size:10px;font-weight:bold;white-space:nowrap;flex-shrink:0}
  .sev-badge.critical{background:rgba(255,255,255,.08);color:var(--crit)}
  .sev-badge.high{background:rgba(255,255,255,.06);color:var(--high)}
  .sev-badge.medium{background:rgba(255,255,255,.04);color:var(--medium)}
  .sev-badge.low{background:rgba(255,255,255,.03);color:var(--low)}
  .blocker-desc{flex:1;font-size:12px;line-height:1.4;word-break:break-word}
  .blocker-meta{font-size:10px;color:var(--muted);margin-top:2px}
  .resolve-btn{background:none;border:1px solid var(--ok);color:var(--ok);
               padding:2px 7px;border-radius:4px;font-size:10px;cursor:pointer;
               flex-shrink:0;min-height:44px}
  .resolve-btn:active{opacity:.7}

  /* achievements */
  .achievement-item{padding:8px 12px;border-bottom:1px solid var(--border);display:flex;gap:8px}
  .achievement-item:last-child{border-bottom:none}
  .ach-icon{font-size:16px;flex-shrink:0}
  .ach-body{flex:1;min-width:0}
  .ach-desc{font-size:12px;line-height:1.4;word-break:break-word}
  .ach-meta{font-size:10px;color:var(--muted);margin-top:2px}

  /* next steps */
  .ns-item{padding:8px 12px;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:center}
  .ns-item:last-child{border-bottom:none}
  .ns-check{width:16px;height:16px;border:1px solid var(--border);border-radius:3px;
            cursor:pointer;flex-shrink:0;display:flex;align-items:center;justify-content:center;
            font-size:11px;min-width:16px}
  .ns-check.done{background:var(--ok);border-color:var(--ok);color:#000}
  .ns-text{flex:1;font-size:12px;word-break:break-word}
  .ns-text.done{text-decoration:line-through;color:var(--muted)}
  .ns-meta{font-size:10px;color:var(--muted);white-space:nowrap}

  /* capabilities */
  .cap-item{padding:8px 12px;border-bottom:1px solid var(--border)}
  .cap-item:last-child{border-bottom:none}
  .cap-header{display:flex;align-items:center;gap:6px;cursor:pointer;
              -webkit-tap-highlight-color:transparent}
  .cap-skill{font-size:11px;font-weight:bold;color:var(--purple);
             background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.10);
             padding:2px 7px;border-radius:10px}
  .cap-desc{font-size:12px;color:var(--muted);flex:1}
  .cap-detail{display:none;margin-top:6px;padding:6px 8px;background:var(--bg);
              border-radius:4px;font-size:11px}
  .cap-detail.open{display:block}
  .cap-example{font-family:monospace;color:var(--ok);margin-top:4px;word-break:break-all}
  .cap-tags{margin-top:4px;display:flex;flex-wrap:wrap;gap:3px}
  .cap-tag{padding:1px 6px;border-radius:8px;font-size:10px;
           background:var(--border);color:var(--muted)}

  /* metrics */
  #metrics-row{display:flex;flex-wrap:wrap;gap:10px;padding:10px 12px}
  .metric-box{flex:1;min-width:80px;text-align:center;
              background:var(--bg);border:1px solid var(--border);
              border-radius:6px;padding:8px}
  .metric-val{font-size:20px;font-weight:bold;color:var(--info)}
  .metric-label{font-size:10px;color:var(--muted);margin-top:2px}

  /* ── active task bar — fixed strip, always on screen regardless of tab/scroll */
  #active-task-bar{
    display:flex;align-items:center;gap:8px;padding:0 14px;
    font-size:11px;font-family:'Courier New',monospace;
    border-bottom:2px solid var(--border);
    position:fixed;top:0;left:0;right:0;z-index:100;
    height:36px;overflow:hidden;
    transition:background .3s,border-color .3s,color .3s;
  }
  /* OK = healthy between cycles */
  #active-task-bar.at-ok{
    background:rgba(176,176,176,.04);color:var(--ok);border-bottom-color:rgba(176,176,176,.25)}
  /* WORKING = task running right now */
  #active-task-bar.at-working{
    background:rgba(176,176,176,.07);color:var(--ok);border-bottom-color:var(--ok)}
  /* STALE = backend says running >3min */
  #active-task-bar.at-stale{
    background:rgba(156,156,156,.07);color:var(--warn);border-bottom-color:var(--warn);
    animation:at-blink 1.4s infinite}
  /* HANG/LOOP/SILENT = frontend detected problem */
  #active-task-bar.at-hang{
    background:rgba(240,240,240,.08);color:var(--err);border-bottom-color:var(--err);
    animation:at-blink .7s infinite}
  @keyframes at-blink{0%,100%{opacity:1}50%{opacity:.55}}
  .at-dot{width:7px;height:7px;border-radius:50%;background:currentColor;flex-shrink:0}
  #active-task-bar.at-working .at-dot{animation:pulse 1s infinite}
  #active-task-bar.at-ok      .at-dot{animation:pulse 3s infinite}
  #active-task-bar.at-hang    .at-dot{animation:at-blink .5s infinite}
  #active-task-bar.at-stale   .at-dot{animation:at-blink 1s infinite}
  .at-label{font-weight:bold;font-size:10px;text-transform:uppercase;
            letter-spacing:.6px;white-space:nowrap;flex-shrink:0}
  .at-detail{font-size:11px;opacity:.75;white-space:nowrap;overflow:hidden;
             text-overflow:ellipsis;flex:1;min-width:0}
  .at-elapsed{font-size:10px;color:var(--muted);white-space:nowrap;flex-shrink:0;
              padding-left:6px}
  .at-src{font-size:9px;color:var(--muted);white-space:nowrap;flex-shrink:0;
          padding:1px 5px;border:1px solid var(--border);border-radius:8px;margin-left:4px}
  .at-next{font-size:10px;color:var(--muted);white-space:nowrap;flex-shrink:0;
           padding-left:6px;opacity:.6}

  /* ── end active task bar ────────────────────────────────────────────────── */
  .flash{animation:flash .8s ease-out forwards}

  /* flash animation */
  @keyframes flash{0%{background:rgba(255,255,255,.12)}100%{background:transparent}}
  .q-item{padding:10px 12px;border-bottom:1px solid var(--border);
          display:flex;align-items:flex-start;gap:10px}
  .q-item:last-child{border-bottom:none}
  .q-status{font-size:16px;flex-shrink:0;margin-top:1px}
  .q-body{flex:1;min-width:0}
  .q-summary{word-break:break-word;font-size:12px;line-height:1.4}
  .q-meta{font-size:10px;color:var(--muted);margin-top:3px;display:flex;gap:8px;flex-wrap:wrap}
  .q-meta a{color:var(--info);text-decoration:none}
  .q-del{background:none;border:none;color:var(--muted);font-size:14px;line-height:1;
         cursor:pointer;padding:2px 4px;margin-left:auto;flex-shrink:0;opacity:.5;
         min-width:24px;min-height:24px;border-radius:3px}
  .q-del:hover{opacity:1;color:var(--err)}
  #clear-done-btn{background:none;border:1px solid var(--border);color:var(--muted);
    padding:2px 7px;border-radius:4px;font-size:10px;cursor:pointer;margin-left:auto;
    min-height:22px;line-height:1}
  #clear-done-btn:hover{color:var(--err);border-color:var(--err)}
  #queue-empty{padding:16px;text-align:center;color:var(--muted);font-size:12px}

  /* chat bubbles */
  #chat-thread{min-height:80px;max-height:400px;overflow-y:auto;
               padding:10px 8px;background:var(--bg)}
  .bubble{margin:6px 0;padding:9px 11px;border-radius:8px;
          font-size:13px;line-height:1.5;word-break:break-word;max-width:90%}
  .bubble.user{background:var(--bubble-user);color:#d0d0d0;margin-left:auto}
  .bubble.ai{background:var(--bubble-ai);color:var(--text);border:1px solid var(--border)}
  .bubble .role-label{font-size:10px;color:var(--muted);margin-bottom:4px;
                      text-transform:uppercase;letter-spacing:.5px}
  .cursor{display:inline-block;width:7px;height:13px;background:var(--info);
          vertical-align:text-bottom;animation:blink .7s step-end infinite}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
  .chat-empty{padding:20px;text-align:center;color:var(--muted);font-size:12px}
  #clear-chat{background:none;border:1px solid var(--border);color:var(--muted);
              padding:3px 8px;border-radius:4px;font-size:11px;cursor:pointer;min-height:44px}

  /* empty states */
  .empty-state{padding:16px;text-align:center;color:var(--muted);font-size:12px}

  /* attention queue */
  .aq-goal{padding:9px 12px;border-bottom:1px solid var(--border);font-size:12px;
           color:var(--info);line-height:1.4}
  .aq-done{padding:7px 12px;border-bottom:1px solid var(--border);font-size:11px;
           color:var(--ok);line-height:1.4}
  .aq-head{padding:5px 12px;font-size:10px;color:var(--muted);text-transform:uppercase;
           letter-spacing:.5px;border-bottom:1px solid var(--border);background:var(--bg)}
  .aq-step{padding:7px 12px;border-bottom:1px solid var(--border);font-size:12px;
           display:flex;gap:8px;align-items:flex-start;line-height:1.4}
  .aq-bullet{color:var(--muted);flex-shrink:0;margin-top:1px}
  .aq-step-text{flex:1;word-break:break-word}
  .aq-decision{padding:6px 12px;border-bottom:1px solid var(--border);font-size:11px;
               color:var(--muted);display:flex;gap:6px;line-height:1.4}
  .aq-decision-bullet{flex-shrink:0}
  .aq-foot{padding:5px 12px;font-size:10px;color:var(--muted);border-top:1px solid var(--border)}

  /* chat context card */
  #chat-ctx-card{margin:4px 0 8px 0;border:1px solid var(--border);border-radius:6px;
                 background:var(--panel);font-size:11px;overflow:hidden}
  .ctx-head{padding:5px 10px;font-size:10px;color:var(--muted);text-transform:uppercase;
            letter-spacing:.5px;border-bottom:1px solid var(--border);background:var(--bg)}
  .ctx-row{padding:5px 10px;color:var(--text);display:flex;gap:8px;
           border-bottom:1px solid var(--border);line-height:1.5}
  .ctx-row:last-child{border-bottom:none}
  .ctx-key{color:var(--muted);min-width:52px;flex-shrink:0;font-size:10px;
           text-transform:uppercase;letter-spacing:.3px;padding-top:1px}
  .ctx-val{flex:1;word-break:break-word}

  /* attention tabs */
  #attn-tabs{display:flex;overflow-x:auto;scrollbar-width:none;
             border-bottom:1px solid var(--border);background:var(--bg);flex-shrink:0}
  #attn-tabs::-webkit-scrollbar{display:none}
  .atab{padding:7px 14px;cursor:pointer;font-size:11px;color:var(--muted);
        border-bottom:2px solid transparent;white-space:nowrap;min-height:36px;
        display:flex;align-items:center;gap:5px;
        -webkit-tap-highlight-color:transparent;flex-shrink:0;user-select:none}
  .atab.active{color:var(--info);border-bottom-color:var(--info)}
  .atab:active{background:var(--border)}
  .atab-dot{width:5px;height:5px;border-radius:50%;background:var(--ok);flex-shrink:0}
  .atab-dot.dead{background:var(--err)}

  /* per-session attention view */
  .sess-head{padding:8px 12px;font-size:12px;color:var(--info);
             border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}
  .sess-alive{font-size:10px;color:var(--ok)}
  .sess-dead{font-size:10px;color:var(--err)}
  .sess-ago{font-size:10px;color:var(--muted)}
  .sess-log{padding:3px 12px;font-size:11px;line-height:1.5;color:var(--muted);
            border-bottom:1px solid var(--border);word-break:break-all;display:flex;gap:6px}
  .sess-log:last-child{border-bottom:none}
  .sess-log .ts{flex-shrink:0}

  @media(max-width:480px){
    body{font-size:12px}
    .log-box{height:200px}
    .log-box.combined{height:230px}
    #chat-thread{max-height:300px}
    .hive-card{min-width:120px}
  }
"""

# ── local-only CSS ────────────────────────────────────────────────────────────
# Input bar, settings modal, arena panel — not needed on Vercel (read-only UI).

LOCAL_CSS = r"""
  /* sticky input bar */
  #input-bar{position:fixed;bottom:0;left:0;right:0;
    padding:8px 10px;padding-bottom:calc(8px + var(--safe-bottom));
    background:var(--panel);border-top:1px solid var(--border);
    display:flex;flex-direction:column;gap:6px;z-index:50}
  #attach-chips{display:flex;flex-wrap:wrap;gap:4px}
  .attach-chip{display:flex;align-items:center;gap:4px;padding:3px 8px;
    border-radius:12px;font-size:11px;background:var(--bg);
    border:1px solid var(--border);color:var(--muted)}
  .attach-chip .rm{cursor:pointer;color:var(--err);font-size:13px;line-height:1;
                   min-width:16px;text-align:center}
  #input-row{display:flex;gap:6px;align-items:flex-end}
  #attach-btn{background:none;border:1px solid var(--border);color:var(--muted);
    border-radius:4px;padding:0 10px;font-size:17px;cursor:pointer;
    min-height:44px;min-width:44px;flex-shrink:0}
  #attach-btn:active{background:var(--border)}
  #prompt-input{flex:1;background:var(--input-bg);border:1px solid var(--border);
    color:var(--text);padding:10px 11px;border-radius:4px;font-family:inherit;
    font-size:13px;resize:none;min-height:44px;max-height:110px;overflow-y:auto;line-height:1.4}
  #prompt-input:focus{outline:none;border-color:var(--info)}
  #send-btn{background:var(--info);color:#000;border:none;border-radius:4px;
    font-weight:bold;font-size:15px;cursor:pointer;min-height:44px;min-width:52px;flex-shrink:0}
  #send-btn:disabled{background:var(--border);color:var(--muted);cursor:not-allowed}
  #send-btn:active:not(:disabled){opacity:.8}
  #priority-btn{background:#e5c07b;color:#000;border:none;border-radius:4px;
    font-size:15px;cursor:pointer;min-height:44px;min-width:44px;flex-shrink:0;font-weight:bold}
  #priority-btn:disabled{background:var(--border);color:var(--muted);cursor:not-allowed}
  #priority-btn:active:not(:disabled){opacity:.8}
  #file-input{display:none}
"""

# ── shared render JS ──────────────────────────────────────────────────────────
# Pure render functions with no server-specific URL assumptions beyond the
# relative paths shared by all deployments (/api/status/*, /api/status/answer).

SHARED_RENDER_JS = r"""
function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

function _flash(el){
  if(!el)return;
  el.classList.remove('flash');
  void el.offsetWidth; // force reflow so animation restarts
  el.classList.add('flash');
}

// ── active task: cache last known status so the 5s tick has real data ────────
let _lastKnownStatus = null;

function renderStatus(s){
  if(!s)return;
  _lastKnownStatus = s;   // always keep fresh copy for the hang-detector tick
  const upd=document.getElementById('status-updated');
  if(upd&&s.last_updated)upd.textContent=s.last_updated.slice(11,19)+' UTC';
  _renderActiveTask(s);   // active-task bar always first
  _renderHiveHealth(s.hives||{});
  _renderMetrics(s.metrics||{},s.model_champions||{});
  _renderBlockers(s.blockers||[]);
  _renderAchievements(s.achievements||[], s.achievements_total);
  _renderNextSteps(s.next_steps||[]);
  _renderCaps(s.capabilities||{});
  _renderQuestions(s.pending_questions||[]);
  _renderHiveFeed(s);
  _renderChatCtx();
  const mc=s.model_champions||{};
  const tc=document.getElementById('arena-text-champ');
  const vc=document.getElementById('arena-vision-champ');
  if(tc)tc.textContent=mc.text||'—';
  if(vc)vc.textContent=mc.vision||'—';
}

// ── hang detector: fully client-side, never trusts the backend ────────────────
// Maintains a rolling buffer of every log line with its arrival timestamp.
// Runs independently of active_task SSE — can override bar to HANG even when
// the backend claims to be healthy.
const _hangDetector = {
  buf: [],            // [{text, ts}, ...] rolling 200-entry buffer
  MAX_BUF: 200,

  // Thresholds
  SILENCE_MS:       180000,  // 3 min no new logs → SILENT
  REPEAT_COUNT:     5,       // same line ≥5 times in 60 s → LOOP
  REPEAT_WINDOW_MS: 60000,
  ERR_COUNT:        3,       // known error pattern ≥3 times in 30 s → ERROR LOOP
  ERR_WINDOW_MS:    30000,

  // Patterns that historically indicate a stuck loop.
  // Each entry is [regex, human-readable label].
  STUCK: [
    [/\b400\b/,                          '400 error loop'],
    [/does not support thinking/i,       'thinking-mode incompatibility loop'],
    [/connection (refused|timed? ?out)/i,'connection refused/timeout loop'],
    [/ssh.*error|error.*ssh/i,           'SSH error loop'],
    [/git.*timeout|timeout.*git/i,       'git timeout loop'],
    [/retrying\.{0,3}$/i,               'retry loop'],
    [/waiting for/i,                     'waiting-for loop'],
    [/out of memory|oom killed/i,        'OOM loop'],
    [/permanent.*error|error.*permanent/i,'permanent-error loop'],
    [/\[Errno\s+\d+\]/,                 'OS error loop'],
  ],

  feed(rawText, ts) {
    const text = rawText.replace(/\x1b\[[0-9;]*m/g,'').replace(/\s+/g,' ').trim();
    if(!text) return;
    this.buf.push({text, ts});
    if(this.buf.length > this.MAX_BUF) this.buf.shift();
  },

  detect() {
    const now = Date.now();
    if(!this.buf.length) return null;

    // 1. Silence — no logs arriving at all
    const sinceLastMs = now - this.buf[this.buf.length-1].ts;
    if(sinceLastMs > this.SILENCE_MS){
      const secs = Math.round(sinceLastMs/1000);
      return {type:'silence', label:'SILENT', detail:`no log activity for ${secs}s — process may be hung`};
    }

    // 2. Exact-line repetition (first 120 chars = key)
    const window60 = this.buf.filter(e => now - e.ts < this.REPEAT_WINDOW_MS);
    const freq = {};
    for(const e of window60){
      const k = e.text.slice(0,120);
      freq[k] = (freq[k]||0) + 1;
    }
    let worst = null;
    for(const [line, count] of Object.entries(freq)){
      if(count >= this.REPEAT_COUNT && (!worst || count > worst.count))
        worst = {line, count};
    }
    if(worst)
      return {type:'loop',
              label:`LOOP \xd7${worst.count}`,
              detail:`"${worst.line.slice(0,90)}" repeated ${worst.count}\xd7 in 60s`};

    // 3. Known stuck-pattern repetition in last 30 s
    const window30 = this.buf.filter(e => now - e.ts < this.ERR_WINDOW_MS);
    for(const [pat, patLabel] of this.STUCK){
      const hits = window30.filter(e => pat.test(e.text));
      if(hits.length >= this.ERR_COUNT)
        return {type:'error_loop',
                label:`ERROR LOOP \xd7${hits.length}`,
                detail:`${patLabel}: "${hits[hits.length-1].text.slice(0,80)}"`};
    }

    return null;  // no hang
  },
};

// elapsed helpers
let _atTimer = null;
function _atElapsedStr(ms){
  const s=Math.round(ms/1000);
  return s<60? s+'s' : Math.floor(s/60)+'m'+(s%60)+'s';
}
function _atStartTimer(startMs){
  if(_atTimer) clearInterval(_atTimer);
  _atTimer = setInterval(()=>{
    const el=document.getElementById('at-elapsed');
    if(!el){clearInterval(_atTimer);return;}
    el.textContent = _atElapsedStr(Date.now()-startMs);
  },1000);
}

// ── active task bar constants ─────────────────────────────────────────────────
const _AT_TRIAGE_INTERVAL  = 60000;   // must match TRIAGE_INTERVAL in orchestrator.py
const _AT_HB_INTERVAL      = 120000;  // HEARTBEAT_INTERVAL
const _AT_STALE_MS         = 180000;  // 3 min without a running task = suspect

function _renderActiveTask(s){
  const bar = document.getElementById('active-task-bar');
  if(!bar) return;

  // ── Layer 1: frontend hang detection — completely independent of backend ──
  const hang = _hangDetector.detect();
  if(hang){
    bar.className='active-task-bar at-hang';
    bar.innerHTML=
      '<span class="at-dot"></span>'+
      '<span class="at-label">'+esc(hang.label)+'</span>'+
      '<span class="at-detail">'+esc(hang.detail)+'</span>'+
      '<span class="at-src">frontend</span>';
    return;
  }

  // ── Layer 2: backend active_task from SSE — use cache if called from tick ──
  const src = (s && s.active_task !== undefined) ? s : _lastKnownStatus;
  const at  = src && src.active_task;

  // No status data yet (first load before SSE connects)
  if(!src){
    bar.className='active-task-bar at-ok';
    bar.innerHTML='<span class="at-dot"></span>'+
      '<span class="at-label">OK</span>'+
      '<span class="at-detail"> connecting\u2026</span>';
    return;
  }

  // ── Task currently running ─────────────────────────────────────────────────
  if(at && at.status==='running' && !at.completed_at){
    const startedMs = at.started_at ? new Date(at.started_at).getTime() : Date.now();
    const ageMs = Date.now() - startedMs;
    if(ageMs > _AT_STALE_MS){
      // Backend says running but >3 min — suspect hang
      bar.className='active-task-bar at-stale';
      bar.innerHTML=
        '<span class="at-dot"></span>'+
        '<span class="at-label">STALE ('+Math.round(ageMs/1000)+'s)</span>'+
        '<span class="at-detail">'+esc(at.task||'unknown')+'</span>'+
        '<span class="at-src">backend-stale</span>';
      return;
    }
    // Fresh working task
    bar.className='active-task-bar at-working';
    bar.innerHTML=
      '<span class="at-dot"></span>'+
      '<span class="at-label">WORKING</span>'+
      '<span class="at-detail">'+esc((at.agent||'orchestrator')+' \xb7 '+(at.task||''))+'</span>'+
      '<span class="at-elapsed" id="at-elapsed">0s</span>';
    _atStartTimer(startedMs);
    return;
  }

  // ── Between cycles: completed or null ─────────────────────────────────────
  // Show OK + last task + next cycle estimate
  const lastTask      = (at && at.task) ? at.task : '\u2014';
  const completedMs   = (at && at.completed_at) ? new Date(at.completed_at).getTime() : 0;
  const sinceMs       = completedMs ? Date.now() - completedMs : null;
  const sinceStr      = sinceMs !== null ? _atElapsedStr(sinceMs)+' ago' : '';
  // Estimate next triage from completion time (conservative: use triage interval)
  const nextMs        = completedMs ? Math.max(0, _AT_TRIAGE_INTERVAL - sinceMs) : null;
  const nextStr       = nextMs !== null ? 'next ~'+_atElapsedStr(nextMs) : '';

  bar.className='active-task-bar at-ok';
  bar.innerHTML=
    '<span class="at-dot"></span>'+
    '<span class="at-label">OK</span>'+
    '<span class="at-detail"> last: '+esc(lastTask)+(sinceStr?' \xb7 '+sinceStr:'')+'</span>'+
    (nextStr?'<span class="at-next">'+esc(nextStr)+'</span>':'');
  // Update the "X ago" and "next ~Ys" every second
  _atStartOkTimer(completedMs, lastTask);
}

let _atOkTimer = null;
function _atStartOkTimer(completedMs, lastTask){
  if(_atOkTimer) clearInterval(_atOkTimer);
  _atOkTimer = setInterval(()=>{
    const bar = document.getElementById('active-task-bar');
    if(!bar || !bar.classList.contains('at-ok')){ clearInterval(_atOkTimer); return; }
    const sinceMs = completedMs ? Date.now()-completedMs : null;
    const sinceStr= sinceMs!==null ? _atElapsedStr(sinceMs)+' ago' : '';
    const nextMs  = sinceMs!==null ? Math.max(0,_AT_TRIAGE_INTERVAL-sinceMs) : null;
    const nextStr = nextMs!==null ? 'next ~'+_atElapsedStr(nextMs) : '';
    bar.innerHTML=
      '<span class="at-dot"></span>'+
      '<span class="at-label">OK</span>'+
      '<span class="at-detail"> last: '+esc(lastTask)+(sinceStr?' \xb7 '+sinceStr:'')+'</span>'+
      (nextStr?'<span class="at-next">'+esc(nextStr)+'</span>':'');
  },1000);
}

// ── Unified hive feed — blockers + next steps + recent achievements ─────────
function _renderHiveFeed(s){
  const feed=document.getElementById('hive-feed');
  if(!feed)return;
  feed.innerHTML='';
  const blockers=(s.blockers||[]).filter(b=>b.status==='open');
  const steps=(s.next_steps||[]).filter(ns=>ns.status!=='done');
  const achs=(s.achievements||[]).slice(0,3);
  const caps=s.capabilities||{};
  const capCount=caps.count||(caps.learned||caps.recent||[]).length||0;

  if(!blockers.length&&!steps.length&&!achs.length){
    feed.innerHTML='<div class="empty-state" style="padding:8px 0">All clear \u2713</div>';
    return;
  }

  // Blockers
  blockers.forEach(b=>{
    const d=document.createElement('div');
    d.className='blocker-item feed-item'; d.id='blocker-'+b.id;
    d.dataset.testid='blocker-item';
    d.innerHTML=
      '<span class="sev-badge '+esc(b.severity||'medium')+'">'+esc(b.severity||'?')+'</span>'+
      '<div class="blocker-desc">'+esc(b.description)+
        '<div class="blocker-meta">'+esc(b.hive||'')+' \xb7 '+esc((b.ts||'').slice(11,19))+'</div>'+
      '</div>'+
      '<button class="resolve-btn" onclick="resolveBlocker(\''+esc(b.id)+'\',this)">Resolve</button>';
    feed.appendChild(d);
  });

  // Pending next steps (top 5 by priority)
  steps.slice(0,5).forEach(ns=>{
    const d=document.createElement('div');
    d.className='ns-item feed-item'; d.dataset.testid='next-step-item';
    d.innerHTML=
      '<div class="ns-check" onclick="toggleStep(\''+esc(ns.id)+'\',this)"></div>'+
      '<div class="ns-text">'+esc(ns.description)+'</div>'+
      '<div class="ns-meta">P'+(ns.priority||5)+'</div>';
    feed.appendChild(d);
  });

  // Recent achievements
  achs.forEach(a=>{
    const d=document.createElement('div');
    d.className='achievement-item feed-item'; d.dataset.testid='achievement-item';
    d.innerHTML=
      '<div class="ach-icon">\uD83C\uDFC6</div>'+
      '<div class="ach-body">'+
        '<div class="ach-desc">'+esc(a.description)+'</div>'+
        '<div class="ach-meta">'+esc(a.hive||'')+' \xb7 '+esc((a.ts||'').slice(11,19))+'</div>'+
      '</div>';
    feed.appendChild(d);
  });

  // Capabilities summary
  if(capCount>0){
    const d=document.createElement('div');
    d.className='feed-item'; d.style.cssText='padding:6px 8px;font-size:11px;color:var(--muted)';
    d.textContent=capCount+' learned capabilities \u2014 see Config \u2192 Arena for details';
    feed.appendChild(d);
  }
}

function _renderHiveHealth(hives){
  const grid=document.getElementById('hive-health-grid');
  if(!grid)return;
  const keys=Object.keys(hives);
  if(!keys.length){
    grid.innerHTML='<div class="empty-state" style="padding:10px 12px">No hive data yet</div>';
    return;
  }
  grid.innerHTML='';
  keys.forEach(name=>{
    const h=hives[name];
    const score=Math.round((h.health_score||0)*100);
    const barCls=score<40?'err':score<70?'warn':'';
    const statusColor=h.status==='running'?'var(--ok)':(h.status==='error'?'var(--err)':'var(--warn)');
    const card=document.createElement('div');
    card.className='hive-card';
    card.dataset.testid='hive-card';
    card.innerHTML=
      '<div class="hc-name">'+esc(name)+'</div>'+
      '<div class="hc-status" style="color:'+statusColor+'">'+esc(h.status||'unknown')+'</div>'+
      '<div class="hc-bar-wrap"><div class="hc-bar '+barCls+'" style="width:'+score+'%"></div></div>'+
      '<div class="hc-meta">'+score+'% health \xb7 '+(h.errors_last_hour||0)+' errors/h \xb7 '+(h.tasks_completed_today||0)+' tasks today</div>';
    grid.appendChild(card);
    _flash(card);
  });
}

function _renderMetrics(m, champs){
  const row=document.getElementById('metrics-row');
  if(!row)return;
  const boxes=[
    {val:m.tasks_completed_total||0,   label:'Tasks Done'},
    {val:m.tasks_failed_total||0,      label:'Failed'},
    {val:m.openrouter_calls_today||0,  label:'API Calls Today'},
    {val:((m.error_rate_24h||0)*100).toFixed(1)+'%', label:'Error Rate 24h'},
  ];
  row.innerHTML=boxes.map(b=>
    '<div class="metric-box"><div class="metric-val">'+esc(String(b.val))+'</div>'+
    '<div class="metric-label">'+esc(b.label)+'</div></div>'
  ).join('');
}

function _renderBlockers(blockers){
  const list=document.getElementById('blockers-list');
  if(!list)return;
  const open=blockers.filter(b=>b.status==='open');
  const cnt=document.getElementById('blockers-count');
  if(cnt)cnt.textContent=open.length+' open';
  if(!open.length){
    list.innerHTML='<div class="empty-state" id="blockers-empty">No open blockers</div>';
    return;
  }
  list.innerHTML='';
  open.forEach(b=>{
    const d=document.createElement('div');
    d.className='blocker-item'; d.id='blocker-'+b.id;
    d.dataset.testid='blocker-item';
    d.innerHTML=
      '<span class="sev-badge '+esc(b.severity||'medium')+'">'+esc(b.severity||'?')+'</span>'+
      '<div class="blocker-desc">'+esc(b.description)+
        '<div class="blocker-meta">'+esc(b.hive||'')+' \xb7 '+esc((b.ts||'').slice(11,19))+'</div>'+
      '</div>'+
      '<button class="resolve-btn" onclick="resolveBlocker(\''+esc(b.id)+'\',this)">Resolve</button>';
    list.appendChild(d);
    _flash(d);
  });
}

function resolveBlocker(bid, btn){
  btn.disabled=true;
  fetch('/api/status/blocker/'+bid,{method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({status:'resolved',resolution:'Manually resolved via UI'})})
  .then(()=>{ const el=document.getElementById('blocker-'+bid); if(el)el.remove(); })
  .catch(()=>{btn.disabled=false;});
}

function _renderAchievements(achs, total){
  const list=document.getElementById('achievements-list');
  if(!list)return;
  const cnt=document.getElementById('ach-count');
  if(cnt)cnt.textContent=(total!=null?total:achs.length);
  if(!achs.length){
    list.innerHTML='<div class="empty-state">No achievements yet</div>';
    return;
  }
  list.innerHTML='';
  achs.slice(0,10).forEach(a=>{
    const d=document.createElement('div');
    d.className='achievement-item';
    d.dataset.testid='achievement-item';
    d.innerHTML=
      '<div class="ach-icon">\uD83C\uDFC6</div>'+
      '<div class="ach-body">'+
        '<div class="ach-desc">'+esc(a.description)+'</div>'+
        '<div class="ach-meta">'+esc(a.hive||'')+' \xb7 '+esc(a.agent||'')+' \xb7 '+esc((a.ts||'').slice(11,19))+
          (a.evidence?' \xb7 '+esc(a.evidence):'')+
        '</div>'+
      '</div>';
    list.appendChild(d);
  });
}

function _renderNextSteps(steps){
  const list=document.getElementById('nextsteps-list');
  if(!list)return;
  const cnt=document.getElementById('ns-count');
  if(cnt)cnt.textContent=steps.length;
  if(!steps.length){
    list.innerHTML='<div class="empty-state">No next steps</div>';
    return;
  }
  list.innerHTML='';
  steps.slice(0,10).forEach(ns=>{
    const done=ns.status==='done';
    const d=document.createElement('div');
    d.className='ns-item';
    d.dataset.testid='next-step-item';
    d.innerHTML=
      '<div class="ns-check '+(done?'done':'')+'" onclick="toggleStep(\''+esc(ns.id)+'\',this)">'+(done?'\u2713':'')+'</div>'+
      '<div class="ns-text '+(done?'done':'')+'">'+esc(ns.description)+'</div>'+
      '<div class="ns-meta">P'+(ns.priority||5)+'</div>';
    list.appendChild(d);
  });
}

function toggleStep(id, el){
  const isDone=el.classList.contains('done');
  const newStatus=isDone?'pending':'done';
  fetch('/api/status/next-step/'+id,{method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({status:newStatus})}).catch(()=>{});
  el.classList.toggle('done',!isDone);
  el.textContent=isDone?'':'\u2713';
  const txt=el.nextSibling;
  if(txt)txt.classList.toggle('done',!isDone);
}

function _renderCaps(caps){
  const list=document.getElementById('caps-list');
  if(!list)return;
  const learned=(caps.recent||caps.learned||[]);
  const count=caps.count||learned.length;
  const cnt=document.getElementById('caps-count');
  if(cnt)cnt.textContent=count;
  if(!learned.length){
    list.innerHTML='<div class="empty-state">No capabilities learned yet</div>';
    return;
  }
  list.innerHTML='';
  learned.forEach(c=>{
    const d=document.createElement('div');
    d.className='cap-item';
    d.dataset.testid='capability-item';
    const detId='cap-det-'+(c.id||Math.random().toString(36).slice(2));
    // Support both schemas:
    //   API-added:         { skill, description, example, tags, source_hive, ts }
    //   human-correction:  { title, rule, source, learned_at, last_updated }
    const skillLabel = c.skill || c.title || '?';
    const descLabel  = c.description || c.rule || '';
    const detail     = c.example || c.rule || '';
    const when       = (c.ts || c.learned_at || '').slice(0,10);
    const from       = c.source_hive || c.source || '?';
    d.innerHTML=
      '<div class="cap-header" onclick="document.getElementById(\''+detId+'\').classList.toggle(\'open\')">'+
        '<span class="cap-skill">'+esc(skillLabel)+'</span>'+
        '<span class="cap-desc">'+esc(descLabel)+'</span>'+
      '</div>'+
      '<div class="cap-detail" id="'+detId+'">'+
        (detail?'<div class="cap-example">'+esc(detail)+'</div>':'')+
        (c.tags&&c.tags.length?'<div class="cap-tags">'+c.tags.map(t=>'<span class="cap-tag">'+esc(t)+'</span>').join('')+'</div>':'')+
        '<div style="font-size:10px;color:var(--muted);margin-top:4px">from '+esc(from)+' \xb7 '+esc(when)+'</div>'+
      '</div>';
    list.appendChild(d);
  });
}

function _renderQuestions(pqs){
  const unanswered=pqs.filter(q=>!q.answered);
  let overlay=document.getElementById('q-overlay');
  const sb=document.getElementById('send-btn');
  if(!unanswered.length){
    if(overlay)overlay.remove();
    if(sb&&sb.dataset.disabledByQ==='1'){
      sb.disabled=false;
      sb.removeAttribute('data-disabled-by-q');
      sb.title='';
    }
    return;
  }
  if(sb){
    sb.disabled=true;
    sb.dataset.disabledByQ='1';
    sb.title='Answer the pending questions to enable chat';
  }
  if(!overlay){
    overlay=document.createElement('div');
    overlay.id='q-overlay';
    overlay.style.cssText='position:fixed;inset:0;z-index:900;background:rgba(0,0,0,.6);display:flex;align-items:flex-start;justify-content:center;padding-top:60px';
    document.body.appendChild(overlay);
  }
  overlay.innerHTML='';
  const card=document.createElement('div');
  card.style.cssText='background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px;width:90%;max-width:480px;max-height:80vh;overflow-y:auto';
  let html='<div style="font-size:13px;font-weight:bold;color:var(--err);margin-bottom:12px">Action Required</div>';
  unanswered.forEach(q=>{
    html+='<div style="margin-bottom:14px" data-qid="'+esc(q.id)+'">';
    html+='<div style="font-size:12px;color:var(--text);margin-bottom:4px">'+esc(q.question);
    if(q.hint)html+=' <span style="color:var(--muted);font-size:10px">('+esc(q.hint)+')</span>';
    html+='</div>';
    if(q.type==='choice'&&q.choices&&q.choices.length){
      html+='<select class="q-ans-input" style="width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);padding:7px 8px;border-radius:4px;font-size:12px">';
      q.choices.forEach(c=>{html+='<option value="'+esc(c)+'">'+esc(c)+'</option>';});
      html+='</select>';
    } else {
      html+='<input class="q-ans-input" type="text" placeholder="Type answer..." style="width:100%;box-sizing:border-box;background:var(--input-bg);border:1px solid var(--border);color:var(--text);padding:8px 10px;border-radius:4px;font-size:12px">';
    }
    html+='</div>';
  });
  html+='<button onclick="submitQAnswers()" style="width:100%;padding:10px;background:var(--info);color:#000;border:none;border-radius:4px;font-size:13px;cursor:pointer;margin-top:4px">Submit Answers</button>';
  card.innerHTML=html;
  overlay.appendChild(card);
}

function submitQAnswers(){
  const items=document.querySelectorAll('#q-overlay [data-qid]');
  const promises=[];
  items.forEach(item=>{
    const qid=item.dataset.qid;
    const inp=item.querySelector('.q-ans-input');
    const val=inp?(inp.value||'').trim():'';
    if(!val)return;
    promises.push(
      fetch('/api/status/answer',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:qid,answer:val,answered_by:'human'})})
    );
  });
  Promise.all(promises).then(()=>{
    fetch('/api/status').then(r=>r.json()).then(renderStatus).catch(()=>{});
  }).catch(()=>{});
}

// ── browser context collector ─────────────────────────────────────────────────
function _collectBrowserCtx(){
  const tz=Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';
  const lang=navigator.language||'en';
  const now=new Date();
  const now_local=now.toLocaleString(lang,{timeZone:tz,hour12:false,
    weekday:'short',year:'numeric',month:'short',day:'numeric',
    hour:'2-digit',minute:'2-digit'});
  const screen_info=screen.width+'\xd7'+screen.height;
  const ua=navigator.userAgent;
  let ua_short='browser';
  if(/Edg\//.test(ua))ua_short='Edge';
  else if(/Chrome\//.test(ua))ua_short='Chrome';
  else if(/Firefox\//.test(ua))ua_short='Firefox';
  else if(/Safari\//.test(ua)&&!/Chrome/.test(ua))ua_short='Safari';
  const conn=navigator.connection?(navigator.connection.effectiveType||navigator.connection.type||null):null;
  return {tz,lang,now_local,screen:screen_info,ua_short,connection:conn};
}

// ── chat context card ─────────────────────────────────────────────────────────
// Visible only when chat-thread has no user/AI bubbles.
// Shows hive brain state (if SSE has fired) and client browser context.
// Neither section is ever sent to the server unless the user submits a prompt.
function _renderChatCtx(){
  const thread=document.getElementById('chat-thread');
  if(!thread)return;
  // Hide (remove) the card as soon as any bubble appears
  if(thread.querySelector('.bubble')){
    const card=document.getElementById('chat-ctx-card');
    if(card)card.remove();
    return;
  }
  let card=document.getElementById('chat-ctx-card');
  if(!card){
    card=document.createElement('div');
    card.id='chat-ctx-card';
    const emptyEl=document.getElementById('chat-empty');
    if(emptyEl)thread.insertBefore(card,emptyEl);
    else thread.insertBefore(card,thread.firstChild);
  }
  const bc=_collectBrowserCtx();
  let html='';
  // HIVE section — populated only after first SSE event
  const s=_lastKnownStatus;
  if(s){
    const sessions=s.orchestrator_sessions||[];
    const sess=sessions.length?sessions[sessions.length-1]:null;
    const hive=Object.values(s.hives||{})[0]||{};
    const nBlockers=(s.blockers||[]).filter(b=>b.status==='open').length;
    const nPending=(s.next_steps||[]).filter(ns=>ns.status==='pending').length;
    const updMs=s.last_updated?Date.now()-new Date(s.last_updated).getTime():null;
    const updAgo=updMs!==null?_atElapsedStr(updMs)+' ago':'';
    html+='<div class="ctx-head">Hive</div>';
    if(sess&&sess.goal)
      html+='<div class="ctx-row"><span class="ctx-key">goal</span><span class="ctx-val">'+esc(sess.goal)+'</span></div>';
    html+='<div class="ctx-row"><span class="ctx-key">health</span><span class="ctx-val">'
      +esc(Math.round((hive.health_score||0)*100)+'%')
      +' \xb7 '+esc((hive.sessions||[]).length+' sessions')
      +' \xb7 '+esc(nBlockers+' blocker'+(nBlockers!==1?'s':''))
      +' \xb7 '+esc(nPending+' pending')
      +'</span></div>';
    const at=s.active_task;
    if(at&&at.task&&at.status==='running')
      html+='<div class="ctx-row"><span class="ctx-key">active</span><span class="ctx-val">'+esc(at.task)+'</span></div>';
    if(updAgo)
      html+='<div class="ctx-row"><span class="ctx-key">updated</span><span class="ctx-val">'+esc(updAgo)+'</span></div>';
  }
  // YOU section — always visible, purely client-side
  html+='<div class="ctx-head">You</div>';
  html+='<div class="ctx-row"><span class="ctx-key">time</span><span class="ctx-val">'+esc(bc.now_local)+'</span></div>';
  html+='<div class="ctx-row"><span class="ctx-key">tz</span><span class="ctx-val">'+esc(bc.tz)+'</span></div>';
  html+='<div class="ctx-row"><span class="ctx-key">locale</span><span class="ctx-val">'+esc(bc.lang)+'</span></div>';
  html+='<div class="ctx-row"><span class="ctx-key">screen</span><span class="ctx-val">'+esc(bc.screen)+' \xb7 '+esc(bc.ua_short)+'</span></div>';
  if(bc.connection)
    html+='<div class="ctx-row"><span class="ctx-key">net</span><span class="ctx-val">'+esc(bc.connection)+'</span></div>';
  card.innerHTML=html;
}

// ── attention queue (compaction-driven) ───────────────────────────────────────
// Reads orchestrator_sessions[-1] from the SSE status payload.
// Renders: goal · done · open blockers · next steps · key decisions.
function _renderAttentionQueue(s){
  const list=document.getElementById('queue-list');
  const emptyEl=document.getElementById('queue-empty');
  const cnt=document.getElementById('queue-count');
  if(!list)return;
  const sessions=s.orchestrator_sessions||[];
  const sess=sessions.length?sessions[sessions.length-1]:null;
  const blockers=(s.blockers||[]).filter(b=>b.status==='open');
  if(!sess){
    list.innerHTML='';
    if(emptyEl)emptyEl.style.display='block';
    if(cnt)cnt.textContent='\u2014';
    return;
  }
  if(emptyEl)emptyEl.style.display='none';
  list.innerHTML='';
  let totalItems=0;
  // Goal
  if(sess.goal){
    const d=document.createElement('div');
    d.className='aq-goal';
    d.innerHTML='<span style="font-size:10px;color:var(--muted);text-transform:uppercase;'
      +'letter-spacing:.5px;margin-right:6px">goal</span>'+esc(sess.goal);
    list.appendChild(d);
  }
  // Progress / Done
  if(sess.progress){
    const d=document.createElement('div');
    d.className='aq-done';
    d.innerHTML='<span style="font-size:10px;text-transform:uppercase;'
      +'letter-spacing:.5px;margin-right:6px">done</span>'+esc(sess.progress);
    list.appendChild(d);
  }
  // Open blockers (live from hive-status)
  if(blockers.length){
    const head=document.createElement('div');
    head.className='aq-head'; head.textContent='Blockers';
    list.appendChild(head);
    blockers.forEach(b=>{
      const d=document.createElement('div');
      d.className='blocker-item'; d.id='blocker-'+b.id;
      d.innerHTML=
        '<span class="sev-badge '+esc(b.severity||'medium')+'">'+esc(b.severity||'?')+'</span>'+
        '<div class="blocker-desc">'+esc(b.description)+
          '<div class="blocker-meta">'+esc(b.hive||'')+' \xb7 '+esc((b.ts||'').slice(11,19))+'</div>'+
        '</div>'+
        '<button class="resolve-btn" onclick="resolveBlocker(\''+esc(b.id)+'\',this)">Resolve</button>';
      list.appendChild(d);
      totalItems++;
    });
  }
  // Next steps (LLM action strings from compaction)
  const steps=sess.next_steps||[];
  if(steps.length){
    const head=document.createElement('div');
    head.className='aq-head'; head.textContent='Needs attention';
    list.appendChild(head);
    steps.forEach(text=>{
      const d=document.createElement('div');
      d.className='aq-step';
      d.innerHTML='<span class="aq-bullet">\u25cb</span><span class="aq-step-text">'+esc(text)+'</span>';
      list.appendChild(d);
      totalItems++;
    });
  }
  // Key decisions
  const decisions=sess.decisions||[];
  if(decisions.length){
    const head=document.createElement('div');
    head.className='aq-head'; head.textContent='Decisions';
    list.appendChild(head);
    decisions.forEach(text=>{
      const d=document.createElement('div');
      d.className='aq-decision';
      d.innerHTML='<span class="aq-decision-bullet">\u25b8</span><span>'+esc(text)+'</span>';
      list.appendChild(d);
    });
  }
  // Footer: last compaction timestamp
  if(sess.ts){
    const foot=document.createElement('div');
    foot.className='aq-foot';
    foot.textContent='Last compaction: '+sess.ts.slice(11,19)+' UTC';
    list.appendChild(foot);
  }
  if(cnt)cnt.textContent=totalItems+(totalItems===1?' item':' items');
}
"""

# ── local status JS ───────────────────────────────────────────────────────────
# Everything that depends on the local server: SSE endpoints, log stream,
# config, onboarding, settings, arena, chat, queue, file upload.

LOCAL_STATUS_JS = r"""
// ── uid ───────────────────────────────────────────────────────────────────────
// Persistent per-browser identity for multi-user privacy isolation.
// Stored in localStorage under 'hive_uid'; sent as X-Hive-UID on API calls.
const UID_KEY = 'hive_uid';
function _genUid(){
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  b[6]=(b[6]&0x0f)|0x40; b[8]=(b[8]&0x3f)|0x80;  // UUID v4 bits
  const h=Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');
  return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20);
}
const HIVE_UID = (()=>{
  let id=localStorage.getItem(UID_KEY);
  if(!id){id=_genUid();localStorage.setItem(UID_KEY,id);}
  return id;
})();
/** Fetch wrapper that automatically includes X-Hive-UID header. */
function hiveFetch(url, opts={}){
  const headers = Object.assign({'X-Hive-UID': HIVE_UID}, opts.headers||{});
  return fetch(url, Object.assign({}, opts, {headers}));
}
// Patch window.fetch so all API calls automatically carry X-Hive-UID.
(()=>{
  const _origFetch = window.fetch;
  window.fetch = function(input, init={}) {
    // Only inject on relative or same-origin API paths
    const url = typeof input === 'string' ? input : (input.url || '');
    if (url.startsWith('/api') || url.startsWith('/stream') || url.startsWith('/status')) {
      const headers = Object.assign({'X-Hive-UID': HIVE_UID},
        init.headers instanceof Headers
          ? Object.fromEntries(init.headers.entries())
          : (init.headers || {}));
      return _origFetch.call(this, input, Object.assign({}, init, {headers}));
    }
    return _origFetch.call(this, input, init);
  };
})();

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('queue-section').open=true;
  document.getElementById('chat-section').open=true;
  _renderChatCtx();
  restoreChat();
  startStatusStream();
  setTimeout(()=>{const p=document.getElementById('prompt-input');if(p)p.focus();},300);
});

// ── log stream ────────────────────────────────────────────────────────────────
const PALETTE=[
  ['#181818','#f0f0f0'],['#1a1a1a','#c0c0c0'],['#141414','#e0e0e0'],
  ['#1e1e1e','#a8a8a8'],['#121212','#d8d8d8'],['#202020','#b8b8b8'],
  ['#0e0e0e','#ececec'],['#161616','#989898'],
];
const _colorIdx={};
function badgeStyle(s){
  if(!(s in _colorIdx))_colorIdx[s]=Object.keys(_colorIdx).length%PALETTE.length;
  const[bg,fg]=PALETTE[_colorIdx[s]]; return 'background:'+bg+';color:'+fg;
}
function lineClass(t){
  const l=t.toLowerCase();
  if(/error|kill|sigkill|failed|\^c/.test(l))return 'err';
  if(/warning|warn|stalled|reset/.test(l))return 'warn';
  if(/succeeded|success|completed/.test(l))return 'ok';
  return '';
}
// ── ANSI → HTML ───────────────────────────────────────────────────────────────
// Full ANSI renderer: 3/4-bit, 256-color (38;5;n), 24-bit TrueColor (38;2;r;g;b),
// bold, dim, italic, underline, strikethrough, blink, reverse, reset.
const _A3={30:'#888',31:'#e06c75',32:'#98c379',33:'#e5c07b',34:'#61afef',
  35:'#c678dd',36:'#56b6c2',37:'#dcdfe4',
  90:'#555',91:'#ff6b6b',92:'#a8e6a3',93:'#ffd93d',
  94:'#74b9ff',95:'#fd79a8',96:'#81ecec',97:'#fff'};
// xterm 256-color palette (indices 0-15 use named, 16-231 color cube, 232-255 grayscale)
function _ansi256(n){
  if(n<16){const m={0:'#000',1:'#800000',2:'#008000',3:'#808000',4:'#000080',5:'#800080',6:'#008080',7:'#c0c0c0',8:'#808080',9:'#ff0000',10:'#00ff00',11:'#ffff00',12:'#0000ff',13:'#ff00ff',14:'#00ffff',15:'#fff'};return m[n]||'#888';}
  if(n<232){n-=16;const b=n%6,g=Math.floor(n/6)%6,r=Math.floor(n/36);const v=x=>x?x*40+55:0;return 'rgb('+v(r)+','+v(g)+','+v(b)+')';}
  const l=8+(n-232)*10; return 'rgb('+l+','+l+','+l+')';
}
function ansiToHtml(raw){
  let s=String(raw).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  // Strip non-SGR sequences (cursor movement, erase, etc.) cleanly
  s=s.replace(/\x1b\[[0-9;]*[ABCDEFGHJKSTfmisu]/g,m=>m.endsWith('m')?m:'');
  let open=0;
  s=s.replace(/\x1b\[([0-9;]*)m/g,(_,codes)=>{
    const parts=(codes||'0').split(';'); let tag=''; let i=0;
    while(i<parts.length){
      const c=+parts[i++];
      if(c===0){if(open){tag+='</span>'.repeat(open);open=0;}}
      else if(c===1){tag+='<span style="font-weight:bold">';open++;}
      else if(c===2){tag+='<span style="opacity:.6">';open++;}
      else if(c===3){tag+='<span style="font-style:italic">';open++;}
      else if(c===4){tag+='<span style="text-decoration:underline">';open++;}
      else if(c===9){tag+='<span style="text-decoration:line-through">';open++;}
      else if(_A3[c]){tag+='<span style="color:'+_A3[c]+'">';open++;}
      else if(c>=40&&c<=47){tag+='<span style="background:'+(_A3[c-10]||'')+'">'; open++;}
      else if(c>=100&&c<=107){tag+='<span style="background:'+(_A3[c-60]||'')+'">'; open++;}
      else if(c===38||c===48){
        const isBg=c===48;
        const mode=+parts[i++];
        let color='';
        if(mode===5&&i<parts.length){color=_ansi256(+parts[i++]);}
        else if(mode===2&&i+2<parts.length){color='rgb('+parts[i++]+','+parts[i++]+','+parts[i++]+')';}
        if(color){tag+='<span style="'+(isBg?'background':'color')+':'+color+'">';open++;}
      }
    }
    return tag;
  });
  return s+(open?'</span>'.repeat(open):'');
}

function addLogLine(box,session,text,ts){
  const d=document.createElement('div');
  d.className='logline '+lineClass(text);
  const badge=session?'<span class="badge" style="'+badgeStyle(session)+'">'+esc(session)+'</span>':'';
  d.innerHTML='<span class="ts">'+esc(ts)+'</span>'+badge+ansiToHtml(text);
  box.appendChild(d);
  while(box.children.length>300)box.removeChild(box.firstChild);
  box.scrollTop=box.scrollHeight;
  // Feed every line into the hang detector (independent of backend)
  _hangDetector.feed(text, Date.now());
}

// ── combined log buffer (capped 400) — used by per-session attention tabs ─────
let _combinedBuf = [];

const logEs=new EventSource('/stream');
logEs.onmessage=function(e){
  const data=JSON.parse(e.data);
  const cb=document.getElementById('combined');
  const entries=data.combined||[];
  entries.forEach(entry=>{
    addLogLine(cb,entry.session,entry.line,entry.ts);
    _combinedBuf.push(entry);
  });
  if(_combinedBuf.length>400)_combinedBuf=_combinedBuf.slice(-400);
  if(cb)document.getElementById('combined-count').textContent=cb.children.length+' lines';
  // refresh active per-session tab live
  if(_activeAttnTab&&_activeAttnTab!=='all'&&_lastKnownStatus)
    _renderSessionAttn(_lastKnownStatus,_activeAttnTab);
};
logEs.onerror=function(){};
logEs.onopen=function(){};

// Re-evaluate the hang detector every 5 s even without a status SSE event.
// Uses _lastKnownStatus (cached from last SSE) so it has real data, not null.
// This ensures the bar turns red if logs go silent or loop — independent of backend.
setInterval(()=>_renderActiveTask(null), 5000);

// ── live status stream ────────────────────────────────────────────────────────
const statusDot=document.getElementById('status-dot');
let _statusStreamActive=false;
function startStatusStream(){
  if(_statusStreamActive)return;   // prevent double-connection on rapid errors
  _statusStreamActive=true;
  const es=new EventSource('/status/stream');
  es.onopen=()=>statusDot.className='status-dot live';
  es.onmessage=e=>{
    try{
      const d=JSON.parse(e.data);
      renderStatus(d);
      _buildAttnTabs(d);
      if(_activeAttnTab==='all') _renderAttentionQueue(d);
      else _renderSessionAttn(d,_activeAttnTab);
    }catch{}
  };
  es.onerror=()=>{
    statusDot.className='status-dot dead';
    es.close();
    _statusStreamActive=false;
    setTimeout(startStatusStream,5000);
  };
}

// ── attention tabs ────────────────────────────────────────────────────────────
let _activeAttnTab = 'all';
let _lastTabSessions = '';   // serialised session list — skip rebuild if unchanged

function switchAttnTab(name){
  _activeAttnTab=name;
  document.querySelectorAll('.atab').forEach(t=>{
    t.classList.toggle('active',t.dataset.tab===name);
  });
  if(!_lastKnownStatus)return;
  if(name==='all') _renderAttentionQueue(_lastKnownStatus);
  else _renderSessionAttn(_lastKnownStatus,name);
}

function _buildAttnTabs(s){
  const bar=document.getElementById('attn-tabs'); if(!bar)return;
  const sessions=[];
  Object.values(s.hives||{}).forEach(h=>{
    (h.sessions||[]).forEach(n=>{if(!sessions.includes(n))sessions.push(n);});
  });
  const key=sessions.slice().sort().join(',');
  if(key===_lastTabSessions)return;   // no change — skip DOM rebuild
  _lastTabSessions=key;
  bar.innerHTML='';
  // All tab
  const allTab=document.createElement('div');
  allTab.className='atab'+(_activeAttnTab==='all'?' active':'');
  allTab.dataset.tab='all'; allTab.textContent='All';
  allTab.onclick=()=>switchAttnTab('all');
  bar.appendChild(allTab);
  // Per-session tabs
  sessions.forEach(name=>{
    const t=document.createElement('div');
    t.className='atab'+(_activeAttnTab===name?' active':'');
    t.dataset.tab=name;
    const dot=document.createElement('span');
    dot.className='atab-dot';   // all sessions are alive if they appear in hives
    t.appendChild(dot);
    t.appendChild(document.createTextNode(name));
    t.onclick=()=>switchAttnTab(name);
    bar.appendChild(t);
  });
}

function _renderSessionAttn(s,name){
  const list=document.getElementById('queue-list');
  const emptyEl=document.getElementById('queue-empty');
  if(!list)return;
  if(emptyEl)emptyEl.style.display='none';
  list.innerHTML='';
  // Header: session alive?
  const hive=Object.values(s.hives||{})[0]||{};
  const alive=(hive.sessions||[]).includes(name);
  const sessLogs=_combinedBuf.filter(e=>e.session===name);
  const lastLog=sessLogs.length?sessLogs[sessLogs.length-1]:null;
  const head=document.createElement('div');
  head.className='sess-head';
  head.innerHTML=
    '<span style="font-weight:bold">'+esc(name)+'</span>'+
    '<span class="'+(alive?'sess-alive':'sess-dead')+'">'+(alive?'running':'not in sessions')+'</span>'+
    (lastLog?'<span class="sess-ago">last log '+esc(lastLog.ts)+'</span>':'');
  list.appendChild(head);
  // Blockers for this session
  const blockers=(s.blockers||[]).filter(b=>
    b.status==='open'&&(b.agent===name||(b.description||'').toLowerCase().includes(name.toLowerCase()))
  );
  if(blockers.length){
    const bh=document.createElement('div');
    bh.className='aq-head'; bh.textContent='Blockers';
    list.appendChild(bh);
    blockers.forEach(b=>{
      const d=document.createElement('div');
      d.className='blocker-item'; d.id='blocker-'+b.id;
      d.innerHTML=
        '<span class="sev-badge '+esc(b.severity||'medium')+'">'+esc(b.severity||'?')+'</span>'+
        '<div class="blocker-desc">'+esc(b.description)+
          '<div class="blocker-meta">'+esc((b.ts||'').slice(11,19))+'</div></div>'+
        '<button class="resolve-btn" onclick="resolveBlocker(\''+esc(b.id)+'\',this)">Resolve</button>';
      list.appendChild(d);
    });
  }
  // Recent log lines
  const recent=sessLogs.slice(-8);
  if(recent.length){
    const lh=document.createElement('div');
    lh.className='aq-head'; lh.textContent='Recent activity';
    list.appendChild(lh);
    recent.forEach(entry=>{
      const d=document.createElement('div');
      d.className='sess-log '+lineClass(entry.line);
      d.innerHTML='<span class="ts">'+esc(entry.ts)+'</span><span>'+ansiToHtml(entry.line)+'</span>';
      list.appendChild(d);
    });
  } else {
    const nol=document.createElement('div');
    nol.className='empty-state'; nol.textContent='No recent log lines';
    list.appendChild(nol);
  }
}

// ── file attachments ──────────────────────────────────────────────────────────
let pendingAttachments=[];
function triggerAttach(){document.getElementById('file-input').click();}
async function handleFiles(evt){
  for(const file of evt.target.files){
    const fd=new FormData(); fd.append('file',file);
    try{
      const r=await fetch('/api/upload',{method:'POST',body:fd});
      const info=await r.json();
      if(info.id){pendingAttachments.push(info);renderChips();}
    }catch(e){console.error('upload failed',e);}
  }
  evt.target.value='';
}
function renderChips(){
  const bar=document.getElementById('attach-chips'); bar.innerHTML='';
  pendingAttachments.forEach((att,idx)=>{
    const chip=document.createElement('div'); chip.className='attach-chip';
    chip.dataset.testid='attach-chip';
    const icon=att.is_image?'\uD83D\uDDBC':att.type==='text'?'\uD83D\uDCC4':'\uD83D\uDCE6';
    chip.innerHTML=icon+' <span>'+esc(att.filename)+'</span><span class="rm" onclick="removeChip('+idx+')">\u2715</span>';
    bar.appendChild(chip);
  });
}
function removeChip(idx){pendingAttachments.splice(idx,1);renderChips();}

// ── chat ──────────────────────────────────────────────────────────────────────
function autoGrow(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,110)+'px';}
function handleKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendPrompt();}}
async function restoreChat(){
  _renderChatCtx();   // show browser/hive context immediately before fetch resolves
  try{
    const r=await fetch('/api/chat'); if(!r.ok)return;
    const msgs=await r.json(); if(!msgs.length)return;
    const thread=document.getElementById('chat-thread');
    document.getElementById('chat-empty').style.display='none';
    const card=document.getElementById('chat-ctx-card'); if(card)card.remove();
    msgs.forEach(m=>{
      const role=m.role==='user'?'user':'ai';
      const d=document.createElement('div'); d.className='bubble '+role;
      d.innerHTML='<div class="role-label">'+(role==='user'?'You':'Hive')+'</div><div class="bubble-text">'+esc(m.content||m.text||'')+'</div>';
      thread.appendChild(d);
    });
    thread.scrollTop=thread.scrollHeight;
  }catch{}
}
function addBubble(role,text){
  const thread=document.getElementById('chat-thread');
  document.getElementById('chat-empty').style.display='none';
  const card=document.getElementById('chat-ctx-card'); if(card)card.remove();
  const d=document.createElement('div'); d.className='bubble '+role;
  d.innerHTML='<div class="role-label">'+(role==='user'?'You':'Hive')+'</div><div class="bubble-text">'+esc(text)+'</div>';
  thread.appendChild(d); thread.scrollTop=thread.scrollHeight;
  return d.querySelector('.bubble-text');
}
let _sending=false;
let _browserCtxSent=false;
async function sendPrompt(priority=false){
  if(_sending)return;
  const input=document.getElementById('prompt-input');
  const prompt=input.value.trim(); if(!prompt)return;
  _sending=true;
  document.getElementById('send-btn').disabled=true;
  const pb=document.getElementById('priority-btn');
  if(pb)pb.disabled=true;
  input.value=''; autoGrow(input);
  addBubble('user', priority ? '⚡ [PRIORITY] '+prompt : prompt);
  const attachIds=pendingAttachments.map(a=>a.id);
  pendingAttachments.length=0; renderChips();
  const thread=document.getElementById('chat-thread');
  const aiBubble=document.createElement('div'); aiBubble.className='bubble ai';
  aiBubble.innerHTML='<div class="role-label">Hive</div><div class="bubble-text"><span class="cursor"></span></div>';
  thread.appendChild(aiBubble); thread.scrollTop=thread.scrollHeight;
  const textNode=aiBubble.querySelector('.bubble-text');
  try{
    const _bc=!_browserCtxSent?_collectBrowserCtx():null;
    _browserCtxSent=true;
    const bodyObj={prompt,attachment_ids:attachIds,priority};
    if(_bc)bodyObj.browser_ctx={tz:_bc.tz,lang:_bc.lang,now:_bc.now_local};
    const body=JSON.stringify(bodyObj);
    const resp=await fetch('/api/prompt',{method:'POST',headers:{'Content-Type':'application/json'},body});
    if(!resp.ok){textNode.textContent='Error: HTTP '+resp.status;return;}
    const reader=resp.body.getReader(); const decoder=new TextDecoder();
    let buf='',fullText='';
    while(true){
      const{value,done}=await reader.read(); if(done)break;
      buf+=decoder.decode(value,{stream:true});
      const lines=buf.split('\n'); buf=lines.pop();
      for(const line of lines){
        if(!line.startsWith('data: '))continue;
        const raw=line.slice(6).trim(); if(raw==='[DONE]')break;
        try{
          const obj=JSON.parse(raw);
          if(obj.delta){fullText+=obj.delta;textNode.textContent=fullText;thread.scrollTop=thread.scrollHeight;}
          else if(obj.error)textNode.textContent='Error: '+obj.error;
        }catch{}
      }
    }
    if(!fullText)textNode.textContent='(no response)';
  }catch(e){textNode.textContent='Error: '+e.message;}
  finally{
    _sending=false;
    document.getElementById('send-btn').disabled=false;
    if(pb)pb.disabled=false;
  }
}
async function clearChat(evt){
  evt.stopPropagation();
  await fetch('/api/chat',{method:'DELETE'}).catch(()=>{});
  const thread=document.getElementById('chat-thread');
  thread.innerHTML='<div class="chat-empty" id="chat-empty">Start a conversation below.</div>';
  _browserCtxSent=false;   // allow fresh context injection on next first message
  _renderChatCtx();
}
"""
