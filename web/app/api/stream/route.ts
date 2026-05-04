export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL =
  process.env.HIVE_BACKEND_URL || "http://localhost:8888";

export async function GET() {
  const enc = new TextEncoder();

  const stream = new ReadableStream({
    async start(ctrl) {
      const send = (d: string) => {
        try {
          ctrl.enqueue(enc.encode(`data: ${d}\n\n`));
        } catch {}
      };

      let upstream: Response;
      try {
        upstream = await fetch(`${BACKEND_URL}/status/stream`, {
          cache: "no-store",
          headers: { Accept: "text/event-stream" },
        });
      } catch (e) {
        // Backend unreachable — send error event and close
        send(JSON.stringify({ type: "error", msg: String(e) }));
        ctrl.close();
        return;
      }

      if (!upstream.ok || !upstream.body) {
        send(
          JSON.stringify({
            type: "error",
            msg: `Backend responded ${upstream.status}`,
          })
        );
        ctrl.close();
        return;
      }

      // SSE framing: accumulate chunks, split on \n\n boundaries
      const reader = upstream.body.getReader();
      const dec = new TextDecoder();
      let buf = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buf += dec.decode(value, { stream: true });

          // Split on double-newline SSE frame boundaries
          const frames = buf.split(/\n\n/);
          buf = frames.pop() ?? "";

          for (const frame of frames) {
            const trimmed = frame.trim();
            if (!trimmed) continue;

            // Skip SSE comment lines (heartbeats like ": ping")
            if (trimmed.startsWith(":")) continue;

            // Extract "data: ..." lines
            const dataLine = trimmed
              .split("\n")
              .find((l) => l.startsWith("data:"));
            if (!dataLine) continue;

            const raw = dataLine.slice(5).trim(); // strip "data:"
            try {
              const parsed = JSON.parse(raw);
              // Wrap in the {type:"status", data} envelope SseProvider expects
              send(JSON.stringify({ type: "status", data: parsed, ts: Date.now() }));
            } catch {
              // Not valid JSON — forward as-is (shouldn't happen with Python backend)
              send(JSON.stringify({ type: "error", msg: `Bad JSON: ${raw}` }));
            }
          }
        }
      } catch (e) {
        send(JSON.stringify({ type: "error", msg: String(e) }));
      } finally {
        reader.releaseLock();
        ctrl.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}
