# Decisiones de producto y arquitectura

Este registro consolida decisiones vigentes. Las ADR históricas 001–056 siguen siendo evidencia, pero varias frases de fase quedaron superadas por implementaciones posteriores.

## D-001 — Evolución incremental, no reescritura

- **Problema:** monolito con lógica acumulada y riesgo de regresión.
- **Decisión:** conservar comportamiento, extraer contratos/helpers y ampliar pruebas antes de refactors peligrosos.
- **No queremos:** reescribir desde cero o cambiar varias fronteras a la vez.
- **Estado:** A.

## D-002 — SQLite sigue siendo la base privada

- **Decisión:** SQLite con migraciones versionadas y foreign keys; no migrar a un servidor de base de datos sin una necesidad demostrada.
- **Restricción:** copias coherentes con API SQLite y procesos coordinados.
- **Estado:** A.

## D-003 — Aplicación privada y superficies públicas separadas

- **Decisión:** SPA privada Python/SQLite en loopback; web corporativa Firebase independiente; portal de licitación con almacenamiento/API pública separados.
- **No queremos:** publicar 8787, compartir la SQLite o mezclar activos Firebase con la SPA privada.
- **Estado:** A para separación; B para portal.

## D-004 — Fuente canónica de descargadores

- **Decisión:** `herramientas_python/Descargar_Licitacion.py` y módulos asociados son la única implementación; BAT/bridges delegan.
- **Alternativa sustituida:** copias divergentes por entrada.
- **Estado:** A.

## D-005 — El resultado parcial no destruye verdad previa

- **Decisión:** solo inventarios completos confirman retiradas; parcial conserva baseline/estado y registra incidencia.
- **Aplica a:** descargadores, Q&A y monitor.
- **Estado:** A.

## D-006 — Seguimiento por marcador físico y baseline SQLite

- **Decisión:** `EnSeguimiento.llangon` es autoridad de pertenencia; SQLite es autoridad de baseline; sidecar solo diagnóstico.
- **No queremos:** un flag paralelo de seguimiento o baseline basada en árbol local.
- **Estado:** A.

## D-007 — Automatización central interna

- **Decisión:** orquestador SQLite ejecuta negocio; Windows solo keeper/wake.
- **Alternativa sustituida:** una tarea Windows por proceso/automatización.
- **Estado:** A en código; instalación real pendiente.

## D-008 — Revisión por estados y cierre explícito

- **Decisión:** siete estados canónicos; admin filtra, Nuria decide, cierre 99 autodescarta solo pendientes.
- **No queremos:** que ediciones ordinarias reabran el día ni que el correo retroceda estados avanzados.
- **Estado:** A.

## D-009 — IMAP seguro e idempotente

- **Decisión:** PEEK, persistir antes de marcar visto, claims y registro de incidencias.
- **No queremos:** perder un mensaje por marcarlo leído antes de confirmar persistencia.
- **Estado:** A.

## D-010 — IA asistencial, validada y desacoplada

- **Decisión:** cola persistente, proveedores Gemini/Codex Local seleccionables, documentos filtrados, JSON validado y revisión humana.
- **No queremos:** IA sobre Q&A, mutación de originales, recomendaciones inventadas o publicar una salida inválida.
- **Estado:** A.

## D-011 — Clientes: borrador humano, no envío automático

- **Decisión:** Suite prepara `.msg` o `.eml`; una persona revisa, envía y marca el estado.
- **No queremos:** SMTP/Outlook enviando al cliente sin confirmación.
- **Estado:** A.

## D-012 — Bajas reversibles de clientes

- **Decisión:** soft delete; impedir nuevas asignaciones y preservar histórico.
- **Estado:** A.

## D-013 — Ficha local desacoplada

- **Decisión:** Excel actualiza clientes solo bajo botón, lee SQLite en solo lectura, conserva caché ante error y genera PDF canónico por bridge.
- **No queremos:** consulta al abrir, escritura Excel→SQLite o sincronización silenciosa.
- **Estado:** B por no estar consolidada.

