# Precheck SQLite y migraciones

Este documento inventaria la persistencia actual antes de introducir migraciones SQLite formales.

Es una fase preparatoria. No se cambia SQLite, no se implementan migraciones, no se toca `app.py`, no se modifican endpoints, no se cambian respuestas JSON y no se modifica la base productiva.

## Estado actual

Persistencia:

- motor: SQLite;
- ruta productiva actual: `webapp/infonalia_webapp/data/infonalia.db`;
- constante: `DB_PATH`;
- conexion: `db()`;
- transaccion basica: `db_session()`;
- inicializacion de esquema: `init_db()`;
- evolucion aditiva historica: `ensure_column()`;
- semillas iniciales: `seed_users_and_settings()`.

Tablas creadas desde `init_db()`:

- `infonalia_dias`;
- `licitaciones`;
- `notificaciones`;
- `usuarios`;
- `app_settings`;
- `noticias`.

Indices creados desde `init_db()`:

- `idx_licitaciones_dia`;
- `idx_licitaciones_estado`;
- `idx_licitaciones_fecha_limite`;
- `idx_notificaciones_destino`;
- `idx_notificaciones_fecha`;
- `idx_usuarios_role`;
- `idx_noticias_status`;
- `idx_noticias_published`.

## Esquema actual resumido

`infonalia_dias`:

- `id`;
- `fecha` con `UNIQUE`;
- `titulo`;
- `estado`;
- `enviado_nuria_at`;
- `nuria_dirty_at`;
- `abierto_nuria_at`;
- `completado_at`;
- `reviewed_at`;
- `created_at`;
- `updated_at`.

`licitaciones`:

- `id`;
- `infonalia_dia_id`;
- `fecha_infonalia`;
- `expediente`;
- `objeto`;
- `organismo`;
- `provincia`;
- `tipo`;
- `presupuesto`;
- `fecha_limite`;
- `hora_limite`;
- `plataforma`;
- `enlace_perfil`;
- `enlace_infonalia`;
- `estado`;
- `comentario`;
- `ruta_carpeta`;
- `created_at`;
- `updated_at`.

`notificaciones`:

- `id`;
- `fecha_hora`;
- `usuario_origen`;
- `usuario_destino`;
- `asunto`;
- `cuerpo`;
- `ficheros_adjuntos`;
- `email_sent_at`;
- `email_error`;
- `read_at`.

`usuarios`:

- `username`;
- `password_hash`;
- `role`;
- `display_name`;
- `email`;
- `active`;
- `created_at`;
- `updated_at`.

`app_settings`:

- `key`;
- `value`;
- `updated_at`.

`noticias`:

- `id`;
- `title`;
- `slug` con `UNIQUE`;
- `excerpt`;
- `content`;
- `category`;
- `tags`;
- `featured_image`;
- `status`;
- `is_featured`;
- `published_at`;
- `author`;
- `created_at`;
- `updated_at`.

## Evolucion actual sin migraciones formales

La app no tiene todavia una tabla de migraciones ni un runner versionado.

El mecanismo historico es:

- `CREATE TABLE IF NOT EXISTS` para crear tablas si faltan;
- `ensure_column()` para anadir columnas si faltan;
- `CREATE INDEX IF NOT EXISTS` para crear indices si faltan;
- `seed_users_and_settings()` para crear usuarios/configuracion por defecto si faltan.

Este enfoque es util para cambios aditivos pequenos, pero no basta para cambios que requieran:

- renombrar columnas;
- eliminar columnas;
- cambiar tipos;
- anadir restricciones;
- transformar datos existentes;
- crear tablas de auditoria o jobs con migracion de datos;
- hacer rollback fiable.

## Invariantes que no deben romperse

- Los tests deben usar SQLite temporal cuando necesiten escribir.
- Los tests no deben tocar `webapp/infonalia_webapp/data/infonalia.db`.
- La base productiva no debe abrirse para pruebas automatizadas de migracion.
- Las migraciones futuras deben ser idempotentes.
- Cualquier cambio de esquema debe tener backup previo y plan de rollback.
- `ruta_carpeta` debe conservar compatibilidad hasta que exista StorageBackend probado.
- La tabla `noticias` debe conservar compatibilidad con `content` hasta que exista plan Markdown seguro.
- Usuarios y `app_settings` no deben perderse al reejecutar inicializacion.
- `POST /api/import/csv`, `POST /api/import/msg` y descargas deben seguir pudiendo usar SQLite temporal en tests.
- No se deben usar datos reales en fixtures.

## Riesgos antes de migraciones

- `init_db()` concentra creacion, evolucion aditiva y semillas.
- No hay historial versionado de schema.
- `ensure_column()` solo cubre columnas nuevas; no valida definicion real de columnas existentes.
- Cambios destructivos podrian afectar datos productivos si se prueban contra `DB_PATH`.
- No existe tabla `schema_migrations`.
- No existe snapshot automatico del esquema actual.
- SQLite tiene limites de concurrencia para escenarios de mayor uso.
- El modelo actual no impone `UNIQUE(expediente, organismo)` aunque la deduplicacion logica usa esos campos.

## Estrategia recomendada antes de implementar

Orden seguro:

1. Generar snapshot documental del esquema productivo antes de tocarlo.
2. Hacer backup de `webapp/infonalia_webapp/data/infonalia.db`.
3. Crear una copia temporal de la base para ensayar la migracion.
4. Introducir una tabla `schema_migrations` solo con tests especificos.
5. Mantener `init_db()` compatible durante una fase de transicion.
6. Escribir migraciones idempotentes y con version unica.
7. Probar migracion sobre SQLite temporal y sobre copia de base, nunca sobre datos reales.
8. Verificar downgrade o rollback operativo si la migracion falla.
9. Ejecutar checks completos antes de commit local.

## Tests existentes relevantes

- `test_app_import_does_not_start_server_or_create_productive_db`;
- `test_csv_import_endpoint_accepts_small_valid_csv_with_temp_db`;
- tests de importacion que sustituyen `DATA_ROOT`, `DOWNLOAD_ROOT` y `DB_PATH`;
- tests de descarga que usan SQLite temporal y `subprocess.run()` simulado;
- tests de login que validan sesiones sin tocar SQLite productiva.

## Checks minimos antes de una migracion real

- `git status --short --untracked-files=all`;
- `.\.venv\Scripts\python.exe -m pytest -q`;
- `.\.venv\Scripts\python.exe -m compileall webapp herramientas_python`;
- `node --check webapp/infonalia_webapp/static/app.js`;
- `node --check webapp/infonalia_webapp/static/public.js`;
- `node --check firebase/public_firebase/static/public.js`;
- `git diff --check`.

## Fuera de este precheck

- No se cambia SQLite.
- No se implementan migraciones.
- No se crea `schema_migrations`.
- No se toca `app.py`.
- No se modifica la base productiva.
- No se cambian endpoints.
- No se cambian respuestas JSON.
- No se anaden dependencias.
- No se usan datos reales.
