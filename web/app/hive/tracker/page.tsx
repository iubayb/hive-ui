"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";

interface Researcher {
  handle: string;
  platform: string;
  keywords?: string[];
  priority_repos?: string[];
}

const PLATFORMS = ["github", "twitter", "arxiv", "linkedin"];

export default function TrackerPage() {
  const [researchers, setResearchers] = useState<Researcher[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [handle, setHandle] = useState("");
  const [platform, setPlatform] = useState("github");
  const [keywords, setKeywords] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function fetchResearchers() {
    try {
      const res = await fetch("/api/tracker");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResearchers(Array.isArray(data) ? data : data.researchers ?? []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchResearchers(); }, []);

  async function handleTrack(e: React.FormEvent) {
    e.preventDefault();
    if (!handle.trim()) return;
    setSubmitting(true);
    try {
      const payload: Researcher = {
        handle: handle.trim(),
        platform,
        keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
      };
      const res = await fetch("/api/tracker", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setHandle("");
      setKeywords("");
      await fetchResearchers();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemove(r: Researcher) {
    try {
      const res = await fetch("/api/tracker", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handle: r.handle, platform: r.platform }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchResearchers();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <PageHeader icon="⊛" title="Researcher Tracker" />
      <main className="px-4 py-4 max-w-lg mx-auto space-y-4 pb-20">
        {/* Add researcher form */}
        <div className="glass-card p-4 space-y-3">
          <span className="section-title">Track Researcher</span>
          <form onSubmit={handleTrack} className="space-y-2 mt-2">
            <div className="flex gap-2">
              <input
                type="text"
                value={handle}
                onChange={(e) => setHandle(e.target.value)}
                placeholder="Handle / username"
                className="flex-1 rounded-md px-3 py-2 text-xs font-mono border"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  borderColor: "var(--color-border)",
                  color: "var(--color-text-primary)",
                }}
                required
              />
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="rounded-md px-2 py-2 text-xs border"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  borderColor: "var(--color-border)",
                  color: "var(--color-text-secondary)",
                }}
              >
                {PLATFORMS.map((p) => (
                  <option key={p} value={p} style={{ background: "#09090b" }}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="Keywords (comma-separated)"
              className="w-full rounded-md px-3 py-2 text-xs font-mono border"
              style={{
                background: "rgba(255,255,255,0.04)",
                borderColor: "var(--color-border)",
                color: "var(--color-text-primary)",
              }}
            />
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-md py-2 text-xs font-semibold transition-opacity disabled:opacity-50"
              style={{
                background: "rgba(0,220,130,0.15)",
                color: "var(--color-brand)",
                border: "1px solid rgba(0,220,130,0.3)",
              }}
            >
              {submitting ? "Tracking…" : "Track"}
            </button>
          </form>
        </div>

        {error && (
          <div className="glass-card p-3 text-xs" style={{ color: "#f87171", borderColor: "rgba(248,113,113,0.2)" }}>
            {error}
          </div>
        )}

        <div className="glass-card p-4 space-y-2">
          <span className="section-title">Tracked Researchers</span>
          {loading ? (
            <p className="text-xs mt-2" style={{ color: "var(--color-text-muted)" }}>Loading…</p>
          ) : researchers.length === 0 ? (
            <p className="text-xs mt-2" style={{ color: "var(--color-text-muted)" }}>No researchers tracked yet.</p>
          ) : (
            <ul className="space-y-2 mt-2">
              {researchers.map((r) => (
                <li
                  key={`${r.platform}:${r.handle}`}
                  className="flex items-start justify-between gap-2 rounded-md px-3 py-2"
                  style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--color-border)" }}
                >
                  <div className="min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-semibold truncate" style={{ color: "var(--color-text-primary)" }}>
                        {r.handle}
                      </span>
                      <span
                        className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium"
                        style={{ background: "rgba(0,220,130,0.1)", color: "var(--color-brand)" }}
                      >
                        {r.platform}
                      </span>
                    </div>
                    {r.keywords && r.keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {r.keywords.map((k) => (
                          <span
                            key={k}
                            className="px-1 py-0.5 rounded text-[10px] font-mono"
                            style={{ background: "rgba(255,255,255,0.05)", color: "var(--color-text-muted)" }}
                          >
                            {k}
                          </span>
                        ))}
                      </div>
                    )}
                    {r.priority_repos && r.priority_repos.length > 0 && (
                      <p className="text-[10px] font-mono truncate" style={{ color: "var(--color-text-muted)" }}>
                        repos: {r.priority_repos.join(", ")}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => handleRemove(r)}
                    className="shrink-0 text-[10px] px-2 py-1 rounded transition-opacity hover:opacity-80"
                    style={{
                      background: "rgba(248,113,113,0.1)",
                      color: "#f87171",
                      border: "1px solid rgba(248,113,113,0.2)",
                    }}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
