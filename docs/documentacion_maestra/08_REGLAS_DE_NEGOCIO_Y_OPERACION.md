# Reglas de negocio y operación

Estas reglas son normativas para el corte documental. Si código y texto difieren, se abre una incidencia y no se “corrige” producción sin autorización.

## Revisión Infonalia

1. Toda entrada nueva se normaliza a `Importada`.
2. Admin puede descartar o enviar a Nuria.
3. Nuria decide `Descartada`, `Descargar para ver` o `Preparar ficha`.
4. Cerrar una revisión (`99`) autodescarta solo licitaciones incluidas que sigan `Importada` o `Enviada a Nuria`.
5. No altera decisiones ya tomadas ni otras licitaciones.
6. Una revisión cerrada no se reabre por editar estado/campos o crear actuación; solo por acción explícita.
7. Los anuncios previos no ofrecen acciones que presupongan pliegos definitivos.

## Correo

1. Solo se procesan remitentes configurados y códigos exactos.
2. Leer el contenido usa PEEK y no marca visto.
3. Éxito o duplicado ignorado puede marcarse leído.
4. Inválido/error solo se marca si `mark_invalid_read` está habilitado; por defecto no.
5. Dry-run no cambia leído, estado ni jobs.
6. La idempotencia usa identificador de mensaje, código y evento persistido.
7. `04` no actúa si IA por correo está deshabilitada.
8. `99` repetido sobre revisión cerrada se ignora de forma segura.
9. Una decisión tardía tras cierre puede aplicarse si el estado es elegible, con auditoría y alerta.
10. Estados avanzados quedan protegidos de regresión por correo.

## Importador IMAP Infonalia

1. Busca no leídos dentro del lookback configurado y carpeta dedicada.
2. Mensajes no estructurados se ignoran.
3. Persistir precede a marcar como leído.
4. Si falla marcar visto después de persistir, la importación permanece y se registra incidencia.
5. Claims impiden dos importaciones simultáneas del mismo mensaje.
6. Bloques/licitaciones usan claves estables para deduplicar.
7. Un mensaje viejo correctamente reconocido puede marcarse visto según configuración, sin reimportar.

## Descargas

1. Solo el descargador canónico implementa plataformas; wrappers delegan.
2. No escribir fuera de la raíz permitida.
3. Reutilizar documentos idénticos y conservar versiones cuando cambien.
4. No tratar captcha/HTML/error como PDF válido.
5. Un resultado parcial nunca confirma retiradas.
6. La retirada solo nace de inventario completo y confiable.
7. Cada job registra solicitud, resultado e incidencia.
8. Las pruebas no deben acceder a portales reales.

## Seguimiento y monitor

1. Solo existe seguimiento si está físicamente `EnSeguimiento.llangon`.
2. Un flag SQL o una caché no pueden sustituir el marcador.
3. La baseline autoritativa vive en `tender_monitor_baselines`.
4. El sidecar es reparable y descartable; no adelanta la baseline.
5. Primera revisión completa crea baseline sin avisar.
6. Forzar reconstrucción de baseline tampoco genera lote/aviso.
7. Respuesta parcial conserva la baseline previa.
8. Cambios confirmados forman lote idempotente.
9. Preguntas/respuestas nunca pasan por IA, aunque el título contenga “acta”.
10. Solo categorías configuradas pasan por IA.
11. Fallo IA no bloquea aviso sin análisis; fallo de un canal no bloquea otro.
12. Una licitación fallida no detiene el ciclo global.
13. Reintentar envío/IA de un lote no vuelve a descargar.
14. Incidencias múltiples se consolidan en un informe por ciclo.
15. Leases compartidos evitan competir descarga directa y monitor.

## Marcadores automáticos B

El cambio local crea `EnSeguimiento.llangon` tras primera/nueva descarga correcta o al elegir `Descargar para ver`/`Preparar ficha`. Solo procede si hay carpeta registrada y almacenamiento físico local/Dropbox Desktop; en Dropbox API se omite. Si la escritura falla, no debe fingirse seguimiento. Hasta consolidación sigue siendo B.

## IA

