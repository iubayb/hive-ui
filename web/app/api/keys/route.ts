export const runtime = "nodejs";

import { NextRequest, NextResponse } from "next/server";
import {
  createCipheriv,
  createDecipheriv,
  randomBytes,
} from "crypto";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { homedir } from "os";
import { join } from "path";

const KEYS_FILE = join(homedir(), ".config", "research-hive", "keys.json");
const ENC_KEY = Buffer.from(
  (process.env.VAULT_ENCRYPTION_KEY ?? "").padEnd(64, "0"),
  "hex"
).slice(0, 32);

function load(): Record<string, string> {
  try {
    if (!existsSync(KEYS_FILE)) return {};
    return JSON.parse(readFileSync(KEYS_FILE, "utf-8")).keys ?? {};
  } catch { return {}; }
}

function save(keys: Record<string, string>) {
  try {
    mkdirSync(join(homedir(), ".config", "research-hive"), { recursive: true });
    writeFileSync(KEYS_FILE, JSON.stringify({ keys }, null, 2));
  } catch {}
}

function enc(text: string): string {
  const iv = randomBytes(12);
  const c = createCipheriv("aes-256-gcm", ENC_KEY, iv);
  const data = Buffer.concat([c.update(text, "utf8"), c.final()]);
  const tag = c.getAuthTag();
  return `${iv.toString("hex")}:${tag.toString("hex")}:${data.toString("hex")}`;
}

function dec(s: string): string {
  const [ivH, tagH, dataH] = s.split(":");
  const d = createDecipheriv("aes-256-gcm", ENC_KEY, Buffer.from(ivH, "hex"));
  d.setAuthTag(Buffer.from(tagH, "hex"));
  return d.update(Buffer.from(dataH, "hex")).toString("utf8") + d.final("utf8");
}

export async function GET() {
  return NextResponse.json({ keys: Object.keys(load()) });
}

export async function POST(req: NextRequest) {
  const { name, value } = await req.json();
  if (!name || !value)
    return NextResponse.json({ error: "name and value required" }, { status: 400 });
  const keys = load();
  keys[name] = enc(value);
  save(keys);
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: NextRequest) {
  const { name } = await req.json();
  if (!name) return NextResponse.json({ error: "name required" }, { status: 400 });
  const keys = load();
  delete keys[name];
  save(keys);
  return NextResponse.json({ ok: true });
}
