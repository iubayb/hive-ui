export default function PullsLoading() {
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
      <main className="px-4 py-4 space-y-2 max-w-lg mx-auto animate-pulse">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 space-y-2">
            <div className="flex items-start gap-2">
              <div className="h-3 w-8 rounded bg-zinc-800 shrink-0 mt-0.5" />
              <div className="h-3 rounded bg-zinc-800 flex-1" />
            </div>
            <div className="flex gap-2 pl-5 items-center">
              <div className="h-3 w-16 rounded bg-zinc-800" />
              <div className="h-3 w-20 rounded bg-zinc-800" />
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}
