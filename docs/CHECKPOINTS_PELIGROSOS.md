# Checkpoints peligrosos

Este documento fija la puerta de entrada para cambios de alto riesgo en Llangon-SuiteV2.

No sustituye a `ARQUITECTURA_FUTURA.md`; resume las condiciones minimas para avanzar cuando una fase toque zonas que pueden romper datos, seguridad o flujo operativo.

## Ambito

Se considera checkpoint peligroso cualquier fase que toque:

- SQLite;
- migraciones;
- CSRF global;
- StorageBackend;
- noticias Markdown;
- refactor de `app.py`.

## Reglas generales

- No mezclar dos checkpoints peligrosos en el mismo commit.
- No cambiar endpoints ni respuestas JSON salvo que la fase lo declare expresamente.
- No cambiar esquema SQLite sin plan de migracion, backup y tests especificos.
- No introducir dependencias nuevas sin documentar motivo, impacto y alternativa descartada.
- No ejecutar descargadores reales ni red externa en tests.
- No usar datos reales en fixtures.
- No hacer push desde el checkpoint.

## Antes de editar

1. Verificar arbol limpio con `git status --short --untracked-files=all`.
2. Identificar ficheros afectados y superficie de comportamiento.
3. Escribir en la fase correspondiente:
   - objetivo;
   - alcance;
   - fuera de alcance;
   - riesgos;
   - plan de rollback.
4. Confirmar que existe un test previo o crear uno antes de cambiar comportamiento.

## Durante la fase

- Mantener cambios pequenos y revisables.
- Preferir contratos puros antes de conectar con `app.py`.
- Usar SQLite temporal en tests cuando sea imprescindible.
- Simular red, descargas, SMTP y procesos externos.
- Mantener Firebase y macros fuera salvo que la fase los nombre expresamente.

## Checks minimos

Ejecutar antes del commit:

```powershell
git status --short --untracked-files=all
python -m compileall webapp herramientas_python
python -m pytest -q
node --check webapp/infonalia_webapp/static/app.js
node --check webapp/infonalia_webapp/static/login.js
node --check firebase/public_firebase/static/public.js
git diff --check
```

Si `python -m pytest -q` falla por entorno, no instalar dependencias globales. Documentar el comando exacto para el dueno del proyecto y dejar la fase sin commit de checkpoint peligroso.

## Commit local

Si los checks pasan:

1. Revisar `git diff --stat`.
2. Revisar que no haya `.pytest_cache/`, `__pycache__/`, temporales, descargas ni datos reales pendientes.
3. Crear commit local con mensaje claro.
4. Verificar de nuevo `git status --short --untracked-files=all`.

No hacer push.

## Evidencia esperada en el informe

- Commit local creado.
- Checks ejecutados y resultado.
- Lista de archivos modificados.
- Confirmacion de que no se usaron datos reales.
- Confirmacion de que no se ejecuto red ni descargadores reales.
- Riesgos pendientes y siguiente fase recomendada.
