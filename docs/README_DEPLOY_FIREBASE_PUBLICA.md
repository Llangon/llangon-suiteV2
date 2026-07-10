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
- `/contacto/`
- `/aviso-legal/`
- `/politica-privacidad/`
- `/politica-cookies/`

## Notas

- `.firebaserc` es local y no se versiona; solo se conserva el ejemplo.
- El enlace `Acceso a zona privada` apunta temporalmente a contacto hasta confirmar la URL privada estable.
- La web publica es una SPA estatica servida por Firebase Hosting; las rutas anteriores se resuelven con rewrites a `index.html`.
- La seccion de noticias usa contenido estatico del bundle publico y no depende de `/api/public/noticias`.
- Los datos legales pendientes estan documentados en `docs/DATOS_LEGALES_PENDIENTES.md`.
