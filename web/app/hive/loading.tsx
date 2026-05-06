export default function HiveLoading() {
  const shimmer = {
    background: "rgba(255,255,255,0.04)",
    borderRadius: "6px",
  } as const;

  return (
    <div style={{ background: "var(--color-surface)" }}>
      {/* Skeleton header (matches PageHeader height) */}
      <div
        className="sticky top-9 border-b flex items-center px-4 gap-2"
        style={{
          height: "48px",
          background: "rgba(9,9,11,0.96)",
          borderColor: "rgba(255,255,255,0.08)",
        }}
      >
        <div style={{ ...shimmer, width: 14, height: 14 }} className="animate-pulse" />
        <div style={{ ...shimmer, width: 60, height: 12 }} className="animate-pulse" />
      </div>

      {/* Quick-links strip skeleton */}
      <div
        className="px-4 py-2 flex gap-1.5 border-b"
        style={{ borderColor: "rgba(255,255,255,0.08)" }}
      >
        {[48, 36, 40, 72, 52, 52].map((w, i) => (
          <div
            key={i}
            className="animate-pulse rounded-full shrink-0"
            style={{ ...shimmer, width: w, height: 28 }}
          />
        ))}
      </div>

      <main className="px-4 py-4 space-y-3 max-w-lg mx-auto animate-pulse">
        {/* 2×2 stat tile grid */}
        <div className="grid grid-cols-2 gap-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border p-3"
              style={{
                background: "var(--color-surface-raised)",
                borderColor: "rgba(255,255,255,0.06)",
                minHeight: 72,
              }}
            >
              <div style={{ ...shimmer, width: 48, height: 28, marginBottom: 8 }} />
              <div style={{ ...shimmer, width: 36, height: 8 }} />
            </div>
          ))}
        </div>

        {/* Model row */}
        <div
          className="rounded-xl border px-3 py-2 flex items-center gap-2"
          style={{
            background: "var(--color-glass)",
            borderColor: "rgba(255,255,255,0.06)",
            height: 36,
          }}
        >
          <div style={{ ...shimmer, width: 32, height: 8 }} />
          <div style={{ ...shimmer, flex: 1, height: 10 }} />
          <div style={{ ...shimmer, width: 40, height: 18, borderRadius: "999px" }} />
        </div>

        {/* Sessions card */}
        <div className="rounded-xl border p-4 space-y-2"
          style={{ background: "var(--color-glass)", borderColor: "rgba(255,255,255,0.06)" }}
        >
          <div style={{ ...shimmer, width: 56, height: 8 }} />
          <div className="grid grid-cols-2 gap-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="rounded-lg p-2 space-y-1.5"
                style={{ background: "rgba(255,255,255,0.02)" }}
              >
                <div style={{ ...shimmer, width: "60%", height: 8 }} />
                <div style={{ ...shimmer, width: "40%", height: 6 }} />
              </div>
            ))}
          </div>
        </div>

        {/* Blockers skeleton */}
        <div className="rounded-xl border p-4 space-y-2"
          style={{ background: "var(--color-glass)", borderColor: "rgba(255,255,255,0.06)" }}
        >
          <div style={{ ...shimmer, width: 48, height: 8 }} />
          {[0, 1].map((i) => (
            <div key={i} style={{ ...shimmer, width: "100%", height: 10 }} />
          ))}
        </div>
      </main>
    </div>
  );
}
