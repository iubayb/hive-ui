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

  /* header */
  #header{padding:10px 14px;background:var(--panel);border-bottom:1px solid var(--border);
          display:flex;align-items:center;justify-content:space-between;
          position:sticky;top:0;z-index:50}
  #header h1{font-size:15px;color:var(--info);letter-spacing:.5px;display:flex;align-items:center;gap:8px}
  #header-btns{display:flex;gap:6px}
  .hdr-btn{background:none;border:1px solid var(--border);color:var(--muted);
           padding:4px 10px;border-radius:4px;font-size:12px;cursor:pointer;
           min-height:44px;min-width:44px}
  .hdr-btn:active{background:var(--border)}

  /* status bar + live dot */
  .status-bar{padding:3px 14px;font-size:11px;color:var(--muted);background:var(--panel);
              border-bottom:1px solid var(--border)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--ok);
       display:inline-block;animation:pulse 2s infinite}
  .dot.dead{background:var(--err);animation:none}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

  /* layout */
  #main{padding-bottom:calc(70px + var(--safe-bottom))}

  /* group tabs */
  #group-tabs{display:flex;gap:0;overflow-x:auto;background:var(--panel);
              border-bottom:1px solid var(--border);padding:0 8px;scrollbar-width:none}
  #group-tabs::-webkit-scrollbar{display:none}
  .gtab{padding:8px 14px;cursor:pointer;font-size:12px;color:var(--muted);
        border-bottom:2px solid transparent;white-space:nowrap;min-height:44px;
        display:flex;align-items:center;-webkit-tap-highlight-color:transparent}
  .gtab.active{color:var(--info);border-bottom-color:var(--info)}
  .gtab:active{background:var(--border)}

  /* collapsible sections */
  .section{margin:8px;border:1px solid var(--border);border-radius:6px;overflow:hidden}
  .section summary{padding:9px 12px;background:var(--panel);font-weight:bold;cursor:pointer;
    display:flex;justify-content:space-between;align-items:center;
    user-select:none;list-style:none;-webkit-tap-highlight-color:transparent;min-height:44px}
  .section summary::-webkit-details-marker{display:none}
  .section summary:active{background:var(--border)}
  .count{font-size:11px;color:var(--muted);font-weight:normal}

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

  /* onboarding */
  #onboarding{margin:8px;padding:16px;background:var(--panel);
              border:1px solid var(--info);border-radius:8px}
  #onboarding h2{color:var(--info);font-size:14px;margin-bottom:12px}
  .ob-q{margin-bottom:14px}
  .ob-q label{display:block;color:var(--muted);font-size:11px;margin-bottom:4px;
              text-transform:uppercase;letter-spacing:.5px}
  .ob-q textarea,.ob-q input{width:100%;background:var(--input-bg);
    border:1px solid var(--border);color:var(--text);padding:8px 10px;
    border-radius:4px;font-family:inherit;font-size:13px;resize:vertical}
  .ob-q textarea:focus,.ob-q input:focus{outline:none;border-color:var(--info)}
  .ob-q .model-row{display:flex;gap:6px}
  .ob-q .model-row input{flex:1}
  .ob-q .favorites{margin-top:6px;display:flex;flex-wrap:wrap;gap:4px}
  .fav-chip{padding:3px 8px;border-radius:12px;font-size:11px;cursor:pointer;
            background:var(--bg);border:1px solid var(--border);color:var(--muted);
            -webkit-tap-highlight-color:transparent}
  .fav-chip.active{border-color:var(--info);color:var(--info)}
  #ob-submit{width:100%;padding:11px;background:var(--info);color:#000;
             border:none;border-radius:4px;font-weight:bold;font-size:14px;
             cursor:pointer;margin-top:6px;min-height:44px}
  #ob-submit:active{opacity:.8}

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

  /* ── active task bar — always-visible strip below the header ──────────── */
  #active-task-bar{
    display:flex;align-items:center;gap:8px;padding:6px 14px;
    font-size:11px;font-family:'Courier New',monospace;
    border-bottom:2px solid var(--border);
    position:sticky;top:0;z-index:45;
    transition:background .3s,border-color .3s,color .3s;
    min-height:36px;overflow:hidden;
  }
  #active-task-bar.at-working{
    background:rgba(176,176,176,.05);color:var(--ok);border-bottom-color:var(--ok)}
  #active-task-bar.at-idle{
    background:var(--panel);color:var(--muted);border-bottom-color:var(--border)}
  #active-task-bar.at-stale{
    background:rgba(156,156,156,.07);color:var(--warn);border-bottom-color:var(--warn);
    animation:at-blink 1.4s infinite}
  #active-task-bar.at-hang{
    background:rgba(240,240,240,.07);color:var(--err);border-bottom-color:var(--err);
    animation:at-blink .7s infinite}
  @keyframes at-blink{0%,100%{opacity:1}50%{opacity:.55}}
  .at-dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex-shrink:0}
  #active-task-bar.at-working .at-dot{animation:pulse 1s infinite}
  #active-task-bar.at-hang    .at-dot{animation:at-blink .5s infinite}
  #active-task-bar.at-stale   .at-dot{animation:at-blink 1s infinite}
  .at-label{font-weight:bold;font-size:10px;text-transform:uppercase;
            letter-spacing:.6px;white-space:nowrap;flex-shrink:0}
  .at-detail{font-size:11px;opacity:.8;white-space:nowrap;overflow:hidden;
             text-overflow:ellipsis;flex:1;min-width:0}
  .at-elapsed{font-size:10px;color:var(--muted);white-space:nowrap;flex-shrink:0}
  .at-src{font-size:9px;color:var(--muted);white-space:nowrap;flex-shrink:0;
          padding:1px 5px;border:1px solid var(--border);border-radius:8px;margin-left:2px}

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

  /* settings modal */
  #settings-modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);
    z-index:100;overflow-y:auto;padding:16px}
  #settings-modal.open{display:block}
  #settings-inner{background:var(--panel);border-radius:8px;padding:16px;max-width:600px;margin:0 auto}
  #settings-inner h2{color:var(--info);font-size:14px;margin-bottom:14px;
                     display:flex;justify-content:space-between;align-items:center}
  #close-settings{background:none;border:none;color:var(--muted);font-size:18px;cursor:pointer}
  .setting-row{margin-bottom:14px}
  .setting-row label{display:block;color:var(--muted);font-size:11px;
                     margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px}
  .setting-row input,.setting-row textarea{width:100%;background:var(--input-bg);
    border:1px solid var(--border);color:var(--text);padding:8px 10px;
    border-radius:4px;font-family:inherit;font-size:13px}
  .setting-row input:focus,.setting-row textarea:focus{outline:none;border-color:var(--info)}
  #save-settings{width:100%;padding:11px;background:var(--ok);color:#000;
    border:none;border-radius:4px;font-weight:bold;font-size:13px;
    cursor:pointer;min-height:44px;margin-top:6px}
  #save-settings:active{opacity:.8}

  /* arena panel inside settings */
  .arena-section{margin-top:18px;padding-top:14px;border-top:1px solid var(--border)}
  .arena-section h3{color:var(--purple);font-size:12px;margin-bottom:10px;
                    text-transform:uppercase;letter-spacing:.5px}
  .champ-row{display:flex;justify-content:space-between;align-items:center;
             padding:6px 0;border-bottom:1px solid var(--border);font-size:12px}
  .champ-row:last-of-type{border-bottom:none}
  .champ-label{color:var(--muted);font-size:11px}
  .champ-val{color:var(--info);font-size:11px;max-width:60%;text-align:right;word-break:break-all}
  #run-arena-btn{width:100%;padding:9px;background:var(--purple);color:#000;
                 border:none;border-radius:4px;font-weight:bold;font-size:12px;
                 cursor:pointer;min-height:44px;margin-top:10px}
  #run-arena-btn:active{opacity:.8}
  #run-arena-btn:disabled{background:var(--border);color:var(--muted);cursor:not-allowed}
  #arena-status-msg{font-size:11px;color:var(--muted);margin-top:6px;text-align:center}
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

