export const runtime = "edge";
export const dynamic = "force-dynamic";

const STATUS_URL =
  "https://raw.githubusercontent.com/iubayb/hive-ui/status/hive-status.json";

export async function GET() {
  const enc = new TextEncoder();

  const stream = new ReadableStream({
    async start(ctrl) {
      const write = (s: string) => {
        try { ctrl.enqueue(enc.encode(s)); } catch {}
      };

      // Tell the browser's EventSource to reconnect every 5 s after stream closes
      write("retry: 5000\n\n");

      try {
        const res = await fetch(STATUS_URL, { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          write(
            `data: ${JSON.stringify({ type: "status", data, ts: Date.now() })}\n\n`
          );
        } else {
          write(
            `data: ${JSON.stringify({ type: "error", msg: `HTTP ${res.status}` })}\n\n`
          );
        }
      } catch (e) {
        write(
          `data: ${JSON.stringify({ type: "error", msg: String(e) })}\n\n`
        );
      }

      ctrl.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
