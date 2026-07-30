# Plan de cierre arquitectónico de los descargadores

## 1. Estado inicial encontrado

La inspección del lanzador central, la Suite y la documentación vigente demuestra que existen **seis** descargadores operativos, aunque el encargo inicial mencione cuatro:

| Plataforma | Fachada compatible | Implementación inicial | Preguntas | Estado técnico |
|---|---|---|---|---|
| PLACE | `herramientas_python/Descargar_PLACE.py` | fachada más `descargadores/place` y `Descargar_Preguntas_PLACE.py` | Sí | `.llangon-place`, esquema 2 |
| Catalunya | `herramientas_python/Descargar_Catalunya.py` | fachada más `descargadores/catalunya` | Sí | `.llangon-catalunya`, esquema 2 |
| Navarra | `herramientas_python/Descargar_Navarra.py` | script monolítico | No | No utiliza estado propio |
| Euskadi | `herramientas_python/Descargar_Euskadi.py` | script monolítico | No | No utiliza estado propio |
| Comunidad de Madrid | `herramientas_python/Descargar_ComunidadMadrid.py` | script monolítico | No | No utiliza estado propio |
| Junta de Andalucía | `herramientas_python/Descargar_JuntaAndalucia.py` | script monolítico con navegación CDP | No | No utiliza estado propio |

Las seis están registradas en `Descargar_Licitacion.py` y `webapp/infonalia_webapp/url_helpers.py`. Los BAT, el puente legado, los botones manuales, `download_jobs`, el worker y las acciones de correo terminan invocando el lanzador central. Por compatibilidad y seguridad, el cierre abarcará las seis plataformas en vez de omitir fachadas activas.

PLACE y Catalunya ya comparten correctamente el motor neutral de preguntas, el estado, el modelo documental, DOCX, retiradas/restauraciones y escritura segura. No se reescribirán esas piezas salvo ampliaciones neutrales cubiertas por regresión.

## 2. Problemas que deben resolverse

- Falta un contrato global, serializable y neutral para una ejecución completa del descargador; `SyncResult` cubre principalmente preguntas.
- Navarra, Euskadi, Comunidad de Madrid y Junta de Andalucía mezclan utilidades documentales duplicadas, navegación, extracción, descarga y `main`.
- PLACE todavía concentra coordinación general y lectura de credenciales en su fachada.
- Navarra es la única plataforma documental nueva con pruebas específicas amplias; las otras tres fachadas históricas carecen de cobertura suficiente.
- Solo Catalunya emite actualmente una línea estructurada consumible por procesos posteriores.
- La documentación vigente describe las plataformas, pero no un contrato único para el futuro monitor.

## 3. Arquitectura propuesta

```text
Suite / download_worker / futuro monitor
                 |
                 v
        Descargar_Licitacion.py
                 |
                 v
        Fachada compatible estrecha
                 |
                 v
       coordinador de plataforma
          /        |         \
      acceso   extracción   documentos
                 |
                 v
          DownloadRunResult
```

Se conservará `herramientas_python/descargadores/common` como núcleo sin jerarquías de clases complejas. Se añadirá:

- un resultado global sencillo (`DownloadRunResult`);
- capacidades de plataforma;
- registros neutrales de archivos y documentos;
- serialización estable;
- un registro de coordinadores para el futuro monitor;
- utilidades documentales comunes solo donde ya existen varios casos reales.

Los paquetes específicos quedarán bajo `descargadores/<plataforma>/`. PLACE y Catalunya mantendrán sus adaptadores actuales. Las demás plataformas tendrán como mínimo un coordinador separado de la fachada y un módulo que encapsule su navegación/extracción documental. Junta conservará CDP como detalle exclusivamente suyo.

## 4. Archivos previstos

### Nuevos

