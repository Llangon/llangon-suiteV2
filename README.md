# Llangon Suite V2

Monorepo privado y limpio para las herramientas de Llangón relacionadas con Infonalia, seguimiento de licitaciones, descargadores por plataforma, web pública y automatizaciones auxiliares.

## Contenido

```text
Llangon-SuiteV2/
├─ README.md
├─ PROJECT_CONTEXT.md
├─ INVENTARIO_MIGRACION.md
├─ MIGRACION_LOG.md
├─ SANEAMIENTO_REPOSITORIO.md
├─ firebase.json
├─ webapp/infonalia_webapp/
├─ firebase/public_firebase/
├─ herramientas_python/
├─ macros/
├─ docs/
└─ documentos_contexto/
```

- `webapp/infonalia_webapp/`: aplicación privada Python, frontend y plantilla de configuración.
- `firebase/public_firebase/`: web pública estática para Firebase Hosting.
- `firebase.json`: configuración de Firebase Hosting; publica únicamente `firebase/public_firebase`.
- `herramientas_python/`: descargadores y utilidades auxiliares. No deben ejecutarse sin una prueba controlada.
- `macros/`: módulos VBA de apoyo.
- `docs/`: documentación operativa vigente.
- `documentos_contexto/`: antecedentes históricos claramente marcados.

Documentación operativa destacada:

- [docs/CLIENTES_Y_ENVIOS_CLIENTES.md](docs/CLIENTES_Y_ENVIOS_CLIENTES.md): módulo de clientes, envíos documentales y correos Outlook preparados.

## Trabajo desde varios equipos

En GitHub Desktop:

1. Antes de empezar, abrir este repositorio y realizar **Fetch origin**.
2. Si existen cambios remotos, realizar **Pull origin** antes de editar.
3. Trabajar únicamente con archivos de código y documentación.
4. Revisar **Changes** y confirmar que no aparecen datos locales ni secretos.
5. Al terminar, crear un commit descriptivo y realizar **Push origin**.

No deben mantenerse cambios distintos sin sincronizar en dos equipos a la vez. Los datos SQLite, `.env`, mensajes, PDFs y descargas deben trasladarse por un canal privado independiente de Git.

## Seguridad

No subir:

- `.env`, contraseñas, tokens, claves o credenciales;
- bases de datos reales o copias;
- mensajes `.msg`, PDFs de clientes o TXT extraídos;
- logs, ZIP, temporales, backups o ficheros `.xlsm` con datos;
- `_NO_SUBIR_GITHUB/`, `.venv`, `node_modules` o cachés.

Antes del primer push, leer [SANEAMIENTO_REPOSITORIO.md](SANEAMIENTO_REPOSITORIO.md).

## Arranque local seguro

Requiere Python 3.10 o posterior. Desde la raíz:

```powershell
cd webapp\infonalia_webapp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completar en `.env` los usuarios y contraseñas obligatorios. Para la primera prueba:

```text
INFONALIA_HOST=127.0.0.1
INFONALIA_ENABLE_ADMIN_ALIAS=0
```

Después puede iniciarse manualmente con `python app.py`. No usar datos reales, descargas ni acceso de red hasta validar la configuración local.

El enlace “Volver a la web pública” de la pantalla de login usa `LLANGON_PUBLIC_SITE_URL`. Si no se configura, apunta a la web pública de prueba en Firebase:

```text
LLANGON_PUBLIC_SITE_URL=https://llangon-web-publica-prueba.web.app/
```

Para ejecutar la suite en Windows sin mantener una consola abierta, ver [docs/DESPLIEGUE_LOCAL_WINDOWS.md](docs/DESPLIEGUE_LOCAL_WINDOWS.md). Ese modo registra tareas programadas locales para web, scheduler y copias SQLite, manteniendo la web en `127.0.0.1:8787`.

## Pruebas

Desde la raíz del proyecto, el comando oficial de backend es:

```powershell
python -m pytest
```

La configuración de `pytest.ini` limita la recogida de pruebas a `webapp/infonalia_webapp/tests` y excluye carpetas de runtime, backups, temporales y builds. Así se evita que pytest explore datos generados o carpetas con permisos especiales.

Comprobación frontend habitual:

```powershell
node --check webapp/infonalia_webapp/static/app.js
```

También puede usarse el script auxiliar:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1
```

