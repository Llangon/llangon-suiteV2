# Informe técnico del descargador de licitaciones de la Junta de Andalucía

Fecha del análisis: 24 de julio de 2026  
Proyecto: Llangon-SuiteV2  
Rama de trabajo observada: `codex/monitor-licitaciones-e2e`  
Commit base observado: `d95cca9`  
Estado del repositorio: árbol de trabajo con numerosos cambios previos no consolidados; este informe distingue los cambios relativos al descargador de la Junta y a su integración con el Monitor.

## 1. Resumen ejecutivo

El ciclo 76 del Monitor no falló por un cambio permanente de selectores ni porque las cuatro licitaciones hubieran dejado de existir. La evidencia indica una combinación de:

1. Inestabilidad transitoria real del portal de la Junta:
   - páginas Angular que finalizaban la navegación, pero dejaban vacío tanto `document.body` como `app-root`;
   - un `Page.navigate` que devolvió `net::ERR_TIMED_OUT`;
   - un antecedente inmediato de `ConnectionResetError(10054)` durante la descarga de un documento;
   - recuperación posterior de las mismas fichas sin cambiar sus URL ni sus contenidos.
2. Dos defectos internos reproducibles en nuestra tolerancia a fallos:
   - el Monitor decidía si debía reintentar leyendo palabras del texto del error; no reconocía el nuevo mensaje de “aplicación sin renderizar” ni `ERR_TIMED_OUT`, porque este último contiene un guion bajo;
   - la llamada CDP `Page.navigate` estaba fuera del bloque de los tres reintentos internos, por lo que un timeout de navegación abortaba el descargador en el primer intento.
3. Un defecto adicional de limpieza observado durante la validación:
   - el cierre usaba `shutil.rmtree(..., ignore_errors=True)`, por lo que Windows podía mantener momentáneamente un archivo bloqueado, ocultar el error y dejar un perfil temporal huérfano;
   - un error al cerrar un canal CDP podía interrumpir el resto de la limpieza;
   - un fallo durante el arranque de Chrome ocurría antes de devolver el proceso al coordinador y podía dejar proceso o perfil sin limpiar.
4. Debilidades anteriores ya corregidas durante esta investigación:
   - las URL históricas `pdc_sirec/...detalle-licitacion.jsf` se usaban directamente aunque el portal vigente es `pdc-front-publico/...detalle-licitacion`;
   - faltaban diagnósticos capaces de diferenciar “portal Angular vacío” de “secciones no encontradas”;
   - una interrupción de red durante un documento podía producir un resultado parcial sin reintento suficiente;
   - el lanzador general no trataba de forma fiable `--destino` y la salida UTF-8 del proceso hijo.

La corrección aplicada no pretende declarar que un portal externo nunca volverá a estar caído. Sí elimina los dos fallos internos que hicieron que el ciclo 76 desaprovechase sus reintentos:

- los fallos del navegador de la Junta ahora tienen clases, códigos estables y una marca booleana `retryable`;
- `DownloadRunResult` transporta `error_code` y `retryable`;
- el Monitor consulta primero esa marca estructurada y mantiene el detector textual únicamente como compatibilidad;
- `Page.navigate` y la espera del render están ahora dentro del mismo bucle de tres intentos;
- si esos tres intentos dentro del navegador no bastan, el Monitor puede efectuar otra llamada completa al descargador, que abre un proceso Chrome y un perfil temporal nuevos.
- el cierre de Chrome aísla errores CDP, espera también después de `kill`, reintenta ocho veces la eliminación del perfil y limpia igualmente los fallos de arranque.

Validación real al terminar:

| Expediente web | URL de entrada | Resultado | Documentos |
|---|---|---:|---:|
| `947853` | URL histórica `pdc_sirec` | `success`, código 0 | 31/31 |
| `944739` | URL Angular actual | `success`, código 0 | 17/17 |
| `945359` | URL Angular actual | `success`, código 0 | 13/13 |
| `974574` | URL Angular actual | `success`, código 0 | 16/16 |

Total de la validación fresca: 77 documentos observados, 77 guardados, 0 errores.

Además, una segunda ejecución de `945359` a través del lanzador general —el recorrido funcional que utiliza el `.bat`— detectó la plataforma, normalizó la URL antigua y reutilizó 13/13 archivos, sin redescargarlos y sin informar cambios falsos.

Conclusión: el incidente del ciclo 76 fue activado por una indisponibilidad transitoria externa, pero nuestra clasificación y colocación de los reintentos eran defectuosas. Esa parte interna sí era corregible y ha sido corregida.

## 2. Alcance y restricciones del análisis

Se revisaron:

- el mensaje `.msg` de incidencias del ciclo 76;
- la vista autenticada del Monitor y el detalle de los ciclos 70, 73, 74, 75, 76 y 77;
- el worker del Monitor;
- el orquestador secuencial;
- el registro interno de descargadores;
- el contrato `DownloadRunResult`;
- la fachada histórica y el lanzador general;
- navegación CDP, detección de render Angular, extracción de enlaces y descarga HTTP;
- pruebas unitarias, de integración y ejecuciones reales sobre las cuatro fichas afectadas.

No se modificaron:

- bases SQLite reales;
- expedientes o carpetas operativas reales;
- configuraciones del Monitor;
- correo, Telegram, Dropbox o tareas Windows;
- secretos, tokens o credenciales;
- el portal de la Junta.

Las descargas reales se realizaron en carpetas desechables dentro del repositorio.

No se lanzó un ciclo real nuevo del Monitor porque eso habría escrito en la base operativa y podría haber producido comunicaciones. La integración Monitor-descargador se validó con base SQLite temporal y dependencias simuladas; la descarga real se validó por separado.

Al auditar el temporal de Windows se encontraron 24 perfiles históricos `junta_descargas_chrome_*` sin proceso asociado. El más reciente coincidía con una validación de este análisis y permitió reproducir el defecto de limpieza. Tras corregirlo:

- una ejecución real adicional no aumentó el contador de perfiles: 24 antes y 24 después;
- se retiró exclusivamente el perfil identificable como creado por esta investigación;
- los 23 perfiles anteriores se dejaron intactos porque no puede atribuirse su propiedad con seguridad.

## 3. Evidencia cronológica

### 3.1. Ciclo 73

