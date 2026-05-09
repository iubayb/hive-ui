export const runtime = "edge";
export const dynamic = "force-dynamic";

const KEY = process.env.OPENROUTER_API_KEY ?? "";
const MODEL = process.env.OPENROUTER_MODEL ?? "meta-llama/llama-3.3-70b-instruct:free";

export async function POST(req: Request) {
  const { messages, system } = await req.json();
  if (!KEY)
    return new Response(JSON.stringify({ error: "no API key" }), { status: 500 });

  const body = {
    model: MODEL,
    stream: true,
    max_tokens: 512,
    messages: system
      ? [{ role: "system", content: system }, ...messages]
      : messages,
  };

  const upstream = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${KEY}`,
      "HTTP-Referer": "https://hive-ui.vercel.app",
      "X-Title": "Hive UI",
    },
    body: JSON.stringify(body),
  });

  if (!upstream.ok) {
    const err = await upstream.text();
    return new Response(JSON.stringify({ error: err }), { status: upstream.status });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
