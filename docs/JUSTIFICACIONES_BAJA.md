# Justificaciones de ofertas anormalmente bajas

## Estado de integración

El módulo está integrado técnicamente en el repositorio, incluidas su lógica de dominio, persistencia, API privada, generación documental, activos de interfaz y pruebas. Actualmente está retirado de la Suite por decisión de producto: `index.html` no carga sus activos, no existe entrada de navegación, no se monta su pantalla y las fichas de licitación no ofrecen acciones de justificaciones de baja.

Esta retirada no elimina el módulo ni sus contratos técnicos. Para retomarlo habrá que volver a conectar de forma explícita los activos `static/justificaciones_baja.js` y `.css`, el contenedor de pantalla, la navegación y las acciones de la ficha ampliada.

## Alcance

El módulo prepara borradores estimativos para un único lote. No reparte costes entre lotes, no sustituye la contabilidad del cliente y no usa IA para decidir importes. La empresa cliente debe revisar y validar los costes, medios y argumentos antes de presentar el documento.

El motor económico usa `Decimal` y es la única fuente de cálculo. Guardar, abrir o cambiar la horquilla no vuelve a generar costes. La generación y el recálculo son acciones explícitas; una línea bloqueada no cambia y un coste manual conserva su origen.

## Arquitectura

- `justificaciones_baja/domain.py`, `calculations.py`, `cost_generation.py`, `validations.py` y `snapshot.py`: dominio económico puro.
- `justificaciones_baja/documents/`: payload documental, plantilla Word, generadores Word/Excel y validadores.
- `justificaciones_baja/application/`: DTO decimal seguro y casos de uso.
- `justificaciones_baja/persistence/`: esquema SQLite y repositorio con concurrencia optimista.
- `justificaciones_baja/imports.py`: inspección y normalización segura de XLSX y texto tabulado.
- `static/justificaciones_baja.js` y `.css`: interfaz aislada.
- `app.py`: fachada estrecha de autenticación, CSRF, HTTP y descargas.

La migración `0029_justificaciones_baja` es aditiva e idempotente. Crea:

- `justificaciones_baja`: identidad indexable, estado, JSON canónico del borrador, revisión y resumen.
- `justificacion_baja_versiones`: snapshots económicos y contexto documental inmutables.
- `justificacion_baja_documentos`: Word/Excel, hashes, generación y ruta relativa.
- `justificacion_baja_assets`: imagen de ruta validada como BLOB; el borrador solo guarda `asset_id` y metadatos.
- `justificacion_baja_historial`: eventos funcionales.

Las versiones, documentos, assets e historial son append-only. Los estados son `Borrador`, `Enviado al cliente` y `Final`.

## Flujo de uso

1. Abrir una licitación y pulsar **Crear justificación de baja**, o entrar en **Justificaciones de baja**.
2. Seleccionar cliente e indicar número/nombre de lote e importe ofertado sin IVA.
3. Confirmar identificación, duración, transporte, Observatorio y gastos generales.
4. Incorporar productos por XLSX, pegado tabular o edición manual.
5. Revisar la previsualización y guardar las líneas. Cada una conserva un `line_id` estable; los nombres duplicados son válidos.
6. Definir la horquilla y pulsar **Generar costes**.
7. Ajustar mediante coste manual, bloqueo y recálculo explícito de seleccionados o no bloqueados.
8. Completar narrativa, lugar, fecha, firmante y representante; adjuntar opcionalmente PNG/JPEG de la ruta o seleccionar una imagen ya existente en la carpeta validada de la licitación.
9. Guardar y revisar errores/advertencias.
10. Pulsar **Congelar versión** cuando el cálculo sea válido.
11. Pulsar **Generar Word y Excel**. Ambos usan el mismo snapshot y payload.
12. Descargar los documentos desde su identificador registrado y cambiar el estado cuando proceda.

## Importación de productos

El asistente XLSX permite elegir hoja, fila inicial y columnas de producto, características, cantidad, precio e importe opcional. Solo admite `.xlsx`; rechaza fórmulas, macros, enlaces externos, objetos incrustados, archivos corruptos y cargas desproporcionadas. La previsualización no persiste el fichero.

