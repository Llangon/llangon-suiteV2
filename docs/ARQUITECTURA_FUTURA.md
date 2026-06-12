# Arquitectura futura de Llangon-SuiteV2

## 1. Objetivo

Este documento define la FASE 0 del proyecto: mapa del flujo actual y decisiones de arquitectura futura.

El objetivo no es cambiar el comportamiento actual, sino dejar documentado cómo evoluciona la aplicación sin romper el flujo operativo existente. En esta fase no se implementan nuevas fuentes, no se implementa Dropbox, no se cambia el esquema SQLite y no se reescribe `app.py`.

La arquitectura futura debe permitir:

- añadir fuentes de licitaciones sin acoplarlas al formulario actual;
- separar la normalización de datos externos de la persistencia interna;
- preparar una capa de almacenamiento que pueda usar disco local o Dropbox;
- evolucionar las noticias desde texto plano a Markdown seguro;
- introducir migraciones, tests y jobs asíncronos en fases posteriores.

## 2. Estado actual resumido

`Llangon-SuiteV2` es un monorepo con estos bloques:

- `webapp/infonalia_webapp/`: app privada Python/SQLite con frontend estático.
- `firebase/public_firebase/`: web pública estática preparada para Firebase Hosting.
- `herramientas_python/`: descargadores por plataforma.
- `macros/`: automatizaciones VBA.
- `docs/`: documentación operativa.

La app privada usa `BaseHTTPRequestHandler` y `ThreadingHTTPServer`, no un framework web. La base de datos SQLite se crea y se evoluciona desde `webapp/infonalia_webapp/app.py`, especialmente en `init_db()`.

La mayor parte de la lógica vive actualmente en `app.py`: configuración, autenticación, esquema SQLite, normalización de CSV y MSG, notificaciones, noticias, descargas, generación de carpetas y endpoints HTTP.

## 3. Flujo actual de entrada de licitaciones

### Entrada CSV

El frontend privado ofrece un formulario de importación en `webapp/infonalia_webapp/static/index.html`. La lógica de envío está en `webapp/infonalia_webapp/static/app.js`, dentro del listener de `importForm`.

El flujo actual es:

1. El usuario administrador selecciona un fichero `.csv`.
2. `app.js` detecta la extensión y envía `FormData` a `/api/import/csv`.
3. `InfonaliaHandler.do_POST()` enruta `/api/import/csv` hacia `api_import_csv()`.
4. `api_import_csv()` lee el body completo, extrae el campo multipart `csv_file` y llama a `import_csv_content()`.
5. `import_csv_content()` lee filas y cabeceras con `read_csv_rows()`.
6. `csv_alias_map()` mapea columnas externas a nombres internos.
7. `build_payload_from_csv_row()` transforma cada fila a payload interno.
8. `get_or_create_dia()` crea o reutiliza un registro en `infonalia_dias`.
9. `insert_payload()` inserta, actualiza u omite cada licitación.
10. `refresh_dia_estado()` recalcula el estado del día.

Funciones principales:

- `api_import_csv()`
- `extract_multipart_file()`
- `import_csv_content()`
- `read_csv_rows()`
- `csv_alias_map()`
- `build_payload_from_csv_row()`
- `get_or_create_dia()`
- `insert_payload()`
- `mark_dia_nuria_dirty()`
- `refresh_dia_estado()`

Campos detectados desde CSV:

- `fecha_infonalia`
- `expediente`
- `objeto`
- `organismo`
- `provincia`
- `tipo`
- `presupuesto`
- `fecha_limite`
- `hora_limite`
- `plataforma`
- `enlace_perfil`
- `enlace_infonalia`
- `estado`
- `comentario`
- `ruta_carpeta`

El único campo realmente obligatorio para insertar es `expediente`. Si no hay expediente, `insert_payload()` devuelve `skipped`.

### Entrada correos/MSG/Infonalia

El frontend usa el mismo formulario de importación. Si el fichero termina en `.msg`, `app.js` envía `FormData` a `/api/import/msg`. El checkbox `enrich_pdf` indica si se intenta completar tipo y hora leyendo el PDF de Infonalia.

El flujo actual es:

1. El administrador selecciona un fichero `.msg`.
2. `app.js` envía el fichero a `/api/import/msg`.
3. `InfonaliaHandler.do_POST()` enruta a `api_import_msg()`.
4. `api_import_msg()` extrae el campo multipart `msg_file`.
5. `import_msg_content()` guarda temporalmente el MSG en `data/uploads/`.
6. `extract_msg.Message()` lee fecha y cuerpo.
7. `parse_msg_body()` separa bloques que contienen `Ref. Infonalia:`.
8. Cada bloque se transforma a payload de licitación.
9. Opcionalmente `enrich_from_infonalia_pdf()` descarga el PDF de Infonalia y usa `pdftotext` para extraer tipo y hora.
10. Cada payload pasa por `insert_payload()`.
11. Se recalcula el estado del día.

Funciones principales:

- `api_import_msg()`
- `import_msg_content()`
- `extract_msg_date()`
- `parse_msg_body()`
- `enrich_from_infonalia_pdf()`
- `download_to_path()`
- `pdf_to_text()`
- `insert_payload()`

Campos extraídos desde MSG/Infonalia:

- `enlace_infonalia`
- `enlace_perfil`
- `expediente`
- `organismo`
- `objeto`
- `provincia`
- `fecha_limite`
- `presupuesto`
- `tipo`
- `hora_limite`
- `plataforma`
- `estado`
- `comentario`
- `ruta_carpeta`

Actualmente la fuente Infonalia no queda registrada como entidad separada. El origen se deduce por el endpoint o por el campo `plataforma`, pero no existe `source_name`, `external_id`, `raw_payload` ni un registro de importación.

## 4. Problemas detectados en el flujo actual

### Identidad y duplicados

La deduplicación actual está concentrada en `insert_payload()`. Se considera existente una licitación si coincide:

- `expediente`
- `organismo`, usando `COALESCE(organismo, '')`

Riesgos:

- el mismo expediente puede aparecer con variantes de organismo;
- diferentes organismos podrían usar expedientes parecidos;
- fuentes futuras pueden traer un identificador externo más fiable;
- la creación manual de licitaciones no usa la misma lógica de deduplicación;
- SQLite no impone `UNIQUE(expediente, organismo)`;
- no existe fingerprint/hash normalizado.

### Mezcla de responsabilidades

La entrada de datos, normalización, deduplicación, persistencia y actualización de estado están mezcladas en `app.py`. Esto dificulta añadir `PlaceSource`, `CsvSource` o `EmailInfonaliaSource` sin tocar zonas sensibles.

### Ausencia de registro de importaciones

No existe tabla o modelo `ImportRun`. El resultado se devuelve al frontend en el momento, pero no queda un historial consultable de:

- cuándo se importó;
- desde qué origen;
- cuántas licitaciones entraron;
- cuántas se actualizaron;
- cuántas fueron duplicadas;
- qué errores hubo.

### Límites de carga

`read_body()` lee el body completo según `Content-Length` y `extract_multipart_file()` procesa multipart en memoria. En fases posteriores conviene añadir límites explícitos y streaming.

### Acoplamiento con días Infonalia

Las licitaciones importadas se agrupan en `infonalia_dias`. Esto encaja con el flujo actual de correos de Infonalia, pero una fuente futura como PLACE puede no tener un "día Infonalia" natural. La arquitectura futura debería conservar `infonalia_dia_id` para compatibilidad, pero no depender de él para todas las fuentes.

## 5. Modelo canónico propuesto para licitaciones

El modelo canónico debe representar una licitación antes de guardarla, venga de CSV, email, PLACE u otra fuente.

Campos mínimos propuestos:

- `id`: identificador interno en SQLite. Obligatorio después de persistir.
- `source_name`: origen normalizado, por ejemplo `csv`, `email_infonalia`, `place`, `junta_andalucia`. Obligatorio para importaciones nuevas.
- `external_id`: identificador estable de la fuente si existe. Opcional, pero recomendado.
- `external_url`: URL original de la fuente. Opcional, recomendado cuando existe.
- `expediente`: número o referencia de expediente. Obligatorio si no hay `external_id`.
- `organismo`: órgano de contratación. Recomendado.
- `titulo`: título corto o nombre principal. Recomendado.
- `descripcion`: resumen u objeto contractual. Opcional, pero muy útil.
- `presupuesto`: importe numérico normalizado. Opcional.
- `fecha_publicacion`: fecha de publicación/anuncio. Opcional.
- `fecha_limite`: fecha límite de presentación. Opcional, pero crítica para calendario.
- `estado`: estado interno de trabajo. Obligatorio al persistir.
- `cpv`: CPV o categoría si la fuente lo aporta. Opcional.
- `raw_payload`: JSON/texto con datos originales. Opcional, útil para auditoría.
- `fingerprint`: hash normalizado para deduplicación. Obligatorio cuando se implante deduplicación robusta.
- `imported_at`: fecha de primera importación. Obligatorio al persistir.
- `last_seen_at`: fecha de última aparición en una fuente. Obligatorio en sincronizaciones futuras.

Campos obligatorios recomendados para crear una licitación:

- `source_name`
- al menos uno de `external_id`, `external_url`, `expediente`
- `estado`
- `fingerprint`
- `imported_at`
- `last_seen_at`

Campos opcionales, pero recomendados:

- `organismo`
- `titulo`
- `descripcion`
- `fecha_limite`
- `presupuesto`
- `raw_payload`

Equivalencia aproximada con el modelo actual:

- `objeto` se acerca a `descripcion` o `titulo`, según calidad del dato.
- `enlace_perfil` se acerca a `external_url`.
- `plataforma` se acerca a `source_name`, aunque hoy es más una etiqueta.
- `ruta_carpeta` pertenece más a almacenamiento/descargas que a identidad de licitación.

## 6. Identidad, deduplicación y upsert

### Clave primaria interna

La clave primaria interna debe seguir siendo un `id` autoincremental o equivalente. No debe depender del expediente ni del identificador externo.

### Clave externa por fuente

Debe existir una clave por fuente:

- `source_name`
- `external_id`

Regla recomendada:

- Si `external_id` existe, `source_name + external_id` identifica una candidatura dentro de esa fuente.
- Si no existe `external_id`, usar `source_name + external_url` normalizada.
- Si no existe URL, usar fingerprint.

### Fingerprint

El fingerprint debe generarse con campos normalizados. Propuesta:

1. normalizar `expediente`;
2. normalizar `organismo`;
3. normalizar `external_url` si existe;
4. opcionalmente incluir `fecha_limite` y una parte estable del título/objeto;
5. crear SHA-256 de una cadena canónica.

