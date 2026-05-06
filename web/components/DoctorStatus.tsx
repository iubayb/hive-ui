"use client";

import { useState, useEffect, useCallback } from "react";

interface Finding {
  session?: string;
  problem?: string;
  fix_command?: string;
  severity?: string;
}

interface DoctorData {
  last_run?: string;
  total_runs?: number;
  runs_total?: number;
  last_findings?: (string | Finding)[];
}

function findingText(f: string | Finding): string {
  if (typeof f === "string") return f;
  return f.problem ?? f.session ?? JSON.stringify(f);
}

export function DoctorStatus() {
  const [data, setData] = useState<DoctorData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/doctor");
      if (!res.ok) return;
      const json: DoctorData = await res.json();
      setData(json);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 60_000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (loading) {
    return (
      <div className="glass-card p-4 text-center text-xs" style={{ color: "var(--color-text-muted)" }}>
        Loading doctor status…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="glass-card p-4 text-center text-xs" style={{ color: "var(--color-text-muted)" }}>
        Doctor status unavailable
      </div>
    );
  }

  const findings = data.last_findings ?? [];
  const healthy = findings.length === 0;

  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="section-title">Doctor</span>
        <span
          className="text-xs px-2 py-0.5 rounded-full font-medium"
          style={{
            background: healthy ? "rgba(0,220,130,0.1)" : "rgba(245,158,11,0.1)",
            color: healthy ? "var(--color-brand)" : "#F59E0B",
            border: `1px solid ${healthy ? "rgba(0,220,130,0.3)" : "rgba(245,158,11,0.3)"}`,
          }}
        >
          {healthy ? "Healthy" : "Issues found"}
        </span>
      </div>

      <div className="flex gap-4 text-xs" style={{ color: "var(--color-text-muted)" }}>
        {data.last_run && (
          <span>
            Last run:{" "}
            <span style={{ color: "var(--color-text-secondary)" }}>
              {new Date(data.last_run).toLocaleTimeString()}
            </span>
          </span>
        )}
        {data.total_runs !== undefined || data.runs_total !== undefined && (
          <span>
            Total runs:{" "}
            <span style={{ color: "var(--color-text-secondary)" }}>{data.total_runs ?? data.runs_total}</span>
          </span>
        )}
        {findings.length > 0 && (
          <span>
            Findings:{" "}
            <span style={{ color: "#F59E0B" }}>{findings.length}</span>
          </span>
        )}
      </div>

      {findings.length > 0 && (
        <ul className="space-y-1.5">
          {findings.map((f, i) => (
            <li key={i} className="flex gap-2 items-start text-xs">
              <span className="shrink-0 mt-0.5" style={{ color: "#F59E0B" }}>⚠</span>
              <span style={{ color: "var(--color-text-secondary)" }}>{findingText(f)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