## Configuración operativa desde la Suite

La pantalla privada de Configuración permite editar opciones operativas de bajo riesgo desde `app_settings`, manteniendo `.env` como fallback y sin escribir secretos en disco desde la interfaz. La regla efectiva es: valor guardado en la Suite, después variable de entorno, después valor seguro por defecto.

Se pueden gestionar desde la Suite opciones de buzones automáticos, importación automática de Infonalia, límites básicos de IA documental y destinatarios de avisos del monitor/agenda. Las contraseñas IMAP, claves Gemini, tokens Telegram y secretos Dropbox siguen siendo de entorno: la app solo muestra “configurado / no configurado”.

## Dropbox local sincronizado

La suite puede trabajar con la carpeta local sincronizada por Dropbox Desktop. La ruta base se configura siempre por variable de entorno; no debe hardcodearse en el código ni en commits.

Variable principal:

```text
LLANGON_DROPBOX_BASE_PATH=
```

Ejemplo temporal en Windows PowerShell:

```powershell
$env:LLANGON_DROPBOX_BASE_PATH="C:\Users\USUARIO\Dropbox\ASESORES LLANGON SL"
```

En este equipo de trabajo:

```powershell
$env:LLANGON_DROPBOX_BASE_PATH="C:\Users\LLangon03\Dropbox\00000 LLANGON"
```

Para dejarlo en `.env`, añadir:

```text
LLANGON_DROPBOX_BASE_PATH=C:\Users\USUARIO\Dropbox\ASESORES LLANGON SL
```

En este equipo:

```text
LLANGON_DROPBOX_BASE_PATH=C:\Users\LLangon03\Dropbox\00000 LLANGON
```

Si `LLANGON_DROPBOX_BASE_PATH` no está definida, el entorno de desarrollo y tests siguen usando las rutas locales/de prueba actuales cuando se configuran expresamente. Las funciones que necesitan validar Dropbox real devuelven mensajes controlados como “Carpeta no configurada”, “La ruta no existe” o “La ruta está fuera de la carpeta base de Dropbox”.

Las carpetas nuevas de expedientes se crean siempre dentro de esa raíz con la estructura:

```text
AÑO\MES\CARPETA_EXPEDIENTE
```

Ejemplo:

```text
2026\07 JULIO\20 JULIO 1400 ALICANTE EL PINOSO ESCUELA INFANTIL PASO202613SIM 1418652R
```

En SQLite se guarda esa ruta relativa, nunca la raíz completa de Windows. Las rutas antiguas que empiecen directamente por el mes, por ejemplo `07 JULIO\...`, se mantienen solo como compatibilidad de lectura si la carpeta ya existe; las descargas nuevas no deben crear carpetas de expediente directamente bajo la raíz de Dropbox sin el año.

El inventario/monitor usa esta prioridad de raíz local:

1. `INFONALIA_MONITOR_ROOT`, solo como override técnico explícito.
2. `LLANGON_DROPBOX_BASE_PATH`, ruta principal recomendada.
3. `INFONALIA_DROPBOX_ROOT`, compatibilidad histórica.

Si no existe ninguna raíz válida, el scheduler no se cae: registra un error controlado en el bloque de inventario e indica que `LLANGON_DROPBOX_BASE_PATH` no está configurada o la ruta no existe.

Reglas de seguridad:

- Las rutas de expedientes se resuelven siempre dentro de la base configurada cuando se indica una ruta relativa.
- Se bloquean rutas absolutas enviadas como relativas y cualquier intento de `..`.
- Si una ficha conserva una ruta absoluta antigua, se puede seguir mostrando y usando, pero queda identificada si está fuera de la base configurada.
- Las operaciones locales son conservadoras: no deben borrar ni sobrescribir ficheros existentes.

## Agenda operativa y email

La pantalla Agenda usa listas limpias por día, semana, calendario mensual y vista completa. La bandeja operativa queda disponible para servicios internos, pero no se muestra como bloque principal.

El resumen por email se lanza manualmente desde Agenda. Si SMTP está configurado, el botón envía correo real al usuario logueado o al fallback `INFONALIA_AGENDA_EMAIL_TO`. Si SMTP no está configurado, devuelve un error claro y no hace dry-run silencioso.

```text
INFONALIA_SMTP_ENABLED=1
INFONALIA_AGENDA_EMAIL_TO=usuario@ejemplo.es
LLANGON_TELEGRAM_ENABLED=0
LLANGON_TELEGRAM_BOT_TOKEN=
LLANGON_TELEGRAM_GROUP_CHAT_ID=
```

Para activar la primera fase de Telegram, configura el `chat_id` del grupo en `LLANGON_TELEGRAM_GROUP_CHAT_ID` y guarda el `telegram_chat_id` de cada usuario desde la pantalla de usuarios de la Suite; no se guarda en `.env`.

`dry_run=true` queda reservado para pruebas/desarrollo del endpoint. No se guardan secretos en Git.

El flujo de documentos recomendado sigue siendo Dropbox local/Desktop con `INFONALIA_STORAGE_BACKEND=local`; Dropbox API queda experimental y desactivado.

## Importación automática del correo Infonalia

La Suite puede vigilar el buzón técnico `info3llangon@gmail.com` para importar automáticamente el correo diario de Infonalia. Gmail debe aplicar previamente la etiqueta IMAP `LLANGON_INFONALIA` a esos mensajes; la Suite no busca en todo `INBOX` ni filtra por remitente/asunto en `IMAP SEARCH`.

El importador selecciona la etiqueta configurada, busca únicamente correos no leídos con `UID SEARCH UNSEEN` y recupera cabeceras/cuerpo con `BODY.PEEK`. Un correo se considera importable cuando el cuerpo parsea bloques reales de LICITACIONES Infonalia. Para cada licitación reutiliza el mismo enriquecimiento por PDF que la importación manual: descarga el anuncio de Infonalia, lo convierte con `pdftotext.exe` y completa campos como tipo de contrato y hora límite cuando aparecen en el PDF. Si no hay estructura válida, queda sin marcar como leído y se registra el motivo controlado.

Variables principales:

```text
LLANGON_INFONALIA_IMPORT_ENABLED=0
LLANGON_INFONALIA_IMPORT_FROM=envios@infonalia.net
LLANGON_INFONALIA_IMPORT_SUBJECT=LICITACIONES - Envío de Novedades - 149022
LLANGON_INFONALIA_IMPORT_NOTIFY_EMAIL=info3@llangon.com
LLANGON_INFONALIA_IMPORT_FOLDER=LLANGON_INFONALIA
LLANGON_INFONALIA_IMPORT_LOOKBACK_HOURS=48
LLANGON_INFONALIA_IMPORT_MARK_READ_ON_SUCCESS=1
LLANGON_INFONALIA_IMPORT_POLL_MINUTES=30
LLANGON_INFONALIA_IMPORT_TEST_FORWARDERS=
```

