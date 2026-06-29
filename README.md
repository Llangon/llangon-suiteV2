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

## Análisis IA documental con Gemini

La Fase 1 de IA permite analizar manualmente los PDFs principales de un expediente y guardar un JSON estructurado en SQLite. Está pensada como apoyo interno: no genera todavía una ficha PDF final para cliente y no analiza licitaciones anteriores.

Por seguridad, Gemini está apagado por defecto y la app arranca sin clave:

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
```

Para activarlo en local, completar `.env`:

```text
GEMINI_ENABLED=true
GEMINI_API_KEY=TU_CLAVE_PRIVADA
```

No subir nunca `GEMINI_API_KEY` a Git. La clave no se imprime en logs ni se devuelve al frontend.

El flujo desde la ficha ampliada es manual:

- abrir una licitación;
- entrar en la pestaña `Análisis IA`;
- pulsar `Generar análisis IA`;
- reutilizar el resumen existente si los documentos no han cambiado;
- usar `Regenerar análisis IA` solo como administrador.

La selección de documentos es conservadora: solo PDFs, priorizando `Cuadro`, `PCAP/PCA`, `PPT`, `Pliego` y `Anexos`, con límite de tamaño y número de documentos. Los documentos de licitaciones anteriores, actas, aperturas y valoraciones se excluyen en esta fase.

Prueba manual controlada:

```powershell
cd C:\Users\LLangon03\Documents\Codex\Llangon-SuiteV2
.\.venv\Scripts\python.exe -m webapp.infonalia_webapp.ai.manual_test --licitacion-id 123
```

Para crear/procesar job si Gemini está configurado:

```powershell
.\.venv\Scripts\python.exe -m webapp.infonalia_webapp.ai.manual_test --licitacion-id 123 --generate
```

## Orden de lectura

1. `README.md`
2. `PROJECT_CONTEXT.md`
3. `SANEAMIENTO_REPOSITORIO.md`
4. `INVENTARIO_MIGRACION.md`
5. `MIGRACION_LOG.md`
