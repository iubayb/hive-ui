import type { Blocker } from "@/store/useHiveStore";

const SEV: Record<string, string> = {
  critical: "#EF4444",
  high: "#F97316",
  medium: "#F59E0B",
  low: "#6B7280",
};

export function BlockerList({ blockers }: { blockers: Blocker[] }) {
  const open = blockers.filter((b) => b.status === "open");
  if (!open.length)
    return (
      <div
        className="glass-card p-4 text-center text-xs"
        style={{ color: "var(--color-brand)" }}
      >
        No open blockers ✓
      </div>
    );
  return (
    <div className="glass-card p-4 space-y-3">
      <span className="section-title">Open Blockers ({open.length})</span>
      <ul className="space-y-2 mt-2">
        {open.map((b) => (
          <li key={b.id} className="flex gap-2 items-start text-xs">
            <span
              className="shrink-0 w-1.5 h-1.5 rounded-full mt-1"
              style={{ background: SEV[b.severity] ?? "#6B7280" }}
            />
            <span style={{ color: "var(--color-text-secondary)" }}>
              {b.description.slice(0, 120)}
              {b.description.length > 120 ? "…" : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
