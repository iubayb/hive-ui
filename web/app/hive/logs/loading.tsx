export default function LogsLoading() {
  return (
    <div style={{ background: "var(--color-surface)" }}>
      <header
        className="sticky top-0 z-40 px-4 py-3 flex items-center gap-2 border-b"
        style={{
          background: "rgba(9,9,11,0.95)",
          borderColor: "var(--color-border)",
        }}
      >
        <div className="h-4 w-24 rounded bg-zinc-800 animate-pulse" />
      </header>
      <main className="px-4 py-4 max-w-lg mx-auto">
        <div
          className="rounded-lg border p-3 animate-pulse"
          style={{
            background: "#09090b",
            borderColor: "var(--color-border)",
            height: "calc(100dvh - 130px)",
          }}
        >
          {Array.from({ length: 18 }).map((_, i) => (
            <div
              key={i}
              className="h-3 rounded bg-zinc-800 mb-2"
              style={{ width: `${55 + (i * 17) % 40}%` }}
            />
          ))}
        </div>
      </main>
    </div>
  );
}
