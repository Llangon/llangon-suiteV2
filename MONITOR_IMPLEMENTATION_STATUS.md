# Estado de implementación del Monitor de licitaciones

Actualizado: 2026-07-22

## Estado general

- Rama de trabajo: `codex/monitor-licitaciones-e2e`.
- Fase actual: implementación end-to-end completada y validada.
- Ejecución automática del monitor: activa desde 2026-07-20 a las 20:51, con franjas diarias a las 08:00, 13:00 y 18:00.
- El repositorio partía de un árbol con numerosos cambios locales no confirmados. La implementación del monitor se protege mediante commits selectivos propios; los cambios ajenos o preexistentes permanecen fuera de esos commits.

## Fases completadas

- Leído el alcance completo del encargo.
- Leídas las fuentes de verdad y la documentación operativa principal.
- Identificados el paquete `webapp/infonalia_webapp/monitor`, el contrato `DownloadRunResult`, el registro neutral de siete descargadores, el marcador real y las integraciones existentes de scheduler, IA, correo, Telegram, usuarios y CSRF.
- Creada una rama de trabajo desde el `HEAD` inicial sin alterar los cambios locales existentes.
- Creada antes del staging una copia de seguridad del parche versionado, el índice y todos los archivos no rastreados visibles para Git, con manifiesto SHA-256 dentro de `.git/codex-backups`.
- Establecida la línea base de pruebas relevantes.
- Implementada la migración `0035_tender_monitor_e2e` con ciclos, ejecuciones, snapshots, lotes, diferencias, vínculos IA, notificaciones, incidencias, resumen consolidado, leases, configuración y destinatarios globales.
- Implementados snapshots técnicos atómicos en `.llangon-monitor/technical_snapshot.json`; solo los escribe el monitor y funcionan como caché diagnóstica, nunca como autoridad del baseline.
- Implementada comparación semántica por bloques, protección de respuestas parciales, retiradas/restauraciones, huellas estables e idempotencia por restricciones SQLite.
- Implementado el orquestador secuencial real con bloqueo global y por licitación, recuperación por expiración, línea base compatible, reintentos temporales, cola IA existente, correo, Telegram e incidencias consolidadas.
- Las descargas normales de la app, correo y BAT central no escriben el baseline ni el sidecar del monitor. El siguiente ciclo conserva así la capacidad de detectar y notificar la novedad aunque el fichero ya esté descargado.
- Integradas API autenticada, CSRF, permisos de administración/revisión, worker asíncrono y ejecución manual global o individual.
- Integrada la programación en el orquestador interno único, con tres franjas diarias, recuperación de la última franja vencida tras reanudación y deduplicación por franja. No se ha creado una tarea Windows independiente.
- Implementados reintentos selectivos de consulta, IA, correo, Telegram e informe de incidencias sin repetir fases ya completadas.
- Implementadas recuperación de leases/ciclos huérfanos y auditoría de errores de configuración o lanzamiento.
- Implementada la sección **Monitor de licitaciones**, con resumen, seguimiento, histórico, filtros, detalle, configuración y panel en ficha avanzada.
- Añadida la guía operativa `docs/MONITOR_LICITACIONES.md`.

## Archivos principales modificados

- `MONITOR_IMPLEMENTATION_STATUS.md` (este registro de continuidad).
- `webapp/infonalia_webapp/monitor/tender_schema.py`.
- `webapp/infonalia_webapp/monitor/snapshots.py`.
- `webapp/infonalia_webapp/monitor/comparison.py`.
- `webapp/infonalia_webapp/monitor/tender_repository.py`.
- `webapp/infonalia_webapp/monitor/tender_preparation.py`.
- `webapp/infonalia_webapp/monitor/tender_rules.py`.
- `webapp/infonalia_webapp/monitor/tender_messages.py`.
- `webapp/infonalia_webapp/monitor/tender_orchestrator.py`.
- `webapp/infonalia_webapp/db_migrations.py`.
- `herramientas_python/Descargar_Licitacion.py`.
- `webapp/infonalia_webapp/app.py`.
- `webapp/infonalia_webapp/automation_orchestrator.py` y `monitor/service.py`.
- `webapp/infonalia_webapp/monitor/tender_api.py` y workers del monitor.
- `webapp/infonalia_webapp/static/tender_monitor.js` y `tender_monitor.css`.
- `webapp/infonalia_webapp/static/index.html` y `static/app.js`.
- Pruebas nuevas de núcleo, orquestador, API, permisos, CSRF y frontend.

## Migraciones aplicadas

- `0035_tender_monitor_e2e` figura aplicada en la base real desde 2026-07-20 13:19:03, antes de la activación automática documentada aquí.
- `0036_tender_monitor_baseline_ownership` figura aplicada en la base real desde 2026-07-22 11:48:52. La tabla `tender_monitor_baselines` contiene un único puntero confirmado por licitación y el sidecar queda fuera de la decisión comparativa.

## Pruebas ejecutadas

