# Informe de validación del importador Infonalia fail-closed

Fecha de validación: 20 de julio de 2026.

## Resultado

**VALIDACIÓN COMPLETA SUPERADA.**

Los 39 MSG binarios exactos superan la validación de inventario, SHA-256, extracción, parseo independiente HTML/texto, conciliación, comparación campo a campo con el manifiesto, persistencia aislada en cinco órdenes y segunda ejecución completa. El resultado es 396 bloques conciliados, 365 referencias únicas y 31 apariciones duplicadas, sin omisiones, conflictos, cuarentenas ni bloques sin categoría.

Esta conclusión es exclusivamente técnica. No se activó producción ni se reprocesó ningún correo real.

## Estado inicial del repositorio

- Rama: `codex/monitor-licitaciones-e2e`, siguiendo `origin/codex/monitor-licitaciones-e2e`.
- El worktree ya contenía numerosos cambios rastreados y no rastreados antes de esta fase. Se registró `git status --short --branch` antes de modificar nada.
- No se ejecutó `git reset`, no se limpió el worktree, no se cambió de rama y no se eliminó ningún cambio existente.
- La implementación fail-closed previa estaba completa y la suite de partida tenía 1.476 pruebas verdes.
- `LLANGON_INFONALIA_STRICT_IMPORT_ENABLED=0` permanecía y permanece en `.env.example`. El `.env` privado no se leyó ni se modificó.

## Corpus exacto e inventario SHA-256

ZIP recibido:

`C:\Users\LLangon03\Downloads\corpus_infonalia_39_msg_validacion_codex.zip`

SHA-256 del ZIP:

`21c41bbfe1f395fc97b6183c462ced9c1402fd609fd65ccd6f14254c8d55c5b0`

La inspección previa a la extracción confirmó:

- 42 entradas de primer nivel.
- 39 archivos `.msg`.
- `infonalia_expected_manifest.json`.
- `Informe_reglas_parser_Infonalia.md`.
- `inventario_sha256_corpus_infonalia.json`.
- Cero entradas vacías, duplicadas, absolutas, anidadas o con recorrido `..`.

La copia binaria, sin transformación, quedó en:

`webapp/infonalia_webapp/tests/fixtures/infonalia/corpus_real_20260720/`

Validación posterior a la extracción:

| Control | Resultado |
|---|---:|
| MSG declarados por inventario | 39 |
| Entradas del inventario | 39 |
| Entradas del manifiesto | 39 |
| MSG reales | 39 |
| Bytes totales de MSG | 3.065.856 |
| SHA-256 calculados | 39 |
| Ausentes | 0 |
| Sobrantes | 0 |
| Vacíos | 0 |
| Diferencias de tamaño | 0 |
| Diferencias SHA-256 inventario/binario | 0 |
| Diferencias SHA-256 manifiesto/binario | 0 |
| Diferencias manifiesto/inventario | 0 |

El manifiesto de la fixture previa y el incluido en el ZIP tienen además el mismo SHA-256: `80644e96aab8555933e4dfc49492a34981bb020756d2065aeae833ab095aba33`. No se modificó el manifiesto para obtener el resultado.

## Camino real de lectura y aislamiento

La extracción MSG ya no está duplicada en el harness. `infonalia_msg_reader.py` es el adaptador común que abre el contenedor Outlook con `extract-msg`; lo usan tanto el harness como la importación manual de `.msg`. Después:

1. El adaptador entrega metadatos, cuerpo plano y cuerpo HTML.
2. `infonalia_import_core.py` analiza HTML y texto por separado, usando DOM para HTML.
3. El mismo `reconcile_message` usado por importación manual e importación IMAP estricta concilia conteos, referencias, orden y campos.
4. El harness clasifica en SQLite temporal cada aparición como `inserted`, `duplicate`, `conflict` o `quarantined`.
5. Las pruebas de integración verifican la fachada manual y el scheduler/IMAP con dobles; el scheduler real no se ejecuta.

Evidencia de extracción desde los binarios:

- 39/39 fechas coinciden con el manifiesto.
- 39/39 tienen Message-ID, asunto, remitente, HTML y texto plano.
- Los 39 HTML se obtuvieron como bytes UTF-8.
- 468.629 caracteres de texto plano y 2.459.677 caracteres HTML procesados.
- 422 entidades HTML y 948 atributos `href` presentes en el contenido real.
- Cero caracteres Unicode de sustitución por error de decodificación.
- Los 39 asuntos son `LICITACIONES - Envío de Novedades - 149022`.
- Se preservaron Unicode, espacios, NBSP, entidades, saltos de línea y URLs; toda diferencia material entre HTML y texto habría bloqueado el correo.

