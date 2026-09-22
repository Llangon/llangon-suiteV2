# Ficha Llangon v2

## Qué incluye

`Ficha_Llangon_v2.xlsm` (versión 2.0.1) es una herramienta local desacoplada de la aplicación web. Contiene:

- hoja de trabajo `Ficha`;
- vista derivada `Informe_PDF` para previsualización y contingencia;
- catálogos y caché local en `_Listas`;
- metadatos y registro de campos en `_Llangon`;
- criterios de adjudicación ampliables mediante tablas y botones explícitos;
- revisión de errores, advertencias e información;
- importación de páginas públicas o XML de PLACE;
- actualización manual de clientes desde SQLite en solo lectura;
- PDF profesional mediante Python/ReportLab.

Abrir el libro no consulta SQLite, no ejecuta el bridge y no actualiza clientes.

## Instalación del bridge

La reconstrucción de la plantilla instala el bridge automáticamente. Si el repositorio se ha movido o se necesita repararlo, desde la raíz:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_llangon_excel_bridge.ps1
```

El instalador crea:

```text
%LOCALAPPDATA%\LlangonSuite\bridge\llangon-excel-bridge.cmd
```

El lanzador conserva la ubicación del repositorio y utiliza su `.venv`. No instala un servidor, no crea tareas Windows y no guarda credenciales.

Si el libro permanece dentro del repositorio, también puede localizar directamente `scripts/windows/llangon_excel_bridge.cmd` sin instalación.

## Uso habitual

1. Guarde una copia de la plantilla con el expediente y cliente correspondientes.
2. Seleccione el cliente disponible en la caché.
3. Use `Actualizar clientes` solo cuando quiera refrescar la lista desde la Suite.
4. Introduzca una URL o ruta XML en `Origen PLACE` y pulse `Importar PLACE` cuando proceda.
5. Complete los campos manuales y las tablas de criterios. Use `+ criterio de juicio` o `+ criterio automático` para insertar filas; el libro desplaza las secciones inferiores y conserva tablas, fórmulas y nombres estables.
6. Pulse `Revisar ficha`.
7. Pulse `Preparar PDF` para generar el documento ReportLab.
8. Use `Abrir informe / PDF` para abrir el último PDF o regenerar `Informe_PDF`.

## Clientes y modo offline

- La caché permanece dentro de cada libro.
- Una actualización fallida no debe borrar la caché existente.
- La lista incluye el ID real, nombre mostrado, razón social mínima, estado y fecha de actualización.
- Los duplicados se distinguen por razón social e ID.
- Los clientes inactivos se conservan y se señalan.
- El botón es la única acción que consulta SQLite.

El bridge deriva la base como:

```text
webapp/infonalia_webapp/data/infonalia.db
```

La conexión utiliza `mode=ro`, `PRAGMA query_only=ON` y un autorizador que deniega DML, DDL, transacciones, `ATTACH` y migraciones.

El intercambio temporal de clientes usa TSV UTF-8 con esquema `1`. Esta elección mantiene sencilla y auditable la carga desde VBA. La operación `clients` es cerrada: Excel no puede enviar SQL ni elegir otra base. Los ficheros temporales se eliminan al terminar.

## PLACE

- Se admiten archivos XML locales.
- Se admiten tanto la URL normal de una licitación como una URL XML de PLACE.
- La Suite consulta la página con cabeceras de navegador, reintentos acotados y redirecciones restringidas a HTTPS bajo `contrataciondelestado.es`.
- Cuando la página enlaza publicaciones XML oficiales, se utiliza primero la más reciente; el HTML queda como contingencia.
- El límite de respuesta es 2 MB.
- Un XML parcial solo aporta campos presentes; nunca vacía otros campos.
- Si un valor importado difiere del trabajo manual, se solicita confirmación antes de sustituirlo.

## PDF y fallback

`Preparar PDF` genera el PDF canónico mediante el bridge y ReportLab. Los errores bloquean la salida final, pero permiten generar un borrador identificado. Las advertencias no bloquean tras confirmación.

La ficha se entrega al renderer como JSON versionado (`payload_version: 1.1`). Las URL de licitación válidas se incluyen como enlaces pulsables en el PDF ReportLab.

Si Python o el bridge no están disponibles:

1. abra `Informe_PDF`;
2. revise la vista derivada;
3. utilice `Exportar PDF Excel`.

La salida de Excel es una contingencia; la paginación profesional corresponde al renderer ReportLab.

## Fallos habituales

### No se encuentra el bridge

- Ejecute el instalador anterior.
- Compruebe que el repositorio conserva `.venv`.
- Si el repositorio se movió, vuelva a ejecutar el instalador.

La ficha continúa funcionando offline.

### No se puede abrir SQLite

- Compruebe que existe la base local de la Suite.
- Reintente manualmente cuando la Suite haya finalizado una operación larga.
- No borre la caché del libro.

### Macros bloqueadas

Use una ubicación de confianza aprobada o una plantilla firmada. No desactive globalmente la seguridad de macros.

### El PDF final está bloqueado

Pulse `Revisar ficha` y corrija los errores. Si necesita revisar el diseño antes de completar todos los datos, genere un borrador.

## Reconstrucción de la plantilla

Las fuentes VBA se mantienen en `macros/ficha_llangon_v2`. La estructura base se genera con `scripts/build_ficha_llangon_v2.mjs` y se finaliza con:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\finalize_ficha_llangon_v2.ps1 `
  -BaseWorkbook .\tmp\ficha_llangon_v2_builder\Ficha_Llangon_v2_base.xlsx `
  -OutputWorkbook .\webapp\infonalia_webapp\tender_documents\templates\Ficha_Llangon_v2.xlsm
```

La reconstrucción requiere acceso al modelo VBA únicamente en el equipo de desarrollo. Los usuarios de la ficha no necesitan ese permiso.

La verificación estática y la aceptación real en Excel se ejecutan con:

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_ficha_llangon_v2.py `
  .\webapp\infonalia_webapp\tender_documents\templates\Ficha_Llangon_v2.xlsm

powershell -ExecutionPolicy Bypass -File .\scripts\windows\test_ficha_llangon_v2_excel.ps1 `
  -Workbook .\webapp\infonalia_webapp\tender_documents\templates\Ficha_Llangon_v2.xlsm
```

La segunda prueba trabaja sobre una copia temporal, ejecuta la ruta real de `Actualizar clientes` contra el bridge instalado, comprueba que el hash de SQLite no cambie, valida los dos contratos PLACE, genera ambas rutas de PDF, guarda, reabre y comprueba que el hash de la plantilla maestra no cambie.

## Fuera de alcance de esta versión

- escritura Excel → SQLite;
- sincronización bidireccional con la Suite;
- nuevas pantallas o endpoints web;
- asociación automática con `cliente_envios`;
- integración real con IA;
- índice Word;
- migración histórica.
