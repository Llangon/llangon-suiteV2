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
LLANGON_AGENDA_WAKE_ENABLED=0
LLANGON_AGENDA_WAKE_TIME=06:00
LLANGON_AGENDA_WAKE_AUTO_SLEEP=1
LLANGON_AGENDA_WAKE_SKIP_SLEEP_IF_USER_ACTIVE=1
LLANGON_AGENDA_WAKE_MIN_IDLE_SECONDS=120
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
| `run_agenda_wake_once.ps1` | Ejecuta la Agenda programada y suspende si es seguro. |
| `suspend_windows.ps1` | Solicita suspension normal de Windows con comprobacion de usuario activo. |
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
- `LlangonSuite-AgendaWake`: laborables a las 06:00, con despertar del equipo activado.

El instalador es idempotente: se puede ejecutar de nuevo para actualizar las tareas.

`LlangonSuite-AgendaWake` queda instalada pero desactivada por defecto si `LLANGON_AGENDA_WAKE_ENABLED` no vale `1`. Esto evita que un equipo empiece a despertar y suspenderse sin activacion consciente.

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

En esa misma pasada se ejecutan tambien las tareas de correo e inventario si estan activadas en `.env`:

```text
LLANGON_INFONALIA_IMPORT_ENABLED=1
LLANGON_INFONALIA_IMPORT_POLL_MINUTES=30
LLANGON_EMAIL_ACTIONS_ENABLED=1
LLANGON_EMAIL_ACTIONS_POLL_MINUTES=10
LLANGON_FILE_INVENTORY_ENABLED=1
LLANGON_FILE_INVENTORY_POLL_MINUTES=60
LLANGON_DROPBOX_BASE_PATH=C:\Users\LLangon03\Dropbox\00000 LLANGON
```

Las tareas de correo usan la configuracion IMAP `LLANGON_ACTIONS_IMAP_*`. El importador de Infonalia lee la etiqueta IMAP `LLANGON_INFONALIA`, busca solo no leidos con `UID SEARCH UNSEEN` y decide la importacion por la estructura parseada del cuerpo. No envia remitente, asunto, acentos ni `SINCE` a `IMAP SEARCH`. Para completar tipo de contrato y hora limite reutiliza el enriquecimiento PDF de la importacion manual; si no encuentra `pdftotext.exe`, revisar `INFONALIA_PDFTOTEXT`. Las ordenes tecnicas solo aceptan asuntos que empiezan por `LLANGON_CMD`.

El inventario usa `LLANGON_DROPBOX_BASE_PATH` como raiz principal. `INFONALIA_DROPBOX_ROOT` queda como fallback historico si la variable principal no esta configurada. Si la ruta no existe, el scheduler registra el error de inventario y continua con el resto de trabajos.

Las descargas locales deben crear carpetas bajo `LLANGON_DROPBOX_BASE_PATH\AÑO\MES\CARPETA_EXPEDIENTE`, por ejemplo `C:\Users\LLangon03\Dropbox\00000 LLANGON\2026\07 JULIO\20 JULIO 1400 ...`. En base de datos se guarda solo la parte relativa `2026\07 JULIO\...`. Las rutas antiguas sin año se conservan como compatibilidad de lectura si ya existen, pero las carpetas nuevas no deben crearse directamente bajo `LLANGON_DROPBOX_BASE_PATH\MES`.

El diagnostico local muestra tambien el estado de esos trabajos:

```powershell
python -m webapp.infonalia_webapp.monitor.scheduler --status
```

## Agenda Wake

`LlangonSuite-AgendaWake` es una tarea programada independiente del scheduler general. Su objetivo es despertar Windows a las 06:00, ejecutar la tarea de negocio existente `agenda_pendientes_diaria` y volver a suspender el equipo solo si termina correctamente y no hay usuario activo.

La tarea real de Agenda detectada en la suite es:

```text
agenda_pendientes_diaria
```

La agenda semanal existe como compatibilidad historica, pero esta marcada como inactiva/manual. Por eso la tarea Windows de despertar se aplica a `agenda_pendientes_diaria`.

Importante: `LlangonSuite-Scheduler` no suspende el equipo tras sus pasadas normales de cada pocos minutos. La suspension pertenece solo a `LlangonSuite-AgendaWake`.

Para activar Agenda Wake, configurar en `webapp/infonalia_webapp/.env` o en variables del proceso antes de instalar:

```text
LLANGON_AGENDA_WAKE_ENABLED=1
LLANGON_AGENDA_WAKE_TIME=06:00
LLANGON_AGENDA_WAKE_AUTO_SLEEP=1
LLANGON_AGENDA_WAKE_SKIP_SLEEP_IF_USER_ACTIVE=1
LLANGON_AGENDA_WAKE_MIN_IDLE_SECONDS=120
```

Despues, reinstalar tareas:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_local_deployment.ps1
```

La tarea queda configurada con `WakeToRun`, equivalente a "Activar el equipo para ejecutar esta tarea". Windows solo despertara si la BIOS/UEFI, energia y permisos de Windows permiten temporizadores de activacion.

El script `run_agenda_wake_once.ps1` fuerza esa pasada a usar solo Agenda pendiente:

```text
MONITOR_AGENDA_PENDING_DAILY_ENABLED=1
LLANGON_INFONALIA_IMPORT_ENABLED=0
LLANGON_EMAIL_ACTIONS_ENABLED=0
LLANGON_FILE_INVENTORY_ENABLED=0
MONITOR_LICITACIONES_SCHEDULE_ENABLED=0
```

Asi no se mezclan importador Infonalia, procesamiento de correo, inventario ni monitor de licitaciones con esta tarea especial.

Si Agenda falla, se registra el error y no se suspende el equipo. Si Agenda termina correctamente, espera unos segundos y llama a `suspend_windows.ps1`.

La suspension usa PowerShell/C# con `powrprof.dll` y `SetSuspendState(false, false, false)`, que solicita suspension normal, no apagado, reinicio ni hibernacion. Antes de suspender, si `LLANGON_AGENDA_WAKE_SKIP_SLEEP_IF_USER_ACTIVE=1`, comprueba inactividad de teclado/raton mediante `GetLastInputInfo`. Si el usuario esta activo o no se puede comprobar de forma segura, escribe:

```text
Suspension omitida: usuario activo.
```

o el motivo equivalente en:

```text
runtime/logs/agenda_wake.log
```

Comprobar estado:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\status_local_deployment.ps1
```

Debe mostrar:

```text
LlangonSuite-AgendaWake
Wake enabled
Auto suspension
runtime/logs/agenda_wake.log
```

Si Windows no despierta:

- revisar que `LLANGON_AGENDA_WAKE_ENABLED=1` y se ha reinstalado la tarea;
- revisar en Programador de tareas que `LlangonSuite-AgendaWake` no esta deshabilitada;
- revisar que la tarea tiene `WakeToRun`;
- revisar Opciones de energia > Permitir temporizadores de activacion;
- revisar si el equipo estaba hibernado o apagado, no suspendido.

Si no vuelve a suspension:

- revisar `runtime/logs/agenda_wake.log`;
- comprobar si Agenda fallo;
- comprobar si el log indica usuario activo;
- revisar `LLANGON_AGENDA_WAKE_AUTO_SLEEP`;
- revisar `LLANGON_AGENDA_WAKE_MIN_IDLE_SECONDS`.

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
