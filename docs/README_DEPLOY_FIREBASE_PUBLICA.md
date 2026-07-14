# Publicar la web publica en Firebase Hosting

Carpeta activa de la web publica:

`firebase/public_firebase`

Configuracion activa de Firebase Hosting:

`firebase.json`

Esta carpeta contiene solo la web publica estatica. No incluye la aplicacion privada.

La version de prueba esta configurada como `noindex, nofollow` mediante:

- meta robots en las paginas;
- `robots.txt`;
- header `X-Robots-Tag` en `firebase.json`.

No retirar esa configuracion hasta tener dominio definitivo y autorizacion expresa.

## Pasos

1. Confirmar que la web no contiene datos privados.
2. Copiar `.firebaserc.example` como `.firebaserc` en la raiz del proyecto.
3. Sustituir `REPLACE_WITH_FIREBASE_PROJECT_ID` por el proyecto autorizado.
4. Abrir una terminal en la raiz del proyecto.
5. Instalar la herramienta de Firebase si fuera necesario:

```bash
npm install -g firebase-tools
```

6. Iniciar sesion en Google:

```bash
firebase login
```

7. Confirmar o asociar esta carpeta al proyecto de prueba autorizado:

```bash
firebase use --add
```

8. Revisar los archivos que se publicaran.
9. Publicar solo con autorizacion expresa y verificando que el destino es el proyecto de prueba:

```bash
firebase deploy
```

## Rutas principales

- `/`
- `/servicios/`
- `/metodologia/`
- `/contratacion-publica/`
- `/noticias/`
- `/zona-privada/`
- `/contacto/`
- `/aviso-legal/`
- `/politica-privacidad/`
- `/politica-cookies/`

## Notas

- `.firebaserc` es local y no se versiona; solo se conserva el ejemplo.
- `Noticias` y `Acceso a zona privada` no se muestran en la navegacion ni en el pie mientras no exista contenido real o una URL externa estable.
- La web publica es una SPA estatica servida por Firebase Hosting; las rutas anteriores se resuelven con rewrites a `index.html`.
- La ruta `/noticias/` muestra un estado vacio honesto y no contiene noticias ficticias ni depende de la aplicacion privada.
- La ruta `/zona-privada/` es auxiliar y solo ofrece contacto mientras no exista un acceso externo configurado.
- La imagen principal usa `public-hero-procurement.webp` con el PNG original como respaldo.
- Los datos legales pendientes estan documentados en `docs/DATOS_LEGALES_PENDIENTES.md`.
