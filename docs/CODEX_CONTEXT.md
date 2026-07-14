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
- `documentos_contexto/`: antecedentes historicos

## Estado actual relevante

- `webapp/infonalia_webapp/app.py` sigue siendo el punto central grande de la app privada.
- Existen submodulos relevantes como `ai/`, `agenda/`, `monitor/`, `storage/` y `services/`.
- La web publica y la app privada deben mantenerse separadas.
- Los tests estan centralizados en `webapp/infonalia_webapp/tests`.
- Hoy pasan `891` tests con `.\.venv\Scripts\python.exe -m pytest -q`.
- Los descargadores usan una sola fuente de verdad en `herramientas_python`; los BAT y el puente legado delegan en el mismo lanzador central.

## Como se ejecuta el proyecto hoy

- Arranque manual de la app privada desde `webapp/infonalia_webapp` con `python app.py`.
- Arranque operativo preferido de la app privada con `scripts/windows/start_web_production.ps1`.
- Healthcheck de la app privada en `http://127.0.0.1:8787/api/health`.
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
- La rama `main` esta `ahead 2` sobre `origin/main`.

## Reglas operativas para Codex

- No usar como fuente principal los documentos de `documentos_contexto/`.
- No inferir que todos los scripts antiguos siguen siendo la via preferida.
- Confirmar siempre si una accion sale del modo seguro o de solo lectura.
- Priorizar `docs/CHECKPOINTS_PELIGROSOS.md` y `docs/PRECHECK_*` cuando el cambio afecte zonas de riesgo.
- Mantener separadas la app privada, la web publica y cualquier automatizacion con efectos reales.

## Documentos relacionados

- `README.md`: entrada general del repo
- `PROJECT_CONTEXT.md`: contexto general del proyecto
- `docs/DESPLIEGUE_LOCAL_WINDOWS.md`: operacion local Windows
- `docs/DECISIONES_TECNICAS.md`: decisiones acumuladas
- `docs/ARQUITECTURA_FUTURA.md`: arquitectura y fases previas
- `docs/DESCARGADORES_LICITACIONES.md`: arquitectura operativa, diagnóstico y mantenimiento de descargadores
