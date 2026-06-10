# Saneamiento Del Repositorio

## Medidas aplicadas

- Repositorio creado sin `.git` heredado ni repositorios anidados.
- Remotos antiguos eliminados al no copiar los historiales.
- `.gitignore` nuevo para secretos, datos, documentos operativos, logs, copias y cachés.
- `.env.example` sin valores reales.
- Usuarios y contraseñas obligatorios; no existen credenciales funcionales por defecto.
- Alias `admin` desactivado y sin contraseña predeterminada.
- Escucha local en `127.0.0.1` y monitor desactivado por defecto.
- Proyecto Firebase sustituido por `.firebaserc.example`.
- Correo incrustado retirado de la macro.
- Rutas específicas del repositorio anterior eliminadas de la documentación vigente.

## Archivos sensibles excluidos

- `.env`, claves, certificados y credenciales;
- bases de datos SQLite y copias;
- `.msg`, `.pdf` y `.txt`, salvo `requirements.txt`;
- logs, ZIP, backups, temporales y `.xlsm`;
- `_NO_SUBIR_GITHUB/`;
- datos bajo `webapp/infonalia_webapp/data/`, salvo sus dos archivos de estructura.

## Rutas

El código localiza `herramientas_python/` desde la raíz del repositorio. Las rutas de Dropbox, `pdftotext`, datos y servicios externos se configuran por variables de entorno.

Las rutas de instalación estándar de Chrome y Edge permanecen como candidatos de detección, no como rutas ligadas a un usuario concreto.

## Riesgos pendientes

- Los identificadores internos heredados del rol de revisión aparecen en nombres de campos, estados y endpoints. Se mantienen para compatibilidad y no representan credenciales, pero conviene migrarlos en una tarea separada.
- No se ha comprobado una base de datos real, porque no debe formar parte del repositorio.
- La configuración SMTP puede guardar la contraseña en SQLite local. Ese archivo requiere permisos restringidos y no debe sincronizarse ni compartirse; conviene migrar el secreto a un almacén seguro antes de un despliegue externo.
- El servidor local no incorpora terminación HTTPS. No debe exponerse directamente a Internet.
- No se han probado servicios externos ni descargadores.
- Debe confirmarse el ID de Firebase antes de crear el `.firebaserc` local.
- La documentación anterior menciona una cuarentena privada fuera del repositorio; no forma parte de esta copia y debe verificarse por separado.

## Antes del primer push

1. Revisar `git status --short`.
2. Revisar `git ls-files`.
3. Confirmar que no aparecen `.env`, bases de datos, claves, PDFs, TXT, MSG, logs, ZIP, backups ni `_NO_SUBIR_GITHUB`.
4. Buscar correos, tokens, contraseñas y rutas personales.
5. Confirmar que el remoto es `https://github.com/Llangon/llangon-suiteV2.git`.
6. Mantener el repositorio de GitHub como privado.
7. No desplegar Firebase como parte del primer commit.
