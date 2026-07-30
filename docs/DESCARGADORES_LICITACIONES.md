# Descargadores de licitaciones

La arquitectura interna consolidada y el contrato para el futuro monitor se describen en `docs/ARQUITECTURA_DESCARGADORES.md`.

## Objetivo

Este documento define la arquitectura operativa vigente de los descargadores de licitaciones desde el 13 de julio de 2026. Su finalidad es evitar que vuelvan a mantenerse copias distintas de los scripts y facilitar el diagnóstico de fallos, especialmente en la Plataforma de Serveis de Contractació Pública de Catalunya.

## Fuente única de verdad

Los descargadores mantenidos por la aplicación viven exclusivamente en:

- lanzador central: `herramientas_python/Descargar_Licitacion.py`;
- PLACE: `herramientas_python/Descargar_PLACE.py`;
- Junta de Andalucía: `herramientas_python/Descargar_JuntaAndalucia.py`;
- Comunidad de Madrid: `herramientas_python/Descargar_ComunidadMadrid.py`;
- Euskadi: `herramientas_python/Descargar_Euskadi.py`;
- Catalunya: `herramientas_python/Descargar_Catalunya.py`;
- Navarra: `herramientas_python/Descargar_Navarra.py`;
- Xunta de Galicia: `herramientas_python/Descargar_XuntaGalicia.py`.

No se deben mantener ni corregir copias de descargadores de plataforma bajo Dropbox o dentro de carpetas de licitaciones. Cualquier corrección funcional debe hacerse en `herramientas_python` y cubrirse con tests.

## Flujo unificado

El flujo operativo es:

1. La carpeta de la licitación contiene `HTTP.url` y `Descargar ficheros de la plataforma.bat`.
2. El BAT ejecuta el mismo Python de la app: `.venv/Scripts/python.exe`.
3. El BAT ejecuta el lanzador central `herramientas_python/Descargar_Licitacion.py`.
4. El lanzador lee la URL, normaliza el esquema, detecta la plataforma y delega en el descargador correspondiente.
5. El descargador de plataforma escribe únicamente en la carpeta de la licitación indicada como destino.

La app usa las mismas rutas mediante `LAUNCHER_PATH` en `webapp/infonalia_webapp/app.py`.

## Generación de BAT

`webapp/infonalia_webapp/storage_paths.py` es responsable de generar el BAT mediante `build_download_bat_content()` y `write_http_url()`.

Reglas vigentes:

- el BAT contiene rutas absolutas al Python y al lanzador central de la app;
- ya no busca `Infonalia\Descargar_Licitacion.py` ascendiendo por Dropbox;
- si encuentra un BAT estándar antiguo con esa búsqueda, lo migra automáticamente;
- si el BAT fue modificado manualmente, no lo sobrescribe;
- `macros/CrearCarpetas_corregido.bas` genera el mismo formato unificado;
- la macro usa `LLANGON_SUITE_ROOT` si está definido y, en su defecto, `%USERPROFILE%\Documents\Codex\Llangon-SuiteV2`.

## Compatibilidad con BAT antiguos

Los BAT ya existentes pueden seguir apuntando a:

`%USERPROFILE%\Dropbox\00000 LLANGON\Infonalia\Descargar_Licitacion.py`

Ese archivo ya no es un segundo lanzador funcional. Es un puente de compatibilidad cuya fuente está en:

`scripts/windows/legacy_download_launcher_bridge.py`

El puente ejecuta siempre:

- `%LLANGON_SUITE_ROOT%\.venv\Scripts\python.exe`, o el fallback del repositorio;
- `%LLANGON_SUITE_ROOT%\herramientas_python\Descargar_Licitacion.py`.

Por tanto, incluso un BAT antiguo termina usando los descargadores centrales. El puente no contiene detección de plataformas ni lógica de descarga y no necesita sincronizarse cuando cambia un descargador.

## Preguntas y respuestas de PLACE

