# Despliegue local Windows

Este documento prepara Llangon Suite V2 para ejecutarse en un equipo Windows sin dejar una consola abierta.

La aplicación sigue siendo local: escucha por defecto en `http://127.0.0.1:8787`. La publicación por Internet con Cloudflare Tunnel queda para una fase posterior.

## Objetivo

- Arrancar la web privada al iniciar sesión en Windows.
- Ejecutar el scheduler de forma independiente y sin solapes.
- Crear una copia diaria segura de la base SQLite.
- Guardar logs en `runtime/logs/`.
- No abrir la aplicación a `0.0.0.0`.
- No guardar secretos ni rutas absolutas en código.

## Variables principales

Configurar en `webapp/infonalia_webapp/.env`:

```text
INFONALIA_HOST=127.0.0.1
INFONALIA_PORT=8787
LLANGON_DROPBOX_BASE_PATH=C:\Users\LLangon03\Dropbox\00000 LLANGON
```

Variables opcionales:

```text
LLANGON_RUNTIME_ROOT=
LLANGON_SQLITE_BACKUP_DIR=
LLANGON_SQLITE_BACKUP_RETENTION=30
MONITOR_SCHEDULER_POLL_MINUTES=5
```

Si `LLANGON_RUNTIME_ROOT` queda vacia, se usa:

```text
Llangon-SuiteV2\runtime
```

## Scripts disponibles

Todos estan en:

```text
scripts/windows/
```

| Script | Uso |
| --- | --- |
| `start_web_production.ps1` | Arranca la web local con logs. |
| `run_scheduler_once.ps1` | Ejecuta el scheduler una vez y termina. |
| `run_backup_once.ps1` | Crea una copia SQLite una vez y termina. |
| `install_local_deployment.ps1` | Registra las tareas programadas. |
| `status_local_deployment.ps1` | Comprueba tareas, logs y healthcheck. |
| `uninstall_local_deployment.ps1` | Quita las tareas programadas sin borrar datos. |
| `run_powershell_hidden.vbs` | Lanzador oculto usado por las tareas para evitar ventanas de consola. |

Los scripts calculan la ruta del proyecto desde su propia ubicacion. No dependen de una ruta fija tipo `C:\Users\...`.

Las tareas programadas se registran mediante `wscript.exe` + `run_powershell_hidden.vbs`. Ese lanzador ejecuta PowerShell con `-NonInteractive` y `-WindowStyle Hidden`, por lo que no debe aparecer ninguna ventana fugaz al iniciar sesion ni al ejecutarse scheduler o backup.

## Instalacion

Abrir PowerShell en la raiz del repositorio:

```powershell
cd C:\Users\LLangon03\Documents\Codex\Llangon-SuiteV2
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_local_deployment.ps1
```

Esto crea o actualiza estas tareas:

- `LlangonSuite-Web`: al iniciar sesion.
- `LlangonSuite-Scheduler`: cada pocos minutos, sin solapes.
- `LlangonSuite-Backup`: diariamente a las 03:30.

El instalador es idempotente: se puede ejecutar de nuevo para actualizar las tareas.

## Comprobacion

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\status_local_deployment.ps1
```

Healthcheck esperado:

```json
{"status": "ok"}
```

Este endpoint no devuelve usuarios, rutas, configuracion ni informacion sensible.

## Prueba manual de la web

Para probar el arranque sin instalar nada mas:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_web_production.ps1
```

Este script ejecuta el servidor Python en primer plano. El propio servidor verifica `/api/health` tras arrancar y escribe el resultado en `runtime/logs/web.log`. Si se ejecuta en una ventana manual, esa ventana queda ocupada mientras la web siga levantada.

En otra ventana:

```powershell
Invoke-WebRequest http://127.0.0.1:8787/api/health -UseBasicParsing
netstat -ano | findstr :8787
powershell -ExecutionPolicy Bypass -File .\scripts\windows\status_local_deployment.ps1
```

Debe verse:

```text
Healthcheck web: OK
TCP 127.0.0.1:8787 ... LISTENING
```

Para detener una prueba manual, cerrar la ventana donde esta corriendo `start_web_production.ps1` o detener el PID que muestre `status_local_deployment.ps1`.

## Logs

Por defecto:

```text
runtime/logs/web.log
runtime/logs/web.stdout.log
runtime/logs/web.stderr.log
runtime/logs/scheduler.log
runtime/logs/backup.log
```

`web.log` contiene el arranque, healthcheck posterior, PID y codigo de salida del proceso. El servidor web tambien usa rotacion interna de log para evitar crecimiento indefinido.

## Copias SQLite

El modulo de backup se ejecuta con:

```powershell
python -m webapp.infonalia_webapp.backup_sqlite
```

La copia usa la API `sqlite3.Connection.backup()`, por lo que es mas segura que copiar el archivo manualmente si la app esta abierta.

Destino por defecto:

```text
runtime/backups/sqlite/
```

Retencion por defecto:

```text
30 copias
```

## Scheduler

La tarea programada llama a:

```powershell
python -m webapp.infonalia_webapp.monitor.scheduler --once
```

Cada ejecucion termina. El propio script `run_scheduler_once.ps1` usa un bloqueo local para evitar solapes si una ejecucion anterior sigue activa.

En esa misma pasada se ejecutan tambien las tareas de correo si estan activadas en `.env`:

```text
LLANGON_INFONALIA_IMPORT_ENABLED=1
LLANGON_INFONALIA_IMPORT_POLL_MINUTES=30
LLANGON_EMAIL_ACTIONS_ENABLED=1
LLANGON_EMAIL_ACTIONS_POLL_MINUTES=10
```

Ambas usan la configuracion IMAP `LLANGON_ACTIONS_IMAP_*`. El importador de Infonalia filtra por remitente/asunto exactos y las ordenes tecnicas solo aceptan asuntos que empiezan por `LLANGON_CMD`.

El diagnostico local muestra tambien el estado de esos dos trabajos:

```powershell
python -m webapp.infonalia_webapp.monitor.scheduler --status
```

## Desinstalacion

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\uninstall_local_deployment.ps1
```

Esto solo elimina las tareas programadas. No borra:

- base de datos;
- descargas;
- logs;
- backups;
- configuracion `.env`.

## Cloudflare Tunnel, fase posterior

Cuando la app privada este validada en local, el tunnel debe apuntar a:

```text
http://127.0.0.1:8787
```

No cambiar `INFONALIA_HOST` a `0.0.0.0`.

No guardar tokens de Cloudflare en Git. La configuracion del tunnel y sus credenciales deben quedar fuera del repositorio.

## Comandos de validacion

```powershell
python -m pytest -q
node --check webapp/infonalia_webapp/static/app.js
python -m webapp.infonalia_webapp.monitor.scheduler --dry-run
python -m webapp.infonalia_webapp.backup_sqlite --dry-run
```

Para validar sintaxis PowerShell sin instalar tareas:

```powershell
$files = Get-ChildItem .\scripts\windows\*.ps1
foreach ($file in $files) {
    [scriptblock]::Create((Get-Content -Raw -LiteralPath $file.FullName)) | Out-Null
}
```
