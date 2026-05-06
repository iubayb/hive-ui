"use client";

import { useHiveStore } from "@/store/useHiveStore";
import type { ReactNode } from "react";

interface PageHeaderProps {
  icon: string;
  title: string;
  subtitle?: string;
  right?: ReactNode;
}

function ConnDot() {
  const isConnected = useHiveStore((s) => s.isConnected);
  return (
    <span
      className="inline-flex items-center gap-1.5 text-[10px] font-mono shrink-0"
      style={{ color: isConnected ? "var(--color-brand)" : "#71717A" }}
      title={isConnected ? "Live — connected to status stream" : "Offline"}
    >
      <span
        style={{
          display: "inline-block",
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: isConnected ? "var(--color-brand)" : "#52525B",
          animation: isConnected ? "pulse-dot 2s ease-in-out infinite" : "none",
          flexShrink: 0,
        }}
      />
      {isConnected ? "live" : "off"}
    </span>
  );
}

export function PageHeader({ icon, title, subtitle, right }: PageHeaderProps) {
  return (
    <header
      className="sticky top-9 z-40 px-4 flex items-center gap-2 border-b"
      style={{
        height: "48px",
        background: "rgba(9,9,11,0.96)",
        borderColor: "var(--color-border)",
        backdropFilter: "blur(20px)",
      }}
    >
      <span
        className="text-base leading-none shrink-0"
        style={{ color: "var(--color-brand)" }}
      >
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <span
          className="font-display font-semibold text-sm truncate block"
          style={{ color: "var(--color-text-primary)" }}
        >
          {title}
        </span>
        {subtitle && (
          <span
            className="text-[10px] font-mono truncate block"
            style={{ color: "var(--color-text-muted)" }}
          >
            {subtitle}
          </span>
        )}
      </div>
      <ConnDot />
      {right && <div className="shrink-0 ml-1">{right}</div>}
    </header>
  );
}