`Descargar_PLACE.py` mantiene el punto de entrada general y, al finalizar, delega la revisión autenticada de preguntas y respuestas en `Descargar_Preguntas_PLACE.py`. Ambos son fachadas compatibles: la implementación está separada entre el núcleo común `herramientas_python/descargadores/common` y el adaptador `herramientas_python/descargadores/place`. La arquitectura del renderer DOCX nativo se describe en `docs/ARQUITECTURA_DESCARGADOR_PLACE.md`.

Las credenciales se leen desde la configuración interna de la Suite. No se guardan en el descargador, en el BAT, en los DOCX o RTF ni en el estado documental.

Cada revisión correcta aplica estas reglas:

- si no hay cambios, actualiza la fecha de última revisión correcta y no crea ningún documento;
- si aparece una pregunta o cambia cualquier contenido ya publicado, crea únicamente un DOCX acumulativo nuevo y no modifica los documentos anteriores;
- la numeración de cada pregunta se conserva aunque PLACE reordene la tabla;
- el documento presenta una única lista ordenada por la fecha oficial de PLACE, de más reciente a más antigua, sin bloques de revisión;
- las modificaciones conservan y muestran las versiones completas, de la vigente a la inicial;
- una pregunta que deja de aparecer se conserva con aviso y solo se marca tras completar con éxito todo el snapshot;
- una respuesta que queda vacía conserva la versión anterior y muestra su estado actual;
- las reapariciones recuperan el mismo identificador y número y mantienen el historial de publicación;
- el texto oficial se conserva literalmente para el documento y solo se normaliza en claves técnicas de comparación.

La memoria técnica se guarda en el subdirectorio oculto `.llangon-place` de la propia licitación. El esquema 2 conserva versiones completas, estado de publicación, retiradas, reapariciones, último snapshot completo y resultado de consulta. El JSON no se coloca junto a los documentos visibles del cliente y ningún documento visible se usa como fuente principal de deduplicación. Por ello, borrar manualmente un DOCX o RTF no hace que las preguntas se vuelvan a incorporar en la revisión siguiente. La escritura usa temporales binarios, validación del paquete DOCX y un diario de transacción recuperable para mantener coherentes el documento y el estado.

Los estados del esquema anterior se migran automáticamente sin cambiar números, fechas oficiales ni versiones. Antes de sustituir el estado real se crea `questions_state.pre_schema_2.json` dentro del mismo directorio técnico. La migración es idempotente y los DOCX o RTF anteriores se conservan sin cambios. El renderer RTF sigue disponible para compatibilidad histórica, pero no se llama desde el flujo operativo.

La regeneración excepcional desde un estado v2 se ejecuta de forma explícita con `Descargar_Preguntas_PLACE.py --destino <carpeta> --regenerar-docx-desde-estado`. Esta operación no consulta la plataforma, no usa credenciales y no modifica el estado; no forma parte del BAT ni debe confundirse con una revisión que haya detectado novedades.

## Funcionamiento específico de Catalunya

### Formatos de ficha admitidos

El descargador admite fichas como:

```text
https://contractaciopublica.cat/ca/detall-publicacio/{expedient_id}/{publicacio_id}
https://contractaciopublica.cat/ca/detall-publicacio/{publicacio_id}
```

También acepta los idiomas `ca`, `es`, `en` y `oc`.

### Extracción principal mediante API

La web de Catalunya es una aplicación Angular. El HTML inicial no contiene necesariamente enlaces `<a>` a los documentos. El método principal no debe esperar al DOM de Chrome: consulta el JSON público que usa la propia web.

Para fichas con expediente y publicación:

```text
/portal-api/detall-publicacio-expedient/{expedient_id}/{publicacio_id}
```

Para fichas con un solo identificador:

```text
/portal-api/detall-publicacio-expedient/{publicacio_id}
```

Los documentos actuales se construyen como:

```text
/portal-api/descarrega-document/{document_id}/{hash}
```

Las publicaciones antiguas conservan:

```text
/portal-api/descarrega-document-antic/{publicacio_id}/{hash}
```

`extraer_documentos_de_api()` recorre el JSON, acepta solo documentos de fichero,
elimina referencias repetidas dentro de una misma publicación y conserva título
y fecha cuando están disponibles.

