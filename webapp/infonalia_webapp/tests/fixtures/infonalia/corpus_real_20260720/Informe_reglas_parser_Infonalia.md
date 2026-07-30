# Informe de seguridad del parser de correos Infonalia

## Corpus revisado

- 39 archivos MSG, fechados entre el 1 de junio y el 20 de julio de 2026.
- 396 bloques de licitación detectados tanto en HTML como en texto plano.
- 365 referencias Infonalia únicas.
- 31 apariciones duplicadas, explicadas íntegramente por tres parejas de correos con contenido repetido.
- Todos los bloques contienen las siete etiquetas nucleares: Ref. Infonalia, Nº Expediente, Organismo, Resumen del Objeto, Provincia de Ejecución, Presupuesto y Plazo Presentación.
- Existen valores explícitos `No consta`; no deben confundirse con campos ausentes.
- 25 apariciones, correspondientes a 20 referencias únicas, contienen `idExpediente=` en la URL de la Junta de Andalucía.
- Existe además un objeto contractual que contiene la palabra `expediente`, demostrando que buscar esa palabra por subcadena también puede corromper el dato aunque no haya una URL de Andalucía.

## Principio de seguridad

No debe confiarse la seguridad a que el parser sea capaz de interpretar cualquier cambio futuro. La garantía debe ser: si el formato cambia o hay una discrepancia, el correo no puede darse por procesado y la incidencia debe quedar visible. Cero descartes silenciosos.

## Reglas de extracción

1. Conservar una copia inmutable o huella del mensaje original y su Message-ID.
2. Extraer y analizar de forma independiente `text/html` y `text/plain`.
3. Detectar bloques únicamente mediante la etiqueta completa `Ref. Infonalia:` normalizada y anclada; nunca por coincidencias parciales.
4. En HTML, trabajar sobre bloques de texto/párrafos del DOM y sobre los `href`; no interpretar el HTML mediante búsquedas indiscriminadas de palabras.
5. Separar etiqueta y valor por el primer `:` y comparar la etiqueta completa normalizada contra una lista cerrada de etiquetas admitidas.
6. `Nº Expediente` solo puede proceder de la etiqueta completa correspondiente. La palabra `expediente` dentro de un objeto, URL, ruta o parámetro no participa en la extracción.
7. Las URL se extraen en un canal separado y nunca pueden modificar campos de negocio.
8. Un valor válido nunca se sobrescribe con un valor vacío.
9. Dos apariciones idénticas de un campo pueden deduplicarse dejando traza; dos valores distintos para el mismo campo son una incidencia bloqueante.
10. `No consta` es un valor explícito válido. Vacío, etiqueta ausente y `No consta` son estados distintos.
11. Cada bloque debe contener exactamente una Ref. Infonalia y las siete etiquetas nucleares con un valor no vacío.
12. La Ref. Infonalia debe cumplir el formato conocido; cualquier formato nuevo se pone en cuarentena y se notifica, no se descarta.
13. El enlace al PDF de Infonalia debe corresponder con la Ref. Infonalia del bloque. Una discrepancia es bloqueante.

## Conciliación obligatoria

Antes de escribir en la base de datos deben coincidir:

- número de marcadores de bloque en HTML;
- número de marcadores de bloque en texto plano;
- número de bloques construidos por ambos parsers;
- conjunto y orden de referencias extraídas por ambos parsers.

Para cada correo debe cumplirse:

`detectadas = válidas + cuarentena`

Y, tras consultar la base de datos:

`válidas = nuevas insertadas + duplicadas idénticas + conflictos`

Un correo solo puede finalizar como correcto cuando `cuarentena = 0`, `conflictos = 0` y todas las igualdades cuadran.

## Escritura y estado del correo

1. Parsear y validar todo el correo antes de tocar datos reales.
2. Preparar el resultado en memoria o en una zona de staging.
3. Insertar todas las novedades en una única transacción por correo.
4. Ante cualquier error de escritura, hacer rollback completo.
5. Marcar el correo como leído/procesado solo después del commit y de la conciliación final.
6. Ante anomalía, no marcarlo como procesado; registrar una ejecución con estado de incidencia y conservar el detalle.
7. El scheduler debe seguir con los demás correos y enviar al final del ciclo un único informe consolidado de incidencias al administrador.

## Auditoría mínima por correo

- Message-ID, asunto, remitente, fecha y huella del contenido.
- Bloques detectados en HTML y texto plano.
- Referencias detectadas y resultado individual: nueva, duplicada idéntica, conflicto o cuarentena.
- Conteos de detectadas, válidas, insertadas, duplicadas, conflictos y cuarentena.
- Motivo exacto de cualquier incidencia.
- Confirmación de commit y de marcado como leído.

## Simulación aislada exigida antes de aplicar cambios

- Copiar los 39 MSG a una carpeta de fixtures dentro de un directorio temporal.
- Utilizar exclusivamente una SQLite temporal creada por pytest.
- Bloquear o simular IMAP, SMTP, Dropbox, Telegram, scheduler y cualquier acceso de red.
- Impedir expresamente que el código lea la SQLite real o `app.get_settings()` de producción.
- Comparar cada correo contra el manifiesto de resultados esperados.
- Resultado global obligatorio: 39 correos, 396 bloques, 365 referencias únicas y 31 duplicados.
- Comprobar las 25 apariciones de URLs `idExpediente=`, correspondientes a 20 referencias únicas.
- Ejecutar los duplicados antes y después de sus originales para demostrar idempotencia.
- Añadir pruebas mutantes: campo eliminado, etiqueta cambiada, HTML/texto discrepantes, campo repetido con valores distintos, HTML corrupto, URL con `idExpediente`, objeto con la palabra `expediente`, `No consta`, espacios y NBSP, etiquetas divididas entre spans y saltos de línea.
- Las mutaciones interpretables deben conservar exactamente el resultado esperado; las no interpretables deben terminar en incidencia controlada, nunca en éxito parcial silencioso.
