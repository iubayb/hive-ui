#!/usr/bin/env node
/**
 * Hive UI — extended Playwright test suite (30 tests, T41–T70)
 * Targeting http://127.0.0.1:8889 (dev server, never 8888)
 *
 * Run: PORT=8889 node tests/test_extended.js
 *
 * Coverage:
 *   T41–T45  Questions (add / list / filter / answer)
 *   T46–T48  Researcher tracker API
 *   T49–T52  Groups
 *   T53–T57  Arena status / results / run guard
 *   T58–T62  Doctor + status KB endpoints
 *   T63–T67  UID registry + privacy
 *   T68–T70  Visual / browser
 */
const { chromium } = require('playwright');
const http  = require('http');
const https = require('https');

const BASE = 'http://127.0.0.1:8889';
const PORT = 8889;

// ── helpers ──────────────────────────────────────────────────────────────────

function httpGet(urlPath, extraHeaders = {}) {
  return new Promise((res, rej) => {
    const opts = {
      hostname: '127.0.0.1', port: PORT,
      path: urlPath, method: 'GET',
      headers: extraHeaders,
    };
    const req = http.request(opts, r => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => res({ status: r.statusCode, body: d }));
      r.on('error', rej);
    });
    req.on('error', rej);
    req.end();
  });
}