La revisión documental no queda anclada a la publicación incluida en `HTTP.url`.
Desde cualquier ficha válida recorre `navegacioEsmenes`, `navegacioFases` y
`navegacioCpp` hasta visitar todas las publicaciones relacionadas del expediente.
Cada publicación se materializa de forma independiente bajo:

```text
{carpeta de la licitación}/{fecha} - {tipo de publicación} - {publicacio_id}/
```

Todos sus enlaces se consultan y todos sus ficheros se guardan dentro de esa
carpeta, aunque repitan título, hash o contenido de otra publicación. No existe
deduplicación entre publicaciones: una corrección, enmienda o nueva fase es una
novedad humana revisable y el monitor informa expresamente de la carpeta creada.
La comparación exacta de bytes solo evita volver a escribir el mismo fichero en
revisiones posteriores de esa misma carpeta. Si no puede consultarse alguna
publicación relacionada, el inventario documental se declara parcial.

### Orden de fallback

El orden correcto es:

1. API JSON de detalle;
2. enlaces presentes en el HTML inicial;
3. Chrome o Edge headless mediante CDP;
4. error controlado si no aparece ningún documento.

Chrome es únicamente un respaldo. En una ficha actual válida con documentos, el resultado normal debe pasar de `Accediendo a Contractacio Publica Catalunya` a `Documentos encontrados: N` sin esperar JavaScript.

### Preguntas y respuestas de Catalunya

`Descargar_Catalunya.py` se conserva como fachada compatible. La implementación específica vive en `herramientas_python/descargadores/catalunya` y reutiliza el motor común de preguntas, el modelo documental neutral, el renderer DOCX y la escritura segura de PLACE.

La consulta de preguntas es pública y solo usa peticiones `GET`:

```text
/portal-api/informacio-basica/{expedient_id}
/portal-api/respostes/{expedient_id}?page={pagina}&pageSize={tamano}
/portal-api/detall-avis/resposta/{publicacion_respuesta_id}
```

No se llama al formulario `/portal-api/preguntes/enviar`, no se resuelve el reCAPTCHA y no se utilizan credenciales. Los expedientes de acceso exclusivo producen un error de acceso estructurado y no modifican el último estado válido.

Cada respuesta se normaliza a `PlatformQuestion`. El identificador estable es la primera publicación presente en `navegacioEsmenes`; una corrección posterior conserva el mismo número y crea una nueva versión. Catalunya solo publica la fecha de la respuesta. Se conserva el instante ISO de la API y el DOCX lo utiliza como fecha visible neutral del encabezado (`Pregunta N del DD-MM-AAAA a las HH:MM`) sin copiarla a `asked_at` ni duplicarla bajo la respuesta.

La paginación se considera completa únicamente si coinciden páginas, totales, tamaño, identificadores únicos y una segunda lectura de la primera página. Cualquier incoherencia bloquea retiradas y deja intacto el estado anterior.

El estado independiente se guarda en `.llangon-catalunya/questions_state.json`. Los DOCX visibles no son la fuente de identidad, por lo que su borrado manual no reinicia la numeración. La regeneración explícita se ejecuta con:

```text
Descargar_Catalunya.py --destino <carpeta> --regenerar-docx-desde-estado
```

Los adjuntos publicados dentro de una respuesta se guardan mediante escritura atómica y comparación de huella bajo `Adjuntos de preguntas y respuestas`. El DOCX conserva además el enlace oficial. Tanto el DOCX acumulativo como esta subcarpeta quedan excluidos de la selección automática y manual para IA.

La fachada mantiene los códigos de salida históricos y añade una línea `RESULTADO_ESTRUCTURADO=<json>` para la Suite y el futuro monitor.

## Funcionamiento específico de Navarra

El descargador acepta tanto fichas del Portal de Contratación de Navarra como enlaces directos de PLENA:

```text
https://hacienda.navarra.es/sicpportal/mtoAnunciosModalidad.aspx?cod={codigo_anuncio}
https://licitacionelectronica.navarra.es/licitador/licitadores/detalle/{codigo_anuncio}/s
```

