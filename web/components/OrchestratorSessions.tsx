"use client";

import { useState } from "react";
import type { OrchestratorSession } from "@/store/useHiveStore";

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

function SessionCard({ session }: { session: OrchestratorSession }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: "var(--color-border)" }}
    >
      {/* Header row — always visible */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start gap-2 px-3 py-2.5 text-left transition-colors hover:bg-white/[0.02]"
      >
        <span
          className="mt-0.5 text-xs shrink-0 transition-transform"
          style={{
            color: "var(--color-text-muted)",
            transform: expanded ? "rotate(90deg)" : "none",
          }}
        >
          ▶
        </span>
        <div className="min-w-0 flex-1">
          <p
            className="text-xs truncate"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {session.summary}
          </p>
          <p
            className="text-[10px] font-mono mt-0.5"
            style={{ color: "var(--color-text-muted)" }}
          >
            {formatTs(session.ts)}
          </p>
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div
          className="px-3 pb-3 space-y-2 border-t"
          style={{ borderColor: "var(--color-border)" }}
        >
          {session.goal && (
            <div className="pt-2">
              <p
                className="text-[10px] font-semibold uppercase tracking-wider mb-0.5"
                style={{ color: "var(--color-text-muted)" }}
              >
                Goal
              </p>
              <p
                className="text-xs"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {session.goal}
              </p>
            </div>
          )}
          {session.progress && (
            <div>
              <p
                className="text-[10px] font-semibold uppercase tracking-wider mb-0.5"
                style={{ color: "var(--color-text-muted)" }}
              >
                Progress
              </p>
              <p
                className="text-xs"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {session.progress}
              </p>
            </div>
          )}
          {session.next_steps && session.next_steps.length > 0 && (
            <div>
              <p
                className="text-[10px] font-semibold uppercase tracking-wider mb-0.5"
                style={{ color: "var(--color-text-muted)" }}
              >
                Next Steps
              </p>
              <ul className="space-y-0.5">
                {session.next_steps.map((s, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-1.5 text-xs"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    <span style={{ color: "var(--color-brand)" }}>→</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {session.decisions && session.decisions.length > 0 && (
            <div>
              <p
                className="text-[10px] font-semibold uppercase tracking-wider mb-0.5"
                style={{ color: "var(--color-text-muted)" }}
              >
                Key Decisions
              </p>
              <ul className="space-y-0.5">
                {session.decisions.map((d, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-1.5 text-xs"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    <span style={{ color: "#fbbf24" }}>◆</span>
                    {d}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function OrchestratorSessions({
  sessions,
}: {
  sessions?: OrchestratorSession[];
}) {
  if (!sessions || sessions.length === 0) return null;

  const recent = [...sessions]
    .sort((a, b) => (b.ts > a.ts ? 1 : -1))
    .slice(0, 3);

  return (
    <div className="glass-card p-4 space-y-2">
      <span className="section-title">Orchestrator Sessions</span>
      <div className="space-y-1.5 mt-2">
        {recent.map((s, i) => (
          <SessionCard key={i} session={s} />
        ))}
      </div>
    </div>
  );
}
