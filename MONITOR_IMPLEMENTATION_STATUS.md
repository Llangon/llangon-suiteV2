# Estado de implementación del Monitor de licitaciones

Actualizado: 2026-07-20

## Estado general

- Rama de trabajo: `codex/monitor-licitaciones-e2e`.
- Fase actual: implementación end-to-end completada y validada.
- Ejecución automática del monitor: debe permanecer desactivada.
- El repositorio partía de un árbol con numerosos cambios locales no confirmados. La implementación del monitor se protege mediante commits selectivos propios; los cambios ajenos o preexistentes permanecen fuera de esos commits.

## Fases completadas

- Leído el alcance completo del encargo.
- Leídas las fuentes de verdad y la documentación operativa principal.
- Identificados el paquete `webapp/infonalia_webapp/monitor`, el contrato `DownloadRunResult`, el registro neutral de seis descargadores, el marcador real y las integraciones existentes de scheduler, IA, correo, Telegram, usuarios y CSRF.
- Creada una rama de trabajo desde el `HEAD` inicial sin alterar los cambios locales existentes.
- Creada antes del staging una copia de seguridad del parche versionado, el índice y todos los archivos no rastreados visibles para Git, con manifiesto SHA-256 dentro de `.git/codex-backups`.
- Establecida la línea base de pruebas relevantes.
- Implementada la migración `0035_tender_monitor_e2e` con ciclos, ejecuciones, snapshots, lotes, diferencias, vínculos IA, notificaciones, incidencias, resumen consolidado, leases, configuración y destinatarios globales.
- Implementados snapshots técnicos atómicos en `.llangon-monitor/technical_snapshot.json`; solo consumen el resultado estructurado del descargador y el estado técnico de preguntas.
- Implementada comparación semántica por bloques, protección de respuestas parciales, retiradas/restauraciones, huellas estables e idempotencia por restricciones SQLite.
- Implementado el orquestador secuencial real con bloqueo global y por licitación, recuperación por expiración, línea base compatible, reintentos temporales, cola IA existente, correo, Telegram e incidencias consolidadas.
- Las descargas normales de la app, correo y BAT central actualizan la línea base técnica sin crear lotes ni avisos.
- Integradas API autenticada, CSRF, permisos de administración/revisión, worker asíncrono y ejecución manual global o individual.
- La programación queda desactivada en esquema, servicio legado y orquestador interno; las variables antiguas no pueden activarla.
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

- `0035_tender_monitor_e2e` añadida y probada de forma idempotente sobre SQLite temporal; no se ha abierto ni modificado la base real.

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

## Acciones operativas no ejecutadas

- No se ha aplicado la migración sobre la base SQLite real.
- No se ha iniciado un ciclo contra plataformas reales.
- No se han enviado correos, Telegram ni trabajos IA reales.
- No se ha activado ninguna tarea programada ni proceso Windows.
- La primera prueba real debe seguir la guía controlada y contar con autorización operativa expresa.
