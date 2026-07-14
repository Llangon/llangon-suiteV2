# Inventario de web publica

Fecha de revision: 24/06/2026

Actualizacion posterior: el 24/06/2026 se revirtio la web publica a la version anterior al redisenyo completo. Ver `docs/INFORME_REVERSION_WEB_PUBLICA_20260624.md`.

Actualizacion 10/07/2026: se retiro la copia publica antigua que seguia dentro de la app privada. La app privada queda solo para trabajo interno y la web publica activa queda exclusivamente en `firebase/public_firebase`.

Actualizacion 13/07/2026: se reorganizo la SPA publica con enfoque comercial, se retiraron de la navegacion las noticias ficticias y el acceso privado no operativo, y se anadio una version WebP optimizada de la imagen principal. La aplicacion privada no se modifico.

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
| `webapp/infonalia_webapp/static/public.html` | Version publica antigua integrada en la app privada | Ya retirada del flujo activo | Eliminado |
| `webapp/infonalia_webapp/static/public.css` | Estilos de la version publica antigua integrada en la app privada | Ya retirada del flujo activo | Eliminado |
| `webapp/infonalia_webapp/static/public.js` | Script de la version publica antigua integrada en la app privada | Ya retirado del flujo activo | Eliminado |
| `webapp/infonalia_webapp/static/assets/public-hero-procurement.png` | Imagen de la version publica antigua integrada en la app privada | Ya retirada del flujo activo | Eliminado |
| `.local_backups/public_firebase_20260624_104312/` | Backup anterior de la web publica | No activo | Conservar como backup historico |
| `.venv/**/build` | Carpeta interna de dependencias Python | No relacionada con la web publica | No tocar |

## Contenido de la carpeta activa

Tras la reversion, `firebase/public_firebase/` contiene actualmente:

- `index.html`;
- `static/public.css`;
- `static/public.js`;
- `static/logo-llangon.png`;
- `static/assets/public-hero-procurement.png`;
- `static/assets/public-hero-procurement.webp`.

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

La app privada ya no conserva una version publica activa dentro de `webapp/infonalia_webapp/static/`.

`http://127.0.0.1:8787/` queda reservado para la aplicacion privada y redirige a `/login` o `/app`.

La web publica activa queda en `firebase/public_firebase` y se revisa en local con la vista previa publica en `http://127.0.0.1:5500/`.

## Backup de esta limpieza

Backup creado:

`.local_backups/web_publica_cleanup_20260624_112340`

Debe incluir:

- configuracion Firebase anterior;
- ejemplo `.firebaserc.example` anterior;
- cache `.firebase/` si existe;
- README de despliegue anterior;
- copia de la version publica antigua integrada en la app privada, solo como respaldo documental, sin moverla de su ubicacion.
