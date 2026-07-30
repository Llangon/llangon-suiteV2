# Monitor de licitaciones

## Alcance

El monitor consulta las plataformas oficiales mediante los siete descargadores registrados en `herramientas_python.descargadores`. No deduce novedades examinando el árbol de Dropbox: compara snapshots técnicos normalizados producidos por los descargadores.

El seguimiento tiene una única fuente de verdad: el fichero físico `EnSeguimiento.llangon` dentro de la carpeta de la licitación. Las tablas `tender_monitor_*` guardan ejecución, estado técnico, diferencias, IA, notificaciones e incidencias; no guardan un segundo flag de seguimiento.

La programación automática usa el orquestador interno único de la suite y está configurada todos los días a las **08:00, 13:00 y 18:00**. El tick existente comprueba el vencimiento cada cinco minutos. Si el PC estaba suspendido, al reanudarse ejecuta una sola vez la última franja vencida del día; una franja ya completada no se repite.

También siguen disponibles las ejecuciones manuales:

- global, solo para administración;
- individual, para administración y revisión desde la ficha de una licitación.

## Flujo técnico

1. Se descubren los marcadores físicos y se valida cada licitación: carpeta, URL oficial, plataforma y descargador registrado.
2. Se obtiene el snapshot confirmado al que apunta `tender_monitor_baselines` en SQLite. El sidecar `.llangon-monitor/technical_snapshot.json` es solo una caché diagnóstica y nunca sustituye esa autoridad.
3. Se ejecuta el descargador neutral de la plataforma.
4. Se normalizan datos generales, fechas relevantes, documentos oficiales y, cuando la plataforma lo soporta, preguntas y respuestas.
   Un hash solo puede acreditar una modificación cuando procede de los bytes observados en la plataforma; el hash de una copia local reutilizada nunca constituye una novedad oficial.
5. Una respuesta parcial conserva los bloques anteriores y nunca convierte ausencias en retiradas.
6. Si no existe línea base y la respuesta documental es completa, se reconstruye la línea base sin generar novedad, IA ni aviso.
   Un sidecar heredado u huérfano tampoco genera incidencia en esta primera revisión: se sustituye por la caché del nuevo baseline. Solo se informa de divergencia cuando ya existe un baseline autoritativo en SQLite.
7. Las diferencias reales se agrupan en un único lote idempotente por licitación.
8. Los documentos nuevos o modificados de categorías configuradas pueden usar la cola IA existente. Preguntas y respuestas nunca activan IA.
9. Se envía un correo agrupado por licitación y un Telegram corto por destinatario configurado. Los canales son independientes.
10. Las incidencias del ciclo se consolidan en un único correo al administrador de incidencias.

Las descargas normales de la aplicación, las acciones por correo y el BAT central descargan ficheros, pero no escriben el baseline ni el sidecar técnico del monitor. Cuando el monitor revise después la licitación, comparará la plataforma contra su baseline anterior, registrará el snapshot nuevo y notificará la novedad aunque el fichero ya exista físicamente; en ese caso el descargador lo reutiliza en vez de volver a copiarlo.

## Estados importantes

- `baseline_rebuilt`: se ha creado una línea base compatible; no es una novedad.
- `no_changes`: la plataforma no presenta diferencias relevantes.
- `notified`: novedades enviadas por todos los canales configurados.
- `partial`: algún canal falló o la respuesta técnica fue parcial; el detalle aclara el caso.
- `no_recipients`: se detectaron novedades, pero no hay destinatarios globales activos.
- `not_prepared`: falta marcador, carpeta, URL, plataforma o descargador.
- `completed_with_incidents`: el ciclo terminó y conserva incidencias auditables.
- `failed`: el ciclo no pudo iniciarse o perdió una condición global necesaria.

Los leases globales y por licitación impiden solapamientos. Un ciclo sin lease ni heartbeat que supera la ventana configurada se cierra como fallido y deja la incidencia `ORPHAN_CYCLE_RECOVERED`.

## Uso desde la interfaz

En **Monitor de licitaciones**:

- **Seguimiento** muestra licitaciones preparadas, último resultado, IA y avisos. **Revisar ahora** inicia un ciclo global manual.
- **Histórico** permite filtrar por estado, licitación, novedades e incidencias. El detalle muestra diferencias, canales, IA y reintentos.
- **Configuración** gestiona tiempos máximos, reintentos, categorías IA y destinatarios globales. La programación muestra su estado y las tres franjas; su activación se administra desde la consola general de automatizaciones.

Los reintentos son selectivos:

- una notificación vuelve a intentar únicamente su correo o Telegram;
- un reintento de IA reutiliza el lote y los documentos ya descargados;
- un error de consulta crea un nuevo ciclo individual;
- el resumen de incidencias puede reenviarse sin repetir el ciclo.

En la ficha avanzada de una licitación, el panel **Monitor de licitaciones** permite revisar individualmente, consultar las últimas ejecuciones y, para administración, crear o retirar el marcador físico.

## Configuración segura

