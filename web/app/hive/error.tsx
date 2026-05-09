"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 p-6">
      <p className="text-sm font-mono" style={{ color: "var(--color-text-secondary)" }}>
        Failed to load hive status
      </p>
      <p className="text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
        {error.message}
      </p>
      <button
        onClick={reset}
        className="px-4 py-2 rounded text-sm transition-colors"
        style={{
          background: "var(--color-glass)",
          color: "var(--color-text-secondary)",
          border: "1px solid var(--color-border)",
        }}
      >
        Retry
      </button>
    </div>
  );
}
