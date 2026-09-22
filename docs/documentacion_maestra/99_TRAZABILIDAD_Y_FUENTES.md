# Trazabilidad y fuentes

## Corte y método

Auditoría inicial realizada el 04/09/2026 y ampliada el 12/09/2026 sobre el árbol local de `Llangon-SuiteV2`. Se contrastaron implementación, pruebas, historial Git, documentación y conversaciones accesibles. La ampliación inspeccionó SQLite real mediante snapshot/API y lectura segura, procesos, logs operativos, backups, tareas Windows y configuración no secreta. No reveló valores secretos ni contactó servicios externos.

## Escala de evidencia

| Nivel | Evidencia | Uso |
| --- | --- | --- |
| E1 | Código actual + prueba que lo ejerce | Afirma implantación técnica. |
| E2 | Código actual sin prueba específica localizada | Afirma existencia, con cautela. |
| E3 | Git/documento técnico fechado coherente con código | Explica decisión/evolución. |
| E4 | Conversación reciente con decisión explícita | Define producto si no contradice implementación posterior. |
| E5 | Propuesta, documento antiguo o informe de producción no revalidado | Histórico, D o pendiente operativo. |

## Fuentes rectoras

- `AGENTS.md`: restricciones, mapa y orden de verdad.
- `docs/CODEX_CONTEXT.md`: puente operativo actualizado hacia esta base maestra.
- `docs/COMANDOS_DESARROLLO.md`: comandos seguros y arranque local.
- Código y pruebas bajo `webapp/infonalia_webapp`.
- Descargadores y utilidades bajo `herramientas_python`.
- Web pública bajo `firebase/public_firebase`.
- Scripts bajo `scripts/` y `scripts/windows/`.
- Cambios locales de Ficha, portal y Cloudflare, expresamente tratados como no consolidados.

## Documentación revisada por área

### Arquitectura, decisiones y seguridad

- `docs/ARQUITECTURA_FUTURA.md`: fases históricas; muchas ya implantadas.
- `docs/DECISIONES_TECNICAS.md`: ADR-001 a ADR-056.
- `docs/PRECHECK_*.md`, `docs/CHECKPOINTS_PELIGROSOS.md`.
- `docs/DESPLIEGUE_LOCAL_WINDOWS.md`, `docs/DESPLIEGUE_COLABORACION.md`.
- `PROJECT_CONTEXT.md` como snapshot antiguo, sin modificar.

### Función e integración

- `docs/CLIENTES_Y_ENVIOS_CLIENTES.md`.
- `docs/MONITOR_LICITACIONES.md` y `MONITOR_IMPLEMENTATION_STATUS.md`.
- `docs/DESCARGADORES_LICITACIONES.md`, arquitecturas PLACE/general e informes por plataforma.
- `docs/INFORME_VALIDACION_IMPORTADOR_INFONALIA.md`.
- `docs/JUSTIFICACIONES_BAJA.md`.
- `docs/FICHA_LLANGON_V2.md`.
- `docs/PORTAL_LICITACIONES_CLOUDFLARE.md`.

### Web pública

- `docs/INVENTARIO_WEB_PUBLICA.md`.
- `docs/WEB_PUBLICA_CAMBIOS.md` y su informe de reversión.
- `docs/README_DEPLOY_FIREBASE_PUBLICA.md`.
- `docs/DATOS_LEGALES_PENDIENTES.md` y textos/guías relacionados.

### Histórico

- `documentos_contexto/PROYECTO_INFONALIA.md`.
- `documentos_contexto/MIGRACION_A_LLANGONWEBAPP.md`.
- `MIGRACION_LOG.md`, `INVENTARIO_MIGRACION.md`, `SANEAMIENTO_REPOSITORIO.md`.

## Código contrastado

### Núcleo y seguridad

`app.py`, `db_migrations.py`, `web_security.py`, `session_security.py`, `user_settings.py`, `licitacion_states.py`, `operational_settings.py` y frontend estático.

### Flujos

Importador Infonalia, acciones por correo, descargadores, storage/markers, Agenda, actuaciones, comentarios, clientes/envíos, notificaciones, backups y orquestador.

### IA y monitor

Paquetes `ai/` y `monitor/`, selección documental, cola, providers, schemas, baselines, diferencias, leases, notificaciones y tests e2e.

### Trabajo local B

`portal_publication/`, `public_portal_server/`, `cloudflare/licitaciones_portal/`, `tender_documents/`, macros y scripts de Ficha, además de diffs del router y marcadores.

## Historia Git significativa

| Fecha | Hito |
| --- | --- |
| 10/06/2026 | Migración inicial al repositorio. |
| 11–12/06 | Retirada de monitor antiguo, hardening, CSRF, CSP, contratos, migraciones y storage. |
| 14–15/06 | Actuaciones, Agenda y decisión Dropbox Desktop primario. |
| 18–19/06 | Centro de automatizaciones/scheduler. |
| 29/06–03/07 | Gemini, cola IA, importador IMAP, acciones por correo, comentarios y descargas. |
| 08/07 | Orquestador interno y limpieza conceptual de tareas Windows. |
| 10–15/07 | Web pública, clientes, justificaciones y merge a main. |
| 20/07 | Monitor e2e completo. |
| 30/07 | Checkpoint/backup de rama auditada (`4877210`). |
| 10–21/08 | Ficha y portal aparecen como trabajo local/stash, no commits del HEAD. |
| 12/09 | Snapshot total PRE_AUDITORIA validado; auditoría operativa, contrato de sistema, health funcional, dashboard y cierre CSRF del portal. |