Ejemplo conceptual:

```text
fingerprint = sha256(
  normalize(expediente) + "|" +
  normalize(organismo) + "|" +
  normalize(external_url)
)
```

Para fuentes pobres en datos, el fingerprint puede tener menor confianza. En ese caso conviene registrar `dedup_confidence`.

### Reglas de upsert

Orden recomendado:

1. Buscar por `source_name + external_id`.
2. Si no existe, buscar por `source_name + external_url`.
3. Si no existe, buscar por fingerprint exacto.
4. Si no existe, buscar coincidencia blanda por `expediente + organismo`.
5. Si hay coincidencia blanda ambigua, no fusionar automáticamente; marcar como posible duplicado.

Al actualizar:

- no sobrescribir campos editados manualmente con campos vacíos;
- registrar `last_seen_at`;
- mantener `imported_at` original;
- guardar `raw_payload` de la última importación o un historial si se justifica;
- marcar qué campos proceden de fuente externa y cuáles fueron revisados manualmente.

### Tratamiento de duplicados

Estados recomendados:

- `unique`: no hay duplicado detectado.
- `duplicate_exact`: coincide por clave externa o fingerprint.
- `duplicate_possible`: coincide por expediente/organismo pero no hay certeza.
- `manual_review_required`: necesita decisión humana.

En una primera fase técnica, bastaría con registrar duplicados posibles sin cambiar la UI principal.

## 7. Registro de importaciones y sincronizaciones

Modelo conceptual propuesto:

### ImportSource

Representa una fuente configurada.

Campos:

- `id`
- `source_name`
- `display_name`
- `source_type`: `csv`, `email_infonalia`, `place`, `other_platform`
- `mode`: `manual`, `automatic`, `both`
- `enabled`
- `config_json`
- `created_at`
- `updated_at`

### ImportRun

Representa una ejecución de importación o sincronización.

Campos:

- `id`
- `source_name`
- `source_type`
- `mode`: `manual` o `automatic`
- `started_at`
- `finished_at`
- `status`: `pending`, `running`, `completed`, `failed`
- `triggered_by`
- `input_name`
- `input_hash`
- `new_count`
- `updated_count`
- `duplicate_count`
- `error_count`
- `notes`

### ImportResult

Representa el resultado por candidato.

Campos:

- `id`
- `import_run_id`
- `source_name`
- `external_id`
- `fingerprint`
- `licitacion_id`
- `status`: `inserted`, `updated`, `skipped`, `duplicate`, `error`
- `error_message`
- `raw_payload`
- `created_at`

Ventaja: permitiría auditar importaciones sin depender solo del mensaje mostrado en pantalla.

## 8. Diseño futuro de fuentes de licitaciones

La app debería evolucionar hacia fuentes intercambiables. No se implementa ahora, pero el contrato conceptual sería:

### SourceCandidate

Dato bruto o semi-bruto obtenido de una fuente.

- `source_name`
- `external_id`
- `external_url`
- `raw_payload`
- `received_at`

### LicitacionSource

Interfaz conceptual:

- `source_name() -> str`
- `fetch_candidates(context) -> list[SourceCandidate]`
- `normalize(candidate) -> LicitacionNormalized`
- `validate(candidate) -> list[ParseError]`

### CsvSource

Fuente manual. No obtiene datos de red. Lee un fichero subido por el administrador y devuelve candidatos normalizados.

### EmailInfonaliaSource

Fuente manual ahora, automatizable más adelante. Lee MSG o cuerpo de email y devuelve licitaciones normalizadas.

### PlaceSource futuro

Fuente futura. Podría consultar PLACE o procesar una exportación. No debe mezclarse con el descargador de documentos; una cosa es descubrir licitaciones y otra descargar sus documentos.

### OtherPlatformSource futuro

Plantilla para más plataformas. Debe devolver candidatos normalizados y errores de parseo sin conocer SQLite ni la UI.

Regla de arquitectura: las fuentes no deberían escribir en SQLite directamente. Deben devolver modelos normalizados para que una capa de importación decida upsert, duplicados y auditoría.

## 9. Flujo actual de descargas

El botón aparece en cada tarjeta de licitación para administradores:

- `webapp/infonalia_webapp/static/app.js`
- botón `data-download-id`
- función `downloadLicitacion(id, button)`
- endpoint `POST /api/licitaciones/{id}/descargar`

Backend actual:

1. `InfonaliaHandler.do_POST()` enruta a `api_download_licitacion()`.
2. Se comprueba rol admin.
3. Se lee la licitación desde SQLite.
4. Se usa `enlace_perfil` como URL principal.
5. `resolve_destination_folder()` decide carpeta de destino.
6. Se crea la carpeta con `mkdir(parents=True, exist_ok=True)`.
7. `write_http_url()` escribe un `HTTP.url`.
8. Se ejecuta `herramientas_python/Descargar_Licitacion.py`.
9. `Descargar_Licitacion.py` detecta plataforma y llama al script específico.
10. La salida se devuelve al frontend.
11. Se guarda `ruta_carpeta` en SQLite.

Scripts implicados:

- `herramientas_python/Descargar_Licitacion.py`
- `herramientas_python/Descargar_PLACE.py`
- `herramientas_python/Descargar_JuntaAndalucia.py`
- `herramientas_python/Descargar_ComunidadMadrid.py`
- `herramientas_python/Descargar_Euskadi.py`
- `herramientas_python/Descargar_Catalunya.py`

Campo actual de carpeta:

- `licitaciones.ruta_carpeta`

Acoplamientos actuales al sistema de archivos local:

- `Path` local como representación de destino.
- `mkdir()` directo desde `app.py`.
- `cwd` del proceso de descarga es la carpeta destino.
- los descargadores reciben `--destino <CARPETA>`.
- los scripts escriben documentos directamente con `open(..., "wb")`.
- `ruta_carpeta` mezcla ruta visible, ruta relativa a Dropbox y ruta local.

## 10. Diseño futuro de almacenamiento local/Dropbox

La evolución recomendada es introducir una capa de almacenamiento, sin cambiar todavía `ruta_carpeta`.

### StorageBackend

Interfaz conceptual:

- `backend_name`
- `prepare_logical_folder(licitacion) -> StorageUri`
- `save_stream(storage_uri, filename, stream, metadata) -> StorageObject`
- `save_bytes(storage_uri, filename, content, metadata) -> StorageObject`
- `commit(storage_uri) -> StorageManifest`
- `rollback(storage_uri)`
- `get_display_path(storage_uri) -> str`
- `get_link(storage_object) -> str | None`

### LocalStorage

Implementación futura para disco local. Debe encapsular:

- creación de carpetas;
- escritura de ficheros;
- nombres seguros;
- ruta visible para usuario;
- manifest de ficheros descargados.

### DropboxStorage futuro

Implementación futura que suba ficheros a Dropbox. Debe evitar que los descargadores escriban directamente en rutas locales finales. Posibles estrategias:

- descargar primero a carpeta temporal controlada y subir a Dropbox al completar;
- o adaptar descargadores para escribir en streams gestionados por `StorageBackend`.

Para reducir riesgo, la primera transición debería ser:

1. mantener descargadores escribiendo en temporal local;
2. crear manifest;
3. subir manifest y ficheros con `DropboxStorage`;
4. borrar temporal si todo termina bien;
5. marcar job como fallido si la subida no se confirma.

### StorageObject

Campos:

- `storage_uri`
- `backend_name`
- `display_path`
- `filename`
- `size`
- `content_type`
- `checksum`
- `external_link`
- `created_at`

### Convivencia con `ruta_carpeta`

En fases intermedias:

- `ruta_carpeta` debe seguir existiendo para no romper UI ni datos existentes.
- Puede guardar `display_path` legible.
- Más adelante conviene añadir campos nuevos como `storage_backend`, `storage_uri` y `file_manifest`.
- No migrar destructivamente hasta tener backup y tests.

## 11. Diseño futuro de DownloadJob

El botón Descargar debería evolucionar a un job.

Estados recomendados:

- `pending`: job creado, pendiente de ejecución.
- `running`: descarga en curso.
- `completed`: ficheros descargados y almacenamiento confirmado.
- `failed`: fallo controlado.

Campos conceptuales:

- `id`
- `licitacion_id`
- `requested_by`
- `source_url`
- `platform`
- `status`
- `storage_backend`
- `storage_uri`
- `display_path`
- `file_manifest`
- `stdout_tail`
- `error_message`
- `started_at`
- `finished_at`
- `created_at`
- `updated_at`

Reglas:

- el endpoint de descarga debería crear un job y devolver su estado;
- la ejecución podría seguir siendo síncrona inicialmente, pero registrada como job;
- en una fase posterior, ejecutar en background;
- no actualizar `ruta_carpeta` hasta que el almacenamiento esté confirmado;
- si falla, conservar error y no dejar la app en estado ambiguo;
- aplicar límites de tamaño, tiempo y número de ficheros;
- registrar manifest con nombres, tamaños y checksum.

Primera fase segura:

- documentar el job;
- después añadir tabla `download_jobs`;
- luego envolver el flujo actual sin cambiar UI;
- finalmente introducir backend Dropbox.

## 12. Evolución propuesta de noticias a Markdown seguro

Modelo deseable:

- `id`
- `titulo`
- `slug`
- `entradilla`
- `contenido_markdown`
- `contenido_html_renderizado` opcional
- `imagen_destacada`
- `estado`: `borrador`, `publicada`
- `fecha_publicacion`
- `created_at`
- `updated_at`

Equivalencias actuales:

- `title` -> `titulo`
- `excerpt` -> `entradilla`
- `content` -> futuro `contenido_markdown`
- `featured_image` -> `imagen_destacada`
- `status` -> `estado`
- `published_at` -> `fecha_publicacion`
- `slug` ya existe y tiene `UNIQUE`

Recomendaciones:

- guardar Markdown como fuente principal;
- no permitir HTML libre;
- si se genera HTML, sanitizarlo antes de mostrarlo;
- desactivar HTML embebido del parser Markdown;
- permitir imagen destacada como campo estructurado, no como HTML arbitrario;
- validar URLs de imagen y, si se admiten externas, limitar esquemas a `https`;
- definir una lista de etiquetas Markdown permitidas;
- no implementar EasyMDE hasta tener render seguro y tests.

Riesgos de HTML libre:

- XSS en la web pública;
- ejecución de scripts si el contenido se inyecta con `innerHTML`;
- enlaces maliciosos;
- imágenes externas de tracking;
- ruptura visual por HTML no controlado.

