# Precheck StorageBackend

Este documento inventaria el flujo actual de descargas antes de introducir cualquier implementacion real de `StorageBackend`.

Es una fase preparatoria. No implementa Dropbox, no cambia `app.py`, no cambia SQLite, no cambia endpoints y no ejecuta descargadores reales.

## Puntos actuales del flujo

Entrada desde UI:

- `POST /api/licitaciones/{id}/descargar`;
- frontend: `downloadLicitacion()` en `webapp/infonalia_webapp/static/app.js`;
- backend: `InfonaliaHandler.api_download_licitacion()`.

Funciones y constantes implicadas:

- `api_download_licitacion()`;
- `resolve_destination_folder()`;
- `write_http_url()`;
- `validate_resolved_destination()`;
- `validate_download_url()`;
- `scan_download_folder()`;
- `validate_download_folder_limits()`;
- `folder_path_for_storage()`;
- `find_dropbox_root()`;
- `DOWNLOAD_ROOT`;
- `LAUNCHER_PATH`;
- `MAX_DOWNLOAD_RUNTIME_SECONDS`;
- `MAX_DOWNLOAD_TOTAL_BYTES`;
- `MAX_DOWNLOAD_FILE_COUNT`.

Ejecucion externa:

- `subprocess.run()`;
- comando base: Python actual, `LAUNCHER_PATH`, URL validada;
- `cwd` es la carpeta destino;
- stdout y stderr se capturan;
- hay timeout por `MAX_DOWNLOAD_RUNTIME_SECONDS`.

Descargador orquestador:

- `herramientas_python/Descargar_Licitacion.py`;
- puede ejecutarse desde una carpeta que contenga `HTTP.url`;
- delega en descargadores de plataforma.

## Persistencia actual

Campo persistido:

- `licitaciones.ruta_carpeta`.

Reglas actuales:

- si ya hay `ruta_carpeta`, se intenta resolver como ruta Dropbox o ruta absoluta;
- si no hay `ruta_carpeta`, se usa Dropbox local si existe;
- si no hay Dropbox local, se usa `DOWNLOAD_ROOT`;
- `ruta_carpeta` se guarda como ruta visible mediante `folder_path_for_storage()`;
- no existen todavia `storage_backend`, `storage_uri`, `file_manifest` ni `download_jobs`.

## Invariantes que no deben romperse

- El endpoint debe seguir requiriendo rol administrador.
- La ruta mutante debe seguir protegida por CSRF.
- Solo se deben aceptar URLs `http` o `https`.
- El destino resuelto debe permanecer dentro de `DOWNLOAD_ROOT` o Dropbox local detectado.
- `HTTP.url` se escribe en la carpeta destino antes de lanzar el descargador.
- `ruta_carpeta` solo debe actualizarse si:
  - `subprocess.run()` termina con codigo `0`;
  - la carpeta descargada supera las validaciones de tamano y numero de ficheros.
- Si hay timeout, fallo de proceso, URL insegura, destino inseguro o limites superados, no se debe marcar `ruta_carpeta` como descarga correcta.
- Los tests no deben tocar la SQLite productiva.
- Los tests no deben ejecutar red ni descargadores reales.

## Riesgos actuales

- Los descargadores escriben directamente en la carpeta destino.
- Puede quedar una carpeta parcial si el proceso falla despues de escribir `HTTP.url` o ficheros parciales.
- No hay manifest con nombre, tamano, hash y origen de cada fichero.
- No hay `DownloadJob` persistente.
- No hay separacion clara entre ruta visible, ruta local y URI logica.
- Dropbox depende hoy de una carpeta local detectada, no de Dropbox API.
- El limite de tamano y numero de ficheros se valida al final, no durante cada escritura.

## Estrategia recomendada antes de implementar

Orden seguro:

1. Mantener `ruta_carpeta` por compatibilidad.
2. Crear primero una implementacion local pura o casi pura, sin Dropbox API.
3. Hacer que la descarga escriba en temporal controlado.
4. Escanear el temporal y crear manifest.
5. Confirmar almacenamiento local.
6. Solo despues actualizar `ruta_carpeta`.
7. Conservar tests existentes de fallo, timeout, URL insegura, destino inseguro y limites.
8. Introducir Dropbox real solo cuando LocalStorage este probado.

## Tests existentes que protegen el flujo

- `test_download_endpoint_success_updates_ruta_carpeta_with_mocked_subprocess`;
- `test_download_route_success_with_valid_csrf_and_mocked_subprocess`;
- `test_download_route_rejects_missing_csrf_before_subprocess`;
- `test_download_route_rejects_invalid_csrf_before_subprocess`;
- `test_download_endpoint_failure_does_not_update_ruta_carpeta`;
- `test_download_endpoint_timeout_does_not_update_ruta_carpeta`;
- `test_download_endpoint_folder_limit_failure_does_not_update_ruta_carpeta`;
- `test_download_endpoint_rejects_file_url_without_subprocess`;
- `test_download_endpoint_rejects_empty_url_without_subprocess`;
- `test_download_endpoint_rejects_unsafe_destination_without_subprocess`.

## Fuera de este precheck

- No se implementa `StorageBackend`.
- No se implementa Dropbox.
- No se crea `DownloadJob`.
- No se cambia SQLite.
- No se toca `api_download_licitacion()`.
- No se ejecutan descargadores reales.
