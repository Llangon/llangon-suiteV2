# Decisiones técnicas

## ADR-001 — No reescribir el proyecto desde cero

### Contexto

`Llangon-SuiteV2` ya contiene una app privada funcional con login, roles, importación CSV/MSG, gestión de licitaciones, calendario, notificaciones, noticias y descargas. Aunque `app.py` es monolítico, el flujo actual parece operativo y está conectado a documentación y hábitos de trabajo internos.

Reescribir desde cero aumentaría el riesgo de perder reglas de negocio implícitas: estados, revisión, agrupación por día Infonalia, carpetas, descargadores y notificaciones.

### Decisión

No reescribir el proyecto desde cero en esta etapa. Mantener la base actual y preparar refactors incrementales, documentados y verificables.

### Consecuencias

- Se conserva el comportamiento actual.
- Las mejoras deben entrar por fases pequeñas.
- Primero se documentan contratos, modelos y riesgos.
- Después se extraen piezas de `app.py` cuando existan tests suficientes.

### Riesgos

- El monolito seguirá pesando durante varias fases.
- Algunas mejoras serán más lentas por compatibilidad.
- Habrá que tener disciplina para no mezclar refactor con nuevas funciones.

### Alternativas descartadas

- Reescribir en Flask/FastAPI/Django ahora: descartado por riesgo y por instrucción explícita.
- Crear una app paralela nueva: descartado porque duplicaría reglas y podría romper operación.

## ADR-002 — Mantener SQLite de momento

### Contexto

La app usa SQLite local en `webapp/infonalia_webapp/data/infonalia.db`. El esquema se crea desde `init_db()` en `app.py`. La documentación ya reconoce que SQLite encaja para una instancia interna y concurrencia limitada.

Todavía no hay pruebas automatizadas ni migraciones formales.

### Decisión

Mantener SQLite de momento. No migrar a PostgreSQL, MySQL ni servicios externos hasta estabilizar modelo, migraciones y tests.

### Consecuencias

- La app mantiene portabilidad local.
- Los datos siguen siendo fáciles de copiar y respaldar.
- Las mejoras de esquema deberán hacerse con migraciones controladas.
- Antes de exponer la app a más usuarios habrá que revisar concurrencia, backups y bloqueo de escritura.

### Riesgos

- SQLite puede limitar concurrencia si crece el uso.
- Sin migraciones formales, los cambios de esquema son frágiles.
- El archivo de base de datos puede contener SMTP u otros datos sensibles.

### Alternativas descartadas

- Migrar ya a PostgreSQL: descartado porque sería demasiado pronto y obligaría a tocar demasiado flujo.
- Usar una base externa gestionada ahora: descartado hasta aclarar despliegue, usuarios y seguridad.

## ADR-003 — Preparar fuentes mediante modelo canónico

### Contexto

Actualmente las licitaciones entran por CSV y MSG/Infonalia. En el futuro podrían venir de Infonalia automatizado, PLACE u otras plataformas.

El flujo actual transforma directamente datos externos a payloads compatibles con la tabla `licitaciones`. No existe un modelo canónico explícito ni registro de fuente.

### Decisión

Preparar conceptualmente un modelo canónico de licitación antes de implementar nuevas fuentes. Las fuentes futuras deberán devolver candidatos normalizados y no escribir directamente en SQLite.

### Consecuencias

- Se podrá añadir `CsvSource`, `EmailInfonaliaSource`, `PlaceSource` u otras sin tocar media app.
- La deduplicación podrá centralizarse.
- Se podrán registrar importaciones y errores por fuente.
- El modelo actual de `licitaciones` podrá convivir temporalmente con campos futuros.

### Riesgos

- Si el modelo canónico se diseña demasiado ambicioso, puede retrasar mejoras.
- Si se diseña demasiado pobre, no resolverá duplicados entre fuentes.
- Habrá que mapear cuidadosamente campos actuales como `objeto`, `plataforma`, `enlace_perfil` y `ruta_carpeta`.

### Alternativas descartadas

- Añadir cada fuente directamente en `app.py`: descartado por acoplamiento.
- Crear tablas independientes por fuente: descartado porque complica la vista unificada y la deduplicación.

## ADR-004 — Preparar almacenamiento mediante StorageBackend

### Contexto

Ahora las descargas escriben en disco local o en rutas bajo Dropbox instalado localmente. `app.py` decide la carpeta, crea directorios y ejecuta scripts que escriben ficheros mediante rutas locales.

En el futuro se quiere que el administrador pulse Descargar y que los ficheros puedan guardarse directamente en Dropbox cuando la app esté subida a la red.

### Decisión

Preparar una abstracción `StorageBackend` antes de implementar Dropbox real. El diseño debe permitir `LocalStorage` y `DropboxStorage` sin reescribir la lógica principal de descarga.

### Consecuencias

- `ruta_carpeta` se mantiene por compatibilidad.
- Se recomienda añadir más adelante `storage_backend`, `storage_uri` y `file_manifest`.
- Las descargas futuras deberían escribir primero en un temporal controlado y confirmar almacenamiento antes de marcar éxito.
- Dropbox no debe depender de que el servidor tenga Dropbox Desktop instalado.

