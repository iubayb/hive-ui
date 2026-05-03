"""
api/index.py — Vercel entry point for the Hive public dashboard.

Deploy
------
1. Set Vercel secrets:
     vercel env add OPENROUTER_API_KEY   (your OpenRouter key)
     vercel env add OPENROUTER_MODEL     (e.g. qwen/qwen3-235b-a22b:free)

2. vercel deploy --prod  (run from the vercel-deploy/ directory)

Routing (vercel.json)
---------------------
  POST /api/chat  → api/chat.js  (Edge Function — streaming SSE)
  /*              → api/index.py (this file — Python handler)

vercel_hive.py lives in the parent vercel-deploy/ directory alongside api/.
"""
import sys, os
# vercel_hive.py is one level up from api/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vercel_hive import handler  # noqa: F401  (Vercel picks this up)
