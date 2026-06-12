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

### Evolución posterior

La Fase 2C.1 aplica CSP estricta solo a respuestas privadas después de auditar `index.html` y `login.html` y mover el script inline de login a `/static/login.js`.

La Fase 2C.2 extiende CSP a la web pública y Firebase después de eliminar el bootstrap inline de `PRIVATE_APP_URL` y sustituirlo por `data-private-app-url`.

La Fase 2C.3 endurece el helper de botones de la web pública para que los `href` dinámicos se escapen y se limiten a rutas relativas, anclas o URLs `http`/`https`, reduciendo riesgo XSS mientras siga existiendo render con `innerHTML`.

La Fase 2C.4 aplica el mismo criterio defensivo a enlaces privados de licitaciones: `normalizeUrl()` deja de propagar esquemas no web y oculta valores ambiguos antes de interpolarlos en plantillas.

La Fase 2C.5 añade escape explícito a los atributos `data-*` privados generados desde plantillas, conservando el flujo actual pero reduciendo dependencia en que los ids y fechas lleguen siempre limpios.

La Fase 2C.6 centraliza la conversión de estados privados a tokens CSS seguros para que las clases dinámicas no dependan de caracteres arbitrarios de datos.

La Fase 2C.7 cierra la primera ronda de auditoría XSS privada con una guarda estática contra patrones HTML peligrosos obvios mientras se planifica una futura reducción de `innerHTML`.

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

## ADR-010 — Puerta de control para checkpoints peligrosos

### Contexto

Las siguientes evoluciones probables incluyen SQLite, migraciones, CSRF global, StorageBackend, noticias Markdown y refactor de `app.py`. Todas pueden afectar datos, seguridad o contratos de la app.

### Decisión

Mantener una puerta de control versionada en `docs/CHECKPOINTS_PELIGROSOS.md` y cubrirla con tests. Antes de cualquier checkpoint peligroso se revisan riesgos, se ejecutan checks completos y se crea commit local si todo pasa. No se hace push desde el checkpoint.

### Consecuencias

- Las fases de alto riesgo tienen una checklist comun.
- Los comandos minimos de verificacion quedan visibles.
- Los tests fallaran si se elimina la cobertura documental basica.
- No sustituye el analisis tecnico de cada fase concreta.

## ADR-011 — Precheck antes de StorageBackend

### Contexto

El flujo de descarga actual mezcla seleccion de destino, escritura de `HTTP.url`, ejecucion de descargadores y actualizacion de `ruta_carpeta`. Antes de introducir `StorageBackend`, conviene inventariar ese flujo y fijar invariantes.

### Decisión

Crear `docs/PRECHECK_STORAGEBACKEND.md` y cubrirlo con tests documentales. El precheck no implementa almacenamiento nuevo; solo deja visible que piezas deben preservarse y que riesgos deben resolverse antes de LocalStorage, Dropbox o DownloadJob.

### Consecuencias

- La futura fase StorageBackend parte de un mapa verificable.
- Se reduce el riesgo de romper `ruta_carpeta` o descargas actuales.
- Dropbox real sigue fuera hasta que exista una transicion local probada.

## ADR-012 — Precheck antes de noticias Markdown

### Contexto

Las noticias actuales guardan texto plano en `content` y se renderizan escapadas en la web publica. La evolucion a Markdown seguro puede introducir parser, sanitizador, cambios de modelo y potencial XSS si se conecta demasiado pronto.

### Decisión

Crear `docs/PRECHECK_NOTICIAS_MARKDOWN.md` y cubrirlo con tests documentales. El precheck no implementa Markdown; solo fija el estado actual, invariantes, riesgos y estrategia minima antes de elegir parser o sanitizador.

### Consecuencias

- La futura fase Markdown parte de un mapa verificable.
- HTML libre sigue descartado.
- SQLite y frontend se mantienen sin cambios hasta que exista plan de migracion y render seguro.

## ADR-013 — Precheck antes de SQLite y migraciones

### Contexto