function _renderActiveTask(s){
  const bar = document.getElementById('active-task-bar');
  if(!bar) return;

  // ── Layer 1: client-side hang detection (overrides everything) ──────────
  const hang = _hangDetector.detect();
  if(hang){
    bar.className='active-task-bar at-hang';
    bar.innerHTML=
      '<span class="at-dot"></span>'+
      '<span class="at-label">'+esc(hang.label)+'</span>'+
      '<span class="at-detail">'+esc(hang.detail)+'</span>'+
      '<span class="at-src">frontend-detect</span>';
    return;
  }

  // ── Layer 2: backend active_task signal ─────────────────────────────────
  // Use passed-in s, OR fall back to last known status from SSE cache
  const src = s || _lastKnownStatus;
  const at = src && src.active_task;

  // No data yet
  if(!at){
    bar.className='active-task-bar at-idle';
    bar.innerHTML='<span class="at-dot"></span><span class="at-label">IDLE</span>'+
      '<span class="at-detail"> waiting for first status event\u2026</span>';
    return;
  }

  // Task completed — show IDLE + last task + elapsed since completion
  if(at.status==='completed' || at.completed_at){
    const ago = at.completed_at
      ? _atElapsedStr(Date.now()-new Date(at.completed_at).getTime())
      : '?';
    bar.className='active-task-bar at-idle';
    bar.innerHTML=
      '<span class="at-dot"></span>'+
      '<span class="at-label">IDLE</span>'+
      '<span class="at-detail"> last: '+esc(at.task||'—')+' \xb7 '+ago+' ago</span>';
    return;
  }

  // Task is running — check staleness (backend claims running for >3 min = suspect)
  const startedMs = at.started_at ? new Date(at.started_at).getTime() : 0;
  const ageMs = Date.now() - startedMs;
  if(ageMs > 180000){
    bar.className='active-task-bar at-stale';
    bar.innerHTML=
      '<span class="at-dot"></span>'+
      '<span class="at-label">STALE ('+Math.round(ageMs/1000)+'s)</span>'+
      '<span class="at-detail">'+esc(at.task)+'</span>'+
      '<span class="at-src">backend-stale</span>';
    return;
  }

  // Fresh and running — show with live elapsed counter
  bar.className='active-task-bar at-working';
  bar.innerHTML=
    '<span class="at-dot"></span>'+
    '<span class="at-label">WORKING</span>'+
    '<span class="at-detail">'+esc((at.agent||'orchestrator')+' \xb7 '+at.task)+'</span>'+
    '<span class="at-elapsed" id="at-elapsed">0s</span>';
  _atStartTimer(startedMs);
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

// ── config ────────────────────────────────────────────────────────────────────
const CONFIG_KEY = 'hive_config_v2';
const CHAT_PERSIST_KEY = 'hive_chat_v1';
const DEFAULT_FAVORITES = [
  'inclusionai/ling-2.6-1t:free',
  'openai/gpt-oss-120b:free',
  'nvidia/nemotron-3-super-120b-a12b:free',
  'google/gemma-4-31b-it:free',
  'nousresearch/hermes-3-llama-3.1-405b:free',
  'qwen/qwen3-coder:free',
  'meta-llama/llama-3.3-70b-instruct:free',
];
function loadConfig(){try{return JSON.parse(localStorage.getItem(CONFIG_KEY))||{};}catch{return {};}}
function saveConfig(c){localStorage.setItem(CONFIG_KEY,JSON.stringify(c));}
let cfg = loadConfig();

window.addEventListener('DOMContentLoaded', () => {
  // Always skip onboarding — use stored config or sensible defaults
  const ob = document.getElementById('onboarding');
  if (ob) ob.style.display = 'none';
  // Ensure queue + chat are open
  const qs = document.getElementById('queue-section');
  const cs = document.getElementById('chat-section');
  if (qs) qs.open = true;
  if (cs) cs.open = true;
  // Restore persisted model default
  if (!cfg.model) cfg.model = DEFAULT_FAVORITES[0];
  renderFavorites('ob-favorites', cfg.model);
  renderFavorites('s-favorites',  cfg.model);
  populateSettings();
  fetchQueue();
  restoreChat();
  // Sessions are shown in the combined log with badges — no individual panels needed
  fetch('/api/groups').then(r=>r.json()).then(g=>renderGroupTabs(g)).catch(()=>{});
  startStatusStream();
  fetchArenaStatus();
  // Auto-focus input after a short delay
  setTimeout(()=>{const p=document.getElementById('prompt-input');if(p)p.focus();},300);
});

function renderFavorites(cid, sel){
  const favs=cfg.favorites||DEFAULT_FAVORITES;
  const c=document.getElementById(cid); if(!c)return; c.innerHTML='';
  favs.forEach(f=>{
    const ch=document.createElement('span');
    ch.className='fav-chip'+(f===sel?' active':'');
    ch.textContent=f.split('/').pop(); ch.title=f;
    ch.onclick=()=>{
      const iid=cid==='ob-favorites'?'ob-model':'s-model';
      document.getElementById(iid).value=f;
      c.querySelectorAll('.fav-chip').forEach(x=>x.classList.remove('active'));
      ch.classList.add('active');
    };
    c.appendChild(ch);
  });
}

function submitOnboarding(){
  const goal=document.getElementById('ob-goal').value.trim();
  if(!goal){document.getElementById('ob-goal').focus();return;}
  let groups={};
  try{groups=JSON.parse(document.getElementById('ob-groups').value||'{}');}catch{}
  cfg={
    goal, groups,
    task_dest:    document.getElementById('ob-dest').value.trim(),
    model:        document.getElementById('ob-model').value.trim()||DEFAULT_FAVORITES[0],
    instructions: document.getElementById('ob-instructions').value.trim(),
    favorites:    cfg.favorites||DEFAULT_FAVORITES,
  };
  saveConfig(cfg);
  if(Object.keys(groups).length){
    fetch('/api/groups',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({groups})}).catch(()=>{});
    renderGroupTabs(groups);
  }
  document.getElementById('onboarding').style.display='none';
  document.getElementById('queue-section').open=true;
  document.getElementById('chat-section').open=true;
}