- Inicio: 24/07/2026 13:00:07.
- Tipo: `automatic_scheduler`.
- Resultado: `completed_with_incidents`.
- Procesadas: 29/29.
- Incidencias: 3.
- Detalle común: `No han aparecido las secciones documentales esperadas.`

Este texto pertenecía al diagnóstico anterior, que no distinguía una aplicación Angular completamente vacía de una alteración estructural de la página.

### 3.2. Ciclo 74

- Inicio: 24/07/2026 13:12:45.
- Tipo: `manual_individual`.
- Resultado: `completed_with_incidents`.
- Procesadas: 1/1.
- Incidencia: `PARTIAL_PLATFORM_RESPONSE`.
- Documento afectado: `Pliego de Cláusula Administrativa.PDF`.
- Error: conexión interrumpida por el host remoto, `ConnectionResetError(10054)`.

Esto demuestra que en ese momento el portal sí llegó a renderizar la ficha y a exponer documentos, pero una transferencia fue interrumpida.

### 3.3. Ciclo 75

- Inicio: 24/07/2026 13:48:24.
- Tipo: `manual_individual`.
- Resultado: `completed`.
- Procesadas: 1/1.
- Incidencias: 0.

Confirma una recuperación temporal sin un cambio estructural permanente.

### 3.4. Ciclo 76

- Inicio: 24/07/2026 14:28:46.
- Tipo: `manual_global`.
- Resultado: `completed_with_incidents`.
- Procesadas: 29/29.
- Novedades: 0.
- Incidencias: 4.
- Informe de correo: 24/07/2026 14:38:09 CEST.
- En las cuatro ejecuciones fallidas se conservó el último estado válido; no se interpretó la ausencia de datos como retirada de documentos.

Detalle:

| Expediente | `idExpediente` | Error final | Reintentos informados por el Monitor |
|---|---:|---|---:|
| `CONTR 2026 0000093394` | `947853` | aplicación Angular sin contenido renderizado | 0 |
| `CONTR 2026 0000095443` | `974574` | aplicación Angular sin contenido renderizado | 0 |
| `CONTR 2025 0000208334` | `945359` | `Chrome no pudo abrir la licitación: net::ERR_TIMED_OUT` | 0 |
| `CONTR 2025 0000695544` | `944739` | aplicación Angular sin contenido renderizado | 1 |

Interpretación correcta de “reintentos”:

- `0` significa una sola llamada del Monitor al descargador.
- Dentro de cada llamada, los fallos ocurridos durante la espera del render podían realizar hasta tres navegaciones en el mismo Chrome.
- Antes de esta corrección, un error producido directamente por `Page.navigate` no entraba en esos tres intentos.
- `1` significa que el Monitor llamó dos veces al descargador, por lo que abrió dos procesos Chrome y dos perfiles temporales independientes.

En `944739`, el error final persistido fue “Angular vacío”, pero el informe solo conserva el último resultado. No existe evidencia suficiente en la interfaz para afirmar cuál fue el error de su primera llamada. Lo único demostrable es que hubo una llamada adicional.

### 3.5. Ciclo 77

- Inicio: 24/07/2026 18:00:28.
- Tipo: `automatic_scheduler`.
- Resultado: `completed`.
- Procesadas: 29/29.
- Novedades: 2.
- Incidencias: 0.

El mismo Monitor procesó posteriormente las 29 licitaciones sin incidencias. Esto descarta como explicación principal:

- un selector roto de forma permanente;
- una URL definitivamente inválida;
- la desaparición permanente de los bloques documentales;
- un error determinista exclusivo de una de las cuatro licitaciones.

## 4. Arquitectura real

### 4.1. Ejecución desde `.bat` o lanzador manual

```text
.bat generado por la Suite
  -> herramientas_python/Descargar_Licitacion.py
     -> detecta plataforma por hostname/URL
     -> normaliza --destino
     -> ejecuta la fachada con el mismo Python
        -> herramientas_python/Descargar_JuntaAndalucia.py
           -> run_junta_andalucia(...)
```

La fachada histórica sigue existiendo por compatibilidad con accesos directos y archivos `.bat`.

### 4.2. Ejecución desde el Monitor

```text
API o scheduler
  -> tender_worker_launcher.py
     -> nuevo proceso Python sin ventana
        -> tender_worker.py
           -> run_tender_monitor_cycle(...)
              -> procesa las licitaciones secuencialmente
                 -> registry.run_downloader(...)
                    -> run_junta_andalucia(...)
```

El Monitor no ejecuta el `.bat` ni la fachada mediante `subprocess`. Invoca directamente el coordinador Python registrado.

El ciclo global es secuencial: el `for licitacion_id in target_ids` procesa una licitación después de otra dentro de un único worker. No hay una tormenta de 29 Chromes simultáneos provocada por el Monitor. Sí hay arranques y cierres consecutivos de procesos Chrome auxiliares.

### 4.3. Flujo interno del descargador de la Junta

```text
URL original
  -> normalización al portal pdc-front-publico
  -> Chrome headless con perfil temporal y puerto CDP libre
  -> creación de página CDP
  -> Page.navigate
  -> espera activa del render Angular
  -> diagnóstico de body, app-root, readyState y URL final
  -> localización de “Documentación complementaria” y “Anuncios publicados”
  -> extracción de enlaces y clasificación por sección
  -> copia de cookies y User-Agent a requests.Session
  -> descarga HTTP directa o, si no hay URL descargable, clic de Chrome
  -> nombre seguro, hash SHA-256, tamaño, sección y estado created/reused/failed
  -> DownloadRunResult
  -> snapshot y comparación del Monitor
```

## 5. Causa raíz técnica

### 5.1. Causa externa desencadenante

El portal de la Junta mostró, dentro de una ventana de pocas horas, tres modos de fallo de red o aplicación:

1. Angular cargado como documento, pero sin contenido en `body` ni en `app-root`.
2. Navegación CDP terminada con `net::ERR_TIMED_OUT`.
3. Conexión HTTP interrumpida por el host remoto durante un documento.

Estos fallos son compatibles con:

- indisponibilidad temporal de uno o varios servicios internos del portal;
- balanceador o proxy que entrega el `index.html`, pero no todos los recursos o llamadas API;
- reinicio o saturación temporal;
- cierre de conexión por el servidor;
- fallo transitorio de red entre el equipo y el portal.