### Riesgos

- Los descargadores actuales están acoplados a carpetas locales.
- Adaptar a Dropbox requerirá decidir entre streaming directo o subida posterior desde temporal.
- Hay que evitar estados intermedios con ficheros parcialmente subidos.

### Alternativas descartadas

- Cambiar directamente `ruta_carpeta` para guardar enlaces Dropbox: descartado por riesgo de romper UI y datos existentes.
- Implementar Dropbox ahora: descartado por instrucción explícita y porque falta diseño de jobs/manifest.

## ADR-005 — Evolucionar noticias hacia Markdown seguro

### Contexto

Las noticias actuales usan campos `title`, `slug`, `excerpt`, `content`, `category`, `tags`, `featured_image`, `status`, `published_at` y se renderizan como texto escapado. El contenido es texto plano.

Se quiere evolucionar a un formato visual, con decisión provisional de Markdown seguro y posible editor visual en el futuro.

### Decisión

Evolucionar noticias hacia Markdown seguro, no HTML libre. Guardar Markdown como fuente principal y generar HTML solo si se sanitiza.

### Consecuencias

- El contenido será más expresivo sin abrir la puerta a HTML arbitrario.
- `imagen_destacada` debe seguir siendo campo estructurado.
- EasyMDE u otro editor debe esperar a que exista render seguro y tests.
- La web pública necesita una estrategia compatible con Firebase: JSON exportado, Cloud Function, API o publicación estática.

### Riesgos

- Un parser Markdown mal configurado podría permitir HTML.
- Si se usa `innerHTML` con HTML no sanitizado, habría riesgo de XSS.
- Imágenes externas pueden introducir tracking o contenido no deseado.

### Alternativas descartadas

- Permitir HTML libre: descartado por seguridad.
- Implementar EasyMDE ahora: descartado porque aún no existe la capa segura de renderizado.
- Mantener texto plano indefinidamente: descartado porque limita la evolución visual.

## ADR-006 — No implementar automatización ni Dropbox en esta fase

### Contexto

La fase actual es FASE 0: análisis técnico, documentación y preparación conceptual. Las futuras necesidades incluyen automatizar fuentes, integrar Dropbox y mejorar noticias, pero todavía no hay tests ni contratos estables.

### Decisión

No implementar automatización, conectores reales, Dropbox, EasyMDE ni jobs en esta fase. Crear solo documentación y, si fuera imprescindible, contratos puros sin conexión al flujo real. En esta ejecución se decide no crear contratos de código para minimizar superficie de cambio.

### Consecuencias

- El comportamiento de la app queda igual.
- Las siguientes fases tendrán un mapa técnico claro.
- Se reduce el riesgo de introducir cambios sin tests.

### Riesgos

- No se obtiene todavía mejora funcional visible.
- Algunas decisiones quedan pendientes hasta validar con el dueño del proyecto.
- Habrá que mantener disciplina para que la siguiente fase no mezcle demasiados objetivos.

### Alternativas descartadas

- Implementar Dropbox real ahora: descartado por riesgo y falta de StorageBackend.
- Implementar conectores a PLACE ahora: descartado por falta de modelo canónico e ImportRun.
- Añadir automatización desatendida ahora: descartado por seguridad y trazabilidad.

## ADR-007 — Crear contratos puros antes de refactorizar app.py

### Contexto

La Fase 0 dejó documentada la necesidad de separar fuentes de licitaciones, almacenamiento, descargas y noticias Markdown. Sin embargo, `app.py` sigue concentrando endpoints, SQLite, parsing, descargas y reglas de negocio actuales.

Refactorizar directamente `app.py` sin contratos previos aumentaría el riesgo de cambiar respuestas JSON, alterar endpoints o romper flujos operativos como CSV, MSG, noticias y descargas.

### Decisión

Crear primero contratos puros en `webapp/infonalia_webapp/core/`, sin conectarlos todavía al flujo real. Los contratos se limitan a dataclasses, enums y protocolos testeables con implementaciones falsas.

Esta fase añade:

- modelos de licitación candidata y normalizada;
- modelos de importación y resultado;
- modelos de almacenamiento y descarga;
- modelo de noticia Markdown;
- protocolos para fuentes, almacenamiento y renderizado de noticias.

### Consecuencias

- Existe una capa conceptual importable y testeable antes de tocar `app.py`.
- Los tests pueden validar contratos sin servidor, SQLite, red, Dropbox ni datos reales.
- Las fases posteriores tendrán un destino claro para extraer lógica de forma incremental.
- El comportamiento actual de la aplicación permanece intacto.

### Riesgos

- Los contratos pueden necesitar ajustes cuando se conecten a datos reales.
- Si se amplían demasiado pronto, podrían convertirse en diseño especulativo.
- Habrá que evitar que fases posteriores conecten estos contratos sin tests de compatibilidad sobre el flujo actual.

### Alternativas descartadas