function populateSettings(){
  document.getElementById('s-goal').value=cfg.goal||'';
  document.getElementById('s-dest').value=cfg.task_dest||'';
  document.getElementById('s-model').value=cfg.model||DEFAULT_FAVORITES[0];
  document.getElementById('s-instructions').value=cfg.instructions||'';
  document.getElementById('s-groups').value=cfg.groups?JSON.stringify(cfg.groups,null,2):'';
  renderFavorites('s-favorites',cfg.model||DEFAULT_FAVORITES[0]);
  const enabled=cfg.ai_auto_answer||false;
  const timeout=cfg.ai_auto_answer_timeout_min||30;
  document.getElementById('s-ai-auto').checked=enabled;
  document.getElementById('s-ai-timeout').value=timeout;
  document.getElementById('s-ai-timeout').disabled=!enabled;
  document.getElementById('s-ai-status').textContent=
    enabled?'AI will answer unanswered questions after '+timeout+' min of UI inactivity.'
           :'AI auto-answer is off — questions wait for human response.';
}
function openSettings(){document.getElementById('settings-modal').classList.add('open');populateSettings();}
function closeSettings(){document.getElementById('settings-modal').classList.remove('open');}
function saveSettings(){
  cfg.goal=document.getElementById('s-goal').value.trim();
  cfg.task_dest=document.getElementById('s-dest').value.trim();
  cfg.model=document.getElementById('s-model').value.trim()||DEFAULT_FAVORITES[0];
  cfg.instructions=document.getElementById('s-instructions').value.trim();
  try{cfg.groups=JSON.parse(document.getElementById('s-groups').value||'{}');}catch{cfg.groups={};}
  cfg.ai_auto_answer=document.getElementById('s-ai-auto').checked;
  cfg.ai_auto_answer_timeout_min=parseInt(document.getElementById('s-ai-timeout').value)||30;
  saveConfig(cfg);
  fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      ai_auto_answer:cfg.ai_auto_answer,
      ai_auto_answer_timeout_min:cfg.ai_auto_answer_timeout_min,
    })}).catch(()=>{});
  if(Object.keys(cfg.groups||{}).length){
    fetch('/api/groups',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({groups:cfg.groups})}).catch(()=>{});
    renderGroupTabs(cfg.groups);
  }
  closeSettings();
}
document.addEventListener('DOMContentLoaded',()=>{
  const tog=document.getElementById('s-ai-auto');
  if(tog)tog.addEventListener('change',()=>{
    document.getElementById('s-ai-timeout').disabled=!tog.checked;
  });
});

