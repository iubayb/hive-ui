import type { HiveStatus, Blocker } from "@/store/useHiveStore";

function HealthBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div
      className="w-full rounded-full overflow-hidden mt-1"
      style={{ height: "3px", background: "rgba(255,255,255,0.06)" }}
    >
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          background: color,
          transition: "width 0.5s ease",
        }}
      />
    </div>
  );
}

export function HiveStatusCard({ status }: { status: HiveStatus }) {
  const hive = status.hives?.default;
  if (!hive) return null;

  const pct = Math.round((hive.health_score ?? 0) * 100);
  const healthColor =
    pct >= 80 ? "#00DC82" : pct >= 50 ? "#F59E0B" : "#EF4444";
  const errorsPerHour = hive.errors_last_hour ?? 0;
  const openBlockers = (status.blockers ?? []).filter(
    (b: Blocker) => b.status === "open"
  ).length;
  const callsToday = (status as any).metrics?.openrouter_calls_today ?? 0;

  // Model name: prefer model_champions.text, fall back to active_model on hive
  const rawModel =
    (status as any).model_champions?.text ?? hive.active_model ?? "";
  const modelLabel = rawModel.split("/").pop() ?? rawModel;

  return (
    <div className="space-y-2">
      {/* 2 × 2 stat tiles */}
      <div className="grid grid-cols-2 gap-2">
        {/* Health */}
        <div
          className={`stat-tile ${pct >= 95 ? "health-glow" : ""}`}
          style={pct >= 95 ? { borderColor: "rgba(0,220,130,0.3)" } : {}}
        >
          <span
            className="text-2xl font-bold font-display leading-none"
            style={{ color: healthColor }}
          >
            {pct}%
          </span>
          <HealthBar pct={pct} color={healthColor} />
          <span className="section-title mt-1.5 block">Health</span>
        </div>

        {/* Sessions */}
        <div className="stat-tile">
          <span
            className="text-2xl font-bold font-display leading-none"
            style={{ color: "var(--color-text-primary)" }}
          >
            {hive.sessions?.length ?? 0}
          </span>
          <span className="section-title mt-2 block">Sessions</span>
        </div>

        {/* Errors / hr */}
        <div className="stat-tile">
          <span
            className="text-2xl font-bold font-display leading-none"
            style={{
              color: errorsPerHour > 0 ? "#F59E0B" : "var(--color-text-primary)",
            }}
          >
            {errorsPerHour}
          </span>
          <span className="section-title mt-2 block">Errors / hr</span>
        </div>

        {/* Blockers */}
        <div className="stat-tile">
          <span
            className="text-2xl font-bold font-display leading-none"
            style={{
              color: openBlockers > 0 ? "#EF4444" : "var(--color-text-primary)",
            }}
          >
            {openBlockers}
          </span>
          <span className="section-title mt-2 block">Blockers</span>
        </div>
      </div>

      {/* Model + calls row */}
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-xl border"
        style={{
          background: "var(--color-glass)",
          borderColor: "var(--color-border)",
        }}
      >
        <span className="section-title shrink-0">model</span>
        <span
          className="flex-1 text-xs font-mono truncate"
          style={{ color: "var(--color-brand)" }}
        >
          {modelLabel || "—"}
        </span>
        {callsToday > 0 && (
          <span
            className="shrink-0 text-[10px] font-mono"
            style={{ color: "var(--color-text-muted)" }}
          >
            {callsToday} calls
          </span>
        )}
        <span className="brand-badge shrink-0">{hive.status}</span>
      </div>
    </div>
  );
}
