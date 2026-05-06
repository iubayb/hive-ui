import { BottomNav } from "@/components/BottomNav";
import { SseProvider } from "@/components/SseProvider";
import { ActiveTaskBar } from "@/components/ActiveTaskBar";

export default function HiveLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <SseProvider />
      <ActiveTaskBar />
      {/* pt-9 clears the 36px fixed ActiveTaskBar; pb-16 clears the fixed BottomNav */}
      <div className="min-h-screen pt-9 pb-16">{children}</div>
      <BottomNav />
    </>
  );
}
