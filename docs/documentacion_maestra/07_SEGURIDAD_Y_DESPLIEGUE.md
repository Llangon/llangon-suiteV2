# Seguridad y despliegue

## Modelo de exposición

- Suite privada: solo `127.0.0.1:8787`.
- Web corporativa: Firebase estático, sin acceso a datos privados.
- Portal por licitación: superficie pública separada; B.
- Nunca exponer la Suite en `0.0.0.0` ni mediante túnel sin autorización y controles adicionales.

Los scripts locales modificados refuerzan loopback, pero esos cambios no están consolidados.

## Autenticación

- Usuarios en SQLite con roles `admin` y `nuria`.
- Contraseñas nuevas: PBKDF2-SHA256, 120.000 iteraciones.
- Compatibilidad de verificación con texto legacy. Verificación del 12/09/2026: los dos usuarios reales usan PBKDF2-SHA256; cero contraseñas legacy detectadas.
- Sesión stateless firmada HMAC-SHA256, con usuario, rol, emisión y token CSRF; máximo 10 horas.
- Cookie `HttpOnly`, `SameSite=Lax`, `Path=/`; atributo `Secure` cuando corresponde.
- Rate limit de login en memoria: 5 intentos/5 minutos por IP+usuario por defecto. Se reinicia con el proceso y no es distribuido.

## Autorización

Admin controla configuración, usuarios, almacenamiento, importaciones manuales, automatizaciones y operaciones sensibles. Nuria revisa licitaciones y usa módulos permitidos. “Técnico” describe una función humana, no un rol de aplicación.

El modo mantenimiento bloquea usuarios no admin.

## CSRF

Las mutaciones conocidas autenticadas exigen cabecera `X-CSRF-Token`; login queda exento. El frontend obtiene el token de `/api/me`. La protección es una lista/rule-set manual, por lo que toda ruta nueva debe añadirse expresamente.

Los POST experimentales `portal-preview/generate` y `portal-publications/*` omitían inicialmente `is_known_mutating_route`. Se incorporaron al control central y existe una prueba que recorre generar, publicar, recuperar, rotar código, aprobar y sincronizar.

## Cabeceras y frontend

- CSP privada estricta basada en `self`, sin objetos ni framing.
- `X-Frame-Options: DENY`, no-sniff y política de caché privada `no-store`.
- Scripts externos/inline evitados en entrypoints.
- URLs, atributos, clases CSS y Markdown se normalizan/escapan.
- El login solo acepta retorno bajo `/app`, evitando open redirect.

## Rutas y ficheros

- Las operaciones se limitan a raíces configuradas.
- Se rechazan rutas absolutas impropias, traversal y symlinks peligrosos.
- Los marcadores se crean vacíos, con nombre exacto y sin sobrescribir.
- Descargas parciales o HTML/captcha no se publican como documento válido.
- Credenciales de plataformas y servicios son write-only en payloads públicos.

## Portal público B

El servidor local rechaza bind no-loopback; la exposición prevista sería el túnel del puerto 8790, nunca 8787. La variante cloud usa código derivado con PBKDF2 (210.000 iteraciones), cookie firmada de 12 h `Secure`/`SameSite=Strict`, D1/R2 y API administrativa. Ambas registran accesos/descargas.

Además de CSRF privado, faltan confirmar despliegue, dominio, secreto de sincronización, retención y arquitectura elegida. **⚠️ PENDIENTE DE VERIFICACIÓN**.

## Backups

### SQLite

Se usa la API de backup SQLite, no copia bruta de una base abierta. Retención local por defecto: 30 copias.

### Backup completo

ZIP privado restaurable que crea primero backup SQLite, manifiesto y política diaria/mensual (30/12 según la documentación). Puede incluir secretos si se configura, por lo que su destino Dropbox debe ser privado y nunca una carpeta compartida.

Antes de modificar el sistema se creó el snapshot externo:

`C:\LLANGON_BACKUPS\PRE_AUDITORIA_LLANGON_20260912_104722`

Incluye árbol completo, `.git`, configuración y `.env` opacos, SQLite mediante API segura, tareas Windows exportadas, estado, manifiesto, hashes y script autónomo. La base pasa `integrity_check`; 2.461 archivos críticos se restauraron en una ubicación aislada con cero diferencias; el script pasó `-ValidateOnly` sin mutar el sistema.

Restauración en una orden:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\LLANGON_BACKUPS\PRE_AUDITORIA_LLANGON_20260912_104722\RESTORE_PRE_AUDITORIA.ps1"
```

## Arranque y salud

Los scripts Windows arrancan el proceso y consultan `/api/health`. El healthcheck local esperado es `http://127.0.0.1:8787/api/health`; debe conservar la respuesta mínima exacta. La auditoría funcional ampliada es admin-only y abre SQLite en solo lectura. El 12/09/2026 la aplicación estaba activa en loopback y las tareas Windows funcionaban.

## Riesgos priorizados

1. Portal sin migración privada versionada.
2. Dos arquitecturas públicas simultáneas no decididas.
3. Cambios locales extensos sin commit, aunque existe snapshot externo verificado.
4. Descarga histórica atascada y vinculada a una orden por correo.
5. Rate limiting solo en memoria.
6. `app.py` monolítico.
7. Advertencia `pypdf`: uso de `replace_contents()` quedará incompatible con pypdf 7 si no se adapta.
8. Conectividad externa y despliegue público no verificados; solo se comprobó preparación local.
