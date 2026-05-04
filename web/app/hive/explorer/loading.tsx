export default function ExplorerLoading() {
  return (
    <div style={{ background: "var(--color-surface)" }}>
      <header
        className="sticky top-0 z-40 px-4 py-3 flex items-center gap-2 border-b"
        style={{
          background: "rgba(9,9,11,0.95)",
          borderColor: "var(--color-border)",
        }}
      >
        <div className="h-4 w-16 rounded bg-zinc-800 animate-pulse" />
        <div className="ml-2 h-4 w-32 rounded bg-zinc-800 animate-pulse" />
      </header>
      <main className="px-4 py-4 max-w-lg mx-auto animate-pulse">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 divide-y divide-zinc-800">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-2.5">
              <div className="h-4 w-4 rounded bg-zinc-800 shrink-0" />
              <div
                className="h-3 rounded bg-zinc-800"
                style={{ width: `${40 + (i * 19) % 45}%` }}
              />
              <div className="ml-auto h-3 w-10 rounded bg-zinc-800" />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