SQLite sigue siendo la persistencia de la app interna. El esquema se crea y evoluciona desde `init_db()` con cambios aditivos, pero todavia no existe tabla de migraciones, runner versionado ni estrategia de rollback documentada.

### Decisión

Crear `docs/PRECHECK_SQLITE_MIGRACIONES.md` y cubrirlo con tests documentales. El precheck no modifica la base productiva ni implementa migraciones; solo fija estado actual, invariantes, riesgos y orden seguro antes de introducir `schema_migrations` o cambios de esquema.

### Consecuencias

- La futura fase de migraciones parte de un mapa verificable.
- Los tests siguen obligados a usar SQLite temporal.
- Cualquier cambio de esquema queda pendiente de backup, plan de rollback y tests especificos.

## ADR-014 — Precheck antes de CSRF global

### Contexto

La app ya protege las mutaciones privadas conocidas con una allowlist explicita en `csrf_required_for_path()`. Pasar a una politica global puede reducir omisiones futuras, pero tambien puede romper login, rutas publicas, Firebase o convertir rutas desconocidas en `403 Forbidden`.

### Decisión

Crear `docs/PRECHECK_CSRF_GLOBAL.md` y cubrirlo con tests documentales. El precheck no activa CSRF global; solo fija cobertura actual, excepciones, invariantes y tests minimos antes de sustituir la allowlist.

### Consecuencias

- La futura fase de CSRF global parte de una superficie inventariada.
- Login, logout, rutas publicas, GET privados y rutas desconocidas quedan identificados como casos sensibles.
- No se mezcla CSRF global con refactor de `app.py`.

## ADR-015 — Precheck antes de refactor de app.py

### Contexto

`app.py` sigue concentrando entorno, sesiones, SQLite, importaciones, descargas, noticias, notificaciones y enrutado HTTP. Refactorizarlo puede mejorar mantenibilidad, pero tambien puede alterar imports, orden de validaciones, endpoints o respuestas JSON si se hace sin una puerta propia.

### Decisión

Crear `docs/PRECHECK_REFACTOR_APP.md` y cubrirlo con tests documentales. El precheck no refactoriza `app.py`; solo fija superficie actual, invariantes, riesgos, orden seguro de extraccion y plan de rollback.

### Consecuencias

- La futura fase de refactor parte de un mapa verificable.
- `app.py` debe mantenerse como fachada publica mientras se extraen piezas.
- El refactor no se mezcla con SQLite, migraciones, CSRF global, StorageBackend ni Markdown.

## ADR-016 — Extraer normalizacion pura desde app.py

### Contexto

El precheck de refactor identifica las funciones puras como primera frontera segura. `clean_text()`, `bool_text()`, `parse_money()`, `parse_date_value()` y `parse_time_value()` no necesitan servidor, SQLite, red, frontend ni filesystem.

### Decisión

Mover esas funciones a `webapp/infonalia_webapp/normalization.py` y reimportarlas desde `app.py` para conservar compatibilidad. El modulo nuevo debe poder importarse sin importar `app.py` ni modulos con efectos laterales.

### Consecuencias

- Se reduce una parte pequena del monolito sin cambiar comportamiento.
- Las funciones quedan testeadas como contrato puro.
- `app.py` conserva los nombres para tests y llamadas existentes.

## ADR-017 — Extraer formateo puro desde app.py

### Contexto

`format_date_es()` y `format_datetime_es()` son formateadores puros usados por respuestas y textos internos. No necesitan servidor, SQLite, red, frontend ni filesystem.

### Decisión

Mover esos formateadores a `webapp/infonalia_webapp/formatting.py` y reimportarlos desde `app.py` para conservar compatibilidad. El modulo nuevo depende solo de `normalization.clean_text()` y libreria estandar.

### Consecuencias

- Se reduce otra parte pequena del monolito sin cambiar comportamiento.
- El contrato de formateo queda probado de forma aislada.
- `app.py` conserva los nombres para llamadas existentes.

## ADR-018 — Extraer nombres de carpeta puros desde app.py

### Contexto

