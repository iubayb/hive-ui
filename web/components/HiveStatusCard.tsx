import type { HiveStatus, Blocker } from "@/store/useHiveStore";

function HealthBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? "#00DC82" : pct >= 50 ? "#F59E0B" : "#EF4444";
  return (
    <div className="flex items-center gap-2">
      <div
        className="flex-1 rounded-full overflow-hidden"
        style={{ height: "4px", background: "rgba(255,255,255,0.08)" }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            transition: "width 0.4s ease",
          }}
        />
      </div>
      <span className="text-xs font-mono" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

export function HiveStatusCard({ status }: { status: HiveStatus }) {
  const hive = status.hives?.default;
  if (!hive) return null;
  const openBlockers = (status.blockers ?? []).filter(
    (b: Blocker) => b.status === "open"
  ).length;
  const pending = (status.next_steps ?? []).filter(
    (n) => n.status === "pending"
  ).length;

  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-display font-semibold text-sm">
          Hive Status
        </span>
        <span className="brand-badge">{hive.status}</span>
      </div>
      <HealthBar score={hive.health_score ?? 0} />
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div style={{ color: "var(--color-text-secondary)" }}>
          <span style={{ color: "var(--color-text-muted)" }}>Sessions </span>
          <span className="font-mono">{hive.sessions?.length ?? 0}</span>
        </div>
        <div style={{ color: "var(--color-text-secondary)" }}>
          <span style={{ color: "var(--color-text-muted)" }}>Errors/hr </span>
          <span className="font-mono">{hive.errors_last_hour ?? 0}</span>
        </div>
        <div
          style={{
            color:
              openBlockers > 0 ? "#EF4444" : "var(--color-text-secondary)",
          }}
        >
          <span style={{ color: "var(--color-text-muted)" }}>Blockers </span>
          <span className="font-mono">{openBlockers}</span>
        </div>
        <div style={{ color: "var(--color-text-secondary)" }}>
          <span style={{ color: "var(--color-text-muted)" }}>Next steps </span>
          <span className="font-mono">{pending}</span>
        </div>
      </div>
      {hive.current_goal && (
        <p className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
          {hive.current_goal}
        </p>
      )}
      <p
        className="text-xs font-mono truncate"
        style={{ color: "var(--color-text-muted)" }}
      >
        {hive.active_model?.split("/").pop()}
      </p>
    </div>
  );
}
