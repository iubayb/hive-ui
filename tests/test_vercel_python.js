#!/usr/bin/env node
/**
 * test_vercel_python.js — Standalone Python server test suite (VP1–VP25)
 *
 * Tests vercel_hive.py in STANDALONE mode (no HIVE_BACKEND_URL).
 * Starts the Python server on port 8091, runs all assertions, then exits.
 *
 * Run: node tests/test_vercel_python.js
 *      OPENROUTER_API_KEY=sk-... node tests/test_vercel_python.js
 */

'use strict';

const http       = require('http');
const https      = require('https');
const { spawn }  = require('child_process');
const { chromium } = require('playwright');

const PORT    = 8091;
const BASE    = `http://127.0.0.1:${PORT}`;
const SCRIPT  = require('path').join(__dirname, '..', 'vercel_hive.py');
const API_KEY = process.env.OPENROUTER_API_KEY || '';

function get(path, opts = {}) {
  return new Promise((res, rej) => {
    const url = BASE + path;
    http.get(url, opts, r => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => res({ status: r.statusCode, body: d, headers: r.headers }));
      r.on('error', rej);
    }).on('error', rej);
  });
}

function post(path, body, extraHeaders = {}) {
  return new Promise((res, rej) => {
    const data = typeof body === 'string' ? body : JSON.stringify(body);
    const opts = {
      hostname: '127.0.0.1', port: PORT, path,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data), ...extraHeaders },
    };
    const req = http.request(opts, r => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => res({ status: r.statusCode, body: d, headers: r.headers }));
      r.on('error', rej);
    });
    req.on('error', rej);
    req.write(data);
    req.end();
  });
}

