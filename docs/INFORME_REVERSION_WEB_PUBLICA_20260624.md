# Informe de reversion de web publica

Fecha: 24/06/2026

## Resumen

Se ha revertido la web publica activa de ASESORES LLANGON, S.L. a la version anterior al redisenyo completo.

La decision tomada es no rehacer la web publica desde cero, sino volver a la base anterior y aplicar retoques pequenos e incrementales a partir de esa version.

## Motivo

La nueva version publica generada el 24/06/2026 no convencio visualmente. Aunque estaba mas estructurada en paginas estaticas separadas, el resultado se percibio menos adecuado que la version previa.

Se vuelve a la version anterior para trabajar sobre una base ya conocida.

## Carpeta activa

La carpeta activa de la web publica sigue siendo:

`firebase/public_firebase`

Esa carpeta contiene ahora de nuevo la version anterior:

- `index.html`
- `static/public.css`
- `static/public.js`
- `static/logo-llangon.png`
- `static/assets/public-hero-procurement.png`

La version restaurada funciona como una SPA estatica: las rutas principales se resuelven desde `public.js`.

## Rutas de la version restaurada

La version anterior usa estas rutas:

- `/`
- `/servicios`
- `/metodologia`
- `/contratacion-publica`
- `/noticias`
- `/noticias/<slug>`
- `/zona-privada`
- `/contacto`
- `/aviso-legal`
- `/politica-privacidad`
- `/politica-cookies`

No usa las rutas nuevas:

- `/como-trabajamos/`
- `/nosotros/`
- `/recursos/`
- `/accesibilidad/`

## Configuracion Firebase

Se mantiene la configuracion limpia en la raiz del proyecto:

`firebase.json`

El hosting sigue apuntando a:

`firebase/public_firebase`

Se han eliminado de `firebase.json` las redirecciones de la version nueva, porque rompian la navegacion anterior:

- `/metodologia -> /como-trabajamos/`
- `/noticias -> /recursos/`
- `/zona-privada -> /contacto/`

Se conserva el header:

`X-Robots-Tag: noindex, nofollow`

para que la web de prueba no se indexe mientras no exista autorizacion para publicacion definitiva.

## Backup antes de revertir

Antes de restaurar se guardo una copia de la version nueva sustituida en:

`.local_backups/web_publica_revert_current_20260624_120000/version_actual_reemplazada`

La fuente usada para restaurar la version anterior fue:

`.local_backups/public_firebase_20260624_104312`

## Cambios conservados

Se conserva el texto de portada ya aprobado:

`Especialistas en contratación pública y asistencia en preparación de ofertas`

Tambien se mantiene el enlace desde el login privado hacia la web publica de prueba:

`https://llangon-web-publica-prueba.web.app/`

## Validaciones realizadas

- `node --check firebase/public_firebase/static/public.js`: correcto.
- `python -m json.tool firebase.json`: correcto.
- `pytest webapp/infonalia_webapp/tests/test_web_security.py -q`: 32 tests correctos.

Aviso: pytest mostro un warning por no poder escribir cache local en `.pytest_cache`, sin afectar al resultado de las pruebas.

## Estado pendiente

La URL publica de Firebase:

`https://llangon-web-publica-prueba.web.app/`

seguira mostrando la version que haya desplegada en Firebase hasta ejecutar un nuevo despliegue.

Para publicar esta reversion hay que lanzar de nuevo `firebase deploy` desde la raiz del proyecto, verificando antes el proyecto Firebase activo.

## Criterio para siguientes cambios

A partir de ahora, los cambios sobre la web publica deben hacerse de forma incremental:

1. tocar una seccion concreta;
2. revisar visualmente;
3. validar en movil y escritorio;
4. desplegar solo cuando el resultado este aprobado.
