# Arquitectura de descargadores de Llangon Suite V2

## Alcance real

El repositorio mantiene siete plataformas operativas. PLACE y Catalunya incluyen preguntas y respuestas; Navarra, Euskadi, Comunidad de Madrid, Junta de Andalucía y Xunta de Galicia son exclusivamente documentales.

| Plataforma | Fachada CLI compatible | Coordinador interno | Preguntas | Estado técnico |
|---|---|---|---|---|
| PLACE | `herramientas_python/Descargar_PLACE.py` | `descargadores.place.downloader.run_place` | Sí | `.llangon-place/questions_state.json`, esquema 2 |
| Catalunya | `herramientas_python/Descargar_Catalunya.py` | `descargadores.catalunya.downloader.run_catalunya` | Sí | `.llangon-catalunya/questions_state.json`, esquema 2 |
| Navarra | `herramientas_python/Descargar_Navarra.py` | `descargadores.navarra.downloader.run_navarra` | No | No aplica |
| Euskadi | `herramientas_python/Descargar_Euskadi.py` | `descargadores.euskadi.downloader.run_euskadi` | No | No aplica |
| Comunidad de Madrid | `herramientas_python/Descargar_ComunidadMadrid.py` | `descargadores.madrid.downloader.run_madrid` | No | No aplica |
| Junta de Andalucía | `herramientas_python/Descargar_JuntaAndalucia.py` | `descargadores.junta_andalucia.downloader.run_junta_andalucia` | No | No aplica |
| Xunta de Galicia | `herramientas_python/Descargar_XuntaGalicia.py` | `descargadores.xunta_galicia.downloader.run_xunta_galicia` | No | `.llangon-xunta/documents_state.json`, esquema 1 |

Las fachadas conservan sus nombres, argumentos, ejecución desde BAT y códigos de salida. La API interna no obliga a los consumidores históricos a cambiar.

## Flujo

```text
Suite / download_worker / futuro monitor
                 |
                 v
       Descargar_Licitacion.py
                 |
                 v
       fachada CLI compatible
                 |
                 v
      coordinador de plataforma
        /         |          \
    acceso    extracción   documentos
                 |
                 v
        DownloadRunResult
```

Los BAT y `download_jobs` siguen usando `Descargar_Licitacion.py` mediante subprocess. El futuro monitor debe usar la API Python del registro para obtener el contrato común directamente, sin analizar texto de consola.

## Núcleo común

### Resultado global

`herramientas_python.descargadores.common.run_result` define:

- `PlatformCapabilities`: capacidades reales de la plataforma;
- `DownloadArtifact`: archivo observado, creado o reutilizado;
- `DownloadRunResult`: resultado completo y serializable;
- `result_from_question_sync()`: adaptador del motor de preguntas existente.

Los estados generales son `success`, `success_with_warnings`, `partial` y `failed`. `no_changes` no es un error ni un quinto estado: es una ejecución correcta con `changes_detected=False`.

El contrato contiene plataforma, expediente, origen, inicio y fin, datos generales, fechas relevantes, recuentos documentales, artefactos, archivos creados y reutilizados, estado técnico, avisos, incidencias recuperables, error principal y capacidades. PLACE y Catalunya añaden el resultado literal de preguntas en `questions`; las otras cinco plataformas mantienen `questions=None`.

### Documentos

`download_models.py` concentra detección de extensión, MIME y nombres derivados de contenido. `safe_files.py` proporciona validación de rutas, hash SHA-256, escritura temporal, publicación atómica, deduplicación y colisiones seguras. Los errores viven en `common/errors.py` y no dependen de los modelos de preguntas.

`common/http.py` centraliza únicamente la configuración básica de las sesiones HTTP públicas. Los endpoints, la navegación y la interpretación de respuestas continúan siendo responsabilidad de cada adaptador.

Las reglas particulares de selección y nombres siguen en cada plataforma.

### Preguntas y respuestas

PLACE y Catalunya reutilizan `PlatformQuestion`, adjuntos, snapshots completos, identidad, numeración, comparación, versiones, retiradas, restauraciones, estado esquema 2, `QuestionDocument`, DOCX común, RTF histórico y publicación transaccional.

Los adaptadores remotos convierten sus datos al modelo común. El núcleo no contiene URL, selector, JSF, ViewState ni JSON propios de una plataforma.

## Módulos específicos

### PLACE

- `place/access.py`: lectura local y de solo lectura de la configuración de credenciales;
- `place/session.py`: sesión autenticada, JSF y ViewState de preguntas;
- `place/documents.py`: extracción y descarga documental;
- `place/questions.py`: snapshot específico;
- `place/downloader.py`: coordinación global y adaptación al resultado común;
- `Descargar_Preguntas_PLACE.py`: fachada histórica y regeneración desde estado.

La ausencia total de credenciales mantiene las preguntas como capacidad opcional no configurada y no invalida una descarga documental correcta.

### Catalunya

