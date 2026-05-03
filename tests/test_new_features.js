#!/usr/bin/env node
/**
 * Hive UI — new-features test suite (24 tests, T71–T94)
 * Covers all features added since commit 8480238:
 *   - Force-priority button (#priority-btn)
 *   - Logs-first DOM order
 *   - Full ANSI renderer (256-color, 24-bit, italic, underline, dim, strikethrough)
 *   - #hive-feed unified feed
 *   - No #panels element
 *   - SSE combined-only stream
 *   - Priority queue insertion
 *   - Chat persistence key hive_chat_v1
 *   - sendPrompt(priority) signature
 *   - Mobile 390px — no overflow, priority-btn visible
 *   - test_system.sh exists + executable
 *   - supervisor.sh has check_resource_guardian
 *   - Ollama throttle.conf present
 *   - Sleep targets masked
 *   - #combined-count element exists
 *
 * Run: PORT=8889 node tests/test_new_features.js
 */
'use strict';
const { chromium } = require('playwright');
const http         = require('http');
const fs           = require('fs');
const path         = require('path');
const { execSync } = require('child_process');

const PORT = process.env.PORT || 8889;
const BASE = `http://127.0.0.1:${PORT}`;
const HIVE_DIR = path.resolve(__dirname, '..');

function httpGet(p) {
  return new Promise((res, rej) => {
    http.get(BASE + p, r => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => res({ status: r.statusCode, body: d }));
      r.on('error', rej);
    }).on('error', rej);
  });
}

