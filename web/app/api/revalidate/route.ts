import { NextRequest, NextResponse } from "next/server";
import { revalidatePath } from "next/cache";

const SECRET = process.env.REVALIDATE_SECRET ?? "";

export async function POST(req: NextRequest) {
  const token =
    req.nextUrl.searchParams.get("token") ??
    req.headers.get("x-revalidate-token") ??
    "";
  if (SECRET && token !== SECRET)
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const paths = ["/hive", "/hive/issues", "/hive/pulls", "/hive/commits", "/hive/workflows"];
  paths.forEach((p) => revalidatePath(p));

  return NextResponse.json({ revalidated: true, paths, ts: Date.now() });
}