// ── group tabs ────────────────────────────────────────────────────────────────
let _activeGroup='__all__';
function renderGroupTabs(groups){
  const bar=document.getElementById('group-tabs');
  bar.querySelectorAll('.gtab:not([data-group="__all__"])').forEach(e=>e.remove());
  Object.keys(groups||{}).forEach(name=>{
    const t=document.createElement('div');
    t.className='gtab'; t.dataset.group=name; t.textContent=name;
    t.onclick=()=>switchGroup(name,t);
    bar.appendChild(t);
  });
}
function switchGroup(name, el){
  _activeGroup=name;
  document.querySelectorAll('.gtab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
}

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

let lastEventTime=Date.now();
const dot=document.getElementById('dot');
const statusBar=document.getElementById('status-bar');
function updateStatus(){
  const ago=Math.round((Date.now()-lastEventTime)/1000);
  statusBar.textContent=ago<5?'Live \u2014 updating every 2s':'Last update '+ago+'s ago';
  dot.classList.toggle('dead',ago>10);
}
setInterval(updateStatus,1000);

const logEs=new EventSource('/stream');
logEs.onmessage=function(e){
  lastEventTime=Date.now();
  const data=JSON.parse(e.data);
  const cb=document.getElementById('combined');
  (data.combined||[]).forEach(entry=>addLogLine(cb,entry.session,entry.line,entry.ts));
  if(cb)document.getElementById('combined-count').textContent=cb.children.length+' lines';
};
logEs.onerror=function(){dot.classList.add('dead');statusBar.textContent='SSE disconnected \u2014 retrying...';};
logEs.onopen=function(){dot.classList.remove('dead');statusBar.textContent='';};

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
  es.onmessage=e=>{try{renderStatus(JSON.parse(e.data));}catch{}};
  es.onerror=()=>{
    statusDot.className='status-dot dead';
    es.close();
    _statusStreamActive=false;
    setTimeout(startStatusStream,5000);
  };
}