No hay evidencia suficiente para elegir una de esas causas externas con precisión. Para hacerlo serían necesarios eventos de red, respuestas HTTP, errores de consola y tiempos por recurso. El CDP actual no conserva esa telemetría.

### 5.2. Defecto interno 1: clasificación por palabras

El Monitor usaba este principio:

```python
text = str(exc).casefold()
return isinstance(exc, (TimeoutError, ConnectionError)) or any(
    token in text
    for token in (
        "timeout",
        "timed out",
        "temporal",
        "temporarily",
        "connection",
        "503",
        "429",
        "bloqueo",
    )
)
```

Problemas concretos:

- `La aplicación de la Junta no llegó a renderizar contenido` no contiene ninguno de esos tokens.
- `net::ERR_TIMED_OUT` contiene `timed_out`, no `timed out`.
- el descargador transforma la excepción en un `DownloadRunResult.failed`; al llegar al Monitor ya se había perdido el tipo original de la excepción;
- una mejora legítima del texto de diagnóstico modificó accidentalmente la política de reintentos.

Este defecto explica por qué tres resultados del ciclo 76 terminaron con cero reintentos y por qué el timeout tampoco quedó correctamente reconocido por su mensaje.

### 5.3. Defecto interno 2: `Page.navigate` fuera del reintento interno

El bucle de tres intentos envolvía la espera de las secciones, pero no la propia navegación. La secuencia era equivalente a:

```python
for attempt in attempts:
    navegar_a_licitacion(...)
    try:
        esperar_documentacion(...)
    except:
        retry
```

Si `Page.navigate` devolvía `ERR_TIMED_OUT`, la excepción salía inmediatamente del bucle. Por tanto:

- el timeout de `945359` solo intentó una navegación en esa llamada;
- el Monitor recibió un resultado `failed`;
- el clasificador textual tampoco reconoció `ERR_TIMED_OUT`;
- no se abrió un Chrome nuevo.

Era una doble pérdida de resiliencia.

### 5.4. Factores anteriores ya corregidos

#### URL histórica

Las URL `pdc_sirec/...detalle-licitacion.jsf` siguen apareciendo en datos históricos y `.url`, pero el frontend vigente está en:

```text
/apl/pdc-front-publico/perfiles-licitaciones/detalle-licitacion?idExpediente=...
```

Ahora se extrae `idExpediente` y se construye una URL HTTPS canónica.

#### Descarga de documentos

Una desconexión `10054` podía dejar una respuesta parcial. Ahora:

- la sesión HTTP usa `urllib3.Retry`;
- la descarga de cada documento tiene reintentos explícitos;
- un archivo ya existente se reutiliza sin realizar una petición de red;
- se reconocen correctamente ODT y ODS.

#### Diagnóstico insuficiente

El mensaje genérico “no han aparecido las secciones” mezclaba:

- página vacía;
- aplicación sin renderizar;
- navegación errónea;
- contenido real sin las secciones esperadas;
- posible cambio estructural.

Ahora se inspeccionan:

- URL final;
- `document.readyState`;
- longitud de `body.innerText`;
- longitud del HTML de `app-root`;
- muestra de texto;
- cantidad de enlaces;
- presencia normalizada de los títulos de sección.

### 5.5. Defecto interno 3: limpieza silenciosa de perfiles Chrome

El cierre anterior terminaba con:

```python
shutil.rmtree(perfil_temporal, ignore_errors=True)
```

En Windows, Chrome puede haber terminado como proceso principal mientras algún manejador de fichero se libera unas décimas de segundo después. `ignore_errors=True` hacía que:

- el borrado fallase silenciosamente;
- no hubiese retry;
- no quedase aviso;
- se acumulasen perfiles.

Además, `page.close()` y `browser.close()` no estaban aislados. Una excepción de cualquiera podía impedir `terminate`, `kill` y el borrado. Por último, si `abrir_chrome()` fallaba antes de devolver su tupla, el coordinador externo todavía no conocía el proceso ni el perfil.

La corrección:

- captura por separado los errores de cierre CDP;
- intenta `terminate` y espera cinco segundos;
- si falla, hace `kill` y vuelve a esperar;
- reintenta ocho veces el borrado del perfil cada 0,5 segundos;
- informa si finalmente no puede eliminarlo;
- aplica la misma limpieza dentro de `abrir_chrome()` si falla el arranque.

## 6. Cambios aplicados

### 6.1. Contrato común

Archivo:

```text
herramientas_python/descargadores/common/run_result.py
```

Campos añadidos de forma aditiva:

```python
error_code: str = ""
retryable: bool = False
```

Objetivo:

- no depender de la redacción humana del error;
- transportar desde la plataforma hasta el Monitor una decisión explícita;
- mantener compatibilidad con constructores existentes gracias a valores predeterminados;
- conservar `schema_version = 2` al ser una ampliación aditiva en el contrato interno actual.

### 6.2. Errores clasificados de la Junta

Archivo:

```text
herramientas_python/descargadores/junta_andalucia/browser.py
```

Jerarquía añadida:

```text
JuntaBrowserError
  -> JuntaTransientBrowserError
       -> JuntaNavigationTransientError
       -> JuntaEmptyRenderError
       -> JuntaDocumentSectionsTimeout
```

Códigos:

- `JUNTA_BROWSER_ERROR`
- `JUNTA_NAVIGATION_TRANSIENT`
- `JUNTA_EMPTY_RENDER`
- `JUNTA_DOCUMENT_SECTIONS_TIMEOUT`
- fallback: `JUNTA_DOWNLOAD_FAILED`

La lista de errores CDP transitorios incluye:

- `ERR_ABORTED`
- `ERR_CONNECTION_ABORTED`
- `ERR_CONNECTION_CLOSED`
- `ERR_CONNECTION_RESET`
- `ERR_EMPTY_RESPONSE`
- `ERR_HTTP2_PROTOCOL_ERROR`
- `ERR_INTERNET_DISCONNECTED`
- `ERR_NAME_NOT_RESOLVED`
- `ERR_NETWORK_CHANGED`
- `ERR_QUIC_PROTOCOL_ERROR`
- `ERR_TEMPORARILY_THROTTLED`
- `ERR_TIMED_OUT`