Los helpers de nombres y descriptores de carpeta no necesitan servidor, SQLite, red ni filesystem real. En cambio, los helpers que resuelven rutas con `Path`, Dropbox o `DOWNLOAD_ROOT` pertenecen a una frontera mas sensible y no deben mezclarse con esta extraccion.

### Decisión

Mover solo los helpers puros de nombres a `webapp/infonalia_webapp/folder_names.py` y reimportarlos desde `app.py` para conservar compatibilidad.

### Consecuencias

- Se reduce otra parte del monolito sin cambiar comportamiento.
- La logica de nombres queda testeada de forma aislada.
- La resolucion de rutas y StorageBackend quedan fuera de esta fase.

## ADR-019 — Extraer helpers de URL y plataforma desde app.py

### Contexto

`normalize_url()`, `should_update_url()` y `detectar_plataforma()` son helpers puros usados por importaciones, noticias, licitaciones y descargas. No necesitan servidor, SQLite, red, frontend ni filesystem.

### Decisión

Mover esos helpers a `webapp/infonalia_webapp/url_helpers.py` y reimportarlos desde `app.py` para conservar compatibilidad. Esta fase no endurece ni cambia reglas de URL; solo conserva el comportamiento actual en un contrato puro.

### Consecuencias

- Se reduce otra parte del monolito sin cambiar comportamiento.
- La deteccion de plataformas queda testeada de forma aislada.
- Cualquier cambio de seguridad en URLs queda para una fase separada.

## ADR-020 — Extraer parsing CSV puro desde app.py

### Contexto

La lectura de bytes CSV, el mapeo de alias, la normalizacion de estado y la construccion de payload son pasos puros. `import_csv_content()` no lo es porque escribe en SQLite y recalcula dias.

### Decisión

Mover solo el parsing CSV puro a `webapp/infonalia_webapp/csv_parsing.py` y reimportarlo desde `app.py` para conservar compatibilidad. Mantener `import_csv_content()` en `app.py` hasta que exista una frontera de persistencia mas clara.

### Consecuencias

- Se reduce otra parte del monolito sin cambiar comportamiento.
- El contrato de parsing CSV queda probado de forma aislada.
- La escritura SQLite queda fuera de esta fase.

## ADR-021 — Extraer helpers puros de noticias desde app.py

### Contexto

`slugify()`, `normalize_news_status()` y `news_to_dict()` preparan valores de noticias sin escribir en SQLite ni tocar endpoints. La evolucion a Markdown seguro queda fuera.

### Decisión

Mover esos helpers a `webapp/infonalia_webapp/news_helpers.py` y reimportarlos desde `app.py` para conservar compatibilidad.

### Consecuencias

- Se reduce otra parte del monolito sin cambiar comportamiento.
- El contrato actual de noticias queda probado de forma aislada.
- Markdown seguro y cambios de esquema quedan fuera de esta fase.

## ADR-022 — Extraer parsing textual MSG/PDF desde app.py

### Contexto

Algunos helpers usados por importacion MSG y enriquecimiento PDF solo parsean texto: extraen campos tras dos puntos, fechas, tipo de contrato y hora limite. No descargan, no ejecutan `pdftotext` y no escriben en SQLite.

### Decisión

Mover esos helpers a `webapp/infonalia_webapp/msg_parsing.py` y reimportarlos desde `app.py`. Mantener `parse_msg_body()`, `enrich_from_infonalia_pdf()` e `import_msg_content()` en `app.py` porque combinan reglas de importacion, red/subproceso o persistencia.

### Consecuencias

- Se reduce otra parte del monolito sin cambiar comportamiento.
- El parsing textual queda probado de forma aislada.
- Descarga PDF, lectura MSG y escritura SQLite quedan fuera de esta fase.

## ADR-023 — Extraer helpers puros de vista previa IA

### Contexto

La vista previa IA mezcla una parte pura de extraccion de texto con otra parte que lee licitaciones desde SQLite y puede enviar notificaciones. La frontera segura es separar solo los helpers de texto y formateo del payload.

### Decisión

