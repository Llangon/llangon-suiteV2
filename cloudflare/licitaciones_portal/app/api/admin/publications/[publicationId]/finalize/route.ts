import { json, portalEnv, requireSync } from "../../../../../lib/portal-server";

export async function POST(request: Request, context: { params: Promise<{ publicationId: string }> }) {
  if (!requireSync(request)) return json({ error: "No autorizado." }, 401);
  const { publicationId } = await context.params;
  const files = await portalEnv().DB.prepare(
    "SELECT object_key FROM publication_files WHERE publication_id = ?",
  ).bind(publicationId).all<{ object_key: string }>();
  for (const file of files.results) {
    if (!await portalEnv().FILES.head(file.object_key)) return json({ error: "Todavía faltan documentos por cargar." }, 409);
  }
  const now = new Date().toISOString();
  const updated = await portalEnv().DB.prepare(
    "UPDATE publications SET status = 'published', published_at = COALESCE(published_at, ?), updated_at = ? WHERE id = ?",
  ).bind(now, now, publicationId).run();
  if (!updated.meta.changes) return json({ error: "Publicación no encontrada." }, 404);
  return json({ ok: true, id: publicationId, files: files.results.length });
}
