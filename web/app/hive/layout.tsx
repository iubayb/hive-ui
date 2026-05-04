import { BottomNav } from "@/components/BottomNav";
import { SseProvider } from "@/components/SseProvider";
import { ConnectionBadge } from "@/components/ConnectionBadge";

export default function HiveLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <SseProvider />
      <ConnectionBadge />
      <div className="min-h-screen pb-16">{children}</div>
      <BottomNav />
    </>
  );
}
