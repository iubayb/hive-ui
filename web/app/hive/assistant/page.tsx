import { PageHeader } from "@/components/PageHeader";
import { AIAssistant } from "@/components/AIAssistant";

export default function AssistantPage() {
  return (
    <div
      className="flex flex-col"
      style={{ height: "calc(100dvh - 100px)", background: "var(--color-surface)" }}
    >
      <PageHeader icon="◈" title="AI Assistant" />
      <div className="flex-1 overflow-hidden">
        <AIAssistant />
      </div>
    </div>
  );
}