Mover `extract_lotes_from_text()`, `extract_keyword_context()`, `extract_centros_from_text()` y `preview_payload_to_text()` a `webapp/infonalia_webapp/ai_preview_helpers.py`. Mantener `build_ai_preview_payload()` y el envio de email en `app.py`.

### Consecuencias

- Se reduce otra parte del monolito sin cambiar comportamiento.
- Las reglas de extraccion IA quedan testeadas de forma aislada.
- SQLite, endpoints y envio de email quedan fuera de esta fase.

## ADR-024 — Extraer render puro de notificaciones

### Contexto

Las notificaciones mezclan tres fronteras: destinatarios desde SQLite, envio SMTP y render/parseo de contenido. La parte de render y parseo puede probarse sin base de datos, red ni filesystem.

### Decisión

Mover `notification_body_parts()`, `parse_day_review_notification()` y el HTML base a `webapp/infonalia_webapp/notification_rendering.py`. Mantener en `app.py` la resolucion de destinatarios, SMTP, logo, escritura SQLite y una envoltura que pasa `PLATFORM_URL` ya cargada desde `.env`.

### Consecuencias

- Se reduce otra parte del monolito sin cambiar comportamiento.
- El HTML de notificacion queda probado de forma aislada.
- Envio real de email, logo embebido y persistencia quedan fuera de esta fase.

## ADR-025 — Introducir migraciones SQLite versionadas

### Contexto

SQLite seguia evolucionando desde `init_db()` mediante `CREATE TABLE IF NOT EXISTS`, `ensure_column()` e indices idempotentes. Antes de cambios de esquema mayores faltaba una tabla versionada que permitiera saber que migraciones se han aplicado.

### Decisión

Crear `webapp/infonalia_webapp/db_migrations.py` con tabla `schema_migrations`, runner idempotente y migracion baseline `0001_baseline_schema`. `init_db()` conserva la creacion historica del esquema y despues ejecuta el runner para registrar el baseline.

### Consecuencias

- Existe una base minima para futuras migraciones versionadas.
- La migracion inicial no transforma datos ni cambia endpoints.
- Antes de esta fase se crea backup local ignorado en `.local_backups/`.

## ADR-026 — Implementar StorageBackend local aislado

### Contexto

El contrato `StorageBackend` ya existia, pero solo con implementaciones falsas en tests. Antes de tocar el endpoint de descarga conviene disponer de una implementacion local real, pequena y probada con filesystem temporal.

### Decisión

Crear `webapp/infonalia_webapp/local_storage.py` con `LocalStorageBackend`. Acepta URIs `local://...`, escribe solo dentro de una raiz explicita, devuelve `StorageObject` y rechaza rutas absolutas o traversal.

### Consecuencias

- Hay una base local para conectar descargas en una fase posterior.
- No se implementa Dropbox ni se cambia `api_download_licitacion()`.
- No se cambia SQLite ni `ruta_carpeta`.

## ADR-027 — Implementar renderer Markdown seguro aislado

### Contexto

El contrato `NewsRenderer` existia, pero no habia implementacion. Conectar Markdown directamente a la UI o a SQLite seria arriesgado sin una capa que escape HTML crudo y filtre enlaces.

### Decisión

Crear `webapp/infonalia_webapp/safe_markdown.py` con `SafeMarkdownRenderer`. Es un renderer limitado: soporta titulos, parrafos, listas, negrita, cursiva y enlaces `http/https`; no permite HTML libre, scripts, iframes, eventos inline ni enlaces `javascript:`.

### Consecuencias

- Existe una base probada para noticias Markdown seguro.
- No se cambia todavia la tabla `noticias`, el frontend ni las respuestas JSON actuales.
- No se anaden dependencias externas.

## ADR-028 — Activar decision CSRF global en app.py

### Contexto

`csrf.py` ya modelaba la politica global: metodos mutantes autenticados requieren token salvo `/login` y prefijos publicos. `app.py` seguia usando una allowlist propia para decidir si una ruta concreta exigia CSRF.

### Decisión

