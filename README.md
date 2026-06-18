# Llangon Suite V2

Monorepo privado y limpio para las herramientas de Llangón relacionadas con Infonalia, seguimiento de licitaciones, descargadores por plataforma, web pública y automatizaciones auxiliares.

## Contenido

```text
Llangon-SuiteV2/
├─ README.md
├─ PROJECT_CONTEXT.md
├─ INVENTARIO_MIGRACION.md
├─ MIGRACION_LOG.md
├─ SANEAMIENTO_REPOSITORIO.md
├─ webapp/infonalia_webapp/
├─ firebase/public_firebase/
├─ herramientas_python/
├─ macros/
├─ docs/
└─ documentos_contexto/
```

- `webapp/infonalia_webapp/`: aplicación privada Python, frontend y plantilla de configuración.
- `firebase/public_firebase/`: web pública estática para Firebase Hosting.
- `herramientas_python/`: descargadores y utilidades auxiliares. No deben ejecutarse sin una prueba controlada.
- `macros/`: módulos VBA de apoyo.
- `docs/`: documentación operativa vigente.
- `documentos_contexto/`: antecedentes históricos claramente marcados.

## Trabajo desde varios equipos

En GitHub Desktop:

1. Antes de empezar, abrir este repositorio y realizar **Fetch origin**.
2. Si existen cambios remotos, realizar **Pull origin** antes de editar.
3. Trabajar únicamente con archivos de código y documentación.
4. Revisar **Changes** y confirmar que no aparecen datos locales ni secretos.
5. Al terminar, crear un commit descriptivo y realizar **Push origin**.

No deben mantenerse cambios distintos sin sincronizar en dos equipos a la vez. Los datos SQLite, `.env`, mensajes, PDFs y descargas deben trasladarse por un canal privado independiente de Git.

## Seguridad

No subir:

- `.env`, contraseñas, tokens, claves o credenciales;
- bases de datos reales o copias;
- mensajes `.msg`, PDFs de clientes o TXT extraídos;
- logs, ZIP, temporales, backups o ficheros `.xlsm` con datos;
- `_NO_SUBIR_GITHUB/`, `.venv`, `node_modules` o cachés.

Antes del primer push, leer [SANEAMIENTO_REPOSITORIO.md](SANEAMIENTO_REPOSITORIO.md).

## Arranque local seguro

Requiere Python 3.10 o posterior. Desde la raíz:

```powershell
cd webapp\infonalia_webapp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completar en `.env` los usuarios y contraseñas obligatorios. Para la primera prueba:

```text
INFONALIA_HOST=127.0.0.1
INFONALIA_ENABLE_ADMIN_ALIAS=0
```

Después puede iniciarse manualmente con `python app.py`. No usar datos reales, descargas ni acceso de red hasta validar la configuración local.

## Agenda operativa y email

La pantalla Agenda usa listas limpias por día, semana, calendario mensual y vista completa. La bandeja operativa queda disponible para servicios internos, pero no se muestra como bloque principal.

El resumen por email se lanza manualmente desde Agenda. Si SMTP está configurado, el botón envía correo real al usuario logueado o al fallback `INFONALIA_AGENDA_EMAIL_TO`. Si SMTP no está configurado, devuelve un error claro y no hace dry-run silencioso.

```text
INFONALIA_SMTP_ENABLED=1
INFONALIA_AGENDA_EMAIL_TO=usuario@ejemplo.es
```

`dry_run=true` queda reservado para pruebas/desarrollo del endpoint. No se guardan secretos en Git.

El flujo de documentos recomendado sigue siendo Dropbox local/Desktop con `INFONALIA_STORAGE_BACKEND=local`; Dropbox API queda experimental y desactivado.

## Licitaciones y seguimiento

La pantalla Licitaciones es el centro de trabajo diario. Cada expediente puede marcarse como revisado, tener estado interno, notas internas, actuaciones vinculadas y seguimiento activo. El seguimiento automático real queda preparado, pero no implementado: el futuro monitor será un script externo de Windows y enviará un email por cada licitación con novedades a los destinatarios globales de `INFONALIA_SEGUIMIENTO_EMAILS`.

La IA queda aparcada: no se muestra ningún botón de ficha, análisis o resumen IA en la interfaz principal.

## Orden de lectura

1. `README.md`
2. `PROJECT_CONTEXT.md`
3. `SANEAMIENTO_REPOSITORIO.md`
4. `INVENTARIO_MIGRACION.md`
5. `MIGRACION_LOG.md`