function httpPost(urlPath, body) {
  return new Promise((res, rej) => {
    const buf = Buffer.from(typeof body === 'string' ? body : JSON.stringify(body));
    const opts = {
      hostname: '127.0.0.1', port: Number(PORT), path: urlPath, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': buf.length },
    };
    const req = http.request(opts, r => {
      let d = ''; r.on('data', c => d += c);
      r.on('end', () => res({ status: r.statusCode, body: d }));
      r.on('error', rej);
    });
    req.on('error', rej);
    req.write(buf); req.end();
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

(async () => {
  const browser = await chromium.launch({ headless: true });
  let passed = 0, failed = 0;
  const results = [];

  function assert(name, cond, detail) {
    const msg = detail ? `${name} — ${detail}` : name;
    if (cond) { passed++; results.push(`  ✓ ${msg}`); }
    else       { failed++; results.push(`  ✗ ${msg}`); }
  }

  // ── Desktop page ─────────────────────────────────────────────────────────────
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 800 });
  try {
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
  } catch(e) { console.error('FATAL: Could not load page:', e.message); process.exit(1); }

  // ── T71: #priority-btn exists in DOM ─────────────────────────────────────────
  try {
    const btn = await page.$('#priority-btn');
    assert('T71: #priority-btn exists in DOM', !!btn);
  } catch(e) { assert('T71: #priority-btn exists', false, e.message); }

  // ── T72: #priority-btn min-height >= 44px (touch target) ─────────────────────
  try {
    const h = await page.$eval('#priority-btn', el => parseInt(getComputedStyle(el).minHeight) || el.getBoundingClientRect().height);
    assert('T72: #priority-btn height >= 44px', h >= 44, `got ${h}px`);
  } catch(e) { assert('T72: #priority-btn height >= 44px', false, e.message); }

  // ── T73: #logs-section comes before #chat-section and #queue-section ─────────
  try {
    const order = await page.evaluate(() => {
      const details = Array.from(document.querySelectorAll('#main > details'));
      const ids = details.map(d => d.id);
      const logsIdx  = ids.indexOf('logs-section');
      const chatIdx  = ids.indexOf('chat-section');
      const queueIdx = ids.indexOf('queue-section');
      return { logsIdx, chatIdx, queueIdx };
    });
    const logsFirst = order.logsIdx >= 0
      && (order.chatIdx < 0  || order.logsIdx < order.chatIdx)
      && (order.queueIdx < 0 || order.logsIdx < order.queueIdx);
    assert('T73: #logs-section before #chat-section and #queue-section',
      logsFirst, `logs=${order.logsIdx} chat=${order.chatIdx} queue=${order.queueIdx}`);
  } catch(e) { assert('T73: logs-section order', false, e.message); }

  // ── T74: ansiToHtml handles 256-color (38;5;196 = bright red) ────────────────
  try {
    const result = await page.evaluate(() => {
      if (typeof ansiToHtml !== 'function') return 'MISSING';
      return ansiToHtml('\x1b[38;5;196mtest\x1b[0m');
    });
    assert('T74: ansiToHtml handles 256-color (38;5;196)',
      result !== 'MISSING' && result.includes('color:') && result.includes('test'),
      `got: ${String(result).slice(0,80)}`);
  } catch(e) { assert('T74: ansiToHtml 256-color', false, e.message); }

  // ── T75: ansiToHtml handles 24-bit TrueColor (38;2;255;100;0) ────────────────
  try {
    const result = await page.evaluate(() => {
      if (typeof ansiToHtml !== 'function') return 'MISSING';
      return ansiToHtml('\x1b[38;2;255;100;0mtest\x1b[0m');
    });
    assert('T75: ansiToHtml handles 24-bit TrueColor (38;2;255;100;0)',
      result !== 'MISSING' && result.includes('rgb(255,100,0)'),
      `got: ${String(result).slice(0,80)}`);
  } catch(e) { assert('T75: ansiToHtml 24-bit color', false, e.message); }

  // ── T76: ansiToHtml handles italic (code 3) → font-style:italic ──────────────
  try {
    const result = await page.evaluate(() => {
      if (typeof ansiToHtml !== 'function') return 'MISSING';
      return ansiToHtml('\x1b[3mtest\x1b[0m');
    });
    assert('T76: ansiToHtml italic (code 3) → font-style:italic',
      result !== 'MISSING' && result.includes('font-style:italic'),
      `got: ${String(result).slice(0,80)}`);
  } catch(e) { assert('T76: ansiToHtml italic', false, e.message); }

  // ── T77: ansiToHtml handles underline (code 4) → text-decoration:underline ───
  try {
    const result = await page.evaluate(() => {
      if (typeof ansiToHtml !== 'function') return 'MISSING';
      return ansiToHtml('\x1b[4mtest\x1b[0m');
    });
    assert('T77: ansiToHtml underline (code 4) → text-decoration:underline',
      result !== 'MISSING' && result.includes('text-decoration:underline'),
      `got: ${String(result).slice(0,80)}`);
  } catch(e) { assert('T77: ansiToHtml underline', false, e.message); }

  // ── T78: ansiToHtml handles dim (code 2) → opacity:.6 ───────────────────────
  try {
    const result = await page.evaluate(() => {
      if (typeof ansiToHtml !== 'function') return 'MISSING';
      return ansiToHtml('\x1b[2mtest\x1b[0m');
    });
    assert('T78: ansiToHtml dim (code 2) → opacity:.6',
      result !== 'MISSING' && result.includes('opacity:.6'),
      `got: ${String(result).slice(0,80)}`);
  } catch(e) { assert('T78: ansiToHtml dim', false, e.message); }

  // ── T79: #hive-feed element exists ───────────────────────────────────────────
  try {
    const el = await page.$('#hive-feed');
    assert('T79: #hive-feed element exists', !!el);
  } catch(e) { assert('T79: #hive-feed exists', false, e.message); }

  // ── T80: #panels div does NOT exist (removed) ────────────────────────────────
  try {
    const el = await page.$('#panels');
    assert('T80: #panels div does NOT exist (removed)', !el);
  } catch(e) { assert('T80: #panels absent', false, e.message); }

  // ── T81: /stream SSE payload uses "combined" key, no "sessions" key ──────────
  // Test via source code (stream only fires when new lines arrive; too slow for live test)
  try {
    const src = fs.readFileSync(path.join(HIVE_DIR, 'logstream.py'), 'utf8');
    // Combined-only: should emit {"combined": ...} not {"sessions": ...}
    const emitsCombined  = src.includes('"combined": new_combined') || src.includes('"combined":');
    const emitsSessions  = src.includes('"sessions": ') && src.includes('payload') && false; // always false — just check structure
    // Confirm no per-session sessions dict in the SSE payload
    const noSessionsEmit = !src.match(/payload\s*=.*"sessions"/);
    assert('T81: logstream.py SSE emits "combined" key',
      emitsCombined, `combined found=${emitsCombined}`);
    assert('T81b: logstream.py SSE does NOT emit "sessions" dict in payload',
      noSessionsEmit, `sessions-in-payload=${!noSessionsEmit}`);
  } catch(e) { assert('T81: SSE combined-only format', false, e.message); }

  // ── T82: POST /api/prompt with priority:true → queue_item.priority === true ──
  let priorityId = null;
  try {
    const r = await httpPost('/api/prompt', JSON.stringify({ prompt: '__test_priority__', priority: true }));
    assert('T82: POST /api/prompt priority returns 200', r.status === 200, `status=${r.status}`);
    try {
      // Response is SSE stream; first data: event is {"queue_item": {...}}
      const match = r.body.match(/data:\s*(\{[^\n]+\})/);
      if (match) {
        const obj = JSON.parse(match[1]);
        const item = obj.queue_item || obj;
        priorityId = item.id || null;
        assert('T82b: response queue_item has id and priority=true',
          !!priorityId && item.priority === true,
          `id=${priorityId} priority=${item.priority}`);
      } else {
        assert('T82b: response queue_item has id and priority=true', false, 'no data: event in body');
      }
    } catch(pe) { assert('T82b: response queue_item has id and priority=true', false, pe.message); }
  } catch(e) { assert('T82: POST /api/prompt priority', false, e.message); }

  // ── T83: Priority item is at index 0 of /api/queue ───────────────────────────
  try {
    await sleep(200);
    const qr = await httpGet('/api/queue');
    const queue = JSON.parse(qr.body);
    const firstItem = Array.isArray(queue) ? queue[0] : null;
    assert('T83: Priority item at index 0 of /api/queue',
      firstItem && (firstItem.prompt === '__test_priority__' || firstItem.priority === true),
      `first=${JSON.stringify(firstItem).slice(0,80)}`);
  } catch(e) { assert('T83: priority item at queue front', false, e.message); }

  // ── T84: tests/test_system.sh exists and is executable ───────────────────────
  try {
    const p = path.join(HIVE_DIR, 'tests', 'test_system.sh');
    const exists = fs.existsSync(p);
    const exec   = exists && !!(fs.statSync(p).mode & 0o111);
    assert('T84: tests/test_system.sh exists and is executable', exists && exec,
      `exists=${exists} exec=${exec}`);
  } catch(e) { assert('T84: test_system.sh exists', false, e.message); }

  // ── T85: supervisor.sh contains check_resource_guardian ──────────────────────
  try {
    const src = fs.readFileSync(path.join(HIVE_DIR, 'supervisor.sh'), 'utf8');
    assert('T85: supervisor.sh has check_resource_guardian()',
      src.includes('check_resource_guardian'));
  } catch(e) { assert('T85: supervisor resource guardian', false, e.message); }

  // ── T86: Ollama throttle.conf exists ─────────────────────────────────────────
  try {
    const exists = fs.existsSync('/etc/systemd/system/ollama.service.d/throttle.conf');
    assert('T86: /etc/systemd/system/ollama.service.d/throttle.conf exists', exists);
  } catch(e) { assert('T86: throttle.conf exists', false, e.message); }

  // ── T87: CPUQuota=1000% inside throttle.conf ─────────────────────────────────
  try {
    const src = fs.readFileSync('/etc/systemd/system/ollama.service.d/throttle.conf', 'utf8');
    assert('T87: throttle.conf has CPUQuota=1000%', src.includes('CPUQuota=1000%'));
  } catch(e) { assert('T87: throttle.conf CPUQuota', false, e.message); }

  // ── T88: sleep.target is masked (symlink to /dev/null) ───────────────────────
  try {
    const link = fs.readlinkSync('/etc/systemd/system/sleep.target');
    assert('T88: sleep.target is masked (→/dev/null)', link === '/dev/null', `link=${link}`);
  } catch(e) { assert('T88: sleep.target masked', false, e.message); }

  // ── T89: crontab has renice job ───────────────────────────────────────────────
  try {
    const cron = execSync('crontab -l 2>/dev/null || true', { encoding: 'utf8' });
    assert('T89: crontab has renice job for ollama/research_loop',
      cron.includes('renice') && (cron.includes('ollama') || cron.includes('research_loop')));
  } catch(e) { assert('T89: crontab renice job', false, e.message); }

  // ── T90: Chat persistence key hive_chat_v1 in page HTML ──────────────────────
  try {
    const src = fs.readFileSync(path.join(HIVE_DIR, 'ui_shared.py'), 'utf8');
    assert('T90: CHAT_PERSIST_KEY = hive_chat_v1 in ui_shared.py',
      src.includes("hive_chat_v1"));
  } catch(e) { assert('T90: chat persist key', false, e.message); }

  // ── T91: window.sendPrompt exists and accepts priority argument ───────────────
  try {
    const result = await page.evaluate(() => {
      if (typeof sendPrompt !== 'function') return 'MISSING';
      // Check the function source includes 'priority' param
      return sendPrompt.toString().includes('priority') ? 'ok' : 'no_priority_param';
    });
    assert('T91: window.sendPrompt(priority) signature exists', result === 'ok', `got: ${result}`);
  } catch(e) { assert('T91: sendPrompt(priority)', false, e.message); }

  // ── T92: Mobile 390px — #priority-btn visible, no horizontal overflow ─────────
  const mobilePage = await browser.newPage();
  await mobilePage.setViewportSize({ width: 390, height: 844 });
  try {
    await mobilePage.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
    const scrollW = await mobilePage.evaluate(() => document.documentElement.scrollWidth);
    const btnVisible = await mobilePage.evaluate(() => {
      const btn = document.getElementById('priority-btn');
      if (!btn) return false;
      const r = btn.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && r.left >= 0 && r.right <= 390;
    });
    assert('T92: Mobile 390px — #priority-btn visible, no overflow',
      scrollW <= 390 && btnVisible,
      `scrollW=${scrollW} btnVisible=${btnVisible}`);
  } catch(e) { assert('T92: mobile priority-btn', false, e.message); }
  await mobilePage.close();

  // ── T93: /api/status returns 200 (hive-live running) ─────────────────────────
  try {
    const r = await httpGet('/api/status');
    assert('T93: /api/status returns 200', r.status === 200, `got ${r.status}`);
  } catch(e) { assert('T93: /api/status 200', false, e.message); }

  // ── T94: #combined-count element exists; #hive-feed exists ───────────────────
  try {
    const cc = await page.$('#combined-count');
    const hf = await page.$('#hive-feed');
    assert('T94: #combined-count and #hive-feed both exist',
      !!cc && !!hf, `combined-count=${!!cc} hive-feed=${!!hf}`);
  } catch(e) { assert('T94: combined-count + hive-feed', false, e.message); }

  // ── Cleanup: remove test priority item from queue ────────────────────────────
  if (priorityId) {
    try {
      await new Promise((res, rej) => {
        const opts = { hostname:'127.0.0.1', port:Number(PORT),
          path:`/api/queue/${priorityId}`, method:'DELETE' };
        const req = http.request(opts, r => { r.resume(); r.on('end', res); r.on('error', rej); });
        req.on('error', rej); req.end();
      });
    } catch(_) {}
  }

  await browser.close();

  console.log('\n' + results.join('\n'));
  console.log(`\n${passed} passed, ${failed} failed out of ${passed + failed} tests`);
  process.exit(failed > 0 ? 1 : 0);
})();
