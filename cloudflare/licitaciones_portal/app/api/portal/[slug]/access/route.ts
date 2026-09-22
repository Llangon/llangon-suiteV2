import { createSession, json, pbkdf2, publicationBySlug, recordEvent, safeEqual } from "../../../../lib/portal-server";

export async function POST(request: Request, context: { params: Promise<{ slug: string }> }) {
  const { slug } = await context.params;
  const publication = await publicationBySlug(slug);
  if (!publication) return json({ error: "Publicación no encontrada." }, 404);
  const body = await request.json().catch(() => ({})) as { code?: string };
  const code = String(body.code || "").trim().toUpperCase();
  const calculated = await pbkdf2(code, String(publication.access_salt), Number(publication.access_iterations));
  if (!safeEqual(calculated, String(publication.access_hash))) return json({ error: "La palabra clave no es correcta." }, 401);
  const session = await createSession(String(publication.id));
  await recordEvent(String(publication.id), session.visitorId, "access");
  return json({ ok: true }, 200, { "Set-Cookie": `llangon_portal=${session.token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=43200` });
}