- `herramientas_python/descargadores/common/run_result.py`
- `herramientas_python/descargadores/registry.py`
- paquetes `descargadores/navarra`, `descargadores/euskadi`, `descargadores/madrid` y `descargadores/junta_andalucia`
- pruebas de contrato común, registro, fachadas e integración aislada
- documentación final de arquitectura y consumo por el monitor

### Modificados

- las seis fachadas compatibles, únicamente para delegar y emitir el resultado cuando proceda;
- `Descargar_Licitacion.py`, manteniendo argumentos y códigos de salida;
- módulos comunes solo para reutilización neutral;
- pruebas existentes de descargadores y lanzador;
- `docs/DESCARGADORES_LICITACIONES.md`.

### Movidos o eliminados

No se eliminarán fachadas. La lógica monolítica de las cuatro plataformas documentales se trasladará a paquetes específicos conservando reexportaciones necesarias para compatibilidad de imports.

## 5. Estados y migraciones

- `.llangon-place` y `.llangon-catalunya` permanecen separados y compatibles con esquema 2.
- No se crearán estados ficticios para las otras plataformas.
- No se necesita migración destructiva ni modificación de SQLite.
- El resultado global podrá informar una ruta de estado vacía cuando la plataforma no disponga de ella.

## 6. Estrategia de compatibilidad

- Mantener nombres de scripts, opciones `--destino`, códigos de salida y reglas visibles de nombres.
- Mantener helpers históricos reexportados cuando existan consumidores o pruebas.
- Mantener `Descargar_Preguntas_PLACE.py` y la regeneración desde estado.
- Mantener el lanzador por subprocess para BAT y flujos actuales.
- Añadir una API Python interna paralela para el monitor, sin obligar a los consumidores actuales a cambiar.
- No añadir preguntas a Navarra, Euskadi, Madrid o Junta.
- No modificar Dropbox, SQLite, correo ni plataformas durante las pruebas.

## 7. Pruebas previstas

- Contrato global: construcción, invariantes, serialización y estados success/warning/partial/failed.
- Registro: seis plataformas, capacidades correctas y ausencia de preguntas en cuatro de ellas.
- Fachadas: importación, firmas, argumentos y delegación.
- Documentos: extensión, nombre, hash, deduplicación, colisión y publicación atómica.
- Cada plataforma documental: primera descarga, repetido, nuevo, fallo parcial y resultado estructurado mediante sesiones simuladas.
- PLACE/Catalunya: toda la regresión de preguntas, DOCX, estados, `no_changes` y regeneración.
- Integración: lanzador, worker y prevención de trabajos duplicados con dobles locales.
- Suite completa de Python, compilación e imports; JavaScript solo si se modifica.

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Romper monkeypatches o imports de fachadas | reexportaciones y pruebas de compatibilidad |
| Cambiar nombres de archivos | conservar constructores y reglas actuales, añadir pruebas de caracterización |
| Convertir fallo parcial en éxito silencioso | resultado global con incidencias recuperables y estado `partial` |
| Duplicar abstracciones de preguntas | adaptar `SyncResult`, no reemplazar el motor validado |
| Mezclar estados | capacidades y layouts explícitos por plataforma |
| Introducir llamadas reales en tests | sesiones, HTML y binarios simulados; prohibición de red por fixture |
| Refactor excesivo de Junta/CDP | aislar la navegación sin generalizarla |
| Trabajo previo no relacionado en el árbol | limitar parches a descargadores, pruebas y documentación del bloque |

## 9. Orden de ejecución

1. Definir y probar el contrato global y el registro.
2. Modularizar Navarra como patrón documental sin preguntas.
3. Modularizar Euskadi y Madrid reutilizando únicamente utilidades probadas.
4. Modularizar Junta manteniendo CDP específico.
5. Estrechar PLACE y adaptar PLACE/Catalunya al contrato global.
6. Integrar la API Python del registro con el lanzador sin alterar subprocess ni BAT.
7. Ampliar cobertura de fachadas, resultados parciales e integración.
8. Ejecutar regresión completa, compilación, auditorías y actualizar documentación final.