Un error claramente permanente como `ERR_INVALID_URL` no se marca como reintentable.

### 6.3. Reintento de navegación correctamente delimitado

Archivo:

```text
herramientas_python/descargadores/junta_andalucia/downloader.py
```

Ahora el `try` incluye tanto:

- `Page.navigate`;
- la espera del render y de las secciones.

Cada llamada completa al descargador permite hasta tres intentos de navegación dentro del mismo navegador. Si todos fallan con un error clasificado como transitorio, el resultado final contiene:

```json
{
  "status": "failed",
  "error_code": "JUNTA_...",
  "retryable": true
}
```

### 6.4. Reintento del Monitor con navegador nuevo

Archivo:

```text
webapp/infonalia_webapp/monitor/tender_orchestrator.py
```

La decisión actual es:

```python
if result.retryable:
    return True
```

Si no existe la marca, se conserva el clasificador textual anterior para otros descargadores todavía no migrados.

La configuración `download_retries`:

- valor por defecto: 2 intentos totales;
- mínimo: 1;
- máximo: 5.

Cada llamada nueva a `run_junta_andalucia` crea:

- un proceso Chrome nuevo;
- un perfil de usuario temporal nuevo;
- un puerto CDP nuevo;
- una página nueva;
- una sesión HTTP nueva.

Esto es distinto de recargar la misma página.

### 6.5. Robustez del lanzador manual

Archivo:

```text
herramientas_python/Descargar_Licitacion.py
```

Se corrigió:

- interpretación de `--destino valor`;
- interpretación de `--destino=valor`;
- creación de la carpeta destino;
- ejecución del proceso hijo con UTF-8;
- propagación de salida;
- bloqueo compartido de destino para evitar dos descargas simultáneas sobre la misma carpeta.

### 6.6. Descarga HTTP y formatos

Archivos:

```text
herramientas_python/descargadores/junta_andalucia/browser.py
herramientas_python/descargadores/junta_andalucia/documents.py
```

Se añadió:

- política `urllib3.Retry` para GET;
- reintento explícito de `requests.RequestException`;
- respeto a `Retry-After`;
- reutilización local antes de consultar la red;
- soporte de extensión ODT/ODS por MIME y contenido;
- metadatos de tamaño y sección en cada artefacto.

### 6.7. Cierre robusto de Chrome

Archivo:

```text
herramientas_python/descargadores/junta_andalucia/browser.py
```

Funciones separadas:

```text
terminar_proceso_chrome(...)
eliminar_perfil_temporal(...)
cerrar_chrome(...)
```

La limpieza deja de ser silenciosa y se ejecuta también cuando el arranque de CDP falla.

## 7. Semántica de seguridad e idempotencia

### 7.1. Estado anterior preservado

Cuando una consulta falla:

- el resultado se marca `failed`;
- el Monitor no sustituye la línea base válida;
- no interpreta una lista vacía como retirada de todos los documentos;
- registra `DOWNLOADER_FAILED`;
- conserva el estado anterior.

Cuando solo fallan algunos documentos:

- el resultado se marca `partial`;
- el Monitor registra `PARTIAL_PLATFORM_RESPONSE`;
- fusiona únicamente bloques válidos;
- no convierte ausencias dudosas en eliminaciones.

### 7.2. Segunda ejecución

Para cada documento ya existente:

- se conserva el archivo;
- se calcula o reutiliza su información;
- el artefacto se marca `reused`;
- `documents_new` permanece en 0;
- `changes_detected` permanece en `false`.

La prueba real de `945359` confirmó 13 reutilizados y 0 nuevos.

### 7.3. Limpieza

Cada ejecución cierra:

- canal CDP de la página;
- canal CDP del navegador;
- proceso Chrome;
- perfil temporal;
- directorio temporal de descargas por clic.

Si `terminate` no finaliza el proceso en cinco segundos, intenta `kill` y espera de nuevo. La eliminación del perfil se reintenta ocho veces. Una prueba real posterior dejó:

```text
perfiles antes: 24
perfiles después: 24
procesos Chrome auxiliares activos: 0
```

El perfil huérfano atribuible a esta investigación se eliminó después de la comprobación.

## 8. Validación realizada

### 8.1. Entorno

```text
Windows
Python 3.13.5, 64 bits
Chrome 150.0.7871.129
requests 2.34.2
urllib3 2.7.0
websocket-client 1.9.0
```

### 8.2. Pruebas dirigidas finales

```text
75 passed in 26.80s
```

Cobertura relevante:

- normalización URL histórica;
- conservación URL actual;
- `ERR_CONNECTION_RESET` clasificado transitorio;
- `ERR_TIMED_OUT` clasificado transitorio;
- `ERR_INVALID_URL` no reintentable;
- contrato con `error_code` y `retryable`;
- propagación de fallo Angular desde Junta hasta `DownloadRunResult`;
- reintento de espera incompleta;
- reintento de `Page.navigate`;
- nuevo intento del Monitor sin depender del texto;
- descarga HTTP después de reset;
- reutilización sin petición;
- ODT;
- cierre del navegador;
- retry de borrado ante bloqueo temporal de Windows;
- limpieza aunque fallen los canales CDP;
- limpieza si Chrome falla durante el arranque;
- resultados `success`, `partial` y `failed`;
- preservación de línea base del Monitor.

### 8.3. Suite completa

Antes de la última ampliación parametrizada de una prueba:

```text
1349 passed
1 failed
```

Único fallo:

```text
test_private_search_boxes_submit_only_on_enter
```

Causa:

```text
index.html no contiene la versión antigua esperada:
/static/app.js?v=20260721-global-tender-filter
```

Es una aserción de versión de recurso frontend, ya existente y ajena al descargador de la Junta. No se modificó.

Después de la última prueba específica añadida:

```text
11 passed
```

Y la batería dirigida completa actual:

```text
72 passed
```

### 8.4. Comprobaciones sintácticas

Correctas:

- `py_compile` de los módulos modificados;
- `node --check webapp/infonalia_webapp/static/app.js`;
- `node --check webapp/infonalia_webapp/static/login.js`;
- `node --check firebase/public_firebase/static/public.js`.

### 8.5. Pruebas reales contra la Junta

