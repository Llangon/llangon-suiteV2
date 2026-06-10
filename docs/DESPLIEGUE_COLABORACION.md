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
6. Mantener `INFONALIA_MONITOR_INTERVAL_MINUTES=0` hasta validar el monitor por separado.

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

## Dropbox

La ubicación se configura sin fijar una ruta específica de un equipo:

```text
INFONALIA_DROPBOX_ROOT=%USERPROFILE%\Dropbox\00000 LLANGON
```

Si Dropbox se encuentra en otra unidad, debe indicarse en el `.env` local.

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

