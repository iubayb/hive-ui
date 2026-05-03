#!/usr/bin/env node
/**
 * Hive UI — full Playwright test suite (40 tests, T1–T40)
 * Targeting http://127.0.0.1:8889 (dev server, never 8888)
 *
 * Run: PORT=8889 node tests/test_all.js
 */
const { chromium } = require('playwright');
const http  = require('http');
const https = require('https');
const fs    = require('fs');
const path  = require('path');
const { execSync } = require('child_process');

const BASE     = 'http://127.0.0.1:8889';
let   SESSIONS = [];  // populated dynamically from /api/sessions before T1

// ── helpers ──────────────────────────────────────────────────────────────────

function httpGet(path) {
  return new Promise((res, rej) => {
    http.get(BASE + path, r => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => res({ status: r.statusCode, body: d }));
      r.on('error', rej);
    }).on('error', rej);
  });
}

function httpPost(urlPath, body, contentType = 'application/json') {
  return new Promise((res, rej) => {
    const buf = typeof body === 'string' ? Buffer.from(body) : body;
    const opts = {
      hostname: '127.0.0.1', port: 8889,
      path: urlPath, method: 'POST',
      headers: {
        'Content-Type':   contentType,
        'Content-Length': buf.length,
      },
    };
    const req = http.request(opts, r => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => res({ status: r.statusCode, body: d }));
      r.on('error', rej);
    });
    req.on('error', rej);
    req.write(buf);
    req.end();
  });
}

function httpDelete(urlPath) {
  return new Promise((res, rej) => {
    const opts = { hostname:'127.0.0.1', port:8889, path:urlPath, method:'DELETE' };
    const req = http.request(opts, r => {
      let d = ''; r.on('data', c => d+=c);
      r.on('end', () => res({status:r.statusCode, body:d}));
      r.on('error', rej);
    });
    req.on('error', rej);
    req.end();
  });
}

