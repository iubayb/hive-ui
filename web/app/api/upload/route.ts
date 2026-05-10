import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const backendUrl = process.env.HIVE_BACKEND_URL ?? "http://localhost:8888";

  try {
    const formData = await req.formData();

    // Re-stream the multipart form to the backend
    const upstream = await fetch(`${backendUrl}/api/upload`, {
      method: "POST",
      body: formData,
    });

    if (!upstream.ok) {
      const text = await upstream.text();
      return NextResponse.json(
        { error: `Backend upload failed: ${upstream.status}`, detail: text },
        { status: upstream.status }
      );
    }

    const json = await upstream.json();
    return NextResponse.json(json);
  } catch (err: any) {
    // Backend unreachable — return a synthetic response so the UI can still
    // show the attachment chip without a hard error.
    return NextResponse.json(
      { error: "upload_unavailable", message: err?.message ?? "unknown" },
      { status: 502 }
    );
  }
}
