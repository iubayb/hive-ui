import { BottomNav } from "@/components/BottomNav";
import { SseProvider } from "@/components/SseProvider";

export default function HiveLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <SseProvider />
      <div className="min-h-screen pb-16">{children}</div>
      <BottomNav />
    </>
  );
}
