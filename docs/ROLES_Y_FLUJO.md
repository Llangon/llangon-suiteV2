# Roles Y Flujo De Trabajo

## Roles

- Administración: importa información, realiza el primer filtro, gestiona usuarios y ejecuta descargas.
- Revisión o dirección: decide qué licitaciones se descartan, se descargan o se preparan.
- Técnico: mantiene la aplicación, los descargadores, las copias y el despliegue.

## Estados funcionales

- Pendiente: licitación recién importada y todavía sin revisar.
- Descartada internamente: no debe pasar a revisión.
- Pendiente de revisión: espera una decisión de revisión o dirección.
- Descartar: la decisión final es no continuar.
- Descargar: se solicita descargar la documentación.
- Hacer: se solicita preparar la licitación.
- Descargada: la documentación ya está creada y guardada.

Algunos identificadores internos heredados todavía usan nombres históricos. Su sustitución requiere una migración funcional separada y no forma parte del saneamiento documental.

## Flujo diario

1. Importar el mensaje `.msg` de Infonalia.
2. Revisar las nuevas licitaciones.
3. Descartar internamente lo que no debe avanzar.
4. Enviar lo restante a revisión.
5. Registrar la decisión: descartar, descargar o preparar.
6. Descargar los ficheros cuando corresponda.
7. Confirmar que la carpeta está lista y cerrar la tarea.

## Vista de revisión

Debe mostrar únicamente la información necesaria para decidir:

- expediente,
- objeto,
- organismo,
- provincia,
- presupuesto,
- fecha límite,
- tipo,
- enlaces,
- botones de decisión.

## Vista de administración

Debe incluir:

- importación MSG y CSV,
- filtros por día y estado,
- descarga de documentación,
- ruta de carpeta,
- comentarios internos,
- indicadores de vencimiento,
- configuración de usuarios y notificaciones.

