#!/usr/bin/env node
/**
 * local_dev_server.js — Local mock Vercel router for testing without `vercel login`.
 *
 * Mimics the Vercel routing defined in vercel.json:
 *   POST /api/chat  → runs api/chat.js Edge Function logic natively in Node.js
 *   OPTIONS /api/chat → CORS preflight via chat.js
 *   GET /api/chat   → 405 (method not allowed from Edge Function)
 *   everything else → proxied to Python standalone server on port 8091
 *
 * Usage: node tests/local_dev_server.js
 * Env:   OPENROUTER_API_KEY, OPENROUTER_MODEL (read from .env.local automatically)
 */

'use strict';

const http    = require('http');
const https   = require('https');
const path    = require('path');
const fs      = require('fs');
const { spawn } = require('child_process');

const MOCK_PORT   = 3001;
const PYTHON_PORT = 8092;
const ROOT        = path.join(__dirname, '..');

// ── load .env.local ───────────────────────────────────────────────────────────
const envLocal = path.join(ROOT, '.env.local');
if (fs.existsSync(envLocal)) {
  for (const line of fs.readFileSync(envLocal, 'utf8').split('\n')) {
    const [k, ...rest] = line.split('=');
    if (k && rest.length) process.env[k.trim()] = rest.join('=').trim();
  }
}

const API_KEY      = process.env.OPENROUTER_API_KEY || '';
const MODEL        = process.env.OPENROUTER_MODEL || 'openai/gpt-oss-120b:free';
const OR_URL       = 'https://openrouter.ai/api/v1/chat/completions';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

// ── Edge Function logic (mirrors api/chat.js) ─────────────────────────────────
async function handleChat(req, res) {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, CORS_HEADERS);
    return res.end();
  }
  if (req.method !== 'POST') {
    res.writeHead(405, CORS_HEADERS);
    return res.end(JSON.stringify({ error: 'Method Not Allowed' }));
  }

  let body = '';
  for await (const chunk of req) body += chunk;

  let parsed;
  try { parsed = JSON.parse(body); }
  catch { res.writeHead(400, { ...CORS_HEADERS, 'Content-Type': 'application/json' }); return res.end(JSON.stringify({ error: 'invalid JSON body' })); }

  const { message, history = [], model } = parsed;
  if (!message || typeof message !== 'string') {
    res.writeHead(400, { ...CORS_HEADERS, 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ error: 'message field required' }));
  }

  if (!API_KEY) {
    res.writeHead(500, { ...CORS_HEADERS, 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ error: 'OPENROUTER_API_KEY not configured' }));
  }

  const useModel   = (model && model.trim()) || MODEL;
  const messages   = [...history, { role: 'user', content: message }];
  const payload    = JSON.stringify({ model: useModel, messages, stream: true });

  const orReq = https.request(OR_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type':  'application/json',
      'HTTP-Referer':  'http://localhost:3001',
      'X-Title':       'Hive Dev',
    },
  }, orRes => {
    if (!orRes.statusCode || orRes.statusCode >= 300) {
      let errBody = '';
      orRes.on('data', c => errBody += c);
      orRes.on('end', () => {
        res.writeHead(orRes.statusCode, { ...CORS_HEADERS, 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: `upstream ${orRes.statusCode}`, detail: errBody }));
      });
      return;
    }
    res.writeHead(200, {
      ...CORS_HEADERS,
      'Content-Type':      'text/event-stream; charset=utf-8',
      'Cache-Control':     'no-cache, no-transform',
      'X-Accel-Buffering': 'no',
    });
    orRes.pipe(res);
  });
  orReq.on('error', e => {
    if (!res.headersSent) {
      res.writeHead(502, { ...CORS_HEADERS, 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
  });
  orReq.write(payload);
  orReq.end();
}

// ── Python proxy (everything except /api/chat) ────────────────────────────────
function proxyToPython(req, res) {
  const opts = {
    hostname: '127.0.0.1',
    port: PYTHON_PORT,
    path: req.url,
    method: req.method,
    headers: req.headers,
  };
  const proxy = http.request(opts, pyRes => {
    res.writeHead(pyRes.statusCode, pyRes.headers);
    pyRes.pipe(res);
  });
  proxy.on('error', () => { res.writeHead(502); res.end('python unavailable'); });
  req.pipe(proxy);
}

// ── router ────────────────────────────────────────────────────────────────────
const server = http.createServer((req, res) => {
  const urlPath = req.url.split('?')[0];
  if (urlPath === '/api/chat') return handleChat(req, res);
  proxyToPython(req, res);
});

// ── start Python standalone on PYTHON_PORT ────────────────────────────────────
const pyScript = path.join(ROOT, 'vercel_hive.py');
const pyEnv    = { ...process.env, PORT: String(PYTHON_PORT) };
delete pyEnv.HIVE_BACKEND_URL;
const pySrv = spawn('python3', [pyScript], { env: pyEnv, stdio: 'ignore' });
pySrv.on('error', e => { console.error('Python start error:', e.message); process.exit(1); });

// Wait for Python to be ready then start the mock server
function waitPython(ms = 8000) {
  const start = Date.now();
  return new Promise((res, rej) => {
    const try_ = () => {
      http.get(`http://127.0.0.1:${PYTHON_PORT}/api/status`, r => { r.resume(); res(); })
        .on('error', () => {
          if (Date.now() - start > ms) return rej(new Error('Python never ready'));
          setTimeout(try_, 200);
        });
    };
    try_();
  });
}

waitPython().then(() => {
  server.listen(MOCK_PORT, '127.0.0.1', () => {
    process.send && process.send('ready');
    process.stdout.write(`mock-vercel ready on http://127.0.0.1:${MOCK_PORT}\n`);
  });
}).catch(e => { console.error(e.message); process.exit(1); });

process.on('exit', () => pySrv.kill());
process.on('SIGTERM', () => { pySrv.kill(); process.exit(0); });
process.on('SIGINT',  () => { pySrv.kill(); process.exit(0); });
