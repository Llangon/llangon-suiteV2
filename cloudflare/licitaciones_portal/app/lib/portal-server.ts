import { env } from "cloudflare:workers";

export type PortalEnv = {
  DB: D1Database;
  FILES: R2Bucket;
  PORTAL_SYNC_SECRET?: string;
  PORTAL_SESSION_SECRET?: string;
};

export const portalEnv = () => env as unknown as PortalEnv;

const encoder = new TextEncoder();

function base64url(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function decode64(value: string): Uint8Array {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const binary = atob(normalized);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

export async function pbkdf2(code: string, salt: string, iterations: number): Promise<string> {
  const key = await crypto.subtle.importKey("raw", encoder.encode(code), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: decode64(salt), iterations },
    key,
    256,
  );
  return base64url(new Uint8Array(bits));
}

export function safeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  return difference === 0;
}

async function hmac(value: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return base64url(new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(value))));
}

export async function createSession(publicationId: string): Promise<{ token: string; visitorId: string }> {
  const secret = portalEnv().PORTAL_SESSION_SECRET;
  if (!secret) throw new Error("PORTAL_SESSION_SECRET no está configurado");
  const visitorId = crypto.randomUUID();
  const payload = base64url(encoder.encode(JSON.stringify({ publicationId, visitorId, expires: Date.now() + 12 * 60 * 60 * 1000 })));
  return { token: `${payload}.${await hmac(payload, secret)}`, visitorId };
}

export async function readSession(request: Request, publicationId: string): Promise<{ visitorId: string } | null> {
  const secret = portalEnv().PORTAL_SESSION_SECRET;
  const cookie = request.headers.get("cookie")?.split(";").map((part) => part.trim()).find((part) => part.startsWith("llangon_portal="))?.slice(15);
  if (!secret || !cookie) return null;
  const [payload, signature] = cookie.split(".");
  if (!payload || !signature || !safeEqual(await hmac(payload, secret), signature)) return null;
  try {
    const parsed = JSON.parse(new TextDecoder().decode(decode64(payload))) as { publicationId: string; visitorId: string; expires: number };
    return parsed.publicationId === publicationId && parsed.expires > Date.now() ? { visitorId: parsed.visitorId } : null;
  } catch { return null; }
}

export function requireSync(request: Request): boolean {
  const configured = portalEnv().PORTAL_SYNC_SECRET;
  const supplied = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "") || "";
  return Boolean(configured && safeEqual(configured, supplied));
}

export function json(data: unknown, status = 200, headers?: HeadersInit): Response {
  return Response.json(data, { status, headers: { "Cache-Control": "no-store", ...headers } });
}

export async function publicationBySlug(slug: string) {
  return portalEnv().DB.prepare("SELECT * FROM publications WHERE slug = ? AND status = 'published'").bind(slug).first<Record<string, unknown>>();
}

export async function recordEvent(publicationId: string, visitorId: string, eventType: "access" | "download", file?: { id: string; name: string }) {
  const occurredAt = new Date().toISOString();
  await portalEnv().DB.prepare(
    "INSERT INTO portal_events (id, publication_id, event_type, file_id, file_name, visitor_id, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
  ).bind(crypto.randomUUID(), publicationId, eventType, file?.id || null, file?.name || null, visitorId, occurredAt).run();
}
