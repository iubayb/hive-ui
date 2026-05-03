/**
 * api/chat.js — Vercel Edge Function for streaming OpenRouter chat.
 *
 * Route: POST /api/chat
 * Body:  { message: string, history?: [{role,content}], model?: string }
 *
 * Reads OPENROUTER_API_KEY and OPENROUTER_MODEL from process.env.
 * Pipes the OpenRouter SSE stream directly back to the browser — zero buffering.
 * No timeout (Edge Functions have no 60 s cap unlike serverless).
 */

export const config = { runtime: 'edge' };

const DEFAULT_MODEL = 'qwen/qwen3-235b-a22b:free';
const OR_BASE       = 'https://openrouter.ai/api/v1/chat/completions';

const CORS = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

export default async function handler(req) {
  // Pre-flight
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: CORS });
  }

  if (req.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405, headers: CORS });
  }

  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    return new Response(
      JSON.stringify({ error: 'OPENROUTER_API_KEY not configured' }),
      { status: 500, headers: { ...CORS, 'Content-Type': 'application/json' } }
    );
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(
      JSON.stringify({ error: 'invalid JSON body' }),
      { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } }
    );
  }

  const { message, history = [], model } = body;
  if (!message || typeof message !== 'string') {
    return new Response(
      JSON.stringify({ error: 'message field required' }),
      { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } }
    );
  }

  const useModel   = (model && model.trim()) || process.env.OPENROUTER_MODEL || DEFAULT_MODEL;
  const messages   = [...history, { role: 'user', content: message }];
  const referer    = req.headers.get('origin') || 'https://hive-public.vercel.app';

  const upstream = await fetch(OR_BASE, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type':  'application/json',
      'HTTP-Referer':  referer,
      'X-Title':       'Hive Public',
    },
    body: JSON.stringify({ model: useModel, messages, stream: true }),
  });

  if (!upstream.ok) {
    const errText = await upstream.text();
    return new Response(
      JSON.stringify({ error: `upstream ${upstream.status}`, detail: errText }),
      { status: upstream.status, headers: { ...CORS, 'Content-Type': 'application/json' } }
    );
  }

  // Pipe SSE stream straight through — no buffering
  return new Response(upstream.body, {
    status: 200,
    headers: {
      ...CORS,
      'Content-Type':    'text/event-stream; charset=utf-8',
      'Cache-Control':   'no-cache, no-transform',
      'X-Accel-Buffering': 'no',
    },
  });
}
