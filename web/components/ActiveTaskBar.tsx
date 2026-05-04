"use client";

import { useHiveStore } from "@/store/useHiveStore";
import { useEffect, useState } from "react";

function useElapsed(startedAt: string | undefined): string {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(id);
  }, []);

  if (!startedAt) return "";
  const ms = now - new Date(startedAt).getTime();
  if (ms < 0) return "00:00";
  const totalMinutes = Math.floor(ms / 60_000);
  const hh = String(Math.floor(totalMinutes / 60)).padStart(2, "0");
  const mm = String(totalMinutes % 60).padStart(2, "0");
  return `${hh}:${mm}`;
}

type DotState = "ok" | "stale" | "hang";

function getDotState(startedAt: string | undefined, isActive: boolean): DotState {
  if (!isActive || !startedAt) return "ok";
  const ms = Date.now() - new Date(startedAt).getTime();
  const minutes = ms / 60_000;
  if (minutes > 15) return "hang";
  if (minutes > 5) return "stale";
  return "ok";
}

const DOT_COLOR: Record<DotState, string> = {
  ok:    "#00DC82",
  stale: "#F59E0B",
  hang:  "#EF4444",
};

export function ActiveTaskBar() {
  const hiveStatus = useHiveStore((s) => s.hiveStatus);

  // active_task in the store is a plain string like "[agent] description"
  // We try to parse "[agent]" prefix; fall back gracefully.
  const rawTask = hiveStatus?.active_task ?? "";
  const isActive = Boolean(rawTask);

  const agentMatch = rawTask.match(/^\[([^\]]+)\]/);
  const agent = agentMatch ? agentMatch[1] : null;
  const description = agentMatch
    ? rawTask.slice(agentMatch[0].length).trim()
    : rawTask;
  const truncated =
    description.length > 80 ? description.slice(0, 80) + "…" : description;

  // started_at isn't in HiveStatus; we approximate by tracking when active_task last changed.
  const [startedAt, setStartedAt] = useState<string | undefined>(undefined);
  const [prevTask, setPrevTask] = useState<string>("");

  useEffect(() => {
    if (rawTask !== prevTask) {
      setPrevTask(rawTask);
      setStartedAt(rawTask ? new Date().toISOString() : undefined);
    }
  }, [rawTask, prevTask]);

  const elapsed = useElapsed(startedAt);
  const dotState = getDotState(startedAt, isActive);
  const dotColor = DOT_COLOR[dotState];

  return (
    <div
      className="fixed top-0 left-0 right-0 z-40 flex items-center gap-2 px-3"
      style={{
        height: "36px",
        background: "#0a0a0a",
        borderBottom: "1px solid #272727",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: "12px",
      }}
    >
      {/* Status dot */}
      <span
        className="shrink-0 rounded-full"
        style={{
          width: 8,
          height: 8,
          background: dotColor,
          boxShadow: isActive ? `0 0 6px 1px ${dotColor}` : "none",
          animation: isActive && dotState === "ok" ? "pulse 2s infinite" : "none",
        }}
      />

      {/* Agent badge */}
      {agent && (
        <span
          className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold"
          style={{
            background: "rgba(0,220,130,0.1)",
            color: "#00DC82",
            border: "1px solid rgba(0,220,130,0.2)",
          }}
        >
          {agent}
        </span>
      )}

      {/* Task description */}
      <span
        className="flex-1 truncate"
        style={{
          color: isActive
            ? dotState === "hang"
              ? "#EF4444"
              : dotState === "stale"
              ? "#F59E0B"
              : "var(--color-text-primary)"
            : "var(--color-text-muted)",
        }}
      >
        {isActive ? truncated : "idle"}
      </span>

      {/* Elapsed time */}
      {isActive && elapsed && (
        <span className="shrink-0" style={{ color: "var(--color-text-muted)" }}>
          {elapsed}
        </span>
      )}
    </div>
  );
}
