# Auditoría de la pantalla de Configuración

Proyecto auditado: `Llangon-SuiteV2`  
Modo de trabajo: solo análisis, sin cambios funcionales  
Fecha: 07/07/2026

## 1. Resumen ejecutivo

La pantalla actual de **Configuración** ya permite manejar varias piezas útiles, pero hoy mezcla en el mismo espacio:

- gestión de usuarios;
- mantenimiento y SMTP;
- estado de Telegram;
- diagnóstico de Dropbox;
- acciones técnicas de prueba o sincronización.

Eso hace que la pantalla sea útil para un perfil técnico, pero poco clara para un usuario de despacho. También hay una segunda capa de problema: parte de la configuración real vive en **base de datos** y otra parte vive en **variables de entorno** o scripts de Windows, de modo que la pantalla actual no representa todavía toda la configuración efectiva de la Suite.

Conclusión de la auditoría:

1. La pantalla actual **sí tiene una base aprovechable**.
2. Conviene **reordenarla por pestañas y por nivel de riesgo**.
3. No todo debe ser editable desde la web.
4. Hay varias opciones hoy ocultas o solo documentadas en `.env` que sí tendría sentido exponer más adelante.
5. También hay opciones que **no conviene convertir en “configuración de usuario”**, porque son infraestructura, seguridad o despliegue.

---

## 2. Qué es configurable ahora mismo

### 2.1. Configurable desde la pantalla actual

Actualmente la pantalla de Configuración permite editar o gestionar:

#### Usuarios

- Alta de usuario.
- Edición de usuario.
- Baja lógica mediante campo `active`.
- Nombre visible.
- Correo electrónico.
- Rol.
- Contraseña.
- `telegram_chat_id`.
- Activación de notificaciones Telegram por usuario.
- Prueba de Telegram por usuario.

#### Operación general

- `maintenance_mode`

#### SMTP / correo saliente

- `smtp_host`
- `smtp_port`
- `smtp_user`
- `smtp_password` (solo sustitución o borrado, no lectura)
- `smtp_from`
- `smtp_enabled`
- `smtp_tls`
- `smtp_ssl`
- `email_dry_run`
- `agenda_email_to`
- `prepared_notice_email_to`
- `seguimiento_emails`
- prueba de SMTP

#### Telegram global

No es editable desde la propia pantalla, pero sí se muestra como estado:

- Telegram activado o no.
- token configurado o no.
- grupo general configurado o no.
- botón de prueba al grupo general.

#### Almacenamiento / Dropbox Desktop

No es editable desde la pantalla, pero sí se muestra como estado y utilidades:

- modo actual de almacenamiento;
- carpeta local efectiva;
- base Dropbox detectada;
- tipo de resolución de la base;
- rango de años de monitor;
- prueba de Dropbox;
- prueba en seco;
- sincronización de marcadores Dropbox.

### 2.2. Configurable hoy, pero en realidad por base de datos y no por `.env`

La pantalla actual edita valores persistidos en `app_settings`:

- `maintenance_mode`
- `smtp_host`
- `smtp_port`
- `smtp_user`
- `smtp_from`
- `smtp_enabled`
- `smtp_tls`
- `smtp_ssl`
- `email_dry_run`
- `agenda_email_to`
- `prepared_notice_email_to`
- `seguimiento_emails`
- `smtp_password` (guardada, pero protegida en lectura)

Esto está bien para una Suite de uso diario porque evita tener que tocar el `.env` para cambios operativos frecuentes.

### 2.3. Configuración efectiva mostrada pero no editable desde la pantalla

La pantalla y el backend ya exponen como estado, pero no como edición:

- `nuria_review_email_to` derivado desde el usuario revisor;
- estado público de Telegram;
- estado público de IA;
- estado de almacenamiento / Dropbox;
- estado de detección de la base Dropbox real;
- rango de años de monitor.

---

## 3. Configuración existente en el proyecto que hoy NO se puede manejar desde la pantalla, pero podría tener sentido exponer

Este bloque incluye opciones que ya existen en el sistema y que podrían llegar a formar parte de una nueva Configuración, siempre con buena separación visual y explicaciones simples.

## 3.1. Comunicaciones automáticas

### Correo técnico / acciones por email

Variables detectadas:

- `LLANGON_ACTION_MAILBOX_TO`
- `LLANGON_ACTION_MAILBOX_CC`
- `LLANGON_ACTION_NOTIFY_EMAIL`
- `LLANGON_ACTION_ALLOWED_SENDERS`
- `LLANGON_ACTIONS_IMAP_HOST`
- `LLANGON_ACTIONS_IMAP_PORT`
- `LLANGON_ACTIONS_IMAP_USER`
- `LLANGON_ACTIONS_IMAP_PASSWORD`
- `LLANGON_ACTIONS_IMAP_FOLDER`
- `LLANGON_EMAIL_ACTIONS_ENABLED`
- `LLANGON_EMAIL_ACTIONS_POLL_MINUTES`

Recomendación:

- **Sí** tiene sentido exponer:
  - activado/desactivado;
  - buzón o carpeta IMAP;
  - usuario IMAP;
  - remitentes permitidos;
  - correo de aviso técnico;
  - frecuencia de revisión.
- **Con secreto protegido**:
  - contraseña IMAP.

### Importación automática de Infonalia

Variables detectadas:

- `LLANGON_INFONALIA_IMPORT_ENABLED`
- `LLANGON_INFONALIA_IMPORT_FROM`
- `LLANGON_INFONALIA_IMPORT_SUBJECT`
- `LLANGON_INFONALIA_IMPORT_NOTIFY_EMAIL`
- `LLANGON_INFONALIA_IMPORT_FOLDER`
- `LLANGON_INFONALIA_IMPORT_LOOKBACK_HOURS`
- `LLANGON_INFONALIA_IMPORT_MARK_READ_ON_SUCCESS`
- `LLANGON_INFONALIA_IMPORT_POLL_MINUTES`
- `LLANGON_INFONALIA_IMPORT_TEST_FORWARDERS`

Recomendación:

- **Sí** tiene bastante sentido exponer:
  - activado/desactivado;
  - carpeta/etiqueta IMAP;
  - correo de aviso;
  - frecuencia;
  - marcar como leído;
  - ventana de búsqueda.
- `from`, `subject` y `test_forwarders` podrían ir en un bloque avanzado.

### Destinatarios de monitor / agenda

Existen ya referencias a:

- `monitor_test_email`
- `monitor_agenda_pending_email_to`

Situación:

- están sembradas en configuración por defecto;
- el monitor las utiliza;
- **no aparecen hoy en la pantalla como campos editables**.

Estado recomendado: **uso no documentado / revisar**  
Conclusión: sí merece la pena decidir explícitamente si estas direcciones siguen vivas en producto y, si siguen, exponerlas en una pestaña de automatismos o agenda.

## 3.2. IA / análisis documental

Configuración detectada:

- `AI_ANALYSIS_PROVIDER`
- `GEMINI_ENABLED`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `GEMINI_MAX_REQUESTS_PER_MINUTE`
- `GEMINI_MAX_REQUESTS_PER_DAY`
- `GEMINI_COOLDOWN_ON_429_MINUTES`
- `GEMINI_MAX_DOCUMENTS_PER_ANALYSIS`
- `GEMINI_MAX_FILE_MB`
- `GEMINI_TIMEOUT_SECONDS`
- `GEMINI_INPUT_MODE`
- `GEMINI_MAX_EXTRACTED_CHARS`
- `GEMINI_MAX_CHARS_PER_DOCUMENT`
- `GEMINI_PDF_INLINE_FALLBACK`
- `GEMINI_MIN_EXTRACTED_CHARS`
- `CODEX_LOCAL_ENABLED`
- `CODEX_EXECUTABLE`
- `CODEX_TIMEOUT_SECONDS`
- `CODEX_WORK_ROOT`
- `CODEX_SANDBOX`
- `CODEX_MAX_FILES`
- `CODEX_MAX_FILE_MB`

La API de configuración ya devuelve estado público de IA:

- proveedor activo;
- si está habilitado;
- si está configurado;
- modelo;
- límites principales;
- modo de entrada;
- flags de Codex Local.

Recomendación:

- Para usuario normal: **solo estado y botones de prueba**, no todo el motor.
- Para administrador avanzado:
  - proveedor activo;
  - activar/desactivar;
  - modelo;
  - timeout;
  - límites principales.
- API key: **siempre oculta**, solo sustituir o borrar.

