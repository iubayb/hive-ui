"use client";

import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/PageHeader";

const MAX_LINES = 500;

function lineColor(text: string): string {
  const t = String(text).toLowerCase();
  if (t.includes("error") || t.includes("fail") || t.includes("exception")) return "#f87171";
  if (t.includes("warn")) return "#fbbf24";
  if (t.includes("ok") || t.includes("success") || t.includes("done")) return "#4ade80";
  return "var(--color-text-secondary)";
}

export default function LogsPage() {
  const [lines, setLines] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource("/api/logs");
    es.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        const raw: unknown[] = parsed.combined ?? [];
        // Backend may return LogEntry objects {session,line,ts} or plain strings
        const combined: string[] = raw.map((e) =>
          typeof e === "string" ? e : (e as { line?: string }).line ?? String(e)
        );
        if (combined.length === 0) return;
        setLines((prev) => {
          const next = [...prev, ...combined];
          return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
        });
      } catch {}
    };
    return () => es.close();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <PageHeader
        icon="⊟"
        title="Logs"
        right={
          <span className="text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
            {lines.length} lines
          </span>
        }
      />
      <main className="px-4 py-4 max-w-lg mx-auto">
        <div
          className="rounded-lg border p-3 overflow-y-auto"
          style={{
            background: "#09090b",
            borderColor: "var(--color-border)",
            height: "calc(100dvh - 170px)",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: "11px",
            lineHeight: "1.6",
          }}
        >
          {lines.length === 0 ? (
            <p style={{ color: "var(--color-text-muted)" }}>Waiting for log stream…</p>
          ) : (
            lines.map((line, i) => (
              <div key={i} style={{ color: lineColor(line) }}>{line}</div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </main>
    </div>
  );
}