- Refactorizar `app.py` directamente: descartado por riesgo sobre endpoints y respuestas actuales.
- Implementar fuentes reales ya: descartado porque primero hace falta estabilizar el contrato.
- Crear una capa de almacenamiento real ya: descartado porque Dropbox y jobs todavía no deben ejecutarse.
- Mantener solo documentación sin código: descartado en esta fase porque ya se necesita una base testeable mínima.

## ADR-008 — Endurecimiento web incremental antes de exponer la app

### Contexto

La app privada sigue pensada para uso local o LAN controlada. Aun así, antes de cualquier despliegue más amplio conviene reducir riesgos básicos: cabeceras ausentes, cookies construidas manualmente y falta de limitación de intentos de login.

No existe todavía una revisión completa de seguridad web, no hay CSRF y no se ha decidido una estrategia final de HTTPS/proxy.

### Decisión

Aplicar endurecimiento incremental y conservador:

- cabeceras de seguridad básicas en respuestas comunes;
- construcción centralizada de cookies de sesión;
- `Secure` configurable para no romper HTTP local;
- rate limiting simple en memoria para login fallido;
- tests puros y funcionales mínimos para evitar regresiones.

No se implementa CSRF ni CSP estricta en esta fase.

### Consecuencias

- La app reduce riesgos básicos sin cambiar URLs ni flujos normales.
- El login correcto, logout y sesiones deben seguir funcionando igual.
- El rate limiting protege frente a intentos repetidos simples en entorno local/LAN.
- La configuración sigue siendo compatible con HTTP local.

### Riesgos

- El rate limiting en memoria se pierde al reiniciar la app y no sirve para varios procesos.
- Sin HTTPS, la cookie no debe marcarse `Secure` en local, pero eso no protege transporte.
- Sin CSRF, las acciones autenticadas siguen necesitando una fase posterior de protección.
- Una CSP estricta podría romper la interfaz si se aplica sin auditoría.

### Alternativas descartadas

- Implementar CSRF ahora: descartado para mantener la fase pequeña y no tocar formularios/frontend.
- Activar `Secure` siempre: descartado porque rompería login en HTTP local.
- Añadir Redis u otro rate limiter distribuido: descartado por complejidad y porque la app sigue siendo local/LAN.
- Aplicar CSP estricta ahora: descartado hasta revisar scripts y estilos inline.

## ADR-009 — CSRF incremental para endpoints mutantes

### Contexto

La app privada ya tiene login, roles, cookies `HttpOnly` con `SameSite=Lax`, cabeceras básicas y rate limiting de login. Aun así, mientras existan endpoints autenticados que modifican estado mediante `POST`, `PATCH` o `DELETE`, sigue pendiente una protección CSRF explícita antes de exponer la app fuera de un entorno local/LAN controlado.

Los endpoints sensibles incluyen importación CSV/MSG, descargas, creación y edición de licitaciones, cambios de estado, gestión de noticias, usuarios, configuración SMTP, notificaciones y cierre de sesión.

### Decisión

Adoptar CSRF de forma incremental:

- esta fase solo crea helpers puros y documenta el mapa de endpoints;
- no se activa todavía ninguna validación en `app.py`;
- no se cambia frontend en esta fase;
- no se protegen endpoints GET;
- `POST /login` queda fuera inicialmente porque no tiene sesión autenticada previa y ya cuenta con rate limiting;
- la prioridad de 2B.2 serán los endpoints autenticados mutantes;
- el token se generará con `secrets.token_urlsafe(32)` y se validará con `hmac.compare_digest`;
- la integración prevista enviará el token desde el frontend en un header como `X-CSRF-Token`;
- ante token ausente o inválido se prevé responder `403 Forbidden`.

### Consecuencias

- La app mantiene el comportamiento actual durante 2B.1.
- Existe una base testeada para integrar CSRF sin mezclarla con refactors de `app.py`.
- La siguiente fase podrá activar protección por grupos de endpoints y validar cada flujo.
- La web pública y Firebase no se rompen porque los endpoints públicos de lectura quedan excluidos.

### Riesgos

- CSRF sigue sin estar activo hasta 2B.2.
- Desde Fase 2B.4, `GET /logout` ya no limpia sesión y el cierre real usa `POST /logout` con CSRF.
- Si se entrega el token al frontend, un XSS podría leerlo; CSP estricta y revisión de renderizado siguen pendientes.
- Un despliegue sin HTTPS/proxy correcto seguiría teniendo riesgos de transporte aunque CSRF esté activo.
- `app.py` sigue siendo monolítico y la integración debe ser cuidadosa para no cambiar respuestas existentes.

### Alternativas descartadas

- Activar CSRF directamente en esta fase: descartado para no tocar endpoints reales ni frontend.
- Proteger todos los GET: descartado porque rompe semántica HTTP y la regla de esta fase.
- Exigir CSRF en `/api/public/noticias`: descartado porque es lectura pública y rompería la web pública/Firebase.
- Crear una dependencia externa para CSRF: descartado porque los helpers necesarios caben en librería estándar.
- Usar solo `SameSite=Lax` como defensa final: descartado porque reduce riesgo, pero no sustituye un token CSRF en endpoints mutantes autenticados.
