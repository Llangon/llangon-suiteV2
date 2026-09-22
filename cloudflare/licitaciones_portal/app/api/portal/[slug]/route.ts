import { json, portalEnv, publicationBySlug, readSession } from "../../../lib/portal-server";

export async function GET(request: Request, context: { params: Promise<{ slug: string }> }) {
  const { slug } = await context.params;
  const publication = await publicationBySlug(slug);
  if (!publication) return json({ error: "Publicación no encontrada." }, 404);
  if (!await readSession(request, String(publication.id))) return json({ error: "Acceso requerido." }, 401);
  const files = await portalEnv().DB.prepare(
    "SELECT id, name, extension, size_bytes FROM publication_files WHERE publication_id = ? ORDER BY sort_order, name",
  ).bind(publication.id).all();
  return json({
    model: JSON.parse(String(publication.model_json)),
    client_label: publication.client_label,
    files: files.results,
  });
}