1. No llamar proveedor deshabilitado o no configurado.
2. Seleccionar solo documentos permitidos dentro de la carpeta.
3. Excluir preguntas, respuestas, Ficha de cliente e históricos/adjudicaciones previas.
4. Hash estable evita duplicar un análisis activo/equivalente.
5. Respetar límites de volumen, tiempo y consumo.
6. 429 difiere el job; errores permanentes lo cierran con código seguro.
7. No guardar JSON inválido, vacío, incoherente o con mojibake.
8. Cancelación posterior a proveedor impide guardar/enviar resultado.
9. Eliminar resumen no elimina documentos originales.
10. Codex Local opera sobre copias en workspace y sin shell.

## Agenda y actuaciones

1. Solo estados de licitación operativos alimentan Agenda: `Descargar para ver`, `Preparar ficha`, `Preparada`.
2. Actuaciones abiertas aparecen por plazo; las cerradas se ocultan salvo consulta explícita.
3. Elementos sin fecha se muestran en los paneles previstos, no se inventa una fecha.
4. Cerrar/cancelar fija trazabilidad de quién/cuándo.
5. No borrar una licitación o día que tenga una actuación abierta; relaciones cerradas pueden desvincularse.
6. La Agenda diaria usa el correo del usuario configurado y dry-run no envía.

## Clientes y envíos

1. Cliente se desactiva de forma reversible; no se elimina por defecto.
2. Un cliente inactivo no se asigna a una actuación nueva, pero relaciones históricas se conservan.
3. Selección de adjuntos debe quedar dentro de carpeta permitida.
4. Generar borrador no equivale a enviar.
5. La Suite nunca pulsa “Enviar” en Outlook ni marca enviado automáticamente.
6. Si Outlook COM falla/no existe, generar EML seguro.
7. El estado `enviado` requiere confirmación humana.

## Ficha Llangon B

1. La actualización de clientes es exclusivamente manual mediante botón.
2. No consultar SQLite al abrir ni en segundo plano.
3. La conexión a SQLite es read-only/query-only y bloquea escrituras.
4. Si la actualización falla, conservar la última caché válida.
5. Excel no escribe clientes ni licitaciones en la Suite.
6. El PDF final no sobrescribe un fichero existente.
7. Un borrador puede mostrar avisos; el PDF final bloquea errores de validación.
8. Excel y documentación deben declarar la misma versión en la próxima consolidación.

## Portal de licitación B

1. Seleccionar exactamente una Ficha PDF por publicación.
2. Las descargas adjuntas son explícitas; no publicar toda la carpeta.
3. Toda página de la Ficha debe quedar representada o conservada literalmente.
4. La IA enriquece, no decide publicar ni elimina contenido.
5. La vista previa y revisión humana preceden a publicación.
6. Cada publicación usa código propio hash; rotarlo invalida el anterior.
7. Solo se exponen ficheros aprobados y se registran accesos/descargas.
8. Notas internas, comentarios internos y SQLite nunca salen al portal.
9. La app privada permanece en loopback.
10. CSRF ya está cubierto; no publicar hasta cerrar migración y arquitectura pública.

## Backups y fallos

1. Backup SQLite mediante API SQLite.
2. Backup completo inicia por una copia SQLite coherente.
3. Un destino con secretos debe ser privado.
4. No suspender durante trabajo crítico.
5. Ningún fallo de notificación revierte silenciosamente una operación ya confirmada.
6. Toda recuperación debe preservar originales y dejar auditoría.

## Salud y observabilidad

1. `/api/health` es liveness mínimo; no añadirle dependencias opcionales ni consultas lentas.
2. La auditoría funcional debe ser admin-only, de solo lectura y no contactar servicios externos.
3. Estado global ERROR solo por fallo crítico; un componente opcional produce como máximo DEGRADADO.
4. Funciona implica silencio; un fallo o atasco se muestra con acción sugerida.
5. Reutilizar tablas, ejecuciones, incidencias y tareas existentes; no crear un registro paralelo sin necesidad.
6. Agenda contiene trabajo y vencimientos; Dashboard contiene excepciones operativas.
7. No cerrar automáticamente una descarga huérfana vinculada a correo sin preservar evento terminal, idempotencia y política de notificación.