El flujo tiene dos fases dentro de un único descargador:

1. extrae del HTML antiguo los enlaces `mtoGeneraDocumento.aspx?DOA=...&DOL=...`;
2. consulta los endpoints públicos de PLENA para obtener el expediente y la documentación publicada por la entidad.

PLENA devuelve también los pliegos del portal antiguo. El descargador los identifica por `DOA` y `DOL` y evita descargarlos dos veces. Los documentos adicionales se consultan mediante `getDocumentosAnonymous` y se descargan con `downloadFileAllowAnonymous`.

Las preguntas y aclaraciones no forman parte de este descargador. Su endpoint no se consulta y su tratamiento queda reservado para una futura función específica de la suite.

## Funcionamiento específico de Xunta de Galicia

El descargador admite fichas públicas con identificador numérico:

```text
https://www.contratosdegalicia.gal/licitacion?N={id_publicacion}
```

La ficha HTML contiene los datos del procedimiento y los documentos de inicio, pliegos, preguntas y respuestas en PDF, mesas, resolución, formalización, ejecución y anexos. Cada fila publica una llamada JavaScript que rellena `POST /descargaG`; el adaptador la convierte en una identidad estable con los campos del formulario ordenados y elimina el enlace duplicado de título/formato.

La descarga real está protegida por reCAPTCHA v3. Chrome o Edge estándar se abre con un perfil temporal y una ventana fuera de pantalla, espera a que `grecaptcha.execute` esté disponible y pulsa el enlace oficial para que la propia página solicite el token. No se usa el modo headless porque la plataforma devuelve deliberadamente una página vacía a su `User-Agent`. El descargador no obtiene tokens por otra vía ni intenta resolver un desafío interactivo. Si la plataforma redirige a «Non son un robot», devuelve `partial` cuando conserva artefactos válidos o `failed` cuando no dispone de una respuesta utilizable.

La espera de descarga filtra por la extensión publicada en el inventario. Esto evita confundir archivos auxiliares efímeros de Chrome, como `downloads.htm`, con el documento de contratación.

El estado oculto `.llangon-xunta/documents_state.json` guarda identidad, metadatos, ruta local y SHA-256. Una revisión reutiliza archivos verificados y abre el navegador solo para documentos nuevos, modificados o ausentes localmente. Las colisiones de contenido conservan ambas versiones mediante sufijo de hash; las retiradas solo se confirman tras un inventario completo y nunca borran el archivo local anterior.

El HTML es la fuente de verdad del inventario. El RSS del expediente puede ayudar al diagnóstico, pero no decide completitud porque varias entradas comparten GUID. Las preguntas publicadas como PDF son documentos ordinarios y la plataforma declara `questions_and_answers=False`.

## Resultado común y plataformas documentales

Las siete fachadas operativas delegan en coordinadores registrados en `herramientas_python/descargadores/registry.py`. Navarra, Euskadi, Comunidad de Madrid, Junta de Andalucía y Xunta de Galicia declaran capacidad documental y no dependen del motor de preguntas. PLACE y Catalunya adaptan su `SyncResult` validado a `DownloadRunResult` sin cambiar sus estados ni sus fachadas históricas.

El futuro monitor debe consumir `run_downloader()` y no analizar la salida de consola de los scripts.

## Incidente de referencia de julio de 2026

Ficha usada para verificar la corrección:

```text
https://contractaciopublica.cat/ca/detall-publicacio/7c0d79ac-3c43-432a-9b37-896fb0c436ec/300822730
```

Resultado comprobado en lectura:

- el endpoint de detalle responde `200 application/json`;
- contiene 8 documentos;
- los documentos incluyen PDF, DOCX, XLSX y ZIP;
- una petición `HEAD` al formato actual de descarga responde `200`;
- no fue necesario descargar archivos para validar el extractor.