## 3.3. Almacenamiento / Dropbox / flujo físico

Configuración detectada:

- `INFONALIA_STORAGE_BACKEND`
- `LLANGON_DROPBOX_BASE_PATH`
- `INFONALIA_DROPBOX_ROOT`
- `INFONALIA_DOWNLOAD_STAGING_ROOT`
- `INFONALIA_DROPBOX_ENABLED`
- `INFONALIA_DROPBOX_DRY_RUN`
- `INFONALIA_DROPBOX_API_ROOT`
- `INFONALIA_DROPBOX_APP_KEY`
- `INFONALIA_DROPBOX_APP_SECRET`
- `INFONALIA_DROPBOX_REFRESH_TOKEN`
- `INFONALIA_DROPBOX_NON_DESTRUCTIVE`
- `INFONALIA_PDFTOTEXT`
- `INFONALIA_PLATFORM_URL`

Recomendación:

- Sí exponer visualmente:
  - ruta base efectiva;
  - origen de esa ruta;
  - si existe o no;
  - modo local vs API;
  - staging root;
  - modo seguro / dry-run;
  - botón de prueba.
- No necesariamente editar desde la web en primera fase:
  - `LLANGON_DROPBOX_BASE_PATH`
  - `INFONALIA_DROPBOX_ROOT`
  - `INFONALIA_DOWNLOAD_STAGING_ROOT`
  - credenciales API de Dropbox

Motivo: son opciones muy ligadas al equipo, al despliegue y a Windows.

## 3.4. Agenda y automatismos

Se han detectado ajustes existentes para:

- scheduler;
- inventario local de ficheros;
- aviso diario de agenda;
- agenda wake;
- horarios e intervalos.

Variables relevantes:

- `MONITOR_SCHEDULER_ENABLED`
- `MONITOR_SCHEDULER_TIMEZONE`
- `MONITOR_SCHEDULER_POLL_MINUTES`
- `MONITOR_AGENDA_PENDING_DAILY_ENABLED`
- `MONITOR_AGENDA_PENDING_DAILY_TIME`
- `MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY`
- `LLANGON_FILE_INVENTORY_ENABLED`
- `LLANGON_FILE_INVENTORY_POLL_MINUTES`
- `LLANGON_FILE_INVENTORY_MAX_FILES_PER_RUN`
- `LLANGON_FILE_INVENTORY_MAX_DEPTH`
- `LLANGON_FILE_INVENTORY_RECONCILE_PATHS`
- `LLANGON_AGENDA_WAKE_ENABLED`
- `LLANGON_AGENDA_WAKE_TIME`
- `LLANGON_AGENDA_WAKE_AUTO_SLEEP`
- `LLANGON_AGENDA_WAKE_SKIP_SLEEP_IF_USER_ACTIVE`
- `LLANGON_AGENDA_WAKE_MIN_IDLE_SECONDS`

Recomendación:

- Parte útil para la app:
  - activar/desactivar importación automática;
  - activar/desactivar procesado de órdenes;
  - activar/desactivar inventario;
  - frecuencia de revisión;
  - correo diario de agenda;
  - hora del envío diario.
- Parte de Windows/infraestructura:
  - agenda wake;
  - autosuspensión;
  - comportamiento con usuario activo.

Esto último no debería ir en una pantalla “normal”; como mucho en una zona avanzada o directamente fuera de la app.

## 3.5. Backup y despliegue local

Configuración detectada:

- `LLANGON_RUNTIME_ROOT`
- `LLANGON_SQLITE_BACKUP_DIR`
- `LLANGON_SQLITE_BACKUP_RETENTION`
- `LLANGON_FULL_BACKUP_ENABLED`
- `LLANGON_FULL_BACKUP_ROOT`
- `LLANGON_FULL_BACKUP_RETENTION_DAILY`
- `LLANGON_FULL_BACKUP_RETENTION_MONTHLY`
- `LLANGON_FULL_BACKUP_INCLUDE_ENV`
- `LLANGON_FULL_BACKUP_INCLUDE_SECRETS`
- `LLANGON_FULL_BACKUP_INCLUDE_CODE`
- `LLANGON_FULL_BACKUP_EXCLUDE_REBUILDABLE`
- `INFONALIA_HOST`
- `INFONALIA_PORT`
- `LLANGON_PUBLIC_SITE_URL`

