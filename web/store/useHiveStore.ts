"use client";

import { create } from "zustand";

export interface Achievement {
  id: string;
  ts: string;
  hive: string;
  agent: string;
  description: string;
  evidence?: string;
}

export interface Blocker {
  id: string;
  ts: string;
  hive: string;
  agent: string;
  description: string;
  severity: "critical" | "high" | "medium" | "low";
  status: "open" | "resolved";
  resolved_at?: string;
  resolution?: string;
  github_issue?: number;
}

export interface NextStep {
  id: string;
  ts: string;
  description: string;
  status: "pending" | "in_progress" | "done" | "cancelled";
  assigned_to?: string;
}

export interface HiveStatus {
  schema_version?: string;
  last_updated?: string;
  active_task?: string;
  hives?: {
    default?: {
      status: string;
      health_score: number;
      sessions: string[];
      current_goal: string;
      active_model: string;
      errors_last_hour: number;
      tasks_completed_today: number;
    };
  };
  achievements?: Achievement[];
  blockers?: Blocker[];
  next_steps?: NextStep[];
  metrics?: {
    tasks_completed_total: number;
    openrouter_calls_today: number;
  };
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export interface LogEntry {
  session: string;
  line: string;
  ts: string;
}

interface AppState {
  hiveStatus: HiveStatus | null;
  logs: LogEntry[];
  chatMessages: ChatMessage[];
  isAssistantThinking: boolean;
  isConnected: boolean;
  setHiveStatus: (s: HiveStatus) => void;
  appendLog: (e: LogEntry) => void;
  addChatMessage: (m: ChatMessage) => void;
  setAssistantThinking: (v: boolean) => void;
  setConnected: (v: boolean) => void;
  clearChat: () => void;
}

export const useHiveStore = create<AppState>((set) => ({
  hiveStatus: null,
  logs: [],
  chatMessages: [],
  isAssistantThinking: false,
  isConnected: false,
  setHiveStatus: (s) => set({ hiveStatus: s, isConnected: true }),
  appendLog: (e) => set((st) => ({ logs: [...st.logs.slice(-500), e] })),
  addChatMessage: (m) => set((st) => ({ chatMessages: [...st.chatMessages, m] })),
  setAssistantThinking: (v) => set({ isAssistantThinking: v }),
  setConnected: (v) => set({ isConnected: v }),
  clearChat: () => set({ chatMessages: [] }),
}));