Para Firebase:

- actualmente `firebase/public_firebase/static/public.js` pide `/api/public/noticias`;
- Firebase Hosting estático no sirve esa API;
- se debe decidir si las noticias públicas saldrán de un JSON exportado, Cloud Function, API privada expuesta o publicación estática.

## 13. Cambios de SQLite que serán necesarios más adelante

No se implementan en esta fase, pero se recomiendan en fases posteriores.

### Licitaciones

Campos futuros posibles:

- `source_name`
- `external_id`
- `external_url`
- `canonical_title`
- `descripcion`
- `fecha_publicacion`
- `cpv`
- `raw_payload`
- `fingerprint`
- `imported_at`
- `last_seen_at`
- `storage_backend`
- `storage_uri`
- `file_manifest`

Constraints/índices:

- índice por `source_name, external_id`;
- índice por `fingerprint`;
- índice por `fecha_limite`;
- posible índice por `expediente, organismo`;
- `CHECK` de estados válidos cuando exista una estrategia de migración.

### Importaciones

Tablas futuras:

- `import_sources`
- `import_runs`
- `import_results`

### Descargas

Tabla futura:

- `download_jobs`

Campos relevantes:

- `licitacion_id`
- `status`
- `storage_backend`
- `storage_uri`
- `display_path`
- `file_manifest`
- `error_message`
- `created_at`
- `updated_at`

### Noticias

Evolución posible:

- mantener `content` temporalmente;
- añadir `content_markdown` o renombrar mediante migración;
- añadir `rendered_html` solo si se decide cachear HTML sanitizado;
- normalizar `status` a `draft/published` o traducir a `borrador/publicada` con una capa de presentación.

### Usuarios y permisos

Mejoras futuras:

- mantener usuarios en SQLite mientras siga siendo app interna;
- revisar sesiones y cookies antes de exposición externa;
- añadir auditoría de acciones sensibles si hay varios administradores.

## 14. Cambios que NO se implementan en esta fase

En esta fase no se implementa:

- refactor de `app.py`;
- Flask, FastAPI, Django ni otro framework;
- nuevas URLs;
- cambios en respuestas JSON actuales;
- migraciones SQLite;
- conectores reales a PLACE u otras plataformas;
- integración real con Dropbox;
- automatización desatendida;
- EasyMDE u otro editor visual;
- cambios en macros VBA;
- ejecución de descargadores reales;
- tests sobre datos reales;
- jobs en background;
- cambios de comportamiento de la app.

## 15. Riesgos pendientes

- El monolito `app.py` sigue siendo el principal riesgo de mantenimiento.
- `ruta_carpeta` mezcla almacenamiento, visualización y compatibilidad con Dropbox local.
- Las importaciones no tienen historial persistente.
- La deduplicación por `expediente + organismo` puede fallar con fuentes nuevas.
- No hay modelo canónico persistido.
- No hay límites fuertes de subida/descarga.
- No hay jobs ni manifest de ficheros.
- Firebase público no tiene una fuente dinámica real para noticias.
- Markdown seguro requiere selección de librería, sanitizador y tests.
- SQLite necesita migraciones formales antes de cambios de esquema.

## 16. Fases recomendadas después de esta fase 0

### Fase 1: Seguridad y límites sin cambiar arquitectura

- limitar tamaño de uploads;
- limitar descargas;
- añadir controles de errores más claros;
- reforzar cabeceras y sesiones si se sale de entorno local.

### Fase 2: Tests de funciones puras actuales

- fechas;
- dinero;
- normalización de estado;
- deduplicación actual;
- parsing CSV;
- parsing MSG con fixtures ficticios.

### Fase 3: Contratos puros

- crear `core/models.py`;
- crear contratos de fuentes y almacenamiento;
- añadir tests de instanciación;
- no conectar todavía con `app.py`.

### Fase 4: Registro de importaciones

- diseñar migración;
- añadir tablas `import_runs` e `import_results`;
- envolver CSV/MSG actuales sin cambiar respuestas JSON.

### Fase 5: StorageBackend local

- envolver el comportamiento local actual;
- mantener `ruta_carpeta`;
- preparar `storage_backend` y `storage_uri`.

### Fase 6: DownloadJob

- registrar descargas como jobs;
- conservar ejecución síncrona inicialmente;
- añadir estados y errores persistentes.

### Fase 7: DropboxStorage futuro

- subir desde temporal local a Dropbox;
- confirmar subida;
- guardar manifest;
- no depender de Dropbox instalado en el PC.

### Fase 8: Noticias Markdown seguro

- seleccionar parser Markdown y sanitizador;
- guardar Markdown como fuente;
- generar HTML sanitizado;
- adaptar web pública con una estrategia compatible con Firebase.

## Contratos creados en Fase 1A

La Fase 1A añade una capa conceptual y testeable en `webapp/infonalia_webapp/core/`. Son contratos puros: no importan `app.py`, no arrancan servidor, no abren SQLite, no llaman a red, no acceden a Dropbox y no leen ni escriben ficheros reales.

Estos contratos todavía no están conectados al flujo real. La app sigue usando los endpoints, modelos SQLite, scripts de descarga, frontend y Firebase actuales.

Archivos creados:

- `core/models.py`: define dataclasses y enums para licitaciones candidatas, licitaciones normalizadas, ejecuciones de importación, resultados de importación, objetos de almacenamiento, jobs de descarga y noticias Markdown.
- `core/source_contracts.py`: define `LicitationSource`, el contrato futuro para fuentes como CSV, correo/Infonalia, PLACE u otras plataformas.
- `core/storage_contracts.py`: define `StorageBackend`, el contrato futuro para almacenamiento local, carpeta Dropbox sincronizada o Dropbox API.
- `core/news_contracts.py`: define `NewsRenderer`, el contrato futuro para renderizar Markdown y sanitizar HTML antes de mostrar noticias enriquecidas.

Uso previsto por fases:

- En una fase posterior de normalización, CSV y MSG podrán adaptarse gradualmente para producir `LicitacionCandidate` y `LicitacionNormalized`, conservando las respuestas actuales.
- En una fase posterior de descargas, el comportamiento local podrá envolverse con una implementación `StorageBackend` sin cambiar de golpe `ruta_carpeta`.
- En una fase posterior de Dropbox, una implementación real podrá usar `dropbox_api` y devolver `StorageObject` persistibles.
- En una fase posterior de noticias, el contenido Markdown podrá pasar por `NewsRenderer` antes de llegar al panel privado o a la web pública.

## Limites aplicados en Fase 1B

La Fase 1B añade protecciones pequenas en las subidas de importacion, sin cambiar URLs ni respuestas de exito.

Limites aplicados:

- cuerpo HTTP maximo: `10 * 1024 * 1024` bytes;
- fichero subido maximo: `10 * 1024 * 1024` bytes;
- extensiones permitidas para importacion: `.csv` y `.msg`.

Endpoints protegidos:

- `POST /api/import/csv`;
- `POST /api/import/msg`.

Comportamiento nuevo en errores de seguridad:

- `413 Payload Too Large` cuando `Content-Length` o el fichero superan el limite;
- `400 Bad Request` cuando `Content-Length` falta, no es numerico o no es valido;
- `400 Bad Request` cuando el nombre del fichero esta vacio, contiene rutas o usa una extension no permitida.

La validacion de nombre se hace en backend. No se confia solo en el frontend. Se bloquean nombres como `../archivo.csv`, `..\\archivo.csv`, rutas Windows como `C:\\temp\\archivo.csv`, rutas absolutas Unix como `/tmp/archivo.csv`, nombres sin extension y dobles extensiones peligrosas como `archivo.csv.exe`.

Limitaciones pendientes:

- el multipart sigue procesandose en memoria para peticiones validas dentro del limite;
- queda pendiente streaming real para subidas grandes si alguna fase futura lo necesita;
- las descargas no quedan limitadas en esta fase;
- no se anaden tests funcionales de endpoints en esta fase;
- no se cambian SQLite, frontend, Firebase, macros, Dropbox ni descargadores.

## Tests funcionales minimos en Fase 1C

La Fase 1C añade tests funcionales mínimos para los endpoints reales de importación, sin arrancar servidor HTTP y sin tocar la SQLite productiva.

Estrategia elegida:

- importar `app.py` con variables de entorno ficticias de test;
- no llamar a `run()` ni arrancar `ThreadingHTTPServer`;
- construir un `InfonaliaHandler` controlado en memoria;
- simular permisos de administrador solo dentro del test;
- enviar cuerpos `multipart/form-data` ficticios pequeños;
- usar SQLite temporal solo para el caso CSV válido.

Cobertura conseguida:

- `POST /api/import/csv` con `.csv` pequeño válido, usando DB temporal;
- rechazo de CSV con extensión incorrecta;
- rechazo de CSV con nombre inseguro;
- rechazo de CSV con `Content-Length` superior al límite sin crear un fichero grande real;
- rechazo de MSG con extensión incorrecta;
- rechazo de MSG con nombre inseguro;
- rechazo de MSG con `Content-Length` superior al límite sin crear un fichero grande real.

El procesamiento completo de MSG válido queda pendiente. No se crea una fixture `.msg` realista en esta fase para evitar datos reales, dependencias pesadas o acoplamiento innecesario a formato binario de Outlook.

La base productiva `webapp/infonalia_webapp/data/infonalia.db` no se usa en estos tests. Los tests guardan cualquier inserción en una ruta temporal y restauran las rutas globales de la app al terminar.

## Seguridad minima de descargas en Fase 1D

La Fase 1D añade una capa minima de seguridad alrededor del flujo actual de descargas locales. No implementa Dropbox real, no crea `DownloadJob` persistente y no cambia el endpoint existente.

Flujo protegido:

- frontend: `downloadLicitacion(id, button)`;
- backend: `POST /api/licitaciones/{id}/descargar`;
- handler: `api_download_licitacion()`;
- destino: `resolve_destination_folder()`;
- fichero auxiliar: `HTTP.url`;
- lanzador: `herramientas_python/Descargar_Licitacion.py`.

Limites y validaciones añadidos:

- URL de descarga: solo se aceptan `http` y `https`;
- destino: la carpeta resuelta debe quedar bajo `DOWNLOAD_ROOT` o bajo la raiz Dropbox local configurada/detectada;
- timeout de proceso: `900` segundos centralizados en `download_safety.py`;
- salida capturada: se trunca a `20000` caracteres;
- carpeta resultante: maximo `500` ficheros;
- carpeta resultante: maximo `500 * 1024 * 1024` bytes.

