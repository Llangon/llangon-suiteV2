import { json, portalEnv, requireSync } from "../../../lib/portal-server";

type FileInput = { id: string; name: string; extension?: string; size_bytes?: number; content_type?: string; sort_order?: number };

export async function POST(request: Request) {
  if (!requireSync(request)) return json({ error: "No autorizado." }, 401);
  const input = await request.json().catch(() => null) as null | Record<string, unknown>;
  if (!input || !input.id || !input.slug || !input.model || !input.access_salt || !input.access_hash) {
    return json({ error: "Publicación incompleta." }, 400);
  }
  const now = new Date().toISOString();
  const db = portalEnv().DB;
  await db.prepare(`
    INSERT INTO publications (id, slug, client_label, model_json, access_salt, access_hash, access_iterations, status, created_at, updated_at, published_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'uploading', ?, ?, NULL)
    ON CONFLICT(id) DO UPDATE SET slug=excluded.slug, client_label=excluded.client_label,
      model_json=excluded.model_json, access_salt=excluded.access_salt, access_hash=excluded.access_hash,
      access_iterations=excluded.access_iterations, status='uploading', updated_at=excluded.updated_at
  `).bind(
    String(input.id), String(input.slug), String(input.client_label || ""), JSON.stringify(input.model),
    String(input.access_salt), String(input.access_hash), Number(input.access_iterations), now, now,
  ).run();
  await db.prepare("DELETE FROM publication_files WHERE publication_id = ?").bind(String(input.id)).run();
  const files = Array.isArray(input.files) ? input.files as FileInput[] : [];
  for (const [index, file] of files.entries()) {
    const objectKey = `publications/${input.id}/${file.id}`;
    await db.prepare(`
      INSERT INTO publication_files (id, publication_id, name, extension, size_bytes, object_key, content_type, sort_order)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).bind(
      String(file.id), String(input.id), String(file.name), String(file.extension || ""), Number(file.size_bytes || 0),
      objectKey, String(file.content_type || "application/octet-stream"), Number(file.sort_order ?? index),
    ).run();
  }
  return json({ id: input.id, slug: input.slug, upload_files: files.map((file) => ({ id: file.id, path: `/api/admin/publications/${input.id}/files/${file.id}` })) });
}