El pegado tabular acepta filas copiadas de Excel con tabulaciones. Ambos métodos reconocen decimales españoles, ignoran filas vacías y totales, muestran errores por fila y avisan si `cantidad × precio` difiere del importe importado. La confirmación incorpora valores, no fórmulas.

## Transporte, costes y advertencias

La fecha/URL del Observatorio, vehículo, tarifa por kilómetro y tarifa por hora son datos manuales y editables. Google Maps no se automatiza: se introducen kilómetros, horas y texto humano, y la captura es opcional.

Las anomalías no se corrigen silenciosamente. Entre otras, se muestran: oferta distinta de las líneas, margen negativo, coste superior al precio, coste manual, beneficio negativo, residual visual, fecha/URL del Observatorio pendiente e imagen ausente. Solo los errores matemáticos o estructurales impiden congelar.

## Versionado y documentos

Una versión congelada no se modifica. Editarla crea un nuevo borrador basado en la versión anterior y la siguiente congelación incrementa el número. Regenerar conserva cifras y nunca sobrescribe archivos.

En uso real, el servidor exige una carpeta de licitación existente dentro de la base Dropbox configurada y escribe solo al pulsar **Generar Word y Excel**:

```text
<carpeta de licitación>/
  Justificaciones de baja/
    Lote_<número>/
      Justificacion_<id>/
        Version_001/
```

El número de lote se toma de la versión congelada, no del borrador actual. El identificador de la justificación evita mezclar documentos de dos clientes o borradores distintos del mismo lote.

La base de datos almacena rutas relativas, tamaño y SHA-256. La descarga autenticada recibe únicamente `document_id`, vuelve a validar base, ruta, extensión, tamaño y hash, y no acepta rutas aportadas por el navegador.

## Permisos y concurrencia

- Administrador: crear, editar, importar, generar/recalcular costes, adjuntar imagen, congelar, documentar y cambiar estado.
- Nuria/revisor: listar, consultar historial/versiones y descargar.

Todas las mutaciones exigen sesión de administrador y token CSRF. Cada guardado envía `revision`; una revisión obsoleta devuelve `409 Conflict` y no sobrescribe los cambios de otra pestaña.

## Pruebas y desarrollo

Las pruebas usan SQLite y carpetas temporales dentro del proyecto. No llaman a Dropbox, correo, Telegram, IA ni otros servicios reales. Comandos principales:

```powershell
.\.venv\Scripts\python.exe -m pytest webapp/infonalia_webapp/tests -q -k justificaciones_baja --basetemp tmp/pytest-jb
node --check webapp/infonalia_webapp/static/justificaciones_baja.js
.\.venv\Scripts\python.exe -m pytest -q --basetemp tmp/pytest-full
```

## Limitaciones conocidas

- No hay escenarios multilote, reparto conjunto, PDF ni reimportación del Excel generado.
- No se descarga automáticamente el último Observatorio.
- Google Maps y la lectura asistida de pliegos no se automatizan en el MVP.
- El Word depende de la plantilla versionada; su paginación final puede variar según la versión de Word y la impresora del equipo.
- El resultado sigue siendo un borrador estimativo pendiente de validación empresarial.

## Primera prueba real

1. Hacer copia de seguridad operativa habitual y arrancar la Suite normalmente.
2. Abrir una licitación cuya carpeta Dropbox figure como válida.
3. Crear una justificación y elegir un cliente existente.
4. Introducir un único lote y revisar especialmente importe sin IVA, semanas, entregas, ruta, tarifas y gastos.
5. Importar la oferta por XLSX y comprobar la suma de líneas antes de confirmar.
6. Generar costes, bloquear/editar las líneas necesarias y revisar el resumen y todas las advertencias.
7. Adjuntar la captura de ruta y completar los textos.
8. Guardar, reabrir y confirmar que los costes no han cambiado.
9. Congelar la versión y generar Word/Excel.
10. Descargar ambos, revisar el borrador con el cliente y, si hay cambios, editar para crear una nueva versión; nunca modificar la versión congelada anterior.
