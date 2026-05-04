export default function CommitsLoading() {
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
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-zinc-800 bg-zinc-900 p-3 space-y-1.5">
            <div className="h-3 rounded bg-zinc-800" style={{ width: `${60 + (i * 13) % 35}%` }} />
            <div className="flex gap-2 items-center">
              <div className="h-3 w-12 rounded bg-zinc-700" />
              <div className="h-3 w-28 rounded bg-zinc-800" />
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}
