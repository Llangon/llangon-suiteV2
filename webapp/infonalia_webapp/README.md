# Infonalia Webapp

Aplicación privada para gestionar días de Infonalia, revisar licitaciones y coordinar la descarga de documentación.

## Ubicación en el monorepo

```text
webapp/infonalia_webapp/
```

Los descargadores utilizados por la app están en:

```text
herramientas_python/
```

La documentación relacionada está en:

- `../../PROJECT_CONTEXT.md`
- `../../docs/DESPLIEGUE_COLABORACION.md`
- `../../docs/ROLES_Y_FLUJO.md`

## Preparación local

Desde la raíz del repositorio:

```powershell
cd webapp\infonalia_webapp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Antes de arrancar, editar `.env` y completar los usuarios y contraseñas obligatorios con valores largos y únicos. La aplicación se detiene si faltan. El archivo `.env` es local y está excluido de Git.

Para una primera prueba segura:

- usar `INFONALIA_HOST=127.0.0.1`,
- mantener `INFONALIA_ENABLE_ADMIN_ALIAS=0`,
- no utilizar datos reales.

## Tests locales

Los tests se preparan desde la raíz del repositorio, usando un entorno virtual local:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r webapp\infonalia_webapp\requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

`requirements-dev.txt` contiene dependencias de desarrollo y test. No forma parte de las dependencias mínimas de producción de la app.

## Arranque manual

```powershell
python app.py
```

Después abrir:

```text
http://127.0.0.1:8787
```

También existen los lanzadores `Instalar dependencias.bat` y `Arrancar Infonalia.bat`. El BAT de arranque usa `127.0.0.1` y deja la app lista para una prueba local básica.

## Configuración

Variables principales:

```text
INFONALIA_ADMIN_USER=
INFONALIA_ADMIN_PASSWORD=
INFONALIA_ADMIN_DISPLAY_NAME=
INFONALIA_ADMIN_EMAIL=
INFONALIA_REVIEWER_USER=
INFONALIA_REVIEWER_PASSWORD=
INFONALIA_REVIEWER_DISPLAY_NAME=
INFONALIA_REVIEWER_EMAIL=
INFONALIA_ENABLE_ADMIN_ALIAS=0
INFONALIA_HOST=127.0.0.1
INFONALIA_PORT=8787
LLANGON_DROPBOX_BASE_PATH=
INFONALIA_DROPBOX_ROOT=C:\ReplicaDb
INFONALIA_PDFTOTEXT=
INFONALIA_PLATFORM_URL=
INFONALIA_SMTP_HOST=
INFONALIA_SMTP_PORT=587
INFONALIA_SMTP_USER=
INFONALIA_SMTP_PASSWORD=
INFONALIA_SMTP_FROM=
INFONALIA_SMTP_TLS=1
INFONALIA_SMTP_SSL=0
LLANGON_ACTION_MAILBOX_TO=info3llangon@gmail.com
LLANGON_ACTION_MAILBOX_CC=info3@llangon.com
LLANGON_ACTION_NOTIFY_EMAIL=info3@llangon.com
LLANGON_ACTION_ALLOWED_SENDERS=
LLANGON_ACTIONS_IMAP_HOST=imap.gmail.com
LLANGON_ACTIONS_IMAP_PORT=993
LLANGON_ACTIONS_IMAP_USER=
LLANGON_ACTIONS_IMAP_PASSWORD=
LLANGON_ACTIONS_IMAP_FOLDER=INBOX
LLANGON_EMAIL_ACTIONS_ENABLED=0
LLANGON_EMAIL_ACTIONS_POLL_MINUTES=10
LLANGON_INFONALIA_IMPORT_ENABLED=0
LLANGON_INFONALIA_IMPORT_FROM=envios@infonalia.net
LLANGON_INFONALIA_IMPORT_SUBJECT=LICITACIONES - Envío de Novedades - 149022
LLANGON_INFONALIA_IMPORT_NOTIFY_EMAIL=info3@llangon.com
LLANGON_INFONALIA_IMPORT_FOLDER=INBOX
LLANGON_INFONALIA_IMPORT_LOOKBACK_HOURS=48
LLANGON_INFONALIA_IMPORT_MARK_READ_ON_SUCCESS=1
LLANGON_INFONALIA_IMPORT_POLL_MINUTES=30
LLANGON_INFONALIA_IMPORT_TEST_FORWARDERS=
```

La URL de acceso incluida en notificaciones solo se muestra cuando `INFONALIA_PLATFORM_URL` tiene un valor local válido.

El procesador de órdenes por correo queda inactivo si falta usuario o contraseña IMAP. Además, solo procesa asuntos que empiezan exactamente por `LLANGON_CMD`; los correos normales no se leen en cuerpo ni se marcan como leídos. `LLANGON_ACTION_ALLOWED_SENDERS` es obligatorio para ejecutar órdenes reales.

El código de acción se interpreta directamente y no depende de que exista previamente en `email_action_codes`. Formato: `00000014101` = licitación `141` + acción `01`; `00000005899` = revisión Infonalia `58` + acción `99`. Mientras la revisión está abierta, la última acción válida gana. Cuando se recibe `99 Revisado`, el día queda cerrado, las licitaciones que sigan en `Importada` o `Enviada a Nuria` pasan automáticamente a `Descartada`, y las órdenes individuales posteriores de ese día se ignoran y se registran en `email_action_events`.

Las acciones por correo son solo de primera criba: permiten `Importada`, `Enviada a Nuria`, `Descartada`, `Descargar para ver` y `Preparar ficha`/`Preparar`. Estados avanzados como `Preparada`, `Oferta enviada`, `Adjudicada`, `No adjudicada` o `En seguimiento` no se modifican desde correo.

Prueba segura:

```powershell
python -m webapp.infonalia_webapp.email_actions_processor --once --dry-run --verbose
```

Procesamiento real filtrado:

```powershell
python -m webapp.infonalia_webapp.email_actions_processor --once --verbose
```

Revisar un código sin tocar IMAP:

```powershell
python -m webapp.infonalia_webapp.email_actions_processor --check-code 00000014101
```

## Importación automática del correo Infonalia

El importador `infonalia_mail_importer` lee el mismo buzón IMAP técnico y solo acepta el correo diario de `envios@infonalia.net` con asunto exacto `LICITACIONES - Envío de Novedades - 149022`. Extrae las licitaciones, crea/actualiza el día Infonalia correspondiente a la fecha del mensaje y envía un aviso a `LLANGON_INFONALIA_IMPORT_NOTIFY_EMAIL` cuando la importación real termina.

La importación es idempotente: `infonalia_email_imports` registra `message_id`, huella del cuerpo, UID IMAP, estado, recuentos y fecha de aviso. Si el mismo mensaje vuelve a aparecer, no duplica licitaciones ni vuelve a notificar.

Pruebas locales sin IMAP:

```powershell
python -m webapp.infonalia_webapp.infonalia_mail_importer --from-eml C:\ruta\correo.eml --parse-only --verbose
python -m webapp.infonalia_webapp.infonalia_mail_importer --from-eml C:\ruta\correo.eml --dry-run --verbose
```

Prueba del buzón sin escribir:

```powershell
python -m webapp.infonalia_webapp.infonalia_mail_importer --once --dry-run --verbose
```

Procesamiento real:

```powershell
python -m webapp.infonalia_webapp.infonalia_mail_importer --once --verbose
```

El scheduler local ejecuta este importador y el procesador `LLANGON_CMD` en la misma pasada de `python -m webapp.infonalia_webapp.monitor.scheduler --once`, siempre que sus variables `*_ENABLED` estén activadas. Los correos se leen con `BODY.PEEK`; no se borran y no se marcan como leídos salvo candidato importado correctamente o duplicado ya controlado.

## Funciones actuales

- Login local y gestión de usuarios.
- Base de datos SQLite local.
- Importación directa de mensajes `.msg`.
- Importación CSV como alternativa.
- Vista de días y licitaciones.
- Filtros, estados, comentarios y notificaciones.
- Integración opcional con SMTP.
- Descarga por plataforma mediante `herramientas_python/Descargar_Licitacion.py`.
- Interfaz para escritorio y móvil.

## Datos locales

La carpeta `data/` puede contener:

- la base de datos SQLite,
- una clave local,
- mensajes importados,
- PDFs y TXT temporales,
- descargas operativas.

Todo ese contenido está excluido de Git salvo `.gitkeep` y `README_DATOS.md`.

## Dropbox

La raíz real de Dropbox se configura mediante `LLANGON_DROPBOX_BASE_PATH`:

```powershell
$env:LLANGON_DROPBOX_BASE_PATH="C:\Users\USUARIO\Dropbox\ASESORES LLANGON SL"
```

En este equipo:

```powershell
$env:LLANGON_DROPBOX_BASE_PATH="C:\Users\LLangon03\Dropbox\00000 LLANGON"
```

No se debe hardcodear esa ruta en el código. Si la variable no está configurada, la app conserva el flujo local/de pruebas. `INFONALIA_DROPBOX_ROOT` queda como compatibilidad histórica para réplicas locales, por ejemplo `C:\ReplicaDb`, pero la variable principal para Dropbox real es `LLANGON_DROPBOX_BASE_PATH`.

Si `LLANGON_DROPBOX_BASE_PATH` está definida pero la carpeta no existe, las funciones que necesitan Dropbox real devuelven un error controlado. Si una ruta de expediente queda fuera de la base configurada, se muestra como “La ruta está fuera de la carpeta base de Dropbox”.

Si no se encuentra una ruta válida, la app puede usar `data/descargas/` como destino local. Esa carpeta también está ignorada.

## Dependencias

Las dependencias externas declaradas son:

- `extract-msg`
- `requests`
- `beautifulsoup4`
- `websocket-client`

El resto de imports pertenece a la biblioteca estándar de Python o a módulos locales de `herramientas_python/`.

Algunos descargadores pueden necesitar Chrome o Edge. La extracción complementaria de datos desde PDF puede usar `pdftotext.exe` si se configura.
