"use client";

import { useState, useEffect, useCallback, useRef } from "react";

interface ArenaStatus {
  running?: boolean;
  champion?: string;
  last_run?: string;
}

interface ModelResult {
  model: string;
  score: number;
}

interface ArenaResults {
  results?: ModelResult[];
}

export function ModelArena() {
  const [status, setStatus] = useState<ArenaStatus | null>(null);
  const [results, setResults] = useState<ArenaResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [sRes, rRes] = await Promise.all([
        fetch("/api/arena/status"),
        fetch("/api/arena/results"),
      ]);
      if (sRes.ok) setStatus(await sRes.json());
      if (rRes.ok) setResults(await rRes.json());
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Poll every 5s while running
  useEffect(() => {
    if (status?.running) {
      pollRef.current = setInterval(fetchAll, 5_000);
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [status?.running, fetchAll]);

  async function runBenchmark() {
    setTriggering(true);
    try {
      const res = await fetch("/api/arena/run", { method: "POST" });
      if (res.ok) {
        setStatus((s) => ({ ...s, running: true }));
      }
    } catch {}
    finally { setTriggering(false); }
  }

  if (loading) {
    return (
      <div className="glass-card p-4 text-center text-xs" style={{ color: "var(--color-text-muted)" }}>
        Loading arena…
      </div>
    );
  }

  const topModels: ModelResult[] = (results?.results ?? [])
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);

  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="section-title">Model Arena</span>
        {status?.running ? (
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{
              background: "rgba(245,158,11,0.1)",
              color: "#F59E0B",
              border: "1px solid rgba(245,158,11,0.3)",
            }}
          >
            ◌ Running…
          </span>
        ) : (
          <button
            onClick={runBenchmark}
            disabled={triggering}
            className="text-xs px-2.5 py-1 rounded-lg transition-all"
            style={{
              background: "var(--color-glass)",
              color: "var(--color-text-secondary)",
              border: "1px solid var(--color-border)",
            }}
          >
            {triggering ? "Starting…" : "Run benchmark"}
          </button>
        )}
      </div>

      {!topModels.length && !status?.champion ? (
        <p className="text-xs text-center py-2" style={{ color: "var(--color-text-muted)" }}>
          No runs yet — start a benchmark to compare models.
        </p>
      ) : (
        <div className="space-y-2">
          {status?.champion && (
            <div className="flex items-center gap-2 text-xs">
              <span style={{ color: "var(--color-text-muted)" }}>Champion:</span>
              <span
                className="font-mono font-medium"
                style={{ color: "var(--color-brand)" }}
              >
                {status.champion}
              </span>
            </div>
          )}
          {status?.last_run && (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Last run:{" "}
              <span style={{ color: "var(--color-text-secondary)" }}>
                {new Date(status.last_run).toLocaleString()}
              </span>
            </p>
          )}
          {topModels.length > 0 && (
            <ul className="space-y-1.5 mt-1">
              {topModels.map((m, i) => (
                <li key={m.model} className="flex items-center gap-2 text-xs">
                  <span
                    className="shrink-0 w-4 text-center font-mono"
                    style={{ color: i === 0 ? "var(--color-brand)" : "var(--color-text-muted)" }}
                  >
                    {i + 1}
                  </span>
                  <span
                    className="flex-1 font-mono truncate"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    {m.model}
                  </span>
                  <span
                    className="font-mono"
                    style={{ color: i === 0 ? "var(--color-brand)" : "var(--color-text-muted)" }}
                  >
                    {m.score.toFixed(2)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