Recomendación:

- Sí tiene sentido mostrar:
  - si hay backup SQLite;
  - si hay backup completo;
  - carpeta de destino;
  - retención;
  - fecha del último backup;
  - URL pública configurada;
  - host/puerto efectivos.
- No conviene convertir todo esto en edición libre en la primera versión de Configuración.

---

## 4. Qué NO conviene hacer configurable desde la interfaz general

Este punto es importante para que la pantalla no se convierta en un “panel de control del servidor”.

## 4.1. Secretos de infraestructura que no deben mostrarse nunca en claro

- `GEMINI_API_KEY`
- `LLANGON_TELEGRAM_BOT_TOKEN`
- `INFONALIA_DROPBOX_APP_SECRET`
- `INFONALIA_DROPBOX_REFRESH_TOKEN`
- `LLANGON_ACTIONS_IMAP_PASSWORD`
- `INFONALIA_SMTP_PASSWORD`
- cualquier otra contraseña real de correo o API

Regla recomendada:

- mostrar solo “configurada / no configurada”;
- permitir reemplazar;
- permitir borrar;
- nunca devolver el valor real al frontend.

## 4.2. Rutas o parámetros muy ligados al equipo

No conviene que un usuario normal pueda editar alegremente:

- `LLANGON_DROPBOX_BASE_PATH`
- `INFONALIA_DROPBOX_ROOT`
- `INFONALIA_DOWNLOAD_STAGING_ROOT`
- `CODEX_WORK_ROOT`
- `LLANGON_RUNTIME_ROOT`
- `LLANGON_SQLITE_BACKUP_DIR`
- `LLANGON_FULL_BACKUP_ROOT`

Estas rutas deberían ir como mucho en:

- zona avanzada;
- o pantalla separada de “Instalación local / diagnóstico”.

## 4.3. Parámetros internos de ejecución o tuning técnico

No conviene exponer al usuario de despacho:

- `CODEX_SANDBOX`
- `CODEX_EXECUTABLE`
- `GEMINI_MAX_EXTRACTED_CHARS`
- `GEMINI_MAX_CHARS_PER_DOCUMENT`
- `GEMINI_MIN_EXTRACTED_CHARS`
- `LLANGON_FILE_INVENTORY_MAX_DEPTH`
- `LLANGON_FILE_INVENTORY_MAX_FILES_PER_RUN`
- parámetros de retención con semántica técnica no explicada

Si alguna vez se exponen, debe ser en bloque “Avanzado” con textos de ayuda muy claros.

## 4.4. Configuración de host/puerto salvo necesidad real

- `INFONALIA_HOST`
- `INFONALIA_PORT`
- flags de loopback / apertura LAN

Esto es despliegue local, no operación funcional de la Suite. No conviene meterlo en la configuración diaria.

---

## 5. Elementos detectados con uso dudoso o que requieren revisión funcional

Estos puntos existen en código o configuración, pero conviene revisarlos antes de decidir si merecen un hueco en la pantalla nueva.

### 5.1. `monitor_test_email`

- Está sembrado en configuración por defecto.
- El monitor lo utiliza como fallback.
- No está bien integrado en la pantalla actual.

Estado: **uso no documentado / revisar**

### 5.2. `monitor_agenda_pending_email_to`

- También está sembrado y usado en monitor/scheduler.
- No está expuesto como campo editable en la configuración principal.

Estado: **uso no documentado / revisar**

### 5.3. `INFONALIA_PLATFORM_URL`

- Detectado en `.env.example`.
- No aparece como protagonista en la UI actual.

Estado: **uso no documentado / revisar**

### 5.4. `INFONALIA_DROPBOX_ENABLED`

- Existe como señal asociada a Dropbox API.
- El flujo recomendado sigue siendo Dropbox Desktop/local.

Estado: **opción técnica / revisar**

### 5.5. `LLANGON_REVIEW_AI_SUMMARY_BUTTON_ENABLED`

- Existe como interruptor de futuro.
- No parece una función madura de uso general todavía.

Estado: **experimental / revisar**

---

## 6. Propuesta de rediseño de la nueva pantalla de Configuración

## 6.1. Principio general

La pantalla debe dejar de ser una lista larga de paneles técnicos y convertirse en un espacio con dos niveles:

