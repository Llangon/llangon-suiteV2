# Arquitectura del descargador de PLACE

## Objetivo

PLACE conserva únicamente el acceso, la navegación y la extracción propios de
la plataforma. El núcleo común recibe modelos normalizados y se responsabiliza
de identidad, comparación, versiones, estado técnico, contenido documental y
escritura segura.

La salida operativa de preguntas es un DOCX nativo. Se genera directamente
desde el modelo neutral `QuestionDocument`, se valida como paquete OOXML y se
publica mediante la misma capa segura que coordina el estado. El renderizador
RTF se conserva únicamente para compatibilidad histórica; el flujo oficial no
lo invoca ni crea ambos formatos en paralelo.

## Dirección de dependencias

```text
modelos comunes
      ↑
estado, sincronización, documento y escritura comunes
      ↑
adaptador PLACE
      ↑
fachadas Descargar_Preguntas_PLACE.py y Descargar_PLACE.py
```

Los módulos de `descargadores/common` no importan el adaptador PLACE. El motor
de comparación no importa los renderizadores. Los renderizadores DOCX y RTF
solo consumen el modelo documental neutral.

## Árbol relevante

```text
herramientas_python/
├── Descargar_PLACE.py                    # fachada operativa y credenciales Suite
├── Descargar_Preguntas_PLACE.py          # fachada compatible y CLI de preguntas
└── descargadores/
    ├── common/
    │   ├── question_models.py             # preguntas, snapshots, resultados y errores
    │   ├── download_models.py             # documentos remotos, extensiones y nombres
    │   ├── download_results.py            # contrato serializable de resultados
    │   ├── question_state.py              # esquema v2 y migración
    │   ├── question_sync.py               # identidad, comparación y versionado puros
    │   ├── document_model.py              # contenido documental neutral
    │   ├── corporate_document.py          # configuración corporativa única
    │   ├── docx_renderer.py               # renderer DOCX oficial y validación OOXML
    │   ├── rtf_renderer.py                # renderer RTF histórico
    │   ├── safe_files.py                  # salida textual/binaria y publicación segura
    │   └── question_workflow.py           # coordinación del núcleo común
    └── place/
        ├── errors.py                      # errores específicos de PLACE
        ├── session.py                     # sesión, autenticación y JSF/ViewState
        ├── questions.py                   # extracción y snapshot completo
        └── documents.py                   # navegación y recuperación documental
```

## Responsabilidades

La clasificación aplicada antes de mover código fue:

- **Específico de PLACE:** sesión, autenticación, JSF/ViewState, selectores,
  paginación, snapshot remoto y obtención de documentos mediante sus enlaces.
- **Común entre plataformas:** modelos, normalización, huellas, estado, migración,
  comparación, numeración, versiones, contenido documental, resultados,
  extensiones, nombres y escritura segura.
- **Flujo propio de la Suite:** resolución del destino, lectura de credenciales
  configuradas y llamada desde `Descargar_Licitacion.py`.
- **Aún no generalizable:** estrategia HTTP, navegación de pliegos y resolución
  de formularios. Permanecen en PLACE hasta contrastarlas con una segunda
  plataforma.

`place/session.py` conoce cookies, formularios JSF, enlaces internos y
autenticación. `place/questions.py` conoce el HTML, la paginación y cómo decidir
si el snapshot remoto es completo. `place/documents.py` obtiene los bytes usando
la sesión PLACE, pero delega su nombre, extensión y guardado local.

`question_sync.py` trabaja exclusivamente con `PlatformQuestion` y estados en
memoria. Mantiene identidades, números, versiones, retiradas y restauraciones.
`question_state.py` conserva el esquema 2 en `.llangon-place`; no depende de los
documentos visibles. `document_model.py` transforma el estado vigente en una
jerarquía de contenido sin códigos de formato. `docx_renderer.py` genera el
paquete DOCX oficial y `rtf_renderer.py` conserva la serialización histórica;
ninguno toma decisiones de comparación o estado.

`safe_files.py` es la implementación única para contenido textual o binario,
escritura temporal, validación de rutas, no sobrescritura, colisiones, bloqueos
transitorios y publicación coherente del documento con el estado.

