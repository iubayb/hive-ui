"use client";

import { useState, useEffect } from "react";

// Extended status shape with knowledge/capabilities
interface Finding {
  source?: string;
  summary?: string;
  timestamp?: string;
  [key: string]: unknown;
}

interface Solution {
  problem?: string;
  solution?: string;
  verified?: boolean;
  [key: string]: unknown;
}

interface Capability {
  name?: string;
  description?: string;
  tags?: string[];
  example?: string;
  [key: string]: unknown;
}

interface FullStatus {
  knowledge?: {
    findings?: Finding[];
    solutions?: Solution[];
  };
  capabilities?: {
    learned?: Capability[];
  };
  [key: string]: unknown;
}

type Tab = "findings" | "solutions" | "capabilities";

function EmptyState({ label }: { label: string }) {
  return (
    <p
      className="text-center py-12 text-sm"
      style={{ color: "var(--color-text-muted)" }}
    >
      No {label} yet.
    </p>
  );
}

export default function KnowledgePage() {
  const [status, setStatus] = useState<FullStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("findings");

  useEffect(() => {
    fetch("/api/status")
      .then((r) => r.json())
      .then((d) => {
        setStatus(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const findings = status?.knowledge?.findings ?? [];
  const solutions = status?.knowledge?.solutions ?? [];
  const capabilities = status?.capabilities?.learned ?? [];

  const TABS: { id: Tab; label: string; count: number }[] = [
    { id: "findings",     label: "Findings",     count: findings.length },
    { id: "solutions",    label: "Solutions",     count: solutions.length },
    { id: "capabilities", label: "Capabilities",  count: capabilities.length },
  ];

  return (
    <div className="px-4 py-5 max-w-lg mx-auto">
      <h1
        className="text-lg font-semibold mb-4"
        style={{ color: "var(--color-text-primary)" }}
      >
        Knowledge Base
      </h1>

      {/* Tabs */}
      <div
        className="flex gap-1 rounded-xl p-1 mb-5"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--color-border)" }}
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex-1 rounded-lg py-1.5 text-xs font-medium transition-colors"
            style={{
              background: tab === t.id ? "rgba(255,255,255,0.08)" : "transparent",
              color: tab === t.id ? "var(--color-text-primary)" : "var(--color-text-muted)",
              cursor: "pointer",
              border: "none",
            }}
          >
            {t.label}
            {t.count > 0 && (
              <span
                className="ml-1.5 rounded-full px-1.5 py-px text-[10px]"
                style={{
                  background: tab === t.id ? "var(--color-brand-muted)" : "rgba(255,255,255,0.06)",
                  color: tab === t.id ? "var(--color-brand)" : "var(--color-text-muted)",
                }}
              >
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <p style={{ color: "var(--color-text-muted)", fontSize: 14 }}>Loading…</p>
      ) : (
        <>
          {/* Findings */}
          {tab === "findings" && (
            <div className="flex flex-col gap-2">
              {findings.length === 0 ? (
                <EmptyState label="findings" />
              ) : (
                findings.map((f, i) => (
                  <div key={i} className="glass-card px-4 py-3">
                    <div className="flex items-center gap-2 mb-1">
                      {f.source && (
                        <span
                          className="text-[10px] font-semibold rounded px-1.5 py-0.5"
                          style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            background: "rgba(255,255,255,0.06)",
                            color: "var(--color-text-secondary)",
                          }}
                        >
                          {String(f.source)}
                        </span>
                      )}
                      {f.timestamp && (
                        <span
                          className="text-[10px] ml-auto"
                          style={{ color: "var(--color-text-muted)", fontFamily: "'JetBrains Mono', monospace" }}
                        >
                          {new Date(String(f.timestamp)).toLocaleString()}
                        </span>
                      )}
                    </div>
                    <p className="text-sm" style={{ color: "var(--color-text-primary)" }}>
                      {f.summary ? String(f.summary) : JSON.stringify(f)}
                    </p>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Solutions */}
          {tab === "solutions" && (
            <div className="flex flex-col gap-2">
              {solutions.length === 0 ? (
                <EmptyState label="solutions" />
              ) : (
                solutions.map((s, i) => (
                  <div key={i} className="glass-card px-4 py-3">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <p
                        className="text-sm font-semibold"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        {s.problem ? String(s.problem) : "Problem"}
                      </p>
                      {s.verified && (
                        <span
                          className="shrink-0 text-[10px] rounded-full px-2 py-0.5"
                          style={{
                            background: "rgba(0,220,130,0.1)",
                            color: "var(--color-brand)",
                            border: "1px solid rgba(0,220,130,0.2)",
                          }}
                        >
                          verified
                        </span>
                      )}
                    </div>
                    {s.solution && (
                      <p
                        className="text-xs rounded px-2 py-1.5"
                        style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          background: "rgba(255,255,255,0.03)",
                          color: "var(--color-text-secondary)",
                          border: "1px solid var(--color-border)",
                          wordBreak: "break-word",
                        }}
                      >
                        {String(s.solution)}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* Capabilities */}
          {tab === "capabilities" && (
            <div className="flex flex-col gap-2">
              {capabilities.length === 0 ? (
                <EmptyState label="capabilities" />
              ) : (
                capabilities.map((c, i) => (
                  <div key={i} className="glass-card px-4 py-3">
                    <p
                      className="text-sm font-semibold mb-1"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {c.name ? String(c.name) : `Capability ${i + 1}`}
                    </p>
                    {c.description && (
                      <p
                        className="text-xs mb-2"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        {String(c.description)}
                      </p>
                    )}
                    {Array.isArray(c.tags) && c.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {c.tags.map((tag, ti) => (
                          <span
                            key={ti}
                            className="text-[10px] rounded-full px-2 py-0.5"
                            style={{
                              background: "rgba(255,255,255,0.06)",
                              color: "var(--color-text-muted)",
                              border: "1px solid var(--color-border)",
                            }}
                          >
                            {String(tag)}
                          </span>
                        ))}
                      </div>
                    )}
                    {c.example && (
                      <p
                        className="text-[10px] rounded px-2 py-1"
                        style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          background: "rgba(255,255,255,0.03)",
                          color: "var(--color-text-muted)",
                          border: "1px solid var(--color-border)",
                          wordBreak: "break-all",
                        }}
                      >
                        {String(c.example)}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
