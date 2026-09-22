# COMANDOS_DESARROLLO

## Convencion recomendada de entorno

- Usa `.venv` en la raiz del repo.
- Ejecuta los comandos desde la raiz del repo salvo que el propio comando indique otra cosa.
- Si un documento antiguo usa otra convencion, tratalo como historico salvo que un script actual la requiera.

## Arranque manual de la app privada

```powershell
.\.venv\Scripts\python.exe -m webapp.infonalia_webapp.serve
```

No usar `python app.py`: los subpaquetes internos requieren el arranque como paquete. El script operativo indicado a continuación usa esta misma vía.

## Arranque operativo con scripts Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_web_production.ps1
```

## Healthcheck de la app privada

```powershell
Invoke-WebRequest http://127.0.0.1:8787/api/health -UseBasicParsing
```

El endpoint anterior solo confirma que el proceso web responde. La auditoría funcional local, sin conexiones externas, se ejecuta con:

```powershell
.\.venv\Scripts\python.exe -m webapp.infonalia_webapp.operational_health
```

El dashboard autenticado incorpora además el estado de tareas Windows mediante `GET /api/admin/operational-health`.

## Vista previa de la web publica

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_public_web_preview.ps1
```

## Tests backend

```powershell
.\.venv\Scripts\python.exe -m pytest --collect-only -q
.\.venv\Scripts\python.exe -m pytest -q --basetemp .codex_tmp\pytest-suite
```

## Checks JavaScript

```powershell
node --check webapp/infonalia_webapp/static/app.js
node --check webapp/infonalia_webapp/static/login.js
node --check firebase/public_firebase/static/public.js
```

## Script combinado de tests

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1
```

## Checks de mantenimiento sin efectos reales

```powershell
python -m compileall webapp herramientas_python
python -m webapp.infonalia_webapp.monitor.scheduler --status
python -m webapp.infonalia_webapp.monitor.scheduler --dry-run
python -m webapp.infonalia_webapp.automation_orchestrator --status
python -m webapp.infonalia_webapp.backup_sqlite --dry-run
.\.venv\Scripts\python.exe -m webapp.infonalia_webapp.operational_health
```

## Tests de descargadores sin efectos reales

Estas pruebas usan dobles y fixtures; no descargan documentos ni acceden a plataformas externas:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  webapp\infonalia_webapp\tests\test_catalunya_downloader.py `
  webapp\infonalia_webapp\tests\test_download_launcher.py `
  webapp\infonalia_webapp\tests\test_legacy_download_launcher_bridge.py `
  webapp\infonalia_webapp\tests\test_storage_paths.py
```

La arquitectura y el diagnóstico están documentados en `docs/DESCARGADORES_LICITACIONES.md`.

## Comandos no automaticos salvo peticion explicita

- `python -m webapp.infonalia_webapp.infonalia_mail_importer --once`
- `python -m webapp.infonalia_webapp.email_actions_processor --once`
- Descargas reales de licitaciones
- Backups completos reales
- Instalacion, modificacion o borrado de tareas Windows
- Envios reales de correo
- Acciones reales de Telegram
- Acciones reales sobre Dropbox

## Nota operativa

Si un comando toca IMAP, SMTP, Telegram, Dropbox, scheduler real, backups reales o descargadores, no debe ejecutarse por defecto en un thread de Codex.
