# Portal de licitaciones mediante Cloudflare Tunnel

## Arquitectura activa

- Suite privada: `http://127.0.0.1:8787`.
- Portal público separado: `http://127.0.0.1:8790`.
- Cloudflare Tunnel publica únicamente el puerto `8790`.
- La suite privada no se expone a Internet.
- Cada `Ficha.pdf` crea un portal y una palabra clave independientes.
- El servidor público conserva accesos y descargas; la suite los incorpora automáticamente al abrir la pestaña `Portal web`.

## Variables necesarias

Añadir a `webapp/infonalia_webapp/.env`:

```text
LLANGON_PORTAL_BASE_URL=http://127.0.0.1:8790
LLANGON_PUBLIC_PORTAL_URL=https://licitaciones.llangon.es
LLANGON_PUBLIC_PORTAL_HOST=127.0.0.1
LLANGON_PUBLIC_PORTAL_PORT=8790
LLANGON_PORTAL_SYNC_SECRET=<valor aleatorio de 48 o más caracteres>
LLANGON_PORTAL_SESSION_SECRET=<otro valor aleatorio de 48 o más caracteres>
LLANGON_PORTAL_NOTIFY_EMAILS=info3@llangon.com
```

Las dos claves deben ser diferentes. No deben guardarse en Git ni enviarse por correo.

## Operación local

Arrancar:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_public_portal_server.ps1
```

Comprobar:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\status_public_portal.ps1
```

Detener:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop_public_portal_server.ps1
```

## Cloudflare Tunnel

Usar un túnel administrado desde Cloudflare y crear dos rutas de aplicación publicada:

```text
licitaciones.llangon.es  -> http://localhost:8790
licitaciones.llangon.com -> http://localhost:8790
```

Instalar el conector como servicio de Windows con el comando y token que muestra Cloudflare. El token y las credenciales quedan fuera del repositorio.

Referencias oficiales:

- https://developers.cloudflare.com/tunnel/setup/
- https://developers.cloudflare.com/tunnel/advanced/tunnel-tokens/

## Flujo de trabajo

1. Abrir la licitación en la suite y entrar en `Portal web`.
2. Seleccionar una única `Ficha.pdf` y los documentos descargables.
3. Generar y revisar la vista previa.
4. Guardar la palabra clave personal mostrada.
5. Pulsar `Publicar portal` y confirmar.
6. La suite carga todos los documentos, verifica la carga, activa el enlace y envía el aviso por email.
7. Al volver a la pestaña `Portal web`, se sincronizan y muestran accesos, descargas, fichero y fecha.

Si existen varias fichas de clientes, se repite el flujo para cada ficha. Cada una conserva su propia URL, clave y actividad.
