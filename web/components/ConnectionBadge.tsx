"use client";

import { useHiveStore } from "@/store/useHiveStore";

export function ConnectionBadge() {
  const isConnected = useHiveStore((s) => s.isConnected);

  return (
    <div className="fixed top-3 right-3 z-50 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold shadow-md backdrop-blur-sm select-none border border-white/10 bg-black/60">
      <span
        className={`inline-block h-2 w-2 rounded-full ${
          isConnected ? "bg-green-400 animate-pulse" : "bg-red-500"
        }`}
      />
      <span className={isConnected ? "text-green-300" : "text-red-400"}>
        {isConnected ? "LIVE" : "OFFLINE"}
      </span>
    </div>
  );
}
