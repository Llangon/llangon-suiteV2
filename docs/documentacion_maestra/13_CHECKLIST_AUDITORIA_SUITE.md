# Checklist de auditoría de la Suite

## 1. Preparación segura

- [ ] Leer `AGENTS.md`, `docs/CODEX_CONTEXT.md` y `docs/COMANDOS_DESARROLLO.md` completos.
- [ ] Confirmar rama, HEAD, remotos, commits divergentes y árbol sucio.
- [ ] No leer `.env`, secretos, bases reales, runtime, logs o backups.
- [ ] No ejecutar correo, Dropbox, Telegram, descargas, tareas Windows o backup real salvo autorización expresa y rollback validado.
- [ ] Si habrá cambios sensibles, crear snapshot externo, manifiesto, hashes, backup SQLite seguro y rollback de una orden antes de modificar.
- [ ] Conservar cambios no relacionados del usuario.

## 2. Inventario

- [ ] Enumerar código, módulos, tests, scripts, docs y proyectos públicos.
- [ ] Separar versionado, modificado y no versionado.
- [ ] Enumerar migraciones y tablas desde código, no desde base real.
- [ ] Enumerar familias de API y mutaciones.
- [ ] Enumerar estados, roles, horarios y variables conceptuales.
- [ ] Revisar historial Git cronológico.
- [ ] Revisar conversaciones accesibles realmente relacionadas y registrar límites.

## 3. Clasificación

- [ ] Asignar A/B/C/D/E a cada módulo/integración/iniciativa.
- [ ] No equiparar pruebas con activación de producción.
- [ ] No equiparar archivo local no versionado con entrega consolidada.
- [ ] Marcar dudas exactamente `⚠️ PENDIENTE DE VERIFICACIÓN`.
- [ ] Resolver contradicciones por fecha, decisión posterior e implementación.

## 4. Seguridad

- [ ] Revisar autenticación, roles, cookies, rate limit y mantenimiento.
- [ ] Comparar todas las rutas mutantes con `is_known_mutating_route`.
- [ ] Revisar control de rutas, traversal, symlink y límites de tamaño.
- [ ] Confirmar que respuestas públicas no exponen secretos.
- [ ] Verificar que privada, Firebase y portal no comparten superficie/datos.
- [ ] Revisar creación de tablas fuera del sistema de migraciones.

## 5. Reglas críticas

- [ ] Revisar cuándo IMAP marca leído.
- [ ] Revisar cierre/autodescarte y estados elegibles.
- [ ] Revisar idempotencia de importación, correo, descarga, IA y monitor.
- [ ] Revisar tratamiento de resultados parciales.
- [ ] Revisar autoridad de marcador, baseline y sidecar.
- [ ] Revisar selección IA y exclusión de Q&A.
- [ ] Revisar independencia de canales de aviso y consolidación de incidencias.
- [ ] Revisar que clientes/envíos no envían automáticamente.
- [ ] Revisar que Ficha no escribe en SQLite.

## 6. Validación sin efectos

- [ ] Ejecutar colección pytest.
- [ ] Usar un `--basetemp` nuevo bajo `.codex_tmp` si el temporal global está bloqueado.
- [ ] Ejecutar suite completa.
- [ ] Ejecutar `node --check` sobre los tres JS principales.
- [ ] Ejecutar lint/typecheck de proyectos frontend adicionales sin desplegar.
- [ ] Registrar conteo, duración, warnings y causa de errores ambientales.
- [ ] No lanzar pruebas que requieran servicios reales salvo autorización.

## 7. Documentación

- [ ] Actualizar fecha de corte y HEAD.
- [ ] Actualizar matrices de estado, integraciones y automatizaciones.
- [ ] Actualizar decisiones, roadmap y elementos retirados.
- [ ] Comprobar enlaces relativos entre los 17 documentos.
- [ ] Buscar términos obsoletos y cifras contradictorias.
- [ ] Confirmar que no se copiaron credenciales ni datos personales innecesarios.
- [ ] Ejecutar segunda lectura de consistencia presente/futuro.

## 8. Verificación operativa opcional

Solo con autorización expresa:

- [ ] Estado y última ejecución de tareas Windows.
- [ ] `GET /api/health` conserva respuesta mínima exacta.
- [ ] Auditoría funcional devuelve OK/DEGRADADO/ERROR sin escribir SQLite.
- [ ] KeeperTick se usa como evidencia primaria del orquestador único; no confundirlo con el heartbeat histórico.
- [ ] Backups SQLite/completo dentro del umbral acordado.
- [ ] Colas sin trabajos activos obsoletos ni fallos recientes sin atender.
- [ ] Integraciones desactivadas no degradan; integraciones activas e incompletas sí.
- [ ] Dashboard muestra excepciones y no duplica la Agenda.
- [ ] Healthcheck del proceso real.
- [ ] Configuración efectiva agregada de automatizaciones.
- [ ] Último backup y restauración aislada.
- [ ] Estado de buzones/canales/túneles/despliegues.
- [ ] Smoke test real de una plataforma controlada.

## Criterio de cierre

La auditoría termina cuando todos los módulos tienen clasificación y evidencia, las contradicciones relevantes están resueltas, los pendientes están marcados, la validación segura está registrada y la documentación no mezcla estado técnico con estado operativo.