- `pytest --collect-only -q`: 1414 pruebas recopiladas.
- Selección de monitor, scheduler, marcador, descargadores, notificaciones y migraciones: 249 superadas en 44,69 s usando `--basetemp codex_pytest_019f7ed9`.
- La primera ejecución sin `--basetemp` quedó bloqueada por permisos del temporal global de pytest; no fue un fallo funcional (135 pasaron y 114 no pudieron preparar `tmp_path`).
- Núcleo/migración inicial: 32 superadas.
- Núcleo/orquestador: 14 superadas.
- Descarga normal, lanzador y monitor: 59 superadas.
- Batería focal final de monitor e integraciones: 142 superadas.
- Recopilación final: 1.453 pruebas.
- Suite completa final: **1.453 superadas en 228,50 s** con un `--basetemp` aislado dentro del workspace, eliminado al terminar.
- `node --check` superado para `app.js`, `tender_monitor.js`, `login.js` y la web pública.
- Programación automática: 88 pruebas focales finales superadas, incluida la activación, las franjas 08:00/13:00/18:00, la recuperación tras despertar, la deduplicación, el lanzamiento automático del worker y la conservación de la activación al verificar el esquema.

## Estado operativo de la activación

- Se creó una copia SQLite consistente previa a la activación en la carpeta protegida de seguridad de Codex.
- La tarea interna `monitor_licitaciones` está habilitada con `08:00,13:00,18:00`; al activarse después de las 18:00 no recuperó retroactivamente esa franja y su siguiente ejecución quedó fijada para 2026-07-21 08:00.
- La activación no inició un ciclo, no ejecutó descargadores y no envió correo, Telegram ni trabajos IA.
- Se reutilizan `LlangonSuite-KeeperTick` y `LlangonSuite-WakeTick`, ambas activas y sanas; no se creó ni modificó una tarea Windows específica del monitor.

## Recuperación del ciclo 29 y validación real (2026-07-21)

- Corregida la resolución de URL: una URL documental o no apta se sustituye por el `HTTP.url` válido de la carpeta canónica; una entrada todavía inválida se registra como `INVALID_PROFILE_URL` antes de invocar el descargador.
- Inventario y monitor se aplazan mutuamente desde el orquestador. El inventario confirma por licitación y deja de mantener una única transacción de escritura durante toda la exploración.
- Cada tick recupera ciclos huérfanos antes de comprobar si existe un ciclo activo. La recuperación cierra también la ejecución en curso y elimina sus leases.
- El worker registra PID de lanzador, PID efectivo, código de salida, horas de inicio/fin y un log por ciclo en `runtime/monitor-workers/`.
- Los fallos fatales se cierran con una conexión SQLite nueva y reintentos, marcando ciclo y ejecución sin depender de la conexión que falló.
- El tick recuperó el ciclo `#29` y la ejecución `174` como huérfanos; ambos quedaron cerrados y sin leases.
- Copia SQLite consistente posterior a la recuperación y anterior al nuevo ciclo: `.git/codex-safety/monitor-cycle29-recovered-before-global-20260721.sqlite3` (`integrity_check=ok`).
- Ciclo global real `#30`: 26/26 procesadas, 23 sin cambios, 1 línea base reconstruida, 1 lote de novedades, 1 incidencia, estado `completed_with_incidents`, worker con código 0.
- La licitación interna `61`, que había fallado en el ciclo 29, terminó correctamente como `baseline_rebuilt`.
- El ciclo 30 detectó una modificación documental real en la licitación `328`; correo y Telegram se enviaron correctamente al único destinatario configurado. El informe consolidado de la incidencia también se envió.
- La incidencia de Junta de Andalucía en la licitación `23` se debía a que el temporal se eliminaba antes de que Chrome liberase `downloads.htm`. Corregido el orden de cierre y añadida limpieza con reintentos.
- Ciclos individuales reales `#31` y `#32` sobre la licitación `23`: ambos `completed`, `no_changes`, sin incidencias, sin lotes ni notificaciones; el segundo verificó también la limpieza silenciosa del temporal.
- IA permaneció desactivada. La programación continúa habilitada en `08:00,13:00,18:00` y no se cambió ninguna tarea Windows.
- Pruebas focales de monitor, inventario y scheduler: 85 superadas. Pruebas focales adicionales de Junta: 4 superadas. `py_compile`, `PRAGMA integrity_check` y `git diff --check` superados.

## Despliegue y validación real de la autoridad de baseline (2026-07-22)

