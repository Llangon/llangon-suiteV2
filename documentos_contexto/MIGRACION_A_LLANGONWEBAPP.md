# Migracion A LlangonWebApp

> Documento histórico anterior a `Llangon-SuiteV2`. Se conserva como antecedente y no sustituye a `README.md` ni a `PROJECT_CONTEXT.md`.

## Objetivo

Mover el trabajo de esta conversacion al proyecto de Codex llamado `LlangonWebApp`, manteniendo el contexto funcional y los archivos creados para Infonalia.

## Contexto Que Debe Conservarse

Estamos creando una app privada para gestionar el flujo de Infonalia con varios companeros:

1. Importar directamente el correo `.msg` de Infonalia.
2. Agrupar licitaciones por dia Infonalia.
3. Filtrar internamente las licitaciones no interesantes.
4. Pasar licitaciones a decisión de revisión o dirección.
5. Registrar decisiones: descartar, descargar o hacer.
6. Ejecutar descargadores por plataforma.
7. Guardar la documentacion en Dropbox.
8. Mantener una interfaz web privada accesible desde PC, Android y Apple.

## Archivos Principales A Llevar

Carpeta de app:

```text
infonalia_webapp/
```

Descargadores:

```text
Descargar_Licitacion.py
Descargar_PLACE.py
Descargar_JuntaAndalucia.py
Descargar_ComunidadMadrid.py
Descargar_Euskadi.py
```

Modulos VBA generados:

```text
CrearCarpetas_corregido.bas
CrearEmailOutlook_Llangon_mejorado.bas
```

Documentacion de proyecto:

```text
PROYECTO_INFONALIA.md
docs/DESPLIEGUE_COLABORACION.md
docs/ROLES_Y_FLUJO.md
```

## Datos Que No Conviene Mover Como Codigo

No deben subirse como parte del codigo:

```text
infonalia_webapp/data/infonalia.db
infonalia_webapp/data/secret.key
infonalia_webapp/data/uploads/
infonalia_webapp/data/tmp_pdf/
infonalia_webapp/data/descargas/
```

Estos quedan excluidos en:

```text
infonalia_webapp/.gitignore
```

## Estado Actual De La App

La app ya incluye:

- Login local.
- Importacion directa desde `.msg`.
- Importacion CSV secundaria.
- Vista de dias Infonalia.
- Vista de licitaciones.
- Estados:
  - Pendiente
  - Descartada por mi
  - Pendiente de revisión
  - Descartar
  - Descargar
  - Hacer
  - Descargada
- Descarga por plataforma usando `Descargar_Licitacion.py`.
- Deteccion de Dropbox mediante `INFONALIA_DROPBOX_ROOT` o `%USERPROFILE%\Dropbox\00000 LLANGON`.
- Estilo visual adaptado a Llangon.
- Configuracion por `.env`.

## Como Arrancar En El Nuevo Proyecto

Dentro de `infonalia_webapp`, ejecutar primero:

```text
Instalar dependencias.bat
```

Despues:

```text
Arrancar Infonalia.bat
```

La app queda en:

```text
http://127.0.0.1:8787
```

## Siguiente Trabajo Recomendado En LlangonWebApp

1. Copiar estos archivos al proyecto `LlangonWebApp`.
2. Revisar que `Descargar_Licitacion.py` encuentra los descargadores desde la nueva ubicacion.
3. Crear usuarios reales para cada persona.
4. Separar la vista de administración y la vista de revisión.
5. Anadir historico de cambios y comentarios.
6. Preparar despliegue en un PC anfitrion o servidor interno.

## Nota Para Continuar La Conversacion

Si se abre una nueva conversacion dentro de `LlangonWebApp`, pegar este resumen:

```text
Estamos migrando la app privada de Infonalia desde un workspace local anterior. La app está en `webapp/infonalia_webapp` y usa Python y SQLite. Importa MSG de Infonalia, agrupa por días, maneja estados de licitaciones y llama a descargadores por plataforma desde `herramientas_python`. Hay que continuar desde la estructura documentada en `MIGRACION_A_LLANGONWEBAPP.md` y mantener el destino de descargas como configuración local.
```