/** POST multipart/form-data with a single file field */
function uploadFile(filename, mimeType, data) {
  const boundary = '----HiveTestBoundary' + Date.now();
  const CRLF = '\r\n';
  const header =
    `--${boundary}${CRLF}` +
    `Content-Disposition: form-data; name="file"; filename="${filename}"${CRLF}` +
    `Content-Type: ${mimeType}${CRLF}${CRLF}`;
  const footer = `${CRLF}--${boundary}--${CRLF}`;
  const body = Buffer.concat([
    Buffer.from(header),
    Buffer.isBuffer(data) ? data : Buffer.from(data),
    Buffer.from(footer),
  ]);
  return httpPost('/api/upload', body, `multipart/form-data; boundary=${boundary}`);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── test runner ───────────────────────────────────────────────────────────────

(async () => {
  const browser = await chromium.launch({ headless: true });
  let passed = 0, failed = 0;
  const results = [];

  function assert(name, cond, detail) {
    const msg = detail ? `${name} — ${detail}` : name;
    if (cond) { passed++; results.push(`  ✓ ${msg}`); }
    else       { failed++; results.push(`  ✗ ${msg}`); }
  }

  // ── discover sessions dynamically (used by T3, T6, T7, T15, T16, T17) ──────
  try {
    const sr = await httpGet('/api/sessions');
    SESSIONS = JSON.parse(sr.body);
    if (!Array.isArray(SESSIONS) || SESSIONS.length === 0) {
      console.error('FATAL: /api/sessions returned empty list');
      process.exit(1);
    }
    console.log(`  [info] discovered ${SESSIONS.length} session(s): ${SESSIONS.join(', ')}`);
  } catch(e) {
    console.error('FATAL: could not fetch /api/sessions:', e.message);
    process.exit(1);
  }

  // ══════════════════════════════════════════════════════════════
  // T1–T17: original log-monitor tests (port 8889, same assertions)
  // ══════════════════════════════════════════════════════════════

  // T1
  try {
    const r = await httpGet('/');
    assert('T1: GET / returns HTTP 200', r.status === 200, `got ${r.status}`);
  } catch(e) { assert('T1: GET / returns HTTP 200', false, e.message); }

  // T2 / T2b
  let snapData = null;
  try {
    const r = await httpGet('/api/snapshot');
    assert('T2: GET /api/snapshot returns 200', r.status === 200, `got ${r.status}`);
    snapData = JSON.parse(r.body);
    assert('T2b: Snapshot is valid JSON with sessions + combined keys',
      'sessions' in snapData && 'combined' in snapData);
  } catch(e) { assert('T2: Snapshot endpoint', false, e.message); }

  // T3
  if (snapData) {
    const hasAll = SESSIONS.every(s => s in snapData.sessions);
    assert(`T3: All ${SESSIONS.length} discovered sessions in snapshot`, hasAll,
      hasAll ? '' : 'missing: ' + SESSIONS.filter(s => !(s in snapData.sessions)).join(', '));
  } else {
    assert('T3: All discovered sessions in snapshot', false, 'no snapshot data');
  }

  // Desktop page
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 800 });
  try {
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
  } catch(e) { console.error('FATAL: Could not load page:', e.message); process.exit(1); }

  // T4
  const h1text = await page.$eval('h1', el => el.textContent).catch(() => '');
  assert('T4: Dashboard header contains "Hive Monitor"', h1text.includes('Hive Monitor'), `got: "${h1text.trim()}"`);

  // T5
  const combinedBox = await page.$('#combined');
  assert('T5: Combined feed #combined exists', !!combinedBox);

  // T6 — dynamic panels (wait up to 10s)
  let boxes, missingBoxes;
  for (let i = 0; i < 20; i++) {
    boxes = await Promise.all(SESSIONS.map(s => page.$(`#box-${s}`)));
    missingBoxes = SESSIONS.filter((_, i) => !boxes[i]);
    if (missingBoxes.length === 0) break;
    await sleep(500);
  }
  assert(`T6: All ${SESSIONS.length} per-session boxes exist`, missingBoxes.length === 0,
    missingBoxes.length ? 'missing: ' + missingBoxes.join(', ') : '');

  // T7
  const bodyText = await page.textContent('body').catch(() => '');
  const missingNames = SESSIONS.filter(s => !bodyText.includes(s));
  assert('T7: All session names visible in DOM', missingNames.length === 0,
    missingNames.length ? 'missing: ' + missingNames.join(', ') : '');

  // T8
  const gotSSE = await page.evaluate(async () => {
    return await new Promise(resolve => {
      const es = new EventSource('/stream');
      const t = setTimeout(() => { es.close(); resolve(false); }, 8000);
      es.onmessage = () => { clearTimeout(t); es.close(); resolve(true); };
      es.onerror   = () => { clearTimeout(t); es.close(); resolve(false); };
    });
  });
  assert('T8: SSE /stream delivers message within 8s', gotSSE);

  // T9
  let lineCount = 0;
  for (let i = 0; i < 10; i++) {
    lineCount = await page.$eval('#combined', el => el.children.length).catch(() => 0);
    if (lineCount > 0) break;
    await sleep(1000);
  }
  assert('T9: Combined feed has log lines after SSE', lineCount > 0, `got ${lineCount} lines`);

  // T10 — mobile overflow
  try {
    const mob = await browser.newPage();
    await mob.setViewportSize({ width: 390, height: 844 });
    await mob.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 12000 });
    await sleep(1000);
    const { scrollWidth, viewWidth } = await mob.evaluate(() => ({
      scrollWidth: document.body.scrollWidth, viewWidth: window.innerWidth,
    }));
    assert('T10: Mobile 390px — no horizontal overflow',
      scrollWidth <= viewWidth + 5, `scrollWidth=${scrollWidth} viewWidth=${viewWidth}`);
    await mob.close();
  } catch(e) {
    assert('T10: Mobile 390px — no horizontal overflow', false, e.message.split('\n')[0]);
  }

  // T11
  const eventCount = await page.evaluate(async () => {
    return await new Promise(resolve => {
      let count = 0;
      const es = new EventSource('/stream');
      const t = setTimeout(() => { es.close(); resolve(count); }, 12000);
      es.onmessage = () => { count++; if (count >= 4) { clearTimeout(t); es.close(); resolve(count); } };
      es.onerror   = () => { clearTimeout(t); es.close(); resolve(count); };
    });
  });
  assert('T11: SSE delivers >= 4 events within 12s', eventCount >= 4, `got ${eventCount} events`);

  // T12
  const statusText = await page.$eval('#status-bar', el => el.textContent).catch(() => '');
  assert('T12: Status bar shows "Live" after SSE event', statusText.includes('Live'), `got: "${statusText}"`);

  // T13
  const dotIsDead = await page.$eval('#dot', el => el.classList.contains('dead')).catch(() => true);
  assert('T13: Live indicator dot is green (not dead)', !dotIsDead);

  // T14 — no re-dump
  const countBefore = await page.$eval('#combined', el => el.children.length).catch(() => 0);
  await sleep(6000);
  const countAfter  = await page.$eval('#combined', el => el.children.length).catch(() => 0);
  const delta = countAfter - countBefore;
  assert('T14: No re-dump between ticks (delta <= 20 lines / 6s)',
    delta >= 0 && delta <= 20, `combined count: ${countBefore} → ${countAfter} (delta ${delta})`);

  // T15
  const boxCounts = await Promise.all(
    SESSIONS.map(s => page.$eval(`#box-${s}`, el => el.children.length).catch(() => 0)));
  const overflowed = SESSIONS.filter((s, i) => boxCounts[i] > 100);
  assert('T15: Per-session boxes respect 100-line rolling limit', overflowed.length === 0,
    overflowed.length ? 'overflowed: '+overflowed.join(', ') : `counts: ${boxCounts.join(', ')}`);

  // T16 / T17 — supervisor tests (generic: uses first two discovered sessions)
  const sess0 = SESSIONS[0] || '';
  const sess1 = SESSIONS.length >= 2 ? SESSIONS[1] : '';

  let sess0PanePid = '', sess1PanePid = '';
  let sess0ChildBefore = '', sess1ChildBefore = '';
  try {
    if (sess0) sess0PanePid      = execSync(`tmux display -t ${sess0} -p '#{pane_pid}' 2>/dev/null || true`).toString().trim();
    if (sess1) sess1PanePid      = execSync(`tmux display -t ${sess1} -p '#{pane_pid}' 2>/dev/null || true`).toString().trim();
    if (sess0PanePid) sess0ChildBefore = execSync(`pgrep -P ${sess0PanePid} 2>/dev/null | head -1 || true`).toString().trim();
    if (sess1PanePid) sess1ChildBefore = execSync(`pgrep -P ${sess1PanePid} 2>/dev/null | head -1 || true`).toString().trim();
  } catch(e) {}

  let killedPid = '';
  if (sess0PanePid && sess0ChildBefore) {
    try {
      killedPid = sess0ChildBefore;
      execSync(`kill ${killedPid} 2>/dev/null || true`);
    } catch(e) {}
  }

  await sleep(1000);
  let killVerified = false;
  if (killedPid) {
    try {
      const still = execSync(`ps -p ${killedPid} -o pid= 2>/dev/null || true`).toString().trim();
      killVerified = still === '';
    } catch(e) { killVerified = true; }
  }

  await sleep(39000);

  let sess0ChildAfter = '';
  let sess0ChildCount = '0';
  try {
    if (sess0PanePid) sess0ChildAfter = execSync(`pgrep -P ${sess0PanePid} 2>/dev/null | head -1 || true`).toString().trim();
    if (sess0PanePid) sess0ChildCount = execSync(`pgrep -c -P ${sess0PanePid} 2>/dev/null || echo 0`).toString().trim();
  } catch(e) {}

  if (sess0 && sess0PanePid) {
    assert('T16a: First session child killed and restarted with new PID',
      killVerified && sess0ChildAfter !== '' && sess0ChildAfter !== killedPid,
      `killVerified=${killVerified} pidBefore=${killedPid} pidAfter=${sess0ChildAfter} session=${sess0}`);
    assert('T16b: First session has live child process after restart',
      parseInt(sess0ChildCount) > 0, `children=${sess0ChildCount} session=${sess0}`);
  } else {
    assert('T16a: First session child killed and restarted (SKIP — no session)', true, 'skipped');
    assert('T16b: First session has live child after restart (SKIP — no session)', true, 'skipped');
  }

  let t16cSnap = null;
  try { t16cSnap = JSON.parse((await httpGet('/api/snapshot')).body); } catch(e) {}
  const t16cLines = t16cSnap && sess0 ? (t16cSnap.sessions[sess0] || []) : [];
  assert('T16c: Dashboard has lines for first session after restart',
    !sess0 || t16cLines.length > 0, `session=${sess0} buffer=${t16cLines.length} lines`);

  if (sess1 && sess1PanePid && sess1ChildBefore) {
    let sess1ChildAfter = '';
    try { sess1ChildAfter = execSync(`pgrep -P ${sess1PanePid} 2>/dev/null | head -1 || true`).toString().trim(); } catch(e) {}
    assert('T17: Supervisor does not restart healthy second session',
      sess1ChildBefore === sess1ChildAfter,
      `child PID before=${sess1ChildBefore} after=${sess1ChildAfter} session=${sess1}`);
  } else {
    assert('T17: Supervisor does not restart healthy session (SKIP — <2 sessions)', true, 'skipped');
  }

  // ══════════════════════════════════════════════════════════════
  // T18–T20: NEW — /api/sessions, /api/config, /api/queue basics
  // ══════════════════════════════════════════════════════════════

  // T18: /api/sessions returns array
  try {
    const r = await httpGet('/api/sessions');
    const list = JSON.parse(r.body);
    assert('T18: /api/sessions returns non-empty array', Array.isArray(list) && list.length > 0,
      `got ${JSON.stringify(list)}`);
  } catch(e) { assert('T18: /api/sessions returns non-empty array', false, e.message); }

  // T19: /api/config returns expected fields
  try {
    const r = await httpGet('/api/config');
    const cfg = JSON.parse(r.body);
    assert('T19: /api/config has model + favorites fields',
      'model' in cfg && Array.isArray(cfg.favorites),
      `got keys: ${Object.keys(cfg).join(', ')}`);
  } catch(e) { assert('T19: /api/config has model + favorites fields', false, e.message); }

  // T20: /api/queue returns array
  try {
    const r = await httpGet('/api/queue');
    const q = JSON.parse(r.body);
    assert('T20: /api/queue returns array', Array.isArray(q), `got ${typeof q}`);
  } catch(e) { assert('T20: /api/queue returns array', false, e.message); }

  // ══════════════════════════════════════════════════════════════
  // T21–T30: Chat UI in browser
  // ══════════════════════════════════════════════════════════════

  // Re-use the existing page; clear localStorage so onboarding shows
  await page.evaluate(() => localStorage.removeItem('hive_config_v2'));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await sleep(500);

  // T21: Onboarding card visible (no config in localStorage)
  const obVisible = await page.$eval('#onboarding', el =>
    getComputedStyle(el).display !== 'none').catch(() => false);
  assert('T21: Onboarding card visible on first load (localStorage cleared)', obVisible);

  // T22: Input field + send button present
  const inputEl  = await page.$('#prompt-input');
  const sendBtn  = await page.$('#send-btn');
  assert('T22: Prompt input and send button exist', !!inputEl && !!sendBtn);

  // T23: Attach button and hidden file input present
  const attachBtn  = await page.$('#attach-btn');
  const fileInput  = await page.$('#file-input');
  assert('T23: Attach button and file input exist', !!attachBtn && !!fileInput);

  // T24: Input has min tap height >= 44px
  const inputHeight = await page.$eval('#prompt-input', el => el.getBoundingClientRect().height).catch(() => 0);
  assert('T24: Prompt input height >= 44px (mobile tap target)', inputHeight >= 44, `height=${inputHeight}px`);

  // Complete onboarding so the rest of the chat tests work
  await page.fill('#ob-goal', 'Test session for automated Playwright tests');
  await page.fill('#ob-model', 'deepseek/deepseek-r1:free');
  await page.click('#ob-submit');
  await sleep(300);

  // T25: Onboarding hidden after submit
  const obHidden = await page.$eval('#onboarding', el =>
    getComputedStyle(el).display === 'none').catch(() => false);
  assert('T25: Onboarding card hidden after completing setup', obHidden);

  // T26: Chat section visible
  const chatSection = await page.$('#chat-section');
  assert('T26: Chat section exists in DOM', !!chatSection);

  // T27: Queue section visible
  const queueSection = await page.$('#queue-section');
  assert('T27: Task queue section exists in DOM', !!queueSection);

  // T28: Settings modal opens/closes
  await page.click('#menu-btn');
  await sleep(200);
  const modalOpen = await page.$eval('#settings-modal', el =>
    el.classList.contains('open')).catch(() => false);
  assert('T28: Settings modal opens on ⚙ Config click', modalOpen);
  await page.click('#close-settings');
  await sleep(200);
  const modalClosed = await page.$eval('#settings-modal', el =>
    !el.classList.contains('open')).catch(() => false);
  assert('T28b: Settings modal closes on ✕ click', modalClosed);

  // T29: localStorage persists config across reload
  const savedGoal = await page.evaluate(() => {
    try { return JSON.parse(localStorage.getItem('hive_config_v2')||'{}').goal || ''; } catch { return ''; }
  });
  assert('T29: Config persists in localStorage after onboarding', savedGoal.includes('Test session'));

  // ══════════════════════════════════════════════════════════════
  // T30–T33: File upload API (node-level, not browser)
  // ══════════════════════════════════════════════════════════════

  // T30: Upload a PNG → 200 + is_image=true
  // 1x1 red PNG (minimal valid PNG bytes)
  const PNG1x1 = Buffer.from(
    '89504e470d0a1a0a0000000d4948445200000001000000010802000000' +
    '9001 2e000000 0c49444154789c6260f8cfc00000000200 01e221bc33' +
    '0000000049454e44ae426082', 'hex');
  // Use a known-good minimal PNG
  const minPng = Buffer.from([
    0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a, // signature
    0x00,0x00,0x00,0x0d,0x49,0x48,0x44,0x52, // IHDR chunk length + type
    0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01, // 1x1
    0x08,0x02,0x00,0x00,0x00,0x90,0x77,0x53, // bit depth + color type + crc (approx)
    0xde,0x00,0x00,0x00,0x0c,0x49,0x44,0x41, // IDAT
    0x54,0x08,0xd7,0x63,0xf8,0xcf,0xc0,0x00,
    0x00,0x00,0x02,0x00,0x01,0xe2,0x21,0xbc,
    0x33,0x00,0x00,0x00,0x00,0x49,0x45,0x4e, // IEND
    0x44,0xae,0x42,0x60,0x82,
  ]);
  try {
    const r = await uploadFile('test.png', 'image/png', minPng);
    const info = JSON.parse(r.body);
    assert('T30: POST /api/upload PNG → 200 + is_image=true',
      r.status === 200 && info.is_image === true && !!info.id,
      `status=${r.status} is_image=${info.is_image} id=${info.id}`);
  } catch(e) { assert('T30: POST /api/upload PNG', false, e.message); }

  // T31: Upload a text file → type=text
  try {
    const r = await uploadFile('hello.py', 'text/plain', Buffer.from('print("hello")'));
    const info = JSON.parse(r.body);
    assert('T31: POST /api/upload .py → type=text',
      r.status === 200 && info.type === 'text', `type=${info.type}`);
  } catch(e) { assert('T31: POST /api/upload .py text', false, e.message); }

  // T32: Upload a binary file → type=binary
  try {
    const r = await uploadFile('data.bin', 'application/octet-stream', Buffer.from([0x00,0xff,0x42]));
    const info = JSON.parse(r.body);
    assert('T32: POST /api/upload binary → type=binary',
      r.status === 200 && info.type === 'binary', `type=${info.type}`);
  } catch(e) { assert('T32: POST /api/upload binary', false, e.message); }

  // T33: Upload > 10 MB → 413
  try {
    const big = Buffer.alloc(11 * 1024 * 1024, 0x41);
    const r = await uploadFile('big.bin', 'application/octet-stream', big);
    assert('T33: Upload > 10 MB rejected with 413', r.status === 413, `status=${r.status}`);
  } catch(e) { assert('T33: Upload > 10 MB → 413', false, e.message); }

  // ══════════════════════════════════════════════════════════════
  // T34–T37: /api/prompt — SSE streaming chat
  // ══════════════════════════════════════════════════════════════

  // T34: POST /api/prompt returns SSE stream with content within 30s
  let promptGotStream = false;
  let promptGotQueueItem = false;
  let promptItemId = null;
  await new Promise(resolve => {
    const body = JSON.stringify({
      prompt: 'Reply with exactly three words: hello hive world',
      attachment_ids: [],
      model: 'deepseek/deepseek-r1:free',
      task_dest: '',
      instructions: '',
    });
    const opts = {
      hostname:'127.0.0.1', port:8889, path:'/api/prompt', method:'POST',
      headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)},
    };
    const req = http.request(opts, res => {
      const timer = setTimeout(() => { req.destroy(); resolve(); }, 30000);
      let buf = '';
      res.on('data', chunk => {
        buf += chunk.toString();
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') { clearTimeout(timer); resolve(); return; }
          try {
            const obj = JSON.parse(raw);
            if (obj.delta || obj.error) promptGotStream = true;
            if (obj.queue_item) { promptGotQueueItem = true; promptItemId = obj.queue_item.id; }
          } catch {}
        }
      });
      res.on('end', () => { clearTimeout(timer); resolve(); });
      res.on('error', () => { clearTimeout(timer); resolve(); });
    });
    req.on('error', () => resolve());
    req.write(body);
    req.end();
  });
  assert('T34: /api/prompt SSE stream delivers data (delta or error)', promptGotStream);
  assert('T35: /api/prompt SSE emits queue_item event immediately', promptGotQueueItem,
    `promptItemId=${promptItemId}`);

  // T36: queue item appears in /api/queue after prompt
  await sleep(500);
  try {
    const r = await httpGet('/api/queue');
    const items = JSON.parse(r.body);
    const found = items.find(i => i.id === promptItemId);
    assert('T36: Queue item present in /api/queue after prompt',
      !!found, `items=${items.length} lookingFor=${promptItemId}`);
  } catch(e) { assert('T36: Queue item in /api/queue', false, e.message); }

  // T37: queue item has status field
  try {
    const r = await httpGet('/api/queue');
    const items = JSON.parse(r.body);
    const found = items.find(i => i.id === promptItemId);
    assert('T37: Queue item has status field',
      found && ['queued','local','pr_open','merged','closed'].includes(found.status),
      `status=${found ? found.status : 'not found'}`);
  } catch(e) { assert('T37: Queue item has status', false, e.message); }

  // T38: DELETE /api/chat clears history
  try {
    const r = await httpDelete('/api/chat');
    assert('T38: DELETE /api/chat returns 200', r.status === 200, `status=${r.status}`);
  } catch(e) { assert('T38: DELETE /api/chat', false, e.message); }

  // T39: POST /api/queue/poll returns 200
  try {
    const r = await httpPost('/api/queue/poll', '{}');
    assert('T39: POST /api/queue/poll returns 200', r.status === 200, `status=${r.status}`);
  } catch(e) { assert('T39: POST /api/queue/poll', false, e.message); }

  // ══════════════════════════════════════════════════════════════
  // T40: Mobile — input bar sticks to bottom, no overflow
  // ══════════════════════════════════════════════════════════════
  try {
    const mob2 = await browser.newPage();
    await mob2.setViewportSize({ width: 390, height: 844 });
    await mob2.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 12000 });
    await sleep(800);

    // Input bar position (fixed/sticky)
    const barPos = await mob2.$eval('#input-bar', el => {
      const r = el.getBoundingClientRect();
      const pos = getComputedStyle(el).position;
      return { bottom: r.bottom, viewH: window.innerHeight, pos };
    });
    const barAtBottom = barPos.pos === 'fixed' || barPos.bottom >= barPos.viewH - 80;

    // No horizontal overflow
    const { scrollWidth, viewWidth } = await mob2.evaluate(() => ({
      scrollWidth: document.body.scrollWidth,
      viewWidth: window.innerWidth,
    }));

    assert('T40: Mobile 390px — input bar fixed at bottom, no overflow',
      barAtBottom && scrollWidth <= viewWidth + 5,
      `pos=${barPos.pos} bottom=${barPos.bottom.toFixed(0)} viewH=${barPos.viewH} scrollW=${scrollWidth}`);

    await mob2.close();
  } catch(e) {
    assert('T40: Mobile 390px — input bar fixed at bottom, no overflow', false, e.message.split('\n')[0]);
  }

  // ── summary ───────────────────────────────────────────────────────────────
  await browser.close();

  console.log('\nPlaywright Test Results:');
  results.forEach(r => console.log(r));
  console.log(`\n${passed} passed, ${failed} failed out of ${passed + failed} tests`);

  if (failed > 0) {
    console.log('\nFailed tests above — fix before pushing branch.');
    process.exit(1);
  }
  process.exit(0);
})();
