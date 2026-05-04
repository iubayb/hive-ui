import { AIAssistant } from "@/components/AIAssistant";

export default function AssistantPage() {
  return (
    <div
      className="flex flex-col"
      style={{ height: "calc(100vh - 56px)", background: "var(--color-surface)" }}
    >
      <header
        className="sticky top-0 z-40 px-4 py-3 flex items-center gap-2 border-b shrink-0"
        style={{
          background: "rgba(9,9,11,0.95)",
          borderColor: "var(--color-border)",
          backdropFilter: "blur(16px)",
        }}
      >
        <span className="text-lg">◈</span>
        <span className="font-display font-semibold text-sm">AI Assistant</span>
      </header>
      <div className="flex-1 overflow-hidden">
        <AIAssistant />
      </div>
    </div>
  );
}