// ── arena ─────────────────────────────────────────────────────────────────────
function fetchArenaStatus(){
  fetch('/api/arena/status').then(r=>r.json()).then(s=>{
    const tc=document.getElementById('arena-text-champ');
    const vc=document.getElementById('arena-vision-champ');
    const lr=document.getElementById('arena-last-run');
    if(tc)tc.textContent=s.text_champion||'—';
    if(vc)vc.textContent=s.vision_champion||'—';
    const t=(s.last_run||{}).text||(s.last_run||{}).vision||{};
    if(lr)lr.textContent=t.run_at?t.run_at.slice(0,16):'—';
  }).catch(()=>{});
}
let _arenaRunning=false;
function runArena(){
  if(_arenaRunning)return;
  _arenaRunning=true;
  const btn=document.getElementById('run-arena-btn');
  const msg=document.getElementById('arena-status-msg');
  btn.disabled=true; btn.textContent='Running\u2026';
  msg.textContent='Fetching free models and running benchmark...';
  fetch('/api/arena/run',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({arena_type:'text'})})
  .then(r=>r.json())
  .then(d=>{
    msg.textContent=d.message||'Arena started';
    setTimeout(()=>{
      _arenaRunning=false; btn.disabled=false; btn.textContent='Run Arena Benchmark';
      fetchArenaStatus(); fetchArenaResults();
    },5000);
  })
  .catch(()=>{
    _arenaRunning=false; btn.disabled=false; btn.textContent='Run Arena Benchmark';
    msg.textContent='Error starting arena';
  });
}
function fetchArenaResults(){
  fetch('/api/arena/results').then(r=>r.json()).then(results=>{
    const board=document.getElementById('arena-leaderboard'); if(!board)return;
    const textRes=(results.text||{}).results||[];
    if(!textRes.length){board.innerHTML='';return;}
    let html='<div style="font-size:11px;color:var(--muted);margin-bottom:6px">Text Arena Leaderboard</div>';
    textRes.forEach((r,i)=>{
      const pct=r.max?Math.round(r.total/r.max*100):0;
      html+='<div style="display:flex;justify-content:space-between;font-size:11px;padding:3px 0;border-bottom:1px solid var(--border)">'+
        '<span>'+(i+1)+'. '+esc(r.model.split('/').pop())+'</span>'+
        '<span style="color:'+(pct>=70?'var(--ok)':pct>=40?'var(--warn)':'var(--err)')+'">'+r.total+'/'+r.max+'</span>'+
        '</div>';
    });
    board.innerHTML=html;
  }).catch(()=>{});
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
const _CHAT_MAX_PERSIST = 30; // max messages kept in localStorage
function autoGrow(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,110)+'px';}
function handleKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendPrompt();}}
function _saveChatHistory(){
  try{
    const thread=document.getElementById('chat-thread');
    const bubbles=[...thread.querySelectorAll('.bubble')];
    const msgs=bubbles.map(b=>({
      role:b.classList.contains('user')?'user':'ai',
      text:b.querySelector('.bubble-text')?.textContent||''
    })).filter(m=>m.text);
    const trimmed=msgs.slice(-_CHAT_MAX_PERSIST);
    localStorage.setItem(CHAT_PERSIST_KEY,JSON.stringify(trimmed));
  }catch{}
}
function restoreChat(){
  try{
    const saved=JSON.parse(localStorage.getItem(CHAT_PERSIST_KEY)||'[]');
    if(!saved.length)return;
    const thread=document.getElementById('chat-thread');
    document.getElementById('chat-empty').style.display='none';
    saved.forEach(m=>{
      const d=document.createElement('div'); d.className='bubble '+m.role;
      d.innerHTML='<div class="role-label">'+(m.role==='user'?'You':'Hive')+'</div><div class="bubble-text">'+esc(m.text)+'</div>';
      thread.appendChild(d);
    });
    thread.scrollTop=thread.scrollHeight;
  }catch{}
}
function addBubble(role,text){
  const thread=document.getElementById('chat-thread');
  document.getElementById('chat-empty').style.display='none';
  const d=document.createElement('div'); d.className='bubble '+role;
  d.innerHTML='<div class="role-label">'+(role==='user'?'You':'Hive')+'</div><div class="bubble-text">'+esc(text)+'</div>';
  thread.appendChild(d); thread.scrollTop=thread.scrollHeight;
  return d.querySelector('.bubble-text');
}
let _sending=false;
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
    const body=JSON.stringify({prompt,attachment_ids:attachIds,priority:priority,
      model:cfg.model||DEFAULT_FAVORITES[0],task_dest:cfg.task_dest||'',instructions:cfg.instructions||''});
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
          else if(obj.queue_item)addQueueItem(obj.queue_item);
          else if(obj.error)textNode.textContent='Error: '+obj.error;
        }catch{}
      }
    }
    if(!fullText)textNode.textContent='(no response)';
    _saveChatHistory();
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
  localStorage.removeItem(CHAT_PERSIST_KEY);
  const thread=document.getElementById('chat-thread');
  thread.innerHTML='<div class="chat-empty" id="chat-empty">Start a conversation below.</div>';
}

