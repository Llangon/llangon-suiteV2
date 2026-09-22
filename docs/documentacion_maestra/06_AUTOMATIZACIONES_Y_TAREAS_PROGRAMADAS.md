# Automatizaciones y tareas programadas

## Arquitectura vigente

El proceso interno conserva definiciones, próxima ejecución, claims, locks y resultados en SQLite. Las tareas Windows solo deben mantener el proceso disponible y despertar el equipo; no deben duplicar la lógica de negocio.

## Inventario interno canónico

| Clave | Trigger por defecto | Habilitada por defecto | Manual | Regla de fallo |
| --- | --- | ---: | ---: | --- |
| `email_actions_processor` | cada 10 min | Sí | No principal | Registra resultado; reintento posterior. |
| `infonalia_mail_import` | cada 30 min | Sí | Desde admin | Claims evitan duplicado; incidente por bloque. |
| `file_inventory` | cada 240 min | Sí | No principal | Conflictos se informan, no se fuerzan. |
| `agenda_pendientes_diaria` | 08:00 laborables | Sí | Desde API de resumen | Error de envío no muta tareas. |
| `full_backup` | 16:00 | Sí en definición | Sí | Crítica; impide suspensión mientras corre. Configuración documentada suele desactivarla. |
| `night_suspend` | 21:00 | Sí | Sí | Solo si no hay actividad ni trabajo crítico. |
| `pc_restart` | evento | Sí | Sí | Programa reinicio con 60 s para cancelar. |
| `pc_restart_cancel` | evento | Sí | Sí | Cancela el reinicio pendiente. |
| `monitor_licitaciones` | 08:00, 13:00, 18:00 | **No** | Sí | Recupera franja al despertar; incidencias consolidadas. |
| `telegram_status` | evento | Sí sujeto a Telegram | Sí | Diagnóstico; no negocio. |

La configuración efectiva puede venir de ajustes de la Suite o entorno. Por ello “default” no significa “activo hoy”. Estado real observado el 12/09/2026:

- `monitor_licitaciones`: override activo con `08:00,13:00,18:00`.
- `night_suspend`: override desactivado; no se reactivó.
- resto de tareas: sin override explícito salvo configuración efectiva heredada; las ejecuciones recientes confirman acciones por correo, importación Infonalia, inventario y monitor.
- backup completo: copia SQLite y ZIP completos recientes.

## Contradicciones resueltas

- `automation_orchestrator.py` y el monitor e2e fijan 08:00/13:00/18:00. Horas 07:00/12:30/17:30 de servicios/documentos anteriores son legacy.
- Agenda diaria vigente: 08:00 laborables. Una referencia antigua a 06:00 queda sustituida.
- El monitor tiene `default_enabled=False`, pero el override real está activado; prevalece el estado persistido.
- `full_backup` combina definición del orquestador y flag de función. El diagnóstico marca degradación si la tarea está programada pero `LLANGON_FULL_BACKUP_ENABLED` la deja sin efecto.

## Tareas Windows limpias

Arquitectura decidida:

1. **KeeperTick:** al iniciar sesión y cada 5 minutos, sin despertar; mantiene la app/orquestador.
2. **WakeTick:** laborables 08:00 y todos los días 15:55, con wake; permite Agenda y backup.

Tareas antiguas `Web`, `Scheduler`, `Backup`, `AgendaWake` y `MonitorScheduler` fueron sustituidas y no deben coexistir con esta pareja. No existe tarea Windows independiente para el monitor.

El 12/09/2026 se exportaron y consultaron ambas tareas: están presentes, habilitadas y con último resultado correcto. No se detectaron tareas Llangon legacy. Las definiciones y el estado forman parte del punto de restauración externo.

## Idempotencia y concurrencia

- Cada ejecución se reclama con locks/claims; un tick repetido no duplica trabajo.
- Automatizaciones y ciclos del monitor recuperan huérfanos. La cola IA dispone de recuperación de trabajos obsoletos.
- `download_jobs` no dispone de recuperación automática equivalente: se detectó el job 53 en `running` desde julio. El healthcheck lo eleva como incidencia; no se corrige en silencio porque está vinculado a una orden de correo.
- El monitor usa leases por ciclo/licitación y recupera huérfanos (`ORPHAN_CYCLE_RECOVERED`).
- El cierre se persiste aun si un canal de notificación falla.
- La suspensión consulta actividad y trabajos críticos; nunca debe interrumpir backup.

## Auditoría diaria 360

Se propuso una auditoría determinista diaria alrededor de 07:15–07:30 y una revisión profunda semanal, con estados OK/AVISO/ERROR/CRÍTICO. No hay definición en el orquestador ni tarea verificable: D. No debe añadirse al inventario activo hasta que se apruebe e implemente.

La auditoría funcional implantada en septiembre no es esa automatización diaria: se ejecuta bajo demanda desde el dashboard o CLI, no envía avisos y usa niveles OK/DEGRADADO/ERROR.

## Evidencia de vida

KeeperTick llama cada cinco minutos al orquestador único mediante `monitor.scheduler --tick`. Ese modo delega en `automation_orchestrator.scheduler_tick` y no actualiza la tabla histórica `monitor_scheduler_heartbeat`. Por ello el contrato vigente usa `LastRunTime` y `LastTaskResult` de KeeperTick; el heartbeat SQLite queda como compatibilidad/fallback.