## Conversaciones accesibles revisadas

La interfaz devolvió 50 conversaciones/tareas recientes y ningún hilo Codex archivado. No ofrece búsqueda global paginada de todo el historial; por ello la exhaustividad conversacional se limita a lo accesible en esa vista y a referencias del repositorio.

- “Reconstruir documentación suite”: origen del encargo maestro actual.
- “Conectar Suite Con Trello”: comparación Trello/Noloco/ClickUp/Notion/Softr y portal propio; se interpretó como D, no decisión.
- “Auditar Y Programar Auditoría”: propuesta de auditoría determinista diaria/semanal; D.
- “Actualizar MD de fuentes”: reglas posteriores de entrega de Ficha en el proyecto documental; confirma necesidad de coherencia Excel/MD y controles estructurales, no una función web de la Suite.
- Conversaciones de otros proyectos (Guivitur, fichas de expedientes concretos, compras, etc.) se descartaron por falta de relación arquitectónica.

**⚠️ PENDIENTE DE VERIFICACIÓN:** conversaciones antiguas de Suite que no aparecen en la ventana reciente ni están citadas en el repositorio.

## Contradicciones y resolución

| Contradicción | Resolución |
| --- | --- |
| 891/1.313/1.443/1.453 tests frente a realidad | Conteo actual verificado: 1.452; ejecución limpia 1.452. |
| Monitor default desactivado vs informe “activo” | Override real: activo con 08:00/13:00/18:00. |
| Horas antiguas vs nuevas | Orquestador/monitor e2e: 08:00/13:00/18:00. |
| Agenda 06:00 vs 08:00 | Orquestador: 08:00 laborables. |
| Rol técnico vs roles reales | Solo `admin` y `nuria`. |
| Estados antiguos vs actuales | Siete estados de `licitacion_states.py`. |
| Dropbox API vs Desktop | Desktop/filesystem es primario; API incremental B. |
| Sidecar vs baseline | Baseline SQLite es autoridad tras 0036. |
| Justificaciones completas vs ocultas | Técnicamente completas, retiradas del producto: E. |
| Ficha 2.0.1 vs 2.1.0 | Código/macros/manifiesto: 2.1.0; doc antigua obsoleta. |
| Portal local+túnel vs D1/R2 | Ambas implementaciones B; decisión pendiente. |
| Portal “Cloudflare activo” vs evidencia | Código local existe, despliegue no verificado. |
| Errores masivos pytest | Causa ambiental: temporal global sin acceso; basetemp aislado pasa todo. |
| Heartbeat SQLite antiguo vs KeeperTick actual | `--tick` delega al orquestador único y no actualiza aquella fila; usar tarea Windows como evidencia primaria. |
| UI Agenda 06:00/reconciliación 60 min vs backend | Corregidos a los defaults canónicos 08:00/240 min. |
| POST de portal fuera de CSRF | Corregidos en el mapa central y cubiertos por regresión. |

## Validaciones ejecutadas

- Colección pytest: 1.452.
- Suite con temporal global: 974 pass/469 setup errors por `PermissionError` de Windows.
- Suite con `--basetemp` nuevo bajo `.codex_tmp`: 1.452 pass, 13 warnings pypdf, 106,65 s. Repetición mediante `scripts/run_tests.ps1`: 1.452 pass en 110,61 s, seguida de los checks JavaScript sin error.
- Sintaxis JS privada/login/pública: correcta.
- ESLint del proyecto Cloudflare: correcto.

La cifra anterior es la línea base del 04/09; la ejecución completa de cierre del 12/09 se registra en `01_ESTADO_ACTUAL_SUITE.md` e `INFORME_RECONSTRUCCION_DOCUMENTAL.md`.

No se realizó build/deploy remoto del portal ni prueba real de proveedores externos. Sí se consultaron tareas y datos operativos de forma agregada/solo lectura.

## Evidencia operativa del 12/09/2026

- Backup externo: `C:\LLANGON_BACKUPS\PRE_AUDITORIA_LLANGON_20260912_104722`.
- 47.899 archivos, 4.273.721.220 bytes y 2.461 hashes críticos.
- SQLite mediante API de backup, `integrity_check=ok`, migración 0036.
- `RESTORE_PRE_AUDITORIA.ps1 -ValidateOnly`: exit 0.
- Restauración crítica aislada: cero diferencias y hash SQLite coincidente.
- KeeperTick/WakeTick exportadas, habilitadas, último resultado correcto; sin tareas Llangon legacy.
- App en loopback 8787; monitor activo; suspensión nocturna desactivada.
- Integraciones activas/preparadas según configuración, sin conexiones de prueba.
- Incidencia reproducida por consulta: descarga 53 permanece `running` desde 21/07/2026.