Cambio de seguridad importante:

- `ruta_carpeta` solo se actualiza en SQLite si el proceso termina con codigo `0` y la carpeta final no supera los limites;
- si el proceso falla, se devuelve error y no se marca la carpeta como descarga correcta;
- si la carpeta supera limites, se devuelve error y no se actualiza `ruta_carpeta`.

Limitaciones pendientes:

- los descargadores siguen escribiendo localmente;
- no hay Dropbox API real;
- no hay `DownloadJob` persistente;
- no hay manifest completo de ficheros;
- los limites se validan despues de que el descargador termine, no durante cada escritura interna;
- esta fase reduce riesgo, pero no sustituye al futuro `StorageBackend`.

## Fase 1E — Tests funcionales de descarga

La Fase 1E añade tests funcionales mínimos para `POST /api/licitaciones/{id}/descargar` sin arrancar servidor HTTP, sin ejecutar descargadores reales y sin tocar Internet.

Estrategia elegida:

- importar `app.py` con variables de entorno ficticias de test;
- construir un `InfonaliaHandler` controlado en memoria;
- simular permisos de administrador solo dentro del test;
- usar SQLite temporal;
- usar carpeta temporal para descargas;
- crear un lanzador ficticio temporal para pasar la validación de existencia;
- sustituir `subprocess.run` por funciones falsas dentro de cada test.

Cobertura conseguida:

- descarga simulada correcta con `returncode = 0`;
- creación de fichero ficticio pequeño en la carpeta temporal;
- actualización de `ruta_carpeta` solo cuando la descarga simulada termina bien y la carpeta pasa los límites;
- fallo simulado con `returncode != 0` sin actualizar `ruta_carpeta`;
- timeout simulado sin actualizar `ruta_carpeta`;
- carpeta fuera de límites sin actualizar `ruta_carpeta`;
- URL `file://` rechazada antes de ejecutar `subprocess`;
- URL vacía rechazada antes de ejecutar `subprocess`;
- destino inseguro rechazado antes de ejecutar `subprocess`.

La SQLite productiva `webapp/infonalia_webapp/data/infonalia.db` no se usa en estos tests. Las rutas globales de la app se sustituyen temporalmente y se restauran al terminar.

Pendiente:

- no se valida todavía un descargador real de cada plataforma;
- no hay manifest completo de ficheros;
- no hay `DownloadJob` persistente;
- los límites de tamaño y número de ficheros siguen comprobándose después de que el proceso termine.

## Fase 2A — Seguridad web básica

La Fase 2A añade endurecimiento web básico para uso local/LAN controlado. No significa que la aplicación quede lista para Internet.

Cabeceras añadidas:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY`;
- `Referrer-Policy: same-origin`;
- `Cache-Control: no-store` en respuestas privadas;
- `Permissions-Policy` conservadora para cámara, micrófono y geolocalización.

Las cabeceras se aplican desde los métodos comunes de respuesta del handler. Los assets estáticos reciben cabeceras de seguridad básicas, pero no `Cache-Control: no-store`, para no degradar innecesariamente CSS, JS o imágenes.

Cookies:

- la cookie de sesión mantiene el nombre `infonalia_session`;
- se centraliza su construcción;
- incluye `HttpOnly`, `SameSite=Lax` y `Path=/`;
- `Secure` queda configurable mediante `INFONALIA_COOKIE_SECURE=1`, pero por defecto permanece desactivado para no romper login en HTTP local.

Rate limiting de login:

- se añade limitación en memoria por IP y usuario normalizado;
- valores por defecto: 5 intentos fallidos durante 5 minutos;
- se puede ajustar con `INFONALIA_LOGIN_MAX_ATTEMPTS` e `INFONALIA_LOGIN_WINDOW_SECONDS`;
- al superar el límite se redirige a `/login?error=rate`;
- un login correcto limpia los intentos fallidos de esa combinación IP/usuario.

Pendiente:

- CSRF queda para Fase 2B;
- HTTPS/proxy queda pendiente para despliegue real;
- CSP estricta queda pendiente hasta revisar scripts y estilos inline;
- el rate limiting en memoria no es distribuido;
- esto no sustituye una revisión de seguridad completa antes de exposición pública.

## Fase 2B.1 — Mapa CSRF y estrategia

La Fase 2B.1 prepara CSRF sin activarlo todavía. No cambia `app.py`, no cambia frontend, no cambia URLs, no cambia respuestas JSON y no modifica SQLite. El objetivo es dejar inventariados los endpoints de riesgo y crear helpers puros testeables para la integración posterior.

### Mapa de endpoints mutantes o sensibles

| Método | Ruta | Función backend | Llamada frontend | Auth | Admin | Efecto | CSRF | Motivo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/login` | `handle_login()` | formulario de login | No | No | crea cookie de sesión si las credenciales son válidas | No en 2B.2 inicial | Queda fuera inicialmente porque no hay sesión autenticada previa y ya tiene rate limiting. Revisar login CSRF más adelante si cambia el flujo. |
| POST | `/logout` | ruta directa en `do_POST()` | botón `logout-button` en `index.html` y `logout()` en `app.js` | Sí | No | borra cookie de sesión | Sí | El cierre de sesión es mutante y queda protegido con token CSRF. `GET /logout` ya no borra cookie. |
| POST | `/api/licitaciones` | `api_create_licitacion()` | submit del editor en `app.js` | Sí | Sí | inserta licitación y puede crear/actualizar día Infonalia | Sí | Endpoint autenticado mutante con escritura SQLite. |
| PATCH | `/api/licitaciones/{id}` | `api_update_licitacion()` | `updateEstado()` y submit del editor | Sí | Admin completo; Nuria limitado a estado | actualiza licitación, estado y estado del día | Sí | Endpoint autenticado mutante con escritura SQLite. |
| DELETE | `/api/licitaciones/{id}` | `api_delete_licitacion()` | `deleteLicitacion()` | Sí | Sí | borra licitación y recalcula día | Sí | Endpoint autenticado mutante destructivo. |
| POST | `/api/licitaciones/{id}/descargar` | `api_download_licitacion()` | `downloadLicitacion()` | Sí | Sí | crea carpeta, escribe `HTTP.url`, ejecuta descargador y actualiza `ruta_carpeta` | Sí | Descarga es mutante: escribe ficheros, ejecuta `subprocess` y modifica SQLite. |
| POST | `/api/licitaciones/{id}/ia-preview` | `api_generate_ai_preview()` | `generatePreview()` | Sí | No | genera una vista previa interna; no persiste datos | Sí | Aunque no escribe SQLite, es un POST autenticado con coste y lógica interna. Se protege por regla general de métodos mutantes. |
| POST | `/api/licitaciones/{id}/ia-preview/email` | `api_send_ai_preview_email()` | `emailPreview()` | Sí | No | crea notificación y puede enviar email | Sí | Endpoint autenticado con escritura SQLite y posible efecto externo SMTP. |
| POST | `/api/import/csv` | `api_import_csv()` | submit del importador CSV | Sí | Sí | importa filas y crea/actualiza licitaciones y días | Sí | Endpoint autenticado mutante con subida de fichero y escritura SQLite. |
| POST | `/api/import/msg` | `api_import_msg()` | submit del importador MSG | Sí | Sí | importa MSG, puede usar temporales, enriquecer PDF, crear/actualizar licitaciones y días | Sí | Endpoint autenticado mutante con subida de fichero; puede escribir temporales, usar red/subproceso en enriquecimiento y modificar SQLite. |
| POST | `/api/dias/{id}/revisado` | `api_mark_dia_revisado()` | `markDayReviewed()` | Sí | No | marca día como revisado y puede crear notificación/email | Sí | Endpoint autenticado mutante con escritura SQLite. |
| POST | `/api/dias/{id}/desmarcar-revisado` | `api_unmark_dia_revisado()` | `markDayReviewed()` | Sí | Sí | desmarca revisión y recalcula estado | Sí | Endpoint autenticado mutante con escritura SQLite. |
| POST | `/api/dias/{id}/enviar-nuria` | `api_send_dia_to_nuria()` | `sendDayToNuria()` | Sí | Sí | marca día como enviado a Nuria, crea notificación y puede enviar email | Sí | Endpoint autenticado mutante con escritura SQLite y posible efecto SMTP. |
| DELETE | `/api/dias/{id}` | `api_delete_dia()` | `deleteDia()` | Sí | Sí | borra día y sus licitaciones | Sí | Endpoint autenticado mutante destructivo. |
| POST | `/api/config/users` | `api_create_user()` | `saveUserConfig()` | Sí | Sí | crea usuario | Sí | Endpoint autenticado mutante de configuración y credenciales. |
| PATCH | `/api/config/users/{username}` | `api_update_user()` | `saveUserConfig()` | Sí | Sí | actualiza rol, email, activo o contraseña | Sí | Endpoint autenticado mutante de configuración y credenciales. |
| DELETE | `/api/config/users/{username}` | `api_delete_user()` | `deleteUserConfig()` | Sí | Sí | desactiva usuario | Sí | Endpoint autenticado mutante de configuración de acceso. |
| PATCH | `/api/config/settings` | `api_update_settings()` | `saveSettingsPayload()` | Sí | Sí | actualiza mantenimiento y SMTP | Sí | Endpoint autenticado mutante de configuración global. |
| POST | `/api/config/test-smtp` | `api_test_smtp()` | `testSmtpConfig()` | Sí | Sí | envía correo de prueba | Sí | Endpoint autenticado con efecto externo SMTP. |
| POST | `/api/news` | `api_create_news()` | `saveNews()` | Sí | Admin o editor | crea noticia | Sí | Endpoint autenticado mutante con escritura SQLite. |
| PATCH | `/api/news/{id}` | `api_update_news()` | `saveNews()` | Sí | Admin o editor | actualiza noticia | Sí | Endpoint autenticado mutante con escritura SQLite. |
| DELETE | `/api/news/{id}` | `api_delete_news()` | `deleteNews()` | Sí | Admin o editor | borra noticia | Sí | Endpoint autenticado mutante destructivo. |
| GET | `/api/public/noticias` | `api_public_news()` | `public.js` y Firebase `public.js` | No | No | lectura pública de noticias publicadas | No | Endpoint público de solo lectura; protegerlo rompería la web pública/Firebase. |

Endpoints GET privados como `/api/me`, `/api/dias`, `/api/licitaciones`, `/api/notificaciones`, `/api/config`, `/api/news` y `/api/health` no deben requerir CSRF porque son lecturas. Si alguno empieza a modificar estado en el futuro, deberá pasar a método mutante y entrar en esta tabla.

