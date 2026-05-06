export function SessionGrid({ sessions }: { sessions: string[] }) {
  if (!sessions?.length)
    return (
      <div
        className="glass-card p-4 text-center text-xs"
        style={{ color: "var(--color-text-muted)" }}
      >
        No active sessions
      </div>
    );
  return (
    <div className="glass-card p-4 space-y-2">
      <span className="section-title">Active Sessions</span>
      <div className="flex flex-wrap gap-1.5 mt-2">
        {sessions.map((s) => (
          <span
            key={s}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-mono"
            style={{
              background: "rgba(0,220,130,0.06)",
              color: "var(--color-brand)",
              border: "1px solid rgba(0,220,130,0.2)",
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse-slow inline-block" />
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}
