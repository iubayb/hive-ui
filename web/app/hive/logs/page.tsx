"use client";

import { useEffect, useRef, useState } from "react";

const MAX_LINES = 500;

function lineColor(text: string): string {
  const t = text.toLowerCase();
  if (t.includes("error") || t.includes("fail") || t.includes("exception"))
    return "#f87171"; // red-400
  if (t.includes("warn")) return "#fbbf24"; // amber-400
  if (t.includes("ok") || t.includes("success") || t.includes("done"))
    return "#4ade80"; // green-400
  return "#a1a1aa"; // zinc-400
}

export default function LogsPage() {
  const [lines, setLines] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource("/api/logs");

    es.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        const combined: string[] = parsed.combined ?? [];
        if (combined.length === 0) return;
        setLines((prev) => {
          const next = [...prev, ...combined];
          return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
        });
      } catch {
        // ignore parse errors
      }
    };

    return () => es.close();
  }, []);

  // Auto-scroll to bottom on new lines
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <header
        className="sticky top-0 z-40 px-4 py-3 flex items-center gap-2 border-b"
        style={{
          background: "rgba(9,9,11,0.95)",
          borderColor: "var(--color-border)",
          backdropFilter: "blur(16px)",
        }}
      >
        <span className="text-lg">⊟</span>
        <span className="font-display font-semibold text-sm">Logs</span>
        <span
          className="ml-auto text-xs font-mono"
          style={{ color: "var(--color-text-muted)" }}
        >
          {lines.length} lines
        </span>
      </header>

      <main className="px-4 py-4 max-w-lg mx-auto">
        <div
          className="rounded-lg border p-3 overflow-y-auto"
          style={{
            background: "#09090b",
            borderColor: "var(--color-border)",
            height: "calc(100dvh - 130px)",
            fontFamily: "var(--font-mono, monospace)",
            fontSize: "11px",
            lineHeight: "1.6",
          }}
        >
          {lines.length === 0 ? (
            <p style={{ color: "var(--color-text-muted)" }}>
              Waiting for log stream…
            </p>
          ) : (
            lines.map((line, i) => (
              <div key={i} style={{ color: lineColor(line) }}>
                {line}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </main>
    </div>
  );
}