- `catalunya/client.py`: acceso público y URL de API;
- `catalunya/documents.py`: documentos JSON/HTML y persistencia;
- `catalunya/browser_fallback.py`: navegación alternativa;
- `catalunya/questions.py`: paginación, esmenas, fechas y adjuntos;
- `catalunya/downloader.py`: coordinación, estado y resultado global.

La fecha del encabezado DOCX usa la regla neutral `asked_at`, después `answered_at`, después fecha oficial de entrada. Catalunya conserva `asked_at` vacío cuando la plataforma no publica esa fecha.

### Navarra

- `navarra/client.py`: PCN, PLENA, endpoints y deduplicación remota;
- `navarra/documents.py`: detección y publicación local;
- `navarra/downloader.py`: coordinación y resultado.

No consulta endpoints de preguntas.

### Euskadi

- `euskadi/client.py`: HTML, expediente y endpoints Dokusi;
- `euskadi/documents.py`: descarga y publicación;
- `euskadi/downloader.py`: coordinación y resultado.

### Comunidad de Madrid

- `madrid/client.py`: HTML, ficha PDF y adjuntos internos;
- `madrid/documents.py`: descarga y publicación;
- `madrid/downloader.py`: coordinación y resultado.

### Junta de Andalucía

- `junta_andalucia/browser.py`: CDP, selectores y navegación Chrome/Edge;
- `junta_andalucia/downloader.py`: coordinación y resultado.

### Xunta de Galicia

- `xunta_galicia/client.py`: valida la ficha, extrae datos generales y construye un inventario completo a partir del HTML;
- `xunta_galicia/browser.py`: ejecuta fuera de pantalla en Chrome/Edge estándar las llamadas protegidas por reCAPTCHA v3, espera la API oficial y no intenta eludir un reto interactivo;
- `xunta_galicia/documents.py`: valida contenido, extensión y tamaño y publica sin sobrescribir versiones anteriores;
- `xunta_galicia/state.py`: conserva identidad remota, ruta y SHA-256 en `.llangon-xunta`;
- `xunta_galicia/downloader.py`: reutiliza el estado válido, descarga únicamente altas o cambios y devuelve el contrato común.

La identidad documental es la representación canónica de `POST /descargaG` con sus campos ordenados. El HTML de la ficha es la fuente de verdad; el RSS no confirma completitud porque reutiliza GUID. Una respuesta parcial o un bloqueo de reCAPTCHA conserva la última línea base completa y el monitor registra la incidencia sin convertir ausencias en retiradas.

La descarga por clic se recibe primero en una carpeta temporal aislada, se filtra por la extensión documental esperada y después se publica atómicamente en el destino. El modo headless no se usa en Xunta porque la plataforma lo sustituye por una página señuelo vacía. CDP no se generaliza porque ninguna otra plataforma comparte ese caso real.

## Ejecución compatible

Desde una carpeta con `HTTP.url`:

```powershell
.\.venv\Scripts\python.exe .\herramientas_python\Descargar_Licitacion.py
```

Con URL explícita:

```powershell
.\.venv\Scripts\python.exe .\herramientas_python\Descargar_Licitacion.py <URL>
```

Las fachadas admiten `--destino <CARPETA>`. Junta conserva `--incluir-sellos` y `--sin-sellos`.

Regeneración de preguntas sin red ni cambio de estado:

```powershell
.\.venv\Scripts\python.exe .\herramientas_python\Descargar_Preguntas_PLACE.py --destino <CARPETA> --regenerar-docx-desde-estado
.\.venv\Scripts\python.exe .\herramientas_python\Descargar_Catalunya.py --destino <CARPETA> --regenerar-docx-desde-estado
```

## Interfaz para el futuro monitor

```python
from herramientas_python.descargadores import run_downloader

result = run_downloader(
    platform="CATALUNYA",
    source_url=url,
    destination=carpeta_licitacion,
)
payload = result.to_dict()
```

El monitor puede consultar previamente `get_downloader_spec(platform).capabilities`. No debe importar selectores, sesiones o módulos específicos ni inferir capacidades por el nombre de la plataforma.

El monitor será responsable de planificación, correo y decisiones posteriores. Los descargadores no deciden qué contenido va a IA. Preguntas, respuestas y sus adjuntos permanecen fuera de IA.

## Añadir una plataforma

1. Crear un paquete específico con coordinador y acceso/extracción necesarios.
2. Reutilizar `download_models` y `safe_files` cuando sus reglas encajen.
3. Devolver `DownloadRunResult`.
4. Declarar capacidades reales; no añadir preguntas si no existen.
5. Registrar un `DownloaderSpec` en `descargadores/registry.py`.
6. Añadir detección compatible al lanzador y a `url_helpers.py` con pruebas de coherencia.
7. Crear una fachada CLI estrecha si la operación manual la necesita.
8. Cubrir éxito, repetición, fallo parcial, argumentos y ausencia de red real.

## Deliberadamente fuera de los descargadores

- planificación del monitor y `.enseguimiento`;
- correo, Telegram o IA;
- SQLite como fuente de verdad de preguntas;
- decisiones jurídicas o técnicas sobre contenido;
- interfaz de historial del monitor;
- edición o eliminación del historial publicado.
