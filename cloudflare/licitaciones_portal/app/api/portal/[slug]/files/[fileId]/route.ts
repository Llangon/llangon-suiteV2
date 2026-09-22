import { json, portalEnv, publicationBySlug, readSession, recordEvent } from "../../../../../lib/portal-server";

export async function GET(request: Request, context: { params: Promise<{ slug: string; fileId: string }> }) {
  const { slug, fileId } = await context.params;
  const publication = await publicationBySlug(slug);
  if (!publication) return json({ error: "Publicación no encontrada." }, 404);
  const session = await readSession(request, String(publication.id));
  if (!session) return json({ error: "Acceso requerido." }, 401);
  const file = await portalEnv().DB.prepare(
    "SELECT * FROM publication_files WHERE id = ? AND publication_id = ?",
  ).bind(fileId, publication.id).first<Record<string, unknown>>();
  if (!file) return json({ error: "Fichero no encontrado." }, 404);
  const object = await portalEnv().FILES.get(String(file.object_key));
  if (!object) return json({ error: "Fichero no disponible." }, 404);
  await recordEvent(String(publication.id), session.visitorId, "download", { id: String(file.id), name: String(file.name) });
  const safeName = String(file.name).replace(/[\r\n"]/g, "_");
  return new Response(object.body, {
    headers: {
      "Content-Type": String(file.content_type),
      "Content-Length": String(file.size_bytes),
      "Content-Disposition": `attachment; filename="${safeName}"; filename*=UTF-8''${encodeURIComponent(safeName)}`,
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
