import { ghFetch } from "@/lib/github";

export const revalidate = 30;

const STATUS_COLOR: Record<string, string> = {
  completed: "#00DC82",
  in_progress: "#F59E0B",
  queued: "#6B7280",
  failure: "#EF4444",
  success: "#00DC82",
};

export default async function WorkflowsPage() {
  let runs: any[] = [];
  try {
    const data = await ghFetch<{ workflow_runs: any[] }>("/actions/runs?per_page=15", { revalidate: 30 });
    runs = data.workflow_runs ?? [];
  } catch {}

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
        <span className="text-lg">⚙</span>
        <span className="font-display font-semibold text-sm">Workflows</span>
      </header>
      <main className="px-4 py-4 space-y-2 max-w-lg mx-auto">
        {runs.length === 0 ? (
          <div className="glass-card p-8 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
            No workflow runs found
          </div>
        ) : (
          runs.map((run) => (
            <a
              key={run.id}
              href={run.html_url}
              target="_blank"
              rel="noreferrer"
              className="glass-card-hover block p-3"
            >
              <div className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{
                    background:
                      STATUS_COLOR[run.conclusion ?? run.status] ?? "#6B7280",
                  }}
                />
                <p className="text-sm flex-1 truncate" style={{ color: "var(--color-text-primary)" }}>
                  {run.name}
                </p>
                <span className="text-xs font-mono shrink-0" style={{ color: "var(--color-text-muted)" }}>
                  {run.conclusion ?? run.status}
                </span>
              </div>
              <p className="text-xs mt-1 pl-4" style={{ color: "var(--color-text-muted)" }}>
                {run.head_commit?.message?.split("\n")[0]?.slice(0, 60)} · {run.head_branch}
              </p>
            </a>
          ))
        )}
      </main>
    </div>
  );
}