1. **Configuración diaria**
2. **Configuración avanzada**

Y dentro de cada nivel, usar pestañas claras.

## 6.2. Estructura propuesta

### Pestaña 1. General

Pensada para uso cotidiano.

Contenido:

- Modo mantenimiento.
- URL pública configurada.
- Estado general de la instalación.
- Resumen rápido:
  - correo saliente;
  - Telegram;
  - Dropbox;
  - IA;
  - automatismos.

Objetivo:

- que al entrar se vea “cómo está la Suite” sin leer detalles técnicos.

### Pestaña 2. Usuarios y permisos

Contenido:

- listado de usuarios;
- alta;
- edición;
- activación/desactivación;
- rol;
- email;
- Telegram por usuario;
- prueba de Telegram por usuario.

Mejora sugerida:

- separar “datos básicos” de “notificaciones”.

### Pestaña 3. Correos y notificaciones

Contenido:

- SMTP saliente;
- remitente;
- prueba SMTP;
- correo Agenda fallback;
- correo aviso ficha preparada;
- correos de seguimiento;
- Telegram general:
  - estado;
  - token configurado;
  - grupo configurado;
  - prueba al grupo.

Esta pestaña sería la más usada por negocio.

### Pestaña 4. Buzones automáticos

Contenido:

- Acciones por correo:
  - activado/desactivado;
  - carpeta IMAP;
  - usuario IMAP;
  - remitentes autorizados;
  - frecuencia;
  - correo de aviso técnico.
- Importación automática de Infonalia:
  - activado/desactivado;
  - carpeta/etiqueta;
  - correo aviso;
  - frecuencia;
  - marcar leído;
  - ventana de búsqueda.

Texto clave:

- lenguaje funcional, no técnico;
- evitar hablar de IMAP salvo en subtítulos o ayuda.

### Pestaña 5. Almacenamiento

Contenido:

- ruta Dropbox efectiva;
- origen de la ruta;
- si la carpeta existe;
- modo actual de almacenamiento;
- staging;
- prueba de Dropbox;
- prueba en seco;
- sincronización de marcadores.

Mejora recomendada:

- mostrar visualmente si el sistema está:
  - OK;
  - en fallback legado;
  - en error;
  - fuera de Dropbox real.

### Pestaña 6. IA documental

Contenido:

- proveedor activo;
- si está activado;
- si está configurado;
- modelo;
- timeout;
- tamaño máximo por documento;
- documentos máximos;
- modo de entrada;
- botón de prueba o diagnóstico básico.

Secreto:

- API key oculta, con “reemplazar”.

### Pestaña 7. Automatismos

Contenido:

- scheduler general;
- revisión automática de correos;
- inventario de ficheros;
- aviso diario de agenda;
- horarios y frecuencias simples.

No meter aquí todavía la capa más rara de Windows.

### Pestaña 8. Avanzado

Contenido:

- parámetros técnicos;
- rutas locales;
- backups;
- host/puerto;
- integración local Windows;
- flags experimentales;
- opciones “uso no documentado / revisar”.

Esta pestaña debe ir:

- colapsada o menos visible;
- con avisos de precaución;
- solo para administradores.

---

## 7. Recomendaciones de diseño y UX

## 7.1. No enseñar todo de golpe

La configuración actual tiene demasiadas piezas para una sola vista plana. La nueva versión debe:

- usar pestañas;
- usar bloques cortos;
- incluir subtítulos humanos;
- esconder lo avanzado por defecto.

## 7.2. Mostrar estado antes que campos

En vez de empezar por inputs, conviene empezar cada pestaña con un resumen:

- Correo: activo / pendiente / mal configurado
- Telegram: listo / falta token / falta grupo
- Dropbox: válido / fallback / no encontrado
- IA: activa / sin clave / desactivada

Así el usuario entiende primero el estado real y luego ya edita.

## 7.3. Secretos siempre enmascarados

Patrón recomendado:

- “Configurada” / “No configurada”
- botón “Cambiar”
- checkbox “Borrar contraseña / clave”

Nunca mostrar la clave previa.

## 7.4. Separar “editar” de “probar”

Ahora conviven formularios y botones de prueba en el mismo bloque. Funciona, pero visualmente confunde.

Mejor:

- arriba formulario;
- abajo acciones de comprobación.

