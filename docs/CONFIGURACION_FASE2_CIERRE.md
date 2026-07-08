# Cierre Fase 2 - Pantalla de Configuración

## Resumen ejecutivo

Se ha implementado la Fase 2 de Configuración para exponer opciones operativas de alto valor sin convertir la pantalla en un panel técnico peligroso. La Suite permite editar ajustes de buzones automáticos, importación automática de Infonalia, límites básicos de IA documental y avisos de automatismos.

La regla de configuración queda centralizada:

1. Valor guardado en `app_settings`.
2. Variable de entorno equivalente.
3. Valor por defecto seguro.

La interfaz no escribe `.env` y no muestra secretos.

## Cambios realizados

- Nuevo helper común `operational_settings.py` para resolver configuración efectiva y origen del valor.
- Nuevas claves editables en `app_settings` validadas desde `user_settings.py`.
- `/api/config` mantiene acceso solo administrador y devuelve estado seguro de los nuevos bloques.
- El procesador de acciones por correo lee la configuración efectiva.
- El importador automático de Infonalia lee la configuración efectiva.
- La configuración IA lee desde `app_settings` las opciones de bajo riesgo y mantiene `GEMINI_API_KEY` como secreto de entorno.
- El scheduler usa las activaciones/frecuencias efectivas para acciones por correo e importación Infonalia.
- La pantalla Configuración incorpora formularios editables en:
  - Buzones automáticos.
  - IA documental.
  - Automatismos.

## Opciones editables nuevas

- `email_actions_enabled`
- `email_actions_poll_minutes`
- `action_mailbox_to`
- `action_mailbox_cc`
- `action_notify_email`
- `action_allowed_senders`
- `actions_imap_host`
- `actions_imap_port`
- `actions_imap_user`
- `actions_imap_folder`
- `infonalia_import_enabled`
- `infonalia_import_notify_email`
- `infonalia_import_folder`
- `infonalia_import_poll_minutes`
- `infonalia_import_mark_read_on_success`
- `infonalia_import_lookback_hours`
- `ai_analysis_provider`
- `gemini_enabled`
- `gemini_model`
- `gemini_max_requests_per_minute`
- `gemini_max_requests_per_day`
- `gemini_max_documents_per_analysis`
- `gemini_max_file_mb`
- `gemini_timeout_seconds`
- `gemini_input_mode`
- `monitor_test_email`
- `monitor_agenda_pending_email_to`

## Opciones que siguen en diagnóstico

- Contraseña IMAP `LLANGON_ACTIONS_IMAP_PASSWORD`.
- Clave `GEMINI_API_KEY`.
- Ajustes avanzados de importación Infonalia: remitente esperado, asunto esperado y reenviadores de prueba.
- Límites avanzados de extracción Gemini.
- Configuración `CODEX_LOCAL_*`.
- Rutas Dropbox, runtime, backups y despliegue.

## Secretos protegidos

No se muestran ni se devuelven valores de:

- `GEMINI_API_KEY`
- `LLANGON_TELEGRAM_BOT_TOKEN`
- `INFONALIA_DROPBOX_APP_SECRET`
- `INFONALIA_DROPBOX_REFRESH_TOKEN`
- `LLANGON_ACTIONS_IMAP_PASSWORD`
- `INFONALIA_SMTP_PASSWORD`
- Contraseñas SMTP/IMAP reales

La UI solo informa “configurado / no configurado”. No se escribe `.env` desde la Suite.

## Tests añadidos o modificados

- Tests de `public_settings_payload` para permitir nuevas claves seguras sin exponer contraseñas.
- Tests de lectura Suite -> entorno -> default.
- Tests de validación de acciones por correo, Gemini e importación Infonalia.
- Tests de constructores de configuración de buzones leyendo `app_settings` antes que `.env`.

## Validaciones ejecutadas

- `py_compile` de módulos Python modificados: correcto usando caché temporal externa.
- `node --check webapp/infonalia_webapp/static/app.js`: correcto.
- Tests focalizados de configuración/secretos: correctos.
- `python -m pytest --collect-only`: 814 tests recogidos, todos dentro de `webapp/infonalia_webapp/tests`.
- `python -m pytest`: 814 passed.

## Resultado final

Fase 2 completada y validada.

## Incidencias

- La compilación Python no pudo escribir en `__pycache__` del proyecto ni en `.pytest_tmp`; se ejecutó correctamente con `PYTHONPYCACHEPREFIX` apuntando a la carpeta temporal del usuario.
- No se han implementado pruebas reales de IMAP o Gemini para evitar conexiones externas y efectos sobre correos reales.

## Revisión manual pendiente

- Entrar como administrador y revisar visualmente los nuevos formularios.
- Confirmar que activar un bloque incompleto muestra error claro.
- Confirmar que la contraseña IMAP y la clave Gemini solo aparecen como estado.

## Commit local

No realizado. El repositorio tenía muchos cambios locales previos al empezar esta fase y el estado final sigue mezclando trabajo anterior con esta implementación. Para evitar un commit con alcance confuso, no se ha creado el commit `feat: expose operational configuration settings`.

## Archivos tocados en esta fase

- `README.md`
- `docs/CONFIGURACION_AUDITORIA.md`
- `docs/CONFIGURACION_FASE2_CIERRE.md`
- `webapp/infonalia_webapp/operational_settings.py`
- `webapp/infonalia_webapp/user_settings.py`
- `webapp/infonalia_webapp/app.py`
- `webapp/infonalia_webapp/email_actions_processor.py`
- `webapp/infonalia_webapp/infonalia_mail_importer.py`
- `webapp/infonalia_webapp/ai/config.py`
- `webapp/infonalia_webapp/monitor/scheduler.py`
- `webapp/infonalia_webapp/static/index.html`
- `webapp/infonalia_webapp/static/app.js`
- `webapp/infonalia_webapp/tests/test_user_settings.py`

## Confirmaciones

- No se implementó Fase 3.
- No se ha escrito `.env`.
- No se han mostrado secretos.
- No se ha hecho push remoto.
- No se ha creado commit por estado Git previo no limpio.
- Suspensión del PC: primer método agotó tiempo; alternativa `rundll32.exe powrprof.dll,SetSuspendState 0,1,0` ejecutada desde Codex con salida correcta.
