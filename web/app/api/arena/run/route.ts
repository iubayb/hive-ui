import { NextResponse } from "next/server";

const BACKEND = process.env.HIVE_BACKEND_URL ?? "http://localhost:8888";

export async function POST() {
  try {
    const res = await fetch(`${BACKEND}/api/arena/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 502 });
  }
}