## 7.5. Marcar lo heredado o legado

Cuando una ruta o parámetro venga de fallback histórico, debe leerse así:

- “Legado”
- “Compatibilidad”
- “Pendiente de migrar”

Eso reduce dudas futuras.

---

## 8. Qué implementaría en fases

## Fase 1. Reordenación visual sin cambiar fondo

Objetivo:

- misma lógica;
- misma persistencia;
- nueva estructura por pestañas;
- resúmenes de estado;
- separar diaria vs avanzada.

Esta fase da mucho valor sin tocar demasiada lógica.

## Fase 2. Exponer configuraciones ya existentes de alto valor

Añadir a UI:

- automatismos de importación Infonalia;
- buzón de acciones;
- más ajustes de avisos;
- bloque de IA con edición controlada;
- `monitor_agenda_pending_email_to` y `monitor_test_email` si se confirma que siguen vigentes.

## Fase 3. Diagnóstico avanzado y despliegue local

Añadir:

- backup SQLite;
- backup completo;
- host/puerto;
- URL pública;
- despliegue local Windows;
- diagnósticos y última ejecución.

## Fase 4. Limpieza de herencia

Objetivo:

- decidir qué opciones siguen vivas;
- retirar o esconder ajustes residuales;
- reducir “uso no documentado / revisar”.

---

## 9. Inventario resumido por categoría

## 9.1. Configuración diaria recomendable

- modo mantenimiento;
- usuarios;
- correo SMTP;
- remitente;
- emails de aviso;
- Telegram por usuario;
- Telegram grupo;
- importación automática de Infonalia;
- acciones por correo;
- estado de Dropbox;
- estado de IA.

## 9.2. Configuración avanzada recomendable

- modelo IA;
- límites IA;
- tiempo de espera IA;
- inventario local de ficheros;
- scheduler;
- backups;
- rutas técnicas;
- staging;
- API Dropbox experimental;
- parámetros avanzados de agenda wake.

## 9.3. No recomendable como configuración general

- claves reales;
- rutas de trabajo muy sensibles;
- ejecutables;
- sandbox interno;
- puertos/host salvo necesidad;
- toggles experimentales sin documentación.

---

## 10. Conclusión

La pantalla de Configuración **no necesita rehacerse desde cero a nivel de negocio**, pero sí necesita una **reorganización fuerte**.

La base ya existe:

- persistencia de ajustes;
- endpoints;
- tests;
- componentes visuales;
- paneles de estado.

Lo que falta es convertir esa base en una experiencia más clara, separando:

- lo que usa una persona del despacho;
- lo que usa un administrador;
- lo que realmente es infraestructura local;
- lo que aún está en estado experimental o poco documentado.

Mi recomendación práctica:

1. hacer primero una **fase de orden visual por pestañas**;
2. después exponer de forma controlada los automatismos de correo e importación;
3. dejar IA, backup y despliegue local en una zona avanzada;
4. revisar y decidir qué hacer con los parámetros marcados como **uso no documentado / revisar**.

---

## 11. Fase 1 implementada

La primera fase reorganiza la pantalla sin cambiar la lógica interna de negocio ni convertir variables sensibles en edición libre.

Estructura visual aplicada:

1. General
2. Usuarios y permisos
3. Correos y notificaciones
4. Buzones automáticos
5. Almacenamiento / Dropbox
6. IA documental
7. Automatismos
8. Avanzado / diagnóstico

Opciones editables que se mantienen:

- usuarios;
- roles actuales;
- email de usuario;
- contraseña de usuario;
- Telegram por usuario;
- modo mantenimiento;
- configuración SMTP ya soportada;
- destinatarios de avisos;
- contraseña SMTP solo como reemplazo o borrado.

Opciones mostradas como solo lectura / diagnóstico:

- estado de Telegram global;
- estado de Dropbox / almacenamiento;
- buzones automáticos;
- importación automática de Infonalia;
- IA documental;
- scheduler;
- inventario interno;
- backup;
- host y puerto efectivos;
- URL pública;
- opciones marcadas como pendientes de revisar.

Reglas de seguridad mantenidas:

- no se muestran tokens, claves ni contraseñas;
- las claves aparecen solo como configuradas o no configuradas;
- rutas sensibles se muestran como diagnóstico, no como edición libre;
- la zona avanzada sigue siendo solo para administradores.

