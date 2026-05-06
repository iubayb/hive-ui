"use client";

import { useEffect } from "react";
import { useHiveStore, type HiveStatus } from "@/store/useHiveStore";
import { HiveStatusCard } from "@/components/HiveStatusCard";
import { SessionGrid } from "@/components/SessionGrid";
import { BlockerList } from "@/components/BlockerList";

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
        <p className="text-2xl">⬡</p>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Waiting for hive data…
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Connecting to status stream…
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <HiveStatusCard status={status} />
      <SessionGrid sessions={hive.sessions ?? []} />
      <BlockerList blockers={status.blockers ?? []} />

      {(status.achievements ?? []).length > 0 && (
        <div className="glass-card p-4 space-y-2">
          <span className="section-title">Recent Achievements</span>
          <ul className="space-y-1.5 mt-2">
            {status.achievements!.slice(0, 5).map((a) => (
              <li
                key={a.id}
                className="text-xs"
                style={{ color: "var(--color-text-secondary)" }}
              >
                <span style={{ color: "var(--color-brand)" }}>✓ </span>
                {a.description.slice(0, 100)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {status.active_task && (
        <div className="glass-card px-4 py-3">
          <span className="section-title block mb-1">Active Task</span>
          <p
            className="text-xs font-mono"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {status.active_task}
          </p>
        </div>
      )}

      {/* Footer: last updated */}
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