## Formato DOCX oficial

`python-docx==1.2.0`, ya declarado en
`webapp/infonalia_webapp/requirements.txt`, construye el documento en memoria.
No hay conversión desde RTF, automatización de Word, LibreOffice ni PDF en el
funcionamiento normal.

El nombre visible es
`Preguntas y respuestas a fecha YYYY-MM-DD HH-MM-SS.docx`. La presentación es
A4 vertical, monocroma y editable: cabecera corporativa de Llangon, título y
fecha de actualización, tabla de dos columnas con los datos principales, enlace
real de texto corto y listado cronológico único. Los avisos, versiones,
retiradas, reapariciones y adjuntos proceden íntegramente de `QuestionDocument`.

Antes de publicar se comprueban el ZIP, los tipos de contenido, las partes y
relaciones OOXML, la apertura con `python-docx`, los hipervínculos externos, la
ausencia de macros y componentes activos y la ausencia de rutas locales,
temporales o metadatos de usuario. Los metadatos corporativos identifican a
Llangon y el expediente.

El resultado estructurado usa `document_generated`, `document_format`,
`document_path`, `document_name` y `document_sha256`. Las claves RTF heredadas
permanecen presentes pero son falsas o vacías cuando el formato es DOCX.

## Compatibilidad

Los nombres y firmas utilizados actualmente continúan disponibles desde
`Descargar_PLACE.py` y `Descargar_Preguntas_PLACE.py`. Las fachadas reexportan o
delegan en una sola implementación; la copia
`Descargar_PLACE.pre_preguntas_20260716.bak` permanece únicamente como respaldo
histórico y no participa en la ejecución.

Los puntos de entrada conservados son:

- `Descargar_Licitacion.py`, usado por la Suite y los BAT;
- ejecución directa de `Descargar_PLACE.py`;
- ejecución directa de `Descargar_Preguntas_PLACE.py`;
- importaciones directas de sus funciones históricas;
- carga mediante `importlib`, utilizada por la integración y las pruebas.

La operación explícita de mantenimiento
`--regenerar-docx-desde-estado` pertenece a
`Descargar_Preguntas_PLACE.py`. Lee un estado v2 existente y publica un DOCX
nuevo sin consultar PLACE, sin pedir credenciales y sin modificar el estado,
el snapshot, las versiones ni los eventos. No se ejecuta desde el BAT ni desde
el flujo normal; sirve exclusivamente para crear de forma controlada una salida
DOCX a partir de memoria técnica ya válida.

## Estado y errores

El estado sigue en `.llangon-place/questions_state.json`, con esquema 2. La
migración desde esquema 1 continúa creando
`questions_state.pre_schema_2.json`. Los errores de autenticación, sesión,
estructura y snapshot se clasifican en el adaptador PLACE; los errores de
estado, renderizado y escritura se clasifican en el núcleo común. Un error
remoto o local no se convierte en “sin cambios” y no sustituye el último estado
válido.

## Añadir otra plataforma

Un segundo adaptador debe producir un `QuestionSnapshot` completo compuesto por
`PlatformQuestion`, aportar metadatos normalizados y clasificar sus propios
errores de acceso. No debe copiar comparación, numeración, estado, renderizado
ni escritura. La segunda plataforma servirá para confirmar qué reglas de acceso
adicionales merecen generalizarse; no se ha anticipado una abstracción HTTP
universal.

## Añadir otro formato

Otro formato debe implementar un contrato textual o binario que reciba
`QuestionDocument`, declare extensión, render y validación, y publique siempre
mediante `safe_files.py`. No requiere modificar autenticación, navegación,
extracción PLACE, comparación, versionado, estado, retiradas ni restauraciones.

## Límites deliberados

No se han adaptado otros descargadores ni creado un sistema de plugins. La
resolución de la carpeta y las credenciales de la Suite siguen en la fachada
operativa porque pertenecen al flujo actual. La obtención HTTP continúa en el
adaptador PLACE cuando necesita sesión, cookies o formularios propios.