### Protección prevista para 2B.2

Se protegerán todos los endpoints autenticados con `POST`, `PUT`, `PATCH` o `DELETE`, con estas excepciones iniciales:

- `POST /login`: excluido inicialmente por no tener sesión previa y por tener rate limiting.
- rutas bajo `/api/public/`: excluidas para no romper web pública ni Firebase; actualmente son GET de lectura.
- `POST /logout`: protegido con CSRF desde Fase 2B.4.

### Estrategia de token

- Generación: `generate_csrf_token()` con `secrets.token_urlsafe(32)`.
- Almacenamiento previsto: añadir el token al payload firmado de sesión en una fase posterior, junto a usuario, rol e `iat`.
- Entrega al frontend: devolver el token en `/api/me` o en un bootstrap privado equivalente después de login.
- Envío desde frontend: incluirlo en cada petición mutante autenticada mediante header `X-CSRF-Token`.
- Validación backend: comparar el token esperado de la sesión con el token recibido usando `hmac.compare_digest`.
- Código HTTP previsto: `403 Forbidden` con JSON de error cuando falte el token o no coincida.

### Riesgos pendientes

- CSRF aún no está activo; esta fase solo prepara mapa, estrategia y helpers puros.
- `GET /logout` ya no limpia sesión desde Fase 2B.4.
- La integración frontend/backend debe hacerse de forma incremental para no romper importación, descargas, noticias ni Firebase.
- Si hay XSS, el token expuesto al frontend también quedaría comprometido; por eso CSP estricta sigue pendiente.
- HTTPS/proxy sigue pendiente para cualquier exposición fuera de entorno local/LAN.

## Fase 2B.2 — CSRF en importaciones y descarga

La Fase 2B.2 activa CSRF de forma mínima y limitada. No protege todavía todos los endpoints mutantes; solo cubre los flujos críticos que ya tenían tests funcionales recientes.

Endpoints protegidos:

- `POST /api/import/csv`;
- `POST /api/import/msg`;
- `POST /api/licitaciones/{id}/descargar`.

Endpoints aún no protegidos:

- creación, edición y borrado manual de licitaciones;
- cambios de estado y acciones sobre días Infonalia;
- usuarios y configuración;
- noticias;
- vista previa IA y envío de vista previa por email;
- `GET /logout`, que ya no limpia sesión desde Fase 2B.4.

Sesión y token:

- la app mantiene la cookie `infonalia_session`;
- la sesión sigue siendo una cookie firmada, no una sesión server-side nueva;
- el token CSRF se guarda dentro del payload firmado de la cookie;
- el login genera un token nuevo;
- las sesiones antiguas sin token reciben uno perezosamente y se refrescan con `Set-Cookie`;
- el token no se guarda en SQLite.

Entrega al frontend:

- `/api/me` devuelve `csrf_token` solo para usuario autenticado;
- `app.js` lo guarda en memoria dentro de `appState.csrfToken`;
- no se usa `localStorage`;
- no se expone token en páginas públicas ni Firebase.

Envío del token:

- el frontend añade `X-CSRF-Token` solo en importación CSV, importación MSG y descarga de licitación;
- no se modifica la UX;
- no se cambian URLs;
- no se cambian nombres de campos `FormData`.

Respuesta ante fallo:

- si falta el token o no coincide, el backend devuelve `403 Forbidden`;
- con token válido, los flujos mantienen su comportamiento previo.

Riesgos pendientes:

- el resto de endpoints mutantes sigue sin CSRF;
- logout usa `POST /logout` con CSRF desde Fase 2B.4;
- HTTPS/proxy y CSP estricta siguen pendientes;
- `app.py` sigue siendo monolítico y la extensión de CSRF debe continuar por fases pequeñas.

## Fase 2B.3 — CSRF en mutaciones privadas restantes

La Fase 2B.3 extiende la protección CSRF al resto de endpoints mutantes del panel privado, manteniendo una allowlist explícita y sin convertirlo en una validación opaca sobre cualquier ruta.

Endpoints protegidos adicionalmente:

- `POST /api/licitaciones`;
- `PATCH /api/licitaciones/{id}`;
- `DELETE /api/licitaciones/{id}`;
- `POST /api/licitaciones/{id}/ia-preview`;
- `POST /api/licitaciones/{id}/ia-preview/email`;
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

La protección previa de 2B.2 se mantiene para:

- `POST /api/import/csv`;
- `POST /api/import/msg`;
- `POST /api/licitaciones/{id}/descargar`.

Frontend:

- `app.js` añade `X-CSRF-Token` a todas las llamadas mutantes privadas existentes;
- las llamadas GET no cambian;
- no se modifica la UX;
- no se toca Firebase ni la web pública.

Backend:

- `do_POST()`, `do_PATCH()` y `do_DELETE()` validan CSRF solo si la ruta está en la allowlist de mutaciones privadas;
- si falta el token o no coincide, se devuelve `403 Forbidden`;
- rutas desconocidas no se convierten en error CSRF: siguen respondiendo `404 Not Found`.

Endpoints excluidos:

- `POST /login`, porque no hay sesión autenticada previa y ya existe rate limiting;
- `POST /logout`, protegido con CSRF desde Fase 2B.4;
- endpoints GET privados de lectura;
- endpoints públicos y Firebase.

Riesgos pendientes:

- CSRF no sustituye HTTPS/proxy ni CSP estricta;
- si aparece XSS, el token en memoria del frontend podría quedar comprometido;
- `app.py` sigue monolítico y conviene no mezclar esta protección con refactors grandes.

## Fase 2B.4 — Logout por POST con CSRF

La Fase 2B.4 elimina el cierre de sesión mediante GET. El objetivo es evitar que una visita inducida a `/logout` pueda borrar la sesión del usuario.

Cambios aplicados:

- `GET /logout` devuelve `405 Method Not Allowed` y no borra cookie;
- `POST /logout` borra la cookie solo cuando la sesión autenticada presenta `X-CSRF-Token` válido;
- si la sesión ya no es válida, `POST /logout` limpia la cookie residual y redirige a `/login`;
- `index.html` cambia el enlace de salida por un botón;
- `app.js` envía `POST /logout` con el token en memoria;
- Firebase y páginas públicas no cambian.

Comportamiento esperado:

- pulsar "Salir" mantiene la UX de cierre de sesión y redirige a `/login`;
- una petición GET externa a `/logout` no cierra sesión;
- un POST sin token o con token inválido devuelve `403 Forbidden`.

Riesgos pendientes:

- CSRF depende de que no exista XSS que pueda leer el token en memoria;
- HTTPS/proxy sigue pendiente para exposición fuera de LAN/local;
- CSP estricta sigue pendiente;
- `app.py` sigue concentrando enrutado, sesión y respuestas.

## Fase 2C.1 — CSP estricta privada

La Fase 2C.1 añade una política CSP estricta solo a respuestas privadas. No se aplica todavía a la web pública ni a Firebase para evitar mezclar políticas con el render público actual.

Cambios aplicados:

- se añade `Content-Security-Policy` en `build_security_headers(is_private=True)`;
- la CSP privada usa recursos propios: `default-src 'self'`, `script-src 'self'`, `style-src 'self'`, `connect-src 'self'`, `img-src 'self' data:`, `font-src 'self'`;
- se bloquean objetos y bases externas con `object-src 'none'` y `base-uri 'self'`;
- se limita envío de formularios con `form-action 'self'`;
- se mantiene `frame-ancestors 'none'`, alineado con `X-Frame-Options: DENY`;
- no se usa `unsafe-inline` ni `unsafe-eval`;
- el script inline de `login.html` pasa a `/static/login.js`;
- `index.html` y `login.html` quedan sin scripts inline ni atributos inline.

Ámbito:

- panel privado;
- login privado;
- respuestas JSON privadas.

Fuera de esta fase:

- web pública, resuelta después en Fase 2C.2;
- Firebase, resuelto después en Fase 2C.2;
- emails HTML, que requieren estilos inline por compatibilidad con clientes de correo;
- endurecimiento específico de XSS en render dinámico.

Riesgos pendientes:

- la app privada sigue usando `innerHTML` para renderizar vistas; aunque los datos se escapan en los puntos principales, conviene revisar XSS con una fase específica;
- los enlaces dinámicos del panel privado quedan endurecidos después en Fase 2C.4;
- CSP pública queda resuelta en Fase 2C.2;
- HTTPS/proxy sigue pendiente para exposición real fuera de LAN/local.

## Fase 2C.2 — CSP pública y Firebase

La Fase 2C.2 aplica CSP a la web pública servida por la app y al despliegue estático de Firebase.

Cambios aplicados:

- `public.html` deja de usar el script inline `window.PRIVATE_APP_URL`;
- `firebase/public_firebase/index.html` deja de usar script inline;
- la URL privada pasa a `data-private-app-url` en el `<body>`;
- `public.js` lee esa URL desde `document.body.dataset.privateAppUrl`;
- se añade CSP pública desde `build_security_headers(is_private=False)`;
- `firebase/public_firebase/firebase.json` añade headers globales de seguridad, incluida la misma CSP pública;
- la política pública usa recursos propios: `default-src 'self'`, `script-src 'self'`, `style-src 'self'`, `connect-src 'self'`, `img-src 'self'`, `font-src 'self'`;
- no se usa `unsafe-inline` ni `unsafe-eval`.

Ámbito:

- web pública servida por `webapp/infonalia_webapp`;
- hosting estático `firebase/public_firebase`;
- assets públicos propios.

Fuera de esta fase:

- revisión XSS profunda del render público con `innerHTML`, parcialmente endurecida después en Fase 2C.3;
- integración de noticias públicas desde una API real en Firebase;
- HTTPS/proxy de la app privada.

Riesgos pendientes:

- `public.js` sigue usando `innerHTML` para montar páginas desde plantillas internas; requiere auditoría XSS específica antes de aceptar contenido dinámico rico;
- la web Firebase intenta cargar `/api/public/noticias` en el mismo origen y cae a lista vacía si no existe API;
- emails HTML siguen usando estilos inline por compatibilidad con clientes de correo.

## Fase 2C.3 — Endurecimiento XSS mínimo en web pública

La Fase 2C.3 revisa el punto dinámico más sensible del render público tras activar CSP: los enlaces generados por el helper `button()` dentro de plantillas inyectadas con `innerHTML`.

Cambios aplicados:

- `public.js` y `firebase/public_firebase/static/public.js` añaden `safeHref()`;
- el helper solo permite rutas relativas, anclas y URLs `http`/`https`;
- esquemas peligrosos como `javascript:` o valores vacíos se degradan a `#`;
- el texto del enlace, la variante CSS y el `href` se escapan antes de entrar en la plantilla HTML;
- se añade un test de seguridad que evita volver a interpolar `href` sin escape.

Ámbito:

- web pública servida por `webapp/infonalia_webapp`;
- hosting estático `firebase/public_firebase`;
- enlace dinámico de zona privada y botones públicos generados desde plantillas internas.

Fuera de esta fase:

- eliminación completa de `innerHTML` en la web pública;
- auditoría profunda de todos los renders privados de `app.js`;
- noticias Markdown seguro;
- cambios de esquema SQLite.

Riesgos pendientes:

- `public.js` sigue renderizando plantillas completas con `innerHTML`;
- los arrays de contenido público son constantes locales, pero si en el futuro pasan a ser editables deberán escapar todos los campos antes de renderizarse;
- la app privada sigue necesitando una fase específica de revisión XSS en `app.js`.

## Fase 2C.4 — Endurecimiento XSS mínimo en enlaces privados

La Fase 2C.4 revisa los enlaces dinámicos del panel privado que se insertan en plantillas con `innerHTML`, especialmente `enlace_perfil` y `enlace_infonalia`.

Cambios aplicados:

- `normalizeUrl()` solo conserva URLs `http`/`https`;
- los dominios sin protocolo siguen normalizándose a `https://`;
- rutas relativas y anclas internas siguen permitidas;
- valores con esquemas explícitos no web, como `javascript:`, `data:`, `mailto:` o `file:`, se descartan;
- URLs protocol-relative `//...` se descartan para evitar ambigüedad;
- se añade un test estático de seguridad que fija esta política.

Ámbito:

- enlaces de perfil e Infonalia en tarjetas de licitación;
- enlaces equivalentes del panel de calendario;
- render privado actual sin tocar endpoints ni SQLite.

Fuera de esta fase:

- eliminación completa de `innerHTML` en `app.js`;
- auditoría profunda de todos los componentes privados;
- sanitización Markdown;
- cambios de persistencia.

Riesgos pendientes:

- `app.js` sigue renderizando muchas vistas con `innerHTML`;
- los atributos `data-*` más usados quedan endurecidos después en Fase 2C.5, pero todavía no hay una auditoría completa de coerción de identificadores;
- si en el futuro se admiten URLs no web por necesidad funcional, deberán tener validación explícita y tests propios.

## Fase 2C.5 — Escape explícito de atributos dinámicos privados

La Fase 2C.5 revisa los atributos `data-*` privados que se generan dentro de plantillas HTML en `app.js`.

Cambios aplicados:

- los ids de días, licitaciones y noticias se escapan antes de interpolarse en `data-*`;
- la fecha dinámica del calendario se escapa antes de interpolarse en `data-calendar-date`;
- se mantiene el comportamiento actual de eventos porque el DOM entrega los mismos valores para ids numéricos y fechas normales;
- se añade un test estático que evita volver a interpolar `${item.id}`, `${dia.id}` o `${key}` directamente en atributos sensibles.

Ámbito:

- botones de días Infonalia;
- calendario;
- botones de noticias privadas;
- botones de acciones de licitaciones.

Fuera de esta fase:

- conversión de renderizado `innerHTML` a creación DOM nodo a nodo;
- validación semántica de ids en el frontend;
- cambios de endpoints o respuestas JSON.

Riesgos pendientes:

- `app.js` sigue usando `innerHTML` como mecanismo principal de render;
- algunas clases CSS dinámicas proceden de helpers propios y quedan endurecidas después en Fase 2C.6;
- la validación real de permisos e ids sigue perteneciendo al backend.

## Fase 2C.6 — Tokens seguros para clases CSS privadas

La Fase 2C.6 revisa las clases CSS dinámicas generadas a partir de estados privados en `app.js`.

Cambios aplicados:

- se añade `cssClassToken()` para convertir valores dinámicos en tokens CSS seguros;
- `badgeClass()` delega en ese helper;
- se conservan letras, números, guiones y guiones bajos;
- acentos y marcas diacríticas se eliminan como antes;
- cualquier otro carácter se sustituye por `-`;
- tokens vacíos vuelven al fallback `Pendiente`;
- se añade un test estático que evita volver al reemplazo limitado de espacios.

Ámbito:

- badges de estado de días y licitaciones;
- eventos del calendario que usan `event-${stateClass}`;
- clases derivadas de estados internos actuales.

Fuera de esta fase:

- sustitución de `innerHTML` por creación DOM;
- validación semántica de estados en frontend;
- cambios en etiquetas visibles de estados.

Riesgos pendientes:

- `app.js` sigue usando plantillas HTML amplias;
- algunos valores dinámicos todavía se renderizan como texto escapado, no como nodos DOM;
- la lista de estados válidos sigue siendo una regla de negocio compartida con backend.

## Fase 2C.7 — Cierre de auditoría XSS incremental privada

La Fase 2C.7 no elimina todavía `innerHTML`, pero cierra la primera ronda de endurecimiento XSS incremental del panel privado con una guarda automática.

Cobertura acumulada:

- Fase 2C.1: CSP privada estricta sin `unsafe-inline` ni `unsafe-eval`;
- Fase 2C.4: enlaces privados filtrados por `normalizeUrl()`;
- Fase 2C.5: escape explícito de ids y fechas en atributos `data-*`;
- Fase 2C.6: tokens CSS dinámicos centralizados y limitados;
- Fase 2C.7: test estático contra patrones HTML peligrosos obvios en `app.js`.

Guarda añadida:

- `app.js` no debe usar `insertAdjacentHTML`;
- `app.js` no debe usar `outerHTML`;
- `app.js` no debe usar `document.write`;
- `app.js` no debe contener literales `javascript:`;
- `app.js` no debe incluir plantillas `<script>` ni `<style>`;
- `app.js` no debe incluir atributos inline tipo `onclick=`.

Ámbito:

- panel privado actual;
- renderizado JavaScript existente;
- prevención de regresiones obvias mientras se mantenga `innerHTML`.

Fuera de esta fase:

- refactor de `app.js` a creación DOM segura;
- eliminación completa de `innerHTML`;
- sanitización de Markdown;
- validación semántica de todos los payloads en frontend.

Riesgos pendientes:

- `innerHTML` sigue presente y debe tratarse como deuda técnica controlada;
- los tests estáticos no sustituyen una auditoría manual completa;
- cualquier nueva funcionalidad que acepte HTML enriquecido debe esperar a la fase de Markdown seguro con sanitizador.

## Fase 2D — Puerta previa a checkpoints peligrosos

La Fase 2D documenta y testea una puerta comun antes de entrar en cambios de alto riesgo.

Motivo:

- las siguientes fases probables pueden tocar SQLite, migraciones, CSRF global, StorageBackend, noticias Markdown o refactor de `app.py`;
- esas areas pueden romper datos, seguridad, endpoints o flujos operativos;
- conviene tener una checklist versionada antes de empezar cualquiera de ellas.

Cambios aplicados:

- se crea `docs/CHECKPOINTS_PELIGROSOS.md`;
- se enumeran las seis areas de alto riesgo;
- se fijan checks minimos antes de commit;
- se documenta que no se debe hacer push desde el checkpoint;
- se anade un test que garantiza que la puerta conserva temas y comandos minimos.

Fuera de esta fase:

- no se toca SQLite;
- no se crean migraciones;
- no se cambia CSRF;
- no se implementa StorageBackend;
- no se implementan noticias Markdown;
- no se refactoriza `app.py`.

## Fase 2E — Precheck StorageBackend

La Fase 2E prepara el terreno para un futuro StorageBackend sin implementarlo.

Cambios aplicados:

- se crea `docs/PRECHECK_STORAGEBACKEND.md`;
- se inventaria el flujo actual de `POST /api/licitaciones/{id}/descargar`;
- se listan funciones, constantes y scripts implicados;
- se documentan invariantes que no deben romperse;
- se enumeran riesgos actuales;
- se deja una estrategia recomendada antes de implementar LocalStorage o Dropbox;
- se anade test documental para asegurar que el precheck cubre las piezas clave.

Fuera de esta fase:

- no se implementa `StorageBackend`;
- no se implementa Dropbox;
- no se crea `DownloadJob`;
- no se cambia SQLite;
- no se toca `api_download_licitacion()`;
- no se ejecutan descargadores reales.

## Fase 2F — Precheck noticias Markdown

La Fase 2F prepara el terreno para noticias Markdown seguro sin implementarlo.

Cambios aplicados:

- se crea `docs/PRECHECK_NOTICIAS_MARKDOWN.md`;
- se inventaria la tabla actual `noticias`;
- se listan endpoints privados y publicos;
- se documenta el render privado y publico actual;
- se documentan contratos futuros `NewsArticle` y `NewsRenderer`;
- se fijan invariantes para no permitir HTML libre;
- se enumeran riesgos antes de parser, sanitizador o migracion;
- se anade test documental para asegurar que el precheck cubre piezas clave.

Fuera de esta fase:

- no se implementa Markdown;
- no se anade parser Markdown;
- no se anade sanitizador;
- no se cambia SQLite;
- no se cambia `api_public_news()`;
- no se cambia `api_create_news()`;
- no se cambia `api_update_news()`;
- no se cambia `public.js`;
- no se cambia Firebase.

## Fase 2G — Precheck SQLite y migraciones

La Fase 2G prepara el terreno para migraciones SQLite formales sin implementarlas.

Cambios aplicados:

- se crea `docs/PRECHECK_SQLITE_MIGRACIONES.md`;
- se inventaria la persistencia actual: `DB_PATH`, `db()`, `db_session()`, `init_db()`, `ensure_column()` y `seed_users_and_settings()`;
- se listan tablas e indices actuales;
- se documenta que el esquema evoluciona hoy con `CREATE TABLE IF NOT EXISTS`, `ensure_column()` y `CREATE INDEX IF NOT EXISTS`;
- se fijan invariantes para no tocar la SQLite productiva desde tests;
- se enumeran riesgos antes de introducir `schema_migrations` o migraciones versionadas;
- se anade test documental para asegurar que el precheck cubre piezas clave.

Fuera de esta fase:

- no se cambia SQLite;
- no se implementan migraciones;
- no se crea `schema_migrations`;
- no se toca `app.py`;
- no se modifica la base productiva;
- no se cambian endpoints;
- no se cambian respuestas JSON.

## Fase 2H — Precheck CSRF global

