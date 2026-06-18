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
```

La URL de acceso incluida en notificaciones solo se muestra cuando `INFONALIA_PLATFORM_URL` tiene un valor local válido.

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

La raíz de Dropbox se configura mediante:

La ruta se define en `INFONALIA_DROPBOX_ROOT` dentro del `.env` local. Durante desarrollo y pruebas debe apuntar a `C:\ReplicaDb`, una réplica local de la estructura de Dropbox. Los marcadores `[IdLicitacion].llangon`, `EnSeguimiento.llangon`, la sincronización y el futuro monitor deben trabajar contra esa réplica, no contra Dropbox real.

Si `INFONALIA_DROPBOX_ROOT` está definido pero la carpeta no existe, la app no intenta autodetectar Dropbox Desktop por detrás. En ese caso usará el flujo local interno hasta que se cree o corrija la ruta configurada.

Si no se encuentra una ruta válida, la app puede usar `data/descargas/` como destino local. Esa carpeta también está ignorada.

## Dependencias

Las dependencias externas declaradas son:

- `extract-msg`
- `requests`
- `beautifulsoup4`
- `websocket-client`

El resto de imports pertenece a la biblioteca estándar de Python o a módulos locales de `herramientas_python/`.

Algunos descargadores pueden necesitar Chrome o Edge. La extracción complementaria de datos desde PDF puede usar `pdftotext.exe` si se configura.
