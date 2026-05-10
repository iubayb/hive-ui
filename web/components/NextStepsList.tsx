import type { NextStep } from "@/store/useHiveStore";

const STATUS_DOT: Record<string, string> = {
  pending:     "#6B7280",
  in_progress: "#F59E0B",
  done:        "#00DC82",
  completed:   "#00DC82",
  blocked:     "#EF4444",
  cancelled:   "#3F3F46",
};

const PRIORITY_COLOR: Record<string, string> = {
  P0: "#EF4444",
  P1: "#F59E0B",
  P2: "#6B7280",
  P3: "#3F3F46",
  high:   "#EF4444",
  medium: "#F59E0B",
  low:    "#6B7280",
};

export function NextStepsList({ steps }: { steps: NextStep[] }) {
  if (!steps.length) return null;

  const pending = steps.filter(
    (s) => s.status !== "done" && s.status !== "cancelled"
  );
  if (!pending.length) return null;

  return (
    <div className="glass-card p-4 space-y-2">
      <span className="section-title">Next Steps</span>
      <ul className="space-y-2 mt-2">
        {pending.slice(0, 6).map((step) => (
          <li key={step.id} className="flex items-start gap-2">
            <span
              className="shrink-0 rounded-full"
              style={{
                width: 6,
                height: 6,
                marginTop: 5,
                background: STATUS_DOT[step.status] ?? "#6B7280",
                flexShrink: 0,
              }}
            />
            <p
              className="flex-1 text-xs leading-snug min-w-0"
              style={{ color: "var(--color-text-secondary)" }}
            >
              {step.description.slice(0, 100)}
            </p>
            {step.assigned_to && (
              <span
                className="shrink-0 text-[9px] font-mono font-semibold px-1 py-0.5 rounded"
                style={{
                  color: PRIORITY_COLOR[step.assigned_to] ?? "var(--color-text-muted)",
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                {step.assigned_to}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
