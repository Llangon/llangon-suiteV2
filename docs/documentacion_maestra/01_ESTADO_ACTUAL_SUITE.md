# Estado actual de Llangon Suite V2

## Resumen ejecutivo

La Suite privada es una aplicación local madura y ampliamente probada. El núcleo incluye recepción y revisión Infonalia, licitaciones, descargadores, seguimiento, Agenda, actuaciones, IA, comentarios, clientes, envíos, automatización, seguridad y diagnóstico operativo. El 12/09/2026 la aplicación estaba activa en loopback, SQLite era íntegra y el scheduler funcionaba mediante sus dos tareas Windows. La rama auditada contiene además un bloque grande de cambios locales sin commit: router mejorado, creación automática de marcadores de seguimiento, Ficha Llangon y dos implementaciones de portal público.

**Repositorio auditado:** rama `codex/monitor-licitaciones-e2e`, `HEAD 4877210` del 30/07/2026, igual a su rama remota. `main` está ocho commits por delante de `origin/main`, pero por detrás de la rama de monitor. El árbol de trabajo contiene 15 ficheros versionados modificados y numerosos componentes no versionados. Por tanto, “estado actual del disco” y “versión consolidada en Git” no son equivalentes.

## Matriz maestra

| Área | Estado | Evidencia y alcance |
| --- | --- | --- |
| Aplicación privada Python/SQLite | A | Servidor, SPA, autenticación, APIs y pruebas consolidadas. |
| Infonalia: CSV, MSG e importador IMAP | A | Importación idempotente, historial, incidencias y automatización. Proceso activado y configuración local preparada; conexión IMAP no probada durante la auditoría. |
| Revisión admin → Nuria → decisión | A | Estados y permisos actuales probados. |
| Descarga de siete plataformas | A | Fuente única en `herramientas_python`; pruebas sin descargas reales. Disponibilidad externa actual: ⚠️ PENDIENTE DE VERIFICACIÓN. |
| Preguntas y respuestas PLACE/Catalunya | A | Modelo neutral común; el resto no ofrece esa capacidad. |
| Monitor de licitaciones | A | Núcleo, API, UI, persistencia, reintentos e integración con avisos. Activo a las 08:00, 13:00 y 18:00; ciclo 237 completado el 12/09/2026. |
| Creación automática de `EnSeguimiento.llangon` | B | Cambio local no consolidado y probado en el árbol actual. |
| IA de licitaciones Gemini/Codex Local | A | Cola, worker, selección, límites, validación y notificaciones. Proveedor activo y preparado según configuración; no se hizo petición externa. |
| Contrato, salud y dashboard operativo | A | `/api/health` mínimo más auditoría admin de solo lectura con niveles OK/DEGRADADO/ERROR y panel centrado en excepciones. |
| Agenda y actuaciones | A | Calendario unificado, vencimientos, eventos, recordatorios e historial. |
| Comentarios unificados | A | Entidades múltiples, visibilidad interna/equipo y fijado. |
| Clientes y envíos | A | Clientes, baja lógica, envíos, adjuntos, borrador Outlook/EML y Agenda. |
| Navegación e interfaz móvil | A | SPA responsive con cajón móvil, controles táctiles y tarjetas específicas en vistas densas. No es una app móvil nativa. |
| Adjudicaciones | B | Hay contenido/criterios IA y estado final de oferta; no hay módulo autónomo de adjudicaciones. |
| Facturación | B | Solo datos operativos del cliente como `forma_facturacion`; no existe módulo contable. |
| Justificaciones de baja | E | Motor completo conservado, pero retirado de la interfaz por decisión de producto. |
| Noticias internas/públicas | B | Persistencia y Markdown seguro implantados; navegación privada oculta y web pública sin noticias reales. |
| Web corporativa Firebase | A | SPA estática separada. Despliegue/dominio real: ⚠️ PENDIENTE DE VERIFICACIÓN. |
| Ficha Llangon Excel/PDF | B | Implementación local no versionada; versión técnica 2.1.0, payload 1.1 y bridge 1.4.0. Integración web bidireccional no existe. |
| Portal público local por licitación | B | Backend público 8790, publicación, código de acceso y eventos; no versionado. Despliegue real: ⚠️ PENDIENTE DE VERIFICACIÓN. |
| Portal Cloudflare D1/R2 | B | Proyecto Next/React/Vinext/Sites no versionado y con lint correcto. Compite o sucede al portal local. Decisión final: ⚠️ PENDIENTE DE VERIFICACIÓN. |
| Trello/Noloco/ClickUp/Notion/Softr | D | Comparación conversacional; no hay integración ni decisión aprobada. |
| Auditoría diaria 360 automática | D | Propuesta detallada, sin implementación ni tarea programada verificable. |