Reutiliza la configuración IMAP `LLANGON_ACTIONS_IMAP_*`. `LLANGON_INFONALIA_IMPORT_FROM`, `LLANGON_INFONALIA_IMPORT_SUBJECT` y `LLANGON_INFONALIA_IMPORT_LOOKBACK_HOURS` quedan como referencia/compatibilidad, pero el flujo normal por etiqueta no depende de ellos. La lectura usa `BODY.PEEK`: no marca correos como leídos por inspeccionarlos, no borra mensajes y solo marca como leído un candidato cuando termina importado o reconocido como duplicado. La tabla `infonalia_email_imports` guarda `message_id` y huella del cuerpo para no importar ni notificar dos veces el mismo correo aunque se vuelva a marcar como no leído. Si un correo ya importado se reprocesa y había licitaciones incompletas, se intenta completar campos vacíos con el enriquecimiento PDF sin duplicar ni reenviar aviso. Si falta `pdftotext.exe`, revisar `INFONALIA_PDFTOTEXT`; se registrará aviso por licitación y se conservarán los datos básicos.

Pruebas sin tocar IMAP:

```powershell
python -m webapp.infonalia_webapp.infonalia_mail_importer --from-eml C:\ruta\correo.eml --parse-only --verbose
python -m webapp.infonalia_webapp.infonalia_mail_importer --from-eml C:\ruta\correo.eml --dry-run --verbose
```

Prueba segura del buzón:

```powershell
python -m webapp.infonalia_webapp.infonalia_mail_importer --once --dry-run --verbose
```

Procesamiento real filtrado:

```powershell
python -m webapp.infonalia_webapp.infonalia_mail_importer --once --verbose
```

## Revisión Infonalia por correo

El correo que recibe Nuria para revisar un día de Infonalia se genera con tarjetas visuales y botones `mailto:`. Los botones no abren la Suite: preparan un correo técnico con un código de acción que la Suite puede leer después desde un buzón IMAP.

Variables principales:

```text
LLANGON_ACTION_MAILBOX_TO=info3llangon@gmail.com
LLANGON_ACTION_MAILBOX_CC=info3@llangon.com
LLANGON_ACTION_NOTIFY_EMAIL=info3@llangon.com
LLANGON_ACTION_ALLOWED_SENDERS=
LLANGON_ACTIONS_IMAP_HOST=imap.gmail.com
LLANGON_ACTIONS_IMAP_PORT=993
LLANGON_ACTIONS_IMAP_USER=
LLANGON_ACTIONS_IMAP_PASSWORD=
LLANGON_ACTIONS_IMAP_FOLDER=INBOX
LLANGON_REVIEW_AI_SUMMARY_BUTTON_ENABLED=0
```

`LLANGON_ACTIONS_IMAP_PASSWORD` no debe subirse a Git. Si falta la configuración IMAP, el procesador queda desactivado de forma controlada y la app sigue funcionando. `LLANGON_ACTION_ALLOWED_SENDERS` debe contener el correo real desde el que Nuria enviará las órdenes; si está vacío, no se procesa ninguna orden.
Cuando Nuria responde con `Descargar para ver` o `Preparar ficha`, la Suite mantiene el cambio de estado y además encola una descarga automática de documentación reutilizando la misma lógica de descarga de la ficha. La cola evita duplicados si ya existe un trabajo pendiente o si la documentación ya figura como descargada. `LLANGON_REVIEW_AI_SUMMARY_BUTTON_ENABLED` queda reservado para una futura acción de resumen IA y permanece desactivado por defecto.

El procesador solo atiende correos cuyo asunto empieza exactamente por `LLANGON_CMD`. Los correos normales del buzón no se leen en cuerpo, no se borran y no se marcan como leídos. La lectura de candidatos usa `BODY.PEEK` para evitar añadir la marca `Leído` por inspección.

Los códigos ya no se validan contra una lista de códigos pendientes. Se interpretan directamente como `9 dígitos de entidad + 2 dígitos de acción`: por ejemplo `00000014101` significa licitación interna `141` y acción `01` (`Descartar`), y `00000005899` significa revisión Infonalia `58` y acción `99` (`Revisado`). La tabla `email_action_codes` se conserva como compatibilidad histórica y para generar los enlaces del correo, pero no bloquea ni consume acciones.