// ── task queue ────────────────────────────────────────────────────────────────
const STATUS_ICON={queued:'\uD83D\uDFE1',pr_open:'\uD83D\uDD35',merged:'\u2705',closed:'\u2B1C',local:'\uD83D\uDCDD'};
function addQueueItem(item){
  const list=document.getElementById('queue-list');
  document.getElementById('queue-empty').style.display='none';
  const existing=document.getElementById('qi-'+item.id); if(existing)existing.remove();
  const d=document.createElement('div'); d.className='q-item'; d.id='qi-'+item.id;
  const icon=STATUS_ICON[item.status]||'\u2753';
  const prLink=item.pr_url?'<a href="'+esc(item.pr_url)+'" target="_blank">PR#'+item.pr_number+' \u2197</a>':'';
  d.innerHTML=
    '<div class="q-status">'+icon+'</div>'+
    '<div class="q-body">'+
      '<div class="q-summary">'+esc(item.summary)+'</div>'+
      '<div class="q-meta">'+
        '<span>'+(item.created_at?item.created_at.slice(11,16):'')+'</span>'+
        '<span>'+esc(item.model||'')+'</span>'+
        '<span class="q-item-status" data-id="'+item.id+'">'+item.status+'</span>'+
        prLink+
      '</div>'+
    '</div>';
  list.insertBefore(d,list.firstChild);
  updateQueueCount();
}
function updateQueueCount(){
  const n=document.querySelectorAll('.q-item').length;
  document.getElementById('queue-count').textContent=n+' task'+(n===1?'':'s');
}
async function fetchQueue(){
  try{
    const r=await fetch('/api/queue');
    const items=await r.json();
    items.forEach(addQueueItem);
    if(!items.length){
      const e=document.getElementById('queue-empty');
      if(e)e.style.display='block';
    }
  }catch{}
}
setInterval(async()=>{
  try{
    await fetch('/api/queue/poll',{method:'POST'});
    const r=await fetch('/api/queue');const items=await r.json();
    items.forEach(item=>{
      const el=document.getElementById('qi-'+item.id); if(!el)return;
      el.querySelector('.q-status').textContent=STATUS_ICON[item.status]||'\u2753';
      const sp=el.querySelector('.q-item-status'); if(sp)sp.textContent=item.status;
    });
    updateQueueCount();
    // show/hide empty state based on rendered items
    const qEmpty=document.getElementById('queue-empty');
    if(qEmpty)qEmpty.style.display=document.querySelectorAll('.q-item').length?'none':'block';
  }catch{}
},90000);
"""
