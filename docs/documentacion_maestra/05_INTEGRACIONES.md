# Integraciones

## Matriz

| Integración | Finalidad | Estado |
| --- | --- | --- |
| Dropbox Desktop / filesystem | Carpeta documental operativa | A |
| Dropbox API | Subida incremental no destructiva | B |
| IMAP | Importación Infonalia y acciones por correo | A; procesos activos y configuración preparada; conexión no probada |
| SMTP | Resúmenes, avisos y notificaciones | A; activo y configuración preparada; envío no probado |
| Outlook COM | Borradores `.msg` | A en Windows compatible; fallback EML |
| Telegram | Avisos internos y diagnósticos | A; activo y configuración preparada; envío no probado |
| Gemini / Codex Local | Análisis IA remoto o local | A; proveedor efectivo preparado; petición no probada |
| Plataformas públicas | Descarga/monitor | A para siete plataformas |
| Firebase Hosting | Web corporativa | A en código; despliegue real no verificado |
| Cloudflare | Portal público/túnel/D1/R2 | B |
| Trello/Noloco y similares | Portal colaborativo externo | D |

## Dropbox y sistema de archivos

La vía principal es la carpeta local sincronizada por Dropbox Desktop. `LLANGON_DROPBOX_BASE_PATH` define conceptualmente la raíz; no se documenta su valor. Las rutas se resuelven dentro de raíces permitidas, rechazan traversal y enlaces simbólicos peligrosos. `{id}.llangon` permite reconciliar carpetas movidas y `EnSeguimiento.llangon` activa seguimiento.

El backend Dropbox API puede probar configuración y hacer dry-run/subida incremental sin borrar. No es autoridad de seguimiento y no puede sustituir el marcador físico. Errores deben registrarse sin convertir una subida parcial en éxito.

## Correo IMAP

Dos consumidores comparten patrón:

- importador Infonalia: busca mensajes estructurados no leídos dentro de ventana temporal;
- procesador de acciones: busca asuntos candidatos `LLANGON_CMD`.

Se usa lectura PEEK para no marcar al descargar. Persistencia y marcado de leído se separan. Claims e identificadores de mensaje evitan doble proceso. Contraseñas y remitentes se configuran en ajustes/entorno y nunca se exponen por API.

## SMTP

Se usa para revisión diaria, Agenda, IA, monitor y avisos preparados. Los modos dry-run no llaman al servidor. La falta de SMTP produce error controlado y no debe invalidar una operación principal ya persistida. En monitor, email y Telegram son canales independientes.

## Outlook

Clientes/envíos crea borradores, no envíos automáticos. En Windows intenta Outlook COM para `.msg`; si no está disponible genera `.eml`. La apertura del borrador también es acción local explícita. No existe seguimiento automático de respuestas.

## Telegram

Canal interno para avisos de acciones/importación/monitor y pruebas de estado. Los usuarios pueden tener chat configurado y existe un canal/grupo operativo. No hay portal cliente por Telegram. Un fallo no revierte la operación de negocio ni bloquea email.

## Gemini

Usa una clave privada, modelo configurable, límites por minuto/día, timeout, cooldown tras 429, tamaño/número de documentos y modos texto/PDF/auto. Clasifica errores de autorización, modelo, red, timeout, 429, 503 y 504; redacta secretos de diagnósticos. No debe llamarse si está deshabilitado o no configurado.

## Codex Local

El worker copia únicamente documentos seleccionados a un workspace, ejecuta `codex exec` sin shell, ignora configuración de usuario, usa sandbox y salida JSON. Tiene timeout, límite de ficheros/tamaño y diagnóstico acotado. Los originales no se modifican.

## Plataformas de contratación

La integración es de lectura/descarga. Cada adaptador devuelve un contrato estructurado de inventario y completitud. Captchas, recaptcha, cambios de estructura o transporte generan estado parcial/fallo; nunca se debe inferir una retirada a partir de una lectura incompleta. No se ejecutaron accesos reales en esta auditoría.

## Firebase

Sirve únicamente `firebase/public_firebase`, con rewrites SPA y cabeceras públicas. No expone la SQLite ni la aplicación privada. Noticias y zona privada permanecen fuera de navegación mientras no haya contenido/enlace real. **⚠️ PENDIENTE DE VERIFICACIÓN:** proyecto y versión desplegada.

## Cloudflare y portal

Diseño común: la Suite decide qué expediente/ficheros publicar; el público recibe solo ese modelo y ficheros; cada publicación tiene código; se auditan acceso y descarga.

- Variante local: `public_portal_server` en loopback 8790, túnel solo hacia ese proceso y API administrativa protegida por bearer.
- Variante cloud: Next/React/Vinext, D1 y R2, cookie de sesión firmada y código hash.

La app privada debe permanecer en loopback y no quedar detrás de un túnel público sin Access y autorización. **⚠️ PENDIENTE DE VERIFICACIÓN:** cuál variante se adopta, dominio, túnel y despliegue.

## Integraciones estudiadas, no existentes

Trello se estudió para coordinación; Noloco, ClickUp, Notion y Softr como alternativas de portal. La conversación más reciente recomendaba prototipar antes de integrar, no aprobó ni construyó una conexión. Se clasifican D.

## Regla de healthcheck

La auditoría funcional no autentica contra IMAP/SMTP, no llama al proveedor IA y no envía Telegram. Comprueba flags efectivos y presencia de configuración requerida sin devolver sus valores. Un servicio opcional desactivado es OK; una función activada con configuración incompleta es DEGRADADO. La conectividad real sigue marcada como **⚠️ PENDIENTE DE VERIFICACIÓN** porque probarla tendría efectos o usaría credenciales externas.
