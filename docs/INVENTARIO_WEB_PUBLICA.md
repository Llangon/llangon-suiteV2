# Inventario de web publica

Fecha de revision: 24/06/2026

Actualizacion posterior: el 24/06/2026 se revirtio la web publica a la version anterior al redisenyo completo. Ver `docs/INFORME_REVERSION_WEB_PUBLICA_20260624.md`.

Objetivo de esta limpieza: dejar una unica carpeta activa y clara para la web publica nueva:

`firebase/public_firebase`

La aplicacion privada queda fuera de esta limpieza y sigue en:

`http://127.0.0.1:8787/`

## Resumen

| Ruta | Clasificacion | Referencias | Recomendacion |
| --- | --- | --- | --- |
| `firebase/public_firebase/` | Version activa de la web publica nueva | Referenciada por documentacion del proyecto y por los tests de seguridad publica | Conservar como unica carpeta activa de contenido web publico |
| `firebase/public_firebase/firebase.json` | Configuracion Firebase colocada dentro de la carpeta publicada | Configuraba `hosting.public` como `.` porque se ejecutaba desde esa carpeta | Movido a backup y sustituido por `firebase.json` en la raiz del proyecto apuntando a `firebase/public_firebase` |
| `firebase/public_firebase/.firebaserc.example` | Ejemplo de configuracion Firebase | No era contenido web | Movido a backup y recreado como `.firebaserc.example` en la raiz |
| `firebase/public_firebase/.firebase/` | Cache/metadatos locales de Firebase | No era contenido web ni configuracion fuente | Movido a backup |
| `firebase/public_firebase/README_DEPLOY_FIREBASE.md` | Documentacion de despliegue dentro de la carpeta publicada | Podia publicarse accidentalmente como fichero estatico | Movido a backup y sustituido por `docs/README_DEPLOY_FIREBASE_PUBLICA.md` |
| `webapp/infonalia_webapp/static/public.html` | Version publica antigua integrada en la app privada | Usada por `webapp/infonalia_webapp/app.py` mediante `send_public_page()` | No tocar en esta limpieza para no romper la app privada |
| `webapp/infonalia_webapp/static/public.css` | Estilos de la version publica antigua integrada en la app privada | Servida desde `/static/public.css` por la app privada | No tocar en esta limpieza para no romper la app privada |
| `webapp/infonalia_webapp/static/public.js` | Script de la version publica antigua integrada en la app privada | Servido desde `/static/public.js` por la app privada y cubierto por tests | No tocar en esta limpieza para no romper la app privada |
| `webapp/infonalia_webapp/static/assets/public-hero-procurement.png` | Imagen de la version publica antigua integrada en la app privada | Usada por la version publica antigua | No tocar en esta limpieza para no romper la app privada |
| `.local_backups/public_firebase_20260624_104312/` | Backup anterior de la web publica | No activo | Conservar como backup historico |
| `.venv/**/build` | Carpeta interna de dependencias Python | No relacionada con la web publica | No tocar |

## Contenido de la carpeta activa

Tras la reversion, `firebase/public_firebase/` contiene actualmente:

- `index.html`;
- `static/public.css`;
- `static/public.js`;
- `static/logo-llangon.png`;
- `static/assets/public-hero-procurement.png`.

La version actual vuelve a ser una SPA estatica. Las rutas publicas se resuelven desde `static/public.js`.

## Firebase Hosting

Estado previo:

- No habia `firebase.json` en la raiz del proyecto.
- Existia `firebase/public_firebase/firebase.json` con `hosting.public` igual a `.`, valido solo si se ejecuta Firebase desde dentro de `firebase/public_firebase`.

Resultado aplicado:

- creado `firebase.json` en la raiz del proyecto;
- configurado `hosting.public` como `firebase/public_firebase`;
- `firebase/public_firebase` queda como carpeta de contenido web estatico.

## Relacion con la app privada

La app privada conserva una version publica antigua dentro de `webapp/infonalia_webapp/static/`.

No se mueve en esta limpieza porque sigue referenciada por:

- `webapp/infonalia_webapp/app.py`, funcion `send_public_page()`;
- tests de seguridad sobre `public.html` y `public.js`;
- rutas publicas servidas por el servidor local.

Recomendacion futura: cuando la web publica de Firebase sea definitiva, decidir si la app privada debe retirar esas rutas, redirigir a la web publica o conservarlas como pagina de emergencia.

## Backup de esta limpieza

Backup creado:

`.local_backups/web_publica_cleanup_20260624_112340`

Debe incluir:

- configuracion Firebase anterior;
- ejemplo `.firebaserc.example` anterior;
- cache `.firebase/` si existe;
- README de despliegue anterior;
- copia de la version publica antigua integrada en la app privada, solo como respaldo documental, sin moverla de su ubicacion.
