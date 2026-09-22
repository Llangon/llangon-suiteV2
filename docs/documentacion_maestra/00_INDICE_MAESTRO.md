# Índice maestro de Llangon Suite V2

**Corte documental:** 12 de septiembre de 2026  
**Ámbito:** repositorio y árbol local, historial Git, documentación, pruebas, SQLite real inspeccionada en modo lectura, procesos, tareas Windows y configuración no secreta.  
**Estado:** base documental maestra reconstruida y contrastada con la operación local.

## Qué es la Suite

Llangon Suite V2 es el sistema interno de trabajo de Asesores Llangon para recibir, revisar, descargar, analizar y seguir licitaciones; gestionar agenda, actuaciones, clientes y envíos; y operar automatizaciones controladas. La aplicación privada es una SPA servida por un backend Python con SQLite. La web corporativa pública y los portales públicos de licitación son superficies separadas.

## Cómo leer esta documentación

1. `01_ESTADO_ACTUAL_SUITE.md`: fotografía ejecutiva y matriz A–E.
2. `02_ARQUITECTURA_TECNICA.md`: componentes y comunicaciones reales.
3. `03_BASE_DE_DATOS_Y_MODELO_DE_DATOS.md`: persistencia, entidades y estados.
4. `04_MODULOS_Y_FLUJOS_FUNCIONALES.md`: comportamiento funcional completo.
5. `08_REGLAS_DE_NEGOCIO_Y_OPERACION.md`: reglas pequeñas que no deben perderse.
6. `07_SEGURIDAD_Y_DESPLIEGUE.md` y `06_AUTOMATIZACIONES_Y_TAREAS_PROGRAMADAS.md`: operación segura.
7. `09_DECISIONES_DE_PRODUCTO_Y_ARQUITECTURA.md`: decisiones vigentes y sustituciones.
8. `10_ROADMAP_VIGENTE.md`: únicamente trabajo actual no cerrado.
9. `99_TRAZABILIDAD_Y_FUENTES.md`: evidencia y límites de la auditoría.

## Índice

| Documento | Uso principal |
| --- | --- |
| `00_INDICE_MAESTRO.md` | Entrada, jerarquía y mapa documental. |
| `01_ESTADO_ACTUAL_SUITE.md` | Estado real por módulo e incertidumbres operativas. |
| `02_ARQUITECTURA_TECNICA.md` | Arquitectura, procesos, rutas, APIs y superficies. |
| `03_BASE_DE_DATOS_Y_MODELO_DE_DATOS.md` | SQLite, migraciones, tablas, entidades y estados. |
| `04_MODULOS_Y_FLUJOS_FUNCIONALES.md` | Flujos funcionales de extremo a extremo. |
| `05_INTEGRACIONES.md` | Dropbox, correo, Outlook, Telegram, IA, Cloudflare y plataformas. |
| `06_AUTOMATIZACIONES_Y_TAREAS_PROGRAMADAS.md` | Orquestador, horarios, tareas Windows y fallos. |
| `07_SEGURIDAD_Y_DESPLIEGUE.md` | Controles, despliegue, copias y riesgos. |
| `08_REGLAS_DE_NEGOCIO_Y_OPERACION.md` | Reglas operativas normativas. |
| `09_DECISIONES_DE_PRODUCTO_Y_ARQUITECTURA.md` | Registro consolidado de decisiones. |
| `10_ROADMAP_VIGENTE.md` | Pendientes actuales priorizados. |
| `11_DESCARTADO_SUSTITUIDO_E_HISTORICO.md` | Soluciones retiradas, dormantes o superadas. |
| `12_GLOSARIO.md` | Vocabulario canónico. |
| `13_CHECKLIST_AUDITORIA_SUITE.md` | Método repetible para futuras auditorías. |
| `14_CONTRATO_SALUD_Y_OBSERVABILIDAD.md` | Contrato automático, healthchecks, niveles y panel operativo. |
| `99_TRAZABILIDAD_Y_FUENTES.md` | Fuentes revisadas, precedencia y trazabilidad. |
| `INFORME_RECONSTRUCCION_DOCUMENTAL.md` | Resultado, contradicciones y control de calidad. |
| `CONTEXTO_MAESTRO_LLANGON_SUITE.md` | Contexto compacto para incorporar a un proyecto ChatGPT. |

## Clasificación obligatoria

- **A — Implantado:** existe en código consolidado y está cubierto por pruebas. No implica que el servicio externo esté configurado o ejecutándose hoy.
- **B — Implantado parcialmente:** hay código real, pero está incompleto, desactivado, sin consolidar, pendiente de despliegue o de verificación operativa.
- **C — Aprobado / pendiente:** consta una decisión vigente, pero falta implementación suficiente.
- **D — Propuesta / en estudio:** idea no aprobada o comparación de alternativas.
- **E — Descartado / sustituido:** retirado, dormante por decisión de producto o superado.

## Jerarquía de verdad

Para instrucciones de trabajo rige literalmente la precedencia de `AGENTS.md`:

1. `AGENTS.md`.
2. `docs/CODEX_CONTEXT.md`.
3. `docs/COMANDOS_DESARROLLO.md`.
4. Documentación existente del repositorio, comenzando por este índice.

Para describir hechos técnicos, el código, migraciones, pruebas y estado operativo verificable prevalecen sobre una narración antigua. `CODEX_CONTEXT.md` remite a esta base y debe actualizarse junto con ella.

Una afirmación sobre producción exige evidencia operativa; el mero código no la demuestra. Las dudas se señalan literalmente con **⚠️ PENDIENTE DE VERIFICACIÓN**.

## Reglas de mantenimiento

- Actualizar primero el documento temático y después el contexto compacto.
- Registrar cambios de decisión en `09_...`; no reescribir la historia como si nunca hubiera existido.
- Mover una iniciativa entre A–E únicamente con evidencia.
- No copiar secretos, rutas de datos reales ni contenido de bases de producción.
- No mezclar la aplicación privada, la web corporativa Firebase y el portal público de licitaciones.
- No usar cifras antiguas de pruebas: consultar la ejecución fechada en `01_ESTADO_ACTUAL_SUITE.md`.
- Mantener `/api/health` mínimo para KeeperTick y usar `/api/admin/operational-health` para diagnóstico funcional.