## D-014 — Justificaciones de baja fuera del producto visible

- **Decisión posterior:** desconectar la interfaz aunque el motor esté completo; conservar código por trazabilidad.
- **Alternativa descartada:** mantener el módulo como flujo operativo actual.
- **Estado:** E.

## D-015 — Noticias honestas y Markdown seguro

- **Decisión:** contenido seguro y sin noticias ficticias; ocultar navegación hasta disponer de contenido real.
- **Estado:** B, porque no existe publicación dinámica pública confirmada.

## D-016 — Portal por publicación, no acceso a la Suite

- **Decisión:** la Suite selecciona una Ficha y adjuntos; el cliente accede a una superficie separada con código individual y trazabilidad.
- **No queremos:** exponer notas internas, SQLite, carpeta completa o aplicación privada.
- **Estado:** B.
- **Sin resolver:** servidor local+túnel frente a D1/R2.

## D-017 — Cobertura literal en portal

- **Decisión:** toda página de Ficha debe visualizarse; IA solo estructura/enriquece, y el contenido no mapeado se conserva literalmente.
- **Estado:** B.

## D-018 — Portal externo general: todavía en estudio

- **Alternativas:** Trello, Noloco, ClickUp, Notion, Softr y portal propio general.
- **Conclusión conversacional:** prototipar antes de integrar; no hubo aprobación de proveedor.
- **Estado:** D.

## D-019 — Auditoría automática 360: propuesta

- **Propuesta:** chequeo determinista diario, interpretación, niveles y revisión semanal.
- **Decisión:** no consta aprobación ni implementación.
- **Estado:** D.

## D-020 — Cambios peligrosos requieren checkpoint y precheck

- **Decisión:** seguridad, SQLite, CSRF, almacenamiento, noticias y refactor se abordan con pruebas, checkpoint y reversibilidad.
- **Estado:** A como práctica del historial; debe mantenerse.

## D-021 — Salud mínima y diagnóstico funcional separados

- **Fecha:** 12/09/2026.
- **Decisión:** conservar `/api/health` mínimo para KeeperTick y añadir `/api/admin/operational-health` para contrato y excepciones.
- **Motivación:** el liveness debe ser rápido/estable; una dependencia opcional no debe declarar caída total.
- **Restricciones:** solo lectura, sin conexiones externas, sin secretos, niveles OK/DEGRADADO/ERROR.
- **Estado:** A.

## D-022 — Dashboard dentro de Automatizaciones

- **Fecha:** 12/09/2026.
- **Decisión:** reutilizar la consola administrativa y priorizar «¿Qué necesita atención ahora?».
- **No queremos:** estadísticas decorativas, duplicar fuentes ni mezclar incidencias técnicas con Agenda.
- **Estado:** A.

## D-023 — KeeperTick es la evidencia de vida del orquestador

- **Fecha:** 12/09/2026.
- **Contexto:** `monitor.scheduler --tick` delega al orquestador único y dejó de actualizar el heartbeat del scheduler anterior.
- **Decisión:** usar última ejecución/resultado de `LlangonSuite-KeeperTick`; mantener `monitor_scheduler_heartbeat` solo como fallback de compatibilidad.
- **Estado:** A.

## D-024 — No corregir silenciosamente trabajos vinculados a correo

- **Fecha:** 12/09/2026.
- **Decisión:** detectar el `download_job` huérfano y mostrarlo como incidencia; no cambiarlo automáticamente durante la auditoría porque su cierre puede producir estado terminal y aviso.
- **Pendiente:** diseñar recuperación explícita, idempotente y auditada.
- **Estado:** B.

## Decisiones que requieren ratificación

1. Arquitectura definitiva del portal público.
2. Si portal/Ficha/router local forman una única entrega y rama.
3. Tratamiento operativo de la descarga 53 atascada.
