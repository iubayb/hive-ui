"use client";

import { useEffect } from "react";
import { useHiveStore, type HiveStatus } from "@/store/useHiveStore";
import { HiveStatusCard } from "@/components/HiveStatusCard";
import { SessionGrid } from "@/components/SessionGrid";
import { BlockerList } from "@/components/BlockerList";
import { QuestionsList } from "@/components/QuestionsList";
import { DoctorStatus } from "@/components/DoctorStatus";
import { OrchestratorSessions } from "@/components/OrchestratorSessions";
import { ModelArena } from "@/components/ModelArena";
import { NextStepsList } from "@/components/NextStepsList";

export function HiveDashboard({ initialStatus }: { initialStatus: HiveStatus | null }) {
  const { hiveStatus, setHiveStatus } = useHiveStore();

  // Seed Zustand with ISR data if store is empty or ISR is newer
  useEffect(() => {
    if (!initialStatus) return;
    const storeTs = hiveStatus?.last_updated ?? "";
    const isrTs = initialStatus.last_updated ?? "";
    if (!hiveStatus || isrTs > storeTs) {
      setHiveStatus(initialStatus);
    }
  }, [initialStatus, hiveStatus, setHiveStatus]);

  // Prefer SSE-live Zustand data; fall back to ISR
  const status = hiveStatus ?? initialStatus;
  const hive = status?.hives?.default;

  if (!status || !hive) {
    return (
      <div className="glass-card p-8 text-center space-y-2">
        <p className="text-2xl" style={{ color: "var(--color-text-muted)" }}>⬡</p>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Waiting for hive data…
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Connecting to status stream…
        </p>
      </div>
    );
  }

  const orchestratorSessions = (status as any).orchestrator_sessions;
  const nextSteps = status.next_steps ?? [];

  return (
    <div className="space-y-3">
      {/* ── Stat tiles ───────────────────────────────── */}
      <HiveStatusCard status={status} />

      {/* ── Active task (inline, brief) ──────────────── */}
      {status.active_task && typeof status.active_task === "object" && (
        <div className="glass-card px-4 py-3">
          <span className="section-title block mb-1">Active Task</span>
          <p
            className="text-xs font-mono leading-snug"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {(status.active_task as { agent?: string }).agent && (
              <span className="opacity-50 mr-1.5">
                [{(status.active_task as { agent?: string }).agent}]
              </span>
            )}
            {(status.active_task as { task?: string }).task ??
              JSON.stringify(status.active_task)}
          </p>
        </div>
      )}

      {/* ── Pending questions — priority widget ──────── */}
      <QuestionsList />

      {/* ── Sessions ─────────────────────────────────── */}
      <SessionGrid sessions={hive.sessions ?? []} />

      {/* ── Blockers ─────────────────────────────────── */}
      <BlockerList blockers={status.blockers ?? []} />

      {/* ── Next steps queue ─────────────────────────── */}
      <NextStepsList steps={nextSteps} />

      {/* ── Doctor ───────────────────────────────────── */}
      <DoctorStatus />

      {/* ── Orchestrator sessions (collapsible) ──────── */}
      <OrchestratorSessions sessions={orchestratorSessions} />

      {/* ── Model arena ──────────────────────────────── */}
      <ModelArena />

      {/* ── Achievements ─────────────────────────────── */}
      {(status.achievements ?? []).length > 0 && (
        <div className="glass-card p-4 space-y-2">
          <span className="section-title">Recent Achievements</span>
          <ul className="space-y-1.5 mt-2">
            {status.achievements!.slice(0, 5).map((a) => (
              <li
                key={a.id}
                className="flex items-start gap-2 text-xs"
                style={{ color: "var(--color-text-secondary)" }}
              >
                <span style={{ color: "var(--color-brand)", flexShrink: 0 }}>✓</span>
                {a.description.slice(0, 100)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Footer ───────────────────────────────────── */}
      {status.last_updated && (
        <p
          className="text-[10px] text-center pb-2 font-mono"
          style={{ color: "var(--color-text-muted)" }}
        >
          updated {new Date(status.last_updated).toLocaleTimeString()}
        </p>
      )}
    </div>
  );
}
