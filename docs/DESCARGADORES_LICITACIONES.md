# Descargadores de licitaciones

## Objetivo

Este documento define la arquitectura operativa vigente de los descargadores de licitaciones desde el 13 de julio de 2026. Su finalidad es evitar que vuelvan a mantenerse copias distintas de los scripts y facilitar el diagnóstico de fallos, especialmente en la Plataforma de Serveis de Contractació Pública de Catalunya.

## Fuente única de verdad

Los descargadores mantenidos por la aplicación viven exclusivamente en:

- lanzador central: `herramientas_python/Descargar_Licitacion.py`;
- PLACE: `herramientas_python/Descargar_PLACE.py`;
- Junta de Andalucía: `herramientas_python/Descargar_JuntaAndalucia.py`;
- Comunidad de Madrid: `herramientas_python/Descargar_ComunidadMadrid.py`;
- Euskadi: `herramientas_python/Descargar_Euskadi.py`;
- Catalunya: `herramientas_python/Descargar_Catalunya.py`.

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

`extraer_documentos_de_api()` recorre el JSON, acepta solo documentos de fichero, elimina duplicados y conserva título y fecha cuando están disponibles.

### Orden de fallback

El orden correcto es:

1. API JSON de detalle;
2. enlaces presentes en el HTML inicial;
3. Chrome o Edge headless mediante CDP;
4. error controlado si no aparece ningún documento.

Chrome es únicamente un respaldo. En una ficha actual válida con documentos, el resultado normal debe pasar de `Accediendo a Contractacio Publica Catalunya` a `Documentos encontrados: N` sin esperar JavaScript.

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

- `test_catalunya_downloader.py`: URL de API, documentos actuales y antiguos;
- `test_download_launcher.py`: detección y delegación a Catalunya;
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
- `scripts/windows/legacy_download_launcher_bridge.py`
- `webapp/infonalia_webapp/storage_paths.py`
- `webapp/infonalia_webapp/app.py`
- `macros/CrearCarpetas_corregido.bas`

