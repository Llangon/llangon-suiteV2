# CODEX_CONTEXT

## Que es Llangon Suite V2

`Llangon-SuiteV2` es el monorepo privado de la suite de trabajo de Llangon alrededor de Infonalia, la revision de licitaciones, la operacion documental, automatizaciones auxiliares y la web publica.

## Que no es

- No es un proyecto publico listo para Internet.
- No es solo la web publica.
- No es un entorno para ejecutar procesos reales por defecto.
- No es un repositorio de datos ni de secretos.

## Mapa tecnico del repo

- `webapp/infonalia_webapp`: app privada Python/SQLite
- `firebase/public_firebase`: web publica estatica
- `herramientas_python`: descargadores por plataforma
- `scripts/` y `scripts/windows/`: operacion local y automatizacion Windows
- `macros/`: macros VBA
- `docs/`: documentacion vigente
- `docs/documentacion_maestra/`: fuente documental maestra; empezar por `00_INDICE_MAESTRO.md`
- `documentos_contexto/`: antecedentes historicos

## Estado actual relevante

- `webapp/infonalia_webapp/app.py` sigue siendo el punto central grande de la app privada.
- Existen submodulos relevantes como `ai/`, `agenda/`, `monitor/`, `storage/` y `services/`.
- La web publica y la app privada deben mantenerse separadas.
- Los tests estan centralizados en `webapp/infonalia_webapp/tests`.
- La auditoría integral del 12/09/2026 recoge y supera 1.452 pruebas, incluidas las regresiones del contrato, healthcheck funcional y dashboard. Consultar la evidencia fechada en `docs/documentacion_maestra/01_ESTADO_ACTUAL_SUITE.md`.
- Los descargadores usan una sola fuente de verdad en `herramientas_python`; los BAT y el puente legado delegan en el mismo lanzador central.
- La base real está migrada hasta `0036_tender_monitor_baseline_ownership`; el contrato automático vive en `system_contract.py`.
- El monitor de licitaciones está activado en las franjas 08:00, 13:00 y 18:00. `night_suspend` está desactivada expresamente.
- Las tareas Windows vigentes y habilitadas son `LlangonSuite-KeeperTick` y `LlangonSuite-WakeTick`; no se detectaron tareas Llangon legacy.

## Como se ejecuta el proyecto hoy

- Arranque manual de la app privada desde la raíz con `python -m webapp.infonalia_webapp.serve`.
- Arranque operativo preferido de la app privada con `scripts/windows/start_web_production.ps1`.
- Healthcheck de la app privada en `http://127.0.0.1:8787/api/health`.
- Diagnóstico funcional administrativo en `/api/admin/operational-health`; es de solo lectura y no conecta con servicios externos.
- Vista previa publica con `scripts/windows/start_public_web_preview.ps1`.

## Zonas sensibles

- secretos
- `.env`
- SQLite real
- datos locales
- Dropbox real
- correo
- Telegram
- backups
- logs
- tareas Windows
- automatizaciones con efectos reales

## Riesgos actuales

- `app.py` es grande y sigue concentrando mucha responsabilidad.
- Hay documentacion historica con cifras antiguas o contexto ya superado.
- Hay mezcla de convenciones antiguas de entorno virtual y arranque.
- Existen temporales de pytest que generan ruido y errores de acceso si se buscan indiscriminadamente.
- Existe una descarga histórica atascada en `running`; el dashboard operativo la muestra sin alterar producción automáticamente.
- El árbol local contiene trabajo amplio sin commit sobre portal público, Ficha Llangon y navegación; preservar esos cambios.

## Reglas operativas para Codex

- No usar como fuente principal los documentos de `documentos_contexto/`, `PROJECT_CONTEXT.md` ni contextos antiguos.
- Usar `docs/documentacion_maestra/00_INDICE_MAESTRO.md` y `CONTEXTO_MAESTRO_LLANGON_SUITE.md` como entradas canónicas.
- No inferir que todos los scripts antiguos siguen siendo la via preferida.
- Confirmar siempre si una accion sale del modo seguro o de solo lectura.
- Priorizar `docs/CHECKPOINTS_PELIGROSOS.md` y `docs/PRECHECK_*` cuando el cambio afecte zonas de riesgo.
- Mantener separadas la app privada, la web publica y cualquier automatizacion con efectos reales.

## Documentos relacionados

- `docs/documentacion_maestra/00_INDICE_MAESTRO.md`: índice y jerarquía canónicos
- `docs/documentacion_maestra/CONTEXTO_MAESTRO_LLANGON_SUITE.md`: contexto compacto para IA
- `docs/documentacion_maestra/14_CONTRATO_SALUD_Y_OBSERVABILIDAD.md`: contrato y diagnóstico funcional
- `README.md` y `PROJECT_CONTEXT.md`: contexto histórico; no prevalecen sobre la documentación maestra
- `docs/DESPLIEGUE_LOCAL_WINDOWS.md`: operacion local Windows
- `docs/DECISIONES_TECNICAS.md`: decisiones acumuladas
- `docs/ARQUITECTURA_FUTURA.md`: arquitectura y fases previas
- `docs/DESCARGADORES_LICITACIONES.md`: arquitectura operativa, diagnóstico y mantenimiento de descargadores
