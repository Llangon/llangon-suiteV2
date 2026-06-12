# Precheck noticias Markdown

Este documento inventaria el flujo actual de noticias antes de introducir Markdown seguro.

Es una fase preparatoria. No implementa Markdown, no anade parser, no anade sanitizador, no cambia SQLite, no cambia endpoints, no cambia respuestas JSON y no cambia el frontend.

## Estado actual

Tabla SQLite:

- `noticias`;
- `id`;
- `title`;
- `slug` con `UNIQUE`;
- `excerpt`;
- `content`;
- `category`;
- `tags`;
- `featured_image`;
- `status`;
- `is_featured`;
- `published_at`;
- `author`;
- `created_at`;
- `updated_at`.

Estados actuales:

- `draft`;
- `published`;
- `archived`.

Funciones backend:

- `slugify()`;
- `normalize_news_status()`;
- `news_to_dict()`;
- `require_news_manager()`;
- `api_public_news()`;
- `api_list_news()`;
- `read_news_payload()`;
- `api_create_news()`;
- `api_update_news()`;
- `api_delete_news()`.

Endpoints:

- `GET /api/public/noticias`;
- `GET /api/news`;
- `POST /api/news`;
- `PATCH /api/news/{id}`;
- `DELETE /api/news/{id}`;
- rutas publicas `/noticias` y `/noticias/{slug}`.

Frontend privado:

- formulario `#news-form`;
- `saveNews()`;
- `loadNewsAdmin()`;
- `renderNewsAdmin()`;
- `editNews()`;
- `deleteNews()`;
- campo actual `content`.

Frontend publico:

- `public.js`;
- `fetch("/api/public/noticias")`;
- `newsCards()`;
- `newsDetailPage()`;
- `escapeHtml()`;
- render de `content` como parrafos de texto escapado.

Firebase:

- `firebase/public_firebase/static/public.js`;
- intenta cargar `/api/public/noticias` en el mismo origen;
- si no hay API, usa placeholders locales.

Contratos futuros existentes:

- `NewsArticle` en `core/models.py`;
- `NewsRenderer` en `core/news_contracts.py`.

## Invariantes que no deben romperse

- El contenido actual debe seguir tratandose como texto plano hasta que exista render Markdown seguro.
- No debe permitirse HTML libre.
- `POST /api/news`, `PATCH /api/news/{id}` y `DELETE /api/news/{id}` deben seguir protegidos por CSRF.
- `GET /api/public/noticias` debe seguir siendo publico y de solo lectura.
- `slug` debe seguir siendo unico.
- `published` sin fecha debe seguir asignando `published_at`.
- La web publica debe seguir escapando `title`, `excerpt`, `category` y `content`.
- Firebase no debe romperse si no existe API en su origen.
- La futura transicion debe conservar compatibilidad con el campo `content` o definir migracion explicita.

## Riesgos antes de Markdown

- Un parser Markdown mal configurado podria permitir HTML embebido.
- Un sanitizador incompleto podria dejar atributos peligrosos.
- Renderizar HTML con `innerHTML` sin sanitizar abriria XSS.
- Imagenes externas pueden introducir tracking o contenido no deseado.
- Cambiar `content` a `content_markdown` requiere migracion SQLite.
- Publicar HTML renderizado cacheado requeriria decidir si se guarda en SQLite.
- Firebase necesita una estrategia de datos: API publica, JSON exportado, Cloud Function o publicacion estatica.

## Estrategia recomendada antes de implementar

Orden seguro:

1. Elegir parser Markdown que permita desactivar HTML crudo.
2. Elegir sanitizador con allowlist explicita.
3. Definir etiquetas permitidas.
4. Definir atributos permitidos.
5. Definir esquemas de URL permitidos: `http` y `https`.
6. Decidir si imagen destacada sigue como campo estructurado.
7. Crear tests hostiles antes de conectar el render a la UI.
8. Mantener `content` durante una fase de compatibilidad o planificar migracion.
9. Renderizar Markdown en una capa aislada antes de exponerlo a `public.js`.
10. No introducir editor visual hasta que el render seguro este probado.

## Tests minimos futuros

- Markdown basico: titulos, listas, enlaces y negritas.
- HTML crudo debe escaparse o eliminarse.
- `javascript:` en enlaces debe eliminarse.
- Eventos inline como `onclick` deben eliminarse.
- Imagenes con esquemas no permitidos deben eliminarse.
- El resultado sanitizado no debe contener `<script>`.
- El render publico no debe mostrar HTML no sanitizado.
- Las respuestas JSON existentes no deben perder campos actuales.

## Fuera de este precheck

- No se implementa Markdown.
- No se anade parser Markdown.
- No se anade sanitizador.
- No se cambia SQLite.
- No se cambia `api_public_news()`.
- No se cambia `api_create_news()`.
- No se cambia `api_update_news()`.
- No se cambia `public.js`.
- No se cambia Firebase.
