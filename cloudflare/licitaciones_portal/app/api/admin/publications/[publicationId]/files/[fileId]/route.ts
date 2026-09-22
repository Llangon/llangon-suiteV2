import { json, portalEnv, requireSync } from "../../../../../../lib/portal-server";

export async function PUT(request: Request, context: { params: Promise<{ publicationId: string; fileId: string }> }) {
  if (!requireSync(request)) return json({ error: "No autorizado." }, 401);
  const { publicationId, fileId } = await context.params;
  const file = await portalEnv().DB.prepare(
    "SELECT object_key, size_bytes FROM publication_files WHERE id = ? AND publication_id = ?",
  ).bind(fileId, publicationId).first<Record<string, unknown>>();
  if (!file) return json({ error: "Fichero no registrado." }, 404);
  const declared = Number(file.size_bytes || 0);
  const supplied = Number(request.headers.get("content-length") || 0);
  if (declared && supplied && declared !== supplied) return json({ error: "El tamaño del fichero no coincide." }, 400);
  await portalEnv().FILES.put(String(file.object_key), request.body, {
    httpMetadata: { contentType: request.headers.get("content-type") || "application/octet-stream" },
  });
  return json({ ok: true, file_id: fileId });
}
