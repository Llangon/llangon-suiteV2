# Informe de reconstrucción documental

## Resultado

Se creó una base nueva de 18 documentos, reconstruida el 04/09/2026 y contrastada con operación real el 12/09/2026. Los documentos históricos no se borraron ni se reescribieron; `CODEX_CONTEXT.md` y `COMANDOS_DESARROLLO.md` sí se actualizaron como puente operativo hacia la nueva base. La reconstrucción diferencia:

- versión consolidada en Git;
- realidad del árbol local sin commit;
- capacidad técnica probada;
- capacidad técnica, activación local comprobada y conectividad externa no probada;
- decisiones aprobadas, propuestas y elementos retirados.

## Hallazgos principales

1. El núcleo privado es considerablemente más completo que varios contextos antiguos: 1.452 pruebas actuales, monitor e2e, orquestador, clientes/envíos, IA dual e importador robusto.
2. El árbol local contiene una segunda etapa importante no consolidada: router profundo, auto-seguimiento, Ficha y portal.
3. Ficha tiene versión real 2.1.0, no 2.0.1.
4. El portal tiene dos arquitecturas públicas alternativas y carece de decisión final.
5. Las rutas POST experimentales de portal no entraban en la protección CSRF manual; se corrigieron y probaron.
6. El esquema privado de portal evita las migraciones numeradas.
7. Justificaciones de baja es código completo pero producto retirado.
8. Trello/Noloco y auditoría 360 son propuestas, no roadmap aprobado.
9. App, SQLite, tareas, backups y activaciones locales quedaron verificadas. Los despliegues públicos y conexiones externas siguen sin probarse.
10. Se detectó una descarga vinculada a correo atascada en `running` desde julio; se muestra en salud operativa sin alterar el dato.
11. El heartbeat del scheduler anterior ya no describe KeeperTick; el diagnóstico usa la tarea Windows real.
12. Dos valores por defecto mostrados por el frontend (06:00 y 60 min) contradecían al backend (08:00 y 240 min); se alinearon.

## Documentos que dejan de ser fuente activa recomendada

- `docs/ROLES_Y_FLUJO.md` por estados/roles obsoletos.
- `docs/ARQUITECTURA_FUTURA.md` como “futuro”; hoy es un diario de evolución.
- `docs/FICHA_LLANGON_V2.md` hasta alinear versiones.
- `docs/WEB_PUBLICA_CAMBIOS.md` porque describe una versión revertida.
- `PROJECT_CONTEXT.md` y snapshots antiguos sin contraste.

`docs/CODEX_CONTEXT.md` sigue formalmente segundo en la jerarquía de `AGENTS.md` y ahora remite expresamente a esta base maestra; no fue necesario alterar `AGENTS.md`.

## Control de calidad realizado

### Cobertura temática

- [x] Arquitectura privada y pública.
- [x] SQLite, migraciones, entidades y estados.
- [x] APIs y módulos funcionales.
- [x] Dropbox, correo, Outlook, Telegram, IA, Cloudflare y plataformas.
- [x] Automatizaciones, horarios y tareas Windows.
- [x] Seguridad, despliegue, backups y recuperación.
- [x] Reglas críticas e idempotencia.
- [x] Ficha Excel y frontera futura Suite↔Excel.
- [x] Propuestas, descartes, decisiones y roadmap actual.
- [x] Trazabilidad Git/documentos/conversaciones.

### Segunda pasada de consistencia

- [x] A–E definidos una sola vez y usados de forma consistente.
- [x] Portal/Ficha no se presentan como producción.
- [x] Justificaciones no se presenta como módulo activo.
- [x] Las horas vigentes son coherentes en documentos.
- [x] Siete estados de licitación coherentes.
- [x] Baseline/marcador/sidecar tienen una sola autoridad cada uno.
- [x] Las cifras de prueba incluyen causa y repetición válida.
- [x] No se incluyeron credenciales ni valores de `.env`.
- [x] Las incertidumbres usan la etiqueta requerida.

## Acciones no realizadas

No se movió/eliminó documentación, no se tocó `README.md`, `PROJECT_CONTEXT.md` ni archivos históricos. Se inspeccionaron datos reales únicamente mediante snapshot/solo lectura y se exportaron tareas. No se desplegó, no se descargó, no se envió correo/Telegram y no se cambió estado remoto.

## Ampliación operativa del 12/09/2026

- Punto previo íntegro y restauración en una orden verificados fuera del repositorio.
- Contrato automático de esquema, roles, estados, tareas, rutas y plataformas.
- Healthcheck funcional con niveles OK/DEGRADADO/ERROR y política sin conexiones externas.
- Dashboard de excepciones integrado en Automatizaciones, separado conceptualmente de Agenda.
- Cierre CSRF del portal experimental.
- Defaults visuales de Agenda/reconciliación corregidos.
- Pruebas de regresión para escritura cero, privacidad, permisos, contrato, tareas Windows, dashboard y CSRF.

## Recomendación de adopción

Usar `00_INDICE_MAESTRO.md` y `CONTEXTO_MAESTRO_LLANGON_SUITE.md` como fuentes principales de un proyecto ChatGPT. Añadir documentos temáticos solo según necesidad. Mantener `99_TRAZABILIDAD_Y_FUENTES.md` disponible para verificar por qué una afirmación se considera vigente.
