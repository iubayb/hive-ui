import { HiveDashboard } from "./HiveDashboard";

export const revalidate = 30;

async function getStatus() {
  try {
    const res = await fetch(
      "https://raw.githubusercontent.com/iubayb/hive-ui/status/hive-status.json",
      { next: { revalidate: 30 } }
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function HivePage() {
  const status = await getStatus();

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <header
        className="sticky top-0 z-40 px-4 py-3 flex items-center justify-between border-b"
        style={{
          background: "rgba(9,9,11,0.95)",
          borderColor: "var(--color-border)",
          backdropFilter: "blur(16px)",
        }}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">⬡</span>
          <span className="font-display font-semibold text-sm">Hive UI</span>
        </div>
      </header>

      <main className="px-4 py-4 max-w-lg mx-auto">
        <HiveDashboard initialStatus={status} />
      </main>
    </div>
  );
}
