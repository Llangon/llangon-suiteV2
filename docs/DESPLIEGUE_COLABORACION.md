# Despliegue Para Trabajar En Equipo

## Opción inicial

Para una prueba interna puede usarse un único PC como anfitrión. Ese equipo mantiene la aplicación encendida y los demás usuarios acceden desde el navegador.

Antes de abrir el acceso a la red, debe completarse una prueba local en `127.0.0.1`, cambiar todas las credenciales de ejemplo y confirmar las reglas del cortafuegos.

## Preparación del anfitrión

1. Crear un entorno virtual en `webapp/infonalia_webapp/`.
2. Instalar `requirements.txt`.
3. Copiar `.env.example` como `.env`.
4. Configurar usuarios, contraseñas únicas y rutas locales.
5. Probar primero con `INFONALIA_HOST=127.0.0.1`.
6. Mantener desactivadas las automatizaciones no imprescindibles hasta validar la configuración local.

La prueba local se abre en:

```text
http://127.0.0.1:8787
```

Para una prueba autorizada dentro de la red local puede configurarse:

```text
INFONALIA_HOST=0.0.0.0
```

Los demás equipos accederían mediante:

```text
http://IP_DEL_PC_ANFITRION:8787
```

No debe exponerse este servidor directamente a Internet.

## Raiz local de Dropbox

En despliegue real la app debe trabajar contra la carpeta local sincronizada por Dropbox Desktop configurada con:

```text
LLANGON_DROPBOX_BASE_PATH=C:\Users\USUARIO\Dropbox\00000 LLANGON
```

No debe hardcodearse una ruta absoluta en codigo. Si para desarrollo se necesita una replica local, debe configurarse explicitamente con `INFONALIA_DROPBOX_ROOT` o `INFONALIA_MONITOR_ROOT`; la aplicacion no debe caer por defecto a una ruta fija.

Configuracion local real recomendada:

```text
INFONALIA_STORAGE_BACKEND=local
LLANGON_DROPBOX_BASE_PATH=C:\Users\USUARIO\Dropbox\00000 LLANGON
INFONALIA_DROPBOX_ENABLED=0
INFONALIA_DROPBOX_DRY_RUN=1
```

Configuracion opcional de replica explicita, solo si se quiere aislar pruebas:

```text
INFONALIA_DROPBOX_ROOT=C:\RUTA\A\REPLICA_LOCAL
```

Si `LLANGON_DROPBOX_BASE_PATH` esta configurada, tiene prioridad sobre `INFONALIA_DROPBOX_ROOT`. Si `INFONALIA_DROPBOX_ROOT` esta definido pero la carpeta no existe, debe corregirse la ruta del `.env`; no se debe caer a una ruta hardcodeada.

## Dropbox local real para despliegue

En despliegue final por VPN se usa Dropbox Desktop real: la app corre en el PC anfitrion, los descargadores escriben en una carpeta local de Dropbox Desktop y Dropbox sincroniza.

Con este modo se conserva el comportamiento ya probado de los descargadores: si un fichero existe se omite, si falta se descarga, y no se duplica por reintentos normales.

## Dropbox API incremental experimental

La integración API queda aparcada para una fase futura. El código permanece disponible, pero no es el flujo recomendado ahora y está desactivado por defecto:

```text
INFONALIA_STORAGE_BACKEND=local
INFONALIA_DOWNLOAD_STAGING_ROOT=.local_runtime/downloads
INFONALIA_DROPBOX_ENABLED=0
INFONALIA_DROPBOX_DRY_RUN=1
INFONALIA_DROPBOX_API_ROOT=/LlangonSuite
INFONALIA_DROPBOX_APP_KEY=
INFONALIA_DROPBOX_APP_SECRET=
INFONALIA_DROPBOX_REFRESH_TOKEN=
INFONALIA_DROPBOX_NON_DESTRUCTIVE=1
```

Para una prueba futura sin subir nada:

1. Configurar `INFONALIA_STORAGE_BACKEND=dropbox`.
2. Mantener `INFONALIA_DOWNLOAD_STAGING_ROOT=.local_runtime/downloads` o apuntarlo a otra carpeta fuera de Dropbox Desktop.
3. Configurar `INFONALIA_DROPBOX_ENABLED=1`.
4. Mantener `INFONALIA_DROPBOX_DRY_RUN=1`.
5. Usar `GET /api/storage/status` y `POST /api/storage/dropbox/dry-run`.
6. Ejecutar una descarga simulada en entorno de pruebas y revisar el manifest local `.infonalia_dropbox_manifest_*.json`.

Cuando se desactive dry-run deben existir las tres credenciales. La app no devuelve tokens al frontend ni los guarda en SQLite.

La política Dropbox es incremental y no destructiva:

- la carpeta remota estable es `/LlangonSuite/Licitaciones/{expediente}_{id}/`;
- la carpeta local previa de descarga, cuando el backend es Dropbox API, debe estar fuera de Dropbox Desktop;
- si la carpeta existe, se reutiliza;
- si un fichero remoto existe, se salta;
- si un fichero remoto falta, se sube;
- no se usa overwrite, update, delete, move destructivo ni autorename para documentos;
- los manifests se guardan en `_manifests/` y pueden usar sufijo seguro para no sobrescribirse.

Para mantenerse en el flujo principal basta con dejar `INFONALIA_STORAGE_BACKEND=local` y `INFONALIA_DROPBOX_ENABLED=0`.

## Seguridad

Antes de una prueba compartida:

- usar usuarios individuales,
- usar contraseñas largas y únicas,
- mantener desactivado el alias de administrador,
- restringir el acceso a la red interna,
- preparar copias de seguridad de SQLite,
- comprobar que los datos locales siguen ignorados,
- no reutilizar credenciales corporativas en el entorno de prueba.

Para acceso externo se necesita un despliegue privado con HTTPS, autenticación reforzada y una revisión específica de seguridad.

## Límites actuales

- SQLite es adecuado para pruebas y equipos pequeños, no para alta concurrencia.
- El PC anfitrión debe permanecer encendido.
- La aplicación no debe publicarse mediante Firebase Hosting; Firebase contiene únicamente la web pública estática.
- Los descargadores dependen de plataformas externas y deben probarse individualmente.