---

## 12. Cierre de revisión de Fase 1

Fecha de revisión: 08/07/2026

Resultado:

- Fase 1 revisada a nivel funcional, de estructura, permisos y seguridad.
- No se ha implementado Fase 2.
- No se han convertido variables de entorno en campos editables.
- No se han añadido nuevas opciones funcionales de configuración.

Comprobaciones realizadas:

- La pantalla conserva las ocho pestañas previstas:
  1. General
  2. Usuarios y permisos
  3. Correos y notificaciones
  4. Buzones automáticos
  5. Almacenamiento / Dropbox
  6. IA documental
  7. Automatismos
  8. Avanzado / diagnóstico
- Los formularios existentes de usuarios, SMTP, Telegram y almacenamiento se mantienen en sus bloques correspondientes.
- El endpoint `/api/config` sigue protegido para administradores.
- Las mutaciones de configuración siguen protegidas por permisos de administrador y CSRF.
- La pestaña avanzada se mantiene dentro de la pantalla de administración.
- Los buzones automáticos se muestran como diagnóstico / solo lectura.
- La IA documental se muestra como estado, sin exponer claves.
- Dropbox y rutas locales se muestran como diagnóstico, no como edición libre.

Incidencias encontradas:

- La primera ejecución de `python -m pytest` falló porque `pytest.ini` usaba una carpeta temporal fija `.pytest_tmp` dentro del proyecto y esta sesión no tenía permisos de escritura sobre esa carpeta.

Incidencias corregidas:

- Se ajustó `pytest.ini` para mantener `testpaths` y `norecursedirs`, pero sin forzar `--basetemp=.pytest_tmp`.
- La recogida de tests sigue limitada a `webapp/infonalia_webapp/tests` y no recorre `runtime`, backups, temporales ni staging.
- Se añadió una prueba automática específica para comprobar que `/api/config` no serializa valores ni nombres de secretos conocidos.

Validaciones ejecutadas:

- `python -m pytest --collect-only`
  - Resultado: 807 tests recogidos solo desde `webapp/infonalia_webapp/tests`.
- `python -m pytest`
  - Resultado: 807 passed.
- `node --check webapp/infonalia_webapp/static/app.js`
  - Resultado: correcto.
- Test focalizado de configuración/Telegram:
  - Resultado: 19 passed.

Secretos comprobados:

El payload de configuración no debe mostrar valores ni nombres de:

- `GEMINI_API_KEY`
- `LLANGON_TELEGRAM_BOT_TOKEN`
- `INFONALIA_DROPBOX_APP_SECRET`
- `INFONALIA_DROPBOX_REFRESH_TOKEN`
- `LLANGON_ACTIONS_IMAP_PASSWORD`
- `INFONALIA_SMTP_PASSWORD`

Estado de revisión visual:

- En el primer intento la app local no estaba arrancada (`ERR_CONNECTION_REFUSED` / healthcheck sin respuesta).
- Después se arrancó la web local y `http://127.0.0.1:8787/api/health` respondió correctamente.
- El navegador integrado pudo abrir `http://127.0.0.1:8787/login` y mostrar la pantalla de acceso.
- No se introdujeron credenciales. Queda pendiente una comprobación manual de las pestañas con sesión de administrador.

Checklist manual recomendada antes de pasar a Fase 2:

- Entrar como administrador.
- Abrir Configuración.
- Cambiar entre las ocho pestañas y comprobar que ninguna queda vacía o confusa.
- Revisar que la pestaña activa se distingue visualmente.
- Probar en una ventana estrecha o móvil que las pestañas permiten desplazamiento horizontal.
- Confirmar que el modo mantenimiento puede activarse/desactivarse y guardarse.
- Editar un usuario de prueba y comprobar que no se pierde la contraseña si se deja vacía.
- Probar alta/baja lógica de usuario si procede.
- Probar Telegram por usuario si ya está configurado.
- Probar SMTP con configuración actual.
- Confirmar que la contraseña SMTP nunca aparece en claro.
- Revisar Buzones automáticos como diagnóstico, sin edición.
- Revisar Almacenamiento / Dropbox, prueba en seco y sincronización de marcadores si procede.
- Revisar IA documental y confirmar que solo muestra estado/modelo/límites.
- Revisar Automatismos sin ejecutar acciones no deseadas.
- Abrir Avanzado / diagnóstico y comprobar que el texto copiable no incluye secretos.

