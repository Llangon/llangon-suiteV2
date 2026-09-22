# Descartado, sustituido e histórico

## E — Retirado o sustituido

| Elemento | Situación | Sustitución vigente |
| --- | --- | --- |
| Justificaciones de baja en navegación | Retirado por decisión de producto; código dormante. | Ningún módulo visible. |
| Estados antiguos (`Pendiente`, `Pendiente Nuria`, `Descartada por mí`, etc.) | Normalizados/migrados. | Siete estados canónicos. |
| Rol “técnico” como rol de app | Documentación antigua incorrecta. | `admin` y `nuria`. |
| Tarea Windows por automatización | Arquitectura legacy. | KeeperTick + WakeTick + orquestador interno. |
| Horarios monitor 07:00/12:30/17:30 | Constantes/documentos legacy. | 08:00/13:00/18:00. |
| Agenda diaria 06:00 | Referencia legacy. | 08:00 laborables. |
| Copia pública dentro de la app privada | Eliminada en julio. | `firebase/public_firebase`. |
| Rediseño público multipágina del 24/06 | Revertido el mismo día. | SPA estática posterior. |
| Noticias ficticias y zona privada no operativa en navegación | Retiradas. | Estados vacíos/contacto honestos. |
| Sidecar como autoridad de monitor | Superado por migración 0036. | Baseline SQLite; sidecar diagnóstico. |
| Flag SQL paralelo para seguimiento | Rechazado. | Marcador físico. |
| Envío automático a clientes | Expresamente no deseado. | Borrador + confirmación humana. |
| Actualización de clientes al abrir Excel | Expresamente no deseada. | Botón manual + caché. |

## D — Ideas estudiadas, no vigentes

- Trello como coordinación con clientes.
- Noloco, ClickUp, Notion y Softr como portal externo.
- Portal cliente general con login, comentarios bidireccionales y estadísticas.
- Auditoría 360 diaria y revisión profunda semanal.
- Dropbox API como backend operativo principal.
- Cloudflare Access/túnel para la propia app privada.
- Preguntas/respuestas en Navarra y demás plataformas sin implementación.
- Sincronización Ficha Excel→Suite.

No deben aparecer como capacidades ni compromisos del roadmap sin una decisión nueva.

## Documentación histórica o superada

| Fuente | Clasificación recomendada |
| --- | --- |
| `documentos_contexto/PROYECTO_INFONALIA.md` | Contexto previo a la migración. |
| `documentos_contexto/MIGRACION_A_LLANGONWEBAPP.md` | Plan/registro histórico. |
| `MIGRACION_LOG.md`, `INVENTARIO_MIGRACION.md`, `SANEAMIENTO_REPOSITORIO.md` | Evidencia histórica de migración y saneamiento. |
| `docs/ARQUITECTURA_FUTURA.md` | Diario de fases ya ejecutadas; no arquitectura futura vigente. |
| `docs/DECISIONES_TECNICAS.md` | ADR acumuladas hasta la etapa de descargadores; mantener como evidencia. |
| `docs/ROLES_Y_FLUJO.md` | Obsoleto: roles y estados antiguos. |
| `PROJECT_CONTEXT.md` | Snapshot antiguo; no usar sin contraste. |
| `docs/CODEX_CONTEXT.md` | Contexto útil pero con cifras/estado desactualizables; la jerarquía de AGENTS aún lo prioriza. |
| `docs/FICHA_LLANGON_V2.md` | Parcialmente obsoleto: declara 2.0.1 frente a 2.1.0 técnica. |
| `docs/WEB_PUBLICA_CAMBIOS.md` | Describe una versión expresamente revertida. |
| `MONITOR_IMPLEMENTATION_STATUS.md` | Informe operacional de julio, no estado vivo. |

## Política de archivo

No se ha borrado ni movido ningún documento. El siguiente paso seguro es retirar estas fuentes del conjunto activo del proyecto ChatGPT y conservarlas en histórico con fecha. Moverlas o cambiar `README.md`, `PROJECT_CONTEXT.md` o documentación histórica requiere autorización conforme a `AGENTS.md`.