function options(path) {
  return new Promise((res, rej) => {
    const opts = {
      hostname: '127.0.0.1', port: PORT, path,
      method: 'OPTIONS',
      headers: { Origin: 'https://example.com', 'Access-Control-Request-Method': 'POST' },
    };
    const req = http.request(opts, r => {
      let d = ''; r.on('data', c => d += c);
      r.on('end', () => res({ status: r.statusCode, body: d, headers: r.headers }));
      r.on('error', rej);
    });
    req.on('error', rej);
    req.end();
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function waitReady(ms = 8000) {
  const start = Date.now();
  return new Promise((res, rej) => {
    const try_ = () => {
      http.get(BASE + '/api/status', r => { r.resume(); res(); })
        .on('error', () => {
          if (Date.now() - start > ms) return rej(new Error('server never became ready'));
          setTimeout(try_, 200);
        });
    };
    try_();
  });
}

(async () => {
  // ── start server ────────────────────────────────────────────────────────────
  const env = { ...process.env, PORT: String(PORT) };
  // Unset HIVE_BACKEND_URL to ensure standalone mode
  delete env.HIVE_BACKEND_URL;
  const srv = spawn('python3', [SCRIPT], { env, stdio: ['ignore', 'pipe', 'pipe'] });
  srv.stderr.on('data', () => {});
  srv.stdout.on('data', () => {});

  try {
    await waitReady(10000);
  } catch (e) {
    console.error('FATAL: server did not start:', e.message);
    srv.kill();
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  let passed = 0, failed = 0;
  const results = [];

  function assert(id, name, cond, detail = '') {
    const label = detail ? `${id}: ${name} — ${detail}` : `${id}: ${name}`;
    if (cond) { passed++; results.push(`  ✓ ${label}`); }
    else       { failed++; results.push(`  ✗ ${label}`); }
  }

  // ── raw HTML fetch ──────────────────────────────────────────────────────────
  let root;
  try { root = await get('/'); } catch (e) { console.error('FATAL fetch /:', e.message); srv.kill(); process.exit(1); }
  const html = root.body;

  // ── VP1–VP8: HTML structure ─────────────────────────────────────────────────
  assert('VP1', 'GET / returns 200', root.status === 200, `status=${root.status}`);
  assert('VP2', 'Content-Type is text/html', (root.headers['content-type'] || '').includes('text/html'), root.headers['content-type']);
  assert('VP3', 'HTML has chat input element', html.includes('id="chat-input"') || html.includes("id='chat-input'"), 'no #chat-input');
  assert('VP4', 'HTML has chat send button', html.includes('id="chat-send"') || html.includes("id='chat-send'"), 'no #chat-send');
  assert('VP5', 'HTML has model badge element', html.includes('id="chat-model"') || html.includes("id='chat-model'"), 'no #chat-model');
  assert('VP6', 'HTML has correct default model in badge', html.includes('openai/gpt-oss-120b:free'), 'model not found in HTML');
  assert('VP7', 'HTML has position:fixed input bar', html.includes('position:fixed'), 'no position:fixed');
  assert('VP8', 'HTML has iOS safe-area insets', html.includes('safe-area-inset-bottom'), 'no safe-area-inset-bottom');

  // ── VP9–VP12: API endpoints ─────────────────────────────────────────────────
  let status, config_;
  try { status = await get('/api/status'); } catch { status = { status: 0, body: '' }; }
  try { config_ = await get('/api/config'); } catch { config_ = { status: 0, body: '' }; }

  assert('VP9',  'GET /api/status returns 200',       status.status === 200, `status=${status.status}`);
  let statusJson;
  try { statusJson = JSON.parse(status.body); } catch { statusJson = null; }
  assert('VP10', '/api/status JSON has mode=standalone', statusJson?.mode === 'standalone', `mode=${statusJson?.mode}`);
  assert('VP11', 'GET /api/config returns 200',        config_.status === 200, `status=${config_.status}`);
  let configJson;
  try { configJson = JSON.parse(config_.body); } catch { configJson = null; }
  assert('VP12', '/api/config has correct default model', configJson?.model === 'openai/gpt-oss-120b:free', `model=${configJson?.model}`);
  assert('VP13', '/api/config favorites[0] is gpt-oss-120b', (configJson?.favorites || [])[0] === 'openai/gpt-oss-120b:free', `fav0=${(configJson?.favorites||[])[0]}`);
  assert('VP14', '/api/config has 6 favorites',         (configJson?.favorites || []).length === 6, `len=${(configJson?.favorites||[]).length}`);

  // ── VP15–VP16: 404 + CORS ───────────────────────────────────────────────────
  let notFound;
  try { notFound = await get('/api/does-not-exist'); } catch { notFound = { status: 0 }; }
  assert('VP15', 'GET /api/unknown returns 404', notFound.status === 404, `status=${notFound.status}`);

  let preflight;
  try { preflight = await options('/api/chat'); } catch { preflight = { status: 0, headers: {} }; }
  assert('VP16', 'OPTIONS /api/chat returns 204', preflight.status === 204, `status=${preflight.status}`);
  assert('VP17', 'OPTIONS /api/chat has CORS header', (preflight.headers['access-control-allow-origin'] || '') === '*', `acao=${preflight.headers['access-control-allow-origin']}`);

  // ── VP18–VP19: POST /api/chat validation ────────────────────────────────────
  let chatEmpty, chatNoKey;
  try { chatEmpty = await post('/api/chat', {}); } catch { chatEmpty = { status: 0, body: '' }; }
  assert('VP18', 'POST /api/chat with no message returns 400', chatEmpty.status === 400, `status=${chatEmpty.status}`);

  // Test "no API key" scenario: start a temp server without key set
  // We can approximate: if API key IS set, test that a real message gets a non-500 response from OpenRouter fallback path;
  // if not set, it should return 500 with error JSON.
  if (!API_KEY) {
    // Attempt a real chat call — should 500 with "not configured" error
    try { chatNoKey = await post('/api/chat', { message: 'hello' }); } catch { chatNoKey = { status: 0, body: '' }; }
    assert('VP19', 'POST /api/chat without API key returns 500', chatNoKey.status === 500, `status=${chatNoKey.status}`);
    let errJson; try { errJson = JSON.parse(chatNoKey.body); } catch {}
    assert('VP19b', 'Error JSON has error field', typeof errJson?.error === 'string', `body=${chatNoKey.body.slice(0,80)}`);
  } else {
    // API key present — Python fallback path should call OpenRouter synchronously
    // Just verify it returns 200 or a valid upstream error (not a server crash)
    try { chatNoKey = await post('/api/chat', { message: 'say hi in one word' }); } catch { chatNoKey = { status: 0, body: '{}' }; }
    const validResp = chatNoKey.status === 200 || chatNoKey.status === 429 || chatNoKey.status === 502;
    assert('VP19', 'POST /api/chat with API key returns valid response', validResp, `status=${chatNoKey.status}`);
  }

  // ── VP20–VP25: Browser rendering ────────────────────────────────────────────
  const page = await browser.newPage();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await sleep(400);

  // No horizontal overflow at 390px
  const scrollW = await page.evaluate(() => document.documentElement.scrollWidth);
  assert('VP20', 'No horizontal overflow at 390px', scrollW <= 390, `scrollW=${scrollW}`);

  // All interactive elements ≥ 44px
  const smallTargets = await page.evaluate(() => {
    const els = document.querySelectorAll('button, input[type=submit], input[type=button], textarea, [onclick]');
    const bad = [];
    els.forEach(el => {
      const r = el.getBoundingClientRect();
      if (r.height > 0 && r.height < 44) bad.push({ id: el.id, tag: el.tagName, h: Math.round(r.height) });
    });
    return bad;
  });
  assert('VP21', 'All interactive elements ≥ 44px tap target', smallTargets.length === 0, smallTargets.map(x => `${x.tag}#${x.id}=${x.h}px`).join(', '));

  // Chat input is visible
  const inputVisible = await page.evaluate(() => {
    const el = document.getElementById('chat-input');
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  });
  assert('VP22', '#chat-input is visible on screen', inputVisible, 'element not visible');

  // Send button is visible and enabled
  const sendState = await page.evaluate(() => {
    const el = document.getElementById('chat-send');
    if (!el) return { visible: false, disabled: true };
    const r = el.getBoundingClientRect();
    return { visible: r.width > 0 && r.height > 0, disabled: el.disabled };
  });
  assert('VP23', '#chat-send is visible', sendState.visible, 'send button not visible');
  assert('VP24', '#chat-send is enabled on load', !sendState.disabled, 'send button is disabled on load');

  // Model badge shows model name
  const modelText = await page.evaluate(() => {
    const el = document.getElementById('chat-model');
    return el ? el.textContent.trim() : '';
  });
  assert('VP25', '#chat-model shows model name', modelText.includes('gpt-oss') || modelText.length > 5, `text="${modelText}"`);

  await browser.close();

  // ── report ──────────────────────────────────────────────────────────────────
  console.log('\nVercel Python standalone tests (VP1–VP25):');
  results.forEach(r => console.log(r));
  console.log(`\n${passed} passed, ${failed} failed out of ${passed + failed} tests`);

  srv.kill();
  process.exit(failed > 0 ? 1 : 0);
})();
