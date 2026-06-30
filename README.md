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

Si `LLANGON_DROPBOX_BASE_PATH` no está definida, el entorno de desarrollo y tests siguen usando las rutas locales/de prueba actuales. Las funciones que necesitan validar Dropbox real devuelven mensajes controlados como “Carpeta no configurada”, “La ruta no existe” o “La ruta está fuera de la carpeta base de Dropbox”.

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
```

`dry_run=true` queda reservado para pruebas/desarrollo del endpoint. No se guardan secretos en Git.

El flujo de documentos recomendado sigue siendo Dropbox local/Desktop con `INFONALIA_STORAGE_BACKEND=local`; Dropbox API queda experimental y desactivado.

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
