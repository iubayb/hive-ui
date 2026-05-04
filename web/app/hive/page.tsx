import { HiveStatusCard } from "@/components/HiveStatusCard";
import { SessionGrid } from "@/components/SessionGrid";
import { BlockerList } from "@/components/BlockerList";

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
  const hive = status?.hives?.default;

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
        {status && (
          <span
            className="text-xs font-mono"
            style={{ color: "var(--color-text-muted)" }}
          >
            {new Date(status.last_updated).toLocaleTimeString()}
          </span>
        )}
      </header>

      <main className="px-4 py-4 space-y-3 max-w-lg mx-auto">
        {status ? (
          <>
            <HiveStatusCard status={status} />
            <SessionGrid sessions={hive?.sessions ?? []} />
            <BlockerList blockers={status.blockers ?? []} />

            {(status.achievements ?? []).length > 0 && (
              <div className="glass-card p-4 space-y-2">
                <span className="section-title">Recent Achievements</span>
                <ul className="space-y-1.5 mt-2">
                  {status.achievements.slice(0, 5).map((a: any) => (
                    <li
                      key={a.id}
                      className="text-xs"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      <span style={{ color: "var(--color-brand)" }}>✓ </span>
                      {a.description.slice(0, 100)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {status.active_task && (
              <div className="glass-card px-4 py-3">
                <span className="section-title block mb-1">Active Task</span>
                <p
                  className="text-xs font-mono"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  {status.active_task}
                </p>
              </div>
            )}
          </>
        ) : (
          <div className="glass-card p-8 text-center space-y-2">
            <p className="text-2xl">⬡</p>
            <p
              className="text-sm"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Waiting for hive data…
            </p>
            <p
              className="text-xs"
              style={{ color: "var(--color-text-muted)" }}
            >
              Push hive-status.json to the status/ branch
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