Recomendación:

- La Fase 1 queda técnicamente preparada para pasar a Fase 2 tras la revisión visual manual en navegador.
- En Fase 2 conviene priorizar solo opciones de alto valor operativo, especialmente buzones automáticos e importación Infonalia, manteniendo secretos con patrón “configurado / reemplazar / borrar”.

## 13. Fase 2 implementada

Opciones nuevas editables:

- Buzones automáticos / acciones por correo: activación, frecuencia, buzón destino, copia, correo técnico de aviso, remitentes autorizados, servidor IMAP, puerto IMAP, usuario IMAP y carpeta IMAP.
- Buzones automáticos / importación Infonalia: activación, correo de aviso, etiqueta IMAP, frecuencia, marcado como leído tras éxito y ventana de búsqueda.
- IA documental: proveedor, activación de Gemini, modelo, límites de peticiones, límite de documentos, tamaño máximo por fichero, timeout y modo de entrada.
- Automatismos: correo de pruebas del monitor y correo de agenda diaria.

Opciones que siguen como solo lectura o diagnóstico:

- Contraseña IMAP de acciones por correo.
- Clave `GEMINI_API_KEY`.
- Filtros avanzados del importador Infonalia (`LLANGON_INFONALIA_IMPORT_FROM`, `LLANGON_INFONALIA_IMPORT_SUBJECT`, `LLANGON_INFONALIA_IMPORT_TEST_FORWARDERS`).
- Límites avanzados de extracción Gemini y configuración `CODEX_LOCAL_*`.
- Rutas Dropbox, runtime, backup y despliegue local.

Regla de lectura implementada:

- Si existe valor guardado en `app_settings`, se usa como configuración efectiva.
- Si no existe valor en Suite, se usa la variable de entorno equivalente.
- Si tampoco existe variable de entorno, se usa un valor por defecto seguro.
- La UI muestra el origen como “Configurado en la Suite”, “Variable de entorno”, “Valor por defecto” o “No configurado”.

Secretos protegidos:

- No se serializan valores de `GEMINI_API_KEY`, `LLANGON_TELEGRAM_BOT_TOKEN`, `INFONALIA_DROPBOX_APP_SECRET`, `INFONALIA_DROPBOX_REFRESH_TOKEN`, `LLANGON_ACTIONS_IMAP_PASSWORD`, `INFONALIA_SMTP_PASSWORD` ni contraseñas reales.
- Las claves y contraseñas se muestran solo como “configurada / no configurada”.
- La interfaz no escribe `.env`.

Validaciones añadidas:

- Emails individuales y listas de emails.
- Puertos entre 1 y 65535.
- Frecuencias entre 1 y 1440 minutos.
- Ventana Infonalia entre 1 y 168 horas.
- Timeout Gemini entre 10 y 900 segundos.
- Documentos Gemini entre 1 y 20.
- Tamaño máximo Gemini entre 1 y 100 MB.
- No se permite activar acciones por correo si falta host, puerto, usuario, carpeta, remitentes autorizados o contraseña IMAP.
- No se permite activar importación automática si falta configuración IMAP base, carpeta o correo de aviso.
- No se permite activar Gemini si falta modelo o clave configurada en entorno.

Cambios técnicos:

- Nuevo helper `operational_settings.py` para resolver configuración efectiva de forma común.
- El procesador de acciones por correo lee `app_settings` con fallback a `.env`.
- El importador automático de Infonalia lee `app_settings` con fallback a `.env`.
- La configuración IA lee `app_settings` para las opciones de bajo riesgo y mantiene la clave como secreto de entorno.
- El scheduler usa las frecuencias y activaciones operativas editables para acciones por correo e importación Infonalia.

Pruebas ejecutadas durante el cierre:

- Tests focalizados de configuración y secretos.
- `node --check webapp/infonalia_webapp/static/app.js`.
- `py_compile` de módulos Python modificados usando caché temporal externa.

Pendiente de Fase 3:

- Pruebas reales seguras de conexión IMAP en seco.
- Edición segura de secretos si se decide implementar un almacén específico.
- Ajustes avanzados de Dropbox, runtime, backups o despliegue.
