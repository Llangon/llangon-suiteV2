# Entorno de desarrollo local

Este PC es exclusivamente de desarrollo. Producción vive en el servidor nuevo; desde aquí no se deben ejecutar tareas programadas Llangon, túneles, despliegues Firebase/Cloudflare ni integraciones reales.

## Arranque seguro

1. Crear el entorno virtual desde la raíz: `py -3 -m venv .venv`.
2. Instalar dependencias: `./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt`.
3. Copiar `webapp/infonalia_webapp/.env.dev.example` a `.env.dev` y sustituir ambas claves por credenciales ficticias y locales.
4. Arrancar siempre con `powershell -ExecutionPolicy Bypass -File ./scripts/windows/start_dev_local.ps1`.

El script fuerza `127.0.0.1:8788`, crea datos, secretos, descargas y logs dentro de `.llangon-dev/`, y desactiva correo, IMAP, Telegram, Dropbox, IA, descargas reales, scheduler, backups y portal público. Nunca utiliza la base real ni los datos configurados en `.env`.

La web corporativa se previsualiza, sin publicar, con `powershell -ExecutionPolicy Bypass -File ./scripts/windows/start_public_web_preview.ps1` en `127.0.0.1:5500`.

## Control de producción en este PC

- Cloudflare Tunnel no está instalado como servicio.
- `LlangonSuite-KeeperTick` y `LlangonSuite-WakeTick` deben permanecer deshabilitadas o eliminadas. No ejecutar sus instaladores.
- No usar `start_web_production.ps1`, instaladores de tareas, Firebase CLI de despliegue, `wrangler`, ni comandos de publicación desde este PC.
- Antes de cambios que afecten despliegue, ejecutar solo comprobaciones locales y pedir autorización para cualquier acción externa.

## Git y GitHub

El remoto `origin` ya apunta a `https://github.com/Llangon/llangon-suiteV2.git`. No se debe reinicializar el repositorio ni hacer un push masivo: el árbol actual contiene cambios locales grandes y no consolidados.

Flujo recomendado después de revisar y dividir el estado actual:

1. Crear una rama por cambio desde `main`: `git switch main`, `git pull --ff-only`, `git switch -c codex/<tema>`.
2. Ejecutar pruebas locales antes del commit: `powershell -ExecutionPolicy Bypass -File ./scripts/run_tests.ps1`.
3. Revisar que el commit no incluya `.env`, SQLite, `.llangon-dev`, `runtime`, descargas, salidas generadas ni temporales.
4. Crear commits pequeños y claros, subir la rama y abrir una pull request hacia `main`.
5. Activar en GitHub protección de `main`: pull request obligatoria, al menos una aprobación, checks obligatorios y prohibir force-push. Añadir una regla equivalente a las ramas de producción si las hubiera.

El primer trabajo pendiente es una revisión de saneamiento del árbol actual para agrupar los cambios existentes en commits revisables. Debe hacerse antes de convertir esta rama en la base normal de desarrollo.
