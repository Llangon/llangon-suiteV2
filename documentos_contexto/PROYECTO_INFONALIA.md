# Proyecto Infonalia

> Documento histórico. Para el estado vigente del monorepo deben consultarse `README.md` y `PROJECT_CONTEXT.md`.

## Objetivo

Centralizar el trabajo de Infonalia en una app privada para que varias personas puedan revisar licitaciones, decidir que expedientes interesan y descargar la documentacion en Dropbox sin depender del Excel como unico punto de trabajo.

## Flujo Principal

1. Importar el correo `.msg` de Infonalia.
2. Revisar las licitaciones recibidas por dia.
3. Filtrar internamente lo que no interesa.
4. Marcar lo que queda como pendiente de revisión.
5. Registrar la decision final: descartar, descargar o hacer.
6. Descargar los ficheros de la plataforma correspondiente.
7. Dejar la licitacion como descargada y con su carpeta enlazada.

## Roles

- Administracion: importa Infonalia, filtra, ejecuta descargas y revisa que las carpetas quedan bien.
- Revisión o dirección: revisa las licitaciones prefiltradas y decide si se descartan, se descargan o se preparan.
- Tecnico: mantiene descargadores, app, copias y mejoras.

## Estado Actual

- App web local con login.
- Importacion directa desde `.msg`.
- Importacion CSV mantenida como herramienta secundaria.
- Estados por licitacion y por dia Infonalia.
- Descarga mediante lanzador general `Descargar_Licitacion.py`.
- Integracion con Dropbox cuando la carpeta existe o se puede resolver.
- Estilo visual adaptado a Llangon.

## Decisiones Tecnicas

- La version actual usa SQLite para ir rapido y mantenerlo sencillo.
- Para trabajar varios usuarios, lo recomendable es ejecutar una unica instancia de la app en un PC o servidor compartido.
- Para acceso desde fuera de la oficina, o muchos usuarios, el siguiente paso seria pasar a una base de datos central tipo PostgreSQL y publicar la app en un hosting privado.
- Los datos reales no deben subirse a un repositorio: base de datos, temporales, adjuntos y descargas quedan fuera del codigo.

## Hoja De Ruta

### Fase 1: Equipo Interno

- Ejecutar la app en un PC fijo o mini servidor.
- Dar acceso al resto por la red local.
- Crear usuarios reales y contrasenas individuales.
- Dejar Dropbox como destino unico de descargas.

### Fase 2: Control Y Seguimiento

- Panel de dias pendientes.
- Vista de revisión con las licitaciones pendientes de decisión.
- Comentarios por licitacion.
- Historico de cambios de estado.
- Avisos de vencimiento.

### Fase 3: App Privada Completa

- Base de datos central.
- Acceso desde PC, Android y Apple.
- Permisos por usuario.
- Copias de seguridad.
- Despliegue privado con HTTPS.
