# Contexto maestro de Llangon Suite V2

**Corte:** 12/09/2026. Este documento es el contexto compacto; ante detalle o conflicto, consultar `00_INDICE_MAESTRO.md` y el documento temático.

## Identidad y límites

Llangon Suite V2 es una aplicación interna de contratación pública. La privada vive en `webapp/infonalia_webapp`, usa Python estándar, SPA JavaScript y SQLite, y debe escuchar solo en `127.0.0.1:8787`. La web corporativa estática vive en `firebase/public_firebase`. El portal público por licitación es una superficie distinta todavía parcial. Nunca mezclar estas tres áreas.

## Clasificación

- A: implantado técnicamente.
- B: parcial, no consolidado, desactivado o no desplegado.
- C: aprobado pendiente.
- D: propuesta/estudio.
- E: descartado/sustituido.

Código probado demuestra capacidad, no activación real. Usar `⚠️ PENDIENTE DE VERIFICACIÓN` si falta evidencia.

## Estado del repositorio

Rama auditada `codex/monitor-licitaciones-e2e`, HEAD `4877210`. El árbol local tiene cambios extensos no versionados/modificados: router, marcadores, Ficha y portal. Núcleo consolidado: A. Esos cambios: B.

## Módulos A

- Infonalia CSV/MSG/IMAP, días, historial e incidencias.
- Revisión admin→Nuria y acciones por correo.
- Licitaciones, centro, detalle, captura e historial.
- Descargadores de PLACE, Catalunya, Navarra, Euskadi, Madrid, Junta de Andalucía y Xunta.
- Q&A de PLACE y Catalunya.
- Monitor e2e, baselines, diferencias, IA y avisos.
- IA Gemini/Codex Local con cola, límites, validación y PDF.
- Agenda, actuaciones, comentarios.
- Clientes, baja lógica, envíos y borradores Outlook/EML.
- SPA responsive para escritorio y móvil; no existe app móvil nativa.
- Automatización interna y controles de seguridad.
- Contrato automático, auditoría funcional de solo lectura y dashboard de excepciones.

Estado local real: aplicación activa en 8787; SQLite íntegra y migrada a 0036; KeeperTick/WakeTick habilitadas; monitor activo; backups recientes; IMAP/SMTP/IA/Telegram preparados. No se probaron conexiones o envíos externos.

## Reglas esenciales

### Estados

Licitación: `Importada`, `Descartada`, `Enviada a Nuria`, `Descargar para ver`, `Preparar ficha`, `Preparada`, `Oferta enviada`. Roles: solo `admin` y `nuria`.

### Revisión/correo

Admin filtra y envía a Nuria; Nuria decide. Código 99 cierra y autodescarta únicamente pendientes. IMAP usa PEEK; se persiste antes de marcar visto; dry-run no muta; duplicados son idempotentes; estados avanzados no retroceden.

### Descarga/monitor

Solo el descargador canónico implementa plataformas. Resultado parcial no confirma retiradas. `EnSeguimiento.llangon` es autoridad de seguimiento; `tender_monitor_baselines` es autoridad de comparación; el sidecar es caché. Primera baseline y reconstrucción forzada no avisan. Q&A nunca pasa por IA. Canales email/Telegram fallan de forma independiente.

### IA

No invocar proveedor deshabilitado. Seleccionar solo PDF permitidos y excluir Q&A/Ficha/históricos. Hash evita duplicado. JSON inválido o de baja calidad no se guarda. Codex Local usa copias aisladas y subprocess sin shell.

### Clientes

La Suite genera borrador; una persona envía y marca enviado. Cliente inactivo no recibe relaciones nuevas, pero el histórico permanece.

## Automatización canónica

- Acciones correo: 10 min.
- Importación Infonalia: 30 min.
- Reconciliación: 240 min.
- Agenda: 08:00 laborables.
- Backup completo: 16:00; copia SQLite y ZIP recientes al auditar.
- Suspensión: 21:00 condicionada; override real desactivado.
- Monitor: 08:00/13:00/18:00; override real activo.
- Reinicio/cancelación y Telegram: manual/evento.
- Windows: KeeperTick + WakeTick; no tareas de negocio separadas.

## Seguridad

PBKDF2-SHA256, sesión HMAC 10 h, cookie HttpOnly/Lax, CSP, no-store y rate limit 5/5 min en memoria. Dos usuarios reales, ambos con hash PBKDF2 y roles válidos. Mutaciones conocidas —incluido portal experimental— requieren `X-CSRF-Token`. No exponer 8787. No tocar secretos, bases reales, runtime, correo, Dropbox, Telegram, descargas, backups o tareas Windows sin permiso explícito y respaldo suficiente.

## Salud y observabilidad

`/api/health` permanece público local y mínimo para KeeperTick. `/api/admin/operational-health` usa SQLite solo lectura y niveles OK/DEGRADADO/ERROR; comprueba contrato, storage, tareas, scheduler, backups, colas, monitor y preparación de integraciones sin llamadas externas. El panel vive al inicio de Automatizaciones y responde «¿Qué necesita atención ahora?». Agenda sigue siendo trabajo/vencimientos.

Incidencia abierta: `download_jobs.id=53`, licitación 372, está `running` desde 21/07/2026 y bloquea una nueva descarga de esa licitación. Detectada, no corregida silenciosamente por estar vinculada a una orden de correo.

## Trabajo B

### Ficha Llangon

Excel local versión técnica 2.1.0, payload 1.1, bridge 1.4.0. Actualiza clientes solo por botón, SQLite read-only, conserva caché si falla y genera PDF canónico. No existe Excel→SQLite ni sincronización bidireccional.

### Portal

Publica una Ficha PDF y adjuntos seleccionados, exige cobertura/revisión, código por publicación y eventos. Existen dos destinos: servidor local 8790+túnel y Cloudflare Next/Vinext+D1/R2. No hay decisión final. Las rutas POST privadas ya están en el mapa CSRF; las tablas privadas siguen sin migración numerada: no desplegar antes de resolver migración y arquitectura.

### Router/marcador automático

URLs profundas y creación automática de seguimiento tras descarga/decisión están probadas en el árbol local, pero no consolidadas.

## E y D

Justificaciones de baja: motor completo pero interfaz retirada (E). Estados/roles/horarios antiguos, tareas Windows legacy y web pública revertida: E. Trello/Noloco/otros portales y auditoría diaria 360: D.

## Ausencias

No hay módulos autónomos de adjudicación o facturación, portal cliente general, comentarios bidireccionales con cliente ni Q&A en cinco plataformas.

## Calidad actual

1.452 pruebas recogidas y superadas usando temporal aislado; 13 warnings pypdf. Los cuatro JS operativos pasan sintaxis y el portal Cloudflare pasa lint. El temporal global de pytest está bloqueado en este equipo y puede producir falsos errores de setup.

## Próximo trabajo legítimo

Revisar conscientemente la descarga 53; cerrar migración/arquitectura del portal; versionar cambios locales; alinear Ficha 2.1.0. No promover propuestas D al roadmap automáticamente.

## Restauración previa

Snapshot verificado: `C:\LLANGON_BACKUPS\PRE_AUDITORIA_LLANGON_20260912_104722`. Restaura árbol, configuración, SQLite y tareas Windows en una orden mediante `RESTORE_PRE_AUDITORIA.ps1`; consulta `07_SEGURIDAD_Y_DESPLIEGUE.md`.
