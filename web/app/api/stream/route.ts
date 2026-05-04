export const runtime = "edge";
export const dynamic = "force-dynamic";

const STATUS_URL =
  "https://raw.githubusercontent.com/iubayb/hive-ui/status/hive-status.json";
const POLL_MS = 5000;

export async function GET() {
  const enc = new TextEncoder();
  let closed = false;

  const stream = new ReadableStream({
    async start(ctrl) {
      const send = (d: string) => {
        if (closed) return;
        try { ctrl.enqueue(enc.encode(`data: ${d}\n\n`)); } catch {}
      };

      send(JSON.stringify({ type: "connected", ts: Date.now() }));

      while (!closed) {
        await new Promise((r) => setTimeout(r, POLL_MS));
        try {
          const res = await fetch(STATUS_URL, { cache: "no-store" });
          if (res.ok) {
            const data = await res.json();
            send(JSON.stringify({ type: "status", data, ts: Date.now() }));
          }
        } catch (e) {
          send(JSON.stringify({ type: "error", msg: String(e) }));
        }
      }
    },
    cancel() { closed = true; },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
