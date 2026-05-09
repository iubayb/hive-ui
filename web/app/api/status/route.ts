export const dynamic = "force-dynamic";

const BACKEND = process.env.HIVE_BACKEND_URL ?? "http://localhost:8888";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/status`, { cache: "no-store" });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json({ error: "Backend unavailable" }, { status: 502 });
  }
}
