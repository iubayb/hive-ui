"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useHiveStore, type ChatMessage } from "@/store/useHiveStore";

function uid() { return Math.random().toString(36).slice(2); }

interface Attachment {
  id: string;
  filename: string;
  type?: string;
  is_image?: boolean;
  pending?: boolean;
}

export function AIAssistant() {
  const {
    chatMessages, addChatMessage,
    isAssistantThinking, setAssistantThinking,
    hiveStatus,
  } = useHiveStore();
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isAssistantThinking]);

  // Auto-grow textarea
  const growTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  useEffect(() => { growTextarea(); }, [input, growTextarea]);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    e.target.value = "";
    for (const file of files) {
      const localId = uid();
      setAttachments((prev) => [...prev, { id: localId, filename: file.name, pending: true }]);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch("/api/upload", { method: "POST", body: fd });
        if (res.ok) {
          const data = await res.json();
          setAttachments((prev) =>
            prev.map((a) =>
              a.id === localId
                ? { id: data.id ?? localId, filename: data.filename ?? file.name, type: data.type, is_image: data.is_image, pending: false }
                : a
            )
          );
        } else {
          setAttachments((prev) => prev.map((a) => a.id === localId ? { ...a, pending: false } : a));
        }
      } catch {
        setAttachments((prev) => prev.map((a) => a.id === localId ? { ...a, pending: false } : a));
      }
    }
  }

  function removeAttachment(id: string) {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }

  function clearChat() {
    useHiveStore.setState({ chatMessages: [] });
  }

  async function send() {
    const text = input.trim();
    if ((!text && attachments.length === 0) || isAssistantThinking) return;
    const userMsg: ChatMessage = { id: uid(), role: "user", content: text };
    addChatMessage(userMsg);
    setInput("");
    const sentAttachments = [...attachments];
    setAttachments([]);
    setAssistantThinking(true);

    const assistantId = uid();
    addChatMessage({ id: assistantId, role: "assistant", content: "" });

    try {
      const h = hiveStatus?.hives?.default;
      const system = h
        ? `You are the Hive AI assistant. health=${Math.round((h.health_score ?? 0) * 100)}%, model=${h.active_model?.split("/").pop()}, open_blockers=${(hiveStatus?.blockers ?? []).filter((b) => b.status === "open").length}.`
        : "You are the Hive AI assistant helping monitor an autonomous AI hive.";

      const history = [...chatMessages, userMsg].map((m) => ({ role: m.role, content: m.content }));
      const payload: Record<string, unknown> = { messages: history, system };
      if (sentAttachments.length > 0) payload.attachment_ids = sentAttachments.map((a) => a.id);

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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

  const canSend = (input.trim() || attachments.length > 0) && !isAssistantThinking;

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {chatMessages.length === 0 && (
          <div className="text-center py-12" style={{ color: "var(--color-text-muted)" }}>
            <p className="text-3xl mb-2">◈</p>
            <p className="text-sm">Ask about hive status, blockers, or tasks.</p>
          </div>
        )}
        {chatMessages.map((m) => (
          <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
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
              {m.content || (isAssistantThinking && m.role === "assistant" ? "…" : "")}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="px-4 pb-4 pt-2 border-t" style={{ borderColor: "var(--color-border)" }}>
        {/* Attachment chips */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {attachments.map((a) => (
              <span
                key={a.id}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs"
                style={{
                  background: "var(--color-glass)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-secondary)",
                  opacity: a.pending ? 0.6 : 1,
                }}
              >
                {a.pending ? "○" : "◈"} {a.filename}
                <button
                  onClick={() => removeAttachment(a.id)}
                  className="ml-0.5 hover:opacity-70 transition-opacity"
                  aria-label={`Remove ${a.filename}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="flex gap-2 items-end">
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileChange} />

          {/* Attach */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isAssistantThinking}
            title="Attach file"
            className="shrink-0 rounded-xl text-sm transition-all flex items-center justify-center"
            style={{
              background: "var(--color-glass)",
              color: "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
              minHeight: "44px",
              minWidth: "44px",
            }}
          >
            ⊕
          </button>

          {/* Auto-growing textarea */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            onInput={growTextarea}
            placeholder="Ask the hive…"
            disabled={isAssistantThinking}
            className="flex-1 px-3 py-2.5 rounded-xl text-sm outline-none resize-none"
            style={{
              background: "var(--color-glass)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-primary)",
              minHeight: "44px",
              maxHeight: "160px",
              lineHeight: "1.5",
              fontFamily: "inherit",
            }}
          />

          {/* Clear (visible when there are messages) */}
          {chatMessages.length > 0 && !isAssistantThinking && (
            <button
              onClick={clearChat}
              title="Clear chat"
              className="shrink-0 rounded-xl text-xs transition-all flex items-center justify-center"
              style={{
                background: "var(--color-glass)",
                color: "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
                minHeight: "44px",
                minWidth: "44px",
              }}
            >
              ⊟
            </button>
          )}

          {/* Send */}
          <button
            onClick={send}
            disabled={!canSend}
            className="shrink-0 rounded-xl text-sm font-medium transition-all flex items-center justify-center"
            style={{
              background: canSend ? "var(--color-brand)" : "var(--color-glass)",
              color: canSend ? "#000" : "var(--color-text-muted)",
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