La aplicación usa `LLANGON_DROPBOX_BASE_PATH` como raíz normal. Para una prueba aislada puede configurarse `INFONALIA_MONITOR_ROOT` con una réplica local que no sea la carpeta productiva.

No se deben copiar secretos al histórico, a capturas ni a incidencias. Las credenciales siguen perteneciendo a los descargadores y servicios existentes. El detalle técnico de incidencias se oculta a usuarios no administradores.

## Prueba manual controlada en desarrollo

Para reproducir el comportamiento sin tocar datos reales:

1. Crear una réplica local fuera de la carpeta productiva y asignarla temporalmente a `INFONALIA_MONITOR_ROOT`.
2. Copiar solo una estructura mínima de licitación de prueba, con `{id}.llangon` y `EnSeguimiento.llangon`; no copiar credenciales ni datos sensibles innecesarios.
3. Usar una base SQLite temporal inicializada por la aplicación, nunca la base real.
4. Mantener sin destinatarios globales o utilizar cuentas de prueba expresamente autorizadas.
5. Ejecutar una primera revisión individual. El resultado esperado es `baseline_rebuilt` y cero notificaciones.
6. Simular en el descargador de prueba un documento nuevo y ejecutar otra revisión. Debe crearse un lote con una sola notificación agrupada.
7. Repetir exactamente el mismo resultado. No debe aparecer un segundo lote ni un segundo aviso.
8. Simular una respuesta parcial eliminando un documento del resultado. No debe registrarse como retirado.
9. Revisar Histórico, incidencias, permisos y los reintentos selectivos.
10. Retirar `INFONALIA_MONITOR_ROOT` al terminar.

La transición a una carpeta o canal real requiere una autorización operativa separada.

## Primera prueba manual real autorizada

Cuando exista autorización para usar datos y canales reales:

1. Crear una copia protegida de la base SQLite y escoger licitaciones controladas, preferiblemente una por plataforma y con línea base ya creada por una descarga normal.
2. En la configuración de usuarios, confirmar el correo y el chat de Telegram del administrador y que Telegram está habilitado para ese usuario.
3. En **Monitor de licitaciones > Configuración**, activar correo y Telegram solo para el administrador, marcarlo como responsable de incidencias y dejar a Nuria sin canales.
4. Usar los botones de prueba de correo y Telegram y verificar su resultado antes de revisar licitaciones.
5. Confirmar que la cabecera indica **Ejecución automática activa** y las franjas 08:00, 13:00 y 18:00.
6. Verificar el marcador físico `EnSeguimiento.llangon` de la licitación elegida.
7. Desde la ficha avanzada, pulsar **Revisar ahora** y comprobar descarga, comparación, lote, IA cuando corresponda, correo, Telegram e histórico.
8. Repetir la revisión sin cambios y confirmar que no aparecen otro lote, otra IA ni otro aviso.
9. En una carpeta controlada, añadir o renombrar un fichero manual y repetir: no debe producir una novedad oficial.
10. Simular cualquier error únicamente en un entorno protegido y comprobar que el ciclo conserva el estado anterior y genera un solo informe consolidado.
11. Tras validar ejecuciones individuales, ejecutar un ciclo global pequeño.
12. Confirmar que la tarea interna conserva las tres franjas, que no ha repetido una franja completada y que no existe ninguna tarea Windows nueva específica del monitor.

## Activar a Nuria posteriormente

No requiere cambios de código:

1. Completar el correo de Nuria en su ficha de usuario.
2. Si recibirá Telegram, configurar su chat y habilitar las notificaciones Telegram del usuario.
3. En **Monitor de licitaciones > Configuración**, marcar correo, Telegram o ambos en la fila de Nuria.
4. Guardar y usar los botones de prueba de sus canales.

Los destinatarios siguen siendo globales; no se crea ninguna excepción por licitación.

## Programación automática

La tarea `monitor_licitaciones` usa el mismo worker y el mismo orquestador de ciclos que la ejecución manual. Sus franjas son `08:00,13:00,18:00`. `LlangonSuite-KeeperTick` la comprueba con el reloj interno mientras el equipo está activo y `LlangonSuite-WakeTick` garantiza el tick de reanudación previsto por la suite. La fecha de activación impide recuperar franjas anteriores al momento de habilitarla y el histórico de `automation_runs` deduplica cada franja completada.

No existe un scheduler, servicio ni tarea Windows independiente para el monitor.

## Validación de desarrollo

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pytest --collect-only -q
.\.venv\Scripts\python.exe -m pytest -q --basetemp .\codex_pytest_monitor
node --check webapp/infonalia_webapp/static/app.js
node --check webapp/infonalia_webapp/static/tender_monitor.js
node --check webapp/infonalia_webapp/static/login.js
node --check firebase/public_firebase/static/public.js
```

Las migraciones aditivas son `0035_tender_monitor_e2e` y `0036_tender_monitor_baseline_ownership`. La segunda crea el puntero de baseline exclusivo del monitor y migra de forma compatible los snapshots anteriores.
