# Roadmap vigente

Este documento no conserva ideas antiguas. Solo recoge trabajo que deriva de código actual, riesgos verificables o una decisión vigente. Ningún punto autoriza por sí mismo acciones sobre producción.

## P0 — Cerrar el árbol local antes de desplegar

1. Crear checkpoint/commit claro para router, marcadores, Ficha y portal, separando entregas si corresponde.
2. Migrar `portal_publications` y `portal_events` a una migración numerada posterior a 0036.
3. Decidir y eliminar la ambigüedad entre `public_portal_server` y Cloudflare D1/R2.
4. Repetir la batería completa, JavaScript y validación del portal tras esa decisión.

Completado en la auditoría: rutas POST del portal incorporadas al control CSRF con regresión.

## P1 — Consolidar Ficha Llangon

1. Alinear documento, plantilla, macros y manifiesto en versión 2.1.0/payload 1.1/bridge 1.4.0.
2. Determinar qué artefactos y scripts son fuente y cuáles son salidas históricas.
3. Verificar aceptación real en Excel/Windows sin cambiar la regla de solo lectura.
4. Versionar la herramienta y su manual como una unidad.

## P1 — Incidencia operativa pendiente

1. Revisar conscientemente la descarga 53, vinculada a la licitación 372 y a una orden de correo, que permanece `running` desde el 21/07/2026. Decidir si se marca fallida y se reintenta; no corregirla silenciosamente porque puede generar un aviso terminal.
2. Confirmar despliegue Firebase y, si existe, portal/túnel/dominio sin cambiar estado remoto.

Ya verificado: tareas Windows, activación del monitor, backups, configuración local de integraciones, hashes de usuarios y simulacro aislado de restauración.

## P2 — Deuda técnica

1. Reducir `app.py` mediante extracciones pequeñas protegidas por pruebas.
2. Sustituir el uso de `pypdf.PageObject.replace_contents()` antes de pypdf 7.
3. Considerar persistir/distribuir el rate limit solo si cambia el modelo de despliegue.
4. Normalizar rutas legacy del monitor sin retirar compatibilidad prematuramente.
5. Añadir una recuperación explícita y auditada para `download_jobs` huérfanos, equivalente a la existente en IA/monitor.

## P2 — Gobernanza documental

1. Ratificar esta carpeta como fuente activa.
2. Mantener `docs/CODEX_CONTEXT.md` como puente hacia la documentación maestra sin alterar la jerarquía fijada por `AGENTS.md`.
3. Clasificar los MD antiguos como histórico/específico; no borrarlos.
4. Ejecutar `13_CHECKLIST_AUDITORIA_SUITE.md` en cada entrega mayor.

## Fuera del roadmap hasta nueva decisión

- Integración con Trello, Noloco, ClickUp, Notion o Softr.
- Portal cliente general bidireccional.
- Auditoría automática diaria 360.
- Excel→SQLite o sincronización bidireccional de Ficha.
- Preguntas/respuestas para las cinco plataformas que no las implementan.
- Módulos autónomos de adjudicación o facturación.
- Reactivación de justificaciones de baja.