Mientras el día Infonalia esté abierto, Nuria puede pulsar varias veces sobre una misma licitación y prevalece siempre la última acción válida recibida. Al recibir `99 Revisado`, la revisión queda cerrada mediante `reviewed_at`; desde ese momento cualquier orden individual de ese mismo día se ignora y queda auditada. Al cerrar, las licitaciones que sigan sin decisión en `Importada` o `Enviada a Nuria` pasan automáticamente a `Descartada`.

Las acciones por correo solo pueden modificar estados de primera criba (`Importada`, `Enviada a Nuria`, `Descartada`, `Descargar para ver`, `Preparar ficha`/`Preparar`) y no pueden cambiar estados avanzados como `Preparada`, `Oferta enviada`, `Adjudicada`, `No adjudicada` o `En seguimiento`.

Prueba manual del procesador en una sola pasada:

```powershell
python -m webapp.infonalia_webapp.email_actions_processor --once --dry-run --verbose
```

Procesamiento real filtrado:

```powershell
python -m webapp.infonalia_webapp.email_actions_processor --once --verbose
```

Incluir órdenes ya leídas:

```powershell
python -m webapp.infonalia_webapp.email_actions_processor --once --include-seen --verbose
```

Revisar un código sin tocar IMAP:

```powershell
python -m webapp.infonalia_webapp.email_actions_processor --check-code 00000014101
```

Simular un código sin tocar IMAP ni cambiar estados:

```powershell
python -m webapp.infonalia_webapp.email_actions_processor --simulate-code 00000014101 --from-email correoautorizado@ejemplo.com --dry-run
```

El scheduler local de Windows no crea un sistema paralelo: cuando `MONITOR_SCHEDULER_ENABLED=1`, la tarea `LlangonSuite-Scheduler` ejecuta `python -m webapp.infonalia_webapp.monitor.scheduler --once`. En esa pasada se procesan, si están activados, la importación automática de Infonalia, las órdenes `LLANGON_CMD` y el inventario local de ficheros, respetando `LLANGON_INFONALIA_IMPORT_POLL_MINUTES`, `LLANGON_EMAIL_ACTIONS_POLL_MINUTES` y `LLANGON_FILE_INVENTORY_POLL_MINUTES`.

## Licitaciones y seguimiento

La pantalla Licitaciones es el centro de trabajo diario. Cada expediente puede marcarse como revisado, tener estado interno, notas internas, actuaciones vinculadas y seguimiento activo. El seguimiento automático real queda preparado, pero no implementado: el futuro monitor será un script externo de Windows y enviará un email por cada licitación con novedades a los destinatarios globales de `INFONALIA_SEGUIMIENTO_EMAILS`.

## Análisis IA documental

La Fase 1 de IA permite preparar un análisis documental interno de una licitación y guardar un JSON estructurado en SQLite. La línea de Gemini queda conservada, pero aparcada; el flujo nuevo prioriza que el usuario elija manualmente qué documentos entran en el análisis antes de generar o regenerar.

El flujo desde la ficha ampliada es manual:

- abrir una licitación;
- entrar en la pestaña `Análisis IA`;
- pulsar `Generar análisis IA`, `Regenerar análisis IA` o `Reintentar`;
- revisar la modal `Seleccionar ficheros para análisis`;
- confirmar únicamente los ficheros que deben analizarse.

La lista de ficheros se lee de la carpeta física del expediente resuelta con la configuración de Dropbox/local. No depende del monitor ni de la pestaña `Documentos`. El frontend envía rutas relativas seguras y el backend vuelve a validarlas para bloquear rutas absolutas, `..` y cualquier salida de la carpeta del expediente.

Los documentos originales no se modifican. Para cada job se crea una carpeta aislada en:

```text
runtime/ai_work/jobs/<job_id>/
```

