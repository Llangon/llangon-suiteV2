# Clientes y Envíos a clientes

## Qué cubre esta fase

Este módulo añade dos piezas de trabajo dentro de Llangon Suite V2:

- `Clientes`: ficha fiscal y operativa básica del cliente.
- `Envíos a clientes`: preparación documental y generación de correos Outlook listos para revisar y enviar manualmente.

La Suite no envía el correo al cliente en esta fase. Solo prepara el borrador `.msg` o, si Outlook COM no está disponible, un fallback controlado `.eml`.

## Alcance actual

Incluye:

- alta y edición de clientes con ficha fiscal completa;
- creación de envíos desde una licitación;
- creación de envíos desde una actuación;
- selección de carpeta de Dropbox y adjuntos solo dentro de esa carpeta;
- propuesta automática de destinatario, asunto y cuerpo según el tipo de envío;
- preparación de correo Outlook en modal editable;
- apertura de la carpeta o del correo preparado cuando el entorno lo permite;
- marcado manual como enviado;
- historial básico en licitación, actuación y ficha de cliente;
- integración en `Agenda / Pendientes`;
- inclusión de los envíos en el correo diario de Agenda.

No incluye todavía:

- pendiente de respuesta;
- respondido;
- cerrado;
- seguimiento posterior de respuestas;
- contratos PDF automáticos;
- envío directo del correo desde la Suite.

## Estados disponibles

Los estados operativos del envío son:

1. `En preparación`
2. `Listo para preparar correo`
3. `Correo Outlook generado`
4. `Enviado`
5. `Incidencia / Error`
6. `Cancelado / No procede`

Los estados de respuesta del cliente no deben usarse en esta fase.

## Tipos de envío

El selector incluye:

- Ficha inicial / resumen de licitación
- Plantilla de oferta
- Documentación para revisión
- Documentación para firma
- Requerimiento
- Subsanación
- Aclaración
- Documentación adicional
- Contrato / encargo
- Recordatorio
- Otro

Cada tipo propone asunto y cuerpo, pero ambos pueden editarse antes de generar el correo.

## Flujo desde licitación

1. Abrir la ficha de la licitación.
2. Entrar en `Envíos a clientes`.
3. Pulsar `Crear envío a cliente`.
4. Elegir cliente, tipo, estado inicial y carpeta Dropbox.
5. Cargar archivos disponibles de esa carpeta.
6. Seleccionar adjuntos válidos.
7. Guardar el envío.
8. Cuando el estado esté listo, abrir `Preparar correo Outlook`.
9. Revisar destinatario, asunto, cuerpo y adjuntos.
10. Generar el correo.
11. Abrir carpeta o correo preparado.
12. Marcar manualmente como enviado cuando ya salga desde Outlook.

## Flujo desde actuación

1. Abrir la actuación.
2. Pulsar `Crear envío de esta actuación`.
3. Seleccionar cliente, carpeta y adjuntos.
4. Guardar.

El envío queda vinculado a:

- la actuación;
- la licitación asociada;
- el cliente elegido.

## Validaciones de Dropbox y adjuntos

Se aplican estas reglas:

- la carpeta es obligatoria;
- la carpeta debe quedar dentro de `LLANGON_DROPBOX_BASE_PATH` o de la base heredada permitida;
- no se admiten rutas con salida fuera de la base;
- los adjuntos deben existir y pertenecer a la carpeta asignada al envío;
- no se admiten carpetas como adjuntos;
- no se admiten ficheros vacíos;
- no se admiten temporales tipo `~$`;
- la subcarpeta `Correos preparados` no se ofrece como origen de adjuntos;
- si el tamaño total supera el umbral recomendado, se informa con aviso;
- si supera el límite duro, el guardado o la generación se rechazan.

## Generación del correo

La carpeta de salida es:

- `...\Correos preparados\`

El nombre del correo se compone con:

- fecha;
- tipo de envío;
- cliente;
- expediente.

El flujo técnico es:

1. Intentar generar `.msg` con Outlook COM en Windows.
2. Si Outlook COM no está disponible o falla, generar `.eml` como fallback seguro.
3. Guardar la ruta final en base de datos.
4. Intentar abrir el fichero generado si el sistema lo permite.
5. Si la apertura falla, mantener la ruta guardada y mostrar acciones de apertura manual.

## Historial y trazabilidad

Cada envío registra eventos básicos como:

- creación;
- actualización;
- generación de correo;
- error de generación;
- marcado manual como enviado.

La licitación muestra su lista de envíos y cada cliente conserva un historial simple de envíos asociados.

## Agenda y correo diario

Los envíos pendientes aparecen en `Agenda / Pendientes` en estos bloques:

- `Tareas y actuaciones pendientes`
- `Envíos listos para preparar correo`
- `Correos Outlook generados pendientes de marcar como enviados`
- `Envíos con incidencia`

El correo diario de Agenda reutiliza ese mismo conjunto y no crea un segundo correo diario independiente.

## Permisos

- `admin`: crea y edita clientes y envíos.
- `nuria`: puede ver pendientes, abrir el borrador, preparar correo, abrir carpeta y marcar como enviado.

Los endpoints mutantes usan el patrón CSRF existente de la Suite.

## Requisitos de entorno

Variables relevantes:

```text
LLANGON_DROPBOX_BASE_PATH=C:\Ruta\Dropbox\00000 LLANGON
INFONALIA_HOST=127.0.0.1
INFONALIA_PORT=8787
```

Notas:

- la aplicación debe arrancar aunque Outlook no esté instalado;
- Outlook COM solo se usa en tiempo de generación del borrador;
- el flujo sigue siendo local sobre Dropbox Desktop sincronizado.

## Limitaciones actuales

- no hay seguimiento de respuestas del cliente;
- la Suite no detecta automáticamente si Outlook ya ha enviado el correo;
- el marcado como enviado sigue siendo manual;
- no existe todavía administración avanzada de plantillas de correo.
