"use client";

import { useState, useEffect } from "react";

export default function KeysPage() {
  const [keys, setKeys] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch("/api/keys")
      .then((r) => r.json())
      .then((d) => setKeys(d.keys ?? []))
      .catch(() => {});
  }, []);

  async function add() {
    if (!name.trim() || !value.trim()) return;
    const res = await fetch("/api/keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), value: value.trim() }),
    });
    if (res.ok) {
      setKeys((k) => [...k, name.trim()]);
      setName("");
      setValue("");
      setStatus("Saved");
      setTimeout(() => setStatus(""), 2000);
    }
  }

  async function remove(k: string) {
    await fetch("/api/keys", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: k }),
    });
    setKeys((ks) => ks.filter((x) => x !== k));
  }

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
        <span className="text-lg">⚿</span>
        <span className="font-display font-semibold text-sm">Key Vault</span>
      </header>
      <main className="px-4 py-4 space-y-4 max-w-lg mx-auto">
        <div className="glass-card p-4 space-y-3">
          <span className="section-title">Add Key</span>
          <input
            className="w-full px-3 py-2 rounded-lg text-sm outline-none"
            style={{
              background: "var(--color-glass)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-primary)",
            }}
            placeholder="Name (e.g. OPENROUTER_API_KEY)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none"
            style={{
              background: "var(--color-glass)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-primary)",
            }}
            placeholder="Value (sk-or-v1-…)"
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <button
            onClick={add}
            className="w-full py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: "var(--color-brand-muted)",
              color: "var(--color-brand)",
              border: "1px solid rgba(0,220,130,0.2)",
              minHeight: "44px",
            }}
          >
            {status || "Save Key"}
          </button>
        </div>

        {keys.length > 0 && (
          <div className="glass-card p-4 space-y-2">
            <span className="section-title">Stored Keys</span>
            <ul className="space-y-1 mt-2">
              {keys.map((k) => (
                <li
                  key={k}
                  className="flex items-center justify-between px-2 py-1.5 rounded-lg"
                  style={{ background: "rgba(255,255,255,0.02)" }}
                >
                  <span className="text-sm font-mono" style={{ color: "var(--color-text-secondary)" }}>
                    {k}
                  </span>
                  <button
                    onClick={() => remove(k)}
                    className="text-xs px-2 py-1 rounded"
                    style={{ color: "#EF4444" }}
                  >
                    remove
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}
