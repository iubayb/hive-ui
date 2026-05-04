import { NextRequest, NextResponse } from "next/server";
import { ghFetch } from "@/lib/github";

const ROUTES: Record<string, { path: string; revalidate: number }> = {
  issues:    { path: "/issues?state=open&per_page=30",   revalidate: 60 },
  pulls:     { path: "/pulls?state=open&per_page=30",    revalidate: 60 },
  commits:   { path: "/commits?per_page=30",             revalidate: 120 },
  workflows: { path: "/actions/runs?per_page=15",        revalidate: 30 },
  contents:  { path: "/contents",                        revalidate: 120 },
};

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ route: string[] }> }
) {
  const { route } = await params;
  const [resource, ...rest] = route;
  const owner = req.nextUrl.searchParams.get("owner") ?? undefined;
  const repo  = req.nextUrl.searchParams.get("repo")  ?? undefined;

  try {
    const cfg = ROUTES[resource];
    const path = cfg ? cfg.path : `/${resource}/${rest.join("/")}`;
    const revalidate = cfg?.revalidate ?? 60;
    const data = await ghFetch(path, { owner, repo, revalidate });
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 502 });
  }
}
