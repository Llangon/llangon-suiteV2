# Precheck CSRF global

Este documento inventaria la proteccion CSRF actual antes de pasar de una allowlist explicita a una politica global.

Es una fase preparatoria. No se activa CSRF global, no se cambia `csrf_required_for_path()`, no se cambia `require_csrf_token()`, no se cambia frontend, no se cambian endpoints, no se cambian respuestas JSON, no se toca SQLite y no se cambia Firebase.

## Estado actual

Helpers puros:

- `generate_csrf_token()` en `webapp/infonalia_webapp/csrf.py`;
- `validate_csrf_token()` en `webapp/infonalia_webapp/csrf.py`;
- `is_mutating_method()` en `webapp/infonalia_webapp/csrf.py`;
- `normalize_path_for_csrf()` en `webapp/infonalia_webapp/csrf.py`;
- `is_csrf_required()` en `webapp/infonalia_webapp/csrf.py`.

Integracion real en `app.py`:

- constante de header: `CSRF_HEADER = "X-CSRF-Token"`;
- sesion firmada en cookie `infonalia_session`;
- token dentro del payload firmado de sesion;
- entrega del token en `/api/me`;
- generacion perezosa de token para sesiones antiguas en `current_user()`;
- validacion en `require_csrf_token()`;
- decision por ruta en `InfonaliaHandler.csrf_required_for_path()`.

Frontend privado:

- `loadMe()` lee `/api/me`;
- `appState.csrfToken` guarda el token en memoria;
- `csrfHeaders()` genera `X-CSRF-Token`;
- las llamadas mutantes conocidas usan `csrfHeaders()`.

## Cobertura actual

Rutas protegidas de forma explicita:

- `POST /logout`;
- `POST /api/licitaciones`;
- `PATCH /api/licitaciones/{id}`;
- `DELETE /api/licitaciones/{id}`;
- `POST /api/licitaciones/{id}/descargar`;
- `POST /api/licitaciones/{id}/ia-preview`;
- `POST /api/licitaciones/{id}/ia-preview/email`;
- `POST /api/import/csv`;
- `POST /api/import/msg`;
- `POST /api/dias/{id}/revisado`;
- `POST /api/dias/{id}/desmarcar-revisado`;
- `POST /api/dias/{id}/enviar-nuria`;
- `DELETE /api/dias/{id}`;
- `POST /api/config/users`;
- `PATCH /api/config/users/{username}`;
- `DELETE /api/config/users/{username}`;
- `PATCH /api/config/settings`;
- `POST /api/config/test-smtp`;
- `POST /api/news`;
- `PATCH /api/news/{id}`;
- `DELETE /api/news/{id}`.

Rutas excluidas o sin CSRF:

- `POST /login`, porque no hay sesion autenticada previa y ya existe rate limiting;
- `GET /logout`, que devuelve `405 Method Not Allowed` y no borra cookie;
- endpoints GET privados de lectura: `/api/me`, `/api/dias`, `/api/licitaciones`, `/api/notificaciones`, `/api/config`, `/api/news` y `/api/health`;
- `GET /api/public/noticias`;
- rutas publicas y Firebase;
- rutas desconocidas, que deben seguir respondiendo `404 Not Found` y no convertirse en error CSRF.

Respuesta actual ante fallo:

- token ausente o invalido: `403 Forbidden`;
- token valido: se alcanza el endpoint real;
- usuario no autenticado: se mantiene `401 Unauthorized` o redireccion segun ruta actual.

## Que significaria CSRF global

Una futura fase de CSRF global no deberia ampliar comportamiento a ciegas. El objetivo seria sustituir la allowlist manual por una regla central:

- solo usuarios autenticados;
- solo metodos mutantes: `POST`, `PUT`, `PATCH` y `DELETE`;
- solo rutas privadas existentes;
- excepciones explicitas para login y rutas publicas;
- mantener logout protegido;
- mantener GET sin CSRF;
- mantener rutas desconocidas como `404 Not Found`.

