# Precheck refactor de app.py

Este documento inventaria la superficie actual de `webapp/infonalia_webapp/app.py` antes de cualquier refactor.

Es una fase preparatoria. No se refactoriza `app.py`, no se mueve codigo, no se cambian imports, no se cambian endpoints, no se cambian respuestas JSON, no se toca SQLite, no se cambia frontend, no se cambia Firebase y no se ejecutan descargadores reales.

## Estado actual

`app.py` concentra actualmente varias responsabilidades:

- carga de entorno con `load_env_file()` y `required_env()`;
- constantes de rutas como `APP_ROOT`, `STATIC_ROOT`, `DATA_ROOT`, `DOWNLOAD_ROOT`, `DB_PATH`, `SECRET_PATH` y `LAUNCHER_PATH`;
- configuracion de usuarios, SMTP, cookies, sesiones y CSRF;
- estados de licitaciones y dias;
- alias y parseo de CSV;
- firma de sesion con `make_token()` y `read_token()`;
- conexion SQLite con `db()` y `db_session()`;
- inicializacion de esquema con `init_db()` y `ensure_column()`;
- usuarios y configuracion con `seed_users_and_settings()`, `get_user_record()`, `get_settings()` y `update_settings()`;
- normalizacion general con `clean_text()`, `parse_money()`, `normalize_url()` y helpers de fecha/hora;
- importacion CSV con `read_csv_rows()`, `build_payload_from_csv_row()` e `import_csv_content()`;
- importacion MSG con `parse_msg_body()`, `enrich_from_infonalia_pdf()` e `import_msg_content()`;
- modelo operativo de dias y licitaciones con `get_or_create_dia()`, `refresh_dia_estado()` e `insert_payload()`;
- rutas de carpetas y descargas con `find_dropbox_root()`, `resolve_destination_folder()`, `write_http_url()` y `repair_internal_download_routes()`;
- vista previa IA y notificaciones con `build_ai_preview_payload()`, `create_notification()` y `send_notification_email()`;
- multipart uploads con `extract_multipart_file()`;
- servidor HTTP en `InfonaliaHandler`;
- arranque con `run()`.

## Superficie HTTP actual

`InfonaliaHandler` agrupa:

- `do_GET()`;
- `do_POST()`;
- `do_PATCH()`;
- `do_DELETE()`;
- autenticacion y sesion con `current_user()`;
- CSRF con `csrf_required_for_path()` y `require_csrf_token()`;
- permisos con `is_admin()` y `require_admin()`;
- lectura de request con `read_body()`;
- endpoints privados de dias, licitaciones, notificaciones, configuracion y noticias;
- endpoints publicos de noticias;
- respuestas con `send_json()`, `send_file()` y `redirect()`.

Endpoints y respuestas son parte del contrato operativo actual. Cualquier extraccion debe conservar rutas, metodos, codigos HTTP y campos JSON salvo fase explicita.

## Modulos ya extraidos o cercanos

Ya existen piezas fuera de `app.py` que marcan el estilo seguro:

- `web_security.py`, para cabeceras y cookies;
- `csrf.py`, para helpers puros de CSRF;
- `limits.py`, para limites puros;
- `core/models.py`, `core/source_contracts.py`, `core/storage_contracts.py` y `core/news_contracts.py`, como contratos puros.

Estos modulos no deben arrastrar importaciones pesadas ni efectos laterales. Un refactor futuro deberia seguir ese patron: extraer primero funciones puras o adaptadores pequenos, probarlas y solo despues conectar.

## Invariantes que no deben romperse

- Importar modulos puros no debe arrancar servidor.
- Importar modulos puros no debe abrir SQLite.
- Importar modulos puros no debe leer ni escribir datos reales.
- `app.py` debe seguir exponiendo `run()` e `InfonaliaHandler`.
- Login, logout, sesiones, roles y CSRF deben mantener comportamiento.
- Endpoints existentes deben mantener URL, metodo, codigo HTTP y JSON de exito.
- `POST /api/import/csv` y `POST /api/import/msg` deben seguir usando los mismos nombres de campos multipart.
- `POST /api/licitaciones/{id}/descargar` no debe ejecutar descargadores reales en tests.
- Los tests deben seguir usando SQLite temporal cuando escriban.
- Firebase, macros VBA y frontend publico deben quedar fuera salvo fase explicita.
- No se debe mezclar refactor de `app.py` con migraciones, CSRF global, StorageBackend o Markdown.

