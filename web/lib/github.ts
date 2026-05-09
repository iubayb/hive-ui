const GITHUB_TOKEN = process.env.GITHUB_TOKEN ?? "";
const DEFAULT_OWNER = process.env.GITHUB_OWNER ?? "iubayb";
const DEFAULT_REPO = process.env.GITHUB_REPO ?? "hive-ui";

export interface GHOpts {
  owner?: string;
  repo?: string;
  revalidate?: number;
}

export async function ghFetch<T>(
  path: string,
  opts: GHOpts & RequestInit = {}
): Promise<T> {
  const { owner = DEFAULT_OWNER, repo = DEFAULT_REPO, revalidate = 60, ...rest } = opts;
  const url = `https://api.github.com/repos/${owner}/${repo}${path}`;
  const headers: Record<string, string> = {
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  if (GITHUB_TOKEN) headers.Authorization = `Bearer ${GITHUB_TOKEN}`;
  const res = await fetch(url, {
    ...rest,
    headers: { ...headers, ...(rest.headers as Record<string, string> ?? {}) },
    next: { revalidate },
  });
  if (!res.ok) throw new Error(`GitHub ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}
