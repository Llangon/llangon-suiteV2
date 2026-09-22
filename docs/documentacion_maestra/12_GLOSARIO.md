# Glosario canónico

| Término | Definición vigente |
| --- | --- |
| Suite | Aplicación privada y sus procesos internos; no incluye automáticamente las webs públicas. |
| Día Infonalia | Lote de licitaciones recibidas/revisadas conjuntamente. |
| Revisión | Ciclo admin→Nuria con decisiones y cierre explícito. |
| Licitación | Entidad central del expediente de contratación. |
| Anuncio previo | Publicación preliminar con acciones reducidas. |
| Actuación | Tarea/incidencia con plazo, estado y posibles vínculos múltiples. |
| Agenda | Vista unificada de licitaciones operativas, actuaciones, eventos y envíos. |
| Cliente | Entidad fiscal/operativa con baja lógica. |
| Envío | Preparación y seguimiento de documentación destinada a un cliente. |
| Borrador | Correo `.msg`/`.eml` aún no enviado. |
| Descargador canónico | Implementación única de descarga bajo `herramientas_python`. |
| Inventario completo | Lectura confiable que puede confirmar altas, cambios y retiradas. |
| Resultado parcial | Lectura incompleta que nunca confirma retiradas. |
| Marcador de identidad | Fichero vacío `{id}.llangon` en una carpeta de licitación. |
| Marcador de seguimiento | Fichero vacío `EnSeguimiento.llangon`; autoridad de seguimiento. |
| Baseline | Último estado remoto confirmado guardado en SQLite para comparar. |
| Snapshot técnico | Caché/diagnóstico; no autoridad. |
| Ciclo monitor | Ejecución global que contiene revisiones de varias licitaciones. |
| Lote de diferencias | Conjunto idempotente de novedades confirmadas de una ejecución. |
| Lease/claim | Reserva persistente para evitar ejecución concurrente o duplicada. |
| Job | Unidad persistida de descarga o IA con estado y auditoría. |
| Q&A | Preguntas y respuestas oficiales de PLACE/Catalunya. |
| Ficha IA | Resumen estructurado generado a partir de documentos seleccionados. |
| Ficha Llangon | Libro Excel local y su PDF canónico; no es la ficha IA. |
| Bridge | Proceso Python llamado por Excel para lectura segura o generación PDF. |
| Portal de licitación | Superficie pública separada para una publicación y sus archivos. |
| Portal cliente general | Idea de área permanente por cliente; no existe. |
| Web pública | Web corporativa estática en Firebase, distinta del portal. |
| Admin | Rol con gestión y mutaciones sensibles. |
| Nuria | Rol de revisión/operación limitada. |
| Técnico | Función humana; no rol de aplicación. |
| Dry-run | Ejecución de diagnóstico sin efectos externos/persistentes previstos. |
| KeeperTick | Tarea Windows de mantenimiento del proceso, sin wake. |
| WakeTick | Tarea Windows que despierta el equipo en franjas decididas. |
| Healthcheck mínimo | `/api/health`; confirma únicamente que el proceso HTTP responde. |
| Auditoría funcional | Diagnóstico admin de solo lectura que clasifica componentes como OK, DEGRADADO o ERROR. |
| Contrato de sistema | Invariantes comprobables de migración, tablas, rutas, roles, estados, tareas y plataformas. |
| DEGRADADO | La Suite sigue disponible, pero un componente requiere atención; no equivale a caída total. |
| Dashboard operativo | Cabecera de Automatizaciones que prioriza excepciones; no sustituye la Agenda. |
| A/B/C/D/E | Clasificación Implantado/Parcial/Aprobado pendiente/Propuesta/Descartado. |
| ⚠️ PENDIENTE DE VERIFICACIÓN | Dato que no puede afirmarse con evidencia disponible y segura. |
