# Contrato de sistema, salud y observabilidad

**Corte:** 12/09/2026.

## Dos niveles de salud

| Mecanismo | Acceso | Finalidad | Efectos |
| --- | --- | --- | --- |
| `GET /api/health` | Público local | Saber si el proceso HTTP responde. KeeperTick depende de su respuesta exacta `{"status":"ok"}`. | Ninguno. Debe permanecer mínimo. |
| `GET /api/admin/operational-health` | Solo `admin` | Diagnóstico funcional para personas, dashboard y máquinas. | Solo lectura; no conecta con servicios externos ni repara datos. |

También puede ejecutarse el diagnóstico local con:

```powershell
.\.venv\Scripts\python.exe -m webapp.infonalia_webapp.operational_health
```

La ejecución por consola no puede consultar el Programador de tareas por sí sola y lo declara degradado/no comprobado. El endpoint administrativo sí incorpora esa comprobación.

## Niveles

- **OK:** el componente cumple el contrato o está desactivado de forma intencionada y es opcional.
- **DEGRADADO:** la Suite puede seguir usándose, pero existe una dependencia, cola, tarea o configuración que requiere atención.
- **ERROR:** falla un componente crítico —por ejemplo SQLite o el esquema esencial— y no puede garantizarse el funcionamiento.

Un componente opcional desactivado no degrada por sí solo la Suite. Para IMAP, SMTP, IA y Telegram la auditoría comprueba únicamente preparación de configuración; nunca inicia sesión ni envía mensajes.

## Contrato automático

`system_contract.py` deriva o consolida condiciones verificables:

- última migración registrada en código;
- tablas esenciales;
- rutas esenciales;
- roles admitidos;
- estados canónicos de licitación y actuación;
- tareas Windows vigentes;
- plataformas del registro único de descargadores.

La validación de SQLite se realiza con conexión URI `mode=ro`, `PRAGMA query_only` y `PRAGMA quick_check(1)`. No ejecuta migraciones ni crea tablas. Los tests comprueban el contrato contra una base inicializada por la propia aplicación y comprueban que el archivo no cambia durante el diagnóstico.

## Componentes comprobados

| Componente | Evidencia | Umbral o regla |
| --- | --- | --- |
| Aplicación | El propio endpoint responde. | Crítico. |
| SQLite | Apertura solo lectura y `quick_check`. | Cualquier fallo es ERROR. |
| Esquema | Migraciones, tablas y roles. | Tabla/migración ausente es ERROR; rol ajeno es DEGRADADO. |
| Dropbox local | Configuración, existencia y tipo directorio. | Ausente/no disponible es DEGRADADO. No se escribe. |
| Scheduler | Última ejecución y resultado de KeeperTick; heartbeat antiguo solo como fallback. | Más de 20 minutos, deshabilitada o resultado no cero: DEGRADADO. |
| Backups | Presencia y edad de copia SQLite y ZIP completo. | Más de 36 horas o configuración incoherente: DEGRADADO. |
| Colas | Descargas e IA activas o fallidas. | Activa más de 2 horas; `deferred` IA más de 24 horas; fallo no descartado en 24 horas: DEGRADADO. |
| Monitor | Último ciclo, heartbeat, errores e incidencias. | Ciclo activo más de 2 horas o último ciclo reciente con incidencias: DEGRADADO. |
| IMAP/SMTP/IA/Telegram | Flags y presencia de campos requeridos. | Función activa e incompleta: DEGRADADO. Sin llamadas externas. |
| Tareas Windows | KeeperTick y WakeTick. | Ausente o deshabilitada: DEGRADADO. |

Los umbrales son operativos y conservadores; deben ajustarse solo con una decisión documentada y tests.

## Dashboard

El dashboard no es una superficie paralela. Encabeza la vista existente **Automatizaciones** con la pregunta «¿Qué necesita atención ahora?» y muestra primero `needs_attention`. La Agenda continúa siendo la fuente de trabajo y vencimientos; el dashboard muestra excepciones técnicas y operativas.

La respuesta contiene:

- `status` y `human_summary`;
- recuento por nivel;
- `needs_attention` con acción sugerida;
- todos los componentes;
- contrato de sistema no secreto;
- política de comprobación (`destructive=false`, `external_connections=false`).

No incluye contraseñas, tokens, claves ni rutas locales completas de datos.

## Estado real observado el 12/09/2026

- Aplicación privada escuchando en loopback 8787 y `/api/health` correcto.
- SQLite accesible, `quick_check=ok`, contrato completo hasta `0036_tender_monitor_baseline_ownership`.
- Dos usuarios activos, uno `admin` y uno `nuria`; ambos con hash PBKDF2-SHA256 y ninguno legacy.
- KeeperTick y WakeTick presentes, habilitadas y con último resultado correcto.
- Backups SQLite y completo presentes y dentro del umbral.
- Monitor de licitaciones activado; último ciclo completado sin incidencias recientes.
- IMAP, SMTP, IA y Telegram preparados según configuración local; conectividad externa no probada.
- **Incidencia abierta:** `download_jobs.id=53` permanece `running` desde el 21/07/2026. El dashboard la detecta. No se alteró el dato ni se envió aviso durante la auditoría.

## Principio de observabilidad

**Funciona → silencio. Falla → incidencia visible.**

Se reutilizan `automation_runs`, `download_jobs`, `ai_analysis_jobs`, ciclos/incidencias del monitor, backups existentes y tareas Windows. No se ha creado una tabla paralela de alarmas ni un servicio externo adicional.
