"use client";

import { useState, useRef, useEffect } from "react";
import { useHiveStore, type ChatMessage } from "@/store/useHiveStore";

function uid() { return Math.random().toString(36).slice(2); }

export function AIAssistant() {
  const {
    chatMessages, addChatMessage,
    isAssistantThinking, setAssistantThinking,
    hiveStatus,
  } = useHiveStore();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isAssistantThinking]);

  async function send() {
    const text = input.trim();
    if (!text || isAssistantThinking) return;
    const userMsg: ChatMessage = { id: uid(), role: "user", content: text };
    addChatMessage(userMsg);
    setInput("");
    setAssistantThinking(true);

    const assistantId = uid();
    addChatMessage({ id: assistantId, role: "assistant", content: "" });

    try {
      const h = hiveStatus?.hives?.default;
      const system = h
        ? `You are the Hive AI assistant. health=${Math.round((h.health_score ?? 0) * 100)}%, model=${h.active_model?.split("/").pop()}, open_blockers=${(hiveStatus?.blockers ?? []).filter((b) => b.status === "open").length}.`
        : "You are the Hive AI assistant helping monitor an autonomous AI hive.";

      const history = [...chatMessages, userMsg].map((m) => ({
        role: m.role, content: m.content,
      }));

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history, system }),
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let reply = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = dec.decode(value, { stream: true });
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") break;
          try {
            const delta = JSON.parse(raw)?.choices?.[0]?.delta?.content ?? "";
            reply += delta;
            useHiveStore.setState((s) => ({
              chatMessages: s.chatMessages.map((m) =>
                m.id === assistantId ? { ...m, content: reply } : m
              ),
            }));
          } catch {}
        }
      }
    } catch (e: any) {
      useHiveStore.setState((s) => ({
        chatMessages: s.chatMessages.map((m) =>
          m.id === assistantId ? { ...m, content: `Error: ${e.message}` } : m
        ),
      }));
    } finally {
      setAssistantThinking(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {chatMessages.length === 0 && (
          <div
            className="text-center py-12"
            style={{ color: "var(--color-text-muted)" }}
          >
            <p className="text-3xl mb-2">◈</p>
            <p className="text-sm">Ask about hive status, blockers, or tasks.</p>
          </div>
        )}
        {chatMessages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className="max-w-[85%] px-3 py-2 rounded-xl text-sm"
              style={
                m.role === "user"
                  ? {
                      background: "var(--color-brand-muted)",
                      color: "var(--color-brand)",
                      border: "1px solid rgba(0,220,130,0.2)",
                      borderBottomRightRadius: "4px",
                    }
                  : {
                      background: "var(--color-glass)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text-secondary)",
                      borderBottomLeftRadius: "4px",
                    }
              }
            >
              {m.content || (isAssistantThinking ? "…" : "")}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div
        className="px-4 pb-4 pt-2 border-t"
        style={{ borderColor: "var(--color-border)" }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
            placeholder="Ask the hive…"
            disabled={isAssistantThinking}
            className="flex-1 px-3 py-2.5 rounded-xl text-sm outline-none"
            style={{
              background: "var(--color-glass)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-primary)",
              minHeight: "44px",
            }}
          />
          <button
            onClick={send}
            disabled={isAssistantThinking || !input.trim()}
            className="px-3 rounded-xl text-sm font-medium transition-all"
            style={{
              background: input.trim() ? "var(--color-brand)" : "var(--color-glass)",
              color: input.trim() ? "#000" : "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              minHeight: "44px",
              minWidth: "44px",
            }}
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}