El harness solo abre los MSG de la fixture y crea SQLite dentro de `TemporaryDirectory`. Las pruebas abortan si el importador intenta abrir la SQLite productiva o crear una conexión externa. No se invoca `app.get_settings()` para obtener configuración real durante la simulación.

## Totales globales

| Magnitud | Esperado | Obtenido |
|---|---:|---:|
| Correos MSG | 39 | 39 |
| Bloques detectados en HTML | 396 | 396 |
| Bloques detectados en texto | 396 | 396 |
| Bloques conciliados | 396 | 396 |
| Referencias únicas | 365 | 365 |
| Apariciones duplicadas propias del corpus | 31 | 31 |
| Apariciones con `idExpediente=` | 25 | 25 |
| Referencias únicas con `idExpediente=` | 20 | 20 |
| Conflictos | 0 | 0 |
| Cuarentenas | 0 | 0 |
| Bloques omitidos o sin categoría | 0 | 0 |
| Diferencias de campos o metadatos | 0 | 0 |

En la primera carga cronológica se cumple globalmente:

`396 detectados = 365 inserted + 31 duplicate + 0 conflict + 0 quarantined`

La misma igualdad se comprueba por correo en la tabla siguiente.

## Resultado por correo

Los resultados de persistencia corresponden a la primera carga cronológica. Las fechas están normalizadas a UTC.