## Capacidades operativas consolidadas

- Importar licitaciones y agruparlas por día Infonalia.
- Filtrar y revisar; enviar una revisión a Nuria; cerrar de forma explícita.
- Aplicar respuestas seguras recibidas por correo y poner descargas en cola.
- Descargar documentación de PLACE, Catalunya, Navarra, Euskadi, Madrid, Junta de Andalucía y Xunta de Galicia.
- Resolver y conservar identidad/historial de preguntas PLACE y Catalunya.
- Seguir licitaciones mediante marcador físico y baseline SQLite.
- Detectar documentos nuevos, modificados o retirados sin producir bajas falsas en respuestas parciales.
- Analizar documentación mediante el proveedor IA configurado, validar calidad y generar ficha/resumen PDF.
- Gestionar actuaciones, eventos, vencimientos, comentarios, clientes y envíos.
- Generar borradores de correo; el envío al cliente sigue siendo una acción humana.
- Administrar configuración funcional, usuarios, automatizaciones, monitor y diagnósticos.

## Estado de calidad

- `pytest --collect-only`: 1.452 pruebas recogidas.
- Primera ejecución: 974 superadas y 469 errores de preparación por acceso denegado al temporal global de pytest; no fueron fallos de aserción.
- Repetición con temporal nuevo y aislado: **1.452 superadas**, 13 advertencias de deprecación de `pypdf`; segunda ejecución mediante `scripts/run_tests.ps1`, también 1.452 superadas.
- `node --check`: correctos `app.js`, `login.js` y `firebase/public_firebase/static/public.js`.
- Portal Cloudflare: lint correcto.
- En la ampliación del 12/09/2026 se inspeccionaron en modo lectura SQLite, procesos, backups, tareas Windows y presencia/configuración de integraciones. No se realizaron descargas, accesos a buzones, envíos, mensajes, escrituras Dropbox ni cambios remotos.

## Estado operativo observado el 12/09/2026

- Proceso web activo en `127.0.0.1:8787`; healthcheck mínimo correcto.
- SQLite de 106.582.016 bytes: snapshot seguro, `integrity_check=ok`, migraciones completas hasta 0036 y contrato esencial completo.
- Dos usuarios activos (`admin` y `nuria`), ambos PBKDF2-SHA256; cero contraseñas legacy detectadas.
- `LlangonSuite-KeeperTick` y `LlangonSuite-WakeTick`: presentes, habilitadas y con último resultado 0. Sin tareas Llangon legacy detectadas.
- `monitor_licitaciones`: activado. `night_suspend`: desactivada explícitamente y no se modificó.
- Backups SQLite y completo encontrados dentro del umbral de 36 horas.
- IMAP, SMTP, IA y Telegram: funciones activas/preparadas según configuración; conectividad externa no comprobada.
- Incidencia real: descarga 53 de la licitación 372 en `running` desde el 21/07/2026; queda visible en el dashboard y no se modifica automáticamente.

## Limitaciones y riesgos principales

1. El backend concentra más de diez mil líneas en `app.py`; las extracciones reducen el riesgo, pero el acoplamiento sigue alto.
2. El árbol local no consolidado es voluminoso; no puede tratarse como una versión desplegable hasta versionarlo y revisar sus límites.
3. Las rutas POST nuevas del portal omitían el control CSRF global; se incorporaron a `is_known_mutating_route` y tienen regresión específica.
4. Las tablas privadas del portal se crean con `ensure_portal_schema`, no mediante una migración numerada.
5. Hay dos backends públicos de portal —servidor local+túnel y Cloudflare D1/R2— sin decisión final documentada.
6. La documentación de Ficha dice 2.0.1, pero el código, macros y manifiesto dicen 2.1.0.
7. La descarga histórica atascada impide nuevas solicitudes para esa licitación mientras no se cierre o reprocese de forma consciente.
8. El antiguo `monitor_scheduler_heartbeat` ya no representa al orquestador único; la salud usa KeeperTick como evidencia primaria y conserva aquella fila solo como fallback.
9. La conectividad real con proveedores externos y el despliegue de las superficies públicas siguen sin probarse para evitar efectos externos.