Hacer que `InfonaliaHandler.csrf_required_for_path()` delegue primero en `is_csrf_required()` y despues confirme que la ruta mutante existe. Asi las rutas desconocidas siguen respondiendo `404 Not Found` y no se convierten en error CSRF.

### Consecuencias

- La decision central vive en `csrf.py`.
- Las excepciones de login, GET y API publica se conservan.
- No se cambian endpoints, frontend ni respuestas JSON esperadas.

## ADR-029 — Generar manifest local tras descarga correcta

### Contexto

El flujo de descarga validaba carpeta y limites, pero no dejaba inventario de ficheros. `LocalStorageBackend` ya permite escribir objetos locales seguros, asi que se puede crear un manifest sin cambiar respuestas ni esquema.

### Decisión

Generar `.infonalia_manifest.json` dentro de la carpeta destino despues de una descarga correcta y antes de actualizar `ruta_carpeta`. El manifest se escribe con `LocalStorageBackend`, incluye rutas relativas, URI local, tamano y checksum, y se ignora en el escaneo de limites por ser fichero interno controlado.

### Consecuencias

- Las descargas exitosas quedan inventariadas.
- No se cambia la respuesta JSON ni SQLite.
- Si falla la creacion del manifest, no se marca `ruta_carpeta` como correcta.

## ADR-030 — Publicar HTML Markdown sanitizado como campo compatible

### Contexto

Ya existe `SafeMarkdownRenderer`, pero las noticias publicas seguian renderizando `content` como texto plano. Cambiar SQLite o sustituir el campo `content` aumentaria riesgo.

### Decisión

Mantener `content` como fuente y anadir `contentHtml` a `news_to_dict()`, generado con `SafeMarkdownRenderer`. El frontend publico usa `contentHtml` cuando llega desde la API y conserva el fallback escapado para placeholders o datos sin HTML sanitizado.

### Consecuencias

- Las noticias pueden mostrar Markdown seguro sin migracion SQLite.
- Los campos existentes no se eliminan.
- Firebase conserva fallback si no hay API en su origen.

## ADR-031 — Preparar tabla download_jobs

### Contexto

Las descargas correctas ya generan un manifest local, pero SQLite no tenia una tabla preparada para registrar ejecuciones o una futura cola asincrona.

### Decisión

Anadir la migracion `0002_download_jobs` con la tabla `download_jobs` y sus indices por licitacion, estado y fecha de creacion. La migracion es idempotente y solo prepara estructura.

### Consecuencias

- Hay base para jobs de descarga futuros.
- No se cambia `api_download_licitacion()`.
- No se cambian endpoints, respuestas JSON ni frontend.
- No se implementa Dropbox real.

## ADR-032 — Preparar historial de importaciones

### Contexto

Las importaciones CSV y MSG devuelven resultados al momento, pero no queda un historial persistente de ejecuciones, conteos, duplicados o errores por candidato.

### Decisión

Anadir la migracion `0003_import_history` con las tablas `import_runs` e `import_results`. La estructura sigue el modelo conceptual documentado y solo prepara persistencia futura.

### Consecuencias

- Hay base para auditar importaciones y sincronizaciones futuras.
- No se conectan todavia CSV ni MSG a estas tablas.
- No se cambian endpoints, respuestas JSON ni frontend.
- No se implementan fuentes reales nuevas como PLACE.

## ADR-033 — Registrar descargas como jobs síncronos

### Contexto

Ya existe la tabla `download_jobs` y las descargas correctas generan manifest, pero el endpoint seguia sin dejar rastro persistente de cada ejecucion.

### Decisión

Crear un job `running` justo antes de ejecutar el descargador local y cerrarlo como `completed` o `failed` segun el resultado. El endpoint sigue siendo sincrono y mantiene la misma respuesta JSON.

### Consecuencias

- Las descargas ejecutadas quedan auditadas en SQLite.
- Los errores de proceso, timeout, limites o manifest quedan asociados al job.
- Las validaciones previas que no llegan a ejecutar descarga no crean job.
- No se implementa cola en segundo plano ni Dropbox real.
