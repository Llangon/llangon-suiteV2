import { json, portalEnv, requireSync } from "../../../../../lib/portal-server";

export async function GET(request: Request, context: { params: Promise<{ publicationId: string }> }) {
  if (!requireSync(request)) return json({ error: "No autorizado." }, 401);
  const { publicationId } = await context.params;
  const after = new URL(request.url).searchParams.get("after") || "";
  const result = await portalEnv().DB.prepare(`
    SELECT id, event_type, file_id, file_name, visitor_id, occurred_at
    FROM portal_events WHERE publication_id = ? AND occurred_at > ?
    ORDER BY occurred_at, id LIMIT 1000
  `).bind(publicationId, after).all();
  return json({ items: result.results });
}