La Fase 2H prepara el terreno para pasar de una allowlist explicita de CSRF a una politica global sin implementarla.

Cambios aplicados:

- se crea `docs/PRECHECK_CSRF_GLOBAL.md`;
- se inventarian helpers puros de `csrf.py`;
- se documenta la integracion real en `app.py`: `CSRF_HEADER`, `current_user()`, `require_csrf_token()` y `csrf_required_for_path()`;
- se listan rutas protegidas, rutas excluidas y rutas que deben seguir devolviendo `404 Not Found`;
- se documenta como `app.js` recibe el token desde `/api/me` y lo envia mediante `csrfHeaders()`;
- se fijan invariantes para no romper login, logout, GET privados, rutas publicas ni Firebase;
- se enumeran riesgos antes de sustituir la allowlist por una politica global;
- se anade test documental para asegurar que el precheck cubre piezas clave.

Fuera de esta fase:

- no se activa CSRF global;
- no se cambia `csrf_required_for_path()`;
- no se cambia `require_csrf_token()`;
- no se cambia frontend;
- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se toca SQLite;
- no se cambia Firebase.

## Fase 2I — Precheck refactor de app.py

La Fase 2I prepara el terreno para refactorizar `app.py` sin hacerlo todavia.

Cambios aplicados:

- se crea `docs/PRECHECK_REFACTOR_APP.md`;
- se inventaria la superficie actual de `app.py`: entorno, rutas, sesiones, SQLite, importaciones, descargas, noticias, notificaciones y HTTP;
- se documenta la responsabilidad de `InfonaliaHandler` y sus metodos `do_GET()`, `do_POST()`, `do_PATCH()` y `do_DELETE()`;
- se identifican modulos ya extraidos o cercanos como `web_security.py`, `csrf.py`, `limits.py` y `core/`;
- se fijan invariantes para conservar endpoints, respuestas JSON, login, logout, CSRF, SQLite temporal y Firebase;
- se propone un orden seguro de extraccion empezando por funciones puras;
- se anade test documental para asegurar que el precheck cubre piezas clave.

Fuera de esta fase:

- no se refactoriza `app.py`;
- no se mueve codigo;
- no se cambian imports;
- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se toca SQLite;
- no se activan migraciones;
- no se activa CSRF global;
- no se implementa `StorageBackend`;
- no se implementa Markdown;
- no se cambia frontend;
- no se cambia Firebase.

## Fase 2J — Extraccion de normalizacion pura

La Fase 2J inicia el refactor de `app.py` con una extraccion pequena y reversible.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/normalization.py`;
- se mueven helpers puros: `clean_text()`, `bool_text()`, `parse_money()`, `parse_date_value()` y `parse_time_value()`;
- `app.py` importa esos nombres y sigue funcionando como fachada publica para llamadas existentes;
- se anaden tests puros para confirmar formatos actuales y que importar `normalization.py` no importa `app.py` ni modulos con efectos laterales.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia SQLite;
- no se mueven handlers HTTP;
- no se toca `InfonaliaHandler`;
- no se cambia frontend;
- no se cambia Firebase;
- no se ejecutan descargadores reales.

## Fase 2K — Extraccion de formateo puro

La Fase 2K continua el refactor incremental de `app.py` con otra extraccion pura.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/formatting.py`;
- se mueven `format_date_es()` y `format_datetime_es()`;
- `app.py` importa esos nombres y los conserva como fachada para llamadas existentes;
- se anaden tests puros para confirmar formatos actuales y que importar `formatting.py` no importa `app.py` ni modulos con efectos laterales.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia SQLite;
- no se mueven handlers HTTP;
- no se toca `InfonaliaHandler`;
- no se cambia frontend;
- no se cambia Firebase;
- no se ejecutan descargadores reales.

## Fase 2L — Extraccion de nombres de carpeta puros

La Fase 2L continua el refactor incremental de `app.py` con helpers puros de nombres de carpeta.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/folder_names.py`;
- se mueven `safe_folder_name()`, `folder_text()`, `expediente_folder_text()`, `short_folder_phrase()`, `extract_municipio_from_organismo()`, `extract_residencia_phrase()`, `extract_hospital_phrase()` y `extract_objeto_folder_key()`;
- `app.py` importa esos nombres y los conserva como fachada para llamadas existentes;
- se dejan fuera helpers con `Path`, Dropbox o rutas reales para no mezclar este refactor con StorageBackend;
- se anaden tests puros para confirmar formatos actuales y que importar `folder_names.py` no importa `app.py` ni modulos con efectos laterales.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia SQLite;
- no se mueven handlers HTTP;
- no se toca `InfonaliaHandler`;
- no se cambia StorageBackend;
- no se cambia frontend;
- no se cambia Firebase;
- no se ejecutan descargadores reales.

## Fase 2M — Extraccion de URL y plataforma

La Fase 2M continua el refactor incremental de `app.py` con helpers puros de URL y deteccion de plataforma.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/url_helpers.py`;
- se mueven `normalize_url()`, `should_update_url()` y `detectar_plataforma()`;
- `app.py` importa esos nombres y los conserva como fachada para llamadas existentes;
- se anaden tests puros para confirmar reglas actuales de normalizacion y plataformas conocidas;
- se confirma que importar `url_helpers.py` no importa `app.py` ni modulos con efectos laterales.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia SQLite;
- no se mueven handlers HTTP;
- no se toca `InfonaliaHandler`;
- no se endurece la politica de URLs;
- no se cambia frontend;
- no se cambia Firebase;
- no se ejecuta red real.

## Fase 2N — Extraccion de parsing CSV puro

La Fase 2N continua el refactor incremental de `app.py` con el parsing CSV que no escribe en SQLite.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/csv_parsing.py`;
- se mueven `CSV_ALIASES`, `normalize_key()`, `csv_alias_map()`, `row_value()`, `normalize_estado()`, `decode_csv_bytes()`, `read_csv_rows()` y `build_payload_from_csv_row()`;
- `app.py` importa esos nombres y los conserva como fachada para llamadas existentes;
- `import_csv_content()` se mantiene en `app.py` porque crea/actualiza datos en SQLite;
- se anaden tests puros para alias, estado, lectura de filas y payload CSV;
- se confirma que importar `csv_parsing.py` no importa `app.py` ni modulos con efectos laterales.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia SQLite;
- no se cambia `import_csv_content()`;
- no se mueven handlers HTTP;
- no se toca `InfonaliaHandler`;
- no se cambia frontend;
- no se cambia Firebase;
- no se usan datos reales.

## Fase 2O — Extraccion de helpers puros de noticias

La Fase 2O continua el refactor incremental de `app.py` con helpers de noticias que no escriben en SQLite.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/news_helpers.py`;
- se mueven `NEWS_STATUSES`, `slugify()`, `normalize_news_status()` y `news_to_dict()`;
- `app.py` importa esos nombres y los conserva como fachada para llamadas existentes;
- se anaden tests puros para slug, estado y forma JSON actual de noticias;
- se confirma que importar `news_helpers.py` no importa `app.py` ni modulos con efectos laterales.

Fuera de esta fase:

- no se implementa Markdown;
- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia SQLite;
- no se mueven handlers HTTP;
- no se toca `InfonaliaHandler`;
- no se cambia frontend;
- no se cambia Firebase.

## Fase 2P — Extraccion de parsing textual MSG/PDF

La Fase 2P continua el refactor incremental de `app.py` con helpers que solo parsean texto ya disponible.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/msg_parsing.py`;
- se mueven `extraer_despues_de_dos_puntos()`, `extract_msg_date()`, `extraer_fecha_msg()`, `extract_tipo_contrato()` y `extract_hora_limite_from_text()`;
- `app.py` importa esos nombres y los conserva como fachada para llamadas existentes;
- `parse_msg_body()`, `enrich_from_infonalia_pdf()` e `import_msg_content()` se mantienen en `app.py`;
- se anaden tests puros para reglas actuales de extraccion.

Fuera de esta fase:

- no se ejecuta red real;
- no se ejecuta `pdftotext`;
- no se leen MSG reales;
- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia SQLite;
- no se mueven handlers HTTP;
- no se cambia frontend;
- no se cambia Firebase.

## Fase 2Q — Extraccion de helpers puros de vista previa IA

La Fase 2Q continua el refactor incremental de `app.py` con la parte pura de la vista previa IA.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/ai_preview_helpers.py`;
- se mueven `extract_lotes_from_text()`, `extract_keyword_context()`, `extract_centros_from_text()` y `preview_payload_to_text()`;
- `app.py` importa esos nombres y los conserva como fachada para llamadas existentes;
- `build_ai_preview_payload()` se mantiene en `app.py` porque lee SQLite;
- se anaden tests puros para las reglas actuales.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia SQLite;
- no se cambia el envio de email;
- no se mueven handlers HTTP;
- no se cambia frontend;
- no se cambia Firebase.

## Fase 2R — Extraccion de render puro de notificaciones

La Fase 2R continua el refactor incremental de `app.py` separando parseo y HTML de notificaciones.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/notification_rendering.py`;
- se mueven `notification_body_parts()`, `parse_day_review_notification()` y el constructor HTML puro;
- `app.py` conserva `render_notification_email_html()` como envoltura para pasar `PLATFORM_URL` y fecha actual;
- se anaden tests puros para parseo, detalles y HTML.

Fuera de esta fase:

- no se cambia SMTP;
- no se cambia el logo embebido;
- no se cambia SQLite;
- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia frontend;
- no se cambia Firebase.

## Fase 2S — Migraciones SQLite versionadas

La Fase 2S introduce la base minima de migraciones SQLite.

Preparacion:

- se confirma que `.local_backups/` queda ignorado;
- se crea backup local de `webapp/infonalia_webapp/data/infonalia.db` antes de integrar migraciones.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/db_migrations.py`;
- se introduce la tabla `schema_migrations`;
- se registra la migracion baseline `0001_baseline_schema`;
- `init_db()` ejecuta el runner despues de asegurar el esquema historico;
- se anaden tests con SQLite temporal para idempotencia, duplicados, fallo no registrado e integracion con `init_db()`.

Fuera de esta fase:

- no se transforman datos existentes;
- no se eliminan ni renombran columnas;
- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia frontend;
- no se cambia Firebase.

## Fase 2T — StorageBackend local aislado

La Fase 2T introduce una implementacion local del contrato `StorageBackend` sin conectarla aun al flujo real de descarga.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/local_storage.py`;
- se implementa `LocalStorageBackend`;
- se aceptan URIs `local://...`;
- se rechazan rutas inseguras, absolutas o con `..`;
- se calcula tamano y hash SHA-256 de ficheros guardados;
- se anaden tests con `tmp_path` para guardar, crear carpetas, obtener ruta visible, borrar y rechazar rutas inseguras.

