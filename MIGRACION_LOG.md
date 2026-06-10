# Log De Migración

## Registro

- Fecha y hora: `2026-06-10 12:39:43 +02:00`
- Origen: `C:\Users\LLangon03\Documents\Codex\llangon-suite`
- Destino: `C:\Users\LLangon03\Documents\Codex\Llangon-SuiteV2`
- Respaldo: `C:\Users\LLangon03\Documents\Codex\BACKUP_llangon-suite_20260610_123524`

## Copia de seguridad

El respaldo completo conserva 161 archivos y 5.712.121 bytes. La comparación SHA-256 no detectó archivos ausentes ni diferencias.

## Copiado

- Aplicación privada y estáticos.
- Web pública y configuración de Firebase Hosting.
- Siete herramientas Python.
- Dos módulos VBA.
- Documentación operativa y documentos de contexto.
- `.gitattributes`.

## Excluido

- Los dos directorios `.git` y sus remotos anteriores.
- El repositorio anidado `inventario-licitaciones-langon`.
- Documentación raíz obsoleta, sustituida por documentación V2.
- Configuración operativa `.firebaserc`, sustituida por un ejemplo.
- Datos, bases de datos, claves, mensajes, PDFs, TXT, logs, backups, entornos y cachés.

## Saneamiento aplicado

- Credenciales obligatorias mediante `.env`, sin contraseñas por defecto.
- Alias administrativo desactivado por defecto y sin contraseña incorporada.
- Monitor desactivado por defecto.
- Lanzador limitado a `127.0.0.1`.
- URL de plataforma trasladada a `INFONALIA_PLATFORM_URL`.
- Correo de macro retirado del código.
- Etiquetas visibles del rol revisor generalizadas.

## Pendiente

- Confirmar el proyecto Firebase real.
- Revisar los identificadores técnicos heredados del rol revisor antes de una migración de esquema.
- Confirmar la ubicación y política de copia de los datos privados externos mencionados por documentación anterior.
- Revisar manualmente la lista final de Git antes del primer commit.

No se ejecutó la aplicación, ningún descargador, el monitor ni Firebase. No se instaló ninguna dependencia. No se realizó commit ni push.

## Preparación Git

El equipo no dispone de `git.exe`, GitHub Desktop, WSL ni una biblioteca Git reutilizable. Para no instalar software sin autorización, se creó únicamente la estructura estándar mínima de un repositorio Git:

- `HEAD` apunta a `refs/heads/main`;
- no existen referencias, objetos ni commits;
- `origin` apunta a `https://github.com/Llangon/llangon-suiteV2.git`.

La comprobación con `git status` y `git check-ignore` queda pendiente hasta disponer de Git. El inventario directo detectó 46 archivos candidatos, ningún archivo prohibido y ningún patrón de secreto de alto riesgo.