## Riesgos antes de refactorizar

- Cambiar imports puede ejecutar `required_env()` antes de que los tests preparen entorno.
- Mover funciones con dependencias globales puede alterar `DB_PATH`, `DATA_ROOT` o `DOWNLOAD_ROOT`.
- Separar `InfonaliaHandler` puede cambiar orden de validaciones y codigos HTTP.
- Extraer endpoints puede cambiar campos JSON por accidente.
- Dividir importacion CSV/MSG puede tocar parseo, deduplicacion o estado de dias.
- Dividir descargas puede mezclar refactor con StorageBackend.
- Dividir noticias puede mezclarse con Markdown seguro.
- Mover seguridad puede romper CSRF, cookies o CSP.
- Cambios grandes en un solo commit harian dificil detectar regresiones.

## Estrategia recomendada antes de implementar

Orden seguro:

1. Mantener `app.py` como fachada publica durante varias fases.
2. Extraer primero funciones puras sin SQLite, red ni filesystem.
3. Extraer despues adaptadores pequenos con tests existentes.
4. Evitar mover `InfonaliaHandler` hasta tener tests funcionales suficientes.
5. No cambiar nombres de funciones llamadas por tests hasta que exista compatibilidad.
6. Mantener imports antiguos reexportados si los tests o scripts los usan.
7. Hacer un commit por frontera logica: seguridad, importacion, descargas, noticias, persistencia o HTTP.
8. Ejecutar checks completos tras cada extraccion.
9. Dejar cualquier cambio de comportamiento para una fase separada y documentada.

## Candidatos de extraccion futura

Primeras extracciones razonables:

- utilidades puras de normalizacion: `clean_text()`, `bool_text()`, `parse_money()`, `parse_date_value()`, `parse_time_value()`;
- helpers de carpetas que no escriben: `safe_folder_name()`, `folder_text()`, `normalize_relative_folder_path()`;
- parseo CSV puro: `decode_csv_bytes()`, `read_csv_rows()`, `csv_alias_map()`, `build_payload_from_csv_row()`;
- parseo MSG puro que no descargue PDF;
- formateadores: `format_date_es()`, `format_datetime_es()`;
- adaptadores de email solo despues de aislar SMTP en tests.

Extracciones que requieren mas cautela:

- `init_db()` y persistencia SQLite;
- `InfonaliaHandler`;
- `api_download_licitacion()`;
- `api_create_news()` y `api_update_news()`;
- seguridad de sesion, cookies y CSRF.

## Tests existentes relevantes

- `test_import_endpoints.py`, para import CSV/MSG sin servidor y con SQLite temporal;
- `test_download_endpoint.py`, para descarga con `subprocess.run()` simulado;
- `test_download_safety.py`, para rutas, destinos y limites;
- `test_login_security.py`, para login, logout y sesiones;
- `test_csrf.py` y `test_csrf_private_mutations.py`, para CSRF;
- `test_web_security.py`, para cabeceras, cookies y render seguro;
- `test_project_safety_docs.py`, para asegurar que los prechecks no se pierden.

## Tests minimos futuros

- Importar cada modulo extraido no debe importar `app.py` salvo que sea fachada.
- Funciones puras extraidas deben tener tests propios sin SQLite.
- Endpoints existentes deben conservar respuestas JSON de exito y error.
- Rutas desconocidas deben seguir devolviendo `404 Not Found`.
- Tests de importacion y descarga deben seguir sin tocar SQLite productiva.
- Tests de descarga deben seguir sin red real ni descargadores reales.
- Frontend y Firebase deben seguir pasando `node --check`.

## Plan de rollback

- Mantener extracciones pequenas y revertibles.
- Si una extraccion rompe tests, revertir solo ese commit.
- Si una extraccion cambia comportamiento observado, restaurar la delegacion desde `app.py`.
- No combinar rollback con nuevas funcionalidades.

## Fuera de este precheck

- No se refactoriza `app.py`.
- No se mueve codigo.
- No se cambian imports.
- No se cambian endpoints.
- No se cambian respuestas JSON.
- No se toca SQLite.
- No se implementan migraciones.
- No se activa CSRF global.
- No se implementa `StorageBackend`.
- No se implementa Markdown.
- No se cambia frontend.
- No se cambia Firebase.
- No se ejecutan descargadores reales.
- No se usan datos reales.
