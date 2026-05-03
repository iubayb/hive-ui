#!/usr/bin/env node
/**
 * Hive UI — ui_shared.py inheritance test suite (20 tests, TUI1–TUI20)
 *
 * Verifies that SHARED_CSS, LOCAL_CSS, SHARED_RENDER_JS, and LOCAL_STATUS_JS
 * from ui_shared.py are correctly injected into the served dashboard and behave
 * as expected in the browser.
 *
 * Run: PORT=8889 node tests/test_ui_inheritance.js
 */

const { chromium } = require('playwright');
const http  = require('http');

const BASE = 'http://127.0.0.1:8889';

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

  // ── fetch raw dashboard HTML once for static string checks ───────────────
  let dashHTML = '';
  try {
    const r = await httpGet('/');
    dashHTML = r.body;
  } catch(e) {
    console.error('FATAL: Could not fetch dashboard:', e.message);
    process.exit(1);
  }

  // ── browser page ─────────────────────────────────────────────────────────
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 800 });
  try {
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
  } catch(e) {
    console.error('FATAL: Could not load page:', e.message);
    process.exit(1);
  }
  await sleep(500);

  // ══════════════════════════════════════════════════════════════
  // Category 1: ui_shared.py exports present in served HTML (TUI1–TUI8)
  // ══════════════════════════════════════════════════════════════

  // TUI1: SHARED_CSS injected — :root{ present (CSS custom properties)
  assert('TUI1: SHARED_CSS injected — :root{ with CSS vars present',
    dashHTML.includes(':root{'), ':root{ not found in dashboard HTML');

  // TUI2: SHARED_CSS design tokens — --bg: token present
  assert('TUI2: SHARED_CSS design token --bg: present in HTML',
    dashHTML.includes('--bg:'), '--bg: not found');

  // TUI3: LOCAL_CSS injected — position:fixed present (input bar)
  assert('TUI3: LOCAL_CSS injected — position:fixed present in HTML',
    dashHTML.includes('position:fixed'), 'position:fixed not found');

  // TUI4: SHARED_RENDER_JS injected — function renderStatus present
  assert('TUI4: SHARED_RENDER_JS injected — function renderStatus present',
    dashHTML.includes('function renderStatus'), 'function renderStatus not found');

  // TUI5: LOCAL_STATUS_JS injected — function loadConfig present
  assert('TUI5: LOCAL_STATUS_JS injected — function loadConfig present',
    dashHTML.includes('function loadConfig'), 'function loadConfig not found');

  // TUI6: localStorage key hive_config_v2 present (from LOCAL_STATUS_JS)
  assert('TUI6: hive_config_v2 localStorage key present in HTML',
    dashHTML.includes('hive_config_v2'), 'hive_config_v2 not found');

  // TUI7: @keyframes pulse animation present (from SHARED_CSS)
  assert('TUI7: @keyframes pulse animation present in HTML',
    dashHTML.includes('@keyframes pulse'), '@keyframes pulse not found');

  // TUI8: safe-area-inset-bottom present (iOS insets, from SHARED_CSS)
  assert('TUI8: safe-area-inset-bottom present in HTML (iOS inset support)',
    dashHTML.includes('safe-area-inset-bottom'), 'safe-area-inset-bottom not found');

  // ══════════════════════════════════════════════════════════════
  // Category 2: Browser-level CSS behaviour (TUI9–TUI13)
  // ══════════════════════════════════════════════════════════════

  // TUI9: CSS var --bg resolves to a non-empty value
  const bgValue = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()
  );
  assert('TUI9: CSS var --bg resolves in browser', bgValue !== '',
    `got: "${bgValue}"`);

  // TUI10: CSS var --crit present and monochrome (hex value, no hue override)
  const critValue = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--crit').trim()
  );
  const isMono = critValue !== '' && /^#[0-9a-fA-F]{3,8}$/.test(critValue);
  assert('TUI10: CSS var --crit resolves as monochrome hex',
    isMono, `got: "${critValue}"`);

  // TUI11: .dot element has border-radius ≥ 50% (from SHARED_CSS)
  const dotBorderRadius = await page.$eval('#dot', el =>
    getComputedStyle(el).borderRadius
  ).catch(() => '');
  assert('TUI11: .dot element has border-radius 50% (rounded)',
    dotBorderRadius === '50%', `got: "${dotBorderRadius}"`);

  // TUI12: #status-bar (or .status-bar) exists and has non-default font-size (from SHARED_CSS)
  const statusBarFontSize = await page.$eval('#status-bar', el =>
    getComputedStyle(el).fontSize
  ).catch(() => '');
  const statusBarFs = parseFloat(statusBarFontSize);
  assert('TUI12: #status-bar has font-size from SHARED_CSS (≤ 12px)',
    statusBarFs > 0 && statusBarFs <= 12, `got: "${statusBarFontSize}"`);

  // TUI13: #prompt-input has min-height ≥ 44px (mobile tap target, from LOCAL_CSS)
  const inputMinH = await page.$eval('#prompt-input', el =>
    parseFloat(getComputedStyle(el).minHeight)
  ).catch(() => 0);
  assert('TUI13: #prompt-input min-height ≥ 44px (mobile tap target)',
    inputMinH >= 44, `got: ${inputMinH}px`);

  // ══════════════════════════════════════════════════════════════
  // Category 3: JS function availability in browser (TUI14–TUI16)
  // ══════════════════════════════════════════════════════════════

  // TUI14: renderStatus function exists on window (from SHARED_RENDER_JS)
  const hasRenderStatus = await page.evaluate(() =>
    typeof window.renderStatus === 'function'
  );
  assert('TUI14: window.renderStatus function exists (from SHARED_RENDER_JS)',
    hasRenderStatus, 'typeof window.renderStatus is not "function"');

  // TUI15: loadConfig function exists on window (from LOCAL_STATUS_JS)
  const hasLoadConfig = await page.evaluate(() =>
    typeof window.loadConfig === 'function'
  );
  assert('TUI15: window.loadConfig function exists (from LOCAL_STATUS_JS)',
    hasLoadConfig, 'typeof window.loadConfig is not "function"');

  // TUI16: resolveBlocker function exists on window (from SHARED_RENDER_JS)
  const hasResolveBlocker = await page.evaluate(() =>
    typeof window.resolveBlocker === 'function'
  );
  assert('TUI16: window.resolveBlocker function exists (from SHARED_RENDER_JS)',
    hasResolveBlocker, 'typeof window.resolveBlocker is not "function"');

  // ══════════════════════════════════════════════════════════════
  // Category 4: SSE and live-update wiring (TUI17–TUI18)
  // ══════════════════════════════════════════════════════════════

  // TUI17: /status/stream SSE delivers JSON with last_updated key
  const gotStatusSSE = await page.evaluate(async () => {
    return await new Promise(resolve => {
      const es = new EventSource('/status/stream');
      const t = setTimeout(() => { es.close(); resolve(null); }, 8000);
      es.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          clearTimeout(t);
          es.close();
          resolve('last_updated' in d ? 'ok' : 'missing_key');
        } catch(_) {
          clearTimeout(t);
          es.close();
          resolve('not_json');
        }
      };
      es.onerror = () => { clearTimeout(t); es.close(); resolve('error'); };
    });
  });
  assert('TUI17: /status/stream SSE delivers JSON with last_updated',
    gotStatusSSE === 'ok', `result: ${gotStatusSSE}`);

  // TUI18: Config uses hive_config_v2 key in localStorage
  // (Verify loadConfig() reads 'hive_config_v2', not an old key)
  const configKeyUsed = await page.evaluate(() => {
    // Set a value under hive_config_v2 and verify loadConfig() reads it
    const testVal = JSON.stringify({ model: 'test-model', favorites: [] });
    localStorage.setItem('hive_config_v2', testVal);
    try {
      const cfg = window.loadConfig();
      return cfg && cfg.model === 'test-model' ? 'ok' : 'wrong_value';
    } catch(e) {
      return 'error: ' + e.message;
    } finally {
      localStorage.removeItem('hive_config_v2');
    }
  });
  assert('TUI18: loadConfig() reads from hive_config_v2 localStorage key',
    configKeyUsed === 'ok', `got: ${configKeyUsed}`);

  // ══════════════════════════════════════════════════════════════
  // Category 5: Mobile/responsive from SHARED_CSS + LOCAL_CSS (TUI19–TUI20)
  // ══════════════════════════════════════════════════════════════

  // TUI19: #input-bar has position: fixed in browser (from LOCAL_CSS)
  const inputBarPos = await page.$eval('#input-bar', el =>
    getComputedStyle(el).position
  ).catch(() => '');
  assert('TUI19: #input-bar has position: fixed (from LOCAL_CSS)',
    inputBarPos === 'fixed', `got: "${inputBarPos}"`);

  // TUI20: #main has padding-bottom > 0 (makes room for fixed input bar)
  const mob = await browser.newPage();
  await mob.setViewportSize({ width: 390, height: 844 });
  await mob.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 12000 });
  await sleep(500);
  const mainPaddingBottom = await mob.evaluate(() => {
    const el = document.querySelector('#main');
    return el ? parseFloat(getComputedStyle(el).paddingBottom) : 0;
  });
  assert('TUI20: #main has padding-bottom > 0 at 390px (input bar clearance)',
    mainPaddingBottom > 0, `got: ${mainPaddingBottom}px`);
  await mob.close();

  // ── results ───────────────────────────────────────────────────────────────
  await browser.close();
  console.log('\nUI Inheritance Test Results:');
  results.forEach(r => console.log(r));
  console.log(`\n${passed} passed, ${failed} failed out of ${passed + failed} tests`);
  if (failed > 0) console.log('\nFailed tests above — fix before pushing branch.');
  process.exit(failed > 0 ? 1 : 0);
})();
