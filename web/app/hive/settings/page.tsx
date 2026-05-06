"use client";

import { useState, useEffect, useCallback } from "react";
import { PageHeader } from "@/components/PageHeader";

interface Config {
  model?: string;
  llm_base_url?: string;
  ai_auto_answer?: boolean;
}

const FREE_MODELS = [
  "meta-llama/llama-3.3-70b-instruct:free",
  "mistralai/mistral-7b-instruct:free",
  "qwen/qwen-2.5-72b-instruct:free",
  "inclusionai/ling-2.6-1t:free",
  "google/gemma-3-27b-it:free",
  "deepseek/deepseek-r1-0528:free",
];

type ToastType = "success" | "error";

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="relative shrink-0 rounded-full transition-colors duration-200"
      style={{
        width: 40, height: 22,
        background: checked ? "var(--color-brand)" : "#3F3F46",
        border: "none", cursor: "pointer",
      }}
    >
      <span
        className="absolute top-0.5 rounded-full transition-transform duration-200"
        style={{
          width: 18, height: 18, background: "#fff",
          transform: checked ? "translateX(20px)" : "translateX(2px)",
        }}
      />
    </button>
  );
}

export default function SettingsPage() {
  const [config, setConfig] = useState<Config>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ type: ToastType; message: string } | null>(null);

  const showToast = useCallback((type: ToastType, message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => {
    fetch("/api/config")
      .then((r) => r.json())
      .then((data) => { setConfig(data ?? {}); setLoading(false); })
      .catch(() => { setLoading(false); showToast("error", "Failed to load configuration"); });
  }, [showToast]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        showToast("success", "Settings saved successfully");
      } else {
        const err = await res.json().catch(() => ({}));
        showToast("error", err?.error ?? "Failed to save settings");
      }
    } catch {
      showToast("error", "Network error — backend unreachable");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ background: "var(--color-surface)" }}>
      <PageHeader icon="⊗" title="Settings" />

      {/* Toast */}
      {toast && (
        <div
          className="fixed top-24 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-lg text-sm font-medium shadow-lg"
          style={{
            background: toast.type === "success" ? "rgba(0,220,130,0.15)" : "rgba(239,68,68,0.15)",
            color: toast.type === "success" ? "#00DC82" : "#EF4444",
            border: `1px solid ${toast.type === "success" ? "rgba(0,220,130,0.3)" : "rgba(239,68,68,0.3)"}`,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {toast.message}
        </div>
      )}

      <main className="px-4 py-4 max-w-lg mx-auto">
        {loading ? (
          <p style={{ color: "var(--color-text-muted)", fontSize: 14 }}>Loading…</p>
        ) : (
          <div className="flex flex-col gap-5">
            {/* Model selector */}
            <div className="glass-card p-4 flex flex-col gap-3">
              <label className="section-title" style={{ display: "block" }}>Model</label>
              <input
                type="text"
                value={config.model ?? ""}
                onChange={(e) => setConfig((c) => ({ ...c, model: e.target.value }))}
                placeholder="e.g. meta-llama/llama-3.3-70b-instruct:free"
                className="w-full rounded-lg px-3 py-2 text-sm"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-primary)",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 12,
                }}
              />
              <div className="flex flex-wrap gap-2">
                {FREE_MODELS.map((m) => {
                  const active = config.model === m;
                  return (
                    <button
                      key={m}
                      onClick={() => setConfig((c) => ({ ...c, model: m }))}
                      className="rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors"
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        background: active ? "var(--color-brand-muted)" : "rgba(255,255,255,0.04)",
                        color: active ? "var(--color-brand)" : "var(--color-text-secondary)",
                        border: `1px solid ${active ? "rgba(0,220,130,0.3)" : "var(--color-border)"}`,
                        cursor: "pointer",
                      }}
                    >
                      {m.split("/")[1] ?? m}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* LLM Base URL */}
            <div className="glass-card p-4 flex flex-col gap-2">
              <label className="section-title" style={{ display: "block" }}>LLM Base URL</label>
              <input
                type="text"
                value={config.llm_base_url ?? ""}
                onChange={(e) => setConfig((c) => ({ ...c, llm_base_url: e.target.value }))}
                placeholder="https://openrouter.ai/api/v1"
                className="w-full rounded-lg px-3 py-2 text-sm"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-primary)",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 12,
                }}
              />
            </div>

            {/* AI Auto-answer */}
            <div className="glass-card p-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
                  AI Auto-answer
                </p>
                <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                  Automatically answer agent questions using AI
                </p>
              </div>
              <Toggle
                checked={Boolean(config.ai_auto_answer)}
                onChange={(v) => setConfig((c) => ({ ...c, ai_auto_answer: v }))}
              />
            </div>

            {/* Save */}
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-xl py-3 text-sm font-semibold transition-opacity"
              style={{
                background: "var(--color-brand)",
                color: "#000",
                opacity: saving ? 0.6 : 1,
                cursor: saving ? "not-allowed" : "pointer",
              }}
            >
              {saving ? "Saving…" : "Save Settings"}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