Esa carpeta contiene copias de los ficheros seleccionados, `manifest.json`, `prompt.md`, `schema.json`, `logs/` y, cuando procede, texto extraído de PDFs en `extracted_text/`.

Endpoints principales:

```text
GET    /api/licitaciones/<id>/ai-files
POST   /api/licitaciones/<id>/ai-summary/generate
POST   /api/licitaciones/<id>/ai-summary/regenerate
DELETE /api/licitaciones/<id>/ai-summary
POST   /api/licitaciones/<id>/ai-summary/email
```

El botón `Borrar` elimina solo el resumen IA guardado para la licitación. No borra jobs históricos, documentos originales, carpetas del expediente ni carpetas temporales de trabajo.

El botón `Enviar por correo` aparece cuando existe un análisis útil. Abre una confirmación con destinatario y asunto editables y envía un email HTML mediante la configuración SMTP existente. En esta fase no adjunta documentos.

Por seguridad, Gemini sigue apagado por defecto y la app arranca sin clave:

```text
GEMINI_ENABLED=false
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
GEMINI_MAX_REQUESTS_PER_MINUTE=2
GEMINI_MAX_REQUESTS_PER_DAY=20
GEMINI_COOLDOWN_ON_429_MINUTES=15
GEMINI_MAX_DOCUMENTS_PER_ANALYSIS=4
GEMINI_MAX_FILE_MB=45
GEMINI_TIMEOUT_SECONDS=120
GEMINI_INPUT_MODE=text
GEMINI_MAX_EXTRACTED_CHARS=180000
GEMINI_MAX_CHARS_PER_DOCUMENT=90000
GEMINI_PDF_INLINE_FALLBACK=false
GEMINI_MIN_EXTRACTED_CHARS=1000
```

Proveedor experimental `codex_local`:

```text
AI_ANALYSIS_PROVIDER=codex_local
CODEX_LOCAL_ENABLED=false
CODEX_EXECUTABLE=codex
CODEX_TIMEOUT_SECONDS=600
CODEX_WORK_ROOT=runtime/ai_work/jobs
CODEX_SANDBOX=read-only
CODEX_MAX_FILES=8
CODEX_MAX_FILE_MB=45
```

`Codex Local` está desactivado por defecto. Si se activa en una futura prueba, se ejecutará únicamente sobre la carpeta temporal del job, no sobre Dropbox ni sobre el repositorio. La ejecución usa `subprocess.run` sin `shell=True`, con timeout, `cwd` del job y validación de JSON de salida. Si no está activado devuelve `CODEX_DISABLED`; si no se encuentra el ejecutable devuelve `CODEX_NOT_FOUND`.

Para activar Gemini en local, completar `.env`:

```text
AI_ANALYSIS_PROVIDER=gemini
GEMINI_ENABLED=true
GEMINI_API_KEY=TU_CLAVE_PRIVADA
```

No subir nunca `GEMINI_API_KEY` ni claves reales a Git. Las claves no se imprimen en logs ni se devuelven al frontend.

Prueba manual controlada:

```powershell
cd C:\Users\LLangon03\Documents\Codex\Llangon-SuiteV2
.\.venv\Scripts\python.exe -m webapp.infonalia_webapp.ai.manual_test --licitacion-id 123
```

Para crear/procesar job si Gemini está configurado:

```powershell
.\.venv\Scripts\python.exe -m webapp.infonalia_webapp.ai.manual_test --licitacion-id 123 --generate
```

Para probar el modo texto sin tocar `.env`:

```powershell
.\.venv\Scripts\python.exe -m webapp.infonalia_webapp.ai.manual_test --licitacion-id 123 --force --timeout 90 --input-mode text
```

## Orden de lectura

1. `README.md`
2. `PROJECT_CONTEXT.md`
3. `SANEAMIENTO_REPOSITORIO.md`
4. `INVENTARIO_MIGRACION.md`
5. `MIGRACION_LOG.md`
