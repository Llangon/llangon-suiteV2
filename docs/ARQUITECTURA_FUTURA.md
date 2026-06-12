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
