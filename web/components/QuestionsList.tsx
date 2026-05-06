"use client";

import { useState, useEffect, useCallback } from "react";

interface Question {
  id: string;
  text: string;
  hint?: string;
  type: "choice" | "text";
  choices?: string[];
}

export function QuestionsList() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<Record<string, boolean>>({});
  const [flash, setFlash] = useState<Record<string, "success" | "error">>({});
  const [loading, setLoading] = useState(true);

  const fetchQuestions = useCallback(async () => {
    try {
      const res = await fetch("/api/questions");
      if (!res.ok) return;
      const data = await res.json();
      const list: Question[] = Array.isArray(data) ? data : (data.questions ?? []);
      setQuestions(list);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchQuestions();
    const interval = setInterval(fetchQuestions, 30_000);
    return () => clearInterval(interval);
  }, [fetchQuestions]);

  async function submitAnswer(q: Question) {
    const answer = answers[q.id];
    if (!answer?.trim()) return;
    setSubmitting((s) => ({ ...s, [q.id]: true }));
    try {
      const res = await fetch("/api/questions/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_id: q.id, answer }),
      });
      if (res.ok) {
        setFlash((f) => ({ ...f, [q.id]: "success" }));
        setTimeout(() => {
          setQuestions((qs) => qs.filter((x) => x.id !== q.id));
          setFlash((f) => { const n = { ...f }; delete n[q.id]; return n; });
        }, 800);
      } else {
        setFlash((f) => ({ ...f, [q.id]: "error" }));
        setTimeout(() => setFlash((f) => { const n = { ...f }; delete n[q.id]; return n; }), 2000);
      }
    } catch {
      setFlash((f) => ({ ...f, [q.id]: "error" }));
      setTimeout(() => setFlash((f) => { const n = { ...f }; delete n[q.id]; return n; }), 2000);
    } finally {
      setSubmitting((s) => ({ ...s, [q.id]: false }));
    }
  }

  if (loading) {
    return (
      <div className="glass-card p-4 text-center text-xs" style={{ color: "var(--color-text-muted)" }}>
        Loading questions…
      </div>
    );
  }

  if (!questions.length) {
    return (
      <div className="glass-card p-4 text-center text-xs" style={{ color: "var(--color-brand)" }}>
        No pending questions ✓
      </div>
    );
  }

  return (
    <div className="glass-card p-4 space-y-4">
      <div className="flex items-center gap-2">
        <span className="section-title">Pending Questions</span>
        <span
          className="text-xs px-1.5 py-0.5 rounded-full font-mono"
          style={{ background: "var(--color-brand-muted)", color: "var(--color-brand)" }}
        >
          {questions.length}
        </span>
      </div>

      <ul className="space-y-4">
        {questions.map((q) => (
          <li
            key={q.id}
            className="space-y-2 pb-3 border-b last:border-b-0"
            style={{
              borderColor: "var(--color-border)",
              opacity: flash[q.id] === "success" ? 0.4 : 1,
              transition: "opacity 0.4s",
            }}
          >
            <p className="text-xs font-medium" style={{ color: "var(--color-text-primary)" }}>
              {q.text}
            </p>
            {q.hint && (
              <p className="text-xs italic" style={{ color: "var(--color-text-muted)" }}>
                {q.hint}
              </p>
            )}

            {q.type === "choice" && q.choices ? (
              <div className="flex flex-wrap gap-1.5">
                {q.choices.map((c) => (
                  <button
                    key={c}
                    onClick={() => setAnswers((a) => ({ ...a, [q.id]: c }))}
                    className="px-2.5 py-1 rounded-lg text-xs transition-all"
                    style={{
                      background: answers[q.id] === c ? "var(--color-brand)" : "var(--color-glass)",
                      color: answers[q.id] === c ? "#000" : "var(--color-text-secondary)",
                      border: "1px solid var(--color-border)",
                    }}
                  >
                    {c}
                  </button>
                ))}
              </div>
            ) : (
              <input
                type="text"
                value={answers[q.id] ?? ""}
                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                onKeyDown={(e) => e.key === "Enter" && submitAnswer(q)}
                placeholder="Type your answer…"
                className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                style={{
                  background: "var(--color-glass)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-primary)",
                }}
              />
            )}

            <div className="flex items-center gap-2">
              <button
                onClick={() => submitAnswer(q)}
                disabled={!answers[q.id]?.trim() || submitting[q.id]}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                style={{
                  background: answers[q.id]?.trim() ? "var(--color-brand)" : "var(--color-glass)",
                  color: answers[q.id]?.trim() ? "#000" : "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                }}
              >
                {submitting[q.id] ? "Sending…" : "Answer"}
              </button>
              {flash[q.id] === "success" && (
                <span className="text-xs" style={{ color: "var(--color-brand)" }}>Answered ✓</span>
              )}
              {flash[q.id] === "error" && (
                <span className="text-xs" style={{ color: "#EF4444" }}>Failed. Retry.</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