Fuera de esta fase:

- no se implementa Dropbox;
- no se cambia `api_download_licitacion()`;
- no se ejecutan descargadores reales;
- no se cambia SQLite;
- no se cambia `ruta_carpeta`;
- no se cambian endpoints ni respuestas JSON.

## Fase 2U — Renderer Markdown seguro aislado

La Fase 2U introduce una implementacion aislada del contrato `NewsRenderer`.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/safe_markdown.py`;
- se implementa `SafeMarkdownRenderer`;
- se soportan titulos, parrafos, listas, negrita, cursiva y enlaces `http/https`;
- se escapa HTML crudo;
- se eliminan scripts, estilos, iframes, eventos inline y enlaces no seguros;
- se anaden tests hostiles para `script`, `onclick`, `javascript:` e imagenes Markdown.

Fuera de esta fase:

- no se cambia SQLite;
- no se cambia `content`;
- no se cambia `api_public_news()`;
- no se cambia `api_create_news()`;
- no se cambia `api_update_news()`;
- no se cambia `public.js`;
- no se cambia Firebase.

## Fase 2V — CSRF global en decision de app.py

La Fase 2V conecta el helper global de CSRF con la decision real de `app.py`.

Cambios aplicados:

- `InfonaliaHandler.csrf_required_for_path()` delega en `is_csrf_required()`;
- se conserva una verificacion de ruta mutante conocida para no convertir rutas desconocidas en error CSRF;
- `POST /login`, `GET`, rutas publicas y rutas desconocidas siguen sin requerir CSRF;
- rutas privadas mutantes conocidas siguen exigiendo `X-CSRF-Token`;
- se amplian tests de CSRF para cubrir la politica global desde `app.py`.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia frontend;
- no se cambia Firebase;
- no se toca SQLite.

## Fase 2W — Manifest local en descargas correctas

La Fase 2W conecta el StorageBackend local con el flujo real de descarga sin cambiar la API.

Cambios aplicados:

- tras una descarga correcta se genera `.infonalia_manifest.json`;
- el manifest incluye esquema, backend, URI de carpeta, URL origen y ficheros con ruta relativa, URI, tamano y checksum;
- el manifest se escribe mediante `LocalStorageBackend`;
- el escaneo de limites ignora el manifest interno para que no altere el conteo de ficheros descargados;
- `ruta_carpeta` solo se actualiza si el manifest se crea correctamente.

Fuera de esta fase:

- no se cambia la respuesta JSON;
- no se cambia SQLite;
- no se implementa Dropbox;
- no se ejecutan descargadores reales en tests;
- no se cambian endpoints;
- no se cambia frontend ni Firebase.

## Fase 2X — Noticias Markdown conectadas de forma compatible

La Fase 2X conecta el renderer Markdown seguro al flujo de noticias sin migracion SQLite.

Cambios aplicados:

- `news_to_dict()` mantiene `content` y anade `contentHtml`;
- `contentHtml` se genera con `SafeMarkdownRenderer`;
- el frontend publico usa `contentHtml` si existe;
- el fallback de texto escapado se conserva para placeholders y datos sin HTML;
- se aplica el mismo fallback compatible en la copia Firebase.

Fuera de esta fase:

- no se cambia SQLite;
- no se renombra `content`;
- no se eliminan campos JSON existentes;
- no se anade editor visual;
- no se cambia el origen de datos de Firebase.

## Fase 2Y — Tabla preparatoria download_jobs

La Fase 2Y prepara SQLite para registrar jobs de descarga futuros sin activar una cola real.

Cambios aplicados:

- se anade la migracion `0002_download_jobs`;
- se crea la tabla `download_jobs`;
- se guardan licitacion, estado, backend, URI, manifest, error y marcas temporales;
- se anaden indices por licitacion, estado y fecha de creacion;
- se amplian tests de migraciones para verificar esquema e idempotencia.

Fuera de esta fase:

- no se implementan jobs reales;
- no se cambia `api_download_licitacion()`;
- no se cambian endpoints ni respuestas JSON;
- no se implementa Dropbox real;
- no se cambia frontend ni Firebase.

## Fase 2Z — Tablas preparatorias de historial de importaciones

La Fase 2Z prepara SQLite para auditar importaciones futuras sin conectar los flujos CSV o MSG actuales.

Cambios aplicados:

- se anade la migracion `0003_import_history`;
- se crea `import_runs` para ejecuciones de importacion;
- se crea `import_results` para resultados por candidato;
- se anaden indices por fuente, estado, ejecucion, licitacion, identificador externo y fingerprint;
- se amplian tests de migraciones para verificar esquema e idempotencia.

Fuera de esta fase:

- no se registra todavia ninguna importacion real;
- no se cambia `POST /api/import/csv`;
- no se cambia `POST /api/import/msg`;
- no se cambian endpoints ni respuestas JSON;
- no se implementa PLACE real;
- no se cambia frontend ni Firebase.

## Fase 3A — Registro sincro de jobs de descarga

La Fase 3A usa la tabla `download_jobs` para auditar descargas sin convertir el flujo en una cola real.

Cambios aplicados:

- el endpoint crea un job `running` justo antes de ejecutar el descargador local;
- una descarga correcta cierra el job como `completed`;
- fallos de proceso, timeout, limites o manifest cierran el job como `failed`;
- el job guarda backend local, URI de carpeta y URI de manifest cuando la descarga termina bien;
- se amplian tests funcionales de descarga para cubrir jobs completados, fallidos y validaciones previas.

Fuera de esta fase:

- no se implementa ejecucion asincrona;
- no se cambian respuestas JSON;
- no se cambian endpoints;
- no se implementa Dropbox real;
- no se ejecutan descargadores reales en tests;
- no se cambia frontend ni Firebase.

## Fase 3B — Registro sincro de importaciones procesadas

La Fase 3B usa `import_runs` e `import_results` para auditar importaciones CSV y MSG sin cambiar la API.

Cambios aplicados:

- CSV crea un `import_run` cuando empieza el procesamiento real;
- MSG crea un `import_run` cuando empieza el procesamiento real;
- cada candidato procesado genera un `import_result`;
- el run se cierra como `completed` con conteos de nuevas, actualizadas, omitidas y errores de expediente;
- se guarda hash de entrada, usuario, fuente y fingerprint de candidato;
- se amplian tests funcionales de importacion para validar el registro CSV.

Fuera de esta fase:

- no se cambian respuestas JSON;
- no se cambian endpoints;
- no se registran validaciones previas de multipart, extension o tamano;
- no se implementa PLACE real;
- no se automatizan importaciones;
- no se cambia frontend ni Firebase.

## Fase 3C — Extraccion de auditoria interna

La Fase 3C reduce acoplamiento de `app.py` moviendo helpers de auditoria a un modulo pequeno.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/audit_records.py`;
- se mueven helpers de `import_runs`, `import_results` y `download_jobs`;
- `app.py` conserva las mismas llamadas desde los flujos actuales;
- se anaden tests directos del modulo nuevo;
- se mantienen tests funcionales de importacion y descarga.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambia SQLite;
- no se anaden migraciones;
- no se cambia frontend ni Firebase.

## Fase 3D — Extraccion de parsing multipart

La Fase 3D separa el parseo de ficheros multipart usados por importaciones CSV y MSG.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/multipart_uploads.py`;
- se mueve la extraccion de nombre de fichero y contenido multipart;
- se reutilizan las validaciones existentes de extension y tamano;
- `app.py` mantiene los mismos endpoints y nombres de campo;
- se anaden tests directos de multipart.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambian limites de subida;
- no se toca SQLite;
- no se cambia frontend ni Firebase.

## Fase 3E — Extraccion de rutas de almacenamiento local

La Fase 3E separa helpers de rutas locales/Dropbox sin implementar Dropbox real.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/storage_paths.py`;
- se mueven normalizacion de rutas relativas y deteccion de rutas internas;
- se mueven reglas de carpeta Dropbox por defecto;
- se mueve escritura de `HTTP.url` y seleccion de raiz local;
- `app.py` mantiene envoltorios para `DOWNLOAD_ROOT` y Dropbox local detectado;
- se anaden tests directos de rutas.

Fuera de esta fase:

- no se cambia `api_download_licitacion()`;
- no se cambian respuestas JSON;
- no se implementa Dropbox API;
- no se cambia SQLite;
- no se cambia frontend ni Firebase.

## Fase 3F — Extraccion de criptografía de sesión

La Fase 3F separa firma de tokens y hashing de contrasenas de `app.py`.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/auth_crypto.py`;
- se mueve firma y lectura de tokens firmados;
- se mueve hashing/verificacion PBKDF2;
- `app.py` mantiene envoltorios para `get_secret()`, `make_token()`, `read_token()` y compatibilidad;
- se anaden tests directos de token, expiracion, tampering y contrasenas.

Fuera de esta fase:

- no se cambian cookies;
- no se cambian sesiones visibles;
- no se cambian endpoints ni respuestas JSON;
- no se cambia SQLite;
- no se cambia frontend ni Firebase.

## Fase 3G — Extraccion de carga de entorno

La Fase 3G separa lectura de `.env` y variables obligatorias de `app.py`.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/environment.py`;
- se mueve `load_env_file()`;
- se mueve `required_env()`;
- `app.py` conserva el mismo momento de carga con `load_env_file(ENV_PATH)`;
- se anaden tests directos de parseo, expansion y variables obligatorias.

Fuera de esta fase:

- no se cambian variables de entorno;
- no se cambian valores por defecto;
- no se cambian endpoints ni respuestas JSON;
- no se cambia SQLite;
- no se cambia frontend ni Firebase.

## Fase 3H — Extraccion de usuarios y configuración

La Fase 3H separa helpers SQLite pequenos de usuarios y settings.

Cambios aplicados:

- se crea `webapp/infonalia_webapp/user_settings.py`;
- se mueve `user_row_to_dict()`;
- se mueve la siembra inicial de usuarios/settings;
- se mueve el upsert de settings;
- `app.py` conserva envoltorios para inyectar configuracion global y timestamp;
- se anaden tests directos de serializacion, siembra y upsert.

Fuera de esta fase:

- no se cambian endpoints;
- no se cambian respuestas JSON;
- no se cambian roles ni usuarios por defecto;
- no se anaden migraciones;
- no se cambia frontend ni Firebase.
