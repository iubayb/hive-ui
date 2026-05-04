export const revalidate = 3600;

async function getReport() {
  try {
    const res = await fetch(
      "https://raw.githubusercontent.com/iubayb/hive-ui/status/research/latest.md",
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return null;
    return res.text();
  } catch { return null; }
}

export default async function AnalysisPage() {
  const report = await getReport();

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <header
        className="sticky top-0 z-40 px-4 py-3 flex items-center gap-2 border-b"
        style={{
          background: "rgba(9,9,11,0.95)",
          borderColor: "var(--color-border)",
          backdropFilter: "blur(16px)",
        }}
      >
        <span className="text-lg">◎</span>
        <span className="font-display font-semibold text-sm">Analysis</span>
      </header>
      <main className="px-4 py-4 max-w-lg mx-auto">
        {report ? (
          <div className="glass-card p-4">
            <pre
              className="text-xs font-mono whitespace-pre-wrap"
              style={{ color: "var(--color-text-secondary)" }}
            >
              {report}
            </pre>
          </div>
        ) : (
          <div className="glass-card p-8 text-center space-y-2">
            <p className="text-2xl">◎</p>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              No analysis report yet
            </p>
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Push research/latest.md to the status/ branch
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
