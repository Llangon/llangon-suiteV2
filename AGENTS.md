# AGENTS

## Fuentes de verdad

Usa este orden cuando trabajes en `Llangon-SuiteV2`:

1. `AGENTS.md`
2. `docs/CODEX_CONTEXT.md`
3. `docs/COMANDOS_DESARROLLO.md`
4. documentacion existente del repo

## Mapa rapido

- `webapp/infonalia_webapp`: app privada Python/SQLite
- `firebase/public_firebase`: web publica estatica
- `herramientas_python`: descargadores y utilidades auxiliares
- `scripts/` y `scripts/windows/`: automatizacion y operacion local Windows
- `macros/`: VBA
- `docs/`: documentacion operativa y tecnica

## App privada vs web publica

- La app privada vive en `webapp/infonalia_webapp`, usa Python/SQLite y no debe mezclarse con Firebase.
- La web publica vive en `firebase/public_firebase`, es estatica y debe mantenerse separada de la app privada.

## Convencion operativa

- Trabaja desde la raiz del repo.
- Usa `.venv` en la raiz como entorno virtual preferido.
- Prioriza validaciones sin efectos reales.

## Reglas permanentes de seguridad

- No tocar secretos, `.env`, credenciales, claves ni tokens.
- No tocar bases SQLite reales ni datos locales.
- No tocar `runtime/`, `.local_backups/`, logs, backups ni carpetas sensibles.
- No exponer la app fuera de loopback sin permiso explicito.

## No tocar sin permiso explicito

- Descargadores reales.
- Importadores de correo.
- Acciones IMAP, SMTP, Telegram o Dropbox.
- Tareas Windows.
- `README.md`, `PROJECT_CONTEXT.md` o documentacion historica.

## Como validar cambios

- `.\.venv\Scripts\python.exe -m pytest --collect-only -q`
- `.\.venv\Scripts\python.exe -m pytest -q`
- `node --check webapp/infonalia_webapp/static/app.js`
- `node --check webapp/infonalia_webapp/static/login.js`
- `node --check firebase/public_firebase/static/public.js`
- `powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1`

## Regla de ejecucion

No lances procesos con efectos reales sin autorizacion expresa. Si un comando toca correo, Dropbox, Telegram, scheduler real, tareas Windows, descargadores o backups reales, deten la ejecucion y pide permiso primero.