#### `947853`

- entrada histórica `http://.../pdc_sirec/...detalle-licitacion.jsf`;
- normalización a HTTPS y `pdc-front-publico`;
- 31 enlaces;
- 31 archivos creados;
- 0 omitidos;
- 0 errores;
- `status=success`;
- código de salida 0.

#### `944739`

- 17 enlaces;
- incluye PDF y ODT;
- 17 archivos creados;
- 0 omitidos;
- 0 errores;
- `status=success`;
- código de salida 0.

#### `945359`

- 13 enlaces;
- incluye un PDF de 58.742.592 bytes;
- 13 archivos creados;
- 0 omitidos;
- 0 errores;
- `status=success`;
- código de salida 0.

Segunda ejecución mediante el lanzador general:

- plataforma detectada correctamente;
- URL histórica normalizada;
- 0 creados;
- 13 reutilizados;
- 0 errores;
- `changes_detected=false`;
- código de salida 0.

#### `974574`

- 16 enlaces;
- 16 archivos creados;
- 0 omitidos;
- 0 errores;
- `status=success`;
- código de salida 0.

#### Validación real adicional de limpieza

Se repitió `944739` después de reforzar el cierre:

- 17/17 documentos;
- `status=success`;
- código 0;
- 0 procesos Chrome auxiliares;
- el número de perfiles temporales no aumentó.

## 9. Qué queda demostrado y qué no

### Demostrado

- Las cuatro fichas existen y hoy son descargables.
- Los selectores actuales localizan sus bloques y enlaces.
- La URL histórica puede transformarse de forma determinista.
- El ciclo 76 sufrió fallos transitorios de red/render.
- El Monitor desaprovechó reintentos por depender del texto.
- `Page.navigate` estaba fuera del bucle interno.
- Ambos defectos internos están corregidos y cubiertos por pruebas.
- Los fallos siguen preservando el último estado válido.
- Las segundas ejecuciones son idempotentes.

### No demostrado

- La causa exacta dentro de la infraestructura de la Junta.
- Si el fallo vacío se originó en el `index.html`, JavaScript, API REST, balanceador, DNS o proxy.
- Que dos intentos inmediatos sean suficientes para cualquier indisponibilidad.
- Que nunca aparezca un CAPTCHA, WAF o cambio estructural futuro.
- Que la API interna usada por Angular sea estable o pública.
- Que migrar a Playwright sea necesariamente mejor sin una prueba comparativa.

## 10. Riesgos residuales

### 10.1. Reintentos demasiado próximos

El Monitor espera como máximo cinco segundos entre llamadas. Una caída de varios minutos no se resolverá con un intento inmediato.

Recomendación: reintento diferido por plataforma, no solo inmediato por licitación.

### 10.2. Repetición correlacionada

Tres navegaciones en el mismo proceso Chrome comparten:

- proceso de red;
- perfil;
- caché y estado de la aplicación;
- ventana temporal de indisponibilidad.

El segundo nivel ya abre Chrome nuevo, pero también ocurre pocos segundos después.

### 10.3. Falta de telemetría de red

El cliente CDP descarta eventos que no corresponden al `id` de la llamada que está esperando. No se guardan de forma estructurada:

- `Network.loadingFailed`;
- códigos HTTP;
- recursos JS fallidos;
- errores de consola;
- tiempos de DNS/conexión/TTFB;
- llamadas XHR/fetch del Angular.

Sin esto, el origen externo solo puede clasificarse de forma aproximada.

### 10.4. Amplificación de reintentos HTTP

Existe:

- retry del adaptador `urllib3`;
- bucle explícito de cuatro intentos por documento.

Según el tipo de fallo y cómo contabilice el adaptador sus reintentos, una sola descarga podría realizar muchas peticiones. En el peor caso teórico puede aproximarse a 20 intentos de red por documento.

Recomendación: una sola autoridad de retry por capa HTTP, con presupuesto total y telemetría.

### 10.5. Tiempo máximo elevado

Para una página no vacía que nunca muestra las secciones:

- hasta 60 segundos de espera;
- multiplicado por tres navegaciones;
- multiplicado por hasta dos llamadas predeterminadas del Monitor.

El coste teórico puede acercarse a seis minutos para una sola licitación, sin contar arranque, cierre o documentos.

Recomendación: presupuestos de tiempo por licitación y por ciclo.

### 10.6. Códigos del resultado no persistidos en la incidencia

El `DownloadRunResult` ya contiene un código específico, pero la incidencia del Monitor continúa usando el código general `DOWNLOADER_FAILED`.

Esto mantiene compatibilidad, pero pierde precisión histórica.

Recomendación: persistir `platform_error_code` en un campo separado o dentro del log técnico, sin sustituir los códigos funcionales del Monitor.

### 10.7. Ausencia de cola diferida por plataforma

El ciclo es secuencial. Si la Junta está caída:

- falla una licitación;
- se reintenta inmediatamente;
- se procesa otra de la Junta dentro de la misma ventana de caída;
- se acumulan incidencias correlacionadas.

Una cola de segunda pasada permitiría:

- continuar otras plataformas;
- esperar;
- reintentar solo las fallidas transitorias;
- reducir falsos incidentes.

### 10.8. Perfiles históricos ya existentes

Después de retirar exclusivamente el perfil creado durante esta investigación quedaron 23 perfiles anteriores en `%TEMP%`. No se borraron porque podrían pertenecer a ejecuciones previas o procesos ya finalizados de otros contextos.

Recomendación:

- métrica de perfiles creados/eliminados;
- tarea de mantenimiento conservadora que solo retire perfiles con antigüedad suficiente y sin proceso Chrome cuya línea de comandos los referencie;
- registro de la ruta de perfil por intento;
- nunca borrar por patrón sin comprobar antigüedad, pertenencia y ausencia de proceso.

## 11. Propuesta de reparación definitiva para debatir

### Nivel 1: ya implementado

- errores tipados;
- `error_code`;
- `retryable`;
- navegación dentro del bucle;
- Chrome nuevo en el retry del Monitor;
- normalización URL;
- diagnóstico de render;
- reintentos de documentos;
- preservación de estado;
- pruebas reales y simuladas.

### Nivel 2: recomendado

Implementar una segunda pasada diferida por plataforma:

1. Primera llamada normal.
2. Si `retryable=true`, encolar la licitación, no registrar todavía una incidencia final.
3. Continuar con el resto del ciclo.
4. Al terminar la primera pasada:
   - agrupar por plataforma;
   - esperar, por ejemplo, 60 segundos más jitter;
   - renovar heartbeat y lease;
   - abrir un Chrome nuevo por cada reintento.
5. Si vuelve a fallar:
   - segundo intervalo, por ejemplo 180 segundos;
   - último intento.
6. Solo después registrar la incidencia final.

Ventajas:

- desacopla el retry de la ventana corta de indisponibilidad;
- evita que cuatro licitaciones consecutivas fallen por el mismo episodio;
- conserva el procesamiento de otras plataformas;
- reduce correos de incidencia falsos.

Costes:

- ciclos más largos;
- gestión de heartbeat y lease;
- necesidad de presupuesto máximo;
- mayor complejidad del informe de progreso.

### Nivel 3: observabilidad

Añadir por intento:

```json
{
  "platform": "JUNTA_ANDALUCIA",
  "tender_id": "945359",
  "attempt": 1,
  "browser_session": 1,
  "navigation_attempt": 1,
  "phase": "initial_navigation",
  "error_code": "JUNTA_NAVIGATION_TRANSIENT",
  "retryable": true,
  "duration_ms": 25341,
  "final_url": "...",
  "ready_state": "complete",
  "body_length": 0,
  "app_root_length": 0,
  "network_failures": ["net::ERR_TIMED_OUT"],
  "http_statuses": [],
  "chrome_version": "150.0.7871.129"
}
```

Los logs deben:

- excluir cookies y cabeceras sensibles;
- limitar muestras de contenido;
- conservar códigos y duraciones;
- permitir correlacionar varios fallos de Junta en el mismo ciclo.

### Nivel 4: evaluar motor de navegador

Comparar tres opciones:

1. Mantener CDP artesanal y añadir un lector de eventos.
2. Migrar solo la Junta a Playwright.
3. Descubrir y consumir la API JSON interna de Angular, usando navegador únicamente como fallback.

No debe decidirse sin una prueba técnica.

Criterios:

- estabilidad durante 50-100 ejecuciones;
- capacidad para capturar respuestas y errores de red;
- mantenimiento;
- coste de dependencias;
- compatibilidad Windows;
- comportamiento en headless;
- descarga de documentos autenticados;
- riesgo de que la API interna cambie;
- respeto a las condiciones del portal.

## 12. Criterio de aceptación propuesto

No considerar el problema “reparado definitivamente” solo porque cuatro ejecuciones consecutivas hayan pasado.

Aceptar la solución cuando:

1. Las cuatro URL de este informe pasan en 20 ciclos distribuidos durante varios días.
2. Al menos una prueba de fallo inyectado demuestra:
   - `ERR_TIMED_OUT`;
   - `ERR_CONNECTION_RESET`;
   - Angular vacío;
   - secciones ausentes con contenido;
   - documento interrumpido.
3. El Monitor realiza el número esperado de:
   - intentos internos;
   - sesiones Chrome;
   - reintentos diferidos.
4. No se producen retiradas falsas.
5. No se envía incidencia si un retry diferido termina bien.
6. Cada incidencia final contiene:
   - fase;
   - código específico;
   - cantidad y tiempos de intentos;
   - diagnóstico de red sanitizado.
7. El tiempo total está limitado.
8. No quedan procesos Chrome ni perfiles temporales huérfanos.
9. Una segunda ejecución reutiliza archivos.
10. La suite completa no añade regresiones.

## 13. Prompt autocontenido para ChatGPT y Gemini

Copiar desde “INICIO DEL PROMPT” hasta “FIN DEL PROMPT” sin añadir nada.

---

### INICIO DEL PROMPT

Actúa como arquitecto senior especializado en Python, automatización web sobre Windows, Chrome DevTools Protocol, Playwright, tolerancia a fallos y sistemas de monitorización idempotentes.

Necesito una revisión técnica independiente. No soy programador: soy administrativo. Por favor, no me pidas que complete huecos ni que escriba código adicional. Trabaja únicamente con la información autocontenida de este mensaje, declara tus supuestos y entrega una recomendación que yo pueda comparar con la de otro modelo.

Objetivo: alcanzar un consenso sobre cómo reparar de forma definitiva un descargador de documentos de licitaciones de la Junta de Andalucía. Ya se ha aplicado una corrección concreta; quiero que evalúes si el diagnóstico es correcto, si la corrección tiene riesgos y qué arquitectura final recomendarías.

#### Entorno

```text
Sistema operativo: Windows
Python: 3.13.5, 64 bits
Chrome: 150.0.7871.129
requests: 2.34.2
urllib3: 2.7.0
websocket-client: 1.9.0
Aplicación privada: Python + SQLite
Monitor: worker Python separado, una licitación detrás de otra
```

#### URL de ejemplo

```text
https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/pdc_sirec/perfiles-licitaciones/detalle-licitacion.jsf?idExpediente=947853
https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/pdc-front-publico/perfiles-licitaciones/detalle-licitacion?idExpediente=944739
https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/pdc-front-publico/perfiles-licitaciones/detalle-licitacion?idExpediente=945359
https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/pdc-front-publico/perfiles-licitaciones/detalle-licitacion?idExpediente=974574
```

La primera es una URL histórica. El descargador extrae `idExpediente` y la convierte a:

```text
https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/pdc-front-publico/perfiles-licitaciones/detalle-licitacion?idExpediente=947853
```

#### Arquitectura

Ejecución manual:

```text
.bat
  -> Descargar_Licitacion.py
     -> detecta Junta
     -> Descargar_JuntaAndalucia.py
        -> run_junta_andalucia()
```

Ejecución desde el Monitor:

```text
scheduler o API
  -> worker_launcher
  -> proceso Python worker
  -> orquestador secuencial
  -> registro interno
  -> run_junta_andalucia()
```

El Monitor no ejecuta el `.bat`. Invoca el coordinador Python directamente.

Dentro del descargador:

```text
normalizar URL
-> abrir Chrome headless con perfil temporal y puerto CDP
-> Page.navigate
-> esperar render Angular
-> localizar “Documentación complementaria” y “Anuncios publicados”
-> extraer enlaces
-> copiar cookies y User-Agent a requests.Session
-> descargar por HTTP o por clic
-> calcular SHA-256, tamaño, sección y estado
-> devolver DownloadRunResult
```

#### Evidencia histórica

Ciclo 73, 24/07/2026 13:00:

```text
29/29 procesadas
3 incidencias Junta
error: No han aparecido las secciones documentales esperadas.
```

Ciclo 74, 13:12:

```text
1/1 procesada
respuesta parcial
fallo de un documento:
ConnectionResetError(10054, conexión interrumpida por el host remoto)
```

Ciclo 75, 13:48:

```text
1/1 procesada
0 incidencias
```

Ciclo 76, 14:28:

```text
29/29 procesadas
4 incidencias Junta
```

Detalle:

```text
947853 -> Angular terminó sin contenido en body ni app-root -> 0 retries de Monitor
974574 -> Angular terminó sin contenido en body ni app-root -> 0 retries de Monitor
945359 -> Page.navigate devolvió net::ERR_TIMED_OUT -> 0 retries de Monitor
944739 -> error final Angular sin contenido -> 1 retry de Monitor
```

El Monitor preservó el estado válido anterior en las cuatro.

Ciclo 77, 18:00:

```text
29/29 procesadas
0 incidencias
```

Las cuatro URL se probaron después en carpetas nuevas:

```text
947853 -> 31/31 documentos, success, exit 0
944739 -> 17/17 documentos, success, exit 0
945359 -> 13/13 documentos, success, exit 0
974574 -> 16/16 documentos, success, exit 0
Total: 77/77 y 0 errores
```

Una segunda ejecución de `945359` mediante el lanzador general:

```text
13 reutilizados
0 nuevos
0 errores
changes_detected=false
exit 0
```

#### Defectos internos encontrados

Primero, el Monitor clasificaba errores transitorios por texto:

```python
def _transient_error(exc):
    text = str(exc).casefold()
    return isinstance(exc, (TimeoutError, ConnectionError)) or any(
        token in text
        for token in (
            "timeout",
            "timed out",
            "temporal",
            "temporarily",
            "connection",
            "503",
            "429",
            "bloqueo",
        )
    )
```

No reconoce:

```text
La aplicación de la Junta no llegó a renderizar contenido
net::ERR_TIMED_OUT
```

El segundo contiene `timed_out`, no `timed out`.

Segundo, el código era conceptualmente:

```python
for attempt in range(3):
    Page.navigate(...)
    try:
        esperar_render()
    except:
        retry
```

Por tanto, un error de `Page.navigate` no participaba en los tres intentos.

#### Corrección aplicada

El contrato común ahora tiene:

```python
error_code: str = ""
retryable: bool = False
```

Se añadieron errores tipados:

```python
class JuntaBrowserError(RuntimeError):
    error_code = "JUNTA_BROWSER_ERROR"
    retryable = False

class JuntaTransientBrowserError(JuntaBrowserError):
    retryable = True

class JuntaNavigationTransientError(JuntaTransientBrowserError):
    error_code = "JUNTA_NAVIGATION_TRANSIENT"

class JuntaEmptyRenderError(JuntaTransientBrowserError):
    error_code = "JUNTA_EMPTY_RENDER"

class JuntaDocumentSectionsTimeout(JuntaTransientBrowserError):
    error_code = "JUNTA_DOCUMENT_SECTIONS_TIMEOUT"
```

Los errores CDP temporales reconocidos son:

```text
ERR_ABORTED
ERR_CONNECTION_ABORTED
ERR_CONNECTION_CLOSED
ERR_CONNECTION_RESET
ERR_EMPTY_RESPONSE
ERR_HTTP2_PROTOCOL_ERROR
ERR_INTERNET_DISCONNECTED
ERR_NAME_NOT_RESOLVED
ERR_NETWORK_CHANGED
ERR_QUIC_PROTOCOL_ERROR
ERR_TEMPORARILY_THROTTLED
ERR_TIMED_OUT
```

`ERR_INVALID_URL` no se marca transitorio.

El bucle ahora incluye navegación y render:

```python
for attempt in range(1, 4):
    if attempt > 1:
        clear_cache()
        navigate_about_blank()
    try:
        Page.navigate(...)
        esperar_render_y_secciones(...)
        break
    except Exception:
        if attempt == 3:
            raise
```

El descargador devuelve:

```json
{
  "status": "failed",
  "error_code": "JUNTA_EMPTY_RENDER",
  "retryable": true
}
```

El Monitor decide:

```python
def _transient_failed_result(result):
    if result.status != "failed":
        return False
    if result.retryable:
        return True
    return clasificador_textual_antiguo(result.error)
```

Se conserva el clasificador textual solo para compatibilidad con otros descargadores.

La configuración del Monitor permite entre 1 y 5 intentos totales y usa 2 por defecto. Una segunda llamada abre un Chrome y un perfil temporal nuevos.

#### Detección de página vacía

Cada 0,5 segundos se inspecciona:

```text
location.href
document.title
document.readyState
longitud de body.innerText
muestra de body.innerText
longitud de app-root.innerHTML
cantidad de enlaces
presencia de “documentacion complementaria” o “anuncios publicados”
```

Si tras 25 segundos:

```text
readyState es interactive o complete
bodyLength == 0
appRootLength == 0
```

se lanza `JuntaEmptyRenderError`.

Si hay contenido, pero no aparecen las secciones en 60 segundos, se lanza `JuntaDocumentSectionsTimeout`.

#### Reintentos de documentos

La sesión `requests` utiliza:

```python
Retry(
    total=4,
    connect=4,
    read=4,
    status=4,
    backoff_factor=0.8,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods={"GET"},
    respect_retry_after_header=True,
)
```

Además, la función de descarga tiene un bucle explícito de cuatro intentos ante `requests.RequestException`.

Un archivo ya existente se reutiliza sin hacer petición HTTP.

#### Semántica del Monitor

Si falla la consulta:

```text
no cambia la línea base
no interpreta documentos ausentes como retirados
registra incidencia
conserva último estado válido
```

Si falla solo una parte:

```text
status=partial
fusiona bloques válidos
no infiere retiradas
```

#### Pruebas