| Fichero | Fecha | SHA-256 | HTML | Texto | Conc. | Insert. | Dup. | Conf. | Cuar. | Estado |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `LICITACIONES - Envío de Novedades - 149022 (37).msg` | 2026-06-01 10:32:30 UTC | `bb48e7c0c321d83c3d628cd552895d114ac631c29ccf7972e51bbe48ed382f04` | 6 | 6 | 6 | 6 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (36).msg` | 2026-06-02 11:36:44 UTC | `14c7ade80b98c2641284f832265f9c203bd5d55ec98d81369a6146dd3fecce7b` | 15 | 15 | 15 | 15 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (35).msg` | 2026-06-03 10:51:01 UTC | `7c175e3a6349ded74c8e1e80c2226ab79f0d6718c5bd088b4514477c21d11f84` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (34).msg` | 2026-06-04 10:40:11 UTC | `892edf422e3c64f687dfaffb16ca64ad7c8854aa2a54d6d452a745ffb0a26aca` | 11 | 11 | 11 | 11 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (33).msg` | 2026-06-05 10:41:10 UTC | `343334738fa42834f4f80f55a92d3ef74aca2ac29e9130753fce4c04f2eb97ed` | 12 | 12 | 12 | 12 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (32).msg` | 2026-06-08 10:40:24 UTC | `35e9b967f1b708b6a4b4b4fcf2e96051a17c16098088a26e455d1b4bcb0b0253` | 7 | 7 | 7 | 7 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (31).msg` | 2026-06-09 10:50:54 UTC | `65fa4d22944ee180997df8c319e53b8f7981d6d353a2d64deaf350722749dbb6` | 17 | 17 | 17 | 17 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (30).msg` | 2026-06-10 10:43:29 UTC | `0d08ee204726331c483a996dd6a38b5e56394f93bac86e1dc36199759d66936e` | 6 | 6 | 6 | 6 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (29).msg` | 2026-06-11 10:27:10 UTC | `9c584267eda626a8ca6e4a255b1657e9f01e24bfd54dc9e8e8b2e4b472804201` | 17 | 17 | 17 | 17 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (28).msg` | 2026-06-12 10:44:11 UTC | `b409001ad16557bc01e6fab37255c76a73a9d45e5c7bce5c17a80acec8b25548` | 19 | 19 | 19 | 19 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (27).msg` | 2026-06-15 11:05:01 UTC | `aa30359f4f55e7470d360fe1a2a5c4d07420f825511d0fedd8541aea02857ee3` | 26 | 26 | 26 | 26 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (26).msg` | 2026-06-16 11:05:19 UTC | `55b6f5212b8f62617f9f417a62024a403a11276750cfc672eaf6dde8dc8ce4a6` | 19 | 19 | 19 | 19 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (25).msg` | 2026-06-17 11:09:37 UTC | `804829533b1294b3916e23a26635b62f7b60ffa344102e3d48046cca175e3fbe` | 8 | 8 | 8 | 8 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (24).msg` | 2026-06-18 11:07:12 UTC | `a486c9279692da6d86bda53833c557e7964ff57003b7b2bf116c032d8619a6c1` | 10 | 10 | 10 | 10 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (23).msg` | 2026-06-19 11:31:04 UTC | `59da6775a775e236639a63db587fe40b2a824beeafaecd0da00e14d8d25687ea` | 10 | 10 | 10 | 10 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (22).msg` | 2026-06-22 11:40:51 UTC | `52d7a3452fa2cd6da89df54157481ac8e79ae2c8c67867d1cdfed730fe654b06` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (21).msg` | 2026-06-23 10:12:25 UTC | `b4aaf118a5dbb60fa8966a504ed9328ed53183f410d3308cf1413e61c587684a` | 5 | 5 | 5 | 5 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (20).msg` | 2026-06-24 10:26:46 UTC | `2a5ef2e6f4c3c78ab150913ae43017643979509811cd3e7278f8086af3cf7af5` | 8 | 8 | 8 | 8 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (19).msg` | 2026-06-25 10:42:28 UTC | `e2b32e55ae1fa749845d3faac0ed6051ecc14572405764faa99bb57b7663defb` | 11 | 11 | 11 | 11 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (18).msg` | 2026-06-26 10:53:09 UTC | `fe6439f5959a926e7f18a4bb0ab538b42cf71d16fd212c14b4659510f32eabee` | 15 | 15 | 15 | 15 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (17).msg` | 2026-06-29 11:16:29 UTC | `7de2afd31886d8c4883b6b6ac1293e0c6909adf057058fef0759619e68204873` | 6 | 6 | 6 | 6 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (16).msg` | 2026-06-30 11:18:13 UTC | `5db2a6422870662b75aeb61512f9cdb1ac222e8e786dc77cbff590dd5b8a948d` | 10 | 10 | 10 | 10 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (15).msg` | 2026-07-01 11:04:57 UTC | `6ba1d646863234b38dd4ebef778fdacf01ba1d8fa62dd8d40cb0294122586d1d` | 7 | 7 | 7 | 7 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (14).msg` | 2026-07-01 16:52:17.681686 UTC | `4a3d160d7fb96487246b8fb94e3f38328fedf1f5b7d10a843934df55544da7e8` | 7 | 7 | 7 | 0 | 7 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (13).msg` | 2026-07-02 11:06:40 UTC | `addaf2ed79788cc0e847e3e767909fe9316864ac2da1476fed476eb540238191` | 18 | 18 | 18 | 18 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (12).msg` | 2026-07-02 11:23:26.700952 UTC | `c3ab5202ec20382a6b2a46a6be5b100ff2b2545bcd5b80a36cfebea427c56fff` | 18 | 18 | 18 | 0 | 18 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (11).msg` | 2026-07-03 10:55:09 UTC | `538f6517055faa733128d73d4dacf2a80e6516917f921dc3ddf5403ae06667a9` | 4 | 4 | 4 | 4 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (10).msg` | 2026-07-06 10:38:50 UTC | `1074dfaad2575f471f35240e382429a0e01e8f8348f3bdd995caf2f7d4f7fd52` | 10 | 10 | 10 | 10 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (9).msg` | 2026-07-07 10:41:44 UTC | `1d833b061d764da22b6e025f7cd44b547ad0d4fa350f71d7f9744a50ffa5b528` | 9 | 9 | 9 | 9 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (8).msg` | 2026-07-08 10:39:29 UTC | `75d1654d9e401f058cd0e8f60549703d0f1dae6012e307ce626bbe78b04dcf35` | 12 | 12 | 12 | 12 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (7).msg` | 2026-07-09 10:36:59 UTC | `8d67acae81f4c139c04c76cac61ebd7b27ddab03cb0a84f1b9dad8f0cef5abf6` | 6 | 6 | 6 | 6 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (6).msg` | 2026-07-10 10:37:59 UTC | `c67dbab3061959c90dd19936092563b3f2e93b95c9c85c8444ae678d1ca725c6` | 8 | 8 | 8 | 8 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (5).msg` | 2026-07-13 10:48:52 UTC | `6929b44309b9bd257b51faac21a7eec70aecd2946f2221f94b48e793ea1b0b09` | 10 | 10 | 10 | 10 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (4).msg` | 2026-07-14 10:28:57 UTC | `d1c4a9a4a43ba9273483e06255372c390394124e630a81f8862552e340109afe` | 6 | 6 | 6 | 6 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (3).msg` | 2026-07-15 10:28:44 UTC | `5aead34037e237a5f5245fd65523a5fc7dbc8ea33ff3f0dc4d3f2c2c9d216924` | 5 | 5 | 5 | 5 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (2).msg` | 2026-07-16 11:09:54 UTC | `43946a2814ca86b6fdda762c74554875c844a82a0ac8c29d6c15d47a15ca9190` | 8 | 8 | 8 | 8 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022 (1).msg` | 2026-07-17 10:16:40 UTC | `63ff1fde70a5281e579739f253ac2bfaa30a9699198b795086f5084a4316a6f5` | 10 | 10 | 10 | 10 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022(1).msg` | 2026-07-20 11:04:18 UTC | `8cd089bc81762ffa9fa231b32c56bdea3e91283fa3021ef2d7aceed5f85f5a09` | 6 | 6 | 6 | 6 | 0 | 0 | 0 | ok |
| `LICITACIONES - Envío de Novedades - 149022.msg` | 2026-07-20 11:04:18 UTC | `3c826e0c810afe192ac7c6f166339afc185433aecd568ff1a1512442bc644fa1` | 6 | 6 | 6 | 0 | 6 | 0 | 0 | ok |

## Duplicidades propias del corpus

Las 31 duplicidades están explicadas íntegramente por tres parejas de correos cuyos bloques y campos canónicos son idénticos:

| Original en orden cronológico | Copia repetida | Bloques duplicados |
|---|---|---:|
| `LICITACIONES - Envío de Novedades - 149022 (15).msg` | `LICITACIONES - Envío de Novedades - 149022 (14).msg` | 7 |
| `LICITACIONES - Envío de Novedades - 149022 (13).msg` | `LICITACIONES - Envío de Novedades - 149022 (12).msg` | 18 |
| `LICITACIONES - Envío de Novedades - 149022(1).msg` | `LICITACIONES - Envío de Novedades - 149022.msg` | 6 |
| **Total** | | **31** |

No hay ninguna referencia repetida con una variante material de expediente, organismo, objeto, provincia, presupuesto, plazo, enlaces o fuente.

## Referencias con `idExpediente=`

Las 20 referencias únicas derivadas de los binarios son:

- `2026075468`
- `2026075494`
- `2026078371`
- `2026083500`
- `2026085310`
- `2026085326`
- `2026085327`
- `2026085329`
- `2026087660`
- `2026089334`
- `2026090315`
- `2026090380`
- `2026090788`
- `2026093711`
- `2026094543`
- `2026094546`
- `2026095946`
- `2026100463`
- `2026103762`
- `2026103763`

En total aparecen 25 veces porque cinco de ellas vuelven a aparecer en las copias de correos duplicadas.

Confirmación específica:

- `2026103762` conserva el expediente `CONTR 2026 0000264070`.
- `2026103763` conserva el expediente `CONTR 2026 0000264400`.

La subcadena `idExpediente=` solo forma parte del canal URL y no altera `Nº Expediente`.

## Órdenes de ejecución

Cada modalidad usa una SQLite temporal nueva. El hash de referencias finales es común a todas: `bfa7b661c16083b509bb7bb20d5c6257f7afbe9fe0d1052a6c9deb4c7b1a0cff`.

| Orden | Correos | Detect. | Insert. | Dup. | Conf. | Cuar. | Sin cat. | Únicas | Hash del orden |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `chronological` | 39 | 396 | 365 | 31 | 0 | 0 | 0 | 365 | `ad5d2f3ee2a010adf9a8a4ce51103f0ca061f759bbe336b94952efbb5ee4f373` |
| `reverse_chronological` | 39 | 396 | 365 | 31 | 0 | 0 | 0 | 365 | `100fc23d87b9e33288eda0ff7b0f1c098fae730abebb73093aa5a414406d41e6` |
| `random_seed_20260720` | 39 | 396 | 365 | 31 | 0 | 0 | 0 | 365 | `fb6f27bea2e8a9a79ca2f04feb0502d9ccccddecdea365adc0ac2cba49321696` |
| `duplicate_copies_before_originals` | 39 | 396 | 365 | 31 | 0 | 0 | 0 | 365 | `cb2a81fa15c6d71c8975ba7efa126425236735d9e7447c8e8e901fb4a81d8e26` |
| `originals_before_duplicate_copies` | 39 | 396 | 365 | 31 | 0 | 0 | 0 | 365 | `53193bf231ce1de4619d8adc842348b8ff4904f67a051731377a18a9915b5cea` |

El orden aleatorio se generó dos veces con semilla `20260720` y produjo exactamente la misma secuencia. Ningún conflicto depende del orden.

## Segunda ejecución completa

La segunda ejecución se realizó sobre la misma SQLite temporal ya cargada cronológicamente:

| Detect. | Insert. | Dup. | Conf. | Cuar. | Sin cat. | Únicas finales |
|---:|---:|---:|---:|---:|---:|---:|
| 396 | 0 | 396 | 0 | 0 | 0 | 365 |

Las 396 duplicidades de esta segunda pasada no se suman a las 31 duplicidades propias de la primera carga del corpus. En la segunda pasada todas las apariciones —incluidas las 365 que fueron nuevas al principio— encuentran ya su referencia y contenido idéntico en la SQLite temporal.

## Defectos y correcciones de esta fase

No apareció ningún defecto del extractor ni del parser al contrastarlos con los 39 MSG: cero diferencias de metadatos, conteo, orden, referencia o campo.

Sí se cerraron tres carencias del harness de validación previo:

1. Ahora compara conjunto exacto de nombres, tamaños y SHA-256 contra el inventario y el manifiesto, y rechaza ausentes, sobrantes, vacíos o discrepancias.
2. Ahora informa por correo y ejecuta cronológico, inverso, aleatorio reproducible, duplicados primero, originales primero y segunda carga sobre la misma SQLite.
3. La lectura del contenedor MSG se extrajo a `infonalia_msg_reader.py` para que harness e importación manual usen exactamente el mismo adaptador.

No se añadieron excepciones por fichero o referencia, no se codificaron resultados del manifiesto en el parser y no se rebajó ningún control fail-closed.

## Archivos incorporados o modificados en esta fase

- `.gitignore`: permite versionar exclusivamente los MSG de esta fixture controlada.
- `webapp/infonalia_webapp/infonalia_msg_reader.py`: adaptador MSG común.
- `webapp/infonalia_webapp/infonalia_corpus_harness.py`: inventario, metadatos, tabla por correo, órdenes e idempotencia.
- `webapp/infonalia_webapp/app.py`: importación manual delegada al lector MSG común.
- `webapp/infonalia_webapp/tests/test_infonalia_import_core.py`: regresión obligatoria de los 39 MSG y todas las modalidades.
- `webapp/infonalia_webapp/tests/fixtures/infonalia/corpus_real_20260720/`: 39 binarios y los tres controles originales del ZIP.
- `docs/INFORME_VALIDACION_IMPORTADOR_INFONALIA.md`: este informe.

La implementación principal previa de `infonalia_import_core.py`, `infonalia_mail_importer.py`, `monitor/scheduler.py`, `.env.example` y sus pruebas se conservó salvo la integración mínima del lector manual común.

## Pruebas finales

| Validación | Resultado |
|---|---|
| Inspección segura del ZIP | 42 entradas válidas; 39 MSG y 3 controles |
| SHA-256 | 39/39 coinciden con inventario y manifiesto |
| Harness completo | Código 0; `ok=true`; 39/396/365/31/25/20 |
| Cinco órdenes | Todos 365 insertados, 31 duplicados, 0 conflictos/cuarentenas |
| Segunda ejecución | 0 insertados, 396 duplicados |
| Pruebas dirigidas parser/adversariales/manual/IMAP/scheduler | `82 passed in 95.43s` |
| Suite general | `1477 passed in 344.84s` |
| Pruebas omitidas para lograr verde | Ninguna |
| `compileall -q webapp herramientas_python` | Correcto |
| `git diff --check` | Correcto; solo avisos informativos CRLF, sin errores |

La prueba real de corpus forma parte de la suite y no está marcada como `skip`.

## Confirmación expresa de aislamiento

- No se abrió ni modificó la SQLite real.
- Todas las persistencias del harness se realizaron en SQLite dentro de directorios temporales.
- No se conectó a IMAP real ni se marcó ningún correo real como leído.
- No se usó SMTP real.
- No se escribió en Dropbox.
- No se usó Telegram.
- No se ejecutó el scheduler real.
- No se ejecutaron ni modificaron tareas programadas de Windows.
- No se ejecutaron descargadores ni backups reales.
- No se leyó ni modificó el `.env` privado.
- No se activó `LLANGON_INFONALIA_STRICT_IMPORT_ENABLED`.
- No se cambió configuración de producción.
- No se desplegó.
- No se reprocesó ningún mensaje del buzón real.

La activación del feature flag y cualquier reprocesamiento histórico quedan expresamente fuera de esta validación y requieren autorización posterior separada.