El helper `is_csrf_required()` ya modela parte de esa politica, pero todavia no gobierna el enrutado real de `app.py`.

## Invariantes que no deben romperse

- `POST /login` debe seguir funcionando sin token CSRF.
- `POST /logout` debe seguir exigiendo token CSRF valido cuando hay sesion autenticada.
- `GET /logout` debe seguir sin borrar cookie.
- Las rutas publicas y Firebase no deben exigir token.
- Los endpoints GET privados no deben exigir token.
- Rutas desconocidas deben seguir respondiendo `404 Not Found`, no `403 Forbidden`.
- Las respuestas JSON de exito no deben cambiar.
- El frontend no debe usar `localStorage` para el token.
- `X-CSRF-Token` debe seguir siendo el header de envio.
- No se debe guardar CSRF en SQLite.
- Los tests no deben usar datos reales, red real, SMTP real ni descargadores reales.

## Riesgos antes de CSRF global

- Una validacion global demasiado temprana puede convertir errores 404 en 403.
- Una excepcion demasiado amplia puede dejar rutas mutantes sin proteger.
- Una excepcion demasiado estrecha puede romper login, rutas publicas o Firebase.
- Si aparece una nueva llamada mutante en `app.js` sin `csrfHeaders()`, una politica global la romperia.
- Si una ruta GET empieza a mutar estado, no quedara protegida por CSRF; debe cambiar a metodo mutante.
- Un XSS podria leer el token en memoria; CSRF no sustituye CSP ni sanitizacion.
- HTTPS/proxy sigue siendo necesario para exposicion fuera de entorno local/LAN.
- Mezclar CSRF global con refactor de `app.py` aumentaria el riesgo de regresiones.

## Estrategia recomendada antes de implementar

Orden seguro:

1. Mantener un listado de rutas privadas existentes y su metodo.
2. Crear tests de matriz para todos los endpoints mutantes conocidos.
3. Crear tests para `POST /login`, `POST /logout`, `GET /logout`, GET privados, rutas publicas y rutas desconocidas.
4. Auditar `app.js` para confirmar que toda llamada mutante usa `csrfHeaders()`.
5. Sustituir la allowlist solo cuando los tests cubran la semantica de ruta.
6. Mantener excepciones explicitas y pequenas.
7. Confirmar que no cambian respuestas JSON de exito.
8. Ejecutar checks completos antes de commit local.

## Tests existentes relevantes

- `test_csrf.py`, para helpers puros sin importar `app.py`;
- `test_csrf_private_mutations.py`, para endpoints mutantes privados protegidos;
- `test_import_endpoints.py`, para CSV y MSG con token valido, ausente e invalido;
- `test_download_endpoint.py`, para descarga con token valido, ausente e invalido;
- `test_login_security.py`, para login, logout y sesiones antiguas con token perezoso.

## Tests minimos futuros

- Todos los mutantes privados existentes deben devolver `403 Forbidden` sin token.
- Todos los mutantes privados existentes deben alcanzar endpoint con token valido.
- `POST /login` debe seguir sin CSRF.
- `POST /logout` debe mantener CSRF.
- `GET /logout` debe seguir devolviendo `405 Method Not Allowed`.
- `GET /api/public/noticias` debe seguir publico.
- GET privados de lectura deben seguir sin CSRF.
- `POST /api/unknown` debe seguir siendo `404 Not Found`.
- Una ruta publica futura no debe quedar protegida por accidente sin decision explicita.

## Fuera de este precheck

- No se activa CSRF global.
- No se cambia `csrf_required_for_path()`.
- No se cambia `require_csrf_token()`.
- No se cambia frontend.
- No se cambian endpoints.
- No se cambian respuestas JSON.
- No se toca SQLite.
- No se cambia Firebase.
- No se usan datos reales.