La primera causa observada fue que el lanzador del repositorio no contemplaba Catalunya. Tras corregirlo, persistió el fallo manual porque los BAT antiguos seguían resolviendo una copia de junio de 2026 bajo Dropbox. Esa copia no contenía la extracción API y agotaba el timeout de Chrome. El puente de compatibilidad elimina esa segunda fuente de verdad.

## Diagnóstico rápido

### Síntoma: `No se reconoce la plataforma`

Revisar `detectar_plataforma()` en `herramientas_python/Descargar_Licitacion.py` y ejecutar:

```powershell
.\.venv\Scripts\python.exe -m pytest -q webapp\infonalia_webapp\tests\test_download_launcher.py
```

### Síntoma: espera JavaScript durante aproximadamente 60 segundos

Para una ficha actual de Catalunya con documentos, este síntoma indica una de estas situaciones:

- se está ejecutando una copia antigua de `Descargar_Catalunya.py`;
- el BAT no está entrando en el lanzador central;
- la API de detalle ha cambiado o está temporalmente inaccesible;
- la URL no coincide con los formatos admitidos.

Comprobar primero que el BAT contiene `PYTHON` y `SCRIPT` apuntando al repositorio. Si es un BAT antiguo, comprobar que el puente instalado coincide con `scripts/windows/legacy_download_launcher_bridge.py`.

Después ejecutar las pruebas sin red ni descargas reales:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  webapp\infonalia_webapp\tests\test_catalunya_downloader.py `
  webapp\infonalia_webapp\tests\test_download_launcher.py `
  webapp\infonalia_webapp\tests\test_legacy_download_launcher_bridge.py
```

### Síntoma: encuentra documentos pero falla cada descarga

Revisar, en este orden:

1. código HTTP y `Content-Type` del enlace;
2. elección entre `descarrega-document` y `descarrega-document-antic`;
3. `Referer` de la ficha;
4. nombre y extensión derivados de contenido y cabeceras;
5. permisos de escritura de la carpeta destino.

Usar `HEAD` o mocks antes de una descarga real. No ejecutar lotes reales durante un diagnóstico automático.

## Tests que protegen el flujo

- `test_catalunya_downloader.py`: URL de API, documentos actuales/antiguos, paginación de preguntas, esmenas, adjuntos, estado independiente, DOCX, regeneración y snapshots incompletos;
- `test_download_launcher.py`: detección y delegación de todas las plataformas, incluida Xunta de Galicia;
- `test_navarra_downloader.py`: perfiles PCN y PLENA, documentos adicionales y ausencia de consultas de preguntas;
- `test_xunta_galicia_downloader.py`: HTML, metadatos, funciones POST, estado, versiones, retiradas, reCAPTCHA y categorías IA gallegas;
- `test_legacy_download_launcher_bridge.py`: resolución del Python y lanzador centrales;
- `test_storage_paths.py`: contenido del BAT y migración del formato antiguo;
- `test_download_endpoint.py`: integración del BAT generado por la app;
- `test_url_helpers.py`: nombre de plataforma en la app.

Validación completa recomendada:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

## Reglas de mantenimiento

- No copiar descargadores de plataforma a Dropbox para solucionar una incidencia.
- No introducir detección de plataformas en el BAT ni en el puente.
- No duplicar lógica entre `url_helpers.py` y el lanzador sin tests de coherencia.
- Mantener la API como vía principal de Catalunya y Chrome como fallback.
- No probar cambios descargando documentos reales salvo autorización expresa.
- Si cambia la ubicación del repositorio, definir `LLANGON_SUITE_ROOT` y regenerar los BAT estándar.
- Si cambia la estructura pública de Catalunya, actualizar fixtures y pruebas antes de tocar la lógica operativa.

## Archivos relacionados

- `herramientas_python/Descargar_Licitacion.py`
- `herramientas_python/Descargar_Catalunya.py`
- `herramientas_python/Descargar_Navarra.py`
- `herramientas_python/Descargar_XuntaGalicia.py`
- `scripts/windows/legacy_download_launcher_bridge.py`
- `webapp/infonalia_webapp/storage_paths.py`
- `webapp/infonalia_webapp/app.py`
- `macros/CrearCarpetas_corregido.bas`