```text
Batería dirigida actual: 75 passed
Suite completa antes de añadir la última parametrización: 1349 passed, 1 failed
Único fallo: test frontend que espera una versión antigua de app.js; es ajeno a Junta
py_compile: correcto
node --check: correcto
```

Durante la validación se detectó que el cierre antiguo podía dejar perfiles temporales en Windows porque usaba `shutil.rmtree(..., ignore_errors=True)`. Se observó un perfil atribuible a la prueba actual y 23 anteriores. Se corrigió así:

```text
errores de page.close y browser.close aislados
terminate + wait
fallback kill + wait
8 intentos de borrado cada 0,5 s
limpieza también si Chrome/CDP falla durante el arranque
```

Una ejecución real posterior mantuvo el contador estable y dejó 0 procesos Chrome auxiliares.

#### Riesgos ya identificados

1. Los reintentos del Monitor están separados solo por 2-5 segundos; una caída de minutos seguirá fallando.
2. Tres navegaciones comparten el mismo Chrome; el retry del Monitor sí abre uno nuevo, pero casi inmediatamente.
3. El CDP artesanal descarta eventos de red no asociados al id de la llamada y no persiste `Network.loadingFailed`, consola ni códigos HTTP.
4. Hay retry de `urllib3` y otro bucle de cuatro intentos; puede haber amplificación de peticiones.
5. Una página con contenido sin secciones puede consumir 60 s × 3 navegaciones × 2 llamadas.
6. El resultado tiene `error_code` específico, pero la incidencia funcional sigue almacenando `DOWNLOADER_FAILED`.
7. El ciclo procesa secuencialmente; varias licitaciones Junta consecutivas pueden fallar durante la misma caída.
8. Existen 23 perfiles temporales históricos anteriores que no se borraron por prudencia; la limpieza nueva debe observarse durante varios días.

#### Propuesta que deseo que evalúes

Crear una segunda pasada diferida por plataforma:

```text
primera llamada
-> si retryable=true, encolar
-> continuar otras licitaciones
-> al acabar la primera pasada, esperar 60 s + jitter
-> reintentar en Chrome nuevo
-> si falla, esperar 180 s + jitter
-> último intento
-> solo entonces registrar incidencia final
```

Además:

- telemetría estructurada por intento;
- eventos de red CDP sanitizados;
- presupuesto máximo por licitación y ciclo;
- un solo presupuesto de retry HTTP;
- persistir `platform_error_code` sin perder el código funcional del Monitor.

También quiero decidir entre:

1. mantener CDP artesanal y añadir captura de eventos;
2. migrar únicamente la Junta a Playwright;
3. identificar la API JSON interna de Angular y usar navegador solo como fallback.

#### Lo que te pido

Entrega una respuesta técnica con estas secciones exactas:

1. **Veredicto sobre la causa raíz**  
   Indica qué está confirmado, qué es inferencia y qué evidencia falta.

2. **Revisión crítica de la corrección aplicada**  
   Busca errores, condiciones de carrera, incompatibilidades, falsos positivos de `retryable`, problemas del contrato y riesgos de mantener `schema_version=2`.

3. **Arquitectura definitiva recomendada**  
   Elige una opción principal entre CDP, Playwright o API interna con fallback. Justifica por qué.

4. **Política exacta de reintentos**  
   Propón número de intentos, backoff, jitter, límites temporales, circuit breaker y tratamiento de 429/5xx/reset/timeout/Angular vacío.

5. **Diseño de segunda pasada por plataforma**  
   Incluye estados, pseudocódigo, heartbeat, lease, persistencia y cuándo se envía una incidencia.

6. **Telemetría mínima necesaria**  
   Define campos, eventos CDP o Playwright, privacidad, retención, métricas de procesos/perfiles temporales y cómo distinguir portal caído de selector roto.

7. **Revisión de los reintentos HTTP**  
   Explica si `urllib3.Retry` más cuatro intentos externos es excesivo y proporciona una configuración alternativa concreta.

8. **Plan de implementación por fases**  
   Separa cambios imprescindibles, recomendados y opcionales. Indica orden, riesgos y rollback.

9. **Plan de pruebas**  
   Incluye unitarias, fallos inyectados, integración, pruebas reales distribuidas en el tiempo y criterios cuantificables de aceptación.

10. **Pseudocódigo o diff orientativo**  
    Proporciona suficiente detalle para que otro programador pueda implementarlo, pero no inventes archivos que no aparecen en este informe.

11. **Tabla de decisión**  
    Puntúa CDP artesanal, Playwright y API interna con fallback en estabilidad, diagnóstico, mantenimiento, coste, riesgo y compatibilidad.

12. **Conclusión ejecutiva para una persona no técnica**  
    Máximo 10 líneas. Debe indicar si la solución actual es segura para seguir operando y qué falta para llamarla definitiva.

No propongas desactivar comprobaciones, ignorar errores, eliminar la preservación de estado, saltar CAPTCHA/WAF ni aumentar reintentos sin límite. Si discrepas del diagnóstico, explica exactamente qué dato lo contradice. No me hagas preguntas: declara supuestos razonables.

### FIN DEL PROMPT

---

## 14. Conclusión final

El descargador funciona actualmente con las cuatro fichas problemáticas y la integración ya no depende del texto humano para decidir un retry. Los dos defectos internos directamente vinculados al ciclo 76 están reparados y cubiertos.

La parte que no puede “repararse” dentro de nuestro código es la disponibilidad del portal externo. Para minimizar su impacto de forma profesional, el siguiente paso razonable no es añadir selectores ni multiplicar retries inmediatos, sino introducir:

- segunda pasada diferida por plataforma;
- presupuesto de tiempo;
- circuit breaker;
- telemetría de red;
- consolidación de retries HTTP;
- validación distribuida durante varios días.

Hasta completar esa observabilidad, la explicación más precisa es:

> El portal de la Junta sufrió fallos transitorios; nuestro descargador los detectó, pero el Monitor no reintentó correctamente algunos por una clasificación textual frágil y un timeout de navegación fuera del bucle. Esos defectos internos están corregidos. La solución actual es operativa y sensiblemente más robusta, pero la garantía definitiva requiere retries diferidos y telemetría que permitan separar con datos una caída del portal de un cambio de estructura.
