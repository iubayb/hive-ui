import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.HIVE_BACKEND_URL ?? "http://localhost:8888";

const ARENA_PATHS: Record<string, string> = {
  status: "/api/arena/status",
  results: "/api/arena/results",
};

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ type: string }> }
) {
  const { type } = await params;
  const backendPath = ARENA_PATHS[type] ?? `/api/arena/${type}`;
  try {
    const res = await fetch(`${BACKEND}${backendPath}`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 502 });
  }
}
