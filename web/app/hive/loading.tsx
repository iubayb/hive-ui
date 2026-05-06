export default function HiveLoading() {
  return (
    <div style={{ background: "var(--color-surface)" }}>
      <header
        className="sticky top-0 z-40 px-4 py-3 flex items-center gap-2 border-b"
        style={{
          background: "rgba(9,9,11,0.95)",
          borderColor: "var(--color-border)",
        }}
      >
        <div className="h-4 w-20 rounded bg-zinc-800 animate-pulse" />
      </header>
      <main className="px-4 py-4 space-y-3 max-w-lg mx-auto animate-pulse">
        {/* Status card skeleton */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="h-4 w-24 rounded bg-zinc-800" />
            <div className="h-4 w-16 rounded bg-zinc-800" />
          </div>
          <div className="h-3 w-full rounded bg-zinc-800" />
          <div className="h-3 w-3/4 rounded bg-zinc-800" />
        </div>
        {/* Grid skeleton — 3 cards */}
        <div className="grid grid-cols-3 gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl border border-zinc-800 bg-zinc-900 p-3 space-y-2">
              <div className="h-6 w-6 rounded bg-zinc-800 mx-auto" />
              <div className="h-3 w-3/4 rounded bg-zinc-800 mx-auto" />
              <div className="h-3 w-1/2 rounded bg-zinc-800 mx-auto" />
            </div>
          ))}
        </div>
        {/* Blockers skeleton */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 space-y-2">
          <div className="h-3 w-20 rounded bg-zinc-800" />
          {[1, 2].map((i) => (
            <div key={i} className="h-3 w-full rounded bg-zinc-800" />
          ))}
        </div>
      </main>
    </div>
  );
}