- Copia SQLite consistente previa al despliegue: `runtime/backups/sqlite/infonalia_20260722_114754.db`; `quick_check` e `integrity_check` correctos.
- Aplicada `0036_tender_monitor_baseline_ownership`, con 26 punteros migrados y sin punteros rotos.
- Reiniciada la aplicación y comprobado `/api/health` con respuesta 200.
- Probados de forma expresa los canales reales del administrador: correo y Telegram respondieron correctamente. Nuria continuó sin canales activos e IA permaneció desactivada.
- Durante el canario se detectaron tres avisos falsos de compatibilidad heredada: dos en PLACE (`#36` y `#37`) y uno en Catalunya (`#41`). Se conservaron en el histórico, se detuvo el avance y se corrigieron las causas: campos opcionales ausentes frente a vacíos, respuestas HTML intermedias sobre enlaces binarios e identidades antiguas basadas solo en nombre.
- PLACE: reconstrucción controlada `#38` y revisiones `#39` y `#40`, ambas `no_changes`, sin lotes, diferencias ni notificaciones.
- Junta de Andalucía: reconstrucción `#43` y revisiones `#44` y `#45`, ambas `no_changes`, sin lotes, diferencias ni notificaciones.
- Comunidad de Madrid: reconstrucción `#46` y revisiones `#47` y `#48`, ambas `no_changes`, sin lotes, diferencias ni notificaciones.
- Xunta de Galicia: el intento `#49` documenta un bloqueo de red del sandbox, sin cambio de baseline ni notificación; repetición autorizada `#50` y revisiones `#51` y `#52`, ambas `no_changes`, sin lotes, diferencias ni notificaciones.
- Catalunya: reconstrucción posterior a la corrección `#53` y revisiones `#54` y `#55`, ambas `no_changes`, sin lotes, diferencias ni notificaciones.
- Euskadi y Navarra no tenían licitaciones seguidas aptas para una prueba productiva. Se validaron dos ejecuciones reales por plataforma en carpetas temporales aisladas: Euskadi 16 documentos creados y después 16 reutilizados; Navarra 1 creado y después 1 reutilizado; cero diferencias en ambos casos y temporales eliminados.
- `LlangonSuite-KeeperTick` y `LlangonSuite-WakeTick` existen, están habilitadas y terminaron su última ejecución con resultado 0. No se instaló ni duplicó ninguna tarea Windows. La tarea interna `monitor_licitaciones` sigue habilitada en `08:00,13:00,18:00`.
- Regresión final oficial: 1.309 pruebas superadas en 338,64 s, cuatro comprobaciones `node --check` correctas y `git diff --check` sin errores.
- Copia SQLite consistente posterior al despliegue: `runtime/backups/sqlite/infonalia_20260722_124125.db`.

## Corrección del ciclo automático de las 13:00 (2026-07-22)

- El ciclo global `#57` procesó 26 licitaciones: 25 `no_changes` y una supuesta modificación; terminó con 21 incidencias y envió un informe consolidado.
- Las 21 incidencias eran diagnósticos `LEGACY_SIDECAR_IGNORED` sobre sidecars heredados cuya huella coincidía exactamente con el baseline autoritativo de SQLite. No eran fallos de descarga. La reparación de un sidecar heredado idéntico pasa a ser silenciosa; una divergencia real continúa registrándose.
- La supuesta modificación de la licitación `148` conservaba nombre y URL y solo variaba el SHA calculado sobre la copia local de Dropbox. El fichero local llegó a presentar un tercer hash sin representar una nueva publicación oficial.
- Añadido `sha256_source` al contrato de artefactos. Un cambio de SHA solo produce `document_modified` cuando ambos snapshots certifican `sha256_source=remote`.
- PLACE calcula ahora el SHA sobre los bytes recibidos de la plataforma incluso si el fichero físico ya existe y se reutiliza. Los hashes locales sin certificación remota dejan de intervenir en la comparación.
- Backup previo a la corrección: `runtime/backups/sqlite/infonalia_20260722_132107.db`.
- Validación real sobre la licitación `148`: ciclos `#58` y `#59`, ambos `completed/no_changes`, sin incidencias, lotes, diferencias ni notificaciones; el segundo reutilizó el mismo snapshot remoto del primero.
- Regresión final: 1.312 pruebas superadas en 326,82 s y comprobaciones JavaScript correctas.

## Corrección del ciclo manual global 62 (2026-07-22)

- El ciclo `#62` procesó correctamente 29 licitaciones: 26 `no_changes`, tres `baseline_rebuilt`, cero novedades, lotes o notificaciones y una única incidencia de baseline.
- La incidencia pertenecía a la licitación `56`: no existía baseline SQLite y sí un sidecar heredado. La primera revisión remota creó correctamente el baseline, por lo que la caché antigua no representaba una divergencia auditable.
- Corregida la clasificación: sin baseline autoritativo no se registra `LEGACY_SIDECAR_IGNORED` ni `SIDECAR_DIVERGENT`; la primera respuesta remota completa crea el baseline y reemplaza silenciosamente el sidecar. Cuando sí existe baseline SQLite, una divergencia real continúa generando incidencia.
- Backup previo al despliegue: `runtime/backups/sqlite/infonalia_20260722_143155.db`.
- Validación real de la licitación `56`: ciclo `#63`, `completed/no_changes`, snapshot `349` reutilizado, sin incidencias, lotes ni notificaciones.
- Regresión final: 1.313 pruebas superadas en 324,01 s y comprobaciones JavaScript correctas.
