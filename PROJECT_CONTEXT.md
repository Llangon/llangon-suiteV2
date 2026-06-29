# Project Context

## Situación

`Llangon-SuiteV2` es el monorepo limpio que sustituye al trabajo anterior. Reúne la aplicación privada de Infonalia, la web pública, herramientas Python, macros VBA y documentación operativa sin conservar historiales Git anteriores.

La memoria del proyecto debe vivir en archivos versionados y revisables. Una conversación local de Codex puede ayudar durante una tarea, pero no debe ser la única fuente de contexto, decisiones o procedimientos.

## Alcance

- Aplicación privada para importar y revisar información de licitaciones.
- Descargadores por plataforma.
- Web pública independiente de la zona privada.
- Macros y documentación de apoyo.

## Criterios de negocio

- No se incluye una línea de negocio de Portugal.
- Llangón no elabora ni decide las ofertas económicas de las empresas clientes.
- Llangón puede guiar, revisar coherencia, preparar plantillas y apoyar la organización documental.
- La empresa cliente elabora, decide y valida siempre su oferta económica.

## Criterios técnicos

- Priorizar la seguridad de datos y la portabilidad entre equipos.
- Mantener código y documentación en Git; mantener datos y secretos fuera de Git.
- Resolver rutas desde el repositorio o mediante variables de entorno.
- No incluir rutas rígidas ligadas a un usuario o equipo.
- Mantener Firebase público separado de la aplicación privada.
- No activar descargas ni exposición de red por defecto.

## Componentes

- `webapp/infonalia_webapp/`: servidor Python, frontend, SQLite local e importación de mensajes.
- `herramientas_python/`: descargadores y orquestador.
- `firebase/public_firebase/`: web pública estática.
- `firebase.json`: configuración de Firebase Hosting que apunta a `firebase/public_firebase`.
- `macros/`: automatizaciones VBA.
- `docs/`: operación y colaboración.
- `documentos_contexto/`: documentos históricos, no instrucciones vigentes por sí solos.

## Límites y riesgos conocidos

- SQLite está orientado a una instancia interna y concurrencia limitada.
- No existe una batería completa de pruebas automatizadas.
- Los descargadores dependen de servicios externos y navegadores locales.
- Persisten identificadores técnicos heredados asociados al rol de revisión para conservar compatibilidad con bases de datos existentes. Su cambio exige una migración funcional específica.
- El identificador real del proyecto Firebase y las rutas de datos deben configurarse localmente.
