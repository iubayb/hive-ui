# Hive Status Data Bus

This orphan branch holds live hive state pushed by the Oracle ARM server every 60 seconds.

- `hive-status.json` — full hive status (health, sessions, blockers, capabilities)
- `logs.jsonl` — recent log stream

Consumed by Vercel Edge SSE route (`/api/stream`) polling raw GitHub URL every 5s.
