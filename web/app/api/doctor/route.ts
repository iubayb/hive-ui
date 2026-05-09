import { NextResponse } from "next/server";

const BACKEND = process.env.HIVE_BACKEND_URL ?? "http://localhost:8888";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/doctor/status`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 502 });
  }
}