function httpPost(urlPath, body, extraHeaders = {}) {
  return new Promise((res, rej) => {
    const buf = typeof body === 'string' ? Buffer.from(body) : body;
    const opts = {
      hostname: '127.0.0.1', port: PORT,
      path: urlPath, method: 'POST',
      headers: Object.assign({
        'Content-Type':   'application/json',
        'Content-Length': buf.length,
      }, extraHeaders),
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

function httpDelete(urlPath, body = null) {
  return new Promise((res, rej) => {
    const buf = body ? Buffer.from(JSON.stringify(body)) : null;
    const opts = {
      hostname: '127.0.0.1', port: PORT,
      path: urlPath, method: 'DELETE',
      headers: buf
        ? { 'Content-Type': 'application/json', 'Content-Length': buf.length }
        : {},
    };
    const req = http.request(opts, r => {
      let d = ''; r.on('data', c => d += c);
      r.on('end', () => res({ status: r.statusCode, body: d }));
      r.on('error', rej);
    });
    req.on('error', rej);
    if (buf) req.write(buf);
    req.end();
  });
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

  // ══════════════════════════════════════════════════════════════
  // T41–T45: Questions
  // ══════════════════════════════════════════════════════════════

  // T41: POST /api/status/question → 200 with id
  let questionId = null;
  try {
    const r = await httpPost('/api/status/question', JSON.stringify({
      hive: 'test-hive', agent: 'test-agent',
      question: 'What is 2+2?', hint: 'arithmetic', type: 'text',
    }));
    const obj = JSON.parse(r.body);
    questionId = obj.id;
    assert('T41: POST /api/status/question → 200 with id',
      r.status === 200 && !!obj.id, `status=${r.status} id=${obj.id}`);
  } catch(e) { assert('T41: POST /api/status/question', false, e.message); }

  // T42: GET /api/status/questions returns list including new question
  try {
    const r = await httpGet('/api/status/questions');
    const list = JSON.parse(r.body);
    const found = Array.isArray(list) && list.find(q => q.id === questionId);
    assert('T42: GET /api/status/questions contains posted question',
      !!found, `list.length=${Array.isArray(list) ? list.length : '?'} id=${questionId}`);
  } catch(e) { assert('T42: GET /api/status/questions', false, e.message); }

  // T43: GET /api/status/questions?unanswered includes unanswered question
  try {
    const r = await httpGet('/api/status/questions?unanswered');
    const list = JSON.parse(r.body);
    const found = Array.isArray(list) && list.find(q => q.id === questionId);
    assert('T43: GET /api/status/questions?unanswered includes unanswered',
      !!found, `found=${!!found}`);
  } catch(e) { assert('T43: ?unanswered filter', false, e.message); }

  // T44: POST /api/status/answer → 200
  try {
    const r = await httpPost('/api/status/answer', JSON.stringify({
      id: questionId, answer: '4', answered_by: 'human',
    }));
    const obj = JSON.parse(r.body);
    assert('T44: POST /api/status/answer → 200 ok:true',
      r.status === 200 && obj.ok === true, `status=${r.status} ok=${obj.ok}`);
  } catch(e) { assert('T44: POST /api/status/answer', false, e.message); }

  // T45: After answering, ?unanswered no longer includes the question
  try {
    const r = await httpGet('/api/status/questions?unanswered');
    const list = JSON.parse(r.body);
    const stillThere = Array.isArray(list) && list.find(q => q.id === questionId);
    assert('T45: Answered question excluded from ?unanswered list',
      !stillThere, `stillInUnanswered=${!!stillThere}`);
  } catch(e) { assert('T45: answered question excluded', false, e.message); }

  // ══════════════════════════════════════════════════════════════
  // T46–T48: Researcher tracker API
  // ══════════════════════════════════════════════════════════════

  // T46: POST /api/tracker/add → 200 with handle echoed
  const TEST_HANDLE = 'test-researcher-' + Date.now();
  try {
    const r = await httpPost('/api/tracker/add', JSON.stringify({
      handle:   TEST_HANDLE,
      platform: 'github',
      keywords: ['ai', 'ml'],
      context:  'test researcher added by T46',
    }));
    const obj = JSON.parse(r.body);
    assert('T46: POST /api/tracker/add → 200 with handle echoed',
      r.status === 200 && obj.handle === TEST_HANDLE,
      `status=${r.status} handle=${obj.handle}`);
  } catch(e) { assert('T46: POST /api/tracker/add', false, e.message); }

  // T47: GET /api/tracker/status → 200 JSON object (no crash)
  try {
    const r = await httpGet('/api/tracker/status');
    const obj = JSON.parse(r.body);
    assert('T47: GET /api/tracker/status → 200 JSON object',
      r.status === 200 && typeof obj === 'object',
      `status=${r.status} keys=${Object.keys(obj).join(',')}`);
  } catch(e) { assert('T47: GET /api/tracker/status', false, e.message); }

  // T48: DELETE /api/tracker/remove → 200 (cleanup T46 entry)
  try {
    const r = await httpDelete('/api/tracker/remove', { handle: TEST_HANDLE });
    const obj = JSON.parse(r.body);
    assert('T48: DELETE /api/tracker/remove → 200',
      r.status === 200 && obj.ok === true,
      `status=${r.status} ok=${obj.ok}`);
  } catch(e) { assert('T48: DELETE /api/tracker/remove', false, e.message); }

  // ══════════════════════════════════════════════════════════════
  // T49–T52: Groups
  // ══════════════════════════════════════════════════════════════

  // T49: POST /api/groups with new group → 200
  try {
    const r = await httpPost('/api/groups', JSON.stringify({
      groups: { 'test-group': ['session-a', 'session-b'] },
    }));
    const obj = JSON.parse(r.body);
    assert('T49: POST /api/groups → 200 ok:true',
      r.status === 200 && obj.ok === true, `status=${r.status}`);
  } catch(e) { assert('T49: POST /api/groups', false, e.message); }

  // T50: GET /api/groups → contains newly added group
  try {
    const r = await httpGet('/api/groups');
    const obj = JSON.parse(r.body);
    const hasGroup = obj.groups && 'test-group' in obj.groups;
    assert('T50: GET /api/groups contains added test-group',
      r.status === 200 && hasGroup, `keys=${Object.keys(obj.groups || {}).join(',')}`);
  } catch(e) { assert('T50: GET /api/groups', false, e.message); }

  // T51: GET /api/groups response has "groups" key
  try {
    const r = await httpGet('/api/groups');
    const obj = JSON.parse(r.body);
    assert('T51: GET /api/groups response shape has "groups" key',
      'groups' in obj, `keys=${Object.keys(obj).join(',')}`);
  } catch(e) { assert('T51: /api/groups shape', false, e.message); }

  // T52: /api/config returns expected config keys
  try {
    const r = await httpGet('/api/config');
    const cfg = JSON.parse(r.body);
    const keys = ['model', 'llm_base_url', 'api_key_set', 'favorites', 'ai_auto_answer'];
    const missing = keys.filter(k => !(k in cfg));
    assert('T52: /api/config has all required keys',
      missing.length === 0, `missing=${missing.join(',') || 'none'}`);
  } catch(e) { assert('T52: /api/config keys', false, e.message); }

  // ══════════════════════════════════════════════════════════════
  // T53–T57: Arena
  // ══════════════════════════════════════════════════════════════

  // T53: GET /api/arena/status → 200 JSON object
  try {
    const r = await httpGet('/api/arena/status');
    const obj = JSON.parse(r.body);
    assert('T53: GET /api/arena/status → 200 JSON object',
      r.status === 200 && typeof obj === 'object',
      `status=${r.status} keys=${Object.keys(obj).join(',')}`);
  } catch(e) { assert('T53: GET /api/arena/status', false, e.message); }

  // T54: GET /api/arena/results → 200 JSON object
  try {
    const r = await httpGet('/api/arena/results');
    const obj = JSON.parse(r.body);
    assert('T54: GET /api/arena/results → 200 JSON object',
      r.status === 200 && typeof obj === 'object',
      `status=${r.status}`);
  } catch(e) { assert('T54: GET /api/arena/results', false, e.message); }

  // T55: POST /api/arena/run with no API key → error or already-running (not crash)
  try {
    const r = await httpPost('/api/arena/run', JSON.stringify({ arena_type: 'text' }));
    const obj = JSON.parse(r.body);
    const hasExpected = 'error' in obj || 'message' in obj || 'running' in obj;
    assert('T55: POST /api/arena/run → structured response (error/message/running)',
      r.status === 200 && hasExpected,
      `status=${r.status} keys=${Object.keys(obj).join(',')}`);
  } catch(e) { assert('T55: POST /api/arena/run response shape', false, e.message); }

  // T56: /api/arena/status has no unexpected 5xx
  try {
    const r = await httpGet('/api/arena/status');
    assert('T56: /api/arena/status no server error (not 5xx)',
      r.status < 500, `status=${r.status}`);
  } catch(e) { assert('T56: arena/status no 5xx', false, e.message); }

  // T57: /api/arena/results returns array or object, not null
  try {
    const r = await httpGet('/api/arena/results');
    const obj = JSON.parse(r.body);
    assert('T57: /api/arena/results is non-null JSON',
      obj !== null, `typeof=${typeof obj}`);
  } catch(e) { assert('T57: arena/results non-null', false, e.message); }

  // ══════════════════════════════════════════════════════════════
  // T58–T62: Doctor + status KB endpoints
  // ══════════════════════════════════════════════════════════════

  // T58: GET /api/doctor/status → 200 with last_run field
  try {
    const r = await httpGet('/api/doctor/status');
    const obj = JSON.parse(r.body);
    assert('T58: GET /api/doctor/status → has last_run field',
      r.status === 200 && 'last_run' in obj,
      `status=${r.status} keys=${Object.keys(obj).join(',')}`);
  } catch(e) { assert('T58: GET /api/doctor/status', false, e.message); }

  // T59: POST /api/status/achievement → 200
  try {
    const r = await httpPost('/api/status/achievement', JSON.stringify({
      hive: 'test-hive', agent: 'test-agent',
      description: 'T59 test achievement', evidence: 'automated test',
    }));
    const obj = JSON.parse(r.body);
    assert('T59: POST /api/status/achievement → 200 ok:true',
      r.status === 200 && obj.ok === true, `status=${r.status}`);
  } catch(e) { assert('T59: POST /api/status/achievement', false, e.message); }

  // T60: POST /api/status/blocker → 200 with id
  let blockerId = null;
  try {
    const r = await httpPost('/api/status/blocker', JSON.stringify({
      hive: 'test-hive', agent: 'test-agent',
      description: 'T60 test blocker', severity: 'low',
    }));
    const obj = JSON.parse(r.body);
    blockerId = obj.id;
    assert('T60: POST /api/status/blocker → 200 with id',
      r.status === 200 && !!obj.id, `status=${r.status} id=${obj.id}`);
  } catch(e) { assert('T60: POST /api/status/blocker', false, e.message); }

  // T61: POST /api/status/finding → 200
  try {
    const r = await httpPost('/api/status/finding', JSON.stringify({
      hive: 'test-hive', summary: 'T61 test finding', source: 'observation',
    }));
    const obj = JSON.parse(r.body);
    assert('T61: POST /api/status/finding → 200 ok:true',
      r.status === 200 && obj.ok === true, `status=${r.status}`);
  } catch(e) { assert('T61: POST /api/status/finding', false, e.message); }

  // T62: POST /api/status/next-step → 200 with id
  try {
    const r = await httpPost('/api/status/next-step', JSON.stringify({
      description: 'T62 test next step', assigned_to: 'hive-doctor',
      priority: 3, source: 'test',
    }));
    const obj = JSON.parse(r.body);
    assert('T62: POST /api/status/next-step → 200 with id',
      r.status === 200 && !!obj.id, `status=${r.status} id=${obj.id}`);
  } catch(e) { assert('T62: POST /api/status/next-step', false, e.message); }

  // ══════════════════════════════════════════════════════════════
  // T63–T67: UID registry + privacy
  // ══════════════════════════════════════════════════════════════

  // T63: GET /api/uid/registry → 200 JSON object
  try {
    const r = await httpGet('/api/uid/registry');
    const obj = JSON.parse(r.body);
    assert('T63: GET /api/uid/registry → 200 JSON object',
      r.status === 200 && typeof obj === 'object' && !Array.isArray(obj),
      `status=${r.status}`);
  } catch(e) { assert('T63: GET /api/uid/registry', false, e.message); }

  // T64: X-Hive-UID header on API call registers uid in /api/uid/registry
  const TEST_UID = 'test-uid-' + Date.now();
  try {
    // Trigger any API endpoint with the uid header
    await httpGet('/api/config', { 'X-Hive-UID': TEST_UID });
    await sleep(200);
    const r = await httpGet('/api/uid/registry');
    const reg = JSON.parse(r.body);
    assert('T64: X-Hive-UID header registers uid in registry',
      TEST_UID in reg, `registered=${TEST_UID in reg} keys=${Object.keys(reg).length}`);
  } catch(e) { assert('T64: uid registration via header', false, e.message); }

  // T65: Frontend HTML includes hive_uid localStorage key
  try {
    const r = await httpGet('/');
    assert('T65: Dashboard HTML includes hive_uid localStorage key',
      r.body.includes('hive_uid'), `found=${r.body.includes('hive_uid')}`);
  } catch(e) { assert('T65: hive_uid in HTML', false, e.message); }

  // T66: Frontend HTML includes X-Hive-UID fetch patch
  try {
    const r = await httpGet('/');
    assert("T66: Dashboard HTML includes X-Hive-UID fetch patch",
      r.body.includes('X-Hive-UID'), `found=${r.body.includes('X-Hive-UID')}`);
  } catch(e) { assert('T66: X-Hive-UID fetch patch in HTML', false, e.message); }

  // T67: GET /api/status/compact → 200 plain text (non-empty)
  try {
    const r = await httpGet('/api/status/compact');
    assert('T67: GET /api/status/compact → 200 non-empty plain text',
      r.status === 200 && r.body.length > 0,
      `status=${r.status} len=${r.body.length}`);
  } catch(e) { assert('T67: GET /api/status/compact', false, e.message); }

  // ══════════════════════════════════════════════════════════════
  // T68–T70: Visual / browser
  // ══════════════════════════════════════════════════════════════

  // T68: Chat section exists with correct id
  try {
    const page = await browser.newPage();
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 12000 });
    const chatEl = await page.$('#chat-section');
    assert('T68: #chat-section element exists in dashboard',
      chatEl !== null, `found=${chatEl !== null}`);
    await page.close();
  } catch(e) { assert('T68: #chat-section exists', false, e.message.split('\n')[0]); }

  // T69: Settings form has all required fields
  try {
    const page = await browser.newPage();
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 12000 });
    const ids = ['s-goal', 's-model', 's-dest', 's-instructions'];
    const missing = [];
    for (const id of ids) {
      const el = await page.$(`#${id}`);
      if (!el) missing.push(id);
    }
    assert('T69: Settings form has all required fields (goal/model/dest/instructions)',
      missing.length === 0, `missing=${missing.join(',') || 'none'}`);
    await page.close();
  } catch(e) { assert('T69: settings form fields', false, e.message.split('\n')[0]); }

  // T70: Queue section renders without horizontal overflow at 390px
  try {
    const page = await browser.newPage();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 12000 });
    await sleep(600);
    const queueEl = await page.$('#queue-section');
    const { scrollWidth, viewWidth } = await page.evaluate(() => ({
      scrollWidth: document.body.scrollWidth,
      viewWidth:   window.innerWidth,
    }));
    assert('T70: Queue section exists and no horizontal overflow at 390px',
      queueEl !== null && scrollWidth <= viewWidth + 5,
      `queueExists=${queueEl !== null} scrollW=${scrollWidth} viewW=${viewWidth}`);
    await page.close();
  } catch(e) { assert('T70: queue section 390px', false, e.message.split('\n')[0]); }

  // ── summary ───────────────────────────────────────────────────────────────
  await browser.close();

  console.log('\nPlaywright Test Results (T41–T70):');
  results.forEach(r => console.log(r));
  console.log(`\n${passed} passed, ${failed} failed out of ${passed + failed} tests`);

  if (failed > 0) {
    console.log('\nFailed tests above — fix before pushing branch.');
    process.exit(1);
  }
  process.exit(0);
})();
